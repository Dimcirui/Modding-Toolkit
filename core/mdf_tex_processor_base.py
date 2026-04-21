import bpy
import os
import json
import tempfile
import shutil

# ── PBR Constants ──────────────────────────────────────────────────────────────

PBR_TYPES = ['color', 'alpha', 'emissive', 'normal', 'roughness', 'metallic', 'ao']

PBR_TYPE_LABELS = {
    'color':     "基础色 (Albedo)",
    'alpha':     "Alpha 遮罩",
    'emissive':  "自发光 (Emissive)",
    'normal':    "法线 (Normal)",
    'roughness': "粗糙度 (Roughness)",
    'metallic':  "金属度 (Metallic)",
    'ao':        "AO",
}

PBR_DEFAULTS = {
    'color':     [0.0, 0.0, 0.0, 1.0],
    'alpha':     [1.0, 1.0, 1.0, 1.0],
    'emissive':  [0.0, 0.0, 0.0, 0.0],
    'normal':    [0.5, 0.5, 1.0, 1.0],
    'roughness': [1.0, 1.0, 1.0, 1.0],
    'metallic':  [0.0, 0.0, 0.0, 1.0],
    'ao':        [1.0, 1.0, 1.0, 1.0],
}

# Only these PBR types expose a per-channel selector in the UI
PBR_CHANNEL_SELECTABLE = {'alpha', 'roughness', 'metallic', 'ao'}

# Slot types that should be converted as BC7_UNORM_SRGB (colour / emissive data)
SRGB_SLOT_TYPES = {'BaseDielectricMap', 'BaseAlphaMap', 'EmissiveMap'}

_CH           = {'R': 0, 'G': 1, 'B': 2, 'A': 3}
_CH_ENUM_ITEMS = [('R', 'R', ''), ('G', 'G', ''), ('B', 'B', ''), ('A', 'A', '')]

# ── Base texture data (all RE Engine games) ────────────────────────────────────

BASE_TEXTURE_TYPE_ABBREV = {
    'BaseDielectricMap':               'ALBD',
    'BaseAlphaMap':                    'BaseAlpha',
    'NormalRoughnessOcclusionMap':     'NRRO',
    'NormalRoughness':                 'NRMR',
    'NormalRoughnessCavityMap':        'NRRC',
    'EmissiveMap':                     'EMI',
    'AlphaTranslucentOcclusionSSSMap': 'ATOS',
    'NormalRoughnessMap':              'NRMR',
    'SSSCavityOcclusionTranslucentMap': 'SCOT',
    'AlphaCavityOcclusionTranslucentMap': 'ACOT',
}

# Channel composition maps.  Values may be:
#   (pbr_type, channel_index[, True=invert]) — source from PBR image
#   None                                     — constant 0.0
#   float/int                                — constant value (e.g. 1.0 = white)
BASE_SLOT_CHANNEL_MAPS = {
    'BaseDielectricMap': {
        'R': ('color',    0),
        'G': ('color',    1),
        'B': ('color',    2),
        'A': ('metallic', 0, True),
    },
    'BaseAlphaMap': {
        'R': ('color', 0),
        'G': ('color', 1),
        'B': ('color', 2),
        'A': ('alpha', 0),
    },
    'NormalRoughnessOcclusionMap': {
        'R': ('roughness', 0),
        'G': ('normal',    1),
        'B': ('ao',        0),
        'A': ('normal',    0),
    },
    'NormalRoughness': {
        'R': ('normal',    0),
        'G': ('normal',    1),
        'B': None,
        'A': ('roughness', 0),
    },
    'NormalRoughnessMap': {
        'R': ('normal',    0),
        'G': ('normal',    1),
        'B': None,
        'A': ('roughness', 0),
    },
    'NormalRoughnessCavityMap': {   # default: same layout as NRRO; RE9 overrides B=1.0
        'R': ('roughness', 0),
        'G': ('normal',    1),
        'B': ('ao',        0),
        'A': ('normal',    0),
    },
    'EmissiveMap': {
        'R': ('emissive', 0),
        'G': ('emissive', 1),
        'B': ('emissive', 2),
        'A': ('emissive', 3),
    },
    'AlphaTranslucentOcclusionSSSMap': {
        'R': ('alpha', 0),
        'G': None,
        'B': ('ao',   0),
        'A': None,
    },
    'SSSCavityOcclusionTranslucentMap': {
        'R': None,
        'G': 1.0,
        'B': ('ao', 0),
        'A': None,
    },
    'AlphaCavityOcclusionTranslucentMap': {
        'R': ('alpha', 0),
        'G': 1.0,
        'B': ('ao', 0),
        'A': None,
    },
}

