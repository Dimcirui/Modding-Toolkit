"""Native PNG/TGA/etc. -> DDS conversion via a bundled texconv DLL.

Uses matyalatte's Texconv-Custom-DLL (MIT, wraps Microsoft's MIT-licensed
DirectXTex) bundled directly in assets/bin/texconv/ — no external Blender
addon dependency. Flag logic (-sepalpha, -srgb, -x2bias) ported from
NSA-Cloud/AsteriskAmpersand's RE-Mesh-Editor texconv.py wrapper (MIT).
"""

import ctypes
import os
import platform

from . import dxgi_format as dxgi

_DLL = None


def _bin_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, "assets", "bin", "texconv")


def _dll_filename():
    system = platform.system()
    if system == 'Windows':
        return "texconv.dll"
    if system == 'Darwin':
        return "libtexconv.dylib"
    if system == 'Linux':
        return "libtexconv.so"
    raise RuntimeError(f"Unsupported OS for texconv: {system}")


def _ensure_com_initialized():
    """texconv reads images via WIC, which requires COM to be initialized on the
    calling thread. Safe to call repeatedly (COM reference-counts init calls);
    we never pair it with CoUninitialize since the host process (Blender) outlives us."""
    if platform.system() != 'Windows':
        return
    COINIT_APARTMENTTHREADED = 0x2
    ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)


def _load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL
    dll_path = os.path.join(_bin_dir(), _dll_filename())
    if not os.path.isfile(dll_path):
        raise RuntimeError(f"texconv library not found: {dll_path}")
    _DLL = ctypes.cdll.LoadLibrary(dll_path)
    return _DLL


def unload_dll():
    global _DLL
    if _DLL is None:
        return
    handle = _DLL._handle
    if platform.system() == 'Windows':
        ctypes.windll.kernel32.FreeLibrary(handle)
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
                    image_filter="LINEAR", verbose=False, allow_slow_codec=False):
    """Convert an image (PNG/TGA/DDS/etc, whatever texconv itself supports) to a
    DX10-header DDS using the given DXGI format name (e.g. "BC7_UNORM_SRGB").

    sRGB-ness of the *output* is entirely controlled by whether dxgi_format_name
    itself contains "SRGB" — callers must pass the format that actually matches
    the source data's color space (see core/mdf_tex_processor_base.py's
    SRGB_SLOT_TYPES for how that's decided per texture role).

    Returns the path to the resulting .dds file.
    """
    if not dxgi.is_valid_format_name(dxgi_format_name):
        raise ValueError(f"Not a known DXGI format: {dxgi_format_name}")

    if (('BC6' in dxgi_format_name or 'BC7' in dxgi_format_name)
            and platform.system() != 'Windows' and not allow_slow_codec):
        raise RuntimeError(
            f"Cannot export {dxgi_format_name} textures on this platform "
            "(no GPU-accelerated compressor outside Windows). Pass allow_slow_codec=True to force it."
        )

    _ensure_com_initialized()
    dll = _load_dll()

    args = ['-f', dxgi_format_name, '-sepalpha']  # -sepalpha: without it, alpha gets mangled by mip generation
    if not generate_mips:
        args += ['-m', '1']
    if image_filter != "LINEAR":
        args += ['-if', image_filter]
    if _is_signed(dxgi_format_name):
        args += ['-x2bias']
    if dxgi.is_srgb(dxgi_format_name):
        args += ['-srgb']

    _run_texconv(dll, filepath, args, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)

    base_name = os.path.splitext(os.path.basename(filepath))[0] + '.dds'
    return os.path.join(out_dir or '.', base_name)
