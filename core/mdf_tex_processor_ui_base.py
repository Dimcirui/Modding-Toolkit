import bpy
import os

from .i18n import T
from .mdf_tex_processor_base import (
    PBR_TYPES, PBR_TYPE_LABELS, PBR_CHANNEL_SELECTABLE, PBR_DEFAULTS,
    BASE_COMMON_SLOT_TYPES, BASE_NULL_TEX_BY_TYPE, BASE_SLOT_CHANNEL_MAPS,
    BASE_TEXTURE_TYPE_ABBREV, register_game_tables, slot_status, FEATURE_CHANNELS,
)
from .mdf_tex_slot_status import recipe_inputs
from .slot_defaults import SlotNulls

PROCESSOR_WINDOW_WIDTH = 660

# List + detail rather than every material expanded at once: a props dialog
# cannot scroll, so the old layout ran off the screen at a dozen materials. The
# list (a UIList) scrolls on its own; only the selected material is drawn below.
_LIST_ROWS = 6

_STATUS_ICON = {'COMPOSE': 'NODE_COMPOSITING', 'DIRECT': 'IMAGE_DATA',
                'DEFAULT': 'LINKED', 'SKIP': 'RADIOBUT_OFF'}
_CH_ORDER = ('R', 'G', 'B', 'A')


def _basename(path):
    return os.path.basename(bpy.path.abspath(path)) if path else ""


def _channel_groups(ch_map):
    """[(channels, source)] with consecutive channels that read the same input
    merged -- 'RGB' colour, 'G A' normal -- so a row is one quantity."""
    groups = []
    for c in _CH_ORDER:
        src = ch_map.get(c)
        if groups and isinstance(src, tuple) and groups[-1][1] == src[:1] + src[2:]:
            groups[-1][0].append(c)
            continue
        key = src[:1] + src[2:] if isinstance(src, tuple) else src
        groups.append(([c], key))
    return groups


