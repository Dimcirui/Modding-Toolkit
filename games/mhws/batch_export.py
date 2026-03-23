import bpy
import json
import os

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
    d = os.path.join(addon_dir, "assets", "mhws_armor_sets")
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


def _make_filepath(natives_root, base_path, part_id, armor_id, filetype):
    ext = MHWS_EXTS[filetype]
    filename = f"{armor_id}{part_id}.{ext}"
    bp = base_path.replace("/", os.sep)
    return os.path.join(natives_root, bp, part_id, filename)


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

        for part_id, part_name in MHWS_PARTS:
            if not (parts_mask & (1 << (int(part_id) - 1))):
                continue
            for filetype in file_types:
                col = get_binding(scene, armor_id, variant, part_id, filetype)
                if not col:
                    skip_count += 1
                    continue
                if col not in bpy.data.collections:
                    print(f"[MHWs] SKIP {part_name}/{filetype}: collection '{col}' not found")
                    skip_count += 1
                    continue
                filepath = _make_filepath(natives_root, base_path, part_id, variant_armor_id, filetype)
                label = f"{part_name} {filetype.upper()}"
                try:
                    print(f"[MHWs] {label}: {col} -> {os.path.basename(filepath)}")
                    _EXPORT_FUNCS[filetype](filepath, col)
                    export_count += 1
                except Exception as err:
                    print(f"[MHWs] FAILED {label}: {err}")
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


classes = [
    MHWS_OT_BatchExport,
    MHWS_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
