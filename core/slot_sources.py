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


def iter_slot_named_image_nodes(node_tree):
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


def find_packed_shader_node(material):
    """The material's packed shader group instance, or None.

    Matched on the tag stored on the group datablock, not on its name — a user
    is free to rename a node or a group, and both upstream importers show what
    happens when identification rests on names (they fight over a global
    ``ColorNodeGroup``).
    """
    if not material or not material.use_nodes or not material.node_tree:
        return None
    # Imported here rather than at module scope: mdf_generator_base imports this
    # module early, and there is no reason to drag the group builder in with it.
    from .shader_pack import TAG
    for node in material.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree is not None:
            if node.node_tree.get(TAG):
                return node
    return None


def _image_node_upstream(socket):
    """The Image Texture feeding ``socket``, through reroutes, or None.

    Deliberately shallow.  A slot socket is meant to take a texture directly —
    that is the entire point of the packed shader — so anything more elaborate
    is a signal that the user wants the generator's own composition or bake path,
    not a guess from here.
    """
    seen = 0
    while socket is not None and socket.is_linked and seen < 8:
        node = socket.links[0].from_node
        if node.type == 'TEX_IMAGE':
            return node
        if node.type == 'REROUTE':
            socket = node.inputs[0]
            seen += 1
            continue
        return None
    return None


def find_shader_slot_images(material, slot_types):
    """Return ``{slot_type: absolute image path}`` read from the packed shader.

    The authoritative source once a material uses the group: the socket a
    texture is plugged into *is* the slot it belongs to, with no naming
    convention in between.  Covers the case find_slot_images cannot — an image
    the user wired by hand, whose node Blender named "Image Texture" (or
    "图像纹理", since it localises new node names).
    """
    node = find_packed_shader_node(material)
    if node is None:
        return {}

    found = {}
    for slot_type in slot_types:
        socket = node.inputs.get(slot_type)
        if socket is None:
            continue
        img_node = _image_node_upstream(socket)
        if img_node is None:
            continue
        path = _resolve_image_path(img_node.image)
        if path:
            found[slot_type] = path
    return found


def find_shader_pbr_map(material):
    """(group node, {pbr_type: socket name}) for a packed shader, else (None, {}).

    The map is read off the group datablock rather than looked up per game, so
    core code stays free of any games/* import.
    """
    node = find_packed_shader_node(material)
    if node is None:
        return None, {}
    from .shader_pack import PBR_MAP_KEY
    raw = node.node_tree.get(PBR_MAP_KEY)
    if raw is None:
        return node, {}
    # Blender hands back an IDPropertyGroup, not a dict.
    try:
        mapping = raw.to_dict()
    except AttributeError:
        mapping = dict(raw)
    return node, {str(k): str(v) for k, v in mapping.items()}


def find_shader_slot_supplies(material):
    """{slot name: [pbr_type, ...]} recorded on the packed shader group."""
    node = find_packed_shader_node(material)
    if node is None:
        return {}
    from .shader_pack import SLOT_SUPPLIES_KEY
    raw = node.node_tree.get(SLOT_SUPPLIES_KEY)
    if raw is None:
        return {}
    try:
        mapping = raw.to_dict()
    except AttributeError:
        mapping = dict(raw)
    return {str(k): [str(x) for x in v] for k, v in mapping.items()}


def shader_pbr_contributions(material):
    """Which PBR-panel inputs the user actually put something into.

    Returns {pbr_type: 'IMAGE' | 'VALUE'}.  'VALUE' means the socket is
    unlinked but no longer at the group's own default, i.e. a number was typed
    in; a socket still at its default contributes nothing and is left out.

    The comparison is against the *group interface's* default rather than a
    table here, so it stays right whatever a spec chooses as its identity.
    """
    node, pbr_map = find_shader_pbr_map(material)
    if node is None or not pbr_map:
        return {}

    iface_defaults = {}
    for item in node.node_tree.interface.items_tree:
        if getattr(item, 'item_type', None) == 'SOCKET' and item.in_out == 'INPUT':
            iface_defaults[item.name] = item.default_value

    out = {}
    for pbr_type, socket_name in pbr_map.items():
        socket = node.inputs.get(socket_name)
        if socket is None:
            continue
        if socket.is_linked:
            out[pbr_type] = 'IMAGE'
            continue
        base = iface_defaults.get(socket_name)
        if base is None:
            continue
        if not _values_equal(socket.default_value, base):
            out[pbr_type] = 'VALUE'
    return out


