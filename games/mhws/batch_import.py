import bpy
import os
from collections import defaultdict

from ...core.i18n import T
from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available
from .batch_export import (
    MHWS_PARTS,
    _load_scheme, _resolve_part_file_types, _canonical_order_file_types,
    _make_filepath, set_binding,
)

# gpuc has no importer (RE Mesh/Chain Editor never reads it back) and is always
# regenerated blank on export, so it never needs to round-trip through import.
IMPORT_FILE_TYPES = ["mesh", "mdf2", "chain2", "clsp"]
FT_ORDER = ["mesh", "mdf2", "chain2", "clsp"]


# ── CollectionProperty 数据结构 ────────────────────────────────────

class MHWS_ImportItem(bpy.types.PropertyGroup):
    """代表一个待导入文件"""
    filepath:          bpy.props.StringProperty()
    armor_id:          bpy.props.StringProperty()   # 装备包中的套装 id，如 "pl001"
    variant:           bpy.props.StringProperty()   # "mm"/"mf"/"fm"/"ff"
    variant_armor_id:  bpy.props.StringProperty()   # 该变体实际的模型前缀，如 "ch02_001_000"
    part:              bpy.props.StringProperty()   # "1".."5"
    filetype:          bpy.props.StringProperty()   # "mesh"/"mdf2"/"chain2"/"clsp"
    enabled:           bpy.props.BoolProperty(default=True)


class MHWS_ImportGroup(bpy.types.PropertyGroup):
    """代表一套装备的 UI 折叠状态"""
    group_key: bpy.props.StringProperty()   # armor_id
    expanded:  bpy.props.BoolProperty(default=False)


# ── 扫描 ──────────────────────────────────────────────────────────

def scan_mhws_catalog(natives_root, scheme_filename, scene):
    """
    按 armor_sets JSON 中记录的路径规则，逐一检查磁盘上是否存在对应文件，
    而非遍历文件夹（MHWs 装备包已经记录了完整的路径信息，直接按图索骥即可）。
    结果写入 scene.mhws_import_items 和 scene.mhws_import_groups。
    返回找到的文件总数。
    """
    items  = scene.mhws_import_items
    groups = scene.mhws_import_groups
    items.clear()
    groups.clear()

    scheme = _load_scheme(scheme_filename)
    if not scheme:
        return 0

    seen_groups = set()

    for armor_set in scheme.get("armor_sets", []):
        armor_id   = armor_set["id"]
        parts_mask = armor_set.get("parts_mask", 0b11111)
        variants   = armor_set.get("variants", {})

        for variant, variant_data in variants.items():
            variant_armor_id = variant_data["armor_id"]
            base_path        = variant_data["base_path"]

            for part_id, _part_name in MHWS_PARTS:
                if not (parts_mask & (1 << (int(part_id) - 1))):
                    continue

                part_fts = [ft for ft in _resolve_part_file_types(armor_set, part_id)
                            if ft in IMPORT_FILE_TYPES]

                for filetype in _canonical_order_file_types(part_fts):
                    filepath = _make_filepath(natives_root, base_path, part_id, variant_armor_id, filetype)
                    if not os.path.isfile(filepath):
                        continue

                    if armor_id not in seen_groups:
                        g           = groups.add()
                        g.group_key = armor_id
                        seen_groups.add(armor_id)

                    item                  = items.add()
                    item.filepath         = filepath
                    item.armor_id         = armor_id
                    item.variant          = variant
                    item.variant_armor_id = variant_armor_id
                    item.part             = part_id
                    item.filetype         = filetype
                    # chain2/clsp 导入瓶颈已修复，默认全部勾选
                    item.enabled          = True

    if len(groups) == 1:
        groups[0].expanded = True

    return len(items)


# ── 辅助：Chain 导入 operator 可用性 ────────────────────────────────
# RE Chain Editor 把 chain2/clsp 各自注册为独立分类（re_chain2 / re_clsp），
# 不像 RE Mesh Editor 有社区分支改名的问题，因此直接查 bpy.ops 即可。

def _chain2_import_available():
    return hasattr(bpy.ops, 're_chain2') and 'importfile' in dir(bpy.ops.re_chain2)


def _clsp_import_available():
    return hasattr(bpy.ops, 're_clsp') and 'importfile' in dir(bpy.ops.re_clsp)


# ── Operators ─────────────────────────────────────────────────────

