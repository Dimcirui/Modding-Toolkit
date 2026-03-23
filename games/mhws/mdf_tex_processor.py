import bpy
import os
import json
import tempfile
import shutil

# ── Constants ─────────────────────────────────────────────────────────────────

MHWS_TEX_VERSION = 241106027

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

# Texture types considered "common" — shown in the primary slot section
COMMON_SLOT_TYPES = {
    'BaseDielectricMap',
    'BaseAlphaMap',
    'NormalRoughnessOcclusionMap',
    'NormalRoughnessCavity',
    'NormalRoughness',
    'AlphaTranslucentOcclusionSSSMap',
    'EmissiveMap',
}

# PBR channel defaults (RGBA) when the source image is not provided
PBR_DEFAULTS = {
    'color':     [0.0, 0.0, 0.0, 1.0],  # black
    'alpha':     [1.0, 1.0, 1.0, 1.0],  # white (opaque)
    'emissive':  [0.0, 0.0, 0.0, 0.0],  # black
    'normal':    [0.5, 0.5, 1.0, 1.0],  # neutral flat (DX: R=0.5 X, G=0.5 Y)
    'roughness': [1.0, 1.0, 1.0, 1.0],  # white (fully rough)
    'metallic':  [0.0, 0.0, 0.0, 1.0],  # black (non-metallic)
    'ao':        [1.0, 1.0, 1.0, 1.0],  # white (no occlusion)
}

# Abbreviations used in output filenames
TEXTURE_TYPE_ABBREV = {
    'BaseDielectricMap':               'ALBD',
    'BaseAlphaMap':                    'BaseAlpha',
    'NormalRoughnessOcclusionMap':     'NRRO',
    'NormalRoughness':                 'NRMR',
    'NormalRoughnessCavity':           'NRRC',
    'EmissiveMap':                     'EMI',
    'AlphaTranslucentOcclusionSSSMap': 'ATOS',
}

# Channel composition maps per slot type.
# Format: { out_channel: (pbr_type, channel_index) | (pbr_type, channel_index, True=invert) | None }
# channel_index: 0=R, 1=G, 2=B, 3=A;  None means constant 0.0
_CH = {'R': 0, 'G': 1, 'B': 2, 'A': 3}

SLOT_CHANNEL_MAPS = {
    'BaseDielectricMap': {
        'R': ('color',    0),
        'G': ('color',    1),
        'B': ('color',    2),
        'A': ('metallic', 0, True),   # dielectric = 1 - metallic
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
        'B': None,                    # constant 0
        'A': ('roughness', 0),
    },
    'NormalRoughnessCavity': {        # same layout as NRRO
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
        'G': None,            # translucent: constant 0
        'B': ('ao',   0),
        'A': None,            # SSS: constant 0
    },
}

# Slots that should use BC7_UNORM_SRGB (color / emissive data)
SRGB_SLOT_TYPES = {'BaseDielectricMap', 'BaseAlphaMap', 'EmissiveMap'}

# PBR types that expose a per-channel selector (single-channel grayscale inputs).
# 'color', 'normal', 'emissive' are excluded: all fixed multi-channel RGB inputs.
PBR_CHANNEL_SELECTABLE = {'alpha', 'roughness', 'metallic', 'ao'}

_CH_ENUM_ITEMS = [('R', 'R', ''), ('G', 'G', ''), ('B', 'B', ''), ('A', 'A', '')]

