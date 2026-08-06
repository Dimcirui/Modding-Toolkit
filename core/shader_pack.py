"""Packed shader node groups — one node per game material archetype.

Why a node group
----------------
Blender offers three ways to add a "custom shader": OSL (Cycles CPU only, no
EEVEE), a gpu-module draw handler (a viewport overlay, invisible to the
material system and to bakes), and a node group assembled from stock nodes.
Only the last is visible to an exporter, so that is what this is.

What it is for
--------------
The upstream importers build a wide flat tree per material — one Image Texture
node per game slot, then a hand-rolled unpack chain per slot feeding Principled
BSDF.  Pleasant to look at, painful to read back.  This collapses the same
thing into a single node whose *input sockets are named after the game's
texture slots*, so a texture plugs straight into the slot it belongs to and
core.slot_sources reads it back by name.

The internals exist only to make the viewport roughly right.  They are
deliberately not a reproduction of the game's shader.  Slots the preview cannot
meaningfully use (colour masks, fx, fur velocity) still get a socket, because
carrying that data to the exporter is the whole point.

Two panels, one rule
--------------------
"PBR 输入" holds the scattered quantities and is open by default, so someone
who has never heard of MRL3 sees an ordinary PBR node.  "游戏槽位" holds the
packed slots and is closed by default.

An unconnected socket contributes its own default value, exactly like
Principled: there is no "unset" state, because a node group cannot branch on
whether a socket happens to be linked.  The two panels therefore *combine*,
using each quantity's neutral element as the identity:

    quantity      neutral            combiner
    base colour   white              multiply
    alpha         1.0                multiply
    roughness     1.0                multiply
    metallic      0.0                add
    emission      black              add
    normal        (0.5, 0.5, 1.0)    add deviations from flat
    AO            white              multiply into base colour

Multiply for the 1-neutral quantities and add for the 0-neutral ones is what
makes "fill in only the PBR panel" and "connect only the slot panel" both yield
exactly the value the user typed or plugged in.  It also happens to match how
the games themselves apply their scalar material properties — MRL3 multiplies
its roughness map by fRoughness__uiUNorm.

Whether a slot socket is "unset" is *not* expressible here, and must not be:
that axis belongs to the processor's per-slot mode enum (SKIP / DEFAULT /
COMPOSE / DIRECT), which is orthogonal to the value a socket carries.
"""

import bpy
from dataclasses import dataclass, field

from .compat import HAS_SEPARATE_COLOR, MTK_SHADER_AVAILABLE
from .i18n import T

# Custom property on the group datablock; the version-dispatch key.  Named
# lookups beat the fuzzy substring matching used for MMDShaderDev
# (`any(hint in name.lower())`), which breaks the moment a user renames a group.
TAG = "mtk_shader"

# {pbr_type: socket name}, also stored on the group datablock.  The group carries
# its own contract so core code can read a packed shader's PBR inputs without
# importing games/* — which it must not do, since games/* imports core/*.
PBR_MAP_KEY = "mtk_pbr_map"

# {slot name: [pbr_type, ...]} — which quantities each packed slot already
# carries.  Also on the datablock, for the same reason as PBR_MAP_KEY: it lets
# the generator spot a slot and a PBR input both claiming the same quantity.
SLOT_SUPPLIES_KEY = "mtk_slot_supplies"

# A packed slot's alpha arrives on its own socket, named "<SlotType> Alpha", so
# the pair lines up one-to-one with an Image Texture node's Color/Alpha outputs.
ALPHA_SUFFIX = " Alpha"

# Set by MTK_OT_ConvertToPackedShader (core/shader_ops.py) on the group
# *instance* it creates -- not the shared group datablock, since every
# material gets its own instance even when several share one node group.
# Records which MDF preset this conversion resolved to (an absolute path,
# either a bundled prefab or an external RE Mesh Editor preset the user
# picked) and whether that resolution is locked to the bundled prefab
# (True) or just a pre-filled, still user-editable external pick (False).
# core.mdf_generator_base reads these before falling back to its own
# name-based guess_best_preset().
PRESET_PATH_KEY   = "mtk_preset_path"
PRESET_LOCKED_KEY = "mtk_preset_locked"

_COL_STEP = 240
_ROW_STEP = 190

