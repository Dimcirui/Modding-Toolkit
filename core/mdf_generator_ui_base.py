"""The generator dialog, shared by the five games: settings on top, a material
list that scrolls on its own, and the selected material's detail below.

Same shape as the processor's dialog (core/mdf_tex_processor_ui_base.py), and
for the same reason: a props dialog cannot scroll, so drawing every material
expanded ran off the screen at a dozen materials.
"""

import os

import bpy

from .i18n import T
from .mdf_generator_base import (
    preset_has_emissive_slots, preset_has_albedo_blend_map, preview_plan,
)
from .mdf_tex_processor_base import PBR_TYPE_LABELS
from .slot_defaults import SlotNulls

GENERATOR_WINDOW_WIDTH = 600
_LIST_ROWS = 6

_PBR_ORDER = ('color', 'normal', 'roughness', 'metallic', 'alpha', 'emissive')
_STRAT_LABEL_KEYS = {
    'color':     "core.mdf_generator_base.strat_color",
    'normal':    "core.mdf_generator_base.strat_normal",
    'roughness': "core.mdf_generator_base.strat_roughness",
    'metallic':  "core.mdf_generator_base.strat_metallic",
    'alpha':     "core.mdf_generator_base.strat_alpha",
    'emissive':  "core.mdf_generator_base.strat_emissive",
}
_STRAT_ICONS = {'Direct': 'IMAGE_DATA', 'Solid': 'MESH_PLANE', 'Bake': 'RENDER_STILL'}

#: SlotPlan kind -> (label key, icon), in the order the summary lists them.
_PLAN_KINDS = {
    'COMPOSE':     ("core.gen_slot_plan.compose",     'NODE_COMPOSITING'),
    'SOLID':       ("core.gen_slot_plan.solid",       'MESH_PLANE'),
    'DIRECT':      ("core.gen_slot_plan.direct",      'IMAGE_DATA'),
    'TOON':        ("core.gen_slot_plan.toon",        'SHADING_TEXTURE'),
    'PLACEHOLDER': ("core.gen_slot_plan.placeholder", 'FILE_IMAGE'),
    'NULL':        ("core.gen_slot_plan.null",        'LINKED'),
    'KEEP':        ("core.gen_slot_plan.keep",        'RADIOBUT_OFF'),
    'PATH':        ("core.gen_slot_plan.path",        'FILE_TEXT'),
}


def _tail(path):
    return (path or "").replace("\\", "/").rstrip("/").split("/")[-1]


def _no_preset(entry):
    if getattr(entry, 'preset_locked', False):
        return False
    return not entry.material_preset or entry.material_preset == 'NONE'


def _bakes(entry):
    return [pt for pt in _PBR_ORDER if getattr(entry, f"strat_{pt}", "") == 'Bake']


def _prop_with_hint(layout, data, prop, label, hint):
    """A text field whose hint shows inside it while it is empty -- the
    ``placeholder`` argument, Blender 4.1+. Older versions get the hint as a
    label after the field, which still costs no extra row."""
    try:
        layout.prop(data, prop, text="" if hint else label, placeholder=hint)
    except TypeError:
        layout.prop(data, prop, text=label)
        if hint and not getattr(data, prop).strip():
            layout.label(text=hint)


