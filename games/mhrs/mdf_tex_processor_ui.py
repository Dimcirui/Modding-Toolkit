import bpy

from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import MHRS_COMMON_SLOT_TYPES, MHRS_NULL_TEX_BY_TYPE


class MHRS_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    """MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合"""
    bl_idname = "mhrs.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    _game_prefix       = "mhrs"
    _settings_attr     = "mhrs_mdf_tex_processor"
    _natives_root_key  = "mhrs_natives_root"
    _root_label        = "Natives Root"
    _path_prefix_label = "natives/STM/"
    _path_hint         = "例如 player/mod/f/pl279"
    _common_slot_types = MHRS_COMMON_SLOT_TYPES
    _null_tex_by_type  = MHRS_NULL_TEX_BY_TYPE


classes = [MHRS_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
