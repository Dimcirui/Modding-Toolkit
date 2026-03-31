import bpy
from .batch_export import (
    _load_scheme, _get_binding, _set_binding,
    _get_enabled, _set_enabled,
    _get_simplified_group_binding, _set_simplified_group_binding,
    _get_simplified_empty_binding, _set_simplified_empty_binding,
)

EXPORTER_WINDOW_WIDTH = 600


def _get_group_toggle_key(character_id, group_name):
    key = f"re4grp_{character_id}_{group_name}"
    return key.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")


def _get_filtered_collections(suffix):
    result = []
    type_map = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION", "chain": "RE_CHAIN_COLLECTION"}
    name_sfx_map = {"mesh": ".mesh", "mdf2": ".mdf2", "chain": ".chain"}
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

class RE4_OT_ToggleEntry(bpy.types.Operator):
    bl_idname = "re4.toggle_entry"
    bl_label = "Toggle"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()
    def execute(self, context):
        current = _get_enabled(context.scene, self.character_id, self.entry_id, self.suffix)
        _set_enabled(context.scene, self.character_id, self.entry_id, self.suffix, not current)
        return {'FINISHED'}


class RE4_OT_ToggleGroup(bpy.types.Operator):
    bl_idname = "re4.toggle_group"
    bl_label = "Toggle Group"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    def execute(self, context):
        key = _get_group_toggle_key(self.character_id, self.group_name)
        context.scene[key] = not context.scene.get(key, False)
        return {'FINISHED'}


class RE4_OT_ToggleSimplified(bpy.types.Operator):
    bl_idname = "re4.toggle_simplified"
    bl_label = "Toggle Simplified"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        context.scene["re4_use_simplified"] = not context.scene.get("re4_use_simplified", True)
        return {'FINISHED'}


# ============================================================
# Collection / armature pickers
# ============================================================

class RE4_OT_PickMeshCollection(bpy.types.Operator):
    bl_idname = "re4.pick_mesh_collection"
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


class RE4_OT_PickMdfCollection(bpy.types.Operator):
    bl_idname = "re4.pick_mdf_collection"
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


