"""Standalone image -> game .tex converter.

Unlike core/mdf_tex_processor_base.py (which auto-derives DXGI format and disk
path from a known MDF2/MRL3 slot type), this tool lets the user pick the format
and output path manually — for textures with no known slot mapping (CMM, XM,
Detail NM, etc.). One shared Scene singleton + one operator serve all five
games; the only per-game variance (tex version, MHWI's external .tex writer)
is a small lookup keyed by the operator's `game` property.
"""

import bpy
import os
import tempfile
import shutil

from .i18n import T

_CH = {'R': 0, 'G': 1, 'B': 2, 'A': 3}
_CH_ITEMS = [('R', 'R', ''), ('G', 'G', ''), ('B', 'B', ''), ('A', 'A', '')]


def get_src_items(self=None, context=None):
    """Dynamic items= callback so channel-source labels follow the addon's
    own language toggle instead of being fixed at registration time."""
    return [
        ('A', T("core.tex_convert_base.src_image_a"), ''),
        ('B', T("core.tex_convert_base.src_image_b"), ''),
        ('CONST0', T("core.tex_convert_base.src_const0"), ''),
        ('CONST1', T("core.tex_convert_base.src_const1"), ''),
    ]


# Common two entries pinned to top with a use-case hint; the rest have no
# hint. All shown together, no more tiered collapsing.
_FORMAT_COMMON = [
    ('R8G8B8A8_UNORM_SRGB', 'R8G8B8A8_sRGB', ''),
    ('R8G8B8A8_UNORM',      'R8G8B8A8_Linear', ''),
    ('BC3_UNORM_SRGB',      'BC3_sRGB', ''),
    ('BC1_UNORM_SRGB',      'BC1_sRGB', ''),
    ('BC4_UNORM',           'BC4_Linear', ''),
]
_FORMAT_EXTRA = [
    ('BC1_UNORM',           'BC1_Linear', ''),
    ('BC2_UNORM_SRGB',      'BC2_sRGB', ''),
    ('BC2_UNORM',           'BC2_Linear', ''),
    ('BC3_UNORM',           'BC3_Linear', ''),
    ('BC4_SNORM',           'BC4_Signed', ''),
    ('BC5_SNORM',           'BC5_Signed', ''),
    ('BC6H_UF16',           'BC6H_UF16 (HDR)', ''),
    ('BC6H_SF16',           'BC6H_SF16 (HDR)', ''),
    ('R8_UNORM',            'R8_Linear', ''),
    ('A8_UNORM',            'A8', ''),
    ('R8G8_UNORM',          'R8G8_Linear', ''),
    ('B8G8R8A8_UNORM_SRGB', 'B8G8R8A8_sRGB', ''),
    ('B8G8R8A8_UNORM',      'B8G8R8A8_Linear', ''),
]
def get_format_items(self=None, context=None):
    """Dynamic items= callback: the two pinned entries have translatable
    use-case hints, the rest are bare format codes with no hint text."""
    pinned = [
        ('BC7_UNORM_SRGB', T("core.tex_convert_base.format_bc7_srgb"), ''),
        ('BC5_UNORM', T("core.tex_convert_base.format_bc5_linear"), ''),
    ]
    return pinned + _FORMAT_COMMON + _FORMAT_EXTRA

_NORMAL_NAME_HINTS = ('_nm', '_nrm', '_normal', 'normal_')
_COLOR_NAME_HINTS  = ('_alb', '_albd', '_bml', '_diffuse', '_basecolor', '_col', 'albedo')

# .tex container version per game (RE Engine games only; MHWI uses its own
# MRL3-era format written by the external MHW Model Editor addon instead).
_GAME_TEX_VERSION = {
    'MHWS': 241106027,
    'MHRS': 28,
    'RE4':  143221013,
    'RE9':  250813143,
}
_GAME_ITEMS = [
    ('MHWI', 'MHWI', ''), ('MHWS', 'MHWS', ''), ('MHRS', 'MHRS', ''),
    ('RE4', 'RE4', ''), ('RE9', 'RE9', ''),
]


def guess_dxgi_format(filepath):
    """Best-effort DXGI format guess from filename; None if not recognized."""
    stem = os.path.splitext(os.path.basename(filepath))[0].lower()
    if any(h in stem for h in _NORMAL_NAME_HINTS):
        return 'BC5_UNORM'
    if any(h in stem for h in _COLOR_NAME_HINTS):
        return 'BC7_UNORM_SRGB'
    return None


def _on_src_a_update(self, context):
    if not self.src_a:
        return
    guessed = guess_dxgi_format(self.src_a)
    if guessed:
        self.format = guessed
        self.format_guess_ok = True
    else:
        self.format_guess_ok = False


