import bpy

from ...core.i18n import T
from .mdf_tex_processor import (
    RE4_SLOT_CHANNEL_MAPS, RE4_NULL_TEX_BY_TYPE, RE4_TEXTURE_TYPE_ABBREV,
    RE4_TEX_VERSION,
)
from ...core.mdf_generator_base import (
    load_preset_enum_items,
    _find_meshes_by_material, mesh_collection_poll,
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
        name="Toon Shading",
        description="Skip emissive texture processing; set the emissive slot path the same as the base color slot",
        default=False,
    )
    generate_mipmaps: bpy.props.BoolProperty(name="Generate MipMaps", default=True)
    skip_textures:    bpy.props.BoolProperty(
        name="Materials Only",
        description="Skip texture composition/conversion; only create the material definition and fill in texture paths",
        default=False,
    )
    use_ao:           bpy.props.BoolProperty(
        name="Add AO",
        description="Manually specify an AO texture (Blender has no built-in AO node)",
        default=False,
    )
    ao_image:         bpy.props.StringProperty(
        name="AO",
        description="AO texture path",
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


def _on_re4_mesh_collection_update(self, context):
    if self.mesh_collection:
        bpy.ops.re4.mdf_gen_refresh()


class RE4GenSettings(bpy.types.PropertyGroup):
    mesh_collection: bpy.props.PointerProperty(
        name="Mesh Collection",
        type=bpy.types.Collection,
        description="Source mesh collection containing objects with Blender materials",
        poll=mesh_collection_poll,
        update=_on_re4_mesh_collection_update,
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
    material_list:     bpy.props.CollectionProperty(type=RE4GenMaterialEntry)
    material_list_idx: bpy.props.IntProperty()
    flip_normal_g:     bpy.props.BoolProperty(
        name="Normal Map: OpenGL -> DirectX",
        description="When enabled, converts a connected OpenGL normal texture directly to DX format, "
                    "so you no longer need to manually invert the G channel in the shader",
        default=False,
    )


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


# ── Select Same Material operator ────────────────────────────────────────────────

class RE4_OT_SelectSameMaterial(bpy.types.Operator):
    """Select all mesh objects in the Mesh Collection using the current material (stage 2: smart filtering)"""
    bl_idname  = "re4.select_same_material"
    bl_label   = "Select Same Material Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    _log_tag = "RE4 Gen"

    @classmethod
    def description(cls, context, properties):
        return T("re4.mdf_generator.select_same_material_desc")

    @classmethod
    def poll(cls, context):
        """Requires an active MESH object with a material set and mesh_collection selected"""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if not obj.material_slots:
            return False
        settings = context.scene.re4_mdf_generator
        if not settings.mesh_collection:
            return False
        mat = obj.material_slots[obj.active_material_index].material
        return mat is not None

    def execute(self, context):
        settings = context.scene.re4_mdf_generator
        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, T("re4.mdf_generator.select_mesh_collection_first"))
            return {'CANCELLED'}

        active_obj = context.active_object
        target_mat = active_obj.material_slots[active_obj.active_material_index].material
        if not target_mat:
            self.report({'ERROR'}, T("re4.mdf_generator.active_object_no_material"))
            return {'CANCELLED'}

        # Find all meshes in the same collection sharing this material
        matched = _find_meshes_by_material(mesh_col, target_mat.name)

        # Deselect everything
        for obj in context.view_layer.objects:
            obj.select_set(False)

        # Select all matched meshes
        for obj in matched:
            obj.select_set(True)

        # Keep the original object active
        if active_obj.name not in {o.name for o in matched}:
            active_obj.select_set(True)
        context.view_layer.objects.active = active_obj

        print(f"[{self._log_tag}] " + T("re4.mdf_generator.select_same_material_log").format(
            mat=target_mat.name, n=len(matched), names=', '.join(o.name for o in matched)))

        total = len(matched) if active_obj.name in {o.name for o in matched} else len(matched) + 1
        self.report(
            {'INFO'},
            T("re4.mdf_generator.select_same_material_done").format(
                n=len(matched), mat=target_mat.name, total=total),
        )
        return {'FINISHED'}


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    RE4GenMaterialEntry,
    RE4GenSettings,
    RE4_OT_MdfGenRefresh,
    RE4_OT_MdfGenProcess,
    RE4_OT_SelectSameMaterial,
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
