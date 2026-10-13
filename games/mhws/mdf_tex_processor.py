import bpy

from ...core.slot_defaults import SlotNulls
from ...core.placeholder_tex import PLACEHOLDER_SLOT_TYPES
from ...core.mdf_tex_processor_base import fx_feature_channels
from ...core.mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
    BASE_COMMON_SLOT_TYPES,
    PBR_TYPES, PBR_TYPE_LABELS, PBR_CHANNEL_SELECTABLE, SRGB_SLOT_TYPES,
    _CH_ENUM_ITEMS,
    make_null_checker, make_collection_update_cb, mdf_collection_poll,
    MdfTexMaterialItem,
    MdfTexRefreshBase, MdfTexPickPBRBase, MdfTexPickDirectBase,
    MdfTexClearPBRBase, MdfTexClearDirectBase,
    MdfTexCopyMaterialBase, MdfTexPasteMaterialBase,
    MdfTexProcessBase,
    octahedral_normals_prop,
)
from ...core.color_grade import color_grade_items, DEFAULT_MODE_INDEX

# ── MHWS Constants ─────────────────────────────────────────────────────────────

MHWS_TEX_VERSION    = 241106027
COMMON_SLOT_TYPES   = BASE_COMMON_SLOT_TYPES
# MHWS-only paths: MasterMaterial/ here is MHWS's own (RE4 keeps its copy under
# _Chainsaw/, RE9 renamed it MaterialShader/), so these cannot be shared.
NULL_TEX_BY_TYPE    = {
    **BASE_NULL_TEX_BY_TYPE,
    'MP_noise':              'MasterMaterial/Textures/MP_noise_MSK4.tex',
    'Wind_Effect_VolumeMap': 'RE_ENGINE_LIBRARY/VFX_Library/Texture/TEX_Vectorfield/tex_capcom_vectorfield_0003_MSK4.tex',
    'FxMap':                 'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
    'noisemap':              'MasterMaterial/Textures/bluenoise_msk1.tex',
    'PanoramaMap':           'MasterMaterial/Textures/kirakira_PAN_ALB.tex',
    'VectorEmitMap':         'MasterMaterial/Textures/eye_VectorEmit_MSK3.tex',
    'VFX_Texture2D':         'MasterMaterial/Textures/VFX_Uber/VFX_Uber_MSK4.tex',
    'VFX_Texture3D':         'MasterMaterial/Textures/VFX_Uber/VFX_Uber3D_MSK4.tex',
    'Ripple_1Dtex':          'MasterMaterial/Textures/hagitori_ripple_ALB.tex',
    'Ripple_Texture3D':      'MasterMaterial/Textures/Noise3D_MSK3.tex',
    # A real noise texture, not a null: 98% of vanilla bindings (the survey).
    'ColorLayer_DetailMaskMap': 'MasterMaterial/Textures/ColorLayer_DetailNoise_01_ALB.tex',
}
TEXTURE_TYPE_ABBREV = BASE_TEXTURE_TYPE_ABBREV

# ── Null checker + collection update callback ──────────────────────────────────

# Mask slots with per-channel inputs (core.mdf_tex_processor_base.FEATURE_CHANNELS).
# Channel meanings: the community MHWS texture guide (caimogu.cc/post/1921753);
# XM_MSK4 binds to FxMap too (102/102 vanilla bindings), so FxMap.A is XM's fuzz
# mask. Unset values are each slot's vanilla null, decoded 2026-10-12:
# NullBlack_Alpha_MSK4 = (0,0,0,0), NullNormal = (0.5,0.5,1,0). Measured on 512
# vanilla masks, nothing else is safe: FX.G is 0 in a third of them, 1 in
# another third, and BC1-encoded masks report A = 1 only because BC1 has no alpha.
_K = "mhws.feature."
MHWS_FEATURE_CHANNELS = {
    'FxMap': fx_feature_channels((0.0, 0.0, 0.0, 0.0)),   # NullBlack_Alpha_MSK4
    'ColorLayer_MaskMap': {                      # needs the _UseSC material suffix
        'R': ('input', _K + "color_area1", 0.0),
        'G': ('input', _K + "color_area2", 0.0),
        'B': ('input', _K + "color_area3", 0.0),
        'A': ('fixed', 0.0, "core.feature.unused"),
    },
    'DetailMaskMap': {                           # where Detail_ALBD_x / Detail_NRRH_x apply
        'R': ('input', _K + "detail_r", 0.0),
        'G': ('input', _K + "detail_g", 0.0),
        'B': ('input', _K + "detail_b", 0.0),
        'A': ('input', _K + "detail_a", 0.0),
    },
    'FurFlowMap': {                              # FM_MSK4
        'R': ('input', _K + "fur_dir1",     0.5),    # 0-180 deg -> 0-1, layer 1
        'G': ('input', _K + "fur_dir2",     0.5),    # layer 2, usually the visible one
        'B': ('input', _K + "fur_presence", 1.0),
        'A': ('fixed', 0.0, "core.feature.unused"),
    },
}

