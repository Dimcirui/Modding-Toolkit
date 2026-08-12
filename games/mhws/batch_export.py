import bpy
import copy
import json
import os
import shutil

from ..re9.batch_export import _do_export_mesh, _do_export_mdf2, _do_export_chain2, _do_export_clsp
from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available
from ...core import console_export
from ...core import export_prep
from ...core.i18n import T

# MHWs 游戏级文件后缀常量
MHWS_EXTS = {
    "mesh":   "mesh.241111606",
    "mdf2":   "mdf2.45",
    "chain2": "chain2.14",
    "clsp":   "clsp.3",
    "gpuc":   "gpuc.241111760",
}

# 5个固定部位（内部/日志用英文名；UI 绘制处按 id 通过 _PART_LABEL_KEYS 查表动态翻译）
MHWS_PARTS = [
    ("1", "Arm"),
    ("2", "Body"),
    ("3", "Helmet"),
    ("4", "Leg"),
    ("5", "Waist"),
]

# T() key for each part id, looked up at draw time in batch_export_ui.py
_PART_LABEL_KEYS = {
    "1": "mhws.batch_export.part_arm",
    "2": "mhws.batch_export.part_body",
    "3": "mhws.batch_export.part_helmet",
    "4": "mhws.batch_export.part_leg",
    "5": "mhws.batch_export.part_waist",
}

# 4种套装变体
# NOTE: consumed by ui/main_panel.py's `mhws_armor_variant` EnumProperty with a
def get_mhws_variants(self=None, context=None):
    return [
        ("ff", T("mhws.batch_export.variant_ff"), ""),
        ("fm", T("mhws.batch_export.variant_fm"), ""),
        ("mf", T("mhws.batch_export.variant_mf"), ""),
        ("mm", T("mhws.batch_export.variant_mm"), ""),
    ]

# 默认每套装备包含的文件类型
# 未来可在 armor_set JSON 中通过 "file_types" 字段覆盖，例如:
# { "id": "...", "file_types": ["mesh", "mdf2"] }  ← 只有 mesh 和 mdf2，无物理
DEFAULT_FILE_TYPES = ["mesh", "mdf2", "chain2", "clsp"]

# 规范导出顺序，确保不管 JSON 数据怎么存都按此顺序处理
_CANONICAL_FILE_TYPE_ORDER = ["mesh", "mdf2", "chain2", "clsp", "gpuc"]
_CANONICAL_FILE_TYPE_INDEX = {ft: i for i, ft in enumerate(_CANONICAL_FILE_TYPE_ORDER)}


def _canonical_order_file_types(fts):
    """将 file_types 列表按规范顺序排列，未知类型追加到末尾"""
    return sorted(fts, key=lambda ft: _CANONICAL_FILE_TYPE_INDEX.get(ft, len(_CANONICAL_FILE_TYPE_ORDER)))

_EXPORT_FUNCS = {
    "mesh":   _do_export_mesh,
    "mdf2":   _do_export_mdf2,
    "chain2": _do_export_chain2,
    "clsp":   _do_export_clsp,
}


def _get_mhws_schemes_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(addon_dir, "assets", "mhws", "armor_sets")
    os.makedirs(d, exist_ok=True)
    return d


_scheme_cache = []

def get_mhws_schemes_callback(self, context):
    global _scheme_cache
    _scheme_cache = []
    d = _get_mhws_schemes_dir()
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            name = os.path.splitext(f)[0]
            _scheme_cache.append((f, name, ""))
    if not _scheme_cache:
        _scheme_cache.append(('NONE', T("core.export_prep.no_armor_pack"), ""))
    return _scheme_cache


