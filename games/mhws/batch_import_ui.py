import bpy
from collections import defaultdict

from ...core.i18n import T
from .batch_import import FT_ORDER
from .batch_export import _load_scheme, get_mhws_variants, _PART_LABEL_KEYS
from .batch_export_ui import _FILETYPE_ICONS

IMPORTER_WINDOW_WIDTH = 560

_VARIANT_ORDER = {"mm": 0, "mf": 1, "fm": 2, "ff": 3}


def _armor_label(scheme, armor_id):
    """根据 armor_id 在当前装备包中查找显示名，找不到则回退为原始 id"""
    if scheme:
        for a in scheme.get("armor_sets", []):
            if a["id"] == armor_id:
                name = a.get("name", armor_id)
                return f"{name}  ({armor_id})"
    return armor_id


def _variant_label(variant):
    for code, label, _ in get_mhws_variants():
        if code == variant:
            return label
    return variant


def _vp_sort_key(variant_part):
    variant, part = variant_part
    return (_VARIANT_ORDER.get(variant, 99), int(part) if part.isdigit() else 99)


# ── 辅助 ──────────────────────────────────────────────────────────

def _build_group_map(items):
    """
    从 scene.mhws_import_items 构建分组映射。
    返回 {armor_id: {(variant, part): [item, ...]}}，内层按 FT_ORDER 排序。
    """
    raw = defaultdict(lambda: defaultdict(list))
    for item in items:
        raw[item.armor_id][(item.variant, item.part)].append(item)
    result = {}
    for gkey, vp_map in raw.items():
        result[gkey] = {
            vp: sorted(its, key=lambda x: FT_ORDER.index(x.filetype)
                        if x.filetype in FT_ORDER else 99)
            for vp, its in vp_map.items()
        }
    return result


# ── 对话框 ────────────────────────────────────────────────────────

class MHWS_OT_BatchImportDialog(bpy.types.Operator):
    bl_idname  = "mhws.batch_import_dialog"
    bl_label   = "MHWs Batch Importer"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_import_ui.dialog_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=IMPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        settings = scene.mhw_suite_settings

        # ── 装备包 ──
        layout.prop(settings, "mhws_armor_scheme", text=T("mhws.batch_export_ui.armor_pack_label"))

        # ── Mod Root ──
        natives_root = scene.get("mhws_natives_root", "")
        row = layout.row(align=True)
        row.operator("mhws.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text=T("mhws.batch_export_ui.not_set"), icon='ERROR')

        # ── 解析按钮 ──
        layout.operator("mhws.scan_import_files", text=T("mhws.batch_import_ui.scan_btn"), icon='FILE_REFRESH')

        items  = scene.mhws_import_items
        groups = scene.mhws_import_groups

        if not groups:
            layout.separator()
            layout.label(
                text=T("mhws.batch_import_ui.click_scan_hint") if natives_root
                     else T("mhws.batch_import_ui.set_mod_root_hint"),
                icon='INFO',
            )
            return

        layout.separator()
        layout.label(text=T("mhws.batch_import_ui.chain2_slow_hint"), icon='INFO')

        # ── 全局选择栏 ──
        enabled_count = sum(1 for it in items if it.enabled)
        row = layout.row(align=True)
        op_all  = row.operator("mhws.select_all_import", text=T("mhws.batch_import_ui.select_all"), icon='CHECKBOX_HLT')
        op_all.value  = True
        op_none = row.operator("mhws.select_all_import", text=T("mhws.batch_import_ui.deselect_all"), icon='CHECKBOX_DEHLT')
        op_none.value = False
        row.label(text=T("mhws.batch_import_ui.selected_count").format(enabled=enabled_count, total=len(items)))

        layout.separator()

        # ── 各套装备 ──
        group_map = _build_group_map(items)
        scheme    = _load_scheme(settings.mhws_armor_scheme)

        for group in groups:
            gkey     = group.group_key
            vp_items = group_map.get(gkey, {})
            total    = sum(len(v) for v in vp_items.values())
            enabled  = sum(1 for its in vp_items.values() for it in its if it.enabled)
            label    = _armor_label(scheme, gkey)

            hrow = layout.row(align=True)
            icon = 'TRIA_DOWN' if group.expanded else 'TRIA_RIGHT'
            tog_op = hrow.operator(
                "mhws.toggle_import_group",
                text=f"{label}  [{enabled}/{total}]",
                icon=icon, emboss=True,
            )
            tog_op.group_key = gkey
            g_all  = hrow.operator("mhws.select_import_group", text="", icon='CHECKBOX_HLT')
            g_all.group_key  = gkey
            g_all.value      = True
            g_none = hrow.operator("mhws.select_import_group", text="", icon='CHECKBOX_DEHLT')
            g_none.group_key = gkey
            g_none.value     = False

            if not group.expanded:
                continue

            box = layout.box()
            for (variant, part), part_items in sorted(vp_items.items(), key=lambda x: _vp_sort_key(x[0])):
                row = box.row(align=True)
                part_label = f"{T(_PART_LABEL_KEYS.get(part, part))}  ({_variant_label(variant)})"
                row.label(text=part_label)
                for it in part_items:
                    ft_icon = _FILETYPE_ICONS.get(it.filetype, 'FILE')
                    row.prop(it, "enabled", text=it.filetype.upper(),
                             icon=ft_icon, toggle=True)

    def execute(self, context):
        bpy.ops.mhws.batch_import()
        return {'FINISHED'}


classes = [
    MHWS_OT_BatchImportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
