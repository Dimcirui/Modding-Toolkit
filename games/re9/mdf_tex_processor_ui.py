import bpy

from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import RE9_COMMON_SLOT_TYPES, RE9_NULL_TEX_BY_TYPE


class RE9_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    """RE9 MDF2 + Tex semi-auto texture processor"""
    bl_idname = "re9.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    _game_prefix       = "re9"
    _settings_attr     = "re9_mdf_tex_processor"
    _natives_root_key  = "re9_natives_root"
    _root_label        = "Natives Root"
    _path_prefix_label = "natives/STM/"
    _path_hint         = "e.g. character/cha000_00/"
    _common_slot_types = RE9_COMMON_SLOT_TYPES
    _null_tex_by_type  = RE9_NULL_TEX_BY_TYPE


classes = [RE9_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
