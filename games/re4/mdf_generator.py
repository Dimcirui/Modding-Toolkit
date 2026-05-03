import bpy

from .mdf_tex_processor import (
    RE4_SLOT_CHANNEL_MAPS, RE4_NULL_TEX_BY_TYPE, RE4_TEXTURE_TYPE_ABBREV,
    RE4_TEX_VERSION,
)
from ...core.mdf_generator_base import (
    load_preset_enum_items,
    MdfGenRefreshBase, MdfGenProcessBase,
)

# ── RE4 constants ──────────────────────────────────────────────────────────────

RE4_GEN_GAME = "RE4"   # must match RE Mesh Editor Presets/ subfolder name


# ── Preset enum callback ───────────────────────────────────────────────────────

def _re4_get_presets(self, context):
    return load_preset_enum_items(RE4_GEN_GAME)


# ── PropertyGroups ─────────────────────────────────────────────────────────────

class RE4GenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty(name="Blender Material")
    material_preset:  bpy.props.EnumProperty(
        name="Preset",
        description="MDF2 material preset from RE Mesh Editor",
        items=_re4_get_presets,
    )
    expanded:         bpy.props.BoolProperty(default=False)
    strategy_display: bpy.props.StringProperty(default="")
    strat_color:      bpy.props.StringProperty(default="?")
    strat_metallic:   bpy.props.StringProperty(default="?")
    strat_roughness:  bpy.props.StringProperty(default="?")
    strat_normal:     bpy.props.StringProperty(default="?")
    strat_alpha:      bpy.props.StringProperty(default="?")
    strat_emissive:   bpy.props.StringProperty(default="?")
    use_toon:         bpy.props.BoolProperty(
        name="使用三渲二",
        description="跳过自发光贴图处理，将自发光槽位路径设为与基础色槽位相同",
        default=False,
    )


class RE4GenSettings(bpy.types.PropertyGroup):
    mesh_collection: bpy.props.PointerProperty(
        name="Mesh Collection",
        type=bpy.types.Collection,
        description="Source mesh collection containing objects with Blender materials",
    )
    mdf_collection_name: bpy.props.StringProperty(
        name="MDF Collection",
        default="",
        description="Target MDF2 collection name (auto-derived from mesh collection if empty)",
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        default="",
        description="Path appended to natives/STM/_Chainsaw/Character/ch/ (e.g. Author/Name/)",
    )
    generate_mipmaps:  bpy.props.BoolProperty(name="Generate MipMaps", default=True)
    material_list:     bpy.props.CollectionProperty(type=RE4GenMaterialEntry)
    material_list_idx: bpy.props.IntProperty()


# ── Operators ──────────────────────────────────────────────────────────────────

class RE4_OT_MdfGenRefresh(MdfGenRefreshBase):
    bl_idname      = "re4.mdf_gen_refresh"
    _settings_attr = "re4_mdf_generator"
    _game_name     = RE4_GEN_GAME


class RE4_OT_MdfGenProcess(MdfGenProcessBase):
    bl_idname          = "re4.mdf_gen_process"
    _settings_attr     = "re4_mdf_generator"
    _game_name         = RE4_GEN_GAME
    _natives_root_key  = "re4_natives_root"
    _tex_version       = RE4_TEX_VERSION
    _use_art_prefix    = False
    _path_fixed_prefix = "_Chainsaw/Character/ch"
    _abbrev_map        = RE4_TEXTURE_TYPE_ABBREV
    _channel_maps      = RE4_SLOT_CHANNEL_MAPS
    _null_tex_by_type  = RE4_NULL_TEX_BY_TYPE
    _log_tag           = "RE4 Gen"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    RE4GenMaterialEntry,
    RE4GenSettings,
    RE4_OT_MdfGenRefresh,
    RE4_OT_MdfGenProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.re4_mdf_generator = bpy.props.PointerProperty(
        type=RE4GenSettings)


def unregister():
    del bpy.types.Scene.re4_mdf_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
