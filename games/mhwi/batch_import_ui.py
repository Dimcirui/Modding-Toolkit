import bpy
from collections import defaultdict
from .batch_import import PART_CODES, PART_NAMES, GENDER_LABELS, FT_ORDER
from .batch_export import _load_armor_sets, get_armor_entry
from .weapon_data import _load_weapon_sets

IMPORTER_WINDOW_WIDTH = 560


def _armor_label(data, group_key):
    """
    根据 group_key（扫描到的文件夹名，如 pl042_0500）查找装备名称。
    SP 幻化的文件夹名无性别前缀，需回退尝试 f_/m_ 前缀。
    返回 "名称 变体  (id)" 或 "id"（找不到时）。
    """
    entry = get_armor_entry(data, group_key)
    if entry is None:
        for prefix in ("f_", "m_"):
            entry = get_armor_entry(data, prefix + group_key)
            if entry:
                break
    if entry is None:
        return group_key
    name    = entry.get("name", group_key)
    variant = entry.get("variant_label", "")
    eid     = entry["id"]
    return f"{name} {variant}  ({eid})" if variant else f"{name}  ({eid})"


def _weapon_label(data, main_code):
    """根据主模型代码（如 bs_two002）在武器预设组中查找显示名，找不到则回退为原始代码"""
    if data:
        for w in data.get("weapon_sets", []):
            if w["id"] == main_code:
                return f"{w['name']}  ({w['id']})"
    return main_code

_FILETYPE_ICONS = {
    "mod3": 'OUTLINER_OB_MESH',
    "mrl3": 'MATERIAL',
    "ctc":  'LINKED',
}


# ── 辅助 ──────────────────────────────────────────────────────────

def _build_group_map(items):
    """
    从 scene.mhwi_import_items 构建分组映射。
    返回 {group_key: {(gender, part): [item, ...]}}
    内层按 FT_ORDER 排序。
    """
    raw = defaultdict(lambda: defaultdict(list))
    for item in items:
        raw[item.group_key][(item.gender, item.part)].append(item)
    result = {}
    for gkey, gp_map in raw.items():
        result[gkey] = {
            gp: sorted(its, key=lambda x: FT_ORDER.index(x.filetype)
                        if x.filetype in FT_ORDER else 99)
            for gp, its in gp_map.items()
        }
    return result


def _gp_sort_key(gender_part):
    gender, part = gender_part
    return (PART_CODES.index(part) if part in PART_CODES else 99,
            0 if gender == 'f' else 1)


# ── 对话框 ────────────────────────────────────────────────────────

class MHWI_OT_BatchImportDialog(bpy.types.Operator):
    """MHWI 装备批量导入对话框"""
    bl_idname  = "mhwi.batch_import_dialog"
    bl_label   = "MHWI Batch Importer"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=IMPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene  = context.scene

        # ── Mod Root ──
        natives_root = scene.get("mhwi_natives_root", "")
        row = layout.row(align=True)
        row.operator("mhwi.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="未设置", icon='ERROR')

        # ── 解析按钮 ──
        layout.operator("mhwi.scan_import_folder", text="解析", icon='FILE_REFRESH')

        items  = scene.mhwi_import_items
        groups = scene.mhwi_import_groups

        if not groups:
            layout.separator()
            layout.label(
                text="点击「解析」扫描装备文件" if natives_root else "请先设置 Mod Root",
                icon='INFO',
            )
            return

        layout.separator()

        # ── 全局选择栏 ──
        enabled_count = sum(1 for it in items if it.enabled)
        row = layout.row(align=True)
        op_all  = row.operator("mhwi.select_all_import", text="全选",   icon='CHECKBOX_HLT')
        op_all.value  = True
        op_none = row.operator("mhwi.select_all_import", text="全不选", icon='CHECKBOX_DEHLT')
        op_none.value = False
        row.label(text=f"{enabled_count} / {len(items)} 已选")

        layout.separator()

        # ── 各套装备 / 武器 ──
        group_map   = _build_group_map(items)
        armor_data  = _load_armor_sets(scene.mhw_suite_settings.mhwi_armor_sets_file)
        weapon_data = _load_weapon_sets(scene.mhw_suite_settings.mhwi_weapon_sets_file)

        for group in groups:
            gkey     = group.group_key
            gp_items = group_map.get(gkey, {})
            total    = sum(len(v) for v in gp_items.values())
            enabled  = sum(1 for its in gp_items.values() for it in its if it.enabled)

            if group.kind == "weapon":
                label = _weapon_label(weapon_data, gkey)
            else:
                label = _armor_label(armor_data, gkey)

            # 组标题行
            hrow = layout.row(align=True)
            icon = 'TRIA_DOWN' if group.expanded else 'TRIA_RIGHT'
            tog_op = hrow.operator(
                "mhwi.toggle_import_group",
                text=f"{label}  [{enabled}/{total}]",
                icon=icon, emboss=True,
            )
            tog_op.group_key = gkey
            g_all  = hrow.operator("mhwi.select_import_group", text="", icon='CHECKBOX_HLT')
            g_all.group_key  = gkey
            g_all.value      = True
            g_none = hrow.operator("mhwi.select_import_group", text="", icon='CHECKBOX_DEHLT')
            g_none.group_key = gkey
            g_none.value     = False

            if not group.expanded:
                continue

            box = layout.box()
            if group.kind == "weapon":
                # 展开内容：按文件自身的 model code 排序，每行显示该文件的所有文件类型
                for (_gender, part), part_items in sorted(gp_items.items(), key=lambda x: x[0][1]):
                    row = box.row(align=True)
                    part_label = f"{part}  (主模型)" if part == gkey else part
                    row.label(text=part_label)
                    for it in part_items:
                        ft_icon = _FILETYPE_ICONS.get(it.filetype, 'FILE')
                        row.prop(it, "enabled", text=it.filetype.upper(),
                                 icon=ft_icon, toggle=True)
            else:
                # 展开内容：按 (part, gender) 排序，每行显示该 (part, gender) 的所有文件类型
                for (gender, part), part_items in sorted(gp_items.items(), key=lambda x: _gp_sort_key(x[0])):
                    row = box.row(align=True)
                    part_label = f"{PART_NAMES.get(part, part)}  ({GENDER_LABELS.get(gender, gender)})"
                    row.label(text=part_label)
                    for it in part_items:
                        ft_icon = _FILETYPE_ICONS.get(it.filetype, 'FILE')
                        row.prop(it, "enabled", text=it.filetype.upper(),
                                 icon=ft_icon, toggle=True)

    def execute(self, context):
        bpy.ops.mhwi.batch_import()
        return {'FINISHED'}


classes = [
    MHWI_OT_BatchImportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
