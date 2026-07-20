"""Minimal DDS (DX10-header only) reader.

Reads whatever texconv writes out: legacy DDS_HEADER + DDS_HEADER_DXT10.
Header field layout is the standard, publicly documented Microsoft DDS format
(https://learn.microsoft.com/windows/win32/direct3ddds/dds-header); cross-checked
against kagenocookie/RE-Engine-Lib's DDSFile.cs for field order, not copied from it.
"""

import struct

from . import dxgi_format as dxgi

DDS_MAGIC = 0x20534444          # "DDS "
DX10_FOURCC = 0x30315844         # "DX10"

# DDS_HEADER (124 bytes after the 4-byte magic):
#   dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount (7 x 4B),
#   dwReserved1[11] (44B), DDS_PIXELFORMAT ddspf (32B), dwCaps, dwCaps2, dwCaps3, dwCaps4 (4 x 4B), dwReserved2 (4B)
# 7*4 + 44 + 32 + 4*4 + 4 = 124
_HEADER_STRUCT = struct.Struct('<7I 44s 32s 4I I')
# DDS_HEADER_DXT10 (20 bytes): dxgiFormat, resourceDimension, miscFlag, arraySize, miscFlags2
_DX10_STRUCT = struct.Struct('<5I')


class DDSFile:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.mip_count = 1
        self.dxgi_format = 0     # raw DXGI numeric value
        self.mips = []           # list of bytes, one per mip level (largest first)

    @property
    def is_srgb(self):
        return dxgi.is_srgb(self.dxgi_format)


def read_dds(filepath):
    """Read a DX10-header DDS file. Raises ValueError for anything else (legacy FourCC, cubemaps, arrays)."""
    with open(filepath, 'rb') as f:
        data = f.read()

    magic = struct.unpack_from('<I', data, 0)[0]
    if magic != DDS_MAGIC:
        raise ValueError(f"Not a DDS file: {filepath}")

    (size, flags, height, width, pitch_or_linear, depth, mip_map_count,
     _reserved1, pixel_format, caps1, caps2, caps3, caps4, reserved2) = _HEADER_STRUCT.unpack_from(data, 4)

    pf_size, pf_flags, pf_fourcc, pf_rgbbitcount, pf_rmask, pf_gmask, pf_bmask, pf_amask = \
        struct.unpack('<8I', pixel_format)

    if pf_fourcc != DX10_FOURCC:
        raise ValueError(f"DDS file has no DX10 header (fourCC={pf_fourcc:#x}): {filepath}")

    offset = 4 + _HEADER_STRUCT.size
    dxgi_fmt, resource_dimension, misc_flag, array_size, misc_flags2 = _DX10_STRUCT.unpack_from(data, offset)
    offset += _DX10_STRUCT.size

    if array_size != 1 or (misc_flag & 0x4):  # DDS_RESOURCE_MISC_TEXTURECUBE
        raise ValueError("Texture arrays / cubemaps are not supported")

    dds = DDSFile()
    dds.width = width
    dds.height = height
    dds.mip_count = max(1, mip_map_count)
    dds.dxgi_format = dxgi_fmt

    w, h = width, height
    for _ in range(dds.mip_count):
        w = max(1, w)
        h = max(1, h)
        mip_size = dxgi.get_image_size(dxgi_fmt, w, h)
        dds.mips.append(data[offset:offset + mip_size])
        offset += mip_size
        w >>= 1
        h >>= 1

    return dds
