"""RE Engine .tex container writer.

Ported from kagenocookie/RE-Engine-Lib's TexFile.cs (the "Modern"/GDeflate header
layout only — every game this addon targets, MHRS/RE4/MHWS/RE9, uses that layout;
the older Legacy layout used by RE7/RE2/DMC5/RE3 is out of scope).

Critical difference from RE Mesh Editor's own tex writer: the DXGI format is
stored here as a raw integer taken directly from the source DDS's DX10 header,
with zero intermediate lookup-table indirection. That indirection (DDS DXGI value
-> format name string -> a *separate* internal format-code table) is where RE Mesh
Editor's pipeline was silently dropping the sRGB tag regardless of the requested
format — this writer structurally can't have that bug since there's only one
representation of the format, end to end.
"""

import struct

from . import dxgi_format as dxgi
from . import gdeflate_native

MIP_HEADER_SIZE = 16
TEX_MAGIC = 0x00584554  # "TEX\0"

# .tex file versions whose mip data must be GDeflate-compressed (per REE-Lib's
# TexSerializerVersion.GDeflate tier).
GDEFLATE_VERSIONS = {241106027, 250813143}  # MHWILDS, RE9

# Modern header (40 bytes): magic, version, width, height, depth, imageCount,
# mipHeaderSize, format, swizzleControl, cubemapMarker, flags,
# swizzleHeightDepth, swizzleWidth, null1, seven, one.
# All five modern-only trailer fields are left at 0 for freshly-built files,
# matching REE-Content-Editor's own from-scratch DDS->tex conversion path.
_HEADER_STRUCT = struct.Struct('<I i h h h B B i i I I B B H H H')

# MipHeader (16 bytes): offset(int64), pitch(int32), size(int32).
_MIP_HEADER_STRUCT = struct.Struct('<q i i')

# CompressedMipHeader (8 bytes): size(int32), offset(int32) -- in that field order.
_COMPRESSED_MIP_HEADER_STRUCT = struct.Struct('<i i')


