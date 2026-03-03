import bpy
from .batch_export import (
    _load_scheme, _get_binding, _set_binding,
    _get_enabled, _set_enabled, get_schemes_callback
)

EXPORTER_WINDOW_WIDTH = 600


class RE9_OT_ToggleEntry(bpy.types.Operator):
    """Toggle mesh/mdf2 export for this entry"""
    bl_idname = "re9.toggle_entry"
    bl_label = "Toggle"
    bl_options = {'INTERNAL'}

    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        current = _get_enabled(scene, self.character_id, self.entry_id, self.suffix)
        _set_enabled(scene, self.character_id, self.entry_id, self.suffix, not current)
        return {'FINISHED'}


class RE9_OT_PickCollection(bpy.types.Operator):
    """Pick a collection for this export entry"""
    bl_idname = "re9.pick_collection"
    bl_label = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()

    collection_name: bpy.props.EnumProperty(
        name="Collection",
        items=lambda self, context: [(c.name, c.name, "") for c in bpy.data.collections]
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        _set_binding(context.scene, self.character_id, self.entry_id, self.suffix, self.collection_name)
        return {'FINISHED'}


class RE9_OT_BatchExportDialog(bpy.types.Operator):
    """Open RE9 batch export dialog. Configure collections and export"""
    bl_idname = "re9.batch_export_dialog"
    bl_label = "RE9 Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

        # Scheme selector
        layout.prop(settings, "re9_export_scheme", text="Character")

        # Natives root
        natives_root = scene.get("re9_natives_root", "")
        row = layout.row(align=True)
        row.operator("re9.set_natives_root", text="Natives Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="Not set", icon='ERROR')

        scheme_file = settings.re9_export_scheme
        if not scheme_file or scheme_file == 'NONE':
            layout.label(text="Select a character scheme", icon='INFO')
            return

        scheme = _load_scheme(scheme_file)
        if not scheme:
            layout.label(text="Failed to load scheme", icon='ERROR')
            return

        character_id = scheme["character_id"]

        layout.separator()

        for group in scheme["groups"]:
            group_box = layout.box()
            group_box.label(text=group["name"], icon='FILE_FOLDER')

            for entry in group["entries"]:
                entry_id = entry["id"]
                entry_box = group_box.box()

                # Entry header
                header_text = entry_id
                note = entry.get("note", "")
                if note:
                    header_text += f"  [{note}]"
                entry_box.label(text=header_text)

                # MESH row
                if entry.get("mesh"):
                    row = entry_box.row(align=True)
                    mesh_enabled = _get_enabled(scene, character_id, entry_id, "mesh")
                    icon_mesh = 'CHECKBOX_HLT' if mesh_enabled else 'CHECKBOX_DEHLT'
                    op = row.operator("re9.toggle_entry", text="", icon=icon_mesh, emboss=False)
                    op.character_id = character_id
                    op.entry_id = entry_id
                    op.suffix = "mesh"
                    row.label(text="MESH", icon='OUTLINER_OB_MESH')
                    current_mesh_col = _get_binding(scene, character_id, entry_id, "mesh")
                    op_pick = row.operator("re9.pick_collection", text=current_mesh_col if current_mesh_col else "Select...", icon='DOWNARROW_HLT')
                    op_pick.character_id = character_id
                    op_pick.entry_id = entry_id
                    op_pick.suffix = "mesh"

                # MDF2 row
                if entry.get("mdf2"):
                    row = entry_box.row(align=True)
                    mdf2_enabled = _get_enabled(scene, character_id, entry_id, "mdf2")
                    icon_mdf = 'CHECKBOX_HLT' if mdf2_enabled else 'CHECKBOX_DEHLT'
                    op = row.operator("re9.toggle_entry", text="", icon=icon_mdf, emboss=False)
                    op.character_id = character_id
                    op.entry_id = entry_id
                    op.suffix = "mdf2"
                    row.label(text=f"MDF2 x{len(entry['mdf2'])}", icon='MATERIAL')
                    current_mdf_col = _get_binding(scene, character_id, entry_id, "mdf2")
                    op_pick = row.operator("re9.pick_collection", text=current_mdf_col if current_mdf_col else "Select...", icon='DOWNARROW_HLT')
                    op_pick.character_id = character_id
                    op_pick.entry_id = entry_id
                    op_pick.suffix = "mdf2"

    def execute(self, context):
        bpy.ops.re9.batch_export()
        return {'FINISHED'}


classes = [
    RE9_OT_ToggleEntry,
    RE9_OT_PickCollection,
    RE9_OT_BatchExportDialog,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)