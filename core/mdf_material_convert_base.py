"""
core/mdf_material_convert_base.py — convert selected MDF materials to a
different RE Mesh Editor preset material, migrating the user's own custom
texture bindings (and optionally shader params) onto the freshly-created
preset material.

Game-agnostic base; games/<game>/mdf_material_convert.py supplies the thin
per-game subclass (target preset directory name, bundled vanilla-path asset).
"""

import os
import bpy
from bpy.props import BoolProperty, EnumProperty

from .i18n import T
from .mdf_tex_processor_base import mdf_collection_poll
from .mdf_generator_base import load_preset_enum_items, import_read_preset_json


# ── Vanilla Art/ path lookup ────────────────────────────────────────────────
# Ground truth is a bundled, preprocessed list (see scripts/build_vanilla_tex_paths.py)
# maintained by the addon author and shipped with the addon -- not user-configurable,
# not re-scanned at runtime. See project_mdf_material_conversion_feature memory for why.

_vanilla_path_cache = {}


def _load_vanilla_art_paths(asset_rel_path):
    """Lazy-loaded, cached frozenset of normalized vanilla Art/*.tex paths."""
    if not asset_rel_path:
        return frozenset()
    if asset_rel_path in _vanilla_path_cache:
        return _vanilla_path_cache[asset_rel_path]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_path = os.path.join(root, *asset_rel_path.split('/'))
    paths = frozenset()
    try:
        with open(abs_path, encoding='utf-8') as f:
            paths = frozenset(line.strip() for line in f if line.strip())
    except OSError as e:
        print(f"[MDF Convert] Failed to load vanilla path list '{abs_path}': {e}")
    _vanilla_path_cache[asset_rel_path] = paths
    return paths


def is_custom_tex_path(path, vanilla_set):
    """True if *path* looks like the user's own asset rather than a vanilla
    one. Not restricted to Art/ -- some modders use their own top-level
    namespace entirely (e.g. "MK_MODS/Eku/Public/atos.tex", confirmed absent
    from the vanilla list), and vanilla assets aren't all under Art/ either
    (systems/, MasterMaterial/, RE_ENGINE_LIBRARY/, GUI/, GameDesign/, etc. --
    see scripts/build_vanilla_tex_paths.py's docstring). So there is no
    reliable prefix to gate on either way; exact-match against the full
    vanilla list is the only thing that holds up. Bindings stored in MDF
    materials never carry the natives/STM/ prefix or a version suffix (see
    make_mdf_path() in mdf_tex_processor_base.py), so only case/slash
    normalization is needed here -- the prefix/suffix stripping already
    happened when the bundled asset was built."""
    if not path:
        return False
    norm = path.replace('\\', '/').lower()
    return norm not in vanilla_set


# ── Texture slot type fallback ──────────────────────────────────────────────
# Some presets use BaseAlphaMap instead of BaseDielectricMap for the albedo
# slot -- same RGB semantics (see BASE_SLOT_CHANNEL_MAPS in
# mdf_tex_processor_base.py), they only differ in what the A channel carries
# (metallic vs. alpha). When the target preset has no exact slot-type match,
# try this fallback before giving up on the binding entirely.
_TEX_TYPE_FALLBACK = {
    'BaseDielectricMap': 'BaseAlphaMap',
}


# ── Param value migration ───────────────────────────────────────────────────

_PROP_VALUE_FIELDS = {
    'VEC4':  'float_vector_value',
    'COLOR': 'color_value',
    'BOOL':  'bool_value',
}


def migrate_property_value(dst_item, src_item):
    """Copy src_item's value onto dst_item, dispatching on dst's own
    data_type. Returns False (no-op) when src's data_type disagrees --
    reading the field dst's type implies off a source that never populated
    it would silently copy whatever that field happens to default to,
    rather than the source's real value."""
    if dst_item.data_type != src_item.data_type:
        return False
    field = _PROP_VALUE_FIELDS.get(dst_item.data_type, 'float_value')
    setattr(dst_item, field, getattr(src_item, field))
    return True


# ── Dialog operator base ────────────────────────────────────────────────────

_migrate_mode_items_cache = []


def _migrate_mode_items(self, context):
    global _migrate_mode_items_cache
    _migrate_mode_items_cache = [
        ('CUSTOM_TEX', T("core.mdf_material_convert_base.mode_custom_tex"),
                       T("core.mdf_material_convert_base.mode_custom_tex_desc")),
        ('ALL_TEX', T("core.mdf_material_convert_base.mode_all_tex"),
                    T("core.mdf_material_convert_base.mode_all_tex_desc")),
        ('ALL_TEX_PARAMS', T("core.mdf_material_convert_base.mode_all_tex_params"),
                           T("core.mdf_material_convert_base.mode_all_tex_params_desc")),
    ]
    return _migrate_mode_items_cache


