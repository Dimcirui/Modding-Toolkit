import bpy
import json
import os
import shutil

from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available


# 部位定义：(代码, 显示名, mask索引)  mask顺序：手腿铠头腰
MHWI_PARTS = [
    ("arm",  "手臂", 0),
    ("leg",  "腿部", 1),
    ("body", "身体", 2),
    ("helm", "头盔", 3),
    ("wst",  "腰部", 4),
]

# 头盔部位代码（特殊处理：无 ctc/ccl，可选 evhl）
HELM_PART = "helm"

# 常规部位的文件类型槽位
REGULAR_FILE_TYPES = ["mod3", "mrl3", "ctc"]

# 头盔的文件类型槽位（无物理）
HELM_FILE_TYPES = ["mod3", "mrl3"]

# SP 独立头部/头发的文件类型槽位（仅模型和材质）
SP_FACE_FILE_TYPES = ["mod3", "mrl3"]
SP_HAIR_FILE_TYPES = ["mod3", "mrl3", "ctc"]

# 导出时写入 MOD3 的默认参数
MOD3_EXPORT_SETTINGS = {
    "autoSolveRepeatedUVs":    True,
    "preserveSharpEdges":      True,
    "useBlenderMaterialName":  False,
    "invisibleMantlesModFix":  True,
    "exportAllLODs":           False,
}


# ── 资源目录 ──────────────────────────────────────────────────────

def _addon_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _get_armor_sets_dir():
    d = os.path.join(_addon_dir(), "assets", "mhwi", "armor_sets")
    os.makedirs(d, exist_ok=True)
    return d

def _get_blank_path(filename):
    return os.path.join(_addon_dir(), "assets", "blank_files", "mhwi", filename)


# ── JSON 加载 ─────────────────────────────────────────────────────

_armor_sets_cache = []

def get_mhwi_armor_sets_callback(self, context):
    global _armor_sets_cache
    _armor_sets_cache = []
    d = _get_armor_sets_dir()
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            name = os.path.splitext(f)[0]
            _armor_sets_cache.append((f, name, ""))
    if not _armor_sets_cache:
        _armor_sets_cache.append(('NONE', "无装备包", ""))
    return _armor_sets_cache


