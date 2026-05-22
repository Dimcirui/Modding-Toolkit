import bpy

from ...core.mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
)
from ...core.mdf_generator_base import (
    load_preset_enum_items,
    MdfGenRefreshBase, MdfGenProcessBase,
)

# ── MHWS constants ─────────────────────────────────────────────────────────────

MHWS_TEX_VERSION  = 241106027
MHWS_GEN_GAME     = "MHWILDS"   # must match RE Mesh Editor Presets/ subfolder name


# ── Preset enum callback ───────────────────────────────────────────────────────

def _mhws_get_presets(self, context):
    return load_preset_enum_items(MHWS_GEN_GAME)


# ── PropertyGroups ─────────────────────────────────────────────────────────────

class MhwsGenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty(name="Blender Material")
    material_preset:  bpy.props.EnumProperty(
        name="Preset",
        description="MDF2 material preset from RE Mesh Editor",
        items=_mhws_get_presets,
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
    generate_mipmaps: bpy.props.BoolProperty(name="生成 MipMaps", default=True)
    skip_textures:    bpy.props.BoolProperty(
        name="仅生成材质",
        description="跳过贴图合成与转换，仅创建材质定义并填入贴图路径",
        default=False,
    )


class MhwsGenSettings(bpy.types.PropertyGroup):
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
        description="Path under natives/STM/Art/ (e.g. Author/CharacterName/)",
    )
    material_list:     bpy.props.CollectionProperty(type=MhwsGenMaterialEntry)
    material_list_idx: bpy.props.IntProperty()


# ── Operators ──────────────────────────────────────────────────────────────────

class MHWS_OT_MdfGenRefresh(MdfGenRefreshBase):
    bl_idname      = "mhws.mdf_gen_refresh"
    _settings_attr = "mhws_mdf_generator"
    _game_name     = MHWS_GEN_GAME


class MHWS_OT_MdfGenProcess(MdfGenProcessBase):
    bl_idname         = "mhws.mdf_gen_process"
    _settings_attr    = "mhws_mdf_generator"
    _game_name        = MHWS_GEN_GAME
    _natives_root_key = "mhws_natives_root"
    _tex_version      = MHWS_TEX_VERSION
    _use_art_prefix   = True
    _abbrev_map       = BASE_TEXTURE_TYPE_ABBREV
    _channel_maps     = BASE_SLOT_CHANNEL_MAPS
    _null_tex_by_type = BASE_NULL_TEX_BY_TYPE
    _log_tag          = "MHWS Gen"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MhwsGenMaterialEntry,
    MhwsGenSettings,
    MHWS_OT_MdfGenRefresh,
    MHWS_OT_MdfGenProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhws_mdf_generator = bpy.props.PointerProperty(
        type=MhwsGenSettings)


def unregister():
    del bpy.types.Scene.mhws_mdf_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
