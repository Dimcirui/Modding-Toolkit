import bpy
from .batch_export import (
    MHWS_PARTS,
    _load_scheme, _canonical_order_file_types,
    _PART_LABEL_KEYS,
    get_binding, set_binding, bound_pairs, physics_context,
    get_mhws_armor_callback, part_slots, vanilla_slots, ignore_slot_limits,
)
from ...core.i18n import T
from ...core import pre_export_check_ops as pec
from ...core import export_autofix
from ...core import shapekey_export
from ...core import mod_root
from ...core import optional_editors

EXPORTER_WINDOW_WIDTH = 580
#: Added per column beyond the five (mesh mdf2 chain2 clsp gpuc) the window was
#: sized for -- i.e. for the jcns column.
OPTIONAL_COLUMN_WIDTH = 110

_FILETYPE_ICONS = {
    "mesh":   'OUTLINER_OB_MESH',
    "mdf2":   'MATERIAL',
    "chain2": 'LINKED',
    "clsp":   'PHYSICS',
    "jcns":   'CONSTRAINT_BONE',
    "gpuc":   'MOD_CLOTH',
}

_FILETYPE_LABELS = {
    "mesh":   "MESH",
    "mdf2":   "MDF2",
    "chain2": "CHAIN2",
    "clsp":   "CLSP",
    "gpuc":   "GPUC",
    "jcns":   "JCNS",
}


def _get_filtered_collections(filetype):
    result = []
    type_map  = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION",
                 "chain2": "RE_CHAIN_COLLECTION", "clsp": "RE_CHAIN_COLLECTION",
                 **{ft: optional_editors.collection_type(ft) for ft in optional_editors.EDITORS}}
    sfx_map   = {"mesh": ".mesh", "mdf2": ".mdf2", "chain2": ".chain2", "clsp": ".clsp",
                 "jcns": ".jcns", "gpuc": ".gpuc"}
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


def _slot_table(context):
    """``(armor_set, active_parts, {part: slots}, columns)`` for the armor and
    variant picked in the dialog; the columns are the file types any part has."""
    settings = context.scene.mhw_suite_settings
    scheme_file = settings.mhws_armor_scheme
    scheme = _load_scheme(scheme_file) if scheme_file and scheme_file != 'NONE' else None
    armor_set = next((a for a in scheme.get("armor_sets", [])
                      if a["id"] == settings.mhws_selected_armor), None) if scheme else None
    parts_mask = armor_set.get("parts_mask", 0b11111) if armor_set else 0b11111
    active_parts = [(pid, pname) for pid, pname in MHWS_PARTS
                    if parts_mask & (1 << (int(pid) - 1))]
    unlocked = ignore_slot_limits(context.scene)
    per_part = {pid: part_slots(armor_set, settings.mhws_armor_variant, pid, unlocked)
                for pid, _name in active_parts}
    columns = _canonical_order_file_types(
        {optional_editors.slot_type(sl) for slots in per_part.values() for sl in slots})
    return armor_set, active_parts, per_part, columns


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
        items=lambda self, ctx: _get_filtered_collections(optional_editors.slot_type(self.filetype))
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name and self.collection_name != "NONE":
            set_binding(context.scene, self.armor_id, self.variant, self.part, self.filetype, self.collection_name)
        return {'FINISHED'}


# ── Pick Armor ──────────────────────────────────────────────────

def _get_armor_label(context, armor_id):
    """根据当前装备包解析 armor_id 对应的显示名，找不到则回退为原始 id"""
    if not armor_id or armor_id == 'NONE':
        return None
    settings = context.scene.mhw_suite_settings
    for item_id, label, *_ in get_mhws_armor_callback(settings, context):
        if item_id == armor_id:
            return label
    return armor_id


