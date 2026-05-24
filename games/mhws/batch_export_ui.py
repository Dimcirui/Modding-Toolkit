import bpy
from .batch_export import (
    MHWS_PARTS, MHWS_VARIANTS, DEFAULT_FILE_TYPES,
    _load_scheme, _resolve_part_file_types, _canonical_order_file_types,
    get_binding, set_binding,
)

EXPORTER_WINDOW_WIDTH = 580

_FILETYPE_ICONS = {
    "mesh":   'OUTLINER_OB_MESH',
    "mdf2":   'MATERIAL',
    "chain2": 'LINKED',
    "clsp":   'PHYSICS',
}

_FILETYPE_LABELS = {
    "mesh":   "MESH",
    "mdf2":   "MDF2",
    "chain2": "CHAIN2",
    "clsp":   "CLSP",
    "gpuc":   "GPUC",
}


def _get_filtered_collections(filetype):
    result = []
    type_map  = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION",
                 "chain2": "RE_CHAIN_COLLECTION", "clsp": "RE_CHAIN_COLLECTION"}
    sfx_map   = {"mesh": ".mesh", "mdf2": ".mdf2", "chain2": ".chain2", "clsp": ".clsp"}
    col_type  = type_map.get(filetype, "")
    name_sfx  = sfx_map.get(filetype, "")
    for c in bpy.data.collections:
        ct = c.get("~TYPE", "")
        if col_type and ct == col_type:
            icon = f"COLLECTION_{c.color_tag}" if c.color_tag != "NONE" else "OUTLINER_COLLECTION"
            result.append((c.name, c.name, "", icon, len(result)))
            continue
        if not ct and name_sfx and c.name.endswith(name_sfx):
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not col_type and not name_sfx:
        # fallback: show all
        for c in bpy.data.collections:
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not result:
        result.append(("NONE", "No matching collections", "", "ERROR", 0))
    return result


# ── Pick Collection ────────────────────────────────────────────

class MHWS_OT_PickCollection(bpy.types.Operator):
    bl_idname = "mhws.pick_collection"
    bl_label = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    armor_id:  bpy.props.StringProperty()
    variant:   bpy.props.StringProperty()
    part:      bpy.props.StringProperty()
    filetype:  bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(
        name="Collection",
        items=lambda self, ctx: _get_filtered_collections(self.filetype)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name and self.collection_name != "NONE":
            set_binding(context.scene, self.armor_id, self.variant, self.part, self.filetype, self.collection_name)
        return {'FINISHED'}


class MHWS_OT_ClearBinding(bpy.types.Operator):
    bl_idname = "mhws.clear_binding"
    bl_label = "Clear Binding"
    bl_options = {'INTERNAL'}

    armor_id: bpy.props.StringProperty()
    variant:  bpy.props.StringProperty()
    part:     bpy.props.StringProperty()
    filetype: bpy.props.StringProperty()

    def execute(self, context):
        set_binding(context.scene, self.armor_id, self.variant, self.part, self.filetype, "")
        return {'FINISHED'}


# ── Main Dialog ────────────────────────────────────────────────

class MHWS_OT_BatchExportDialog(bpy.types.Operator):
    """MHWs 装备批量导出对话框"""
    bl_idname = "mhws.batch_export_dialog"
    bl_label = "MHWs Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

        # ── Selectors ──
        layout.prop(settings, "mhws_armor_scheme", text="装备包")
        row = layout.row(align=True)
        row.prop(settings, "mhws_armor_variant", text="")
        row.prop(settings, "mhws_selected_armor", text="装备")

        # ── Natives Root ──
        natives_root = scene.get("mhws_natives_root", "")
        row = layout.row(align=True)
        row.operator("mhws.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="未设置", icon='ERROR')

        # ── Early out ──
        variant  = settings.mhws_armor_variant
        armor_id = settings.mhws_selected_armor
        if not armor_id or armor_id == 'NONE':
            layout.separator()
            layout.label(text="请选择装备以配置绑定", icon='INFO')
            return

        # Get armor_set data
        scheme_file = settings.mhws_armor_scheme
        scheme = _load_scheme(scheme_file) if scheme_file and scheme_file != 'NONE' else None
        if scheme:
            armor_set = next(
                (a for a in scheme.get("armor_sets", []) if a["id"] == armor_id), None
            )
        else:
            armor_set = None

        parts_mask = armor_set.get("parts_mask", 0b11111) if armor_set else 0b11111
        active_parts = [(pid, pname) for pid, pname in MHWS_PARTS
                        if parts_mask & (1 << (int(pid) - 1))]

        # Compute per-part file types and the union across all parts
        per_part_fts = {}
        all_file_types = []
        for part_id, part_name in active_parts:
            fts = _canonical_order_file_types(
                _resolve_part_file_types(armor_set, part_id)) if armor_set else DEFAULT_FILE_TYPES
            per_part_fts[part_id] = fts
            for ft in fts:
                if ft not in all_file_types:
                    all_file_types.append(ft)
        all_file_types = _canonical_order_file_types(all_file_types)

        layout.separator()

        # ── Header row ──
        header = layout.row(align=False)
        header.label(text="")  # part name column placeholder
        for ft in all_file_types:
            header.label(text=_FILETYPE_LABELS.get(ft, ft.upper()), icon=_FILETYPE_ICONS.get(ft, 'DOT'))

        # ── Part rows ──
        for part_id, part_name in active_parts:
            row = layout.row(align=False)
            row.label(text=f"{part_id}  {part_name}")
            part_fts = per_part_fts[part_id]
            for ft in all_file_types:
                sub = row.row(align=True)
                if ft not in part_fts:
                    # This file type does not apply to this part
                    sub.label(text="")
                    continue

                if ft == "gpuc":
                    # gpuc is always blank-copied, no collection binding
                    sub.label(text="AUTO", icon='FILE_BLANK')
                    continue

                cur = get_binding(scene, armor_id, variant, part_id, ft)
                op = sub.operator(
                    "mhws.pick_collection",
                    text=cur if cur else "—",
                    icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft]
                )
                op.armor_id = armor_id
                op.variant  = variant
                op.part     = part_id
                op.filetype = ft
                if cur:
                    op_c = sub.operator("mhws.clear_binding", text="", icon='X')
                    op_c.armor_id = armor_id
                    op_c.variant  = variant
                    op_c.part     = part_id
                    op_c.filetype = ft

        layout.separator()
        layout.prop(settings, "mhws_use_blank_export", icon='FILE_BLANK')

        self._draw_bonesystem(layout, settings)

    def _draw_bonesystem(self, layout, settings):
        layout.separator()
        box = layout.box()
        row = box.row(align=True)
        row.prop(settings, "mhws_use_bonesystem",
                 text="使用 Bonesystem", icon='ARMATURE_DATA')
        if not settings.mhws_use_bonesystem:
            return

        col = box.column(align=False)
        col.prop(settings, "mhws_bs_armature", text="骨架")
        name_row = col.row(align=True)
        name_row.prop(settings, "mhws_fbxskel_name", text="FBXSkel 名")
        name_row.operator("mhws.bonesystem_settings", text="", icon='PREFERENCES')

    def execute(self, context):
        bpy.ops.mhws.batch_export()
        return {'FINISHED'}


classes = [
    MHWS_OT_PickCollection,
    MHWS_OT_ClearBinding,
    MHWS_OT_BatchExportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
