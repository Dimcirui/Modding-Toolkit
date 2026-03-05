import bpy
from .batch_export import (
    _load_scheme, _get_binding, _set_binding,
    _get_enabled, _set_enabled, get_schemes_callback,
    _get_simplified_group_binding, _set_simplified_group_binding,
    _get_simplified_empty_binding, _set_simplified_empty_binding,
)

EXPORTER_WINDOW_WIDTH = 600


def _get_group_toggle_key(character_id, group_name):
    key = f"re9grp_{character_id}_{group_name}"
    return key.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")


def _get_filtered_collections(suffix):
    result = []
    type_map = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION", "sfur": "RE_SFUR_COLLECTION"}
    name_sfx_map = {"mesh": ".mesh", "mdf2": ".mdf2", "sfur": ".sfur"}
    target_type = type_map.get(suffix, "")
    name_sfx = name_sfx_map.get(suffix, "")
    for c in bpy.data.collections:
        col_type = c.get("~TYPE", "")
        if col_type == target_type:
            icon = f"COLLECTION_{c.color_tag}" if c.color_tag != "NONE" else "OUTLINER_COLLECTION"
            result.append((c.name, c.name, "", icon, len(result)))
            continue
        if not col_type and name_sfx and c.name.endswith(name_sfx):
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not result:
        result.append(("NONE", "No matching collections", "", "ERROR", 0))
    return result


def _get_armatures():
    result = []
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            result.append((obj.name, obj.name, "", 'ARMATURE_DATA', len(result)))
    if not result:
        result.append(("NONE", "No armatures", "", "ERROR", 0))
    return result


# ============================================================
# Toggle operators
# ============================================================

class RE9_OT_ToggleEntry(bpy.types.Operator):
    bl_idname = "re9.toggle_entry"
    bl_label = "Toggle"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()
    def execute(self, context):
        current = _get_enabled(context.scene, self.character_id, self.entry_id, self.suffix)
        _set_enabled(context.scene, self.character_id, self.entry_id, self.suffix, not current)
        return {'FINISHED'}


class RE9_OT_ToggleGroup(bpy.types.Operator):
    bl_idname = "re9.toggle_group"
    bl_label = "Toggle Group"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    def execute(self, context):
        key = _get_group_toggle_key(self.character_id, self.group_name)
        context.scene[key] = not context.scene.get(key, False)
        return {'FINISHED'}


class RE9_OT_ToggleSimplified(bpy.types.Operator):
    bl_idname = "re9.toggle_simplified"
    bl_label = "Toggle Simplified"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        context.scene["re9_use_simplified"] = not context.scene.get("re9_use_simplified", False)
        return {'FINISHED'}


# ============================================================
# Collection / armature pickers
# ============================================================