class MdfConvertMaterialDialogBase(bpy.types.Operator):
    """Convert selected MDF materials to a different preset material.

    Subclasses must additionally declare their own ``preset_choice``
    EnumProperty (with their own items= callback hardcoded to their game's
    RE Mesh Editor preset directory, e.g. games/mhws/mdf_material_convert.py).
    It cannot live here: Blender calls a dynamic items= callback with a
    lightweight properties-only ``self`` that reliably supports reading other
    *registered* bpy.props off it, but not plain Python class attributes such
    as a would-be ``_preset_dir_game`` -- ``type(self)`` in that context is
    not the leaf subclass. core/shader_ops.py's own preset-choice callback
    hardcodes its game the same way, for the same reason.
    """
    bl_label   = "Convert MDF Material"
    bl_options = {'REGISTER', 'UNDO'}

    #: Overridden per game -- relative path (from the addon root) to the
    #: bundled vanilla-path asset consumed by is_custom_tex_path(). Only read
    #: from execute()/poll(), where self is reliably the real subclass instance.
    _vanilla_asset_rel = ""
    _log_tag = "MDF Convert"

    migrate_mode: EnumProperty(
        name="Migrate Mode",
        items=_migrate_mode_items,
        default=0,  # 'CUSTOM_TEX' -- dynamic items require an int index default
    )

    delete_original: BoolProperty(name="Delete Original Material", default=True)

    @classmethod
    def poll(cls, context):
        return any(o.get("~TYPE") == "RE_MDF_MATERIAL" for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "migrate_mode", expand=True)
        col.prop(self, "preset_choice", text=T("core.mdf_material_convert_base.preset_choice_label"))
        col.prop(self, "delete_original", text=T("core.mdf_material_convert_base.delete_original_label"))

    def execute(self, context):
        cls = type(self)
        vanilla_set = _load_vanilla_art_paths(cls._vanilla_asset_rel)

        preset_path = self.preset_choice
        if not preset_path or preset_path == 'NONE':
            self.report({'ERROR'}, T("core.mdf_material_convert_base.no_preset_selected"))
            return {'CANCELLED'}

        targets = [o for o in list(context.selected_objects)
                   if o.get("~TYPE") == "RE_MDF_MATERIAL" and getattr(o, 're_mdf_material', None)]
        if not targets:
            self.report({'WARNING'}, T("core.mdf_material_convert_base.no_targets"))
            return {'CANCELLED'}

        readPresetJSON = import_read_preset_json()
        if readPresetJSON is None:
            self.report({'ERROR'}, T("core.mdf_material_convert_base.cannot_load_preset_tool"))
            return {'CANCELLED'}

        migrate_params = (self.migrate_mode == 'ALL_TEX_PARAMS')
        migrate_all_tex = (self.migrate_mode != 'CUSTOM_TEX')

        converted = failed = 0
        tex_migrated = tex_skipped_vanilla = tex_skipped_no_slot = 0
        params_migrated = params_skipped = 0

        for obj in targets:
            try:
                old_data = obj.re_mdf_material
                old_name = old_data.materialName
                old_bindings = {b.textureType: b.path for b in old_data.textureBindingList_items}
                old_props = ([(p.prop_name, p) for p in old_data.propertyList_items]
                             if migrate_params else [])

                mdf_col = next((c for c in obj.users_collection if mdf_collection_poll(None, c)), None)
                if mdf_col is None:
                    print(f"[{cls._log_tag}] {old_name}: no parent .mdf2 collection found, skipped")
                    failed += 1
                    continue

                new_obj = readPresetJSON(preset_path, mdf_col)
                # RE Mesh Editor's readPresetJSON returns False (not None) on a
                # read/parse failure -- `not new_obj` catches both.
                if not new_obj:
                    print(f"[{cls._log_tag}] {old_name}: readPresetJSON failed for '{preset_path}'")
                    failed += 1
                    continue

                new_data = new_obj.re_mdf_material
                new_data.materialName = old_name

                new_bindings_by_type = {b.textureType: b for b in new_data.textureBindingList_items}
                for tex_type, old_path in old_bindings.items():
                    if not migrate_all_tex:
                        if not is_custom_tex_path(old_path, vanilla_set):
                            if old_path:
                                tex_skipped_vanilla += 1
                            continue
                    dst = new_bindings_by_type.get(tex_type)
                    if dst is None:
                        fallback_type = _TEX_TYPE_FALLBACK.get(tex_type)
                        if fallback_type:
                            dst = new_bindings_by_type.get(fallback_type)
                    if dst is None:
                        tex_skipped_no_slot += 1
                        continue
                    dst.path = old_path
                    tex_migrated += 1

                if migrate_params:
                    new_props_by_name = {p.prop_name: p for p in new_data.propertyList_items}
                    for prop_name, src_item in old_props:
                        dst_item = new_props_by_name.get(prop_name)
                        if dst_item is not None and migrate_property_value(dst_item, src_item):
                            params_migrated += 1
                        else:
                            params_skipped += 1

                if self.delete_original:
                    bpy.data.objects.remove(obj, do_unlink=True)

                converted += 1

            except Exception as e:
                failed += 1
                print(f"[{cls._log_tag}] convert failed for '{obj.name}': {e}")
                import traceback
                traceback.print_exc()

        if failed:
            self.report({'WARNING'}, T("core.mdf_material_convert_base.done_with_fail").format(
                done=converted, failed=failed))
        elif migrate_params:
            self.report({'INFO'}, T("core.mdf_material_convert_base.done_with_params").format(
                done=converted, tex=tex_migrated, vskip=tex_skipped_vanilla, noslot=tex_skipped_no_slot,
                pmig=params_migrated, pskip=params_skipped))
        else:
            self.report({'INFO'}, T("core.mdf_material_convert_base.done").format(
                done=converted, tex=tex_migrated, vskip=tex_skipped_vanilla, noslot=tex_skipped_no_slot))
        return {'FINISHED'}
