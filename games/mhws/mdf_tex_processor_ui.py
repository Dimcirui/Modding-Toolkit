import bpy

from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import COMMON_SLOT_TYPES, NULL_TEX_BY_TYPE


class MHWS_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    """MHWs MDF2 + Tex semi-auto texture processor"""
    bl_idname = "mhws.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    _game_prefix       = "mhws"
    _settings_attr     = "mdf_tex_processor"
    _natives_root_key  = "mhws_natives_root"
    _root_label        = "Mod Root"
    _path_prefix_label = "natives/STM/Art/"
    _path_hint         = "e.g. Author/CharacterName/"
    _common_slot_types = COMMON_SLOT_TYPES
    _null_tex_by_type  = NULL_TEX_BY_TYPE


classes = [MHWS_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