class MdfTexDialogBase(bpy.types.Operator):
    """RE Engine MDF2 + Tex semi-auto texture processor"""
    bl_label   = "MDF2 + Tex Processor"
    bl_options = {'REGISTER'}

    # ── Game-specific class variables (override in subclasses) ─────────────────
    _game_prefix       = ""                    # e.g. "mhws" or "re9"
    _settings_attr     = ""                    # Scene attribute name
    _natives_root_key  = ""                    # Scene custom-property key
    _root_label        = "Mod Root"            # Label on the root picker button
    _path_prefix_label = "natives/STM/Art/"   # Label before the base-path field
    _path_hint         = "例：Author/Character/"
    _common_slot_types = BASE_COMMON_SLOT_TYPES
    _null_tex_by_type  = BASE_NULL_TEX_BY_TYPE
    # Must be the same tables the game's MdfTexProcessBase subclass uses, or
    # the badges would describe a different export than the one that runs.
    _channel_maps      = BASE_SLOT_CHANNEL_MAPS
    _abbrev_map        = BASE_TEXTURE_TYPE_ABBREV
    _slot_nulls        = None   # the game's SlotNulls -- same object its processor uses
    _feature_channels  = {}     # the game's mask slots with per-channel inputs

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def invoke(self, context, event):
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)
        col = settings.mdf_collection
        # Always refresh on open, not just when col matches what was loaded
        # last time -- _do_refresh already handles both "same collection
        # again" (preserves the in-memory config) and "switched collections"
        # (saves the old one's state, restores the new one's) safely, so
        # there is no correctness reason to skip it; skipping it just left a
        # stale materials list on screen until the user clicked refresh
        # themselves.
        if col:
            getattr(bpy.ops, cls._game_prefix).mdf_tex_refresh()
        return context.window_manager.invoke_props_dialog(
            self, width=PROCESSOR_WINDOW_WIDTH)

    def execute(self, context):
        getattr(getattr(bpy.ops, type(self)._game_prefix), 'mdf_tex_process')()
        return {'FINISHED'}

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        cls      = type(self)
        settings = getattr(scene, cls._settings_attr)
        pfx      = cls._game_prefix
        nulls    = cls._slot_nulls or SlotNulls(cls._null_tex_by_type)
        tables   = register_game_tables(settings, cls._channel_maps, nulls,
                                        cls._feature_channels)

        # Header
        row = layout.row(align=True)
        row.prop(settings, "mdf_collection", text="MDF Collection")
        row.operator(f"{pfx}.mdf_tex_refresh", text="", icon='FILE_REFRESH')

        row = layout.row(align=True)
        row.operator(f"{pfx}.set_natives_root",
                     text=cls._root_label, icon='FILEBROWSER')
        natives_root = scene.get(cls._natives_root_key, "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text=T("core.mdf_tex_processor_ui_base.not_set"), icon='ERROR')

        row = layout.row(align=True)
        row.label(text=cls._path_prefix_label)
        row.prop(settings, "texture_base_path", text="")

        # Global, not per-material: whether a slot's normal is octahedral is a
        # property of how the whole texture set was authored, not of one entry.
        if hasattr(settings, "octahedral_normals"):
            layout.prop(settings, "octahedral_normals",
                        text=T("core.octahedral_normals.label"))
        if not settings.texture_base_path.strip():
            hint = layout.row()
            hint.label(text=f"    {cls._path_hint}", icon='INFO')

        layout.prop(settings, "global_disable_mipmaps",
                    text=T("core.mdf_generator_base.global_disable_mipmaps"))
        grade_row = layout.row(align=True)
        grade_row.label(text=T("core.color_grade.label"))
        grade_row.prop(settings, "global_color_grade", text="")

        if not settings.materials:
            layout.separator()
            layout.label(text=T("core.mdf_tex_processor_ui_base.select_and_refresh"), icon='INFO')
            return

        layout.separator()
        layout.template_list("MDFTEX_UL_materials", cls._settings_attr,
                             settings, "materials", settings, "materials_index",
                             rows=_LIST_ROWS)

        mi = settings.materials_index
        if not 0 <= mi < len(settings.materials):
            return
        self._draw_material(layout, context, settings, settings.materials[mi], mi, tables)

    def _draw_material(self, layout, context, settings, mat, mi, tables):
        cls = type(self)
        pfx = cls._game_prefix
        box = layout.box()

        header = box.row(align=False)
        header.label(text=mat.material_name, icon='MATERIAL')
        op_copy = header.operator(f"{pfx}.mdf_tex_copy_material", text="", icon='COPYDOWN')
        op_copy.mat_index = mi
        paste_row = header.row(align=True)
        paste_row.enabled = bool(settings.clipboard_json)
        op_paste = paste_row.operator(f"{pfx}.mdf_tex_paste_material", text="", icon='PASTEDOWN')
        op_paste.mat_index = mi

        if mat.slots:
            opt_row = box.row(align=True)
            opt_row.prop(mat, "generate_mipmaps",
                         text=T("core.mdf_tex_processor_base.generate_mipmaps_label"))
            if mat.generate_mipmaps:
                opt_row.prop(mat, "mipmap_strategy", text="")
            opt_row.prop(mat, "skip_textures",
                         text=T("core.mdf_tex_processor_base.skip_textures_label"))

        self._draw_inputs(box, mat, mi)

        if not mat.slots:
            return
        pbr_paths = {pt: getattr(mat.pbr, pt) for pt in PBR_TYPES}
        mat_obj = settings.mdf_collection.objects.get(mat.material_obj_name) if settings.mdf_collection else None
        mat_data = getattr(mat_obj, 're_mdf_material', None)
        mmtr = getattr(mat_data, 'mmtrPath', '') if mat_data else ''
        common_slots = [(si, s) for si, s in enumerate(mat.slots)
                        if s.texture_type in cls._common_slot_types]
        other_slots  = [(si, s) for si, s in enumerate(mat.slots)
                        if s.texture_type not in cls._common_slot_types]

        if common_slots:
            box.label(text=T("core.mdf_tex_processor_ui_base.common_textures"), icon='RENDERLAYERS')
            self._draw_slots(box, mat, common_slots, mi, tables, pbr_paths, mmtr)

        if other_slots:
            other_header = box.row(align=False)
            other_icon = 'TRIA_DOWN' if mat.other_expanded else 'TRIA_RIGHT'
            other_header.prop(mat, "other_expanded", text="", icon=other_icon, emboss=False)
            other_header.label(text=T("core.mdf_tex_processor_ui_base.other_textures").format(
                n=len(other_slots)), icon='RENDERLAYERS')
            if mat.other_expanded:
                self._draw_slots(box, mat, other_slots, mi, tables, pbr_paths, mmtr)

    def _draw_inputs(self, box, mat, mi):
        """One row per input some slot of *this* material reads. The rest are
        named on one line instead of silently missing."""
        cls = type(self)
        pfx = cls._game_prefix
        read = set()
        for s in mat.slots:
            read |= recipe_inputs(s.texture_type, cls._channel_maps) or set()

        pbr_header = box.row(align=False)
        pbr_icon = 'TRIA_DOWN' if mat.pbr_expanded else 'TRIA_RIGHT'
        pbr_header.prop(mat, "pbr_expanded", text="", icon=pbr_icon, emboss=False)
        n_set = sum(1 for pt in PBR_TYPES if pt in read and getattr(mat.pbr, pt))
        pbr_header.label(text=T("core.mdf_tex_processor_ui_base.inputs").format(
            n=n_set, total=len(read)), icon='NODE_COMPOSITING')
        if not mat.pbr_expanded:
            return

        pbr_box = box.box()
        for pt in PBR_TYPES:
            if pt not in read:
                continue
            row = pbr_box.row(align=True)
            row.label(text=PBR_TYPE_LABELS[pt])
            cur = getattr(mat.pbr, pt)
            pick_op = row.operator(
                f"{pfx}.mdf_tex_pick_pbr",
                text=_basename(cur) if cur else "--",
                icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
            )
            pick_op.mat_index = mi
            pick_op.pbr_type  = pt
            if cur:
                clr_op = row.operator(f"{pfx}.mdf_tex_clear_pbr", text="", icon='X')
                clr_op.mat_index = mi
                clr_op.pbr_type  = pt
            if pt == 'normal' and cur:
                row.prop(mat.pbr, "normal_flip_g",
                         text="GL>DX", icon='LOOP_BACK', toggle=True)
            if pt in PBR_CHANNEL_SELECTABLE and cur:
                ch_sub = row.row(align=True)
                ch_sub.scale_x = 0.35
                for ch_val in _CH_ORDER:
                    ch_sub.prop_enum(mat.pbr, f"{pt}_ch", ch_val)
                inv_sub = row.row(align=True)
                inv_sub.scale_x = 0.4
                inv_sub.prop(mat.pbr, f"{pt}_inv", text="Inv", toggle=True)
        unread = [PBR_TYPE_LABELS[pt] for pt in PBR_TYPES if pt not in read]
        if unread:
            pbr_box.label(text=T("core.mdf_tex_processor_ui_base.inputs_unread").format(
                names=", ".join(unread)), icon='INFO')

    def _status_text(self, st, slot, nulls, mmtr):
        null_rel = nulls.null_for(slot.texture_type, mmtr, slot.original_path) or ""
        if st.mode == 'COMPOSE':
            fdef = type(self)._feature_channels.get(slot.texture_type, {})
            body = ", ".join(T(fdef[pt[3:]][1]) if pt.startswith("ch:") else PBR_TYPE_LABELS[pt]
                             for pt in st.sources)
            text = T("core.mdf_tex_slot_status.compose") + (f" ← {body}" if body else "")
        elif st.mode == 'DIRECT':
            text = T("core.mdf_tex_slot_status.direct") + f" ← {_basename(slot.direct_image) or '--'}"
        elif st.mode == 'DEFAULT':
            text = T("core.mdf_tex_slot_status.default") + f" → {null_rel.split('/')[-1]}"
        else:
            text = T("core.mdf_tex_slot_status.skip") + (
                f" · {slot.original_path.split('/')[-1]}" if slot.original_path else "")
        if st.problem:
            text += f"  ({T('core.mdf_tex_slot_status.' + st.problem)})"
        return text

    def _draw_slots(self, box, mat, indexed_slots, mi, tables, pbr_paths, mmtr=''):
        cls = type(self)
        pfx = cls._game_prefix
        col = box.column(align=True)
        for si, slot in indexed_slots:
            st = slot_status(tables, mat, slot, pbr_paths)
            ch_map = cls._channel_maps.get(slot.texture_type)
            fdef = cls._feature_channels.get(slot.texture_type)

            row = col.row(align=True)
            if ch_map is not None or fdef:
                row.prop(slot, "expanded", text="", emboss=False,
                         icon='TRIA_DOWN' if slot.expanded else 'TRIA_RIGHT')
            else:
                row.label(text="", icon='BLANK1')
            split = row.split(factor=0.40, align=True)
            abbrev = cls._abbrev_map.get(slot.texture_type)
            split.label(text=f"{abbrev}  ·  {slot.texture_type}" if abbrev else slot.texture_type)
            right = split.row(align=True)
            right.label(text=self._status_text(st, slot, tables[1], mmtr),
                        icon='ERROR' if st.problem else _STATUS_ICON[st.mode])
            mode_sub = right.row(align=True)
            mode_sub.scale_x = 0.8
            mode_sub.prop(slot, "mode", text="")
            pick_op = right.operator(f"{pfx}.mdf_tex_pick_direct", text="",
                                     icon='FILEBROWSER')
            pick_op.mat_index  = mi
            pick_op.slot_index = si
            if slot.direct_image:
                clr_op = right.operator(f"{pfx}.mdf_tex_clear_direct", text="", icon='X')
                clr_op.mat_index  = mi
                clr_op.slot_index = si

            if fdef and slot.expanded:
                self._draw_feature_channels(col, slot, fdef, mi, si)
            elif ch_map is not None and slot.expanded:
                self._draw_channels(col, mat, ch_map, pbr_paths)

    def _draw_channels(self, col, mat, ch_map, pbr_paths):
        """Where each channel of the slot comes from: an input (file + channel),
        that input's neutral value when it is not set, or a fixed constant."""
        for chans, src in _channel_groups(ch_map):
            row = col.row(align=True)
            row.label(text="", icon='BLANK1')
            split = row.split(factor=0.12, align=True)
            split.label(text=" ".join(chans) if len(chans) < 3 else "".join(chans))
            inner = split.split(factor=0.36, align=True)
            if not isinstance(src, tuple):
                inner.label(text="—")
                inner.label(text=T("core.mdf_tex_processor_ui_base.fixed").format(
                    v=f"{0.0 if src is None else src:g}"))
                continue
            pt, rule_inv = src[0], len(src) > 1 and src[1] is True
            inner.label(text=PBR_TYPE_LABELS[pt])
            path = pbr_paths.get(pt, "")
            if path and os.path.isfile(path):
                text = _basename(path)
                if pt in PBR_CHANNEL_SELECTABLE:
                    text += f" · {getattr(mat.pbr, pt + '_ch')}"
                    if getattr(mat.pbr, pt + '_inv'):
                        text += " · Inv"
                icon = 'IMAGE_DATA'
            else:
                neutral = PBR_DEFAULTS.get(pt, [1.0])
                v = neutral[0] if pt not in ('color', 'emissive', 'normal') else None
                text = (T("core.mdf_tex_processor_ui_base.neutral").format(v=f"{v:g}")
                        if v is not None else T("core.mdf_tex_processor_ui_base.no_input"))
                icon = 'DOT'
            if rule_inv:
                text += "  " + T("core.mdf_tex_processor_ui_base.inverted_rule")
            inner.label(text=text, icon=icon)

    def _draw_feature_channels(self, col, slot, fdef, mi, si):
        """A mask slot's own per-channel inputs. 'fixed' channels -- unknown or
        unused -- are shown, not offered: nothing should be fed into a channel
        whose meaning nobody has established."""
        pfx = type(self)._game_prefix
        for c in FEATURE_CHANNELS:
            kind, a, b = fdef.get(c, ('fixed', 0.0, ''))
            row = col.row(align=True)
            row.label(text="", icon='BLANK1')
            split = row.split(factor=0.12, align=True)
            split.label(text=c)
            inner = split.split(factor=0.36, align=True)
            if kind == 'fixed':
                inner.label(text=T(b) if b else "—")
                inner.label(text=T("core.mdf_tex_processor_ui_base.fixed").format(v=f"{a:g}"))
                continue
            inner.label(text=T(a))
            right = inner.row(align=True)
            prop = f"feat_{c.lower()}"
            cur = getattr(slot, prop)
            pick = right.operator(f"{pfx}.mdf_tex_pick_direct",
                                  text=_basename(cur) if cur else
                                  T("core.mdf_tex_processor_ui_base.neutral").format(v=f"{b:g}"),
                                  icon='IMAGE_DATA' if cur else 'FILEBROWSER')
            pick.mat_index, pick.slot_index, pick.channel = mi, si, c
            if cur:
                clr = right.operator(f"{pfx}.mdf_tex_clear_direct", text="", icon='X')
                clr.mat_index, clr.slot_index, clr.channel = mi, si, c
                ch_sub = right.row(align=True)
                ch_sub.scale_x = 0.35
                for ch_val in _CH_ORDER:
                    ch_sub.prop_enum(slot, f"{prop}_ch", ch_val)
                inv_sub = right.row(align=True)
                inv_sub.scale_x = 0.4
                inv_sub.prop(slot, f"{prop}_inv", text="Inv", toggle=True)
