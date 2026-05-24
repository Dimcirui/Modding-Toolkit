import bpy
import os
import json
import tempfile
import shutil
import time

from ...core.mdf_generator_base import (
    MdfGenRefreshBase,
    analyze_material_strategies,
    _get_pbr_paths, _slugify, _strip_blender_suffix, _separate_mesh_by_material,
    _emissive_strength_is_zero, _is_emissive_slot, _is_albedo_slot,
    _make_source_id, _try_downgrade_slot, _generate_solid_texture_path,
    load_mhwi_preset_enum_items,
    _import_mhwi_tex_convert, _call_mhwi_read_preset, _import_mhwi_create_collection,
    BAKE_SIZE_DEFAULT,
)
from ...core.mdf_tex_processor_base import _import_tex_utils, _compose_channels
from .mrl3_tex_processor import (
    MHWI_SLOT_CHANNEL_MAPS, MHWI_NULL_TEX,
    MHWI_SRGB_SLOT_TYPES, MHWI_BC5_SLOT_TYPES,
    _mhwi_tex_binding, _mhwi_disk_path,
)


def _mhwi_get_presets(self, context):
    return load_mhwi_preset_enum_items()


# ── PropertyGroups ─────────────────────────────────────────────────────────────

class MhwiGenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty()
    material_preset:  bpy.props.EnumProperty(
        name="Preset", items=_mhwi_get_presets)
    expanded:         bpy.props.BoolProperty(default=True)
    strategy_display: bpy.props.StringProperty()
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


def _mhwi_mod3_col_poll(self, col):
    # MHWI 走的是 MHW Model Editor 的 MOD3 体系，不是 RE Engine 的 .mesh
    return col.get("~TYPE") == "MHW_MOD3_COLLECTION" or col.name.endswith(".mod3")


class MhwiGenSettings(bpy.types.PropertyGroup):
    # 属性名保留 mesh_collection 以兼容 MdfGenRefreshBase；MHWI 实际填的是 MOD3 集合
    mesh_collection: bpy.props.PointerProperty(
        name="Mod3 Collection",
        type=bpy.types.Collection,
        poll=_mhwi_mod3_col_poll,
    )
    mrl3_collection_name: bpy.props.StringProperty(
        name="MRL3 Collection Name",
        description="留空则自动从 MOD3 集合名推断",
        default="",
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="nativePC/ 下的贴图目录，例：pl/f_equip/pl042_0500/helm/tex",
        default="",
    )
    material_list:    bpy.props.CollectionProperty(type=MhwiGenMaterialEntry)


# ── Refresh operator ───────────────────────────────────────────────────────────

class MHWI_OT_Mrl3GenRefresh(MdfGenRefreshBase):
    """刷新材质列表"""
    bl_idname      = "mhwi.mrl3_gen_refresh"
    _settings_attr = "mhwi_mrl3_generator"
    _game_name     = "MHWI"

    @classmethod
    def _load_preset_items(cls):
        return load_mhwi_preset_enum_items()


# ── Process operator ───────────────────────────────────────────────────────────

