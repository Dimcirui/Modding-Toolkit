import bpy
import os


# 扫描的装备目录（性别标识, 文件夹名）
EQUIP_DIRS = [("f", "f_equip"), ("m", "m_equip")]

# 支持的部位代码（扫描顺序也作为 UI 排序基准）
PART_CODES = ["arm", "leg", "body", "helm", "wst"]

# 扫描的文件扩展名
SCAN_EXTS = {".mod3", ".mrl3", ".ctc"}

PART_NAMES    = {"arm": "手臂", "leg": "腿部", "body": "身体", "helm": "头盔", "wst": "腰部"}
GENDER_LABELS = {"f": "女", "m": "男"}
FT_ORDER      = ["mod3", "mrl3", "ctc"]


# ── CollectionProperty 数据结构 ────────────────────────────────────

class MHWI_ImportItem(bpy.types.PropertyGroup):
    """代表一个待导入文件"""
    filepath:  bpy.props.StringProperty()
    group_key: bpy.props.StringProperty()   # model_id，用于归组
    gender:    bpy.props.StringProperty()   # "f" / "m"
    part:      bpy.props.StringProperty()   # "arm" / "leg" / ...
    filetype:  bpy.props.StringProperty()   # "mod3" / "mrl3" / "ctc"
    enabled:   bpy.props.BoolProperty(default=True)


class MHWI_ImportGroup(bpy.types.PropertyGroup):
    """代表一套装备的 UI 折叠状态"""
    group_key: bpy.props.StringProperty()   # model_id
    expanded:  bpy.props.BoolProperty(default=False)


# ── 扫描 ──────────────────────────────────────────────────────────

def scan_mhwi_folder(natives_root, scene):
    """
    扫描 nativePC/pl/{f,m}_equip/ 下的装备文件，
    将结果写入 scene.mhwi_import_items 和 scene.mhwi_import_groups。
    返回找到的文件总数。
    """
    items  = scene.mhwi_import_items
    groups = scene.mhwi_import_groups
    items.clear()
    groups.clear()

    pl_dir = os.path.join(natives_root, "nativePC", "pl")
    if not os.path.isdir(pl_dir):
        return 0

    seen_groups = set()   # 已添加到 groups 的 model_id

    for gender, equip_folder in EQUIP_DIRS:
        equip_dir = os.path.join(pl_dir, equip_folder)
        if not os.path.isdir(equip_dir):
            continue

        for model_id in sorted(os.listdir(equip_dir)):
            model_dir = os.path.join(equip_dir, model_id)
            if not os.path.isdir(model_dir):
                continue

            for part in PART_CODES:
                mod_dir = os.path.join(model_dir, part, "mod")
                if not os.path.isdir(mod_dir):
                    continue

                for fname in sorted(os.listdir(mod_dir)):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in SCAN_EXTS:
                        continue

                    if model_id not in seen_groups:
                        g           = groups.add()
                        g.group_key = model_id
                        seen_groups.add(model_id)

                    item           = items.add()
                    item.filepath  = os.path.join(mod_dir, fname)
                    item.group_key = model_id
                    item.gender    = gender
                    item.part      = part
                    item.filetype  = ext[1:]   # ".mod3" → "mod3"
                    item.enabled   = True

    # 只有一套装备时默认展开
    if len(groups) == 1:
        groups[0].expanded = True

    return len(items)


# ── 辅助：Collection 管理 ─────────────────────────────────────────

def _get_or_create_collection(name):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link_under(child_col, parent_col):
    """把 child_col 移入 parent_col（如在场景根则先移除）"""
    scene_root = bpy.context.scene.collection
    child_names_in_root = {c.name for c in scene_root.children}
    if child_col.name in child_names_in_root:
        scene_root.children.unlink(child_col)
    child_names_in_parent = {c.name for c in parent_col.children}
    if child_col.name not in child_names_in_parent:
        parent_col.children.link(child_col)


def _resolve_target(col_name, parent_col):
    """
    如果 parent_col 下有与 col_name 去掉最后一段扩展名后同名的子集合，
    返回该子集合作为更精确的嵌套目标，否则返回 parent_col 本身。
    例: f_body070_0000.mrl3 → base=f_body070_0000 → 找到 parent_col 下的 f_body070_0000
    """
    base = col_name.rsplit(".", 1)[0] if "." in col_name else None
    if base:
        for child in parent_col.children:
            if child.name == base:
                return child
    return parent_col


# ── Operators ─────────────────────────────────────────────────────

class MHWI_OT_ScanImportFolder(bpy.types.Operator):
    """扫描当前 Mod Root 目录，列出可导入的装备文件"""
    bl_idname  = "mhwi.scan_import_folder"
    bl_label   = "解析"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        natives_root = context.scene.get("mhwi_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Mod Root 目录（nativePC 的上级文件夹）")
            return {'CANCELLED'}
        count = scan_mhwi_folder(natives_root, context.scene)
        if count == 0:
            self.report({'WARNING'}, "未找到任何可导入的装备文件，请确认目录结构正确")
        else:
            self.report({'INFO'}, f"解析完成，找到 {count} 个文件")
        return {'FINISHED'}


class MHWI_OT_ToggleImportGroup(bpy.types.Operator):
    """展开/折叠一套装备"""
    bl_idname  = "mhwi.toggle_import_group"
    bl_label   = "Toggle Import Group"
    bl_options = {'INTERNAL'}
    group_key: bpy.props.StringProperty()

    def execute(self, context):
        for g in context.scene.mhwi_import_groups:
            if g.group_key == self.group_key:
                g.expanded = not g.expanded
                break
        return {'FINISHED'}