def shader_slot_contributions(material, slot_names):
    """Which game-slot sockets carry a hand-typed non-default value.

    The SLOT-side counterpart to shader_pbr_contributions: a slot socket left
    unlinked can still have been deliberately changed away from the group's
    own default, the same way a PBR input can. Returns {slot_name: 'VALUE'}
    (a slot socket is texture-only, so there is no 'IMAGE' case here -- that
    is what find_shader_slot_images already covers).
    """
    node = find_packed_shader_node(material)
    if node is None or not slot_names:
        return {}

    iface_defaults = {}
    for item in node.node_tree.interface.items_tree:
        if getattr(item, 'item_type', None) == 'SOCKET' and item.in_out == 'INPUT':
            iface_defaults[item.name] = item.default_value

    out = {}
    for slot_name in slot_names:
        socket = node.inputs.get(slot_name)
        if socket is None or socket.is_linked:
            continue
        base = iface_defaults.get(slot_name)
        if base is None:
            continue
        if not _values_equal(socket.default_value, base):
            out[slot_name] = 'VALUE'
    return out


def _values_equal(a, b, tol=1e-4):
    try:
        av, bv = list(a), list(b)
    except TypeError:
        try:
            return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return a == b
    if len(av) != len(bv):
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(av, bv))


def find_shader_socket_image(material, socket_name):
    """Absolute path of the image feeding a named socket on the packed shader."""
    node = find_packed_shader_node(material)
    if node is None:
        return None
    socket = node.inputs.get(socket_name)
    if socket is None:
        return None
    img_node = _image_node_upstream(socket)
    return _resolve_image_path(img_node.image) if img_node is not None else None


def find_shader_socket_value(material, socket_name, default=None):
    """A named socket's constant value, or ``default`` if it is linked/absent.

    A linked socket has no single value to report, so the caller gets the
    default rather than a number that is not what the shader is actually using.
    """
    node = find_packed_shader_node(material)
    if node is None:
        return default
    socket = node.inputs.get(socket_name)
    if socket is None or socket.is_linked:
        return default
    try:
        return float(socket.default_value)
    except (TypeError, ValueError):
        return default


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

    return {slot: path for slot, (path, _auth)
            in find_slot_sources(material, slot_types).items()}


#: How a slot's source was identified.  SHADER means the user plugged a texture
#: into that slot's socket — an explicit statement, so the generator honours it
#: over its own channel composition.  NAME means a node merely happens to carry
#: the slot's name, which is a convention the importers follow; good enough to
#: recover slots that would otherwise be lost, but not an instruction.
AUTHORITY_SHADER = 'SHADER'
AUTHORITY_NAME   = 'NAME'


def find_slot_sources(material, slot_types):
    """Return ``{slot_type: (path, authority)}`` from every available source."""
    if not material or not material.use_nodes or not material.node_tree:
        return {}
    wanted = set(slot_types)
    if not wanted:
        return {}

    found = {slot: (path, AUTHORITY_SHADER)
             for slot, path in find_shader_slot_images(material, slot_types).items()}

    for key, node in iter_slot_named_image_nodes(material.node_tree):
        if key not in wanted or key in found:
            continue
        path = _resolve_image_path(node.image)
        if path:
            found[key] = (path, AUTHORITY_NAME)
    return found


def stage_source_file(src_path, temp_dir, tex_name, slot_type):
    """Copy ``src_path`` into ``temp_dir`` under a slot-unique stem.

    texconv derives its output filename from the input's, so two slots sourcing
    files that happen to share a basename would collide in temp_dir — and with
    different sRGB flags the second conversion would silently win.  Staging
    under ``<tex_name>_<slot>_direct`` removes the hazard.

    Returns the staged path, ready to hand to slot_resolver.write_slot_tex.
    """
    import shutil

    stem   = f"{tex_name}_{slot_type.lower()}_direct"
    ext    = os.path.splitext(src_path)[1]
    staged = os.path.join(temp_dir, stem + ext)
    shutil.copyfile(src_path, staged)
    return staged