BASE_COMMON_SLOT_TYPES = {
    'BaseDielectricMap',
    'BaseAlphaMap',
    'NormalRoughnessOcclusionMap',
    'NormalRoughnessCavityMap',
    'NormalRoughness',
    'NormalRoughnessMap',
    'AlphaTranslucentOcclusionSSSMap',
    'SSSCavityOcclusionTranslucentMap',
    'AlphaCavityOcclusionTranslucentMap',
    'EmissiveMap',
}

BASE_NULL_TEX_BY_TYPE = {
    'MP_noise':                      'MasterMaterial/Textures/MP_noise_MSK4.tex',
    'Wind_Effect_VolumeMap':         'RE_ENGINE_LIBRARY/VFX_Library/Texture/TEX_Vectorfield/tex_capcom_vectorfield_0003_MSK4.tex',
    'BaseDielectricMap':             'systems/rendering/NullBlack.tex',
    'NormalRoughnessOcclusionMap':   'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'NormalRoughnessCavityMap':      'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'NormalRoughnessMap':            'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'EmissiveMap':                   'systems/rendering/NullBlack.tex',
    'FxMap':                         'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
    'AlphaTranslucentOcclusionSSSMap': 'systems/rendering/NullATOS.tex',
    'SSSCavityOcclusionTranslucentMap': 'systems/rendering/NullATOS.tex',
    'AlphaCavityOcclusionTranslucentMap': 'systems/rendering/NullATOS.tex',
    'noisemap':                      'MasterMaterial/Textures/bluenoise_msk1.tex',
    'DetailMaskMap':                 'systems/rendering/NullBlack.tex',
    'Detail_ALBD_R':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_R':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_G':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_G':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_B':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_B':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_A':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_A':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'PanoramaMap':                   'MasterMaterial/Textures/kirakira_PAN_ALB.tex',
    'VectorEmitMap':                 'MasterMaterial/Textures/eye_VectorEmit_MSK3.tex',
    'VFX_Texture2D':                 'MasterMaterial/Textures/VFX_Uber/VFX_Uber_MSK4.tex',
    'VFX_Texture3D':                 'MasterMaterial/Textures/VFX_Uber/VFX_Uber3D_MSK4.tex',
    'Hair_Height_SpecMask_Shift_Map':'systems/rendering/NullWhite.tex',
    'HairOverMap':                   'systems/rendering/NullGray.tex',
    'MultiBlend_ALBDMap':            'systems/rendering/NullGray.tex',
    'MultiBlend_NRMMap':             'systems/rendering/NullNormal.tex',
    'GpuWind_MaskMap':               'systems/rendering/NullWhite.tex',
    'ColorLayer_MaskMap':            'systems/rendering/NullBlack.tex',
    'ColorLayer_DetailMaskMap':      'systems/rendering/NullBlack.tex',
    'Ripple_1Dtex':                  'MasterMaterial/Textures/hagitori_ripple_ALB.tex',
    'Ripple_Texture3D':              'MasterMaterial/Textures/Noise3D_MSK3.tex',
}

# ── Factory helpers ────────────────────────────────────────────────────────────