def _pad_to_256(pitch):
    return ((pitch + 255) // 256) * 256


def _build_uncompressed(dds, tex_version):
    """Build the plain (pre-GDeflate) .tex byte layout: header + mip table + padded pixel data.
    Returns (header_bytes, mip_table_bytes, mip_records, body_bytes) where mip_records
    is a list of (offset, pitch, size) describing each mip's position within the full file.
    """
    mip_count = len(dds.mips)
    mip_header_size = mip_count * MIP_HEADER_SIZE

    header_bytes = _HEADER_STRUCT.pack(
        TEX_MAGIC, tex_version, dds.width, dds.height, 1,   # depth = 1 (no volume textures)
        1, mip_header_size,                                  # imageCount = 1 (no arrays)
        dds.dxgi_format, -1, 0, 0,                            # format, swizzleControl=-1, cubemapMarker=0, flags=0
        0, 0, 0, 0, 0,                                        # modern trailer fields, all 0
    )
    data_start = len(header_bytes) + mip_header_size

    body = bytearray()
    mip_records = []
    w, h = dds.width, dds.height
    for level in range(mip_count):
        w = max(1, w)
        h = max(1, h)
        raw = dds.mips[level]
        real_pitch = dxgi.get_pitch(dds.dxgi_format, w)
        padded_pitch = _pad_to_256(real_pitch)
        pad = padded_pitch - real_pitch

        mip_start = len(body)
        if pad == 0:
            body += raw
        else:
            for row_start in range(0, len(raw), real_pitch):
                body += raw[row_start:row_start + real_pitch]
                body += b'\x00' * pad
        mip_size = len(body) - mip_start

        mip_records.append((data_start + mip_start, padded_pitch, mip_size))
        w >>= 1
        h >>= 1

    mip_table_bytes = b''.join(_MIP_HEADER_STRUCT.pack(off, pitch, size) for off, pitch, size in mip_records)
    return header_bytes, mip_table_bytes, mip_records, bytes(body)


def _apply_gdeflate(header_bytes, mip_table_bytes, mip_records, body, level=gdeflate_native.BEST_RATIO):
    """Recompress the mip data section with GDeflate, matching REE-Content-Editor's
    TextureLoader.SaveTo: every mip is compressed individually, falling back to storing
    it raw only if compression yields nothing."""
    data_start = mip_records[0][0]  # == len(header_bytes) + len(mip_table_bytes)

    compressed_headers = []
    compressed_chunks = []
    running_offset = 0
    for (off, _pitch, size) in mip_records:
        rel_start = off - data_start
        raw_mip = body[rel_start:rel_start + size]
        try:
            comp = gdeflate_native.compress(raw_mip, level=level)
        except Exception:
            comp = b''
        if not comp:
            comp = raw_mip
        compressed_headers.append((len(comp), running_offset))
        compressed_chunks.append(comp)
        running_offset += len(comp)

    compressed_header_bytes = b''.join(
        _COMPRESSED_MIP_HEADER_STRUCT.pack(size, off) for size, off in compressed_headers
    )
    return header_bytes + mip_table_bytes + compressed_header_bytes + b''.join(compressed_chunks)


def build_tex_from_dds(dds, tex_version):
    """Pack a dds_file.DDSFile into RE Engine .tex container bytes for tex_version."""
    header_bytes, mip_table_bytes, mip_records, body = _build_uncompressed(dds, tex_version)
    if tex_version in GDEFLATE_VERSIONS:
        return _apply_gdeflate(header_bytes, mip_table_bytes, mip_records, body)
    return header_bytes + mip_table_bytes + body


def write_tex_from_dds(dds_filepath, tex_version, out_path):
    """Read a DX10 DDS file and write it out as an RE Engine .tex file."""
    from . import dds_file
    dds = dds_file.read_dds(dds_filepath)
    data = build_tex_from_dds(dds, tex_version)
    with open(out_path, 'wb') as f:
        f.write(data)
    return out_path


def read_tex_to_dds(filepath):
    """Read an RE Engine .tex file's mip 0 into a dds_file.DDSFile.

    Only mip 0 -- the port's texture repack works at full resolution and
    regenerates mips on write, same as the existing compose path
    (mdf_tex_processor_base._compose_channels + write_slot_tex). Inverse of
    build_tex_from_dds, but not a strict mirror of it: build_tex_from_dds
    starts from a dds_file.DDSFile, this starts from raw container bytes, so
    it has to parse the header instead of assuming the layout it just wrote.
    """
    from . import dds_file

    with open(filepath, 'rb') as f:
        data = f.read()

    (magic, version, width, height, _depth, _image_count, mip_header_size,
     dxgi_fmt, _swizzle_control, _cubemap_marker, _flags,
     _swizzle_h, _swizzle_w, _null1, _seven, _one) = _HEADER_STRUCT.unpack_from(data, 0)
    if magic != TEX_MAGIC:
        raise ValueError(f"Not a .tex file: {filepath}")

    header_size = _HEADER_STRUCT.size
    mip_count = mip_header_size // MIP_HEADER_SIZE
    if mip_count < 1:
        raise ValueError(f".tex file has no mips: {filepath}")

    mip0_offset, mip0_pitch, mip0_size = _MIP_HEADER_STRUCT.unpack_from(data, header_size)
    data_start = header_size + mip_header_size

    if version in GDEFLATE_VERSIONS:
        comp_size0, comp_off0 = _COMPRESSED_MIP_HEADER_STRUCT.unpack_from(data, data_start)
        chunk_start = data_start + mip_count * _COMPRESSED_MIP_HEADER_STRUCT.size
        comp_chunk = data[chunk_start + comp_off0: chunk_start + comp_off0 + comp_size0]
        try:
            raw = gdeflate_native.decompress(comp_chunk)
        except Exception:
            # compress() stores a mip raw when GDeflate saves nothing (common for
            # already-compressed BC7 data) -- comp_size0 then equals the raw
            # padded mip size and comp_chunk already *is* the mip.
            raw = comp_chunk
    else:
        raw = data[mip0_offset: mip0_offset + mip0_size]

    # Strip the 256-byte row padding _build_uncompressed added on write.
    real_pitch = dxgi.get_pitch(dxgi_fmt, width)
    if mip0_pitch != real_pitch:
        rows = len(raw) // mip0_pitch
        raw = b''.join(raw[r * mip0_pitch: r * mip0_pitch + real_pitch] for r in range(rows))

    dds = dds_file.DDSFile()
    dds.width = width
    dds.height = height
    dds.mip_count = 1
    dds.dxgi_format = dxgi_fmt
    dds.mips = [raw]
    return dds
