import bpy
from .batch_export import (
    _load_scheme, _get_binding, _set_binding,
    _get_enabled, _set_enabled, get_schemes_callback
)

EXPORTER_WINDOW_WIDTH = 600


def _get_group_toggle_key(character_id, group_name):
    key = f"re9grp_{character_id}_{group_name}"
    return key.replace(" ", "_").replace("(", "").replace(")", "")


def _get_filtered_collections(suffix):
    """Get collections filtered by type, with icon based on color_tag.
    suffix='mesh' -> only RE_MESH_COLLECTION
    suffix='mdf2' -> only RE_MDF_COLLECTION
    Falls back to name-based filtering if ~TYPE not present."""
    result = []
    
    type_map = {
        "mesh": "RE_MESH_COLLECTION",
        "mdf2": "RE_MDF_COLLECTION",
    }
    target_type = type_map.get(suffix, "")
    
    for c in bpy.data.collections:
        col_type = c.get("~TYPE", "")
        
        # Primary filter: by ~TYPE custom property (set by RE Mesh Editor)
        if col_type == target_type:
            if c.color_tag == "NONE":
                icon = "OUTLINER_COLLECTION"
            else:
                icon = f"COLLECTION_{c.color_tag}"
            result.append((c.name, c.name, "", icon, len(result)))
            continue
        
        # Fallback filter: by name suffix (if ~TYPE not set)
        if not col_type:
            if suffix == "mesh" and c.name.endswith(".mesh"):
                icon = "COLLECTION_COLOR_01"  # red
                result.append((c.name, c.name, "", icon, len(result)))
            elif suffix == "mdf2" and c.name.endswith(".mdf2"):
                icon = "COLLECTION_COLOR_04"  # blue
                result.append((c.name, c.name, "", icon, len(result)))
    
    if not result:
        result.append(("NONE", "No matching collections", "", "ERROR", 0))
    return result


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


class RE9_OT_ToggleGroup(bpy.types.Operator):
    """Expand/collapse this group"""
    bl_idname = "re9.toggle_group"
    bl_label = "Toggle Group"
    bl_options = {'INTERNAL'}

    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()

    def execute(self, context):
        key = _get_group_toggle_key(self.character_id, self.group_name)
        context.scene[key] = not context.scene.get(key, False)
        return {'FINISHED'}


class RE9_OT_PickMeshCollection(bpy.types.Operator):
    """Pick a mesh collection (red) for this export entry"""
    bl_idname = "re9.pick_mesh_collection"
    bl_label = "Pick Mesh Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()

    collection_name: bpy.props.EnumProperty(
        name="Mesh Collection",
        items=lambda self, context: _get_filtered_collections("mesh")
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "mesh", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickMdfCollection(bpy.types.Operator):
    """Pick a MDF2 collection (blue) for this export entry"""
    bl_idname = "re9.pick_mdf_collection"
    bl_label = "Pick MDF2 Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()

    collection_name: bpy.props.EnumProperty(
        name="MDF2 Collection",
        items=lambda self, context: _get_filtered_collections("mdf2")
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "mdf2", self.collection_name)
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
            group_name = group["name"]
            toggle_key = _get_group_toggle_key(character_id, group_name)
            is_expanded = scene.get(toggle_key, False)

            # Group header
            row = layout.row(align=True)
            op = row.operator("re9.toggle_group", text="",
                              icon='TRIA_DOWN' if is_expanded else 'TRIA_RIGHT',
                              emboss=False)
            op.character_id = character_id
            op.group_name = group_name
            row.label(text=f"{group_name} ({len(group['entries'])})", icon='FILE_FOLDER')

            if not is_expanded:
                continue

            group_box = layout.box()
            for entry in group["entries"]:
                entry_id = entry["id"]

                # Entry header
                header_text = entry_id
                note = entry.get("note", "")
                if note:
                    header_text += f"  [{note}]"
                group_box.label(text=header_text)

                # MESH row
                if entry.get("mesh"):
                    row = group_box.row(align=True)
                    mesh_enabled = _get_enabled(scene, character_id, entry_id, "mesh")
                    icon_mesh = 'CHECKBOX_HLT' if mesh_enabled else 'CHECKBOX_DEHLT'
                    op = row.operator("re9.toggle_entry", text="", icon=icon_mesh, emboss=False)
                    op.character_id = character_id
                    op.entry_id = entry_id
                    op.suffix = "mesh"

                    current_mesh_col = _get_binding(scene, character_id, entry_id, "mesh")
                    # Show icon based on collection color
                    mesh_icon = 'OUTLINER_OB_MESH'
                    if current_mesh_col and current_mesh_col in bpy.data.collections:
                        ct = bpy.data.collections[current_mesh_col].color_tag
                        mesh_icon = f"COLLECTION_{ct}" if ct != "NONE" else 'OUTLINER_OB_MESH'
                    row.label(text="MESH", icon=mesh_icon)

                    op_pick = row.operator("re9.pick_mesh_collection",
                                           text=current_mesh_col if current_mesh_col else "Select...",
                                           icon='DOWNARROW_HLT')
                    op_pick.character_id = character_id
                    op_pick.entry_id = entry_id

                # MDF2 row
                if entry.get("mdf2"):
                    row = group_box.row(align=True)
                    mdf2_enabled = _get_enabled(scene, character_id, entry_id, "mdf2")
                    icon_mdf = 'CHECKBOX_HLT' if mdf2_enabled else 'CHECKBOX_DEHLT'
                    op = row.operator("re9.toggle_entry", text="", icon=icon_mdf, emboss=False)
                    op.character_id = character_id
                    op.entry_id = entry_id
                    op.suffix = "mdf2"

                    current_mdf_col = _get_binding(scene, character_id, entry_id, "mdf2")
                    mdf_icon = 'MATERIAL'
                    if current_mdf_col and current_mdf_col in bpy.data.collections:
                        ct = bpy.data.collections[current_mdf_col].color_tag
                        mdf_icon = f"COLLECTION_{ct}" if ct != "NONE" else 'MATERIAL'
                    row.label(text=f"MDF2 x{len(entry['mdf2'])}", icon=mdf_icon)

                    op_pick = row.operator("re9.pick_mdf_collection",
                                           text=current_mdf_col if current_mdf_col else "Select...",
                                           icon='DOWNARROW_HLT')
                    op_pick.character_id = character_id
                    op_pick.entry_id = entry_id

    def execute(self, context):
        bpy.ops.re9.batch_export()
        return {'FINISHED'}


classes = [
    RE9_OT_ToggleEntry,
    RE9_OT_ToggleGroup,
    RE9_OT_PickMeshCollection,
    RE9_OT_PickMdfCollection,
    RE9_OT_BatchExportDialog,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)