def _load_scheme(filename):
    if not filename or filename == 'NONE':
        return None
    filepath = os.path.join(_get_mhws_schemes_dir(), filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


_armor_cache = []

def get_mhws_armor_callback(self, context):
    """动态回调：根据当前选中的 scheme 文件列出装备"""
    global _armor_cache
    _armor_cache = []
    scheme = _load_scheme(self.mhws_armor_scheme)
    if scheme:
        for armor in scheme.get("armor_sets", []):
            armor_id = armor["id"]
            name = armor.get("name", armor_id)
            _armor_cache.append((armor_id, f"{name}  ({armor_id})", ""))
    if not _armor_cache:
        _armor_cache.append(('NONE', T("core.export_prep.no_armor"), ""))
    return _armor_cache


# ── Binding 存储（scene 自定义属性）────────────────────────────
# Key 格式：mhws_{armor_id}_{part}_{filetype}（不含 variant，所有款式共享同一套绑定）

def _make_key(armor_id, variant, part, filetype):
    return f"mhws_{armor_id}_{part}_{filetype}".replace(" ", "_")

def get_binding(scene, armor_id, variant, part, filetype):
    return scene.get(_make_key(armor_id, variant, part, filetype), "")

def set_binding(scene, armor_id, variant, part, filetype, value):
    scene[_make_key(armor_id, variant, part, filetype)] = value


def _get_blank_path(filetype):
    """Return the path to the built-in blank file for the given filetype."""
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, "assets", "blank_files", "mhws", f"blank.{filetype}")


def _resolve_part_file_types(armor_set, part_id):
    """Resolve which file types apply to a specific part.
    Priority: armor_set.parts_file_types[part_id] >
              armor_set.file_types >
              DEFAULT_FILE_TYPES
    """
    parts_fts = armor_set.get("parts_file_types")
    if parts_fts and part_id in parts_fts:
        return parts_fts[part_id]
    return armor_set.get("file_types", DEFAULT_FILE_TYPES)


def _make_filepath(natives_root, base_path, part_id, armor_id, filetype):
    ext = MHWS_EXTS[filetype]
    filename = f"{armor_id}{part_id}.{ext}"
    bp = base_path.replace("/", os.sep)
    return os.path.join(natives_root, bp, part_id, filename)


# ── Bonesystem ────────────────────────────────────────────────

_REFERENCE_FBXSKEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'assets', 'mhws', 'bonesystem', 'ch03_000_9000.fbxskel.7',
)

# Bones whose head position should be snapped to the named parent bone after
# pose copy. This keeps weapon attachment points and HJ helpers in sync.
_BONESYSTEM_SNAP_LIST = [
    ('L_Hand',      'L_Wep_Sub'),
    ('L_Hand',      'L_Wep'),
    ('R_Hand',      'R_Wep_Sub'),
    ('R_Hand',      'R_Wep'),
    ('R_Forearm',   'R_Shield'),
    ('L_UpperArm',  'L_UpperArm_HJ_00'),
    ('R_UpperArm',  'R_UpperArm_HJ_00'),
    ('L_UpperArm',  'L_UpperArmTwist_HJ_00'),
    ('R_UpperArm',  'R_UpperArmTwist_HJ_00'),
    ('L_UpperArm',  'L_UpperArmDouble_HJ_00'),
    ('R_UpperArm',  'R_UpperArmDouble_HJ_00'),
    ('L_Forearm',   'L_ForearmDouble_HJ_00'),
    ('R_Forearm',   'R_ForearmDouble_HJ_00'),
    ('L_Forearm',   'L_Forearm_HJ_00'),
    ('R_Forearm',   'R_Forearm_HJ_00'),
    ('L_Knee',      'L_KneeDouble_HJ_00'),
    ('R_Knee',      'R_KneeDouble_HJ_00'),
]


def _copy_bone_matrices(context, src_arm, dst_arm):
    """
    Copy pose-bone world matrices from src_arm to dst_arm,
    then apply the result as the new rest pose on dst_arm.
    """
    # Read source pose matrices
    context.view_layer.objects.active = src_arm
    bpy.ops.object.mode_set(mode='POSE')
    bone_matrices = {b.name: copy.deepcopy(b.matrix) for b in src_arm.pose.bones}
    bpy.ops.object.mode_set(mode='OBJECT')

    # Apply to destination
    context.view_layer.objects.active = dst_arm
    bpy.ops.object.mode_set(mode='POSE')
    for bone in dst_arm.pose.bones:
        if bone.name in bone_matrices:
            bone.matrix = bone_matrices[bone.name]
            context.view_layer.update()

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.pose.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')