# ── Channel composition (generic 2-source version of mdf_tex_processor_base's
# _compose_channels — that one is keyed by PBR type name, this one by 'A'/'B') ─

def _compose_channels(channel_map, path_a, path_b, out_dir, name_hint):
    """channel_map: {'R': (src_key, ch_idx, invert), ...}
    src_key: 'A' | 'B' | 'CONST0' | 'CONST1'."""
    import numpy as np

    sources = {}
    if path_a and os.path.isfile(path_a):
        sources['A'] = path_a
    if path_b and os.path.isfile(path_b):
        sources['B'] = path_b
    if not sources:
        return None

    raw_imgs = {}
    ref_w = ref_h = 0
    for key, path in sources.items():
        tmp_name = f"__tex_convert_tmp_{key}"
        if tmp_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[tmp_name])
        img = bpy.data.images.load(path, check_existing=False)
        img.name = tmp_name
        img.colorspace_settings.name = 'Non-Color'
        iw, ih = img.size
        if iw > ref_w:
            ref_w, ref_h = iw, ih
        raw_imgs[key] = img

    if ref_w == 0:
        ref_w = ref_h = 1024

    loaded = {}
    for key, img in raw_imgs.items():
        iw, ih = img.size
        if iw != ref_w or ih != ref_h:
            img.scale(ref_w, ref_h)
        loaded[key] = np.array(img.pixels[:], dtype=np.float32).reshape(ref_h, ref_w, 4)
        bpy.data.images.remove(img)

    result = np.zeros((ref_h, ref_w, 4), dtype=np.float32)
    for out_ch, (src_key, ch_idx, invert) in channel_map.items():
        oi = _CH[out_ch]
        if src_key == 'CONST0':
            result[:, :, oi] = 0.0
            continue
        if src_key == 'CONST1':
            result[:, :, oi] = 1.0
            continue
        arr = loaded.get(src_key)
        if arr is None:
            result[:, :, oi] = 0.0
            continue
        data = arr[:, :, ch_idx].copy()
        if invert:
            data = 1.0 - data
        result[:, :, oi] = data

    out_path = os.path.join(out_dir, f"{name_hint}_composed.png")
    tmp_out = "__tex_convert_out"
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