class MHWS_OT_ScanImportFiles(bpy.types.Operator):
    bl_idname  = "mhws.scan_import_files"
    bl_label   = "Scan"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import.scan_desc")

    def execute(self, context):
        scene        = context.scene
        settings     = scene.mhw_suite_settings
        natives_root = scene.get("mhws_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("mhws.batch_import.set_mod_root_first"))
            return {'CANCELLED'}

        count = scan_mhws_catalog(natives_root, settings.mhws_armor_scheme, scene)
        if count == 0:
            self.report({'WARNING'}, T("mhws.batch_import.no_files_found"))
        else:
            self.report({'INFO'}, T("mhws.batch_import.scan_done").format(n=count))
        return {'FINISHED'}


class MHWS_OT_ToggleImportGroup(bpy.types.Operator):
    bl_idname  = "mhws.toggle_import_group"
    bl_label   = "Toggle Import Group"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import.toggle_group_desc")

    group_key: bpy.props.StringProperty()

    def execute(self, context):
        for g in context.scene.mhws_import_groups:
            if g.group_key == self.group_key:
                g.expanded = not g.expanded
                break
        return {'FINISHED'}


class MHWS_OT_SelectImportGroup(bpy.types.Operator):
    bl_idname  = "mhws.select_import_group"
    bl_label   = "Select Import Group"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import.select_group_desc")

    group_key: bpy.props.StringProperty()
    value:     bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhws_import_items:
            if item.armor_id == self.group_key:
                item.enabled = self.value
        return {'FINISHED'}


class MHWS_OT_SelectAllImport(bpy.types.Operator):
    bl_idname  = "mhws.select_all_import"
    bl_label   = "Select All Import"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import.select_all_desc")

    value: bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhws_import_items:
            item.enabled = self.value
        return {'FINISHED'}


class MHWS_OT_BatchImport(bpy.types.Operator):
    bl_idname  = "mhws.batch_import"
    bl_label   = "MHWs Batch Import"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import.batch_import_desc")

    def _import_mesh(self, mesh_item, mdf2_item, variant_armor_id, part_id):
        """导入 mesh（可选携带 mdf2 材质），返回新建骨架的数据块名，找不到则返回 None"""
        directory = os.path.dirname(mesh_item.filepath) + os.sep
        filename  = os.path.basename(mesh_item.filepath)
        kwargs = dict(
            directory=directory,
            files=[{"name": filename}],
            loadMaterials=bool(mdf2_item),
            loadMDFData=bool(mdf2_item),
            loadShellFur=True,
        )
        if mdf2_item:
            kwargs["mdfPath"] = mdf2_item.filepath

        before = set(bpy.data.armatures.keys())
        call_re_mesh_op('importfile', 'EXEC_DEFAULT', **kwargs)
        after = set(bpy.data.armatures.keys()) - before

        expected = f"{variant_armor_id}{part_id} Armature"
        if expected in after:
            return expected
        if len(after) == 1:
            return next(iter(after))
        return expected if expected in bpy.data.armatures else None

    def _import_mdf_only(self, mdf2_item):
        """mesh 文件缺失但 mdf2 单独存在时的兜底：走 RE Mesh Editor 独立的 MDF 导入"""
        directory = os.path.dirname(mdf2_item.filepath) + os.sep
        filename  = os.path.basename(mdf2_item.filepath)
        bpy.ops.re_mdf.importfile('EXEC_DEFAULT', directory=directory, files=[{"name": filename}])

    def _import_chain(self, item, filetype, armature_name):
        op_ns = getattr(bpy.ops, f"re_{filetype}")
        op_ns.importfile('EXEC_DEFAULT', filepath=item.filepath, targetArmature=armature_name)

    def _bind(self, scene, armor_id, variant, part_id, filetype, expected_col_name):
        """导入成功后自动把生成的集合登记为导出绑定，省去手动 Pick Collection"""
        if expected_col_name in bpy.data.collections:
            set_binding(scene, armor_id, variant, part_id, filetype, expected_col_name)

    def execute(self, context):
        if not re_mesh_op_available('importfile'):
            self.report({'ERROR'}, T("mhws.batch_import.mesh_editor_missing"))
            return {'CANCELLED'}

        items   = context.scene.mhws_import_items
        enabled = [it for it in items if it.enabled]
        if not enabled:
            self.report({'WARNING'}, T("mhws.batch_import.no_items_selected"))
            return {'CANCELLED'}

        has_chain2 = _chain2_import_available()
        has_clsp   = _clsp_import_available()
        scene      = context.scene
        settings   = scene.mhw_suite_settings

        # 按 (armor_id, variant, part) 分组，确保同一部位的 mesh 先于 chain2/clsp 导入
        # （chain2/clsp 需要绑定到 mesh 导入时创建的骨架上）
        unit_map = defaultdict(dict)
        for it in enabled:
            unit_map[(it.armor_id, it.variant, it.part, it.variant_armor_id)][it.filetype] = it

        ok = fail = skip = 0
        succeeded_variants = {}   # (armor_id, variant) -> None，用 dict 保留插入顺序

        for (armor_id, variant, part_id, variant_armor_id), ft_map in unit_map.items():
            mesh_item  = ft_map.get("mesh")
            mdf2_item  = ft_map.get("mdf2")
            armature_name = None

            if mesh_item:
                try:
                    armature_name = self._import_mesh(mesh_item, mdf2_item, variant_armor_id, part_id)
                    ok += 1
                    succeeded_variants[(armor_id, variant)] = None
                    self._bind(scene, armor_id, variant, part_id, "mesh", f"{variant_armor_id}{part_id}.mesh")
                    if mdf2_item:
                        ok += 1
                        self._bind(scene, armor_id, variant, part_id, "mdf2", f"{variant_armor_id}{part_id}.mdf2")
                    print(f"[MHWs] Imported: {os.path.basename(mesh_item.filepath)}")
                except Exception as e:
                    print(f"[MHWs] Mesh import FAILED {mesh_item.filepath}: {e}")
                    fail += 1 + (1 if mdf2_item else 0)
            elif mdf2_item:
                try:
                    self._import_mdf_only(mdf2_item)
                    ok += 1
                    succeeded_variants[(armor_id, variant)] = None
                    print(f"[MHWs] Imported (MDF2 only): {os.path.basename(mdf2_item.filepath)}")
                except Exception as e:
                    print(f"[MHWs] MDF2 import FAILED {mdf2_item.filepath}: {e}")
                    fail += 1

            for filetype, available in (("chain2", has_chain2), ("clsp", has_clsp)):
                chain_item = ft_map.get(filetype)
                if not chain_item:
                    continue
                if not armature_name:
                    print(f"[MHWs] SKIP {chain_item.filepath}: no armature imported for this part")
                    skip += 1
                    continue
                if not available:
                    print(f"[MHWs] SKIP {chain_item.filepath}: RE Chain Editor's {filetype} importer not found")
                    skip += 1
                    continue
                try:
                    self._import_chain(chain_item, filetype, armature_name)
                    self._bind(scene, armor_id, variant, part_id, filetype, f"{variant_armor_id}{part_id}.{filetype}")
                    ok += 1
                    succeeded_variants[(armor_id, variant)] = None
                    print(f"[MHWs] Imported: {os.path.basename(chain_item.filepath)} -> {armature_name}")
                except Exception as e:
                    print(f"[MHWs] {filetype} import FAILED {chain_item.filepath}: {e}")
                    fail += 1

        # 最后一个成功导入的套装/变体，设为批量导出面板当前选中项
        if succeeded_variants:
            last_armor_id, last_variant = list(succeeded_variants)[-1]
            settings.mhws_selected_armor = last_armor_id
            settings.mhws_armor_variant  = last_variant

        if fail:
            self.report({'WARNING'}, T("mhws.batch_import.done_with_fail").format(ok=ok, fail=fail, skip=skip))
        else:
            self.report({'INFO'}, T("mhws.batch_import.done").format(ok=ok, skip=skip))
        return {'FINISHED'}


classes = [
    MHWS_ImportItem,
    MHWS_ImportGroup,
    MHWS_OT_ScanImportFiles,
    MHWS_OT_ToggleImportGroup,
    MHWS_OT_SelectImportGroup,
    MHWS_OT_SelectAllImport,
    MHWS_OT_BatchImport,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhws_import_items  = bpy.props.CollectionProperty(type=MHWS_ImportItem)
    bpy.types.Scene.mhws_import_groups = bpy.props.CollectionProperty(type=MHWS_ImportGroup)


def unregister():
    del bpy.types.Scene.mhws_import_items
    del bpy.types.Scene.mhws_import_groups
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