class MHWS_OT_PickArmor(bpy.types.Operator):
    bl_idname = "mhws.pick_armor"
    bl_label = "Pick Armor"
    bl_options = {'INTERNAL'}
    bl_property = "armor_id"

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_export_ui.pick_armor_desc")

    armor_id: bpy.props.EnumProperty(
        name="Armor",
        items=lambda self, ctx: get_mhws_armor_callback(ctx.scene.mhw_suite_settings, ctx)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.armor_id and self.armor_id != 'NONE':
            context.scene.mhw_suite_settings.mhws_selected_armor = self.armor_id
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


def _gather_check_pairs(scene, armor_id, variant, active_parts):
    """``[(label, mdf_col, mesh_col), ...]`` for every active part that
    currently has an mdf2 binding -- the pairs pre_export_check can actually
    check. A part with no mdf2 bound has nothing the exporter would write
    either, so it is silently left out rather than reported as "unchecked".
    """
    pairs = []
    for part_id, part_name in active_parts:
        mdf_name = get_binding(scene, armor_id, variant, part_id, "mdf2")
        mdf_col = bpy.data.collections.get(mdf_name) if mdf_name else None
        if mdf_col is None:
            continue
        mesh_name = get_binding(scene, armor_id, variant, part_id, "mesh")
        mesh_col = bpy.data.collections.get(mesh_name) if mesh_name else None
        pairs.append((T(_PART_LABEL_KEYS.get(part_id, part_name)), mdf_col, mesh_col))
    return pairs


# ── Main Dialog ────────────────────────────────────────────────

class MHWS_OT_BatchExportDialog(bpy.types.Operator):
    bl_idname = "mhws.batch_export_dialog"
    bl_label = "MHWs Batch Exporter"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.batch_export_ui.batch_export_dialog_desc")

    def invoke(self, context, event):
        _armor_set, _parts, _slots, columns = _slot_table(context)
        width = EXPORTER_WINDOW_WIDTH + OPTIONAL_COLUMN_WIDTH * max(0, len(columns) - 5)
        return context.window_manager.invoke_props_dialog(self, width=width)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

        # ── Selectors ──
        layout.prop(settings, "mhws_armor_scheme", text=T("core.export_prep.armor_pack"))
        row = layout.row(align=True)
        row.prop(settings, "mhws_armor_variant", text="")
        cur_armor_label = _get_armor_label(context, settings.mhws_selected_armor)
        row.operator("mhws.pick_armor",
                     text=cur_armor_label if cur_armor_label else T("core.export_prep.pick_armor_placeholder"),
                     icon='DOWNARROW_HLT')

        # ── Natives Root ──
        natives_root = mod_root.read(scene, "mhws_natives_root")
        row = layout.row(align=True)
        row.operator("mhws.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text=T("core.export_prep.not_set"), icon='ERROR')

        # ── Early out ──
        variant  = settings.mhws_armor_variant
        armor_id = settings.mhws_selected_armor
        if not armor_id or armor_id == 'NONE':
            layout.separator()
            layout.label(text=T("mhws.batch_export_ui.select_armor_to_configure"), icon='INFO')
            return

        armor_set, active_parts, per_part_slots, all_file_types = _slot_table(context)

        layout.separator()

        # ── Header row ──
        header = layout.row(align=False)
        header.label(text="")  # part name column placeholder
        for ft in all_file_types:
            header.label(text=_FILETYPE_LABELS.get(ft, ft.upper()), icon=_FILETYPE_ICONS.get(ft, 'DOT'))

        # ── Part rows ──
        for part_id, part_name in active_parts:
            row = layout.row(align=False)
            row.label(text=f"{part_id}  {T(_PART_LABEL_KEYS.get(part_id, part_name))}")
            part_slots_ = per_part_slots[part_id]
            vanilla = vanilla_slots(armor_set, variant, part_id)
            for ft in all_file_types:
                slots = [sl for sl in part_slots_ if optional_editors.slot_type(sl) == ft]
                if not slots:
                    # This file type does not apply to this part
                    row.row(align=True).label(text="")
                    continue
                # A part can ship several jcns: one picker each, stacked in the cell.
                cell = row.column(align=True) if len(slots) > 1 else row
                for slot in slots:
                    self._draw_slot(cell.row(align=True), scene, armor_id, variant, part_id,
                                    slot, slot in vanilla)

        layout.separator()
        row = layout.row(align=True)
        row.prop(settings, "mhws_use_blank_export", text=T("ui.prop.use_blank_export"), icon='FILE_BLANK')
        row.prop(settings, "mhws_ignore_slot_limits", text=T("ui.prop.ignore_slot_limits"),
                 icon='UNLOCKED')
        export_autofix.draw_toggle(row, settings, 'MHWS')
        shapekey_export.draw(layout, scene, 'MHWS',
                             [m for _p, _d, m in bound_pairs(scene, armor_id, variant) if m is not None], natives_root)

        self._draw_body_reshape(layout, settings, scene, armor_id, variant)

        pairs = _gather_check_pairs(scene, armor_id, variant, active_parts)
        hints = {}
        vdata = (armor_set or {}).get("variants", {}).get(variant) or {}
        base = vdata.get("base_path", "").replace("\\", "/")
        if base.lower().startswith("natives/stm/art/"):
            hints['tex_base_hint'] = base[len("natives/STM/Art/"):]
        pec.draw_inline_summary(self, layout, context, 'MHWS', pairs, natives_root,
                                autofix_pairs=bound_pairs(scene, armor_id, variant),
                                hints=hints,
                                physics=physics_context(scene, armor_id, variant, armor_set))

    @staticmethod
    def _draw_slot(sub, scene, armor_id, variant, part_id, slot, vanilla):
        ft = optional_editors.slot_type(slot)
        if ft == "gpuc" and not optional_editors.available("gpuc"):
            # gpuc is always blank-copied, no collection binding
            sub.label(text="AUTO", icon='FILE_BLANK')
            return
        cur = get_binding(scene, armor_id, variant, part_id, slot)
        # An unbound vanilla gpuc is still blank-copied, as without the editor.
        unbound = "AUTO" if ft == "gpuc" and vanilla else "—"
        suffix = optional_editors.slot_suffix(slot)
        text = cur if cur else unbound
        if suffix:
            text = f"{suffix}  {text}"
        op = sub.operator(
            "mhws.pick_collection",
            text=text,
            icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft]
        )
        op.armor_id = armor_id
        op.variant  = variant
        op.part     = part_id
        op.filetype = slot
        if cur:
            op_c = sub.operator("mhws.clear_binding", text="", icon='X')
            op_c.armor_id = armor_id
            op_c.variant  = variant
            op_c.part     = part_id
            op_c.filetype = slot

    def _draw_body_reshape(self, layout, settings, scene, armor_id, variant):
        """Bonesystem and the Wilds lua bone system side by side: they are two
        alternative ways to reshape the body, at most one on (the props' update
        callbacks switch the other off), so one box shows the choice and then
        the settings of whichever is on."""
        layout.separator()
        box = layout.box()
        row = box.row(align=True)
        row.prop(settings, "mhws_use_bonesystem",
                 text=T("mhws.batch_export_ui.use_bonesystem_label"), icon='ARMATURE_DATA')
        row.prop(settings, "mhws_use_lua_bone_system",
                 text=T("mhws.batch_export_ui.use_lua_bone_system_label"), icon='ARMATURE_DATA')
        if settings.mhws_use_bonesystem:
            self._draw_bonesystem(box, settings)
        elif settings.mhws_use_lua_bone_system:
            self._draw_lua_bone_system(box, settings, scene, armor_id, variant)

    def _draw_bonesystem(self, box, settings):
        col = box.column(align=False)
        col.prop(settings, "mhws_bs_armature", text=T("mhws.batch_export_ui.armature_label"))
        name_row = col.row(align=True)
        name_row.prop(settings, "mhws_fbxskel_name", text=T("mhws.batch_export_ui.fbxskel_name_label"))
        name_row.operator("mhws.bonesystem_settings", text="", icon='PREFERENCES')

    def _draw_lua_bone_system(self, box, settings, scene, armor_id, variant):
        box.prop(settings, "mhws_bs_armature", text=T("mhws.batch_export_ui.armature_label"))

        head_row = box.row(align=False)
        head_row.label(text=T("mhws.batch_export_ui.lua_bone_head_label"))
        for ft in ("mesh", "mdf2"):
            sub = head_row.row(align=True)
            cur = get_binding(scene, armor_id, variant, "head", ft)
            op = sub.operator(
                "mhws.pick_collection",
                text=cur if cur else "—",
                icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft]
            )
            op.armor_id = armor_id
            op.variant  = variant
            op.part     = "head"
            op.filetype = ft
            if cur:
                op_c = sub.operator("mhws.clear_binding", text="", icon='X')
                op_c.armor_id = armor_id
                op_c.variant  = variant
                op_c.part     = "head"
                op_c.filetype = ft

    def execute(self, context):
        bpy.ops.mhws.batch_export()
        return {'FINISHED'}


classes = [
    MHWS_OT_PickCollection,
    MHWS_OT_PickArmor,
    MHWS_OT_ClearBinding,
    MHWS_OT_BatchExportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
