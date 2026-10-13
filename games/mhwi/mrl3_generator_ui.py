import bpy

from ...core.i18n import T
from ...core.mdf_generator_base import get_mhwi_preset_dir, preset_has_albedo_blend_map
from ...core.mdf_generator_ui_base import MdfGenDialogBase
from .mrl3_tex_processor import MHWI_SLOT_CHANNEL_MAPS, MHWI_NULL_TEX


class MHWI_OT_Mrl3GeneratorDialog(MdfGenDialogBase):
    bl_idname  = "mhwi.mrl3_generator_dialog"
    bl_label   = "MRL3 Generator"

    _game_prefix       = "mhwi"
    _settings_attr     = "mhwi_mrl3_generator"
    _natives_root_key  = "mhwi_natives_root"
    _op_stem           = "mrl3_gen"
    _collection_label  = "Mod3 Collection"
    _out_kind          = "MRL3"
    _out_name_attr     = "mrl3_collection_name"
    _src_ext, _out_ext = ".mod3", ".mrl3"
    _path_prefix_label = "nativePC/"
    _path_hint         = "e.g. pl/f_equip/pl042_0500/helm/tex"
    _desc_key          = "mhwi.mrl3_generator_ui.dialog_desc"
    _preset_dir_missing_key = "mhwi.mrl3_generator_ui.preset_dir_not_found"
    _empty_hint_key    = "mhwi.mrl3_generator_ui.select_mod3_then_refresh"
    _is_mrl3           = True

    def _preset_dir(self):
        return get_mhwi_preset_dir()

    def _plan_tables(self):
        # MHWI has no vanilla survey and no placeholder slots.
        return dict(channel_maps=MHWI_SLOT_CHANNEL_MAPS,
                    null_for=lambda st, mmtr, cur: MHWI_NULL_TEX.get(st),
                    nulls=None, placeholder_slots=frozenset())

    def _draw_extra(self, box, entry):
        if preset_has_albedo_blend_map(entry.material_preset):
            box.prop(entry, "hide_snow_overlay", text=T("mhwi.mrl3_generator.hide_snow_overlay_name"))


classes = [MHWI_OT_Mrl3GeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
