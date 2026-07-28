"""Per-slot texture source discovery, straight from a Blender material.

Both RE Mesh Editor and MHW Model Editor name every Image Texture node after
the game texture slot it was loaded from::

    imageNode.name  = textureType     # e.g. "AlbedoMap", "NormalRoughnessOcclusionMap"
    imageNode.label = textureType

That makes the node name an authoritative slot → image mapping, and it survives
things the Principled BSDF route cannot express at all: AO has no Principled
socket (mdf_generator_base defaults it to a solid 1.0) and detail maps have
nowhere to live, so both are silently lost when a material is read through
Principled only.  Reading node names recovers them.

Deliberately *not* done here: interpreting node links or inferring anything
from tree topology.  Upstream's trees are flat, carry unfinished branches and
large blocks of commented-out code, and differ per game and per shader type —
topology is not a stable contract.  Node names are.

Note on scope: the MDF/MRL3 material PropertyGroups (``obj.re_mdf_material``,
``matObj.mhw_mrl3_material``) are a *better* source — they hold the game's own
slot list — but they live on separate Empty objects inside an MDF/MRL3
collection, not on the mesh's Material.  The generator only has the Material,
so it cannot reach them; that source belongs to the processor, which already
has an MDF collection selected.
"""

import os
import bpy

# Source files we can hand to texconv.  .tex is the game's own container and
# would have to be unpacked first — skip rather than fail late.
_USABLE_EXTS = {'.png', '.tga', '.tif', '.tiff', '.dds', '.jpg', '.jpeg', '.bmp'}


def _resolve_image_path(img):
    """Absolute on-disk path for an Image datablock, or None if unusable.

    Filters out the 1x1 placeholders both importers generate for absent
    textures (``bpy.data.images.new(name=f"Missing {texType}", 1, 1)``) — those
    are GENERATED, carry no file, and must never reach the exporter.
    """
    if img is None:
        return None
    if img.source == 'GENERATED':
        return None

    raw = (img.filepath or '').strip()
    if not raw:
        return None

    path = bpy.path.abspath(raw)
    if not os.path.isfile(path):
        return None
    if os.path.splitext(path)[1].lower() not in _USABLE_EXTS:
        return None
    return path


def _iter_slot_named_image_nodes(node_tree):
    """Yield (slot_name, node) for Image Texture nodes named after a slot.

    Blender uniquifies ``node.name`` on collision ("AlbedoMap.001") but leaves
    ``node.label`` alone, so label is checked as a fallback.  Name wins when
    both are present.
    """
    for node in node_tree.nodes:
        if node.type != 'TEX_IMAGE':
            continue
        yield node.name, node
        label = (node.label or '').strip()
        if label and label != node.name:
            yield label, node


def find_slot_images(material, slot_types):
    """Return ``{slot_type: absolute image path}`` for the given slot types.

    A slot is included only when the material has an Image Texture node whose
    name (or label) matches the slot type exactly *and* that node carries a
    real, readable file.

    Array textures are correctly skipped: RE Mesh Editor represents those as a
    pass-through *group* node named after the slot, not an Image Texture, so it
    never matches — there is no single file to export.
    """
    if not material or not material.use_nodes or not material.node_tree:
        return {}

    wanted = set(slot_types)
    if not wanted:
        return {}

    found = {}
    for key, node in _iter_slot_named_image_nodes(material.node_tree):
        if key not in wanted or key in found:
            continue
        path = _resolve_image_path(node.image)
        if path:
            found[key] = path
    return found


def stage_source_file(src_path, temp_dir, tex_name, slot_type):
    """Copy ``src_path`` into ``temp_dir`` under a slot-unique stem.

    texconv derives its output filename from the input's, so two slots sourcing
    files that happen to share a basename would collide in temp_dir — and with
    different sRGB flags the second conversion would silently win.  Staging
    under ``<tex_name>_<slot>_direct`` removes the hazard.

    Returns (staged_path, dds_path).
    """
    import shutil

    stem  = f"{tex_name}_{slot_type.lower()}_direct"
    ext   = os.path.splitext(src_path)[1]
    staged = os.path.join(temp_dir, stem + ext)
    shutil.copyfile(src_path, staged)
    return staged, os.path.join(temp_dir, stem + '.dds')
