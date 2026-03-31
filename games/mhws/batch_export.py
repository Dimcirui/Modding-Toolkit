import bpy
import copy
import json
import os
import shutil

from ..re9.batch_export import _do_export_mesh, _do_export_mdf2, _do_export_chain2, _do_export_clsp

# MHWs 游戏级文件后缀常量
MHWS_EXTS = {
    "mesh":   "mesh.241111606",
    "mdf2":   "mdf2.45",
    "chain2": "chain2.14",
    "clsp":   "clsp.3",
}

# 5个固定部位
MHWS_PARTS = [
    ("1", "手臂"),
    ("2", "身体"),
    ("3", "头盔"),
    ("4", "腿"),
    ("5", "腰"),
]

# 4种套装变体
MHWS_VARIANTS = [
    ("mm", "男猎男套", ""),
    ("mf", "男猎女套", ""),
    ("fm", "女猎男套", ""),
    ("ff", "女猎女套", ""),
]

# 默认每套装备包含的文件类型
# 未来可在 armor_set JSON 中通过 "file_types" 字段覆盖，例如:
# { "id": "...", "file_types": ["mesh", "mdf2"] }  ← 只有 mesh 和 mdf2，无物理
DEFAULT_FILE_TYPES = ["mesh", "mdf2", "chain2", "clsp"]

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
        _scheme_cache.append(('NONE', "无装备包", ""))
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
        _armor_cache.append(('NONE', "无装备", ""))
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
        return False, "Bonesystem: 请填写 FBXSkel 定义名"
    if user_arm is None or user_arm.type != 'ARMATURE':
        return False, "Bonesystem: 请选择一个骨架对象"
    if not os.path.isfile(_REFERENCE_FBXSKEL):
        return False, f"Bonesystem: 找不到参考骨架文件: {_REFERENCE_FBXSKEL}"

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

        return True, f"Bonesystem 完成: {fbxskel_name}.fbxskel.7 / {helmet_id}.json"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Bonesystem 失败: {e}"

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
    """MHWs 装备批量导出"""
    bl_idname = "mhws.batch_export"
    bl_label = "MHWs Batch Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not hasattr(bpy.ops, 're_mesh') or not hasattr(bpy.ops.re_mesh, 'exportfile'):
            self.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        natives_root = scene.get("mhws_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Mod Root 目录（natives 的上级文件夹）")
            return {'CANCELLED'}

        scheme = _load_scheme(settings.mhws_armor_scheme)
        if not scheme:
            self.report({'ERROR'}, "无法加载装备包")
            return {'CANCELLED'}

        armor_id = settings.mhws_selected_armor
        if not armor_id or armor_id == 'NONE':
            self.report({'ERROR'}, "请先选择一套装备")
            return {'CANCELLED'}

        # 找到对应的 armor_set 条目
        armor_set = next((a for a in scheme.get("armor_sets", []) if a["id"] == armor_id), None)
        if not armor_set:
            self.report({'ERROR'}, f"在装备包中未找到: {armor_id}")
            return {'CANCELLED'}

        variant = settings.mhws_armor_variant
        variant_data = armor_set.get("variants", {}).get(variant)
        if not variant_data:
            self.report({'ERROR'}, f"装备 {armor_id} 没有变体: {variant}")
            return {'CANCELLED'}

        variant_armor_id = variant_data["armor_id"]
        base_path = variant_data["base_path"].replace("\\", "/")
        file_types = armor_set.get("file_types", DEFAULT_FILE_TYPES)
        parts_mask = armor_set.get("parts_mask", 0b11111)

        export_count = 0
        fail_count = 0
        skip_count = 0
        use_blank = settings.mhws_use_blank_export

        for part_id, part_name in MHWS_PARTS:
            if not (parts_mask & (1 << (int(part_id) - 1))):
                continue
            for filetype in file_types:
                col = get_binding(scene, armor_id, variant, part_id, filetype)
                filepath = _make_filepath(natives_root, base_path, part_id, variant_armor_id, filetype)
                label = f"{part_name} {filetype.upper()}"
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
            self.report({'WARNING'}, f"完成: 导出 {export_count}, 失败 {fail_count}, 跳过 {skip_count}")
        else:
            self.report({'INFO'}, f"完成: 导出 {export_count}, 跳过 {skip_count}")
        return {'FINISHED'}


class MHWS_OT_SetNativesRoot(bpy.types.Operator):
    """选择 MHWs Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"""
    bl_idname = "mhws.set_natives_root"
    bl_label = "Set Mod Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
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
    """调整 Bonesystem JSON 导出参数"""
    bl_idname = "mhws.bonesystem_settings"
    bl_label = "Bonesystem 导出设置"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        s = context.scene.mhw_suite_settings
        layout = self.layout
        row = layout.row()
        left  = row.column()
        right = row.column()

        left.label(text="隐藏选项:")
        left.prop(s, "mhws_bs_hide_face")
        left.prop(s, "mhws_bs_hide_hair")
        left.prop(s, "mhws_bs_hide_slinger")

        right.label(text="绑定选项:")
        right.prop(s, "mhws_bs_bind_face")
        if s.mhws_bs_bind_face:
            right.label(text="绑定部位:")
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
