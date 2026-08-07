import bpy
from bpy.props import EnumProperty

from ...core.mdf_material_convert_base import MdfConvertMaterialDialogBase
from ...core.mdf_generator_base import load_preset_enum_items
from ...core.i18n import T
from .mdf_generator import MHWS_GEN_GAME

_preset_choice_items_cache = []


def _mhws_preset_choice_items(self, context):
    # Hardcoded to MHWS rather than read off self/type(self) -- Blender's
    # dynamic items= callback doesn't reliably see plain class attributes on
    # the leaf subclass, only real bpy.props. See MdfConvertMaterialDialogBase's
    # docstring for the full explanation.
    global _preset_choice_items_cache
    _preset_choice_items_cache = load_preset_enum_items(MHWS_GEN_GAME)
    return _preset_choice_items_cache


class MHWS_OT_MdfConvertMaterial(MdfConvertMaterialDialogBase):
    bl_idname = "mhws.mdf_convert_material_dialog"
    bl_label  = "Convert MDF Material"

    @classmethod
    def description(cls, context, properties):
        return T("mhws.mdf_material_convert.dialog_desc")

    preset_choice: EnumProperty(name="Preset", items=_mhws_preset_choice_items)

    _vanilla_asset_rel = "assets/mhws/vanilla_tex_paths.txt"
    _log_tag           = "MDF Convert"


classes = [MHWS_OT_MdfConvertMaterial]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
