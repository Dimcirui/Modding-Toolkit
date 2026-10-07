"""Minimal uncompressed 32-bit TGA writer, used as the staging format handed to
texconv.

Why this exists
---------------
A composed slot used to reach texconv as a PNG: ``bpy.data.images.new`` +
``Image.save()`` on the Blender side, WIC decode on texconv's side.  Both ends
of that are a full zlib pass over a buffer that only ever needed to survive one
hop between two processes' worth of code in the same process -- the file is
created and consumed within the same call.  For a 4K slot that is two of the
most expensive things in the whole convert, spent entirely on a handoff.

TGA is the cheapest thing texconv reads that is also lossless: an 18-byte header
followed by raw pixels, so writing it is one ``ndarray.tofile`` and reading it
costs texconv a ``memcpy``.  It is still 8 bits per channel, exactly like the PNG
it replaces, so the bytes that reach the block compressor are unchanged -- the
resulting .tex should be byte-identical, and that is the test to run after
touching anything here.

Why not DDS, which would skip texconv's decode entirely
-------------------------------------------------------
``slot_resolver.write_slot_tex`` dispatches on the source extension, and a
``.dds`` source takes the *passthrough* branch -- straight to ``dds_to_tex``, no
compression.  Staging as DDS would therefore silently ship uncompressed RGBA8
textures to the game: right pixels, no error, several times the size.  TGA has no
such branch and flows through the normal texconv path.

TGA also carries no colour-space metadata at all, so
``texconv_native._sanitize_png_color_metadata`` degrades to the no-op it already
returns for non-PNG input, and the whole "Blender tags its PNGs sRGB and
DirectXTex believes it" hazard cannot arise on this path.
"""

import numpy as np

#: id_length, colour_map_type, image_type(2 = uncompressed true-colour),
#: colour map spec (5 bytes, unused), x/y origin, width, height, depth, descriptor.
_HEADER_STRUCT_FMT = '<BBB5s2H2HBB'

#: Low nibble = attribute (alpha) bits; bit 5 set would mean top-down row order.
#: Left clear, i.e. bottom-up -- which is Blender's own pixel order, so the array
#: goes to disk without a flip.
_DESCRIPTOR_BOTTOM_UP_ALPHA8 = 0x08

#: Written into the TGA's image-ID field so the converter can tell our staging files
#: from a TGA the user picked.  It matters for one thing: DirectXTex treats a TGA
#: whose alpha is 0 everywhere as "alpha channel unused" and loads it fully opaque,
#: unless texconv gets ``-tgazeroalpha``.  For an exported TGA that guess is often
#: right; for ours it is always wrong -- an all-zero alpha we wrote is the value we
#: meant (the MHWI snow mask is exactly that, and came out solid white).  So the
#: flag is passed for files carrying this ID and nobody else's.
STAGING_ID = b"Modding-Toolkit staging"


def is_staging_tga(filepath):
    """True if *filepath* is a TGA written by :func:`write_tga_rgba8`."""
    try:
        with open(filepath, 'rb') as f:
            head = f.read(18 + len(STAGING_ID))
    except OSError:
        return False
    return (len(head) == 18 + len(STAGING_ID) and head[0] == len(STAGING_ID)
            and head[18:] == STAGING_ID)


def write_tga_rgba8(filepath, arr):
    """Write an ``(h, w, 4)`` float32 RGBA array in 0..1 as an uncompressed TGA.

    Quantisation matches Blender's own float->byte rule
    (``unit_float_to_uchar_clamp``: clamp, then ``v * 255 + 0.5`` truncated), so
    a buffer routed through here lands on the same bytes it would have had going
    through ``Image.save()``.
    """
    import struct

    h, w = arr.shape[:2]

    header = struct.pack(
        _HEADER_STRUCT_FMT,
        len(STAGING_ID),  # id_length
        0,        # colour_map_type: none
        2,        # image_type: uncompressed true-colour
        b'\0' * 5,
        0, 0,     # x_origin, y_origin
        w, h,
        32,       # bits per pixel
        _DESCRIPTOR_BOTTOM_UP_ALPHA8,
    )

    quantised = (np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    # TGA stores true-colour little-endian, which for 32bpp means B,G,R,A on disk.
    bgra = quantised[:, :, [2, 1, 0, 3]]

    with open(filepath, 'wb') as f:
        f.write(header)
        f.write(STAGING_ID)
        np.ascontiguousarray(bgra).tofile(f)

    return filepath