class RE9_OT_PickMeshCollection(bpy.types.Operator):
    bl_idname = "re9.pick_mesh_collection"
    bl_label = "Pick Mesh Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Mesh Collection",
        items=lambda self, ctx: _get_filtered_collections("mesh"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "mesh", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickMdfCollection(bpy.types.Operator):
    bl_idname = "re9.pick_mdf_collection"
    bl_label = "Pick MDF2 Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="MDF2 Collection",
        items=lambda self, ctx: _get_filtered_collections("mdf2"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "mdf2", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickSfurCollection(bpy.types.Operator):
    bl_idname = "re9.pick_sfur_collection"
    bl_label = "Pick SFur Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="SFur Collection",
        items=lambda self, ctx: _get_filtered_collections("sfur"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "sfur", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickArmature(bpy.types.Operator):
    bl_idname = "re9.pick_armature"
    bl_label = "Pick Armature"
    bl_options = {'INTERNAL'}
    bl_property = "armature_name"
    character_id: bpy.props.StringProperty()
    armature_name: bpy.props.EnumProperty(name="Armature",
        items=lambda self, ctx: _get_armatures())
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.armature_name != "NONE":
            _set_binding(context.scene, self.character_id, "_fbxskel", "fbxskel", self.armature_name)
        return {'FINISHED'}


# Simplified mode: per-group pickers
class RE9_OT_PickSimplifiedGroupMesh(bpy.types.Operator):
    bl_idname = "re9.pick_sg_mesh"
    bl_label = "Pick Group Mesh"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Mesh",
        items=lambda self, ctx: _get_filtered_collections("mesh"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_group_binding(context.scene, self.character_id, self.group_name, "mesh", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickSimplifiedGroupMdf(bpy.types.Operator):
    bl_idname = "re9.pick_sg_mdf"
    bl_label = "Pick Group MDF2"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="MDF2",
        items=lambda self, ctx: _get_filtered_collections("mdf2"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_group_binding(context.scene, self.character_id, self.group_name, "mdf2", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickSimplifiedEmptyMesh(bpy.types.Operator):
    bl_idname = "re9.pick_se_mesh"
    bl_label = "Pick Empty Mesh"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Empty Mesh",
        items=lambda self, ctx: _get_filtered_collections("mesh"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_empty_binding(context.scene, self.character_id, "mesh", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickSimplifiedEmptyMdf(bpy.types.Operator):
    bl_idname = "re9.pick_se_mdf"
    bl_label = "Pick Empty MDF2"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Empty MDF2",
        items=lambda self, ctx: _get_filtered_collections("mdf2"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_empty_binding(context.scene, self.character_id, "mdf2", self.collection_name)
        return {'FINISHED'}


class RE9_OT_PickSimplifiedEmptySfur(bpy.types.Operator):
    bl_idname = "re9.pick_se_sfur"
    bl_label = "Pick Empty SFur"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Empty SFur",
        items=lambda self, ctx: _get_filtered_collections("sfur"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_empty_binding(context.scene, self.character_id, "sfur", self.collection_name)
        return {'FINISHED'}
    
class RE9_OT_ClearSimplifiedGroup(bpy.types.Operator):
    bl_idname = "re9.clear_sg"
    bl_label = "Clear Group Binding"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()
    def execute(self, context):
        _set_simplified_group_binding(context.scene, self.character_id, self.group_name, self.suffix, "")
        return {'FINISHED'}

class RE9_OT_ClearSimplifiedEmpty(bpy.types.Operator):
    bl_idname = "re9.clear_se"
    bl_label = "Clear Empty Binding"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()
    def execute(self, context):
        _set_simplified_empty_binding(context.scene, self.character_id, self.suffix, "")
        return {'FINISHED'}


# ============================================================
# Main dialog
# ============================================================

class RE9_OT_BatchExportDialog(bpy.types.Operator):
    """RE9 batch export dialog"""
    bl_idname = "re9.batch_export_dialog"
    bl_label = "RE9 Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

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
        use_simplified = scene.get("re9_use_simplified", False)

        # Simplified toggle
        layout.separator()
        row = layout.row()
        simp_icon = 'CHECKBOX_HLT' if use_simplified else 'CHECKBOX_DEHLT'
        row.operator("re9.toggle_simplified", text="", icon=simp_icon, emboss=False)
        row.label(text="Use Simplified Export", icon='SORTBYEXT')

        # --- FBXSKEL (always shown) ---
        fbxskel_path = scheme.get("fbxskel", "")
        if fbxskel_path:
            layout.separator()
            box = layout.box()
            row = box.row(align=True)
            fbx_en = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            op = row.operator("re9.toggle_entry", text="",
                              icon='CHECKBOX_HLT' if fbx_en else 'CHECKBOX_DEHLT', emboss=False)
            op.character_id = character_id; op.entry_id = "_fbxskel"; op.suffix = "fbxskel"
            row.label(text="FBXSKEL", icon='ARMATURE_DATA')
            cur_arm = _get_binding(scene, character_id, "_fbxskel", "fbxskel")
            op_p = row.operator("re9.pick_armature", text=cur_arm if cur_arm else "Select armature...",
                                icon='DOWNARROW_HLT')
            op_p.character_id = character_id

        layout.separator()

        if use_simplified:
            self._draw_simplified(layout, scene, scheme, character_id)
        else:
            self._draw_normal(layout, scene, scheme, character_id)

    def _draw_simplified(self, layout, scene, scheme, character_id):
        # Global empty model settings
        box = layout.box()
        box.label(text="Empty Model Collections (Global)", icon='GHOST_ENABLED')

        row = box.row(align=True)
        row.label(text="Empty MESH:", icon='OUTLINER_OB_MESH')
        cur = _get_simplified_empty_binding(scene, character_id, "mesh")
        op = row.operator("re9.pick_se_mesh", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
        op.character_id = character_id

        row = box.row(align=True)
        row.label(text="Empty MDF2:", icon='MATERIAL')
        cur = _get_simplified_empty_binding(scene, character_id, "mdf2")
        op = row.operator("re9.pick_se_mdf", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
        op.character_id = character_id

        row = box.row(align=True)
        row.label(text="Empty SFUR:", icon='OUTLINER_OB_CURVES')
        cur = _get_simplified_empty_binding(scene, character_id, "sfur")
        op = row.operator("re9.pick_se_sfur", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
        op.character_id = character_id

        layout.separator()

        # Per-group user model settings
        for group in scheme["groups"]:
            group_name = group["name"]
            # Check if this group has any "user" entries
            has_user = any(e.get("simplified") == "user" for e in group["entries"])
            if not has_user:
                # All empty or skip - just show label
                row = layout.row()
                row.label(text=f"{group_name}", icon='FILE_FOLDER')
                # Count types
                empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
                skip_count = sum(1 for e in group["entries"] if e.get("simplified") == "skip")
                info = []
                if empty_count: info.append(f"{empty_count} empty")
                if skip_count: info.append(f"{skip_count} skip")
                row.label(text=f"({', '.join(info)})")
                continue

            box = layout.box()
            box.label(text=f"{group_name}", icon='FILE_FOLDER')

            # User model selectors for this group
            row = box.row(align=True)
            row.label(text="MESH:", icon='OUTLINER_OB_MESH')
            cur = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
            op = row.operator("re9.pick_sg_mesh", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.character_id = character_id; op.group_name = group_name
            if cur:
                op_c = row.operator("re9.clear_sg", text="", icon='X')
                op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mesh"

            row = box.row(align=True)
            row.label(text="MDF2:", icon='MATERIAL')
            cur = _get_simplified_group_binding(scene, character_id, group_name, "mdf2")
            op = row.operator("re9.pick_sg_mdf", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.character_id = character_id; op.group_name = group_name
            if cur:
                op_c = row.operator("re9.clear_sg", text="", icon='X')
                op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mdf2"

            # Show summary
            user_count = sum(1 for e in group["entries"] if e.get("simplified") == "user")
            empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
            skip_count = sum(1 for e in group["entries"] if e.get("simplified") == "skip")
            info = [f"{user_count} user"]
            if empty_count: info.append(f"{empty_count} empty")
            if skip_count: info.append(f"{skip_count} skip")
            box.label(text=f"Entries: {', '.join(info)}")

    def _draw_normal(self, layout, scene, scheme, character_id):
        for group in scheme["groups"]:
            group_name = group["name"]
            toggle_key = _get_group_toggle_key(character_id, group_name)
            is_expanded = scene.get(toggle_key, False)

            row = layout.row(align=True)
            op = row.operator("re9.toggle_group", text="",
                              icon='TRIA_DOWN' if is_expanded else 'TRIA_RIGHT', emboss=False)
            op.character_id = character_id; op.group_name = group_name
            row.label(text=f"{group_name} ({len(group['entries'])})", icon='FILE_FOLDER')

            if not is_expanded:
                continue

            group_box = layout.box()
            for entry in group["entries"]:
                entry_id = entry["id"]
                header = entry_id
                note = entry.get("note", "")
                if note: header += f"  [{note}]"
                group_box.label(text=header)

                if entry.get("mesh"):
                    row = group_box.row(align=True)
                    en = _get_enabled(scene, character_id, entry_id, "mesh")
                    op = row.operator("re9.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mesh"
                    cur = _get_binding(scene, character_id, entry_id, "mesh")
                    ic = 'OUTLINER_OB_MESH'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text="MESH", icon=ic)
                    op_p = row.operator("re9.pick_mesh_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

                if entry.get("mdf2"):
                    row = group_box.row(align=True)
                    en = _get_enabled(scene, character_id, entry_id, "mdf2")
                    op = row.operator("re9.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mdf2"
                    cur = _get_binding(scene, character_id, entry_id, "mdf2")
                    ic = 'MATERIAL'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text=f"MDF2 x{len(entry['mdf2'])}", icon=ic)
                    op_p = row.operator("re9.pick_mdf_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

                if entry.get("sfur"):
                    row = group_box.row(align=True)
                    en = _get_enabled(scene, character_id, entry_id, "sfur")
                    op = row.operator("re9.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "sfur"
                    cur = _get_binding(scene, character_id, entry_id, "sfur")
                    ic = 'OUTLINER_OB_CURVES'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text="SFUR", icon=ic)
                    op_p = row.operator("re9.pick_sfur_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

    def execute(self, context):
        bpy.ops.re9.batch_export()
        return {'FINISHED'}


classes = [
    RE9_OT_ToggleEntry,
    RE9_OT_ToggleGroup,
    RE9_OT_ToggleSimplified,
    RE9_OT_PickMeshCollection,
    RE9_OT_PickMdfCollection,
    RE9_OT_PickSfurCollection,
    RE9_OT_PickArmature,
    RE9_OT_PickSimplifiedGroupMesh,
    RE9_OT_PickSimplifiedGroupMdf,
    RE9_OT_PickSimplifiedEmptyMesh,
    RE9_OT_PickSimplifiedEmptyMdf,
    RE9_OT_PickSimplifiedEmptySfur,
    RE9_OT_BatchExportDialog,
    RE9_OT_ClearSimplifiedGroup,
    RE9_OT_ClearSimplifiedEmpty,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)