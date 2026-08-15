import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty
from ...core.i18n import T
from ...core import pre_export_check_ops as pec
from .batch_export import (
    _load_scheme, _get_binding, _set_binding,
    _get_enabled, _set_enabled,
    _get_simplified_group_binding, _set_simplified_group_binding,
    _set_simplified_empty_binding,
    resolve_mesh_mdf2,
)

EXPORTER_WINDOW_WIDTH = 600


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


class RE4_OT_ToggleSimplified(bpy.types.Operator):
    bl_idname = "re4.toggle_simplified"
    bl_label = "Toggle Simplified"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        context.scene["re4_use_simplified"] = not context.scene.get("re4_use_simplified", True)
        return {'FINISHED'}


# ── Unified collection picker ─────────────────────────────────────────────────
# One operator for what used to be 9: 3 slots x 3 scopes, each a verbatim
# copy of this body differing only in a suffix string. The scope/slot pair now
# arrives as operator properties -- the same shape mhwi/mhws/mhrs have always
# used (see MHWS_OT_PickCollection's `filetype`), which is also why the dynamic
# `items=` callback reading self.slot is safe: those three already ship it.
#
# 'EMPTY' has no call site. The per-entry "empty" bindings are only ever cleared
# (re4.clear_se), never picked, so the 3 RE4_OT_PickSimplifiedEmpty*
# classes it replaces were unreachable. The scope is kept because the capability
# behind it exists -- wiring a button is now one line rather than a new class.

