import bpy

from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import RE4_COMMON_SLOT_TYPES, RE4_NULL_TEX_BY_TYPE


class RE4_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    """RE4 MDF2 + Tex semi-auto texture processor"""
    bl_idname = "re4.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    _game_prefix       = "re4"
    _settings_attr     = "re4_mdf_tex_processor"
    _natives_root_key  = "re4_natives_root"
    _root_label        = "Natives Root"
    _path_prefix_label = "natives/STM/_Chainsaw/Character/ch/"
    _path_hint         = "e.g. Author/Name/"
    _common_slot_types = RE4_COMMON_SLOT_TYPES
    _null_tex_by_type  = RE4_NULL_TEX_BY_TYPE


classes = [RE4_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