# What NodeTreeInterface.new_socket() actually accepts.  Subtyped variants such
# as NodeSocketFloatFactor are RNA *result* types, not valid arguments — passing
# one raises TypeError.  A factor is a NodeSocketFloat with subtype='FACTOR'.
VALID_SOCKET_TYPES = frozenset({
    'NodeSocketBool', 'NodeSocketVector', 'NodeSocketInt',
    'NodeSocketShader', 'NodeSocketFloat', 'NodeSocketColor',
})


# ── Spec types ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SlotSocket:
    """One packed game texture slot.

    ``name`` must be the exact game slot type — core.slot_sources looks it up
    verbatim, so this string is a data contract, not a label.  Human-readable
    text goes in ``label_key`` and surfaces as the socket tooltip.
    """
    name: str
    label_key: str
    default_color: tuple = (1.0, 1.0, 1.0, 1.0)
    alpha: bool = False
    default_alpha: float = 1.0
    #: False = the preview cannot use this slot; the socket exists so the
    #: exporter can still find the image.
    display: bool = True
    #: PBR quantities this slot already carries, as core.mdf_tex_processor_base
    #: PBR_TYPES names.  apply_ir leaves those PBR sockets at their neutral
    #: values when the slot is populated — otherwise the two panels combine and
    #: the quantity gets applied twice.
    supplies: tuple = ()
    #: True when the socket carries data rather than colour (normals, roughness,
    #: masks).  apply_ir sets the image's colorspace accordingly — see
    #: _set_colorspace for why this is a property of the image, not the socket.
    non_color: bool = True


@dataclass(frozen=True)
class PBRSocket:
    name: str
    socket_type: str
    default: object
    label_key: str
    #: core.mdf_tex_processor_base PBR_TYPES name this socket represents, so
    #: apply_ir can map an IR entry to it.  None for sockets that are not a PBR
    #: quantity (Emission Strength).
    pbr_type: str = None
    #: see SlotSocket.non_color
    non_color: bool = True
    #: Explicit slider range.  See _configure_numeric for why this is never
    #: left to the default.
    min_value: float = None
    max_value: float = None
    #: Float subtype, e.g. 'FACTOR' for a 0..1 slider.  Applied after creation;
    #: new_socket() only takes the six base types in VALID_SOCKET_TYPES.
    subtype: str = None


@dataclass(frozen=True)
class ShaderPackSpec:
    group_name: str
    shader_id: str          # e.g. "mhwi_standard_v1"; stored on the group as TAG
    pbr_panel_key: str
    slot_panel_key: str
    pbr: tuple
    slots: tuple
    wire: object            # callable(ShaderPackBuilder) -> None
    #: Filename (relative to this spec's game's bundled preset directory,
    #: e.g. assets/mdf_presets/mhws/) of the MDF material preset this spec
    #: implies -- choosing this spec at conversion time is choosing this
    #: preset too, so the generator can read it back instead of guessing from
    #: the Blender material's name. None for specs with no such mapping yet.
    preset_filename: str = None


# ── Build helpers handed to a spec's wire() ───────────────────────────────────