# ── Null / default texture paths (relative to natives/STM/) ──────────────────
# When mode == 'DEFAULT', the binding path is set to natives/STM/{value}.
# Used for texture slots that should point to a game-provided null texture.
NULL_TEX_BY_TYPE = {
    'MP_noise':                      'MasterMaterial/Textures/MP_noise_MSK4.tex',
    'Wind_Effect_VolumeMap':         'RE_ENGINE_LIBRARY/VFX_Library/Texture/TEX_Vectorfield/tex_capcom_vectorfield_0003_MSK4.tex',
    'BaseDielectricMap':             'systems/rendering/NullBlack.tex',
    'NormalRoughnessOcclusionMap':   'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'EmissiveMap':                   'systems/rendering/NullBlack.tex',
    'FxMap':                         'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
    'AlphaTranslucentOcclusionSSSMap': 'systems/rendering/NullATOS.tex',
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

# Normalised set of all null paths for fast auto-detection
_NULL_PATHS_SET = {v.replace('\\', '/').lower() for v in NULL_TEX_BY_TYPE.values()}


def _is_null_tex(binding_path):
    """Return True if binding_path points to a known null/default texture."""
    p = binding_path.replace('\\', '/').lower()
    # Strip leading natives/STM/ prefix if present
    for prefix in ('natives/stm/',):
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    return p in _NULL_PATHS_SET


# ── RE Mesh Editor Import ─────────────────────────────────────────────────────

def _import_tex_utils():
    """
    Locate and import ImageListToDDS / DDSToTex from RE Mesh Editor.
    Returns (ImageListToDDS, DDSToTex) or (None, None) if unavailable.
    Uses sys.modules search (fast, works after first import) with addon_utils fallback.
    """
    import sys
    import importlib

    # Fast path: already imported
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.re_tex_utils'):
            try:
                return mod.ImageListToDDS, mod.DDSToTex
            except AttributeError:
                pass

    # Primary availability check (same as RE9 batch export)
    if not hasattr(bpy.ops, 're_mesh') or not hasattr(bpy.ops.re_mesh, 'exportfile'):
        return None, None

    # Find the package root and import tex utils
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


# ── Channel Composition ───────────────────────────────────────────────────────

def _compose_channels(slot_type, pbr_paths, pbr_channels, temp_dir, tex_name, pbr_inv=None):
    """
    Compose a packed texture from individual PBR inputs for the given slot type.
    pbr_channels: {pbr_type: channel_char} overrides for selectable types ('R','G','B','A').
    pbr_inv: {pbr_type: bool} user-requested invert for selectable types.
    Saves a PNG to temp_dir and returns its path, or None on failure.
    All images are loaded as Non-Color (raw bytes) to bypass Blender color management.
    """
    if pbr_inv is None:
        pbr_inv = {}
    import numpy as np

    ch_map = SLOT_CHANNEL_MAPS.get(slot_type)
    if ch_map is None:
        print(f"[MDF Tex Processor] No channel map for slot type: {slot_type}")
        return None

    # ── Load needed PBR images ──
    loaded = {}      # pbr_type -> numpy array (H, W, 4) float32
    ref_w = ref_h = 0

    needed_types = {src[0] for src in ch_map.values() if src is not None}
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

        iw, ih = img.size[0], img.size[1]

        # Use the first loaded image as the reference size
        if ref_w == 0:
            ref_w, ref_h = iw, ih
        elif iw != ref_w or ih != ref_h:
            img.scale(ref_w, ref_h)
            iw, ih = ref_w, ref_h

        pix = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        loaded[pbr_type] = pix
        bpy.data.images.remove(img)

    if ref_w == 0:
        ref_w = ref_h = 1024   # fallback if no images provided at all

    # ── Compose channels ──
    result = np.zeros((ref_h, ref_w, 4), dtype=np.float32)

    for out_ch, src in ch_map.items():
        out_i = _CH[out_ch]
        if src is None:
            result[:, :, out_i] = 0.0
            continue

        pbr_type = src[0]
        in_ch_i  = src[1]
        invert   = len(src) > 2 and src[2] is True

        # Allow user to override which channel to read for selectable types
        if pbr_type in PBR_CHANNEL_SELECTABLE:
            override = pbr_channels.get(pbr_type)
            if override:
                in_ch_i = _CH.get(override, in_ch_i)

        pix = loaded.get(pbr_type)
        if pix is None:
            result[:, :, out_i] = PBR_DEFAULTS.get(pbr_type, [0.0] * 4)[in_ch_i]
        else:
            data = pix[:, :, in_ch_i].copy()
            if invert:
                data = 1.0 - data
            # Apply user-requested invert (e.g. smoothness→roughness)
            if pbr_type in PBR_CHANNEL_SELECTABLE and pbr_inv.get(pbr_type):
                data = 1.0 - data
            result[:, :, out_i] = data

    # ── Save composed image as PNG ──
    abbrev = TEXTURE_TYPE_ABBREV.get(slot_type, slot_type)
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


# ── Path Helpers ──────────────────────────────────────────────────────────────

def _make_mdf_path(base_path, tex_name, slot_type):
    """Path string stored in the MDF2 binding (no version suffix)."""
    abbrev = TEXTURE_TYPE_ABBREV.get(slot_type, slot_type)
    base   = base_path.strip('/\\').replace('\\', '/')
    return f"natives/STM/Art/{base}/{tex_name}_{abbrev}.tex"


def _make_disk_path(natives_root, base_path, tex_name, slot_type):
    """Absolute filesystem path for the .tex file.
    natives_root is the mod root (parent of the natives folder), matching
    the same convention used by MHWS_OT_SetNativesRoot / batch_export.
    """
    abbrev = TEXTURE_TYPE_ABBREV.get(slot_type, slot_type)
    rel    = os.path.join('natives', 'STM', 'Art',
                          base_path.strip('/\\'), f"{tex_name}_{abbrev}.tex")
    return os.path.join(natives_root, rel)


# ── Property Groups ───────────────────────────────────────────────────────────

class MdfTexPBRInputs(bpy.types.PropertyGroup):
    # File paths
    color:     bpy.props.StringProperty(name="基础色 (Albedo)", subtype='FILE_PATH')
    alpha:     bpy.props.StringProperty(name="Alpha 遮罩",      subtype='FILE_PATH')
    emissive:  bpy.props.StringProperty(name="自发光",           subtype='FILE_PATH')
    normal:    bpy.props.StringProperty(name="法线 (Normal)",   subtype='FILE_PATH')
    roughness: bpy.props.StringProperty(name="粗糙度",           subtype='FILE_PATH')
    metallic:  bpy.props.StringProperty(name="金属度",           subtype='FILE_PATH')
    ao:        bpy.props.StringProperty(name="AO",              subtype='FILE_PATH')
    # Channel selectors for single-channel inputs (color/normal/emissive are fixed multi-channel)
    alpha_ch:     bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    roughness_ch: bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    metallic_ch:  bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    ao_ch:        bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    # Invert toggles (e.g. smoothness→roughness, dielectric→metallic)
    alpha_inv:     bpy.props.BoolProperty(name="反相", default=False)
    roughness_inv: bpy.props.BoolProperty(name="反相", default=False)
    metallic_inv:  bpy.props.BoolProperty(name="反相", default=False)
    ao_inv:        bpy.props.BoolProperty(name="反相", default=False)


class MdfTexSlotItem(bpy.types.PropertyGroup):
    texture_type:  bpy.props.StringProperty(name="Texture Type")
    original_path: bpy.props.StringProperty(name="Original Path")

    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ('COMPOSE', 'PBR转换', '从上方 PBR 输入合成通道并转换',       'NODE_COMPOSITING', 0),
            ('DIRECT',  '直接选择', '直接选择已打包好的图片/DDS/TEX文件', 'IMAGE_DATA',       1),
            ('DEFAULT', '默认空贴图', '写入该槽位对应的游戏内空贴图路径',    'LINKED',           2),
            ('SKIP',    '不修改',  '保持现有路径不变',                    'RADIOBUT_OFF',     3),
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


def _mdf_collection_poll(self, col):
    """Only show MDF2 collections in the picker."""
    return col.get("~TYPE") == "RE_MDF_COLLECTION" or col.name.endswith(".mdf2")


class MdfTexProcessorSettings(bpy.types.PropertyGroup):
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=_mdf_collection_poll,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/Art/ (e.g. Dimcirui/ShinanoPB)",
        default="",
    )
    generate_mipmaps: bpy.props.BoolProperty(
        name="Generate MipMaps",
        default=True,
    )
    materials:       bpy.props.CollectionProperty(type=MdfTexMaterialItem)
    materials_index: bpy.props.IntProperty()
    clipboard_json:  bpy.props.StringProperty(default="")


