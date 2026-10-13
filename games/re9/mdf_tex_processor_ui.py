import bpy

from ...core.i18n import T
from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import (SLOT_NULLS, RE9_COMMON_SLOT_TYPES, RE9_NULL_TEX_BY_TYPE,
                                RE9_SLOT_CHANNEL_MAPS, RE9_TEXTURE_TYPE_ABBREV)


class RE9_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    bl_idname = "re9.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    @classmethod
    def description(cls, context, properties):
        return T("re9.mdf_tex_processor_ui.dialog_desc")

    _game_prefix       = "re9"
    _settings_attr     = "re9_mdf_tex_processor"
    _natives_root_key  = "re9_natives_root"
    _root_label        = "Natives Root"
    _path_prefix_label = "natives/STM/"
    _path_hint         = "e.g. character/cha000_00/"
    _common_slot_types = RE9_COMMON_SLOT_TYPES
    _null_tex_by_type  = RE9_NULL_TEX_BY_TYPE
    _slot_nulls        = SLOT_NULLS
    _channel_maps      = RE9_SLOT_CHANNEL_MAPS
    _abbrev_map        = RE9_TEXTURE_TYPE_ABBREV


classes = [RE9_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