class ShaderPackBuilder:
    """Small façade over a node tree, so a spec's wire() reads as a graph.

    Keeps game-specific wiring out of this module while still centralising the
    version-sensitive node choices (Separate/Combine Color).
    """

    def __init__(self, tree, group_in, group_out, principled):
        self.tree   = tree
        self.nodes  = tree.nodes
        self.links  = tree.links
        self.gin    = group_in
        self.gout   = group_out
        self.bsdf   = principled
        self._col   = 1

    # -- access ---------------------------------------------------------------

    def inp(self, name):
        """Group input socket by name.  KeyError here means the spec and the
        wire() disagree — a loud failure at build time is what we want."""
        return self.gin.outputs[name]

    def bsdf_in(self, *names):
        """First Principled input that exists, by name.

        4.0 renamed several sockets ("Emission" -> "Emission Color",
        "Specular" -> "Specular IOR Level").  MTK_SHADER_AVAILABLE already
        requires 4.0+, so this is belt-and-braces for later renames rather than
        back-compatibility.
        """
        for n in names:
            s = self.bsdf.inputs.get(n)
            if s is not None:
                return s
        raise KeyError(f"Principled BSDF has none of {names}")

    # -- graph ----------------------------------------------------------------

    def node(self, idname, *, label=None, col=None, row=0):
        n = self.nodes.new(idname)
        n.location = ((self._col if col is None else col) * _COL_STEP,
                      -row * _ROW_STEP)
        if label:
            n.label = label
        return n

    def link(self, a, b):
        return self.links.new(a, b)

    def column(self, index):
        self._col = index
        return self

    def separate(self, color_socket, **kw):
        n = self.node('ShaderNodeSeparateColor' if HAS_SEPARATE_COLOR
                      else 'ShaderNodeSeparateRGB', **kw)
        self.link(color_socket, n.inputs[0])
        return n

    def combine(self, r, g, b, **kw):
        n = self.node('ShaderNodeCombineColor' if HAS_SEPARATE_COLOR
                      else 'ShaderNodeCombineRGB', **kw)
        for i, v in enumerate((r, g, b)):
            self._feed(n.inputs[i], v)
        return n

    def math(self, operation, a, b=None, *, clamp=False, **kw):
        n = self.node('ShaderNodeMath', **kw)
        n.operation = operation
        n.use_clamp  = clamp
        self._feed(n.inputs[0], a)
        if b is not None:
            self._feed(n.inputs[1], b)
        return n

    def vector_math(self, operation, a, b=None, **kw):
        n = self.node('ShaderNodeVectorMath', **kw)
        n.operation = operation
        self._feed(n.inputs[0], a)
        if b is not None:
            self._feed(n.inputs[1], b)
        return n

    def mix(self, blend_type, a, b, *, fac=1.0, clamp=False, **kw):
        """Colour mix.

        Uses the legacy ShaderNodeMixRGB rather than 4.x's ShaderNodeMix: the
        latter carries several identically-named A/B sockets (one pair per data
        type), so addressing them means hardcoding indices.  Fac/Color1/Color2
        are unambiguous.
        """
        n = self.node('ShaderNodeMixRGB', **kw)
        n.blend_type = blend_type
        n.use_clamp  = clamp
        # fac may be a constant or a socket (an exposed strength control).
        self._feed(n.inputs['Fac'], fac)
        self._feed(n.inputs['Color1'], a)
        self._feed(n.inputs['Color2'], b)
        return n

    def _feed(self, socket, value):
        """Link a socket or assign a constant, whichever ``value`` is."""
        if hasattr(value, 'node'):
            self.link(value, socket)
        else:
            socket.default_value = value


# ── Group construction ────────────────────────────────────────────────────────

def _configure_numeric(sock, lo=None, hi=None, subtype=None):
    """Apply a numeric socket's range and subtype after creation.

    The range is never left to the defaults: NodeTreeInterfaceSocketFloat
    documents both min_value and max_value as 0.0, which would clamp the socket
    to zero.  Setting it costs nothing and removes the question.

    ``subtype`` is best-effort.  The API reference renders the float subtype
    enum as just ('DEFAULT',), which is plainly incomplete, so the accepted
    spelling cannot be confirmed from the docs — and it is cosmetic (a slider
    versus a value field).  A wrong value must not stop the group building.
    """
    if lo is not None:
        sock.min_value = lo
    if hi is not None:
        sock.max_value = hi
    if subtype:
        try:
            sock.subtype = subtype
        except (TypeError, AttributeError) as e:
            print(f"[MTK] socket {sock.name!r}: subtype {subtype!r} rejected "
                  f"({e}); falling back to the default widget")


def _new_socket(iface, name, *, socket_type, description, parent):
    if socket_type not in VALID_SOCKET_TYPES:
        raise ValueError(
            f"socket {name!r}: {socket_type!r} is not accepted by "
            f"new_socket(); use one of {sorted(VALID_SOCKET_TYPES)} and set a "
            f"subtype instead")
    return iface.new_socket(name, description=description, in_out='INPUT',
                            socket_type=socket_type, parent=parent)


def _add_interface(tree, spec):
    iface = tree.interface

    # Output first so it sits above the panels in the interface list.
    iface.new_socket("BSDF", in_out='OUTPUT', socket_type='NodeSocketShader')

    pbr_panel = iface.new_panel(T(spec.pbr_panel_key), default_closed=False)
    for s in spec.pbr:
        sock = _new_socket(iface, s.name, socket_type=s.socket_type,
                           description=T(s.label_key), parent=pbr_panel)
        sock.default_value = s.default
        if s.socket_type in ('NodeSocketFloat', 'NodeSocketInt'):
            _configure_numeric(sock, s.min_value, s.max_value, s.subtype)

    # Closed by default: someone who does not know the game's packing sees a
    # plain PBR node and never has to open this.
    slot_panel = iface.new_panel(T(spec.slot_panel_key), default_closed=True)
    for s in spec.slots:
        sock = _new_socket(iface, s.name, socket_type='NodeSocketColor',
                           description=T(s.label_key), parent=slot_panel)
        sock.default_value = s.default_color
        if s.alpha:
            a = _new_socket(iface, s.name + ALPHA_SUFFIX,
                            socket_type='NodeSocketFloat',
                            description=T(s.label_key), parent=slot_panel)
            a.default_value = s.default_alpha
            _configure_numeric(a, 0.0, 1.0, 'FACTOR')


