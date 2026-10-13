import bpy

from .mdf_generator import RE9_GEN_GAME, RE9_OT_MdfGenProcess
from ...core.mdf_generator_base import get_preset_dir_for_game
from ...core.mdf_generator_ui_base import MdfGenDialogBase


class RE9_OT_MdfGeneratorDialog(MdfGenDialogBase):
    bl_idname  = "re9.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"

    _game_prefix       = "re9"
    _settings_attr     = "re9_mdf_generator"
    _natives_root_key  = "re9_natives_root"
    _path_prefix_label = "natives/STM/"
    _path_hint         = "e.g. character/cha102_00/"
    _desc_key          = "re9.mdf_generator_ui.dialog_desc"
    _preset_dir_missing_key = "re9.mdf_generator_ui.preset_dir_not_found"
    _empty_hint_key    = "re9.mdf_generator_ui.select_mesh_then_refresh"
    _process_cls       = RE9_OT_MdfGenProcess

    def _preset_dir(self):
        return get_preset_dir_for_game(RE9_GEN_GAME)


classes = [RE9_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