def make_null_checker(null_tex_by_type):
    """Return an is_null(path) -> bool for the given null_tex_by_type dict."""
    paths_set = {v.replace('\\', '/').lower() for v in null_tex_by_type.values()}
    def is_null(binding_path):
        p = binding_path.replace('\\', '/').lower()
        if p.startswith('natives/stm/'):
            p = p[len('natives/stm/'):]
        return p in paths_set
    return is_null

def make_collection_update_cb(is_null_fn):
    """Return an update callback for a mdf_collection PointerProperty."""
    def _on_collection_update(self, context):
        try:
            col = self.mdf_collection
            if col:
                _do_refresh(self, col, context.scene, is_null_fn=is_null_fn)
            else:
                if self.mdf_loaded_collection:
                    _save_col_state(context.scene, self.mdf_loaded_collection,
                                    {m.material_name: _capture_material_state(m)
                                     for m in self.materials})
                self.materials.clear()
                self.mdf_loaded_collection = ""
        except Exception as e:
            print(f"[MDF Tex] Auto-refresh error: {e}")
    return _on_collection_update


def make_mdf_path(base_path, tex_name, slot_type, abbrev_map, use_art_prefix=True):
    """Path string stored in the MDF2 binding (no version suffix)."""
    abbrev = abbrev_map.get(slot_type, slot_type)
    base   = base_path.strip('/\\').replace('\\', '/')
    return f"Art/{base}/{tex_name}_{abbrev}.tex" if use_art_prefix else f"{base}/{tex_name}_{abbrev}.tex"


def make_disk_path(natives_root, base_path, tex_name, slot_type, abbrev_map, tex_version,
                   use_art_prefix=True):
    """Absolute filesystem path for the .tex file."""
    abbrev = abbrev_map.get(slot_type, slot_type)
    parts  = base_path.strip('/\\').replace('\\', '/').split('/')
    mid    = os.path.join('Art', *parts) if use_art_prefix else os.path.join(*parts)
    rel    = os.path.join('natives', 'STM', mid, f"{tex_name}_{abbrev}.tex.{tex_version}")
    return os.path.join(natives_root, rel)


# ── RE Mesh Editor import ──────────────────────────────────────────────────────