# Vanilla-measured defaults where assets/mhws/vanilla_slot_defaults.json exists,
# the hand table above otherwise -- see core/slot_defaults.py.
SLOT_NULLS = SlotNulls.for_game("mhws", NULL_TEX_BY_TYPE)
_is_null_mhws = SLOT_NULLS.is_null
_on_mhws_collection_update = make_collection_update_cb(_is_null_mhws)


# ── Settings PropertyGroup ─────────────────────────────────────────────────────



class MdfTexProcessorSettings(bpy.types.PropertyGroup):
    octahedral_normals: octahedral_normals_prop()
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=mdf_collection_poll,
        update=_on_mhws_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/Art/ (e.g. Dimcirui/ShinanoPB)",
        default="",
    )
    materials:             bpy.props.CollectionProperty(type=MdfTexMaterialItem)
    materials_index:       bpy.props.IntProperty()
    clipboard_json:        bpy.props.StringProperty(default="")
    mdf_loaded_collection: bpy.props.StringProperty(default="")
    # 与生成器同名同义的全局档，见 core/color_grade.py。默认 NONE。
    global_color_grade: bpy.props.EnumProperty(
        name="Colour Grade (Global)",
        description="Tone adjustment applied to every colour (sRGB) texture before encoding",
        items=lambda self, ctx: color_grade_items(),
        default=DEFAULT_MODE_INDEX,
    )
    global_disable_mipmaps: bpy.props.BoolProperty(
        name="Disable MipMaps (Global)",
        description="Override every material's own Generate MipMaps checkbox and skip mipmap generation entirely",
        default=False,
    )


# ── Operators ──────────────────────────────────────────────────────────────────

class MHWS_OT_MdfTexRefresh(MdfTexRefreshBase):
    bl_idname      = "mhws.mdf_tex_refresh"
    _settings_attr = "mdf_tex_processor"
    _is_null_fn    = staticmethod(_is_null_mhws)


class MHWS_OT_MdfTexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "mhws.mdf_tex_pick_pbr"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "mhws.mdf_tex_pick_direct"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "mhws.mdf_tex_clear_pbr"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "mhws.mdf_tex_clear_direct"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "mhws.mdf_tex_copy_material"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "mhws.mdf_tex_paste_material"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexProcess(MdfTexProcessBase):
    bl_idname         = "mhws.mdf_tex_process"
    _settings_attr    = "mdf_tex_processor"
    _natives_root_key = "mhws_natives_root"
    _null_tex_by_type = NULL_TEX_BY_TYPE
    _slot_nulls       = SLOT_NULLS
    _feature_channels = MHWS_FEATURE_CHANNELS
    _placeholder_slots = PLACEHOLDER_SLOT_TYPES
    _channel_maps     = BASE_SLOT_CHANNEL_MAPS
    _tex_version      = MHWS_TEX_VERSION
    _abbrev_map       = TEXTURE_TYPE_ABBREV
    _use_art_prefix   = True
    _log_tag          = "MDF Tex"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MdfTexProcessorSettings,
    MHWS_OT_MdfTexRefresh,
    MHWS_OT_MdfTexPickPBR,
    MHWS_OT_MdfTexPickDirect,
    MHWS_OT_MdfTexClearPBR,
    MHWS_OT_MdfTexClearDirect,
    MHWS_OT_MdfTexCopyMaterial,
    MHWS_OT_MdfTexPasteMaterial,
    MHWS_OT_MdfTexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mdf_tex_processor = bpy.props.PointerProperty(
        type=MdfTexProcessorSettings)
    from ...core.mdf_port_tex import register_game_tex_config
    register_game_tex_config(
        "MHWS",
        abbrev_map=TEXTURE_TYPE_ABBREV,
        channel_maps=BASE_SLOT_CHANNEL_MAPS,
        tex_version=MHWS_TEX_VERSION,
        use_art_prefix=True,
        path_fixed_prefix="",
        null_tex_by_type=NULL_TEX_BY_TYPE,
        natives_root_key="mhws_natives_root",
        vanilla_asset_rel="assets/mhws/vanilla_tex_paths.txt",
    )


def unregister():
    from ...core.mdf_port_tex import unregister_game_tex_config
    unregister_game_tex_config("MHWS")
    del bpy.types.Scene.mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
