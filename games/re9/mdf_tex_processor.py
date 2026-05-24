import bpy

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
)

# ── RE9 Constants ──────────────────────────────────────────────────────────────

RE9_TEX_VERSION = 250813143

RE9_TEXTURE_TYPE_ABBREV = {
    **BASE_TEXTURE_TYPE_ABBREV,
    'OcclusionMap': 'OCC',
}

# RE9 channel maps: same as base but NRRC B channel = pure white (no Cavity input),
# plus OcclusionMap slot (AO packed into RGB).
RE9_SLOT_CHANNEL_MAPS = {
    **BASE_SLOT_CHANNEL_MAPS,
    'NormalRoughnessCavityMap': {
        'R': ('roughness', 0),
        'G': ('normal',    1),
        'B': 1.0,              # Cavity — always pure white for RE9
        'A': ('normal',    0),
    },
    'OcclusionMap': {
        'R': ('ao', 0),
        'G': ('ao', 0),
        'B': ('ao', 0),
        'A': 1.0,
    },
}

RE9_COMMON_SLOT_TYPES = BASE_COMMON_SLOT_TYPES | {'OcclusionMap'}

RE9_NULL_TEX_BY_TYPE = {
    **BASE_NULL_TEX_BY_TYPE,
    'OcclusionMap': 'systems/rendering/NullWhite.tex',
}

# ── Null checker + collection update callback ──────────────────────────────────

_is_null_re9             = make_null_checker(RE9_NULL_TEX_BY_TYPE)
_on_re9_collection_update = make_collection_update_cb(_is_null_re9)


# ── Settings PropertyGroup ─────────────────────────────────────────────────────

class RE9MdfTexProcessorSettings(bpy.types.PropertyGroup):
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=mdf_collection_poll,
        update=_on_re9_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/ (e.g. character/cha102_00)",
        default="",
    )
    materials:             bpy.props.CollectionProperty(type=MdfTexMaterialItem)
    materials_index:       bpy.props.IntProperty()
    clipboard_json:        bpy.props.StringProperty(default="")
    mdf_loaded_collection: bpy.props.StringProperty(default="")


# ── Operators ──────────────────────────────────────────────────────────────────

class RE9_OT_MdfTexRefresh(MdfTexRefreshBase):
    bl_idname      = "re9.mdf_tex_refresh"
    _settings_attr = "re9_mdf_tex_processor"
    _is_null_fn    = staticmethod(_is_null_re9)


class RE9_OT_MdfTexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "re9.mdf_tex_pick_pbr"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "re9.mdf_tex_pick_direct"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "re9.mdf_tex_clear_pbr"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "re9.mdf_tex_clear_direct"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "re9.mdf_tex_copy_material"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "re9.mdf_tex_paste_material"
    _settings_attr = "re9_mdf_tex_processor"


class RE9_OT_MdfTexProcess(MdfTexProcessBase):
    bl_idname         = "re9.mdf_tex_process"
    _settings_attr    = "re9_mdf_tex_processor"
    _natives_root_key = "re9_natives_root"
    _null_tex_by_type = RE9_NULL_TEX_BY_TYPE
    _channel_maps     = RE9_SLOT_CHANNEL_MAPS
    _tex_version      = RE9_TEX_VERSION
    _abbrev_map       = RE9_TEXTURE_TYPE_ABBREV
    _use_art_prefix   = False
    _log_tag          = "RE9 MDF Tex"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    RE9MdfTexProcessorSettings,
    RE9_OT_MdfTexRefresh,
    RE9_OT_MdfTexPickPBR,
    RE9_OT_MdfTexPickDirect,
    RE9_OT_MdfTexClearPBR,
    RE9_OT_MdfTexClearDirect,
    RE9_OT_MdfTexCopyMaterial,
    RE9_OT_MdfTexPasteMaterial,
    RE9_OT_MdfTexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.re9_mdf_tex_processor = bpy.props.PointerProperty(
        type=RE9MdfTexProcessorSettings)


def unregister():
    del bpy.types.Scene.re9_mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