def _load_armor_sets(filename):
    if not filename or filename == 'NONE':
        return None
    filepath = os.path.join(_get_armor_sets_dir(), filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


_hr_armor_cache = []
_mr_armor_cache = []
_sp_armor_cache = []

def get_mhwi_hr_armor_callback(self, context):
    global _hr_armor_cache
    _hr_armor_cache = []
    data = _load_armor_sets(context.scene.mhw_suite_settings.mhwi_armor_sets_file)
    if data:
        for armor in data.get("armor_sets", []):
            if armor.get("rank", "HR") == "HR":
                _hr_armor_cache.append(_armor_enum_item(armor, len(_hr_armor_cache)))
    if not _hr_armor_cache:
        _hr_armor_cache.append(('NONE', "无装备", "", 0))
    return _hr_armor_cache

def get_mhwi_mr_armor_callback(self, context):
    global _mr_armor_cache
    _mr_armor_cache = []
    data = _load_armor_sets(context.scene.mhw_suite_settings.mhwi_armor_sets_file)
    if data:
        for armor in data.get("armor_sets", []):
            if armor.get("rank", "HR") == "MR":
                _mr_armor_cache.append(_armor_enum_item(armor, len(_mr_armor_cache)))
    if not _mr_armor_cache:
        _mr_armor_cache.append(('NONE', "无装备", "", 0))
    return _mr_armor_cache

def get_mhwi_sp_armor_callback(self, context):
    global _sp_armor_cache
    _sp_armor_cache = []
    data = _load_armor_sets(context.scene.mhw_suite_settings.mhwi_armor_sets_file)
    if data:
        for armor in data.get("armor_sets", []):
            if armor.get("rank") == "SP":
                _sp_armor_cache.append(_armor_enum_item(armor, len(_sp_armor_cache)))
    if not _sp_armor_cache:
        _sp_armor_cache.append(('NONE', "无装备", "", 0))
    return _sp_armor_cache

def _armor_enum_item(armor, idx):
    model_id  = armor["id"]
    name      = armor.get("name", model_id)
    variant   = armor.get("variant_label", "")
    label     = f"{name} {variant}  ({model_id})" if variant else f"{name}  ({model_id})"
    return (model_id, label, "", idx)


def get_armor_entry(data, model_id):
    if not data:
        return None
    return next((a for a in data.get("armor_sets", []) if a["id"] == model_id), None)


# ── Binding 存取 ──────────────────────────────────────────────────
# Key 格式：mhwi_{model_id}_{part}_{filetype}
# 空模标志：mhwi_blank_{model_id}_{part}
# ctc 导出 ccl：mhwi_ccl_{model_id}_{part}

def _bkey(model_id, part, filetype):
    return f"mhwi_{model_id}_{part}_{filetype}".replace(" ", "_")

def _blank_key(model_id, part):
    return f"mhwi_blank_{model_id}_{part}".replace(" ", "_")

def _ccl_key(model_id, part):
    return f"mhwi_ccl_{model_id}_{part}".replace(" ", "_")


def get_binding(scene, model_id, part, filetype):
    return scene.get(_bkey(model_id, part, filetype), "")

def set_binding(scene, model_id, part, filetype, value):
    scene[_bkey(model_id, part, filetype)] = value

def get_blank(scene, model_id, part):
    return bool(scene.get(_blank_key(model_id, part), False))

def set_blank(scene, model_id, part, value):
    scene[_blank_key(model_id, part)] = value

def get_export_ccl(scene, model_id, part):
    return bool(scene.get(_ccl_key(model_id, part), True))

def set_export_ccl(scene, model_id, part, value):
    scene[_ccl_key(model_id, part)] = value


# ── 路径构造 ──────────────────────────────────────────────────────

def _make_filepath(natives_root, model_id, gender, part, ext):
    """
    nativePC/pl/{gender}_equip/{model_id}/{part}/mod/{gender}_{part}{numeric}.{ext}
    例: nativePC/pl/f_equip/pl042_0500/arm/mod/f_arm042_0500.mod3
    """
    numeric = model_id[2:]          # "042_0500"
    rel = os.path.join(
        "nativePC", "pl",
        f"{gender}_equip",
        model_id,
        part, "mod",
        f"{gender}_{part}{numeric}.{ext}",
    )
    return os.path.join(natives_root, rel)


def _get_sp_gender(model_id):
    """从 SP model_id 的首字符提取性别，如 f_pl119_0000 -> 'f'"""
    return model_id[0]


def _make_sp_armor_filepath(natives_root, model_id, part, ext):
    """
    SP 幻化装备路径，model_id 自带性别前缀
    nativePC/pl/{g}_equip/{dir_id}/{part}/mod/{g}_{part}{numeric}.{ext}
    例: f_pl119_0000 -> nativePC/pl/f_equip/pl119_0000/arm/mod/f_arm119_0000.mod3
    """
    gender  = _get_sp_gender(model_id)   # "f"
    dir_id  = model_id[2:]               # "pl119_0000"（去掉 "f_"）
    numeric = model_id[4:]               # "119_0000"（去掉 "f_pl"）
    rel = os.path.join(
        "nativePC", "pl",
        f"{gender}_equip",
        dir_id,
        part, "mod",
        f"{gender}_{part}{numeric}.{ext}",
    )
    return os.path.join(natives_root, rel)


def _make_sp_face_filepath(natives_root, face_id, ext):
    """
    SP 独立头部路径
    nativePC/pl/{g}_face/{face_num}/mod/{face_id}.{ext}
    例: nativePC/pl/f_face/face003/mod/f_face003.mod3
    """
    gender   = face_id[0]    # "f"
    face_num = face_id[2:]   # "face003"
    rel = os.path.join(
        "nativePC", "pl",
        f"{gender}_face",
        face_num, "mod",
        f"{face_id}.{ext}",
    )
    return os.path.join(natives_root, rel)


def _make_sp_hair_filepath(natives_root, hair_id, ext):
    """
    SP 独立头发路径（不区分性别）
    nativePC/pl/hair/{hair_id}/mod/{hair_id}.{ext}
    例: nativePC/pl/hair/hair404/mod/hair404.mod3
    """
    rel = os.path.join(
        "nativePC", "pl",
        "hair",
        hair_id, "mod",
        f"{hair_id}.{ext}",
    )
    return os.path.join(natives_root, rel)


# ── 底层导出函数 ──────────────────────────────────────────────────

def _do_export_mod3(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    col = bpy.data.collections.get(collection_name)
    bpy.context.scene.mhw_mod3_toolpanel.exportMod3Collection = col
    bpy.ops.mhw_mod3.export_mhw_mod3(
        filepath=filepath,
        **MOD3_EXPORT_SETTINGS,
    )

def _do_export_mrl3(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    col = bpy.data.collections.get(collection_name)
    bpy.context.scene.mhw_mrl3_toolpanel.exportMrl3Collection = col
    bpy.ops.mhw_mrl3.export_mhw_mrl3(
        filepath=filepath,
    )

def _do_export_ctc(filepath, collection_name, export_ccl):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    col = bpy.data.collections.get(collection_name)
    bpy.context.scene.mhw_ctc_toolpanel.exportCTCCollection = col
    bpy.ops.mhw_ctc.export_mhw_ctc(
        filepath=filepath,
        exportCCL=export_ccl,
    )


_EXPORT_FUNCS = {
    "mod3": _do_export_mod3,
    "mrl3": _do_export_mrl3,
}


# ── 核心导出逻辑 ──────────────────────────────────────────────────

def _export_gender(context, settings, armor_entry, gender, natives_root):
    """为单个性别执行导出，返回 (export_count, fail_count, skip_count)"""
    scene     = context.scene
    model_id  = armor_entry["id"]
    mask_str  = armor_entry.get("mask", "11111")
    mask      = [c == '1' for c in mask_str.ljust(5, '0')]

    export_count = fail_count = skip_count = 0

    for part_code, part_name, mask_idx in MHWI_PARTS:
        if not mask[mask_idx]:
            continue

        # 使用空模标志
        if get_blank(scene, model_id, part_code):
            _write_blank_part(natives_root, model_id, gender, part_code)
            export_count += 1
            continue

        is_helm = (part_code == HELM_PART)
        file_types = HELM_FILE_TYPES if is_helm else REGULAR_FILE_TYPES

        for ft in file_types:
            col = get_binding(scene, model_id, part_code, ft)
            label = f"{gender}/{part_name}/{ft.upper()}"

            if not col:
                skip_count += 1
                continue
            if col not in bpy.data.collections:
                print(f"[MHWI] SKIP {label}: collection '{col}' not found")
                skip_count += 1
                continue

            filepath = _make_filepath(natives_root, model_id, gender, part_code, ft)
            try:
                print(f"[MHWI] {label}: {col} -> {os.path.basename(filepath)}")
                if ft == "ctc":
                    export_ccl = get_export_ccl(scene, model_id, part_code)
                    _do_export_ctc(filepath, col, export_ccl)
                else:
                    _EXPORT_FUNCS[ft](filepath, col)
                export_count += 1
            except Exception as err:
                print(f"[MHWI] FAILED {label}: {err}")
                fail_count += 1

    return export_count, fail_count, skip_count


def _write_blank_part(natives_root, model_id, gender, part_code):
    """写出空模：blank.mod3（头盔额外写 blank.evhl）"""
    filepath_mod3 = _make_filepath(natives_root, model_id, gender, part_code, "mod3")
    os.makedirs(os.path.dirname(filepath_mod3), exist_ok=True)
    blank_mod3 = _get_blank_path("blank.mod3")
    if os.path.isfile(blank_mod3):
        shutil.copy2(blank_mod3, filepath_mod3)
        print(f"[MHWI] BLANK mod3 -> {os.path.basename(filepath_mod3)}")
    else:
        print(f"[MHWI] WARNING: blank.mod3 not found at {blank_mod3}")

    if part_code == HELM_PART:
        numeric  = model_id[2:]
        evhl_name = f"{gender}_{part_code}{numeric}.evhl"
        filepath_evhl = os.path.join(os.path.dirname(filepath_mod3), evhl_name)
        blank_evhl = _get_blank_path("blank.evhl")
        if os.path.isfile(blank_evhl):
            shutil.copy2(blank_evhl, filepath_evhl)
            print(f"[MHWI] BLANK evhl -> {evhl_name}")
        else:
            print(f"[MHWI] WARNING: blank.evhl not found at {blank_evhl}")


def _write_blank_sp_part(natives_root, model_id, part_code):
    """SP 空模：仅写 blank.mod3，头盔不写 evhl"""
    filepath_mod3 = _make_sp_armor_filepath(natives_root, model_id, part_code, "mod3")
    os.makedirs(os.path.dirname(filepath_mod3), exist_ok=True)
    blank_mod3 = _get_blank_path("blank.mod3")
    if os.path.isfile(blank_mod3):
        shutil.copy2(blank_mod3, filepath_mod3)
        print(f"[MHWI] BLANK mod3 -> {os.path.basename(filepath_mod3)}")
    else:
        print(f"[MHWI] WARNING: blank.mod3 not found at {blank_mod3}")


def _export_sp(context, armor_entry, natives_root):
    """SP 整套幻化导出（固定性别，含独立头部和头发），返回 (export_count, fail_count, skip_count)"""
    scene     = context.scene
    model_id  = armor_entry["id"]
    face_id   = armor_entry["face_id"]
    hair_id   = armor_entry["hair_id"]
    mask_str  = armor_entry.get("mask", "11111")
    mask      = [c == '1' for c in mask_str.ljust(5, '0')]

    export_count = fail_count = skip_count = 0

    # ── 五件护甲部位 ──
    for part_code, part_name, mask_idx in MHWI_PARTS:
        if not mask[mask_idx]:
            continue

        if get_blank(scene, model_id, part_code):
            _write_blank_sp_part(natives_root, model_id, part_code)
            export_count += 1
            continue

        is_helm    = (part_code == HELM_PART)
        file_types = HELM_FILE_TYPES if is_helm else REGULAR_FILE_TYPES

        for ft in file_types:
            col   = get_binding(scene, model_id, part_code, ft)
            label = f"SP/{part_name}/{ft.upper()}"

            if not col:
                skip_count += 1
                continue
            if col not in bpy.data.collections:
                print(f"[MHWI] SKIP {label}: collection '{col}' not found")
                skip_count += 1
                continue

            filepath = _make_sp_armor_filepath(natives_root, model_id, part_code, ft)
            try:
                print(f"[MHWI] {label}: {col} -> {os.path.basename(filepath)}")
                if ft == "ctc":
                    _do_export_ctc(filepath, col, get_export_ccl(scene, model_id, part_code))
                else:
                    _EXPORT_FUNCS[ft](filepath, col)
                export_count += 1
            except Exception as err:
                print(f"[MHWI] FAILED {label}: {err}")
                fail_count += 1

    # ── 独立头部 ──
    for ft in SP_FACE_FILE_TYPES:
        col   = get_binding(scene, face_id, "face", ft)
        label = f"SP/头部/{ft.upper()}"

        if not col:
            skip_count += 1
            continue
        if col not in bpy.data.collections:
            print(f"[MHWI] SKIP {label}: collection '{col}' not found")
            skip_count += 1
            continue

        filepath = _make_sp_face_filepath(natives_root, face_id, ft)
        try:
            print(f"[MHWI] {label}: {col} -> {os.path.basename(filepath)}")
            _EXPORT_FUNCS[ft](filepath, col)
            export_count += 1
        except Exception as err:
            print(f"[MHWI] FAILED {label}: {err}")
            fail_count += 1

    # ── 独立头发 ──
    for ft in SP_HAIR_FILE_TYPES:
        col   = get_binding(scene, hair_id, "hair", ft)
        label = f"SP/头发/{ft.upper()}"

        if not col:
            skip_count += 1
            continue
        if col not in bpy.data.collections:
            print(f"[MHWI] SKIP {label}: collection '{col}' not found")
            skip_count += 1
            continue

        filepath = _make_sp_hair_filepath(natives_root, hair_id, ft)
        try:
            print(f"[MHWI] {label}: {col} -> {os.path.basename(filepath)}")
            if ft == "ctc":
                _do_export_ctc(filepath, col, get_export_ccl(scene, hair_id, "hair"))
            else:
                _EXPORT_FUNCS[ft](filepath, col)
            export_count += 1
        except Exception as err:
            print(f"[MHWI] FAILED {label}: {err}")
            fail_count += 1

    return export_count, fail_count, skip_count


# ── Operator ──────────────────────────────────────────────────────

class MHWI_OT_BatchExport(bpy.types.Operator):
    """MHWI 装备批量导出"""
    bl_idname = "mhwi.batch_export"
    bl_label  = "MHWI Batch Export"
    bl_options = {'REGISTER'}

    def _cleanup_mesh_collections(self, context, scene, settings):
        """Run RE Mesh cleanup on all bound mod3 collections; silently skip if RE Mesh Editor unavailable."""
        if not re_mesh_op_available('delete_loose'):
            return

        rank = settings.mhwi_rank_tab
        if rank == 'HR':
            model_id = settings.mhwi_selected_hr_armor
        elif rank == 'MR':
            model_id = settings.mhwi_selected_mr_armor
        else:
            model_id = settings.mhwi_selected_sp_armor

        if not model_id or model_id == 'NONE':
            return

        seen = set()
        mesh_collections = []
        for part_code, _, _ in MHWI_PARTS:
            col_name = get_binding(scene, model_id, part_code, "mod3")
            if col_name and col_name not in seen:
                col = bpy.data.collections.get(col_name)
                if col:
                    mesh_collections.append(col)
                    seen.add(col_name)

        if not mesh_collections:
            return

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
        scene    = context.scene
        settings = scene.mhw_suite_settings

        if not hasattr(bpy.ops, 'mhw_mod3') or not hasattr(bpy.ops.mhw_mod3, 'export_mhw_mod3'):
            self.report({'ERROR'}, "MHW Model Editor 未安装")
            return {'CANCELLED'}

        natives_root = scene.get("mhwi_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Mod Root 目录（nativePC 的上级文件夹）")
            return {'CANCELLED'}

        rank = settings.mhwi_rank_tab
        if rank == 'HR':
            model_id = settings.mhwi_selected_hr_armor
        elif rank == 'MR':
            model_id = settings.mhwi_selected_mr_armor
        else:
            model_id = settings.mhwi_selected_sp_armor

        if not model_id or model_id == 'NONE':
            self.report({'ERROR'}, "请先选择一套装备")
            return {'CANCELLED'}

        data        = _load_armor_sets(settings.mhwi_armor_sets_file)
        armor_entry = get_armor_entry(data, model_id)
        if not armor_entry:
            self.report({'ERROR'}, f"装备包中未找到: {model_id}")
            return {'CANCELLED'}

        if settings.mhwi_cleanup_before_export:
            self._cleanup_mesh_collections(context, scene, settings)

        total_export = total_fail = total_skip = 0
        if rank == 'SP':
            total_export, total_fail, total_skip = _export_sp(context, armor_entry, natives_root)
        else:
            genders = _resolve_genders(settings.mhwi_gender)
            for gender in genders:
                e, f, s = _export_gender(context, settings, armor_entry, gender, natives_root)
                total_export += e
                total_fail   += f
                total_skip   += s

        if total_fail > 0:
            self.report({'WARNING'},
                f"完成: 导出 {total_export}, 失败 {total_fail}, 跳过 {total_skip}")
        else:
            self.report({'INFO'},
                f"完成: 导出 {total_export}, 跳过 {total_skip}")
        return {'FINISHED'}


def _resolve_genders(gender_setting):
    if gender_setting == 'F':
        return ['f']
    if gender_setting == 'M':
        return ['m']
    return ['f', 'm']  # 'BOTH'


class MHWI_OT_SetNativesRoot(bpy.types.Operator):
    """选择 MHWI Mod 根目录（nativePC 的上级文件夹）"""
    bl_idname = "mhwi.set_natives_root"
    bl_label  = "Set Mod Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.directory.rstrip("/\\")
        if os.path.basename(path).lower() == "nativepc":
            path = os.path.dirname(path)
        context.scene["mhwi_natives_root"] = path
        self.report({'INFO'}, f"MHWI Mod root: {path}")
        return {'FINISHED'}


classes = [
    MHWI_OT_BatchExport,
    MHWI_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