def _do_bonesystem_export(context, settings, variant_armor_id):
    """
    Generate reference skeleton, copy user's armature pose onto it,
    snap helper bones, then write .fbxskel.7 and BoneSystem JSON.

    fbxskel file  → {natives_root}/natives/stm/BoneSystem/{fbxskel_name}.fbxskel.7
    JSON file     → {natives_root}/reframework/data/BoneSystem/{variant_armor_id}2.json

    Returns (ok: bool, message: str).
    """
    from .fbxskel import load_reference_skeleton, export_fbxskel, write_fbxskel

    natives_root  = context.scene.get("mhws_natives_root", "")
    fbxskel_name  = settings.mhws_fbxskel_name.strip()
    user_arm      = settings.mhws_bs_armature

    if not fbxskel_name:
        return False, T("mhws.batch_export.bonesystem_fill_name")
    if user_arm is None or user_arm.type != 'ARMATURE':
        return False, T("mhws.batch_export.bonesystem_select_armature")
    if not os.path.isfile(_REFERENCE_FBXSKEL):
        return False, T("mhws.batch_export.bonesystem_ref_not_found").format(path=_REFERENCE_FBXSKEL)

    # Save context state
    prev_active   = context.view_layer.objects.active
    prev_selected = [o for o in context.selected_objects]
    for o in prev_selected:
        o.select_set(False)

    ref_arm = None
    try:
        # 1. Load reference skeleton
        ref_arm = load_reference_skeleton(_REFERENCE_FBXSKEL)

        # 2. Copy user's bone matrices → reference, apply as rest pose
        _copy_bone_matrices(context, user_arm, ref_arm)

        # 3. Snap helper bones (replaces bpy.ops.view3d.snap_selected_to_active)
        context.view_layer.objects.active = ref_arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = ref_arm.data.edit_bones
        for parent_name, snap_name in _BONESYSTEM_SNAP_LIST:
            if parent_name in eb and snap_name in eb:
                target_head = eb[parent_name].head.copy()
                snap_bone   = eb[snap_name]
                delta       = target_head - snap_bone.head
                snap_bone.head  = target_head
                snap_bone.tail += delta
        bpy.ops.object.mode_set(mode='OBJECT')

        # 4. Export fbxskel binary
        bone_infos = export_fbxskel(ref_arm)
        data       = write_fbxskel(bone_infos)

        fbxskel_dir = os.path.join(natives_root, 'natives', 'stm', 'BoneSystem')
        os.makedirs(fbxskel_dir, exist_ok=True)
        fbxskel_path = os.path.join(fbxskel_dir, fbxskel_name + '.fbxskel.7')
        with open(fbxskel_path, 'wb') as f:
            f.write(data)
        print(f"[MHWs Bonesystem] fbxskel → {fbxskel_path}")

        # 5. Write JSON  (named after the body ID: variant_armor_id + part "2")
        helmet_id = f"{variant_armor_id}2"
        json_dir  = os.path.join(natives_root, 'reframework', 'data', 'BoneSystem')
        os.makedirs(json_dir, exist_ok=True)
        json_path = os.path.join(json_dir, helmet_id + '.json')
        json_data = {
            "HideFace":    settings.mhws_bs_hide_face,
            "HideHair":    settings.mhws_bs_hide_hair,
            "HideSlinger": settings.mhws_bs_hide_slinger,
            "BindFace":    settings.mhws_bs_bind_face,
            "BindPart":    int(settings.mhws_bs_bind_part),
            "FbxPath":     fbxskel_name,
        }
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=4)
        print(f"[MHWs Bonesystem] JSON   → {json_path}")

        return True, T("mhws.batch_export.bonesystem_done").format(fbxskel=fbxskel_name, json=helmet_id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, T("mhws.batch_export.bonesystem_failed").format(err=e)

    finally:
        # Clean up reference armature and restore context
        if ref_arm is not None and ref_arm.name in bpy.data.objects:
            bpy.data.objects.remove(ref_arm, do_unlink=True)
        context.view_layer.objects.active = prev_active
        for o in prev_selected:
            if o.name in bpy.data.objects:
                o.select_set(True)


# ── 导出 Operator ──────────────────────────────────────────────

class MHWS_OT_BatchExport(bpy.types.Operator):
    bl_idname = "mhws.batch_export"
    bl_label = "MHWs Batch Export"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_export.batch_export_desc")

    def _bound_mesh_collections(self, scene, settings):
        """Every distinct mesh collection bound to the selected armor set."""
        armor_id = settings.mhws_selected_armor
        variant = settings.mhws_armor_variant
        seen = set()
        mesh_collections = []
        for part_id, _ in MHWS_PARTS:
            col_name = get_binding(scene, armor_id, variant, part_id, "mesh")
            if col_name and col_name not in seen:
                col = bpy.data.collections.get(col_name)
                if col:
                    mesh_collections.append(col)
                    seen.add(col_name)
        return mesh_collections

    def _cleanup_mesh_collections(self, context, scene, settings):
        """Run RE Mesh cleanup operators on all bound mesh collections before export."""
        if not re_mesh_op_available('delete_loose'):
            self.report({'WARNING'}, T("mhws.batch_export.re_mesh_not_installed_cleanup_skip"))
            return

        mesh_collections = self._bound_mesh_collections(scene, settings)
        if not mesh_collections:
            return

        # mode_set 需要活动物体；无活动物体时必定已在 OBJECT 模式，直接跳过即可，
        # 否则 poll 失败抛 "上下文缺失活动物体"（手动导出有选中物体故不复现）。
        if context.view_layer.objects.active is not None and context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        for col in mesh_collections:
            for obj in [o for o in col.objects if o.type == 'MESH']:
                context.view_layer.objects.active = obj
                obj.select_set(True)
                try: call_re_mesh_op('delete_loose')
                except Exception: pass
                try: call_re_mesh_op('solve_repeated_uvs')
                except Exception: pass
                try: call_re_mesh_op('remove_zero_weight_vertex_groups')
                except Exception: pass
                try:
                    call_re_mesh_op('limit_total_normalize', maxWeights='12')
                except Exception:
                    try:
                        bpy.ops.object.vertex_group_limit_total(limit=12)
                        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
                    except Exception:
                        pass
                obj.select_set(False)

    def execute(self, context):
        show_console = console_export.get_preferences(context).show_console_on_batch_export
        with console_export.kept_open_for_export(show_console):
            return self._execute_with_triangulation(context)

    def _execute_with_triangulation(self, context):
        # Triangulation rides on the modifier stack: RE Mesh Editor exports
        # evaluated geometry, so the mesh data is never touched and the
        # modifiers come off again even if the export raises.
        settings = context.scene.mhw_suite_settings
        if not settings.mhws_triangulate_face:
            return self._run_export(context)
        with export_prep.triangulated_for_export(context.scene.objects, 'mhws') as touched:
            if touched:
                print("[MHWS] triangulating {n} face mesh(es) for export".format(n=len(touched)))
            return self._run_export(context)

    def _run_export(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not re_mesh_op_available('exportfile'):
            self.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        if settings.mhws_cleanup_before_export:
            self._cleanup_mesh_collections(context, scene, settings)

        natives_root = scene.get("mhws_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("core.export_prep.set_mod_root_first"))
            return {'CANCELLED'}

        scheme = _load_scheme(settings.mhws_armor_scheme)
        if not scheme:
            self.report({'ERROR'}, T("mhws.batch_export.cannot_load_armor_pack"))
            return {'CANCELLED'}

        armor_id = settings.mhws_selected_armor
        if not armor_id or armor_id == 'NONE':
            self.report({'ERROR'}, T("mhws.batch_export.select_armor_set_first"))
            return {'CANCELLED'}

        # 找到对应的 armor_set 条目
        armor_set = next((a for a in scheme.get("armor_sets", []) if a["id"] == armor_id), None)
        if not armor_set:
            self.report({'ERROR'}, T("mhws.batch_export.armor_not_found_in_pack").format(id=armor_id))
            return {'CANCELLED'}

        variant = settings.mhws_armor_variant
        variant_data = armor_set.get("variants", {}).get(variant)
        if not variant_data:
            self.report({'ERROR'}, T("mhws.batch_export.armor_no_variant").format(id=armor_id, variant=variant))
            return {'CANCELLED'}

        variant_armor_id = variant_data["armor_id"]
        base_path = variant_data["base_path"].replace("\\", "/")
        parts_mask = armor_set.get("parts_mask", 0b11111)

        export_count = 0
        fail_count = 0
        skip_count = 0
        use_blank = settings.mhws_use_blank_export

        for part_id, part_name in MHWS_PARTS:
            if not (parts_mask & (1 << (int(part_id) - 1))):
                continue
            part_fts = _canonical_order_file_types(
                _resolve_part_file_types(armor_set, part_id))
            for filetype in part_fts:
                filepath = _make_filepath(natives_root, base_path, part_id, variant_armor_id, filetype)
                label = f"{part_name} {filetype.upper()}"

                # gpuc: always copy blank, unconditionally (no collection binding)
                # gpuc files break mods when other files are edited, so must be replaced with blank
                if filetype == "gpuc":
                    blank_src = _get_blank_path("gpuc")
                    if os.path.isfile(blank_src):
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        shutil.copy2(blank_src, filepath)
                        print(f"[MHWs] {label}: BLANK -> {os.path.basename(filepath)}")
                        export_count += 1
                    else:
                        print(f"[MHWs] SKIP gpuc (blank not found): {blank_src}")
                        skip_count += 1
                    continue

                col = get_binding(scene, armor_id, variant, part_id, filetype)
                if not col:
                    if use_blank:
                        blank_src = _get_blank_path(filetype)
                        if os.path.isfile(blank_src):
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
                            shutil.copy2(blank_src, filepath)
                            print(f"[MHWs] {label}: BLANK -> {os.path.basename(filepath)}")
                            export_count += 1
                        else:
                            print(f"[MHWs] SKIP blank (file not found): {blank_src}")
                            skip_count += 1
                    else:
                        skip_count += 1
                    continue
                if col not in bpy.data.collections:
                    print(f"[MHWs] SKIP {label}: collection '{col}' not found")
                    skip_count += 1
                    continue
                try:
                    print(f"[MHWs] {label}: {col} -> {os.path.basename(filepath)}")
                    _EXPORT_FUNCS[filetype](filepath, col)
                    export_count += 1
                except Exception as err:
                    print(f"[MHWs] FAILED {label}: {err}")
                    fail_count += 1

        # ── Bonesystem ──
        if settings.mhws_use_bonesystem:
            ok, msg = _do_bonesystem_export(context, settings, variant_armor_id)
            if ok:
                self.report({'INFO'}, msg)
            else:
                self.report({'WARNING'}, msg)
                fail_count += 1

        if fail_count > 0:
            self.report({'WARNING'}, T("mhws.batch_export.done_with_fail").format(
                export=export_count, fail=fail_count, skip=skip_count))
        else:
            self.report({'INFO'}, T("mhws.batch_export.done").format(export=export_count, skip=skip_count))
        return {'FINISHED'}


class MHWS_OT_SetNativesRoot(bpy.types.Operator):
    bl_idname = "mhws.set_natives_root"
    bl_label = "Set Mod Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_export.set_natives_root_desc")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        path = self.directory.rstrip("/\\")
        # If the user selected the natives folder itself, step up one level
        if os.path.basename(path).lower() == "natives":
            path = os.path.dirname(path)
        context.scene["mhws_natives_root"] = path
        self.report({'INFO'}, f"MHWs Mod root: {path}")
        return {'FINISHED'}


class MHWS_OT_BonesystemSettings(bpy.types.Operator):
    bl_idname = "mhws.bonesystem_settings"
    bl_label = "Bonesystem Export Settings"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_export.bonesystem_settings_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        s = context.scene.mhw_suite_settings
        layout = self.layout
        row = layout.row()
        left  = row.column()
        right = row.column()

        left.label(text=T("mhws.batch_export.hide_options"))
        left.prop(s, "mhws_bs_hide_face")
        left.prop(s, "mhws_bs_hide_hair")
        left.prop(s, "mhws_bs_hide_slinger")

        right.label(text=T("mhws.batch_export.bind_options"))
        right.prop(s, "mhws_bs_bind_face")
        if s.mhws_bs_bind_face:
            right.label(text=T("mhws.batch_export.bind_part"))
            right.prop(s, "mhws_bs_bind_part", text="")

    def execute(self, context):
        return {'FINISHED'}


classes = [
    MHWS_OT_BatchExport,
    MHWS_OT_SetNativesRoot,
    MHWS_OT_BonesystemSettings,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