class RE4_OT_PickChainCollection(bpy.types.Operator):
    bl_idname = "re4.pick_chain_collection"
    bl_label = "Pick Chain Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Chain Collection",
        items=lambda self, ctx: _get_filtered_collections("chain"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_binding(context.scene, self.character_id, self.entry_id, "chain", self.collection_name)
        return {'FINISHED'}


class RE4_OT_PickArmature(bpy.types.Operator):
    bl_idname = "re4.pick_armature"
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
class RE4_OT_PickSimplifiedGroupMesh(bpy.types.Operator):
    bl_idname = "re4.pick_sg_mesh"
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


class RE4_OT_PickSimplifiedGroupMdf(bpy.types.Operator):
    bl_idname = "re4.pick_sg_mdf"
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


class RE4_OT_PickSimplifiedGroupChain(bpy.types.Operator):
    bl_idname = "re4.pick_sg_chain"
    bl_label = "Pick Group Chain"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Chain",
        items=lambda self, ctx: _get_filtered_collections("chain"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_group_binding(context.scene, self.character_id, self.group_name, "chain", self.collection_name)
        return {'FINISHED'}


class RE4_OT_PickSimplifiedEmptyMesh(bpy.types.Operator):
    bl_idname = "re4.pick_se_mesh"
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


class RE4_OT_PickSimplifiedEmptyMdf(bpy.types.Operator):
    bl_idname = "re4.pick_se_mdf"
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


class RE4_OT_PickSimplifiedEmptyChain(bpy.types.Operator):
    bl_idname = "re4.pick_se_chain"
    bl_label = "Pick Empty Chain"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"
    character_id: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(name="Empty Chain",
        items=lambda self, ctx: _get_filtered_collections("chain"))
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        if self.collection_name != "NONE":
            _set_simplified_empty_binding(context.scene, self.character_id, "chain", self.collection_name)
        return {'FINISHED'}


class RE4_OT_ClearSimplifiedGroup(bpy.types.Operator):
    bl_idname = "re4.clear_sg"
    bl_label = "Clear Group Binding"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    suffix: bpy.props.StringProperty()
    def execute(self, context):
        _set_simplified_group_binding(context.scene, self.character_id, self.group_name, self.suffix, "")
        return {'FINISHED'}

class RE4_OT_ClearSimplifiedEmpty(bpy.types.Operator):
    bl_idname = "re4.clear_se"
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

class RE4_OT_BatchExportDialog(bpy.types.Operator):
    """RE4 batch export dialog"""
    bl_idname = "re4.batch_export_dialog"
    bl_label = "RE4 Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

        layout.prop(settings, "re4_export_scheme", text="Character")

        # Natives root
        natives_root = scene.get("re4_natives_root", "")
        row = layout.row(align=True)
        row.operator("re4.set_natives_root", text="Natives Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="Not set", icon='ERROR')

        scheme_file = settings.re4_export_scheme
        if not scheme_file or scheme_file == 'NONE':
            layout.label(text="Select a character scheme", icon='INFO')
            return
        scheme = _load_scheme(scheme_file)
        if not scheme:
            layout.label(text="Failed to load scheme", icon='ERROR')
            return

        character_id = scheme["character_id"]
        use_simplified = scene.get("re4_use_simplified", True)

        # Simplified toggle
        layout.separator()
        row = layout.row()
        simp_icon = 'CHECKBOX_HLT' if use_simplified else 'CHECKBOX_DEHLT'
        row.operator("re4.toggle_simplified", text="", icon=simp_icon, emboss=False)
        row.label(text="Use Simplified Export", icon='SORTBYEXT')

        # --- FBXSKEL ---
        fbxskel_path = scheme.get("fbxskel", "")
        if fbxskel_path:
            layout.separator()
            box = layout.box()
            row = box.row(align=True)
            fbx_en = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            op = row.operator("re4.toggle_entry", text="",
                              icon='CHECKBOX_HLT' if fbx_en else 'CHECKBOX_DEHLT', emboss=False)
            op.character_id = character_id; op.entry_id = "_fbxskel"; op.suffix = "fbxskel"
            row.label(text="FBXSKEL", icon='ARMATURE_DATA')
            cur_arm = _get_binding(scene, character_id, "_fbxskel", "fbxskel")
            op_p = row.operator("re4.pick_armature", text=cur_arm if cur_arm else "Select armature...",
                                icon='DOWNARROW_HLT')
            op_p.character_id = character_id
            # 假头法
            row2 = box.row(align=True)
            row2.prop(settings, "re4_use_fakebone", icon='BONE_DATA')
            if settings.re4_use_fakebone:
                native_skel = scheme.get("native_skeleton", "")
                if native_skel:
                    row2.label(text=native_skel, icon='FILE')
                else:
                    row2.label(text="预设未配置 native_skeleton", icon='ERROR')

        layout.separator()
        layout.prop(settings, "re4_use_blank_export", icon='FILE_BLANK')

        if use_simplified:
            self._draw_simplified(layout, scene, scheme, character_id, settings.re4_use_blank_export)
        else:
            self._draw_normal(layout, scene, scheme, character_id)

    def _draw_simplified(self, layout, scene, scheme, character_id, use_blank=False):
        # Global empty model settings — hidden when blank export is on
        if not use_blank:
            box = layout.box()
            box.label(text="Empty Model Collections (Global)", icon='GHOST_ENABLED')

            row = box.row(align=True)
            row.label(text="Empty MESH:", icon='OUTLINER_OB_MESH')
            cur = _get_simplified_empty_binding(scene, character_id, "mesh")
            op = row.operator("re4.pick_se_mesh", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.character_id = character_id

            row = box.row(align=True)
            row.label(text="Empty MDF2:", icon='MATERIAL')
            cur = _get_simplified_empty_binding(scene, character_id, "mdf2")
            op = row.operator("re4.pick_se_mdf", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.character_id = character_id

            row = box.row(align=True)
            row.label(text="Empty Chain:", icon='CONSTRAINT_BONE')
            cur = _get_simplified_empty_binding(scene, character_id, "chain")
            op = row.operator("re4.pick_se_chain", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.character_id = character_id

        layout.separator()

        for group in scheme["groups"]:
            group_name = group["name"]
            has_user = any(e.get("simplified") == "user" for e in group["entries"])
            if not has_user:
                row = layout.row()
                row.label(text=f"{group_name}", icon='FILE_FOLDER')
                empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
                skip_count  = sum(1 for e in group["entries"] if e.get("simplified") == "skip")
                info = []
                if empty_count: info.append(f"{empty_count} empty")
                if skip_count:  info.append(f"{skip_count} skip")
                row.label(text=f"({', '.join(info)})")
                continue

            box = layout.box()
            box.label(text=f"{group_name}", icon='FILE_FOLDER')

            # Check which file types appear in "user" entries for this group
            user_entries = [e for e in group["entries"] if e.get("simplified") == "user"]
            has_mesh  = any(e.get("mesh")  for e in user_entries)
            has_mdf2  = any(e.get("mdf2")  for e in user_entries)
            has_chain = any(e.get("chain") for e in user_entries)

            if has_mesh:
                row = box.row(align=True)
                row.label(text="MESH:", icon='OUTLINER_OB_MESH')
                cur = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
                op = row.operator("re4.pick_sg_mesh", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op.character_id = character_id; op.group_name = group_name
                if cur:
                    op_c = row.operator("re4.clear_sg", text="", icon='X')
                    op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mesh"

            if has_mdf2:
                row = box.row(align=True)
                row.label(text="MDF2:", icon='MATERIAL')
                cur = _get_simplified_group_binding(scene, character_id, group_name, "mdf2")
                op = row.operator("re4.pick_sg_mdf", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op.character_id = character_id; op.group_name = group_name
                if cur:
                    op_c = row.operator("re4.clear_sg", text="", icon='X')
                    op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mdf2"

            if has_chain:
                row = box.row(align=True)
                row.label(text="Chain:", icon='CONSTRAINT_BONE')
                cur = _get_simplified_group_binding(scene, character_id, group_name, "chain")
                op = row.operator("re4.pick_sg_chain", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op.character_id = character_id; op.group_name = group_name
                if cur:
                    op_c = row.operator("re4.clear_sg", text="", icon='X')
                    op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "chain"

            user_count  = sum(1 for e in group["entries"] if e.get("simplified") == "user")
            empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
            skip_count  = sum(1 for e in group["entries"] if e.get("simplified") == "skip")
            info = [f"{user_count} user"]
            if empty_count: info.append(f"{empty_count} empty")
            if skip_count:  info.append(f"{skip_count} skip")
            box.label(text=f"Entries: {', '.join(info)}")

    def _draw_normal(self, layout, scene, scheme, character_id):
        for group in scheme["groups"]:
            group_name = group["name"]
            toggle_key = _get_group_toggle_key(character_id, group_name)
            is_expanded = scene.get(toggle_key, False)

            row = layout.row(align=True)
            op = row.operator("re4.toggle_group", text="",
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
                    op = row.operator("re4.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mesh"
                    cur = _get_binding(scene, character_id, entry_id, "mesh")
                    ic = 'OUTLINER_OB_MESH'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text="MESH", icon=ic)
                    op_p = row.operator("re4.pick_mesh_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

                if entry.get("mdf2"):
                    row = group_box.row(align=True)
                    en = _get_enabled(scene, character_id, entry_id, "mdf2")
                    op = row.operator("re4.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mdf2"
                    cur = _get_binding(scene, character_id, entry_id, "mdf2")
                    ic = 'MATERIAL'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text=f"MDF2 x{len(entry['mdf2'])}", icon=ic)
                    op_p = row.operator("re4.pick_mdf_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

                if entry.get("chain"):
                    row = group_box.row(align=True)
                    en = _get_enabled(scene, character_id, entry_id, "chain")
                    op = row.operator("re4.toggle_entry", text="",
                                      icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                    op.character_id = character_id; op.entry_id = entry_id; op.suffix = "chain"
                    cur = _get_binding(scene, character_id, entry_id, "chain")
                    ic = 'CONSTRAINT_BONE'
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE": ic = f"COLLECTION_{ct}"
                    row.label(text="Chain", icon=ic)
                    op_p = row.operator("re4.pick_chain_collection",
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.character_id = character_id; op_p.entry_id = entry_id

    def execute(self, context):
        bpy.ops.re4.batch_export()
        return {'FINISHED'}


classes = [
    RE4_OT_ToggleEntry,
    RE4_OT_ToggleGroup,
    RE4_OT_ToggleSimplified,
    RE4_OT_PickMeshCollection,
    RE4_OT_PickMdfCollection,
    RE4_OT_PickChainCollection,
    RE4_OT_PickArmature,
    RE4_OT_PickSimplifiedGroupMesh,
    RE4_OT_PickSimplifiedGroupMdf,
    RE4_OT_PickSimplifiedGroupChain,
    RE4_OT_PickSimplifiedEmptyMesh,
    RE4_OT_PickSimplifiedEmptyMdf,
    RE4_OT_PickSimplifiedEmptyChain,
    RE4_OT_ClearSimplifiedGroup,
    RE4_OT_ClearSimplifiedEmpty,
    RE4_OT_BatchExportDialog,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
