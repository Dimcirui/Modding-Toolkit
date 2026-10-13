import bpy

from .mdf_generator import MHWS_GEN_GAME, MHWS_OT_MdfGenProcess
from ...core.mdf_generator_base import get_preset_dir_for_game
from ...core.mdf_generator_ui_base import MdfGenDialogBase


class MHWS_OT_MdfGeneratorDialog(MdfGenDialogBase):
    bl_idname  = "mhws.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"

    _game_prefix       = "mhws"
    _settings_attr     = "mhws_mdf_generator"
    _natives_root_key  = "mhws_natives_root"
    _path_prefix_label = "natives/STM/Art/"
    _path_hint         = "e.g. Author/CharacterName/"
    _desc_key          = "mhws.mdf_generator_ui.dialog_desc"
    _preset_dir_missing_key = "mhws.mdf_generator_ui.preset_dir_not_found"
    _empty_hint_key    = "mhws.mdf_generator_ui.select_mesh_collection_hint"
    _process_cls       = MHWS_OT_MdfGenProcess

    def _preset_dir(self):
        return get_preset_dir_for_game(MHWS_GEN_GAME)


classes = [MHWS_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
