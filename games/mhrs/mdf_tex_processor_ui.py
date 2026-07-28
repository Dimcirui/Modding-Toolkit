import bpy

from ...core.i18n import T
from ...core.mdf_tex_processor_ui_base import MdfTexDialogBase
from .mdf_tex_processor import MHRS_COMMON_SLOT_TYPES, MHRS_NULL_TEX_BY_TYPE


class MHRS_OT_MdfTexProcessorDialog(MdfTexDialogBase):
    """MDF2 Processor — processes textures on top of existing MDF2 materials. Requires an existing,
    already-named MDF2 collection"""
    bl_idname = "mhrs.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex Processor"

    # NOTE: MdfTexDialogBase (core/mdf_tex_processor_ui_base.py, out of this migration's scope)
    # draws _path_hint as a plain f-string, not through T() — no per-draw dynamic-tooltip hook
    # exists there yet, so this is a stable English literal (matches the sibling re4/re9/mhws
    # subclasses, which already do the same).
    _path_hint         = "e.g. player/mod/f/pl279"

    _game_prefix       = "mhrs"
    _settings_attr     = "mhrs_mdf_tex_processor"
    _natives_root_key  = "mhrs_natives_root"
    _root_label        = "Natives Root"
    _path_prefix_label = "natives/STM/"
    _common_slot_types = MHRS_COMMON_SLOT_TYPES
    _null_tex_by_type  = MHRS_NULL_TEX_BY_TYPE

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.mdf_tex_processor_ui.dialog_desc")


classes = [MHRS_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