def _build(tree, spec):
    _add_interface(tree, spec)

    group_in  = tree.nodes.new('NodeGroupInput')
    group_in.location = (-_COL_STEP * 2, 0)
    group_out = tree.nodes.new('NodeGroupOutput')
    principled = tree.nodes.new('ShaderNodeBsdfPrincipled')

    builder = ShaderPackBuilder(tree, group_in, group_out, principled)
    spec.wire(builder)

    # Place the tail after wire() so it lands right of whatever was built.
    right = max((n.location[0] for n in tree.nodes), default=0.0)
    principled.location = (right + _COL_STEP, 0)
    group_out.location  = (right + _COL_STEP * 2.4, 0)
    tree.links.new(principled.outputs['BSDF'], group_out.inputs['BSDF'])
    return tree


def ensure_group(spec):
    """Return the spec's node group, building it on first use.

    Raises RuntimeError when the running Blender cannot express the interface —
    callers gate on compat.MTK_SHADER_AVAILABLE, and operators should poll()
    False rather than reach here.
    """
    if not MTK_SHADER_AVAILABLE:
        raise RuntimeError("packed shader needs node group interface panels")

    existing = bpy.data.node_groups.get(spec.group_name)
    if existing is not None:
        if existing.get(TAG) == spec.shader_id:
            return existing
        # The name is taken by an older revision, or by something not ours.
        # Deliberately not rebuilt in place: interface.clear() would drop every
        # link the user has already made.  Blender uniquifies the new name.  A
        # real v1 -> v2 migration belongs with the first actual v2, where the
        # socket-rename map is known.
        print(f"[MTK] node group '{spec.group_name}' already exists with tag "
              f"{existing.get(TAG)!r}, expected {spec.shader_id!r}; "
              f"building a separate group")

    tree = bpy.data.node_groups.new(spec.group_name, 'ShaderNodeTree')
    tree[TAG] = spec.shader_id
    # Self-describing: which socket carries which PBR quantity.  Lets the
    # generator analyse a packed shader's inputs game-agnostically.
    tree[PBR_MAP_KEY] = {s.pbr_type: s.name for s in spec.pbr if s.pbr_type}
    tree[SLOT_SUPPLIES_KEY] = {s.name: list(s.supplies)
                               for s in spec.slots if s.supplies}
    try:
        return _build(tree, spec)
    except Exception:
        # Never leave a half-built group behind for a user to trip over.
        bpy.data.node_groups.remove(tree)
        raise


def add_group_node(node_tree, spec, location=(0.0, 0.0)):
    """Instance the spec's group into ``node_tree``."""
    group = ensure_group(spec)
    node = node_tree.nodes.new('ShaderNodeGroup')
    node.node_tree = group
    node.location  = location
    node.width     = 240.0
    return node


# ── Filling an instance from a MaterialIR ─────────────────────────────────────

_TEX_COL_STEP = 320
_TEX_ROW_STEP = 300


