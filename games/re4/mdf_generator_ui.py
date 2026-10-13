import bpy

from .mdf_generator import RE4_GEN_GAME, RE4_OT_MdfGenProcess
from ...core.mdf_generator_base import get_preset_dir_for_game
from ...core.mdf_generator_ui_base import MdfGenDialogBase


class RE4_OT_MdfGeneratorDialog(MdfGenDialogBase):
    bl_idname  = "re4.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"

    _game_prefix       = "re4"
    _settings_attr     = "re4_mdf_generator"
    _natives_root_key  = "re4_natives_root"
    _path_prefix_label = "natives/STM/_Chainsaw/Character/ch/"
    _path_hint         = "e.g. Author/CharacterName/"
    _desc_key          = "re4.mdf_generator_ui.dialog_desc"
    _preset_dir_missing_key = "re4.mdf_generator_ui.preset_dir_not_found"
    _empty_hint_key    = "re4.mdf_generator_ui.select_mesh_collection_hint"
    _process_cls       = RE4_OT_MdfGenProcess

    def _preset_dir(self):
        return get_preset_dir_for_game(RE4_GEN_GAME)


classes = [RE4_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
