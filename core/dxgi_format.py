"""DXGI format constants and helpers.

Ported from the public Microsoft DXGI_FORMAT enum (dxgiformat.h) — these are
official, documented numeric values, not proprietary to any third party.
Field-layout details cross-checked against kagenocookie/RE-Engine-Lib's
DDSFile.cs (MIT-compatible reference; ReeLib is BSD/MIT licensed) purely to
confirm correctness, no code copied verbatim.
"""

# Only the subset actually used by this addon's texture pipeline; extend as needed.
DXGI_FORMAT = {
    'UNKNOWN': 0,
    'R8G8B8A8_TYPELESS': 27,
    'R8G8B8A8_UNORM': 28,
    'R8G8B8A8_UNORM_SRGB': 29,
    'R8G8B8A8_UINT': 30,
    'R8G8B8A8_SNORM': 31,
    'R8G8B8A8_SINT': 32,
    'R8G8_UNORM': 49,
    'R8_UNORM': 61,
    'A8_UNORM': 65,
    'BC1_TYPELESS': 70,
    'BC1_UNORM': 71,
    'BC1_UNORM_SRGB': 72,
    'BC2_TYPELESS': 73,
    'BC2_UNORM': 74,
    'BC2_UNORM_SRGB': 75,
    'BC3_TYPELESS': 76,
    'BC3_UNORM': 77,
    'BC3_UNORM_SRGB': 78,
    'BC4_TYPELESS': 79,
    'BC4_UNORM': 80,
    'BC4_SNORM': 81,
    'BC5_TYPELESS': 82,
    'BC5_UNORM': 83,
    'BC5_SNORM': 84,
    'B8G8R8A8_UNORM': 87,
    'B8G8R8X8_UNORM': 88,
    'B8G8R8A8_TYPELESS': 90,
    'B8G8R8A8_UNORM_SRGB': 91,
    'B8G8R8X8_TYPELESS': 92,
    'B8G8R8X8_UNORM_SRGB': 93,
    'BC6H_TYPELESS': 94,
    'BC6H_UF16': 95,
    'BC6H_SF16': 96,
    'BC7_TYPELESS': 97,
    'BC7_UNORM': 98,
    'BC7_UNORM_SRGB': 99,
}
DXGI_FORMAT_NAMES = {v: k for k, v in DXGI_FORMAT.items()}

_BC_BLOCK_SIZE_8 = {
    DXGI_FORMAT['BC1_TYPELESS'], DXGI_FORMAT['BC1_UNORM'], DXGI_FORMAT['BC1_UNORM_SRGB'],
    DXGI_FORMAT['BC4_TYPELESS'], DXGI_FORMAT['BC4_UNORM'], DXGI_FORMAT['BC4_SNORM'],
}
_BC_BLOCK_SIZE_16 = {
    DXGI_FORMAT['BC2_TYPELESS'], DXGI_FORMAT['BC2_UNORM'], DXGI_FORMAT['BC2_UNORM_SRGB'],
    DXGI_FORMAT['BC3_TYPELESS'], DXGI_FORMAT['BC3_UNORM'], DXGI_FORMAT['BC3_UNORM_SRGB'],
    DXGI_FORMAT['BC5_TYPELESS'], DXGI_FORMAT['BC5_UNORM'], DXGI_FORMAT['BC5_SNORM'],
    DXGI_FORMAT['BC6H_TYPELESS'], DXGI_FORMAT['BC6H_UF16'], DXGI_FORMAT['BC6H_SF16'],
    DXGI_FORMAT['BC7_TYPELESS'], DXGI_FORMAT['BC7_UNORM'], DXGI_FORMAT['BC7_UNORM_SRGB'],
}
_BC_FORMATS = _BC_BLOCK_SIZE_8 | _BC_BLOCK_SIZE_16

_UNCOMPRESSED_BITS_PER_PIXEL = {
    DXGI_FORMAT['R8G8B8A8_TYPELESS']: 32,
    DXGI_FORMAT['R8G8B8A8_UNORM']: 32,
    DXGI_FORMAT['R8G8B8A8_UNORM_SRGB']: 32,
    DXGI_FORMAT['R8G8B8A8_UINT']: 32,
    DXGI_FORMAT['R8G8B8A8_SNORM']: 32,
    DXGI_FORMAT['R8G8B8A8_SINT']: 32,
    DXGI_FORMAT['R8G8_UNORM']: 16,
    DXGI_FORMAT['R8_UNORM']: 8,
    DXGI_FORMAT['A8_UNORM']: 8,
    DXGI_FORMAT['B8G8R8A8_UNORM']: 32,
    DXGI_FORMAT['B8G8R8X8_UNORM']: 32,
    DXGI_FORMAT['B8G8R8A8_TYPELESS']: 32,
    DXGI_FORMAT['B8G8R8A8_UNORM_SRGB']: 32,
    DXGI_FORMAT['B8G8R8X8_TYPELESS']: 32,
    DXGI_FORMAT['B8G8R8X8_UNORM_SRGB']: 32,
}


def is_valid_format_name(name):
    return name in DXGI_FORMAT


def is_srgb(fmt):
    """fmt: DXGI format string name or numeric value."""
    name = fmt if isinstance(fmt, str) else DXGI_FORMAT_NAMES.get(fmt, '')
    return 'SRGB' in name


def is_block_compressed(fmt_value):
    return fmt_value in _BC_FORMATS


def get_compressed_block_size(fmt_value):
    """Bytes per 4x4 block."""
    if fmt_value in _BC_BLOCK_SIZE_8:
        return 8
    if fmt_value in _BC_BLOCK_SIZE_16:
        return 16
    raise ValueError(f"Not a BC format: {fmt_value}")


def get_pitch(fmt_value, width):
    if is_block_compressed(fmt_value):
        return ((width + 3) // 4) * get_compressed_block_size(fmt_value)
    return width * (_UNCOMPRESSED_BITS_PER_PIXEL.get(fmt_value, 32) // 8)


def get_image_size(fmt_value, width, height):
    if is_block_compressed(fmt_value):
        return ((width + 3) // 4) * ((height + 3) // 4) * get_compressed_block_size(fmt_value)
    return width * height * (_UNCOMPRESSED_BITS_PER_PIXEL.get(fmt_value, 32) // 8)