def apply_ir(node, spec, ir, node_tree=None):
    """Populate a group instance from ``ir``, creating Image Texture nodes.

    Returns the list of nodes created, so a caller can frame or delete them.

    A slot and a PBR socket that carry the same quantity must not both be
    filled: the group *combines* the two panels, so that would apply the value
    twice (base colour would come out as image x image).  Slots win, being the
    lossless source, and every PBR quantity they supply is left at its neutral
    default.
    """
    tree = node_tree or node.id_data
    created = []

    # Which PBR quantities are already covered by a populated slot.
    covered = set()
    for slot in spec.slots:
        if slot.name in ir.slots:
            covered.update(slot.supplies)

    # A warning about a quantity a slot supplies is noise — the reader could not
    # reduce the chain, but nothing was lost.
    ir.drop_warnings_for(covered)

    row = 0
    for slot in spec.slots:
        ref = ir.slots.get(slot.name)
        if ref is None:
            continue
        # name as well as label: Blender localises a new node's name from the UI
        # language ("图像纹理"), so the slot name would otherwise live only on the
        # label.  Setting it matches what both upstream importers do and makes
        # slot_sources.iter_slot_named_image_nodes find it by name rather than
        # relying on the label fallback.
        tex = _add_image_node(tree, node, ref, slot.name, row, name=slot.name,
                              non_color=slot.non_color)
        created.append(tex)
        tree.links.new(tex.outputs['Color'], node.inputs[slot.name])
        if slot.alpha:
            alpha_socket = node.inputs.get(slot.name + ALPHA_SUFFIX)
            if alpha_socket is not None:
                tree.links.new(tex.outputs['Alpha'], alpha_socket)
        row += 1

    for sock in spec.pbr:
        if sock.pbr_type is None or sock.pbr_type in covered:
            continue
        value = ir.pbr.get(sock.pbr_type)
        if value is None:
            continue
        target = node.inputs.get(sock.name)
        if target is None:
            continue

        if hasattr(value, 'image'):
            tex = _add_image_node(tree, node, value, sock.name, row,
                                  non_color=sock.non_color)
            created.append(tex)
            out = tex.outputs['Alpha'] if value.channel == 'A' else tex.outputs['Color']
            tree.links.new(out, target)
            row += 1
        else:
            _assign_default(target, value)

    for name, value in ir.params.items():
        target = node.inputs.get(name)
        if target is not None and not target.is_linked:
            _assign_default(target, value)

    if ir.warnings:
        # Kept on the node so the UI can show them later without re-reading the
        # material, and so they survive a save.
        node["mtk_warnings"] = list(ir.warnings)
    node.label = f"{spec.group_name} ← {ir.source}"
    return created


def _set_colorspace(image, non_color):
    """Point an image at the right colorspace for the socket it feeds.

    This has to be done on the *image*, not the socket: Blender decodes at the
    Image Texture node, so a normal map left on sRGB is already gamma-mangled
    before the group ever sees it — nothing downstream can undo that.  Hence
    "the Normal input requires Non-Color" is really "a normal map is not colour".

    Note this is a datablock property, so it affects every use of the image.  For
    a normal or a roughness map that is correct — it was never colour anywhere.
    """
    want = 'Non-Color' if non_color else 'sRGB'
    try:
        if image.colorspace_settings.name != want:
            image.colorspace_settings.name = want
    except (AttributeError, TypeError) as e:
        # Some image types (or a build without the colorspace) simply refuse.
        print(f"[MTK] could not set {getattr(image, 'name', '?')!r} to {want}: {e}")


def _add_image_node(tree, group_node, ref, label, row, name=None, non_color=True):
    tex = tree.nodes.new('ShaderNodeTexImage')
    tex.image    = ref.image
    tex.label    = label
    _set_colorspace(tex.image, non_color)
    if name:
        # Blender may append .001 on collision; the label still reads cleanly.
        tex.name = name
    tex.location = (group_node.location[0] - _TEX_COL_STEP * 1.4,
                    group_node.location[1] - row * _TEX_ROW_STEP)
    # Channel-packed: the games store unrelated data per channel, so alpha must
    # not be premultiplied into the colour.
    try:
        tex.image.alpha_mode = 'CHANNEL_PACKED'
    except (AttributeError, TypeError):
        pass
    return tex


def _assign_default(socket, value):
    """Write a scalar or tuple into a socket, tolerating width mismatches.

    An IR constant read from a 4-component colour may land on a 3-component
    vector socket, or a float on a colour.  Truncate or broadcast rather than
    raise — a preview value is not worth failing a conversion over.
    """
    try:
        current = socket.default_value
        if hasattr(current, '__len__'):
            n = len(current)
            if hasattr(value, '__len__'):
                vals = list(value)[:n] + [0.0] * max(0, n - len(value))
            else:
                vals = [float(value)] * n
                if n == 4:
                    vals[3] = 1.0
            socket.default_value = vals
        else:
            socket.default_value = (float(value[0]) if hasattr(value, '__len__')
                                    else float(value))
    except (TypeError, ValueError, AttributeError) as e:
        print(f"[MTK] could not set {socket.name!r} to {value!r}: {e}")
