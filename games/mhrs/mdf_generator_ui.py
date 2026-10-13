import bpy

from .mdf_generator import MHRS_GEN_GAME, MHRS_OT_MdfGenProcess
from ...core.mdf_generator_base import get_preset_dir_for_game
from ...core.mdf_generator_ui_base import MdfGenDialogBase


class MHRS_OT_MdfGeneratorDialog(MdfGenDialogBase):
    bl_idname  = "mhrs.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"

    _game_prefix       = "mhrs"
    _settings_attr     = "mhrs_mdf_generator"
    _natives_root_key  = "mhrs_natives_root"
    _path_prefix_label = "natives/STM/"
    _path_hint_key     = "mhrs.mdf_generator_ui.base_path_hint"
    _desc_key          = "mhrs.mdf_generator_ui.dialog_desc"
    _preset_dir_missing_key = "mhrs.mdf_generator_ui.preset_dir_not_found"
    _empty_hint_key    = "mhrs.mdf_generator_ui.select_collection_hint"
    _process_cls       = MHRS_OT_MdfGenProcess

    def _preset_dir(self):
        return get_preset_dir_for_game(MHRS_GEN_GAME)


classes = [MHRS_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
