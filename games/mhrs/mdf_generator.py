import bpy

from .mdf_tex_processor import (
    MHRS_SLOT_CHANNEL_MAPS, MHRS_NULL_TEX_BY_TYPE, MHRS_TEXTURE_TYPE_ABBREV,
    MHRS_TEX_VERSION,
)
from ...core.mdf_generator_base import (
    load_preset_enum_items,
    MdfGenRefreshBase, MdfGenProcessBase,
)

# ── MHRS constants ──────────────────────────────────────────────────────────────

MHRS_GEN_GAME = "MHRS"   # must match RE Mesh Editor Presets/ subfolder name


# ── Preset enum callback ───────────────────────────────────────────────────────

def _mhrs_get_presets(self, context):
    return load_preset_enum_items(MHRS_GEN_GAME)


# ── PropertyGroups ─────────────────────────────────────────────────────────────

class MHRSGenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty(name="Blender Material")
    material_preset:  bpy.props.EnumProperty(
        name="Preset",
        description="MDF2 material preset from RE Mesh Editor",
        items=_mhrs_get_presets,
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
    use_ao:           bpy.props.BoolProperty(
        name="添加 AO",
        description="手动指定 AO 贴图 (Blender 无内置 AO 节点)",
        default=False,
    )
    ao_image:         bpy.props.StringProperty(
        name="AO",
        description="AO 贴图路径",
        subtype='FILE_PATH',
    )
    native_size_color:     bpy.props.IntProperty(default=0)
    native_size_normal:    bpy.props.IntProperty(default=0)
    native_size_roughness: bpy.props.IntProperty(default=0)
    native_size_metallic:  bpy.props.IntProperty(default=0)
    native_size_alpha:     bpy.props.IntProperty(default=0)
    native_size_emissive:  bpy.props.IntProperty(default=0)
    bake_size_color:       bpy.props.IntProperty(default=0)
    bake_size_normal:      bpy.props.IntProperty(default=0)
    bake_size_roughness:   bpy.props.IntProperty(default=0)
    bake_size_metallic:    bpy.props.IntProperty(default=0)
    bake_size_alpha:       bpy.props.IntProperty(default=0)
    bake_size_emissive:    bpy.props.IntProperty(default=0)


def _on_mhrs_mesh_collection_update(self, context):
    if self.mesh_collection:
        bpy.ops.mhrs.mdf_gen_refresh()


class MHRSGenSettings(bpy.types.PropertyGroup):
    mesh_collection: bpy.props.PointerProperty(
        name="Mesh Collection",
        type=bpy.types.Collection,
        description="Source mesh collection containing objects with Blender materials",
        update=_on_mhrs_mesh_collection_update,
    )
    mdf_collection_name: bpy.props.StringProperty(
        name="MDF Collection",
        default="",
        description="Target MDF2 collection name (auto-derived from mesh collection if empty)",
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        default="",
        description="Path appended to natives/STM/ (e.g. player/mod/f/pl279)",
    )
    material_list:     bpy.props.CollectionProperty(type=MHRSGenMaterialEntry)
    material_list_idx: bpy.props.IntProperty()
    flip_normal_g:     bpy.props.BoolProperty(
        name="法线 OpenGL → DirectX",
        description="启用后，将连接的 OpenGL 法线贴图直接转为 DX 格式，"
                    "不再需要在着色器内手动进行 G 通道反相",
        default=False,
    )


# ── Operators ──────────────────────────────────────────────────────────────────

class MHRS_OT_MdfGenRefresh(MdfGenRefreshBase):
    bl_idname      = "mhrs.mdf_gen_refresh"
    _settings_attr = "mhrs_mdf_generator"
    _game_name     = MHRS_GEN_GAME


class MHRS_OT_MdfGenProcess(MdfGenProcessBase):
    bl_idname          = "mhrs.mdf_gen_process"
    _settings_attr     = "mhrs_mdf_generator"
    _game_name         = MHRS_GEN_GAME
    _natives_root_key  = "mhrs_natives_root"
    _tex_version       = MHRS_TEX_VERSION
    _use_art_prefix    = False
    _abbrev_map        = MHRS_TEXTURE_TYPE_ABBREV
    _channel_maps      = MHRS_SLOT_CHANNEL_MAPS
    _null_tex_by_type  = MHRS_NULL_TEX_BY_TYPE
    _log_tag           = "MHRS Gen"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MHRSGenMaterialEntry,
    MHRSGenSettings,
    MHRS_OT_MdfGenRefresh,
    MHRS_OT_MdfGenProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhrs_mdf_generator = bpy.props.PointerProperty(
        type=MHRSGenSettings)


def unregister():
    del bpy.types.Scene.mhrs_mdf_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