def _import_mhwtex_convert():
    """Locate MHW Model Editor's convertDDSFileToTex — MHWI's .tex container is
    written by that external addon, not by core/tex_file.py (RE Engine only)."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.tex_function'):
            fn = getattr(mod, 'convertDDSFileToTex', None)
            if fn:
                return fn
    if not hasattr(bpy.ops, 'mhw_tex'):
        return None
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            tm = importlib.import_module(f"{pkg}.modules.tex.tex_function")
            fn = getattr(tm, 'convertDDSFileToTex', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


# ── PropertyGroup (single shared Scene singleton) ──────────────────────────────

def get_channel_mode_items(self=None, context=None):
    return [
        ('SINGLE', T("core.tex_convert_base.mode_single"), T("core.tex_convert_base.mode_single_desc")),
        ('RGB_A', T("core.tex_convert_base.mode_rgb_a"), T("core.tex_convert_base.mode_rgb_a_desc")),
        ('RGBA', T("core.tex_convert_base.mode_rgba"), T("core.tex_convert_base.mode_rgba_desc")),
    ]


class TexConvertSettings(bpy.types.PropertyGroup):
    channel_mode: bpy.props.EnumProperty(
        name="Channel Source",
        items=get_channel_mode_items,
    )
    src_a: bpy.props.StringProperty(name="Source Image", subtype='FILE_PATH', update=_on_src_a_update)
    src_a_invert: bpy.props.BoolProperty(name="Invert", default=False)
    src_b: bpy.props.StringProperty(name="Alpha Source", subtype='FILE_PATH')
    src_b_invert: bpy.props.BoolProperty(name="Invert", default=False)

    # SINGLE mode only: overlay a tiled detail normal map onto the source
    # image (blends only the X/Y components, Z is re-derived to keep the
    # result a unit normal — the standard UDN/partial-derivative technique).
    detail_enabled: bpy.props.BoolProperty(name="Detail Normal Map", default=False)
    detail_path: bpy.props.StringProperty(name="Detail Map", subtype='FILE_PATH')
    detail_tiling_x: bpy.props.FloatProperty(name="Tiling X", default=1.0, min=0.01)
    detail_tiling_y: bpy.props.FloatProperty(name="Tiling Y", default=1.0, min=0.01)

    # In RGBA mode each output channel only picks a "source image/constant +
    # source channel"; invert follows the corresponding source image's
    # (A/B) src_a_invert/src_b_invert above, not set per output channel — so
    # future adjustments hang off the source image rather than being
    # duplicated per channel.
    ch_r_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_g_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_b_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_a_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_r_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='R')
    ch_g_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='G')
    ch_b_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='B')
    ch_a_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='A')

    format: bpy.props.EnumProperty(name="Target Format", items=get_format_items)
    format_guess_ok: bpy.props.BoolProperty(default=True)

    generate_mipmaps: bpy.props.BoolProperty(name="Generate Mipmaps", default=True)
    output_path: bpy.props.StringProperty(name="Output Path", subtype='FILE_PATH')


# ── Operators ────────────────────────────────────────────────────────────────

class MT_OT_TexConvertGuessFormat(bpy.types.Operator):
    bl_idname  = "mt.tex_convert_guess_format"
    bl_label   = "Re-guess Format"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.guess_format_desc")

    def execute(self, context):
        settings = context.scene.tex_convert_tool
        if not settings.src_a:
            self.report({'WARNING'}, T("core.tex_convert_base.select_src_image_first"))
            return {'CANCELLED'}
        guessed = guess_dxgi_format(settings.src_a)
        if guessed:
            settings.format = guessed
            settings.format_guess_ok = True
            self.report({'INFO'}, T("core.tex_convert_base.guessed_format").format(fmt=guessed))
        else:
            settings.format_guess_ok = False
            self.report({'WARNING'}, T("core.tex_convert_base.guess_failed"))
        return {'FINISHED'}


class MT_OT_TexConvertDialog(bpy.types.Operator):
    """Convert a single image directly to the target game's .tex texture."""
    bl_idname  = "mt.tex_convert_dialog"
    bl_label   = "Texture Conversion"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.dialog_desc")

    game: bpy.props.EnumProperty(items=_GAME_ITEMS, default='MHWS', options={'HIDDEN'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        s = context.scene.tex_convert_tool

        layout.label(text=f"{T('core.tex_convert_base.dialog_title')} ({self.game})")
        layout.separator()

        layout.prop(s, "channel_mode", expand=True)
        layout.separator()

        fmt_row = layout.row(align=True)
        fmt_row.prop(s, "format", text=T("core.tex_convert_base.format_name"))
        fmt_row.operator("mt.tex_convert_guess_format", text="", icon='FILE_REFRESH')
        if s.src_a and not s.format_guess_ok:
            layout.label(text=T("core.tex_convert_base.guess_fallback_warning"), icon='ERROR')

        layout.separator()

        # Image selection
        if s.channel_mode == 'SINGLE':
            layout.prop(s, "src_a", text=T("core.tex_convert_base.src_a_name"))
        elif s.channel_mode == 'RGB_A':
            layout.prop(s, "src_a", text=T("core.tex_convert_base.rgb_source_label"))
            layout.prop(s, "src_b", text=T("core.tex_convert_base.src_b_name"))
        else:  # RGBA
            layout.prop(s, "src_a", text=T("core.tex_convert_base.src_image_a"))
            layout.prop(s, "src_b", text=T("core.tex_convert_base.src_image_b"))

        # Adjust — hangs off the source image, not the output channel; future
        # brightness/saturation etc. adjustments go here too.
        if s.src_a or (s.src_b and s.channel_mode != 'SINGLE'):
            layout.separator()
            adj_box = layout.box()
            adj_box.label(text=T("core.tex_convert_base.adjust_header"))
            if s.channel_mode == 'RGB_A':
                # src_a is always the RGB source and src_b always the Alpha
                # source in this mode, so the labels can say so directly.
                if s.src_a:
                    adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_rgb_name"))
                if s.src_b:
                    adj_box.prop(s, "src_b_invert", text=T("core.tex_convert_base.invert_alpha_name"))
            elif s.channel_mode == 'RGBA':
                # A single image can feed any mix of destination channels
                # here, so invert is a single flag for the whole image again
                # (not split by RGB vs Alpha, unlike RGB_A above).
                if s.src_a:
                    adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_a_label"))
                if s.src_b:
                    adj_box.prop(s, "src_b_invert", text=T("core.tex_convert_base.invert_b_label"))
            else:  # SINGLE
                adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_name"))
                adj_box.separator()
                adj_box.prop(s, "detail_enabled", text=T("core.tex_convert_base.detail_enabled_name"))
                if s.detail_enabled:
                    adj_box.prop(s, "detail_path", text=T("core.tex_convert_base.detail_map_name"))
                    tile_row = adj_box.row(align=True)
                    tile_row.prop(s, "detail_tiling_x", text=T("core.tex_convert_base.detail_tiling_x_name"))
                    tile_row.prop(s, "detail_tiling_y", text=T("core.tex_convert_base.detail_tiling_y_name"))

        # RGBA channel mapping: only pick source image/constant + source channel
        if s.channel_mode == 'RGBA':
            layout.separator()
            for ch in ('r', 'g', 'b', 'a'):
                row = layout.row(align=True)
                row.label(text=ch.upper())
                row.prop(s, f"ch_{ch}_source", text="")
                row.prop(s, f"ch_{ch}_channel", text="")

        layout.separator()
        layout.prop(s, "generate_mipmaps", text=T("core.tex_convert_base.generate_mipmaps_name"))
        layout.prop(s, "output_path", text=T("core.tex_convert_base.output_path_name"))
        if not s.output_path:
            layout.label(text=T("core.tex_convert_base.output_empty_hint"), icon='INFO')

    def execute(self, context):
        s = context.scene.tex_convert_tool

        src_a = bpy.path.abspath(s.src_a) if s.src_a else ""
        if not src_a or not os.path.isfile(src_a):
            self.report({'ERROR'}, T("core.tex_convert_base.select_src_image_first"))
            return {'CANCELLED'}

        src_b = bpy.path.abspath(s.src_b) if s.src_b else ""

        if s.output_path:
            out_path = bpy.path.abspath(s.output_path)
        else:
            stem = os.path.splitext(src_a)[0]
            ext = '.tex' if self.game == 'MHWI' else f'.tex.{_GAME_TEX_VERSION[self.game]}'
            out_path = stem + ext

        temp_dir = tempfile.mkdtemp(prefix="tex_convert_")

        try:
            if s.channel_mode == 'SINGLE':
                working = src_a
                if s.detail_enabled and s.detail_path:
                    detail_path = bpy.path.abspath(s.detail_path)
                    if os.path.isfile(detail_path):
                        working = _blend_detail_normal(
                            working, detail_path, s.detail_tiling_x, s.detail_tiling_y,
                            temp_dir, "tex_convert_detail")
                        if not working:
                            self.report({'ERROR'}, T("core.tex_convert_base.detail_blend_failed"))
                            return {'CANCELLED'}
                if s.src_a_invert:
                    channel_map = {c: ('A', i, True) for c, i in _CH.items()}
                    png_path = _compose_channels(channel_map, working, "", temp_dir, "tex_convert")
                else:
                    png_path = working
            elif s.channel_mode == 'RGB_A':
                channel_map = {
                    'R': ('A', 0, s.src_a_invert), 'G': ('A', 1, s.src_a_invert),
                    'B': ('A', 2, s.src_a_invert), 'A': ('B', 0, s.src_b_invert),
                }
                png_path = _compose_channels(channel_map, src_a, src_b, temp_dir, "tex_convert")
            else:  # RGBA
                channel_map = {}
                for ch in ('R', 'G', 'B', 'A'):
                    key = ch.lower()
                    src_key = getattr(s, f"ch_{key}_source")
                    invert = (s.src_a_invert if src_key == 'A'
                              else s.src_b_invert if src_key == 'B'
                              else False)
                    channel_map[ch] = (src_key, _CH[getattr(s, f"ch_{key}_channel")], invert)
                png_path = _compose_channels(channel_map, src_a, src_b, temp_dir, "tex_convert")

            if not png_path:
                self.report({'ERROR'}, T("core.tex_convert_base.channel_compose_failed"))
                return {'CANCELLED'}

            from . import texconv_native
            dds_path = texconv_native.convert_to_dds(
                png_path, s.format, temp_dir, generate_mips=s.generate_mipmaps)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            if self.game == 'MHWI':
                fn = _import_mhwtex_convert()
                if fn is None:
                    self.report({'ERROR'}, T("core.tex_convert_base.mhwtex_convert_unavailable"))
                    return {'CANCELLED'}
                fn([dds_path], out_path)
            else:
                from . import tex_file
                tex_file.write_tex_from_dds(dds_path, _GAME_TEX_VERSION[self.game], out_path)

            self.report({'INFO'}, T("core.tex_convert_base.generated").format(name=os.path.basename(out_path)))
            return {'FINISHED'}

        except Exception as err:
            self.report({'ERROR'}, T("core.tex_convert_base.convert_failed").format(err=err))
            return {'CANCELLED'}
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ── Registration ───────────────────────────────────────────────────────────────

classes = [TexConvertSettings, MT_OT_TexConvertGuessFormat, MT_OT_TexConvertDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tex_convert_tool = bpy.props.PointerProperty(type=TexConvertSettings)


def unregister():
    del bpy.types.Scene.tex_convert_tool
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