class RE4_OT_PickBinding(bpy.types.Operator):
    bl_idname = "re4.pick_binding"
    bl_label = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    #: 'ENTRY' | 'GROUP' | 'EMPTY'. A plain string, not an enum, because
    #: bl_property already designates collection_name as the searched enum and
    #: no operator in this addon has been proven to work with a second one.
    scope: bpy.props.StringProperty(default="ENTRY")
    slot: bpy.props.StringProperty()
    character_id: bpy.props.StringProperty()
    entry_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(
        name="Collection",
        items=lambda self, ctx: _get_filtered_collections(self.slot)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name != "NONE":
            scene = context.scene
            if self.scope == "GROUP":
                _set_simplified_group_binding(scene, self.character_id,
                                              self.group_name, self.slot,
                                              self.collection_name)
            elif self.scope == "EMPTY":
                _set_simplified_empty_binding(scene, self.character_id, self.slot,
                                              self.collection_name)
            elif self.scope == "ENTRY":
                _set_binding(scene, self.character_id, self.entry_id, self.slot,
                             self.collection_name)
            else:
                # Silently doing nothing is how a typo'd scope would hide.
                self.report({'ERROR'}, f"unknown pick scope {self.scope!r}")
                return {'CANCELLED'}
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


# ── Copy/paste a group's bindings ───────────────────────────────────────────
# The master-detail layout makes this a natural fit: many groups share the
# same collections (costume variants, LOD-adjacent parts), and re-picking
# each one by hand is exactly the busywork this addon already avoids
# elsewhere. Module-level, not Scene data -- it is per-session clipboard
# state, not part of the .blend, same reasoning as pre_export_check_ops's
# _LAST_RUN.
_group_clipboard = {}


def _group_supported_slots(scheme, group_name):
    """Which of mesh/mdf2/chain a group's "user"-tagged entries actually use --
    the same has_mesh/has_mdf2/has_chain computation _draw_group_detail_simplified
    draws its pickers from, needed again here so paste can skip a slot the
    target group has no picker for at all."""
    group = next((g for g in scheme["groups"] if g["name"] == group_name), None) if scheme else None
    if group is None:
        return {}
    user_entries = [e for e in group["entries"] if e.get("simplified") == "user"]
    return {
        "mesh":  any(e.get("mesh")  for e in user_entries),
        "mdf2":  any(e.get("mdf2")  for e in user_entries),
        "chain": any(e.get("chain") for e in user_entries),
    }


class RE4_OT_CopyGroupBindings(bpy.types.Operator):
    bl_idname = "re4.copy_group_bindings"
    bl_label = "Copy Group Bindings"
    bl_options = {'INTERNAL'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        return T("re4.batch_export_ui.copy_bindings_desc")

    def execute(self, context):
        global _group_clipboard
        scene = context.scene
        clip = {}
        for slot in ("mesh", "mdf2", "chain"):
            cur = _get_simplified_group_binding(scene, self.character_id, self.group_name, slot)
            if cur:
                clip[slot] = cur
        _group_clipboard = clip
        if clip:
            self.report({'INFO'}, T("re4.batch_export_ui.copy_done").format(
                n=len(clip), group=self.group_name))
        else:
            self.report({'WARNING'}, T("re4.batch_export_ui.copy_nothing").format(
                group=self.group_name))
        return {'FINISHED'}


class RE4_OT_PasteGroupBindings(bpy.types.Operator):
    bl_idname = "re4.paste_group_bindings"
    bl_label = "Paste Group Bindings"
    bl_options = {'INTERNAL', 'UNDO'}
    character_id: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        return T("re4.batch_export_ui.paste_bindings_desc")

    @classmethod
    def poll(cls, context):
        return bool(_group_clipboard)

    def execute(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings
        scheme = _load_scheme(settings.re4_export_scheme)
        supported = _group_supported_slots(scheme, self.group_name)

        applied = 0
        for slot, value in _group_clipboard.items():
            if not supported.get(slot):
                continue
            _set_simplified_group_binding(scene, self.character_id, self.group_name, slot, value)
            applied += 1

        if applied:
            self.report({'INFO'}, T("re4.batch_export_ui.paste_done").format(
                n=applied, group=self.group_name))
        else:
            self.report({'WARNING'}, T("re4.batch_export_ui.paste_nothing").format(
                group=self.group_name))
        return {'FINISHED'}


# ============================================================
# Group list -- left column of the master-detail layout
# ============================================================
# A scheme can run to over a dozen groups and 50+ entries (re9's Leon.json is
# 13/55); drawing every group's entries inline, expanded or not, is what made
# this dialog outgrow the screen. Only the selected group's detail is drawn
# now, so the popup's height is bounded by its biggest single group instead of
# the whole scheme.

class RE4_GroupListItem(bpy.types.PropertyGroup):
    group_name: StringProperty()
    entry_count: IntProperty()
    #: Set from the aggregated pre-export check right before this list draws,
    #: so a group with a problem is visible without opening the report.
    has_issues: BoolProperty()


class RE4_UL_Groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        layout.label(text=f"{item.group_name} ({item.entry_count})",
                     icon='ERROR' if item.has_issues else 'FILE_FOLDER')


def _gather_check_pairs(scene, character_id, scheme, use_simplified):
    """``[(label, mdf_col, mesh_col), ...]`` for whatever this batch would
    actually export -- reads through the same ``resolve_mesh_mdf2`` the real
    export loop uses, so an entry that resolves to nothing there (skipped,
    disabled, or a blank-export fallback) contributes nothing to check either.

    Simplified mode checks once per group (the group-level binding covers
    every "user" entry in it together); normal mode checks once per entry.
    """
    pairs = []
    for group in scheme["groups"]:
        group_name = group["name"]
        if use_simplified:
            user_entries = [e for e in group["entries"] if e.get("simplified") == "user"]
            if not user_entries or not any(e.get("mdf2") for e in user_entries):
                continue
            mesh_name, mdf_name = resolve_mesh_mdf2(
                scene, character_id, group, {"simplified": "user"}, True)
            mdf_col = bpy.data.collections.get(mdf_name) if mdf_name else None
            if mdf_col is None:
                continue
            mesh_col = bpy.data.collections.get(mesh_name) if mesh_name else None
            pairs.append((group_name, mdf_col, mesh_col))
        else:
            for entry in group["entries"]:
                if not entry.get("mdf2"):
                    continue
                mesh_name, mdf_name = resolve_mesh_mdf2(scene, character_id, group, entry, False)
                mdf_col = bpy.data.collections.get(mdf_name) if mdf_name else None
                if mdf_col is None:
                    continue
                mesh_col = bpy.data.collections.get(mesh_name) if mesh_name else None
                pairs.append((f"{group_name} / {entry['id']}", mdf_col, mesh_col))
    return pairs


def _mark_group_issues(groups, entries):
    """Set ``has_issues`` on each ``RE4_GroupListItem`` by checking whether any
    check entry's label was prefixed with that group's pair label -- either
    the bare group name (simplified) or ``"<group> / <entry>"`` (normal)."""
    for item in groups:
        prefix_group = item.group_name + " ·"
        prefix_entry = item.group_name + " / "
        item.has_issues = any(
            e['label'].startswith(prefix_group) or e['label'].startswith(prefix_entry)
            for e in entries)


# ============================================================
# Main dialog
# ============================================================

class RE4_OT_BatchExportDialog(bpy.types.Operator):
    """RE4 batch export dialog"""
    bl_idname = "re4.batch_export_dialog"
    bl_label = "RE4 Batch Exporter"
    bl_options = {'REGISTER'}

    groups: CollectionProperty(type=RE4_GroupListItem)
    group_index: IntProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def _sync_groups(self, scheme, scheme_file):
        """Repopulate the group list only when the selected character scheme
        actually changed since the last draw -- rebuilding it every redraw
        would reset ``group_index`` (and the scroll position with it) on
        every unrelated property change."""
        if getattr(self, '_groups_scheme_file', None) == scheme_file:
            return
        self._groups_scheme_file = scheme_file
        self.groups.clear()
        for group in scheme["groups"]:
            item = self.groups.add()
            item.group_name = group["name"]
            item.entry_count = len(group["entries"])
        self.group_index = 0

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
        self._sync_groups(scheme, scheme_file)

        # Simplified toggle
        layout.separator()
        row = layout.row()
        simp_icon = 'CHECKBOX_HLT' if use_simplified else 'CHECKBOX_DEHLT'
        row.operator("re4.toggle_simplified", text="", icon=simp_icon, emboss=False)
        row.label(text="Use Simplified Export", icon='SORTBYEXT')

        # --- FBXSKEL ---
        fbxskel_raw = scheme.get("fbxskel", "")
        fbxskel_paths = ([fbxskel_raw] if isinstance(fbxskel_raw, str) else list(fbxskel_raw))
        fbxskel_paths = [p for p in fbxskel_paths if p]
        if fbxskel_paths:
            layout.separator()
            box = layout.box()
            row = box.row(align=True)
            fbx_en = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            op = row.operator("re4.toggle_entry", text="",
                              icon='CHECKBOX_HLT' if fbx_en else 'CHECKBOX_DEHLT', emboss=False)
            op.character_id = character_id; op.entry_id = "_fbxskel"; op.suffix = "fbxskel"
            fbx_label = f"FBXSKEL (×{len(fbxskel_paths)})" if len(fbxskel_paths) > 1 else "FBXSKEL"
            row.label(text=fbx_label, icon='ARMATURE_DATA')
            if not settings.re4_use_body_arm:
                cur_arm = _get_binding(scene, character_id, "_fbxskel", "fbxskel")
                op_p = row.operator("re4.pick_armature", text=cur_arm if cur_arm else "Select armature...",
                                    icon='DOWNARROW_HLT')
                op_p.character_id = character_id
            # 假头法
            row2 = box.row(align=True)
            row2.prop(settings, "re4_use_fakebone", text=T("ui.prop.use_fakebone"), icon='BONE_DATA')
            if settings.re4_use_fakebone:
                native_skel = scheme.get("native_skeleton", "")
                if native_skel:
                    row2.label(text=native_skel, icon='FILE')
                else:
                    row2.label(text=T("re4.batch_export_ui.preset_missing_native_skeleton"), icon='ERROR')
            # 使用身体骨架
            row3 = box.row(align=True)
            row3.prop(settings, "re4_use_body_arm", text=T("ui.prop.use_body_armature"), icon='ARMATURE_DATA')
            if settings.re4_use_body_arm:
                body_groups = scheme.get("body_groups_for_fbxskel", [])
                if body_groups:
                    row3.label(text=" > ".join(body_groups), icon='INFO')
                else:
                    row3.label(text=T("re4.batch_export_ui.preset_missing_body_groups"), icon='ERROR')

        layout.separator()
        layout.prop(settings, "re4_use_blank_export", text=T("ui.prop.use_blank_export"), icon='FILE_BLANK')
        layout.prop(settings, "re4_triangulate_face", text=T("ui.prop.triangulate_face"), icon='MOD_TRIANGULATE')

        # Run the check before the list draws, so each row can carry its own
        # issue icon; the summary line at the bottom reuses the same result.
        pairs = _gather_check_pairs(scene, character_id, scheme, use_simplified)
        entries = pec.ensure_checked(self, context, 'RE4', pairs, natives_root)
        _mark_group_issues(self.groups, entries)

        layout.separator()
        split = layout.split(factor=0.35)
        col1, col2 = split.column(), split.column()
        col1.template_list("RE4_UL_Groups", "", self, "groups", self, "group_index",
                           rows=max(4, min(len(self.groups), 10)))

        selected_group = None
        if self.groups and 0 <= self.group_index < len(self.groups):
            item = self.groups[self.group_index]
            selected_group = next((g for g in scheme["groups"] if g["name"] == item.group_name), None)

        # Below the list rather than inside the detail box: sitting next to
        # the MESH/MDF2/Chain pickers made it easy to mistake for one more
        # slot rather than an action on the whole group. Simplified-mode
        # only -- normal mode's bindings are per-entry, not per-group, so
        # there is nothing group-level here for copy/paste to act on.
        if use_simplified and selected_group is not None:
            user_entries = [e for e in selected_group["entries"] if e.get("simplified") == "user"]
            if user_entries:
                row = col1.row(align=True)
                op_copy = row.operator("re4.copy_group_bindings",
                                       text=T("re4.batch_export_ui.copy_bindings"), icon='COPYDOWN')
                op_copy.character_id = character_id; op_copy.group_name = selected_group["name"]
                op_paste = row.operator("re4.paste_group_bindings",
                                        text=T("re4.batch_export_ui.paste_bindings"), icon='PASTEDOWN')
                op_paste.character_id = character_id; op_paste.group_name = selected_group["name"]

        if selected_group is not None:
            box = col2.box()
            if use_simplified:
                self._draw_group_detail_simplified(box, scene, character_id, selected_group)
            else:
                self._draw_group_detail_normal(box, scene, character_id, selected_group)

        pec.draw_summary_row(self, layout)

    def _draw_group_detail_simplified(self, layout, scene, character_id, group):
        group_name = group["name"]
        user_entries  = [e for e in group["entries"] if e.get("simplified") == "user"]
        empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
        skip_count  = sum(1 for e in group["entries"] if e.get("simplified") == "skip")

        layout.label(text=group_name, icon='FILE_FOLDER')

        if not user_entries:
            info = []
            if empty_count: info.append(f"{empty_count} empty")
            if skip_count:  info.append(f"{skip_count} skip")
            layout.label(text=f"({', '.join(info)})" if info else "—")
            return

        has_mesh  = any(e.get("mesh")  for e in user_entries)
        has_mdf2  = any(e.get("mdf2")  for e in user_entries)
        has_chain = any(e.get("chain") for e in user_entries)

        # Label above the picker, not beside it: this box is only 35% of the
        # dialog's width, and a collection name long enough to fill a sibling
        # row's leftover space gets silently ellipsis-clipped by the button
        # widget -- measured against a real "ch03_..._RE4.mdf2 hair"-style
        # name (core/pre_export_check_ops.py's own detail text had the same
        # problem for a different reason: see _wrap_line there).
        if has_mesh:
            layout.label(text="MESH:", icon='OUTLINER_OB_MESH')
            row = layout.row(align=True)
            cur = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
            op = row.operator("re4.pick_binding", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.scope = "GROUP"; op.slot = "mesh"
            op.character_id = character_id; op.group_name = group_name
            if cur:
                op_c = row.operator("re4.clear_sg", text="", icon='X')
                op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mesh"

        if has_mdf2:
            layout.label(text="MDF2:", icon='MATERIAL')
            row = layout.row(align=True)
            cur = _get_simplified_group_binding(scene, character_id, group_name, "mdf2")
            op = row.operator("re4.pick_binding", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.scope = "GROUP"; op.slot = "mdf2"
            op.character_id = character_id; op.group_name = group_name
            if cur:
                op_c = row.operator("re4.clear_sg", text="", icon='X')
                op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "mdf2"

        if has_chain:
            layout.label(text="Chain:", icon='CONSTRAINT_BONE')
            row = layout.row(align=True)
            cur = _get_simplified_group_binding(scene, character_id, group_name, "chain")
            op = row.operator("re4.pick_binding", text=cur if cur else "Select...", icon='DOWNARROW_HLT')
            op.scope = "GROUP"; op.slot = "chain"
            op.character_id = character_id; op.group_name = group_name
            if cur:
                op_c = row.operator("re4.clear_sg", text="", icon='X')
                op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = "chain"

        info = [f"{len(user_entries)} user"]
        if empty_count: info.append(f"{empty_count} empty")
        if skip_count:  info.append(f"{skip_count} skip")
        layout.separator()
        layout.label(text=f"Entries: {', '.join(info)}")

    def _draw_group_detail_normal(self, layout, scene, character_id, group):
        layout.label(text=group["name"], icon='FILE_FOLDER')
        for entry in group["entries"]:
            entry_id = entry["id"]
            header = entry_id
            note = entry.get("note", "")
            if note: header += f"  [{note}]"
            entry_box = layout.box()
            entry_box.label(text=header)

            # Checkbox+label on their own row, picker+clear on the next: this
            # box is only 35% of the dialog's width, and a long collection
            # name sharing a row with them gets silently ellipsis-clipped.
            if entry.get("mesh"):
                head = entry_box.row(align=True)
                en = _get_enabled(scene, character_id, entry_id, "mesh")
                op = head.operator("re4.toggle_entry", text="",
                                   icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mesh"
                cur = _get_binding(scene, character_id, entry_id, "mesh")
                ic = 'OUTLINER_OB_MESH'
                if cur and cur in bpy.data.collections:
                    ct = bpy.data.collections[cur].color_tag
                    if ct != "NONE": ic = f"COLLECTION_{ct}"
                head.label(text="MESH", icon=ic)
                row = entry_box.row(align=True)
                op_p = row.operator("re4.pick_binding",
                                    text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op_p.scope = "ENTRY"; op_p.slot = "mesh"
                op_p.character_id = character_id; op_p.entry_id = entry_id

            if entry.get("mdf2"):
                head = entry_box.row(align=True)
                en = _get_enabled(scene, character_id, entry_id, "mdf2")
                op = head.operator("re4.toggle_entry", text="",
                                   icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                op.character_id = character_id; op.entry_id = entry_id; op.suffix = "mdf2"
                cur = _get_binding(scene, character_id, entry_id, "mdf2")
                ic = 'MATERIAL'
                if cur and cur in bpy.data.collections:
                    ct = bpy.data.collections[cur].color_tag
                    if ct != "NONE": ic = f"COLLECTION_{ct}"
                head.label(text=f"MDF2 x{len(entry['mdf2'])}", icon=ic)
                row = entry_box.row(align=True)
                op_p = row.operator("re4.pick_binding",
                                    text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op_p.scope = "ENTRY"; op_p.slot = "mdf2"
                op_p.character_id = character_id; op_p.entry_id = entry_id

            if entry.get("chain"):
                head = entry_box.row(align=True)
                en = _get_enabled(scene, character_id, entry_id, "chain")
                op = head.operator("re4.toggle_entry", text="",
                                   icon='CHECKBOX_HLT' if en else 'CHECKBOX_DEHLT', emboss=False)
                op.character_id = character_id; op.entry_id = entry_id; op.suffix = "chain"
                cur = _get_binding(scene, character_id, entry_id, "chain")
                ic = 'CONSTRAINT_BONE'
                if cur and cur in bpy.data.collections:
                    ct = bpy.data.collections[cur].color_tag
                    if ct != "NONE": ic = f"COLLECTION_{ct}"
                head.label(text="Chain", icon=ic)
                row = entry_box.row(align=True)
                op_p = row.operator("re4.pick_binding",
                                    text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op_p.scope = "ENTRY"; op_p.slot = "chain"
                op_p.character_id = character_id; op_p.entry_id = entry_id

    def execute(self, context):
        bpy.ops.re4.batch_export()
        return {'FINISHED'}


classes = [
    RE4_GroupListItem,
    RE4_UL_Groups,
    RE4_OT_PickBinding,
    RE4_OT_ToggleEntry,
    RE4_OT_ToggleSimplified,
    RE4_OT_PickArmature,
    RE4_OT_ClearSimplifiedGroup,
    RE4_OT_ClearSimplifiedEmpty,
    RE4_OT_CopyGroupBindings,
    RE4_OT_PasteGroupBindings,
    RE4_OT_BatchExportDialog,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