class MHWI_OT_Mrl3GenProcess(bpy.types.Operator):
    """从 Blender 材质生成 MRL3 + 贴图"""
    bl_idname  = "mhwi.mrl3_gen_process"
    bl_label   = "Generate MRL3 + Textures"
    bl_options = {'REGISTER'}

    _log_tag  = "MRL3 Gen"
    _bake_size = BAKE_SIZE_DEFAULT

    def execute(self, context):
        _t_total = time.time()
        settings = context.scene.mhwi_mrl3_generator

        natives_root = context.scene.get("mhwi_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Mod Root 目录")
            return {'CANCELLED'}

        mod3_col = settings.mesh_collection
        if not mod3_col:
            self.report({'ERROR'}, "请先选择 MOD3 集合")
            return {'CANCELLED'}

        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, "请填写 Base Path（nativePC/ 下的贴图目录）")
            return {'CANCELLED'}

        if not settings.material_list:
            self.report({'ERROR'}, "请先点击 Refresh 加载材质")
            return {'CANCELLED'}

        _t_import = time.time()
        ConvertDDSToTex = _import_mhwi_tex_convert()
        print(f"[{self._log_tag}] 加载 MHW Model Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ConvertDDSToTex is None:
            self.report({'ERROR'},
                        "无法加载 MHW Model Editor 贴图转换函数，请确认已安装并启用")
            return {'CANCELLED'}

        _t_import = time.time()
        ImageListToDDS, _ddstotex = _import_tex_utils()
        print(f"[{self._log_tag}] 加载 RE Mesh Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ImageListToDDS is None:
            self.report({'ERROR'}, "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用")
            return {'CANCELLED'}

        mrl3_col = self._get_or_create_mrl3_collection(context, mod3_col, settings)

        temp_dir = tempfile.mkdtemp(prefix="mhwi_mrl3_gen_")
        comp_cache = {}  # (slot_type, source_ids, pbr_channels) → (composed, disk, binding)
        export_count = fail_count = 0

        try:
            for mat_entry in settings.material_list:
                try:
                    _t_mat = time.time()
                    self._process_one_material(
                        context, mat_entry, settings, mrl3_col,
                        natives_root, base_path, temp_dir,
                        ImageListToDDS, ConvertDDSToTex, mod3_col,
                        comp_cache,
                    )
                    export_count += 1
                    print(f"[{self._log_tag}] OK: {mat_entry.blender_material} ({time.time() - _t_mat:.2f}s)")
                except Exception as e:
                    import traceback
                    print(f"[{self._log_tag}] FAIL {mat_entry.blender_material}: {e}")
                    traceback.print_exc()
                    fail_count += 1
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        _t_sep = time.time()
        try:
            _separate_mesh_by_material(context, mod3_col)
            print(f"[{self._log_tag}] 分离网格: {time.time() - _t_sep:.2f}s", flush=True)
        except Exception as e:
            print(f"[{self._log_tag}] Mesh separate/rename warning: {e}")

        print(f"[{self._log_tag}] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)
        if fail_count:
            self.report({'WARNING'}, f"完成: 成功 {export_count}, 失败 {fail_count}")
        else:
            self.report({'INFO'}, f"完成: 成功生成 {export_count} 个材质的 MRL3 + 贴图")
        return {'FINISHED'}

    def _get_or_create_mrl3_collection(self, context, mod3_col, settings):
        mrl3_name = settings.mrl3_collection_name.strip()
        if not mrl3_name:
            # MHWI 的源集合后缀是 .mod3（MHW Model Editor 体系），不是 .mesh
            mrl3_name = (mod3_col.name.replace('.mod3', '.mrl3')
                         if '.mod3' in mod3_col.name
                         else mod3_col.name + ".mrl3")

        if mrl3_name in bpy.data.collections:
            return bpy.data.collections[mrl3_name]

        parent = next(
            (c for c in bpy.data.collections
             if mod3_col.name in [ch.name for ch in c.children]),
            None,
        )

        createCollection = _import_mhwi_create_collection()
        if createCollection:
            return createCollection(mrl3_name, "COLOR_05", "MHW_MRL3_COLLECTION", parent)

        # Fallback if MHW Model Editor function is unavailable
        col = bpy.data.collections.new(mrl3_name)
        col["~TYPE"] = "MHW_MRL3_COLLECTION"
        col.color_tag = "COLOR_05"
        if parent:
            parent.children.link(col)
        else:
            context.scene.collection.children.link(col)
        return col

    def _process_one_material(self, context, mat_entry, settings, mrl3_col,
                               natives_root, base_path, temp_dir,
                               ImageListToDDS, ConvertDDSToTex, mod3_col,
                               comp_cache):
        mat_name = mat_entry.blender_material
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            raise ValueError(f"Material '{mat_name}' not found")

        preset_path = mat_entry.material_preset
        if not preset_path or preset_path == 'NONE':
            raise ValueError(f"No preset selected for '{mat_name}'")
        if not os.path.isfile(preset_path):
            raise FileNotFoundError(f"Preset not found: {preset_path}")

        mesh_obj = next(
            (obj for obj in mod3_col.all_objects
             if obj.type == 'MESH'
             and any(m and m.name == mat_name for m in obj.data.materials)),
            None,
        )

        _t = time.time()
        strategies = analyze_material_strategies(mat)
        print(f"[{self._log_tag}]   分析材质节点: {time.time() - _t:.2f}s", flush=True)
        _t = time.time()
        pbr_paths  = _get_pbr_paths(
            mat, strategies, temp_dir, self._bake_size, context, mesh_obj)
        print(f"[{self._log_tag}]   解析PBR路径 (含烘培): {time.time() - _t:.2f}s", flush=True)

        pbr_channels = {}
        for pbr_type, strat_val in strategies.items():
            if strat_val[0] == 'DIRECT' and len(strat_val) > 2 and strat_val[2] != 'R':
                pbr_channels[pbr_type] = strat_val[2]

        tex_name = _slugify(_strip_blender_suffix(mat_name))

        _t = time.time()
        with open(preset_path, encoding='utf-8') as f:
            preset_data = json.load(f)
        print(f"[{self._log_tag}]   加载Preset JSON: {time.time() - _t:.2f}s", flush=True)
        slot_types = [entry["name"] for entry in preset_data.get("Map List", [])]

        use_toon       = getattr(mat_entry, 'use_toon', False)
        emi_zero       = _emissive_strength_is_zero(mat)
        emissive_slots = {st for st in slot_types if _is_emissive_slot(st)}
        albedo_slots   = {st for st in slot_types if _is_albedo_slot(st, MHWI_SLOT_CHANNEL_MAPS)}

        slot_binding_values = {}

        for slot_type in slot_types:
            # Emissive: skip composition if toon mode or strength is zero
            if slot_type in emissive_slots:
                if use_toon:
                    continue  # filled from albedo binding after loop
                if emi_zero:
                    null = MHWI_NULL_TEX.get(slot_type)
                    if null:
                        slot_binding_values[slot_type] = null
                    continue

            if slot_type not in MHWI_SLOT_CHANNEL_MAPS:
                null = MHWI_NULL_TEX.get(slot_type)
                if null:
                    slot_binding_values[slot_type] = null
                continue

            # --- skip_textures: just compute the binding path ---
            if getattr(mat_entry, 'skip_textures', False):
                slot_binding_values[slot_type] = _mhwi_tex_binding(
                    base_path, tex_name, slot_type)
                continue

            # --- cache key construction ---
            ch_map = MHWI_SLOT_CHANNEL_MAPS[slot_type]
            needed_pt = {src[0] for src in ch_map.values()
                         if src is not None and isinstance(src, tuple)}
            key_parts = []
            cache_ok = True
            for pt in sorted(needed_pt):
                sv = strategies.get(pt)
                if sv:
                    sid = _make_source_id(sv)
                    if sid is not None:
                        key_parts.append((pt, sid))
                    else:
                        cache_ok = False
                        break
                else:
                    cache_ok = False
                    break

            cache_key = None
            if cache_ok:
                ch_ov = frozenset((k, v) for k, v in pbr_channels.items() if k in needed_pt)
                cache_key = (slot_type, tuple(key_parts), ch_ov)
                cached = comp_cache.get(cache_key)
                if cached is not None:
                    slot_binding_values[slot_type] = cached[2]
                    continue

                # Only attempt downgrade for cacheable slots (no BAKE involved)
                rgba = _try_downgrade_slot(slot_type, strategies, pbr_channels, MHWI_SLOT_CHANNEL_MAPS)
                if rgba is not None:
                    hint = f"{tex_name}_{slot_type.lower()}_dg"
                    composed = _generate_solid_texture_path(rgba, temp_dir, hint, size=256)
                    if composed:
                        dds_fmt = (
                            'BC7_UNORM_SRGB' if slot_type in MHWI_SRGB_SLOT_TYPES else
                            'BC5_UNORM'      if slot_type in MHWI_BC5_SLOT_TYPES  else
                            'BC7_UNORM'
                        )
                        disk_path = _mhwi_disk_path(natives_root, base_path, tex_name, slot_type)
                        os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                        dds_stem = os.path.splitext(os.path.basename(composed))[0]
                        dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                        _t_dds = time.time()
                        ImageListToDDS([(composed, dds_fmt)], temp_dir, mat_entry.generate_mipmaps)
                        print(f"[{self._log_tag}]   PNG→DDS {slot_type} (优化): {time.time() - _t_dds:.2f}s", flush=True)
                        if not os.path.isfile(dds_path):
                            raise FileNotFoundError(f"texconv output not found: {dds_path}")
                        _t_tex = time.time()
                        ConvertDDSToTex([dds_path], disk_path)
                        print(f"[{self._log_tag}]   DDS→TEX {slot_type} (优化): {time.time() - _t_tex:.2f}s", flush=True)

                        binding = _mhwi_tex_binding(base_path, tex_name, slot_type)
                        slot_binding_values[slot_type] = binding
                        comp_cache[cache_key] = (composed, disk_path, binding)
                        continue

            # --- full composition path ---
            _t_comp = time.time()
            composed = _compose_channels(
                slot_type, pbr_paths, pbr_channels, temp_dir, tex_name,
                channel_maps=MHWI_SLOT_CHANNEL_MAPS,
            )
            print(f"[{self._log_tag}]   合成通道 {slot_type}: {time.time() - _t_comp:.2f}s", flush=True)

            if composed:
                dds_fmt = (
                    'BC7_UNORM_SRGB' if slot_type in MHWI_SRGB_SLOT_TYPES else
                    'BC5_UNORM'      if slot_type in MHWI_BC5_SLOT_TYPES  else
                    'BC7_UNORM'
                )
                disk_path = _mhwi_disk_path(natives_root, base_path, tex_name, slot_type)
                os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                dds_stem = os.path.splitext(os.path.basename(composed))[0]
                dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                _t_dds = time.time()
                ImageListToDDS([(composed, dds_fmt)], temp_dir, mat_entry.generate_mipmaps)
                print(f"[{self._log_tag}]   PNG→DDS {slot_type}: {time.time() - _t_dds:.2f}s", flush=True)
                if not os.path.isfile(dds_path):
                    raise FileNotFoundError(f"texconv output not found: {dds_path}")
                _t_tex = time.time()
                ConvertDDSToTex([dds_path], disk_path)
                print(f"[{self._log_tag}]   DDS→TEX {slot_type}: {time.time() - _t_tex:.2f}s", flush=True)

                binding = _mhwi_tex_binding(base_path, tex_name, slot_type)
                slot_binding_values[slot_type] = binding

                if cache_key is not None:
                    comp_cache[cache_key] = (composed, disk_path, binding)
                print(f"[{self._log_tag}]   {slot_type} -> {os.path.basename(disk_path)}")
            else:
                null = MHWI_NULL_TEX.get(slot_type)
                if null:
                    slot_binding_values[slot_type] = null

        # Toon shading: copy albedo binding value to all emissive slots
        if use_toon and emissive_slots:
            albedo_binding = next(
                (slot_binding_values[st] for st in albedo_slots if st in slot_binding_values),
                None,
            )
            for st in emissive_slots:
                if albedo_binding:
                    slot_binding_values[st] = albedo_binding
                else:
                    null = MHWI_NULL_TEX.get(st)
                    if null:
                        slot_binding_values[st] = null

        _t = time.time()
        mat_obj = _call_mhwi_read_preset(preset_path, mrl3_col)
        print(f"[{self._log_tag}]   创建MRL3材质: {time.time() - _t:.2f}s", flush=True)
        mat_obj.mhw_mrl3_material.materialName = tex_name
        for map_item in mat_obj.mhw_mrl3_material.mapList_items:
            if map_item.name in slot_binding_values:
                map_item.value = slot_binding_values[map_item.name]


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MhwiGenMaterialEntry,
    MhwiGenSettings,
    MHWI_OT_Mrl3GenRefresh,
    MHWI_OT_Mrl3GenProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhwi_mrl3_generator = bpy.props.PointerProperty(
        type=MhwiGenSettings)


def unregister():
    del bpy.types.Scene.mhwi_mrl3_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