class MDFGEN_UL_materials(bpy.types.UIList):
    """Material list for the generator dialog: what each material will be made
    from, and anything that will stop it -- visible without opening it."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        bakes = _bakes(item)
        problem = _no_preset(item) or (bakes and item.mesh_count == 0)
        row = layout.row(align=True)
        split = row.split(factor=0.42, align=True)
        split.label(text=item.blender_material,
                    icon='ERROR' if problem else 'MATERIAL')
        right = split.row(align=True)
        if _no_preset(item):
            right.label(text=T("core.mdf_generator_ui_base.no_preset"))
            return
        if getattr(item, 'preset_locked', False):
            name, picon = os.path.splitext(_tail(item.preset_path_override))[0], 'LOCKED'
        else:
            try:
                name = bpy.types.UILayout.enum_item_name(item, "material_preset", item.material_preset)
            except Exception:
                name = os.path.splitext(_tail(item.material_preset))[0]
            picon = 'NONE'
        right.label(text=name, icon=picon)
        tags = []
        if getattr(item, 'uses_packed_shader', False) and item.shader_source == 'SLOT':
            tags.append(T("core.mdf_generator_ui_base.tag_slots"))
        n_direct = sum(1 for pt in _PBR_ORDER if getattr(item, f"strat_{pt}", "") == 'Direct')
        if n_direct:
            tags.append(T("core.mdf_generator_ui_base.tag_direct").format(n=n_direct))
        if bakes:
            tags.append(T("core.mdf_generator_ui_base.tag_bake").format(n=len(bakes)))
        if item.use_toon:
            tags.append(T("core.mdf_generator_ui_base.tag_toon"))
        if item.skip_textures:
            tags.append(T("core.mdf_generator_ui_base.tag_path_only"))
        right.label(text=" · ".join(tags))


class MdfGenDialogBase(bpy.types.Operator):
    bl_label   = "MDF2 Generator"
    bl_options = {'REGISTER'}

    # ── Game-specific class variables (override in subclasses) ─────────────────
    _game_prefix       = ""                  # operators are <prefix>.mdf_gen_refresh etc.
    _settings_attr     = ""
    _natives_root_key  = ""
    _op_stem           = "mdf_gen"
    _collection_label  = "Mesh Collection"
    _out_kind          = "MDF"               # "MRL3" for MHWI
    _out_name_attr     = "mdf_collection_name"
    _src_ext, _out_ext = ".mesh", ".mdf2"
    _path_prefix_label = "natives/STM/"
    _path_hint         = ""                  # literal hint; _path_hint_key wins when set
    _path_hint_key     = ""
    _desc_key          = ""
    _preset_dir_missing_key = ""
    _empty_hint_key    = ""
    _is_mrl3           = False
    _process_cls       = None                # the game's MdfGenProcessBase subclass

    @classmethod
    def description(cls, context, properties):
        return T(cls._desc_key) if cls._desc_key else ""

    def _preset_dir(self):
        raise NotImplementedError

    def _plan_tables(self):
        """kwargs for preview_plan: the tables the game's export loop uses."""
        p = type(self)._process_cls
        nulls = p._slot_nulls or SlotNulls(p._null_tex_by_type)
        return dict(channel_maps=p._channel_maps,
                    null_for=lambda st, mmtr, cur: nulls.null_for(st, mmtr, cur),
                    nulls=nulls, placeholder_slots=p._placeholder_slots,
                    default_null=True)

    def _draw_extra(self, box, entry):
        """Game-only options under the shared ones (MHWI's snow overlay)."""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def _op(self, name):
        return getattr(getattr(bpy.ops, type(self)._game_prefix), f"{type(self)._op_stem}_{name}")

    def invoke(self, context, event):
        settings = getattr(context.scene, type(self)._settings_attr)
        # Always refresh on open, not just when the list is empty -- a list
        # left over from before some out-of-band change (converting a
        # material to a different packed-shader spec/preset, editing the
        # collection elsewhere) would otherwise keep showing stale data until
        # the user remembers to click the refresh button themselves.
        if settings.mesh_collection:
            self._op("refresh")()
        return context.window_manager.invoke_props_dialog(
            self, width=GENERATOR_WINDOW_WIDTH)

    def execute(self, context):
        self._op("process")()
        return {'FINISHED'}

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        cls      = type(self)
        pfx      = cls._game_prefix
        settings = getattr(scene, cls._settings_attr)

        row = layout.row(align=True)
        row.prop(settings, "mesh_collection", text=cls._collection_label)
        row.operator(f"{pfx}.{cls._op_stem}_refresh", text="", icon='FILE_REFRESH')
        row.operator(f"{pfx}.select_same_material", text="", icon='RESTRICT_SELECT_OFF')

        row = layout.row(align=True)
        split = row.split(factor=0.55, align=True)
        left = split.row(align=True)
        left.operator(f"{pfx}.set_natives_root", text="", icon='FILEBROWSER')
        natives_root = scene.get(cls._natives_root_key, "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            left.label(text=".../" + "/".join(parts[-3:]) if len(parts) > 3 else natives_root)
        else:
            left.label(text=T("core.mdf_tex_processor_ui_base.not_set"), icon='ERROR')
        auto = ""
        if settings.mesh_collection:
            mc = settings.mesh_collection.name
            auto = mc.replace(cls._src_ext, cls._out_ext) if cls._src_ext in mc else mc + cls._out_ext
        _prop_with_hint(split.row(align=True), settings, cls._out_name_attr, cls._out_kind,
                        T("core.mdf_generator_base.auto").format(name=auto) if auto else "")

        row = layout.row(align=True)
        row.label(text=cls._path_prefix_label)
        _prop_with_hint(row, settings, "texture_base_path", "",
                        T(cls._path_hint_key).strip() if cls._path_hint_key else cls._path_hint)

        self._draw_options(layout, settings)

        if not self._preset_dir():
            layout.label(text=T(cls._preset_dir_missing_key), icon='ERROR')

        if not settings.material_list:
            layout.separator()
            layout.label(text=T(cls._empty_hint_key), icon='INFO')
            return

        layout.template_list("MDFGEN_UL_materials", cls._settings_attr,
                             settings, "material_list", settings, "material_list_idx",
                             rows=_LIST_ROWS)
        idx = settings.material_list_idx
        if 0 <= idx < len(settings.material_list):
            self._draw_entry(layout, settings, settings.material_list[idx])

    def _draw_options(self, layout, settings):
        """The global switches, folded: they are set once per model, and the
        header still names every one that is not at its default."""
        on = []
        if settings.flip_normal_g:
            on.append("GL→DX")
        if getattr(settings, "octahedral_normals", False):
            on.append(T("core.mdf_generator_ui_base.opt_octahedral"))
        if settings.global_disable_mipmaps:
            on.append(T("core.mdf_generator_ui_base.opt_no_mip"))
        if settings.global_use_toon:
            on.append(T("core.mdf_generator_ui_base.opt_toon"))
        if settings.global_color_grade != 'NONE':
            try:
                on.append(bpy.types.UILayout.enum_item_name(
                    settings, "global_color_grade", settings.global_color_grade))
            except Exception:
                on.append(settings.global_color_grade)
        row = layout.row(align=True)
        row.prop(settings, "options_expanded", text="", emboss=False,
                 icon='TRIA_DOWN' if settings.options_expanded else 'TRIA_RIGHT')
        row.label(text=T("core.mdf_generator_ui_base.options") + "  —  " + (
            " · ".join(on) if on else T("core.mdf_generator_ui_base.opt_defaults")))
        if not settings.options_expanded:
            return
        box = layout.box()
        col = box.column(align=True)
        col.prop(settings, "flip_normal_g", text=T("core.mdf_generator_ui_base.flip_g"))
        if hasattr(settings, "octahedral_normals"):
            col.prop(settings, "octahedral_normals", text=T("core.octahedral_normals.label"))
        row = col.row(align=True)
        row.prop(settings, "global_disable_mipmaps",
                 text=T("core.mdf_generator_base.global_disable_mipmaps"))
        row.prop(settings, "global_use_toon",
                 text=T("core.mdf_generator_base.global_use_toon"))
        row = col.row(align=True)
        row.label(text=T("core.color_grade.label"))
        row.prop(settings, "global_color_grade", text="")

    def _draw_entry(self, layout, settings, entry):
        cls = type(self)
        box = layout.box()

        header = box.row(align=True)
        split = header.split(factor=0.45, align=True)
        split.label(text=entry.blender_material + (
            "  ·  " + T("core.mdf_generator_ui_base.meshes").format(n=entry.mesh_count)
            if entry.mesh_count else ""), icon='MATERIAL')
        right = split.row(align=True)
        if getattr(entry, 'preset_locked', False):
            # A bundled prefab: not one of material_preset's own items, and not
            # meant to be re-picked here -- see the "使用插件预制材质" checkbox in
            # Convert to Packed Shader.
            right.label(text=os.path.splitext(_tail(entry.preset_path_override))[0]
                        or entry.preset_path_override, icon='LOCKED')
        else:
            right.prop(entry, "material_preset", text="")
        op = right.operator("mhw.gen_copy_material", text="", icon='COPYDOWN')
        op.settings_attr, op.mat_name = cls._settings_attr, entry.blender_material
        paste = right.row(align=True)
        paste.enabled = bool(settings.clipboard_json)
        op = paste.operator("mhw.gen_paste_material", text="", icon='PASTEDOWN')
        op.settings_attr, op.mat_name = cls._settings_attr, entry.blender_material

        packed = getattr(entry, "uses_packed_shader", False)
        if packed:
            # A packed shader already carries the AO map and its strength, and
            # toon mode belongs to the emissive shaders it replaces -- so those
            # options are hidden and a choice of which panel to read appears.
            row = box.row(align=True)
            row.label(text=T("core.mdf_generator_ui_base.read"))
            # A plain prop(expand=True) on this *dynamic* items= enum renders
            # blank button text in Blender, so draw it as two toggle buttons.
            for value, key in (('PBR', "core.mdf_generator_base.shader_source_pbr"),
                               ('SLOT', "core.mdf_generator_base.shader_source_slot")):
                op = row.operator("mhw.set_shader_source", text=T(key),
                                  depress=(entry.shader_source == value))
                op.settings_attr, op.mat_name, op.value = \
                    cls._settings_attr, entry.blender_material, value

        self._draw_sources(box, entry)

        row = box.row(align=True)
        row.prop(entry, "generate_mipmaps", toggle=True,
                 text=T("core.mdf_tex_processor_base.generate_mipmaps_label"))
        row.prop(entry, "skip_textures", toggle=True,
                 text=T("core.mdf_generator_ui_base.skip"))
        if not packed:
            if preset_has_emissive_slots(entry.material_preset, is_mrl3=cls._is_mrl3):
                row.prop(entry, "use_toon", toggle=True, text=T("core.mdf_generator_ui_base.toon"))
            row.prop(entry, "use_ao", toggle=True, text=T("ui.prop.use_ao"))
            if entry.use_ao:
                ao = box.row(align=True)
                ao.prop(entry, "ao_image", text="")
                ch_sub = ao.row(align=True)
                ch_sub.scale_x = 0.35
                for ch_val in ('R', 'G', 'B', 'A'):
                    ch_sub.prop_enum(entry, "ao_ch", ch_val)
                ao.prop(entry, "ao_inv", toggle=True,
                        text=T("core.mdf_tex_processor_base.prop_invert"))
                if hasattr(entry, "ao_strength"):
                    ao.prop(entry, "ao_strength", text=T("core.mdf_generator_ui_base.ao_strength"))
        self._draw_extra(box, entry)

        self._draw_plan(box, settings, entry)

    def _draw_sources(self, box, entry):
        """Where each PBR channel comes from, as the node analysis found it."""
        cls = type(self)
        grid = box.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for pt in _PBR_ORDER:
            strat = getattr(entry, f"strat_{pt}", "?")
            src   = getattr(entry, f"src_{pt}", "")
            cell = grid.row(align=True)
            sub = cell.split(factor=0.38, align=True)
            sub.label(text=T(_STRAT_LABEL_KEYS[pt]))
            text = T("core.mdf_generator_ui_base.bake") if strat == 'Bake' else (src or strat)
            inner = sub.row(align=True)
            inner.label(text=text, icon=_STRAT_ICONS.get(strat, 'QUESTION'))
            native_size = getattr(entry, f"native_size_{pt}", 0)
            if strat != 'Solid' and native_size > 0:
                override = getattr(entry, f"bake_size_{pt}", 0)
                label = f"{override}" if override > 0 and override != native_size else ""
                op = inner.operator("mhw.set_channel_size", text=label,
                                    icon='FULLSCREEN_ENTER')
                op.settings_attr = cls._settings_attr
                op.mat_name      = entry.blender_material
                op.channel       = pt
                op.native_size   = native_size
        if _bakes(entry) and entry.mesh_count == 0:
            box.label(text=T("core.mdf_generator_ui_base.bake_no_mesh"), icon='ERROR')

    def _draw_plan(self, box, settings, entry):
        """What each slot of the preset will get -- from core/gen_slot_plan.py,
        the same plan the export loop dispatches on. Folded by default."""
        try:
            plan = preview_plan(entry, settings, is_mrl3=type(self)._is_mrl3,
                                **self._plan_tables())
        except Exception as err:          # a draw must never raise
            box.label(text=f"{T('core.mdf_generator_ui_base.slots')}: {err}", icon='ERROR')
            return
        if not plan:
            return
        counts = {}
        for _, p in plan:
            counts[p.kind] = counts.get(p.kind, 0) + 1
        summary = " · ".join(f"{T(_PLAN_KINDS[k][0])} {counts[k]}"
                             for k in _PLAN_KINDS if k in counts)
        row = box.row(align=True)
        row.prop(entry, "slots_expanded", text="", emboss=False,
                 icon='TRIA_DOWN' if entry.slots_expanded else 'TRIA_RIGHT')
        row.label(text=f"{T('core.mdf_generator_ui_base.slots')}  —  {summary}")
        if not entry.slots_expanded:
            return
        col = box.column(align=True)
        for st, p in plan:
            row = col.row(align=True)
            row.label(text="", icon='BLANK1')
            split = row.split(factor=0.42, align=True)
            split.label(text=st)
            key, icon = _PLAN_KINDS[p.kind]
            split.label(text=self._plan_text(p, key), icon=icon)

    @staticmethod
    def _plan_text(p, key):
        text = T(key)
        if p.kind in ('COMPOSE', 'SOLID') and p.sources:
            # [] not .get(): the labels translate live in __getitem__ only.
            text += " ← " + ", ".join(PBR_TYPE_LABELS[s] if s in PBR_TYPE_LABELS else s
                                      for s in p.sources)
        elif p.kind == 'DIRECT':
            text += " ← " + _tail(p.detail)
        elif p.kind == 'NULL':
            text += " → " + _tail(p.detail)
        return text