class MHWI_OT_SelectImportGroup(bpy.types.Operator):
    """批量选中/取消选中一套装备的所有文件"""
    bl_idname  = "mhwi.select_import_group"
    bl_label   = "Select Import Group"
    bl_options = {'INTERNAL'}
    group_key: bpy.props.StringProperty()
    value:     bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhwi_import_items:
            if item.group_key == self.group_key:
                item.enabled = self.value
        return {'FINISHED'}


class MHWI_OT_SelectAllImport(bpy.types.Operator):
    """全选/全不选所有待导入文件"""
    bl_idname  = "mhwi.select_all_import"
    bl_label   = "Select All Import"
    bl_options = {'INTERNAL'}
    value: bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhwi_import_items:
            item.enabled = self.value
        return {'FINISHED'}


class MHWI_OT_BatchImport(bpy.types.Operator):
    """MHWI 装备批量导入"""
    bl_idname  = "mhwi.batch_import"
    bl_label   = "MHWI Batch Import"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not (hasattr(bpy.ops, 'mhw_mod3') and hasattr(bpy.ops.mhw_mod3, 'import_mhw_mod3')):
            self.report({'ERROR'}, "MHW Model Editor 未安装")
            return {'CANCELLED'}

        items   = context.scene.mhwi_import_items
        # 保证 mod3 → mrl3 → ctc 顺序，避免 CTC 在 MOD3 前导入导致物理绑定失败
        enabled = sorted(
            (it for it in items if it.enabled),
            key=lambda x: FT_ORDER.index(x.filetype) if x.filetype in FT_ORDER else 99,
        )
        if not enabled:
            self.report({'WARNING'}, "没有选中任何项目")
            return {'CANCELLED'}

        # 构建 (group_key, gender, part) → {filetype: filepath} 的配对映射
        # 用于将同一部位的 mod3+mrl3 合并为单次 MOD3 联合导入，以正确解析材质名
        from collections import defaultdict as _dd
        pair_map = _dd(dict)
        for it in enabled:
            pair_map[(it.group_key, it.gender, it.part)][it.filetype] = it.filepath

        # 已配对的 mrl3 路径集合（将随 mod3 联合导入，无需单独导入）
        paired_mrl3_paths = {
            ft_map["mrl3"]
            for ft_map in pair_map.values()
            if "mod3" in ft_map and "mrl3" in ft_map
        }

        def _do_import(filepath, mrl3_path=None):
            directory = os.path.dirname(filepath) + os.sep
            filename  = os.path.basename(filepath)
            if mrl3_path:
                bpy.ops.mhw_mod3.import_mhw_mod3(
                    'EXEC_DEFAULT',
                    directory=directory,
                    files=[{"name": filename}],
                    loadMrl3Data=True,
                    mrl3Path=mrl3_path,
                )
            else:
                ext = os.path.splitext(filepath)[1].lower().lstrip(".")
                op_map = {
                    "mod3": bpy.ops.mhw_mod3.import_mhw_mod3,
                    "mrl3": bpy.ops.mhw_mrl3.import_mhw_mrl3,
                    "ctc":  bpy.ops.mhw_ctc.import_mhw_ctc,
                }
                op_func = op_map.get(ext)
                if op_func:
                    op_func('EXEC_DEFAULT', directory=directory, files=[{"name": filename}])

        ok = fail = 0
        for item in enabled:
            # 已通过 mod3 联合导入的 mrl3，跳过
            if item.filepath in paired_mrl3_paths:
                ok += 1
                print(f"[MHWI] Paired (via MOD3): {os.path.basename(item.filepath)}")
                continue

            parent_col = _get_or_create_collection(item.group_key)
            mrl3_path  = None
            if item.filetype == "mod3":
                key = (item.group_key, item.gender, item.part)
                mrl3_path = pair_map[key].get("mrl3")

            try:
                scene_root = bpy.context.scene.collection
                before     = {c.name for c in bpy.data.collections}
                _do_import(item.filepath, mrl3_path)
                after      = {c.name for c in bpy.data.collections}
                root_names = {c.name for c in scene_root.children}
                for name in after - before:
                    # 只移动落在场景根的顶层集合，importer 自行嵌套好的子集合跳过
                    if name in root_names:
                        col    = bpy.data.collections.get(name)
                        target = _resolve_target(name, parent_col)
                        if col:
                            _link_under(col, target)
                ok += 1
                suffix = " (+MRL3)" if mrl3_path else ""
                print(f"[MHWI] Imported{suffix}: {os.path.basename(item.filepath)}")
            except Exception as e:
                print(f"[MHWI] Import FAILED {item.filepath}: {e}")
                fail += 1

        if fail:
            self.report({'WARNING'}, f"完成: 导入 {ok}, 失败 {fail}")
        else:
            self.report({'INFO'}, f"完成: 导入 {ok} 个文件")
        return {'FINISHED'}


classes = [
    MHWI_ImportItem,
    MHWI_ImportGroup,
    MHWI_OT_ScanImportFolder,
    MHWI_OT_ToggleImportGroup,
    MHWI_OT_SelectImportGroup,
    MHWI_OT_SelectAllImport,
    MHWI_OT_BatchImport,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhwi_import_items  = bpy.props.CollectionProperty(type=MHWI_ImportItem)
    bpy.types.Scene.mhwi_import_groups = bpy.props.CollectionProperty(type=MHWI_ImportGroup)


def unregister():
    del bpy.types.Scene.mhwi_import_items
    del bpy.types.Scene.mhwi_import_groups
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
