"""Shared slot resolution: turning one source image into one game .tex.

The processor (existing MDF → replace textures) and the generators (Blender
material → new MDF from preset) start from different places and should keep
separate entry points — "I have the original MDF" and "I am building from
scratch" are genuinely different starting points, and merging them would just
push the difference into UI branches.

What must *not* be duplicated is the tail: given a source image file and a
destination, write the game's .tex.  That block had drifted into seven near
copies:

  - the processor handled .tex passthrough and .dds direct conversion; the
    generators did not, so a .dds source was needlessly decoded and
    re-compressed through texconv
  - MHWI selects three DXGI formats (BC5 for normals), the RE games two
  - MHWI's tex writer takes (dds_paths, out), the RE games' takes
    (dds_paths, version, out)

Callers pass ``dds_to_tex`` already bound to their tex version, which is what
lets one function serve both signatures.
"""

import os
import shutil


def resolve_dds_format(slot_type, srgb_slots, bc5_slots=None):
    """DXGI format name for a slot's texture data.

    sRGB wins over BC5: no slot is both colour data and a two-channel normal
    map, and checking sRGB first matches every existing call site.
    """
    if slot_type in srgb_slots:
        return 'BC7_UNORM_SRGB'
    if bc5_slots and slot_type in bc5_slots:
        return 'BC5_UNORM'
    return 'BC7_UNORM'


def write_slot_tex(src_img, disk_path, temp_dir, *,
                   dds_fmt, generate_mipmaps,
                   image_to_dds, dds_to_tex):
    """Convert one source image into a .tex at ``disk_path``.

    ``src_img``     source file: .tex, .dds, or anything texconv reads
    ``dds_to_tex``  callable (dds_path_list, out_path) -> None, already bound
                    to the caller's tex version
    ``image_to_dds`` callable ([(src, fmt)], out_dir, mipmaps) -> None

    Creates the destination directory.  Raises FileNotFoundError if texconv
    produced nothing, so a silent zero-byte texture cannot reach the game.
    """
    os.makedirs(os.path.dirname(disk_path), exist_ok=True)

    src_name  = os.path.basename(src_img)
    src_lower = src_img.lower()

    # Substring rather than extension match — preserved verbatim from the
    # processor, whose behaviour this function must not change.  It means a
    # source like "foo.texture.png" is copied raw instead of converted; see the
    # note in the commit that introduced this module.
    if '.tex' in src_name.lower():
        shutil.copy2(src_img, disk_path)
        return src_img

    if src_lower.endswith('.dds'):
        dds_to_tex([src_img], disk_path)
        return src_img

    # texconv names its output after the input, in out_dir.  Callers that pull
    # sources from outside temp_dir must stage them under a unique stem first
    # (see slot_sources.stage_source_file) or two slots sharing a basename will
    # collide here under different sRGB flags.
    dds_path = os.path.join(temp_dir, os.path.splitext(src_name)[0] + '.dds')
    image_to_dds([(src_img, dds_fmt)], temp_dir, generate_mipmaps)
    if not os.path.isfile(dds_path):
        raise FileNotFoundError(f"texconv output not found: {dds_path}")
    dds_to_tex([dds_path], disk_path)
    return dds_path
