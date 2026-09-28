"""Repairs for the texture files a mod ships (docs/pre_export_check_plan.md §5.1).

Three problems, each fixed in place under the mod root, product to product --
no backups (user's call: the inputs are converted files, not source art, and
extra files are only more to clean up):

``rewrite_version``
    A texture built for another game (``.tex.28`` where MHWS wants
    ``.tex.241106027``, or a header whose version disagrees with its suffix).
    Only the container changes: every mip is read and re-wrapped, pixels
    untouched (``mdf_port_tex.rewrite_tex_container``).  The wrongly versioned
    file itself is left alone -- it is the user's, not ours.
``resize_pow2``
    A side that is not a power of two: decoded, resized with the texture
    converter's own rule (``tex_convert_base.snap_to_power_of_two``: nearest
    within 15%, otherwise up), re-encoded in the file's original DXGI format.
``convert_foreign``
    A file under a ``.tex`` name that is really a DDS (re-wrapped, lossless)
    or an image (PNG/JPG/BMP/TIFF/TGA, converted as the slot it is bound to wants
    it, so sRGB and linear land right).  Anything else is only reported.
"""

import glob
import os
import shutil
import struct
import tempfile

from . import tex_file
from .dxgi_format import DXGI_FORMAT_NAMES

_MAGICS = (
    (b"TEX\x00", "TEX"),
    (b"DDS ", "DDS"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPG"),
    (b"BM", "BMP"),
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
)
# TGA has no leading magic; a version-2 file ends with this (Photoshop, GIMP
# and Blender all write it).  A version-1 TGA is indistinguishable from noise.
_TGA_FOOTER = b"TRUEVISION-XFILE.\x00"
_EXT = {"DDS": ".dds", "PNG": ".png", "JPG": ".jpg", "BMP": ".bmp", "TIFF": ".tif",
        "TGA": ".tga"}
CONVERTIBLE = set(_EXT)


def sniff(path):
    """What a file really is, by its first bytes (or a TGA's footer), or None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
            for magic, kind in _MAGICS:
                if head.startswith(magic):
                    return kind
            fh.seek(0, os.SEEK_END)
            if fh.tell() >= 18 + len(_TGA_FOOTER):
                fh.seek(-len(_TGA_FOOTER), os.SEEK_END)
                if fh.read() == _TGA_FOOTER:
                    return "TGA"
    except OSError:
        return None
    return None


def header_version(path):
    """The version a .tex header records, or None if it is not a .tex."""
    try:
        with open(path, "rb") as fh:
            magic, version = struct.unpack("<II", fh.read(8))
    except (OSError, struct.error):
        return None
    return version if magic == tex_file.TEX_MAGIC else None


def other_versions(disk_path, version):
    """``[(version, path)]`` of the same texture under other version suffixes."""
    suffix = f".{version}"
    if not disk_path.endswith(suffix):
        return []
    base = disk_path[:-len(suffix)]
    out = []
    for p in glob.glob(glob.escape(base) + ".*"):
        tail = p[len(base) + 1:]
        if tail.isdigit() and int(tail) != version:
            out.append((int(tail), p))
    return sorted(out)


def rewrite_version(src, version, out):
    from .mdf_port_tex import rewrite_tex_container
    tmp = out + ".mtk_tmp"
    rewrite_tex_container(src, version, tmp)
    os.replace(tmp, out)
    return out


def _snap(size):
    from .tex_convert_base import snap_to_power_of_two
    return tuple(snap_to_power_of_two(v) for v in size)


def _dxgi_name(path):
    with open(path, "rb") as fh:
        fields = tex_file._HEADER_STRUCT.unpack(fh.read(tex_file._HEADER_STRUCT.size))
    return DXGI_FORMAT_NAMES.get(fields[7])


def resize_pow2(path, version):
    """Re-encode *path* at power-of-two sides, same DXGI format.  Returns the
    new ``(width, height)``."""
    from .mdf_port_tex import decode_tex_to_png
    from . import texconv_native
    size = tex_file.read_tex_size(path)
    fmt = _dxgi_name(path)
    if size is None or not fmt:
        raise ValueError(f"cannot read {path}")
    target = _snap(size)
    tmp = tempfile.mkdtemp(prefix="mtk_texfix_")
    try:
        png = decode_tex_to_png(path, tmp)
        dds = texconv_native.convert_to_dds(png, fmt, tmp, generate_mips=True, size=target)
        tex_file.write_tex_from_dds(dds, version, path + ".mtk_tmp")
        os.replace(path + ".mtk_tmp", path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return target


def convert_foreign(path, kind, slot_type, version):
    """Turn a DDS or an image sitting under a .tex name into a real .tex for
    *slot_type*.  Also snaps its sides to powers of two, since a renamed source
    image rarely has them."""
    from .mdf_tex_processor_base import _import_tex_utils, SRGB_SLOT_TYPES
    from .slot_resolver import write_slot_tex, resolve_dds_format
    if kind not in CONVERTIBLE:
        raise ValueError(f"not convertible: {kind}")
    tmp = tempfile.mkdtemp(prefix="mtk_texfix_")
    try:
        # A '.tex' anywhere in the name makes write_slot_tex copy it raw; stage
        # it under its real extension first.
        staged = os.path.join(tmp, "source" + _EXT[kind])
        shutil.copyfile(path, staged)
        out = path + ".mtk_tmp"
        if kind == "DDS":
            tex_file.write_tex_from_dds(staged, version, out)
        else:
            image_to_dds, dds_to_tex = _import_tex_utils()
            write_slot_tex(staged, out, tmp,
                           dds_fmt=resolve_dds_format(slot_type, SRGB_SLOT_TYPES),
                           generate_mipmaps=True, image_to_dds=image_to_dds,
                           dds_to_tex=lambda p, o: dds_to_tex(p, version, o))
        os.replace(out, path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    size = tex_file.read_tex_size(path)
    if size and _snap(size) != tuple(size):
        resize_pow2(path, version)
    return path
