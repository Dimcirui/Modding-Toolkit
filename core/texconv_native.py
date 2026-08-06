"""Native PNG/TGA/etc. -> DDS conversion via a bundled texconv DLL (Windows only).

Uses matyalatte's Texconv-Custom-DLL (MIT, wraps Microsoft's MIT-licensed
DirectXTex) bundled directly in assets/bin/texconv/ — no external Blender
addon dependency. Flag logic (-sepalpha, -x2bias) ported from
NSA-Cloud/AsteriskAmpersand's RE-Mesh-Editor texconv.py wrapper (MIT).
"""

import ctypes
import os

from . import dxgi_format as dxgi

_DLL = None


def _bin_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, "assets", "bin", "texconv")


def _ensure_com_initialized():
    """texconv reads images via WIC, which requires COM to be initialized on the
    calling thread. Safe to call repeatedly (COM reference-counts init calls);
    we never pair it with CoUninitialize since the host process (Blender) outlives us."""
    COINIT_APARTMENTTHREADED = 0x2
    ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)


def _load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL
    dll_path = os.path.join(_bin_dir(), "texconv.dll")
    if not os.path.isfile(dll_path):
        raise RuntimeError(f"texconv library not found: {dll_path}")
    _DLL = ctypes.cdll.LoadLibrary(dll_path)
    return _DLL


def unload_dll():
    global _DLL
    if _DLL is None:
        return
    ctypes.windll.kernel32.FreeLibrary(_DLL._handle)
    _DLL = None


def _is_signed(fmt_name):
    return 'SNORM' in fmt_name or 'SF16' in fmt_name


def _run_texconv(dll, file, args, out_dir, verbose=False, allow_slow_codec=False):
    args = list(args)
    if out_dir:
        args += ['-o', out_dir]
        if out_dir not in ('.', '') and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
    args += ['-y', '--', os.path.normpath(file)]

    args_p = (ctypes.c_wchar_p * len(args))(*[ctypes.c_wchar_p(a) for a in args])
    err_buf = ctypes.create_unicode_buffer(512)
    result = dll.texconv(len(args), args_p, verbose, False, allow_slow_codec, err_buf, 512)
    if result != 0:
        raise RuntimeError(err_buf.value)


def convert_to_dds(filepath, dxgi_format_name, out_dir, generate_mips=True,
                    image_filter="CUBIC", verbose=False, allow_slow_codec=False,
                    size=None):
    """Convert an image (PNG/TGA/DDS/etc, whatever texconv itself supports) to a
    DX10-header DDS using the given DXGI format name (e.g. "BC7_UNORM_SRGB").

    sRGB-ness is a *tag only*: the "SRGB" in dxgi_format_name goes into the DDS
    header (and on to the .tex header) to tell the GPU how to decode, but the
    pixel bytes are never gamma-converted — a source PNG is already sRGB-encoded,
    so an extra decode/encode pass would only lose precision or, if it doesn't
    round-trip exactly, darken the result. This deliberately does NOT pass
    texconv's -srgb (TEX_FILTER_SRGB_IN|OUT), matching how kagenocookie's
    REE-Content-Editor converts textures (DirectXTex called with plain
    TexCompressFlags.Default and the sRGB-ness carried only by the format enum).

    Callers must still pass the format matching the texture's *role*, since that
    tag is what the shader honours (see core/mdf_tex_processor_base.py's
    SRGB_SLOT_TYPES for how that's decided per slot).

    ``image_filter`` defaults to CUBIC rather than texconv's own LINEAR default,
    again to match REE-Content-Editor (TexFilterFlags.Cubic|SeparateAlpha) — its
    mips hold detail noticeably better at the lower levels.

    ``size`` is an optional (width, height) to resize to; the game engines
    want powers of two and non-conforming sizes can crash them.

    Returns the path to the resulting .dds file.
    """
    if not dxgi.is_valid_format_name(dxgi_format_name):
        raise ValueError(f"Not a known DXGI format: {dxgi_format_name}")

    _ensure_com_initialized()
    dll = _load_dll()

    args = ['-f', dxgi_format_name, '-sepalpha']  # -sepalpha: without it, alpha gets mangled by mip generation
    if not generate_mips:
        args += ['-m', '1']
    if image_filter:
        args += ['-if', image_filter]
    if size:
        # texconv resizes before compressing, so the block encoder sees the
        # final resolution rather than a downscale of an already-lossy image
        args += ['-w', str(int(size[0])), '-h', str(int(size[1]))]
    if _is_signed(dxgi_format_name):
        args += ['-x2bias']

    _run_texconv(dll, filepath, args, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)

    base_name = os.path.splitext(os.path.basename(filepath))[0] + '.dds'
    return os.path.join(out_dir or '.', base_name)


def convert_to_png(filepath, out_dir, verbose=False, allow_slow_codec=False):
    """Decompress a DDS (any DXGI format, including BC7_UNORM_SRGB) to a plain
    8-bit PNG, always mip 0.

    Mirrors convert_to_dds's own rule in reverse: never gamma-convert, just hand
    back the stored bytes. No -srgb/-srgbi/-srgbo regardless of whether the
    source is tagged _SRGB — an editor (Photoshop, GIMP, ...) that instead
    re-decodes on its own DDS import and re-encodes on PNG export is exactly
    what silently doubles the gamma curve on a round trip through an external
    tool. Keeping this byte-for-byte means feeding the PNG back into
    core/mdf_tex_processor_base.py's PBR compose and re-converting reproduces
    the original DDS exactly.

    Returns the path to the resulting .png file.
    """
    _ensure_com_initialized()
    dll = _load_dll()

    args = ['-f', 'R8G8B8A8_UNORM', '-ft', 'PNG']
    _run_texconv(dll, filepath, args, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)

    base_name = os.path.splitext(os.path.basename(filepath))[0] + '.png'
    return os.path.join(out_dir or '.', base_name)
