import bpy

from ...core.i18n import T
from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from ...core.slot_defaults import SlotNulls
from .mrl3_tex_processor import (
    MHWI_ALL_SLOT_TYPES, MHWI_NULL_TEX, MHWI_SLOT_CHANNEL_MAPS, MHWI_ABBREV_MAP,
    MHWI_FEATURE_CHANNELS,
)


class MHWI_OT_Mrl3TexProcessorDialog(MdfTexDialogBase):
    """The MDF processor's dialog, pointed at an MRL3 collection.

    One drawing code path for all five games, so MHWI gets the same AUTO
    badges, material list and per-channel rows -- and the same inputs gating:
    only what an MHWI slot stores is offered (no AO/cavity/SSS row), derived
    from MHWI_SLOT_CHANNEL_MAPS rather than a hand list. MHWI has no master
    material and no hand-measured survey, so nulls are its own table.
    """
    bl_idname  = "mhwi.mrl3_tex_processor_dialog"
    bl_label   = "MRL3 + Tex Processor"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_tex_processor_ui.dialog_desc")

    _game_prefix       = "mhwi"
    _settings_attr     = "mhwi_mrl3_tex_processor"
    _natives_root_key  = "mhwi_natives_root"
    _root_label        = "Mod Root"
    _path_prefix_label = "nativePC/"
    _path_hint_key     = "mhwi.mrl3_tex_processor_ui.base_path_example"
    _empty_hint_key    = "mhwi.mrl3_tex_processor_ui.select_mrl3_then_refresh"
    _collection_attr   = "mrl3_collection"
    _op_stem           = "mrl3_tex"
    _show_mip_strategy = False          # MHWI's export never reads mipmap_strategy
    _common_slot_types = MHWI_ALL_SLOT_TYPES
    _null_tex_by_type  = MHWI_NULL_TEX
    _slot_nulls        = SlotNulls(MHWI_NULL_TEX)
    _channel_maps      = MHWI_SLOT_CHANNEL_MAPS
    _abbrev_map        = MHWI_ABBREV_MAP
    _feature_channels  = MHWI_FEATURE_CHANNELS

    @property
    def _collection_label(self):
        return T("mhwi.mrl3_tex_processor_ui.mrl3_collection_label")

    def _mmtr_for(self, settings, mat):
        return ""                        # MRL3 has no master material


classes = [MHWI_OT_Mrl3TexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