def _import_tex_utils():
    """Locate and import ImageListToDDS / DDSToTex from RE Mesh Editor."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.re_tex_utils'):
            try:
                return mod.ImageListToDDS, mod.DDSToTex
            except AttributeError:
                pass
    if not hasattr(bpy.ops, 're_mesh') or not hasattr(bpy.ops.re_mesh, 'exportfile'):
        return None, None
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            tu = importlib.import_module(f"{pkg}.modules.tex.re_tex_utils")
            return tu.ImageListToDDS, tu.DDSToTex
        except Exception:
            continue
    return None, None


# ── Channel composition ────────────────────────────────────────────────────────

def _compose_channels(slot_type, pbr_paths, pbr_channels, temp_dir, tex_name, pbr_inv=None,
                       channel_maps=None, normal_flip_g=False):
    """Compose a packed texture from PBR inputs for the given slot type.
    channel_maps: optional override; defaults to BASE_SLOT_CHANNEL_MAPS.
    Channel map values: tuple (pbr_type, ch_idx[, True]) | None (=0.0) | float (constant).
    normal_flip_g: when True, inverts the G channel of the normal map (OpenGL to DirectX).
    """
    if pbr_inv is None:
        pbr_inv = {}
    if channel_maps is None:
        channel_maps = BASE_SLOT_CHANNEL_MAPS
    import numpy as np

    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        print(f"[MDF Tex] No channel map for slot type: {slot_type}")
        return None

    needed_types = {src[0] for src in ch_map.values()
                    if src is not None and isinstance(src, tuple)}
    loaded = {}
    ref_w = ref_h = 0

    for pbr_type in needed_types:
        img_path = pbr_paths.get(pbr_type, '')
        if not img_path or not os.path.isfile(img_path):
            continue
        tmp_name = f"__mdf_compose_tmp_{pbr_type}"
        if tmp_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[tmp_name])
        img = bpy.data.images.load(img_path)
        img.name = tmp_name
        img.colorspace_settings.name = 'Non-Color'
        iw, ih = img.size
        if ref_w == 0:
            ref_w, ref_h = iw, ih
        elif iw != ref_w or ih != ref_h:
            img.scale(ref_w, ref_h)
            iw, ih = ref_w, ref_h
        loaded[pbr_type] = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        bpy.data.images.remove(img)

    if not loaded:
        return None

    if ref_w == 0:
        ref_w = ref_h = 1024

    result = np.zeros((ref_h, ref_w, 4), dtype=np.float32)

    for out_ch, src in ch_map.items():
        out_i = _CH[out_ch]
        if src is None:
            result[:, :, out_i] = 0.0
            continue
        if isinstance(src, (int, float)):
            result[:, :, out_i] = float(src)
            continue
        pbr_type = src[0]
        in_ch_i  = src[1]
        invert   = len(src) > 2 and src[2] is True
        if pbr_type in PBR_CHANNEL_SELECTABLE:
            override = pbr_channels.get(pbr_type)
            if override:
                in_ch_i = _CH.get(override, in_ch_i)
        pix = loaded.get(pbr_type)
        if pix is None:
            result[:, :, out_i] = PBR_DEFAULTS.get(pbr_type, [0.0]*4)[in_ch_i]
        else:
            data = pix[:, :, in_ch_i].copy()
            if invert:
                data = 1.0 - data
            if pbr_type in PBR_CHANNEL_SELECTABLE and pbr_inv.get(pbr_type):
                data = 1.0 - data
            if normal_flip_g and pbr_type == 'normal' and in_ch_i == 1:
                data = 1.0 - data
            result[:, :, out_i] = data

    abbrev   = BASE_TEXTURE_TYPE_ABBREV.get(slot_type, slot_type)
    out_name = f"{tex_name}_{abbrev}_composed.png"
    out_path = os.path.join(temp_dir, out_name)

    tmp_out = f"__mdf_compose_out_{abbrev}"
    if tmp_out in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[tmp_out])
    out_img = bpy.data.images.new(tmp_out, width=ref_w, height=ref_h, alpha=True)
    out_img.colorspace_settings.name = 'Non-Color'
    out_img.pixels[:] = result.flatten().tolist()
    out_img.filepath_raw = out_path
    out_img.file_format = 'PNG'
    out_img.save()
    bpy.data.images.remove(out_img)
    return out_path


# ── State persistence ──────────────────────────────────────────────────────────

def _capture_material_state(m):
    return {
        'pbr':            {pt: getattr(m.pbr, pt) for pt in PBR_TYPES},
        'pbr_chs':        {pt: getattr(m.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
        'pbr_inv':        {pt: getattr(m.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
        'normal_flip_g':  m.pbr.normal_flip_g,
        'slots':          {s.texture_type: {'mode': s.mode, 'direct_image': s.direct_image}
                           for s in m.slots},
    }

def _save_col_state(scene, col_name, state):
    scene[f"mdf_tex_saved__{col_name}"] = json.dumps(state)

def _load_col_state(scene, col_name):
    raw = scene.get(f"mdf_tex_saved__{col_name}", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _do_refresh(settings, col, scene, is_null_fn=None):
    """Populate settings.materials from an MDF2 collection, preserving prior config."""
    if is_null_fn is None:
        is_null_fn = make_null_checker(BASE_NULL_TEX_BY_TYPE)

    loaded_name = settings.mdf_loaded_collection
    new_name    = col.name

    if loaded_name == new_name:
        saved = {m.material_name: _capture_material_state(m) for m in settings.materials}
        for k, v in _load_col_state(scene, new_name).items():
            saved.setdefault(k, v)
    else:
        if loaded_name:
            _save_col_state(scene, loaded_name,
                            {m.material_name: _capture_material_state(m)
                             for m in settings.materials})
        saved = _load_col_state(scene, new_name)

    settings.materials.clear()
    count = 0

    for obj in col.objects:
        if obj.get("~TYPE") != "RE_MDF_MATERIAL":
            continue
        mat_data = getattr(obj, 're_mdf_material', None)
        if mat_data is None:
            continue

        item = settings.materials.add()
        item.material_obj_name = obj.name
        item.material_name     = mat_data.materialName

        prev       = saved.get(mat_data.materialName, {})
        prev_pbr   = prev.get('pbr',     {})
        prev_chs   = prev.get('pbr_chs', {})
        prev_inv   = prev.get('pbr_inv', {})
        prev_slots = prev.get('slots',   {})

        for pt in PBR_TYPES:
            setattr(item.pbr, pt, prev_pbr.get(pt, ''))
        for pt in PBR_CHANNEL_SELECTABLE:
            setattr(item.pbr, f"{pt}_ch",  prev_chs.get(pt, 'R'))
            setattr(item.pbr, f"{pt}_inv", prev_inv.get(pt, False))
        item.pbr.normal_flip_g = prev.get('normal_flip_g', False)

        for binding in mat_data.textureBindingList_items:
            slot               = item.slots.add()
            slot.texture_type  = binding.textureType
            slot.original_path = binding.path
            if binding.textureType in prev_slots:
                sd = prev_slots[binding.textureType]
                if isinstance(sd, dict):
                    slot.mode         = sd.get('mode', 'SKIP')
                    slot.direct_image = sd.get('direct_image', '')
                else:
                    slot.mode, slot.direct_image = sd
            elif is_null_fn(binding.path):
                slot.mode = 'DEFAULT'
        count += 1

    _save_col_state(scene, new_name,
                    {m.material_name: _capture_material_state(m) for m in settings.materials})
    settings.mdf_loaded_collection = new_name
    return count


# ── MDF collection poll ────────────────────────────────────────────────────────

def mdf_collection_poll(self, col):
    return col.get("~TYPE") == "RE_MDF_COLLECTION" or col.name.endswith(".mdf2")


# ── Shared PropertyGroups ──────────────────────────────────────────────────────

class MdfTexPBRInputs(bpy.types.PropertyGroup):
    color:     bpy.props.StringProperty(name="基础色 (Albedo)", subtype='FILE_PATH')
    alpha:     bpy.props.StringProperty(name="Alpha 遮罩",      subtype='FILE_PATH')
    emissive:  bpy.props.StringProperty(name="自发光",           subtype='FILE_PATH')
    normal:    bpy.props.StringProperty(name="法线 (Normal)",   subtype='FILE_PATH')
    roughness: bpy.props.StringProperty(name="粗糙度",           subtype='FILE_PATH')
    metallic:  bpy.props.StringProperty(name="金属度",           subtype='FILE_PATH')
    ao:        bpy.props.StringProperty(name="AO",              subtype='FILE_PATH')
    alpha_ch:     bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    roughness_ch: bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    metallic_ch:  bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    ao_ch:        bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    alpha_inv:     bpy.props.BoolProperty(name="反相", default=False)
    roughness_inv: bpy.props.BoolProperty(name="反相", default=False)
    metallic_inv:  bpy.props.BoolProperty(name="反相", default=False)
    ao_inv:        bpy.props.BoolProperty(name="反相", default=False)
    normal_flip_g: bpy.props.BoolProperty(name="GL>DX", default=False,
                                          description="合成时翻转法线G通道 (OpenGL转DirectX)")


class MdfTexSlotItem(bpy.types.PropertyGroup):
    texture_type:  bpy.props.StringProperty(name="Texture Type")
    original_path: bpy.props.StringProperty(name="Original Path")
    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ('COMPOSE', 'PBR转换',   '从上方 PBR 输入合成通道并转换',      'NODE_COMPOSITING', 0),
            ('DIRECT',  '直接选择',  '直接选择已打包好的图片/DDS/TEX文件', 'IMAGE_DATA',       1),
            ('DEFAULT', '默认空贴图','写入该槽位对应的游戏内空贴图路径',    'LINKED',           2),
            ('SKIP',    '不修改',    '保持现有路径不变',                   'RADIOBUT_OFF',     3),
        ],
        default='SKIP',
    )
    direct_image: bpy.props.StringProperty(name="Direct Image", subtype='FILE_PATH')


class MdfTexMaterialItem(bpy.types.PropertyGroup):
    material_obj_name: bpy.props.StringProperty()
    material_name:     bpy.props.StringProperty()
    expanded:          bpy.props.BoolProperty(default=False)
    pbr_expanded:      bpy.props.BoolProperty(default=False)
    other_expanded:    bpy.props.BoolProperty(default=False)
    pbr:   bpy.props.PointerProperty(type=MdfTexPBRInputs)
    slots: bpy.props.CollectionProperty(type=MdfTexSlotItem)


# ── Base operator classes (NOT registered; subclasses must define bl_idname) ───

class MdfTexRefreshBase(bpy.types.Operator):
    bl_label   = "Refresh"
    bl_options = {'INTERNAL'}
    _settings_attr = ""
    _is_null_fn    = staticmethod(lambda p: False)

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        col = settings.mdf_collection
        if not col:
            self.report({'ERROR'}, "请先选择 MDF 集合")
            return {'CANCELLED'}
        count = _do_refresh(settings, col, context.scene, is_null_fn=type(self)._is_null_fn)
        self.report({'INFO'}, f"已加载 {count} 个材质")
        return {'FINISHED'}


class MdfTexPickPBRBase(bpy.types.Operator):
    bl_label   = "Pick Image"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:   bpy.props.IntProperty()
    pbr_type:    bpy.props.StringProperty()
    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, self.filepath)
        return {'FINISHED'}


class MdfTexPickDirectBase(bpy.types.Operator):
    bl_label   = "Pick Image"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:   bpy.props.IntProperty()
    slot_index:  bpy.props.IntProperty()
    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = self.filepath
                slots[self.slot_index].mode = 'DIRECT'
        return {'FINISHED'}


class MdfTexClearPBRBase(bpy.types.Operator):
    bl_label   = "Clear"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()
    pbr_type:  bpy.props.StringProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, '')
        return {'FINISHED'}


class MdfTexClearDirectBase(bpy.types.Operator):
    bl_label   = "Clear"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:  bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = ''
                slots[self.slot_index].mode = 'SKIP'
        return {'FINISHED'}


class MdfTexCopyMaterialBase(bpy.types.Operator):
    bl_label   = "Copy"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if not (0 <= self.mat_index < len(mats)):
            return {'CANCELLED'}
        mat = mats[self.mat_index]
        data = {
            'pbr':           {pt: getattr(mat.pbr, pt) for pt in PBR_TYPES},
            'pbr_chs':       {pt: getattr(mat.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
            'pbr_inv':       {pt: getattr(mat.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
            'normal_flip_g': mat.pbr.normal_flip_g,
            'slots':         {s.texture_type: {'mode': s.mode, 'direct_image': s.direct_image}
                              for s in mat.slots},
        }
        settings.clipboard_json = json.dumps(data)
        self.report({'INFO'}, f"已复制 {mat.material_name}")
        return {'FINISHED'}


class MdfTexPasteMaterialBase(bpy.types.Operator):
    bl_label   = "Paste"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        if not settings.clipboard_json:
            self.report({'WARNING'}, "剪贴板为空")
            return {'CANCELLED'}
        mats = settings.materials
        if not (0 <= self.mat_index < len(mats)):
            return {'CANCELLED'}
        data = json.loads(settings.clipboard_json)
        mat  = mats[self.mat_index]
        for pt, path in data.get('pbr', {}).items():
            if pt in PBR_TYPES:
                setattr(mat.pbr, pt, path)
        for pt, ch in data.get('pbr_chs', {}).items():
            if pt in PBR_CHANNEL_SELECTABLE:
                try:
                    setattr(mat.pbr, f"{pt}_ch", ch)
                except Exception:
                    pass
        for pt, inv in data.get('pbr_inv', {}).items():
            if pt in PBR_CHANNEL_SELECTABLE:
                setattr(mat.pbr, f"{pt}_inv", bool(inv))
        if 'normal_flip_g' in data:
            mat.pbr.normal_flip_g = bool(data['normal_flip_g'])
        slot_data = data.get('slots', {})
        for slot in mat.slots:
            if slot.texture_type in slot_data:
                sd = slot_data[slot.texture_type]
                slot.mode         = sd.get('mode', 'SKIP')
                slot.direct_image = sd.get('direct_image', '')
        self.report({'INFO'}, f"已粘贴到 {mat.material_name}")
        return {'FINISHED'}


class MdfTexProcessBase(bpy.types.Operator):
    """Process MDF2 texture bindings: compose/convert images and update paths"""
    bl_label   = "Process"
    bl_options = {'REGISTER'}

    _settings_attr    = ""
    _natives_root_key = ""
    _null_tex_by_type = {}
    _channel_maps     = {}
    _tex_version      = 0
    _abbrev_map       = {}
    _use_art_prefix   = True
    _path_fixed_prefix = ""   # Optional path segment prepended to texture_base_path
    _log_tag          = "MDF Tex"

    def execute(self, context):
        scene    = context.scene
        cls      = type(self)
        settings = getattr(scene, cls._settings_attr)

        natives_root = scene.get(cls._natives_root_key, "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Natives Root 目录（natives 的上级文件夹）")
            return {'CANCELLED'}
        if not settings.mdf_collection:
            self.report({'ERROR'}, "请先选择 MDF 集合")
            return {'CANCELLED'}
        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, "请填写 Base Path")
            return {'CANCELLED'}
        if cls._path_fixed_prefix:
            base_path = cls._path_fixed_prefix.strip('/') + '/' + base_path.strip('/')
        if not settings.materials:
            self.report({'ERROR'}, "请先点击 Refresh 加载材质")
            return {'CANCELLED'}

        ImageListToDDS, DDSToTex = _import_tex_utils()
        if ImageListToDDS is None or DDSToTex is None:
            self.report({'ERROR'}, "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用")
            return {'CANCELLED'}

        temp_dir = tempfile.mkdtemp(prefix="mdf_tex_")
        export_count = fail_count = skip_count = 0

        try:
            for mat_item in settings.materials:
                mat_obj = settings.mdf_collection.objects.get(mat_item.material_obj_name)
                if mat_obj is None:
                    continue
                mat_data = getattr(mat_obj, 're_mdf_material', None)
                if mat_data is None:
                    continue

                tex_name     = mat_item.material_name.removesuffix('_UseSC')
                pbr_paths      = {pt: getattr(mat_item.pbr, pt) for pt in PBR_TYPES}
                pbr_channels   = {pt: getattr(mat_item.pbr, f"{pt}_ch")
                                  for pt in PBR_CHANNEL_SELECTABLE}
                pbr_inv        = {pt: getattr(mat_item.pbr, f"{pt}_inv")
                                  for pt in PBR_CHANNEL_SELECTABLE}
                normal_flip_g  = mat_item.pbr.normal_flip_g

                color_path    = pbr_paths.get('color', '')
                emissive_path = pbr_paths.get('emissive', '')
                share_emi     = bool(color_path and emissive_path and color_path == emissive_path)
                albd_path_out = None

                for slot in mat_item.slots:
                    if slot.mode == 'SKIP':
                        skip_count += 1
                        continue
                    binding = next(
                        (b for b in mat_data.textureBindingList_items
                         if b.textureType == slot.texture_type), None)
                    if binding is None:
                        skip_count += 1
                        continue

                    mdf_path = make_mdf_path(base_path, tex_name, slot.texture_type,
                                             cls._abbrev_map, cls._use_art_prefix)

                    if slot.mode == 'DEFAULT':
                        null_rel = cls._null_tex_by_type.get(slot.texture_type)
                        if null_rel:
                            binding.path = null_rel
                            print(f"[{cls._log_tag}] NULL {slot.texture_type}: {null_rel}")
                            export_count += 1
                        else:
                            print(f"[{cls._log_tag}] SKIP (no null) {slot.texture_type}")
                            skip_count += 1
                        continue

                    if (slot.mode == 'COMPOSE'
                            and slot.texture_type == 'EmissiveMap'
                            and share_emi and albd_path_out):
                        binding.path = albd_path_out
                        print(f"[{cls._log_tag}] EMI reuse ALBD: {albd_path_out}")
                        export_count += 1
                        continue

                    try:
                        if slot.mode == 'COMPOSE':
                            src_img = _compose_channels(
                                slot.texture_type, pbr_paths, pbr_channels,
                                temp_dir, tex_name, pbr_inv,
                                channel_maps=cls._channel_maps,
                                normal_flip_g=normal_flip_g)
                            if src_img is None:
                                null_rel = cls._null_tex_by_type.get(slot.texture_type)
                                if null_rel:
                                    binding.path = null_rel
                                    print(f"[{cls._log_tag}] NULL (empty inputs) {slot.texture_type}: {null_rel}")
                                    export_count += 1
                                else:
                                    print(f"[{cls._log_tag}] SKIP (empty inputs, no null) {slot.texture_type}")
                                    skip_count += 1
                                continue
                        else:  # DIRECT
                            src_img = bpy.path.abspath(slot.direct_image)
                            if not src_img or not os.path.isfile(src_img):
                                print(f"[{cls._log_tag}] SKIP direct {slot.texture_type}: not found")
                                skip_count += 1
                                continue

                        dds_fmt   = ('BC7_UNORM_SRGB'
                                     if slot.texture_type in SRGB_SLOT_TYPES
                                     else 'BC7_UNORM')
                        disk_path = make_disk_path(
                            natives_root, base_path, tex_name, slot.texture_type,
                            cls._abbrev_map, cls._tex_version, cls._use_art_prefix)
                        os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                        src_lower = src_img.lower()
                        src_name  = os.path.basename(src_img)

                        if '.tex' in src_name.lower():
                            shutil.copy2(src_img, disk_path)
                        elif src_lower.endswith('.dds'):
                            DDSToTex([src_img], cls._tex_version, disk_path)
                        else:
                            dds_stem = os.path.splitext(src_name)[0]
                            dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                            ImageListToDDS([(src_img, dds_fmt)], temp_dir,
                                           settings.generate_mipmaps)
                            if not os.path.isfile(dds_path):
                                raise FileNotFoundError(
                                    f"texconv output not found: {dds_path}")
                            DDSToTex([dds_path], cls._tex_version, disk_path)

                        binding.path = mdf_path
                        if slot.texture_type == 'BaseDielectricMap':
                            albd_path_out = mdf_path
                        print(f"[{cls._log_tag}] OK {slot.texture_type} -> {os.path.basename(disk_path)}")
                        export_count += 1

                    except Exception as err:
                        print(f"[{cls._log_tag}] FAIL {slot.texture_type}: {err}")
                        fail_count += 1

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if fail_count > 0:
            self.report({'WARNING'},
                        f"完成: 生成 {export_count}, 失败 {fail_count}, 跳过 {skip_count}")
        else:
            self.report({'INFO'}, f"完成: 生成 {export_count}, 跳过 {skip_count}")
        return {'FINISHED'}


# ── Registration (shared PropertyGroups only) ──────────────────────────────────

_base_classes = [MdfTexPBRInputs, MdfTexSlotItem, MdfTexMaterialItem]


def register():
    for cls in _base_classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_base_classes):
        bpy.utils.unregister_class(cls)