# ── Operators ─────────────────────────────────────────────────────────────────

class MHWS_OT_MdfTexRefresh(bpy.types.Operator):
    """Refresh material list from the selected MDF collection"""
    bl_idname = "mhws.mdf_tex_refresh"
    bl_label  = "Refresh"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        col = settings.mdf_collection
        if not col:
            self.report({'ERROR'}, "请先选择 MDF 集合")
            return {'CANCELLED'}

        # Preserve existing user data keyed by material name
        saved = {}
        for m in settings.materials:
            saved[m.material_name] = {
                'pbr':      {pt: getattr(m.pbr, pt) for pt in PBR_TYPES},
                'pbr_chs':  {pt: getattr(m.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
                'pbr_inv':  {pt: getattr(m.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
                'slots':    {s.texture_type: (s.mode, s.direct_image) for s in m.slots},
            }

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

            prev = saved.get(mat_data.materialName, {})

            prev_pbr = prev.get('pbr', {})
            for pt in PBR_TYPES:
                setattr(item.pbr, pt, prev_pbr.get(pt, ''))
            prev_chs = prev.get('pbr_chs', {})
            for pt in PBR_CHANNEL_SELECTABLE:
                setattr(item.pbr, f"{pt}_ch", prev_chs.get(pt, 'R'))
            prev_inv = prev.get('pbr_inv', {})
            for pt in PBR_CHANNEL_SELECTABLE:
                setattr(item.pbr, f"{pt}_inv", prev_inv.get(pt, False))

            prev_slots = prev.get('slots', {})
            for binding in mat_data.textureBindingList_items:
                slot               = item.slots.add()
                slot.texture_type  = binding.textureType
                slot.original_path = binding.path
                if binding.textureType in prev_slots:
                    slot.mode, slot.direct_image = prev_slots[binding.textureType]
                elif _is_null_tex(binding.path):
                    slot.mode = 'DEFAULT'
                # else: keep default 'SKIP'
            count += 1

        self.report({'INFO'}, f"已加载 {count} 个材质")
        return {'FINISHED'}


class MHWS_OT_MdfTexPickPBR(bpy.types.Operator):
    """Pick a PBR source image for compose mode"""
    bl_idname = "mhws.mdf_tex_pick_pbr"
    bl_label  = "Pick Image"
    bl_options = {'INTERNAL'}

    mat_index: bpy.props.IntProperty()
    pbr_type:  bpy.props.StringProperty()

    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, self.filepath)
        return {'FINISHED'}


class MHWS_OT_MdfTexPickDirect(bpy.types.Operator):
    """Pick a pre-packed image for direct mode"""
    bl_idname = "mhws.mdf_tex_pick_direct"
    bl_label  = "Pick Image"
    bl_options = {'INTERNAL'}

    mat_index:  bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = self.filepath
                slots[self.slot_index].mode = 'DIRECT'
        return {'FINISHED'}


class MHWS_OT_MdfTexClearPBR(bpy.types.Operator):
    """Clear a PBR source image"""
    bl_idname = "mhws.mdf_tex_clear_pbr"
    bl_label  = "Clear"
    bl_options = {'INTERNAL'}

    mat_index: bpy.props.IntProperty()
    pbr_type:  bpy.props.StringProperty()

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, '')
        return {'FINISHED'}


class MHWS_OT_MdfTexClearDirect(bpy.types.Operator):
    """Clear a direct image and reset slot to Skip"""
    bl_idname = "mhws.mdf_tex_clear_direct"
    bl_label  = "Clear"
    bl_options = {'INTERNAL'}

    mat_index:  bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = ''
                slots[self.slot_index].mode = 'SKIP'
        return {'FINISHED'}


class MHWS_OT_MdfTexCopyMaterial(bpy.types.Operator):
    """Copy this material's PBR inputs and slot configuration to clipboard"""
    bl_idname = "mhws.mdf_tex_copy_material"
    bl_label  = "Copy"
    bl_options = {'INTERNAL'}

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
        mats = settings.materials
        if not (0 <= self.mat_index < len(mats)):
            return {'CANCELLED'}
        mat = mats[self.mat_index]
        data = {
            'pbr':     {pt: getattr(mat.pbr, pt) for pt in PBR_TYPES},
            'pbr_chs': {pt: getattr(mat.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
            'pbr_inv': {pt: getattr(mat.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
            'slots':   {s.texture_type: {'mode': s.mode, 'direct_image': s.direct_image}
                        for s in mat.slots},
        }
        settings.clipboard_json = json.dumps(data)
        self.report({'INFO'}, f"已复制 {mat.material_name}")
        return {'FINISHED'}


class MHWS_OT_MdfTexPasteMaterial(bpy.types.Operator):
    """Paste clipboard configuration to this material"""
    bl_idname = "mhws.mdf_tex_paste_material"
    bl_label  = "Paste"
    bl_options = {'INTERNAL'}

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = context.scene.mdf_tex_processor
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

        slot_data = data.get('slots', {})
        for slot in mat.slots:
            if slot.texture_type in slot_data:
                sd = slot_data[slot.texture_type]
                slot.mode         = sd.get('mode', 'SKIP')
                slot.direct_image = sd.get('direct_image', '')

        self.report({'INFO'}, f"已粘贴到 {mat.material_name}")
        return {'FINISHED'}


class MHWS_OT_MdfTexProcess(bpy.types.Operator):
    """Process MDF2 texture bindings: compose/convert images and update paths"""
    bl_idname = "mhws.mdf_tex_process"
    bl_label  = "Process"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene    = context.scene
        settings = scene.mdf_tex_processor

        # ── Validate ──
        natives_root = scene.get("mhws_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Mod Root 目录（natives 的上级文件夹）")
            return {'CANCELLED'}

        if not settings.mdf_collection:
            self.report({'ERROR'}, "请先选择 MDF 集合")
            return {'CANCELLED'}

        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, "请填写 Base Path (e.g. Dimcirui/ShinanoPB)")
            return {'CANCELLED'}

        if not settings.materials:
            self.report({'ERROR'}, "请先点击 Refresh 加载材质")
            return {'CANCELLED'}

        # ── Import tex utils ──
        ImageListToDDS, DDSToTex = _import_tex_utils()
        if ImageListToDDS is None or DDSToTex is None:
            self.report({'ERROR'}, "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用")
            return {'CANCELLED'}

        # ── Process ──
        temp_dir = tempfile.mkdtemp(prefix="mhws_tex_")
        export_count = fail_count = skip_count = 0

        try:
            for mat_item in settings.materials:
                mat_obj = settings.mdf_collection.objects.get(mat_item.material_obj_name)
                if mat_obj is None:
                    continue
                mat_data = getattr(mat_obj, 're_mdf_material', None)
                if mat_data is None:
                    continue

                tex_name     = mat_item.material_name
                pbr_paths    = {pt: getattr(mat_item.pbr, pt) for pt in PBR_TYPES}
                pbr_channels = {pt: getattr(mat_item.pbr, f"{pt}_ch")
                                for pt in PBR_CHANNEL_SELECTABLE}
                pbr_inv      = {pt: getattr(mat_item.pbr, f"{pt}_inv")
                                for pt in PBR_CHANNEL_SELECTABLE}

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

                    mdf_path = _make_mdf_path(base_path, tex_name, slot.texture_type)

                    # DEFAULT: write known null texture path, no file conversion
                    if slot.mode == 'DEFAULT':
                        null_rel = NULL_TEX_BY_TYPE.get(slot.texture_type)
                        if null_rel:
                            binding.path = f"natives/STM/{null_rel}"
                            print(f"[MDF Tex] NULL {slot.texture_type}: natives/STM/{null_rel}")
                            export_count += 1
                        else:
                            print(f"[MDF Tex] SKIP (no null tex) {slot.texture_type}")
                            skip_count += 1
                        continue

                    # COMPOSE or DIRECT: need to generate a .tex file
                    if slot.mode == 'COMPOSE':
                        src_img = _compose_channels(
                            slot.texture_type, pbr_paths, pbr_channels, temp_dir, tex_name, pbr_inv)
                        if src_img is None:
                            print(f"[MDF Tex] SKIP compose {slot.texture_type}: no channel map")
                            skip_count += 1
                            continue
                    else:  # DIRECT
                        src_img = bpy.path.abspath(slot.direct_image)
                        if not src_img or not os.path.isfile(src_img):
                            print(f"[MDF Tex] SKIP direct {slot.texture_type}: file not found")
                            skip_count += 1
                            continue

                    dds_fmt  = ('BC7_UNORM_SRGB'
                                if slot.texture_type in SRGB_SLOT_TYPES
                                else 'BC7_UNORM')
                    disk_path = _make_disk_path(
                        natives_root, base_path, tex_name, slot.texture_type)
                    os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                    try:
                        src_lower = src_img.lower()
                        src_name  = os.path.basename(src_img)

                        if '.tex' in src_name.lower():
                            # Source is already a .tex (or .tex.version) file — copy directly
                            shutil.copy2(src_img, disk_path)
                        elif src_lower.endswith('.dds'):
                            # Source is DDS — skip image conversion, go straight to DDSToTex
                            DDSToTex([src_img], MHWS_TEX_VERSION, disk_path)
                        else:
                            # Source is a raster image (PNG/TGA/TIFF) — convert to DDS first
                            dds_stem = os.path.splitext(src_name)[0]
                            dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                            ImageListToDDS([(src_img, dds_fmt)], temp_dir,
                                           settings.generate_mipmaps)
                            if not os.path.isfile(dds_path):
                                raise FileNotFoundError(
                                    f"texconv output not found: {dds_path}")
                            DDSToTex([dds_path], MHWS_TEX_VERSION, disk_path)

                        binding.path = mdf_path
                        print(f"[MDF Tex] OK {slot.texture_type} → {os.path.basename(disk_path)}")
                        export_count += 1

                    except Exception as err:
                        print(f"[MDF Tex] FAIL {slot.texture_type}: {err}")
                        fail_count += 1

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if fail_count > 0:
            self.report({'WARNING'},
                        f"完成: 生成 {export_count}, 失败 {fail_count}, 跳过 {skip_count}")
        else:
            self.report({'INFO'}, f"完成: 生成 {export_count}, 跳过 {skip_count}")
        return {'FINISHED'}


# ── Registration ──────────────────────────────────────────────────────────────

classes = [
    MdfTexPBRInputs,
    MdfTexSlotItem,
    MdfTexMaterialItem,
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


def unregister():
    del bpy.types.Scene.mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
