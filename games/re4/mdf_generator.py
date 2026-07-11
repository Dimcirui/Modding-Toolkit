import bpy

from .mdf_tex_processor import (
    RE4_SLOT_CHANNEL_MAPS, RE4_NULL_TEX_BY_TYPE, RE4_TEXTURE_TYPE_ABBREV,
    RE4_TEX_VERSION,
)
from ...core.mdf_generator_base import (
    load_preset_enum_items,
    _find_meshes_by_material,
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


def _on_re4_mesh_collection_update(self, context):
    if self.mesh_collection:
        bpy.ops.re4.mdf_gen_refresh()


class RE4GenSettings(bpy.types.PropertyGroup):
    mesh_collection: bpy.props.PointerProperty(
        name="Mesh Collection",
        type=bpy.types.Collection,
        description="Source mesh collection containing objects with Blender materials",
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
        name="法线 OpenGL → DirectX",
        description="启用后，将连接的 OpenGL 法线贴图直接转为 DX 格式，"
                    "不再需要在着色器内手动进行 G 通道反相",
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
    """选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）"""
    bl_idname  = "re4.select_same_material"
    bl_label   = "Select Same Material Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    _log_tag = "RE4 Gen"

    @classmethod
    def poll(cls, context):
        """必须有激活 MESH 物体，且其材质已设置，mesh_collection 已选择"""
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
            self.report({'ERROR'}, "请先选择 Mesh Collection")
            return {'CANCELLED'}

        active_obj = context.active_object
        target_mat = active_obj.material_slots[active_obj.active_material_index].material
        if not target_mat:
            self.report({'ERROR'}, "激活物体没有材质")
            return {'CANCELLED'}

        # 查找同集合下共享相同材质的所有网格
        matched = _find_meshes_by_material(mesh_col, target_mat.name)

        # 取消所有选中
        for obj in context.view_layer.objects:
            obj.select_set(False)

        # 选中所有匹配的网格
        for obj in matched:
            obj.select_set(True)

        # 保持原物体激活
        if active_obj.name not in {o.name for o in matched}:
            active_obj.select_set(True)
        context.view_layer.objects.active = active_obj

        print(f"[{self._log_tag}] 智能筛选: 材质 '{target_mat.name}' → "
              f"{len(matched)} 个网格: {', '.join(o.name for o in matched)}")

        self.report(
            {'INFO'},
            f"已选中 {len(matched)} 个使用 '{target_mat.name}' 的网格"
            f"（含自身共 {len(matched) if active_obj.name in {o.name for o in matched} else len(matched) + 1} 个）",
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
