"""Operators and menus for the packed shader — the first user-reachable part.

Three entry points, because there are three different moments:

  Shader Editor > Add > MOD Toolkit    building a material from scratch
  Shader Editor sidebar                inspecting/converting the one in front of you
  main panel, next to the generator    converting every material on a selection

The third matters most and is the one most easily forgotten: the real workflow
imports a whole armour set, so nobody is going to open the Shader Editor forty
times.

Conversion never deletes anything.  The previous shader is disconnected from
Material Output and left in place — Blender's undo is reliable, but a user
watching an operator rewire their material needs to see the old nodes are still
there.  Nothing is destroyed, so nothing needs confirming.

Warnings are stored on the group node (``mtk_warnings``) and summarised in the
operator report.  Never a modal dialog: forty materials would mean forty
dialogs.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty

from .compat import MTK_SHADER_AVAILABLE, MIN_VERSION
from .i18n import T
from . import shader_pack
from . import shader_readers


# ── Spec registry ─────────────────────────────────────────────────────────────
# Imported lazily: games/* imports core/*, so a module-level import here would
# make core depend on games and invert the addon's load order.

GAME_ITEMS = [
    ('MHWI', "MHWI (MRL3)", "Monster Hunter World: Iceborne"),
    # MHWS gets one entry per material archetype rather than a single "MHWS"
    # ident: its real .mmtr templates diverge too much by material type (skin
    # vs everything else) to share one slot set without either bloating the
    # panel or silently dropping slots a given material actually needs -- see
    # games/mhws/shader_defs.py's module docstring. This list is also what
    # "Add > MOD Toolkit" and the sidebar's raw add-a-group buttons iterate;
    # the prefab-material convert dialog (MTK_OT_ConvertToPackedShader) has
    # its own dropdown and does not read this list.
    ('MHWS_STANDARD', "MHWS - Standard", "Monster Hunter Wilds: cloth, most armour and character parts"),
    ('MHWS_WEAPON',   "MHWS - Weapon",   "Monster Hunter Wilds: weapon material"),
    ('MHWS_SKIN',     "MHWS - Skin",     "Monster Hunter Wilds: skin material"),
    ('MHWS_HAIR',     "MHWS - Hair",     "Monster Hunter Wilds: hair material"),
    # Basic: MHWILDS's own general-purpose fallback (Base_Equip.mmtr) -- "use
    # this one if you don't know which material to use" (the user's words).
    ('MHWS_BASIC',    "MHWS - Basic",    "Monster Hunter Wilds: general-purpose fallback material"),
    # RE4 similarly gets one entry per archetype rather than a single "RE4"
    # ident, for the same reason: Standard (pbr_body/pbr_cloth's real preset),
    # Hair (pbr_hair's) and Emissive (Eye_EMI's) diverge in base slot,
    # metallic handling and normal-slot packing -- see
    # games/re4/shader_defs.py's module docstring.
    ('RE4_STANDARD',  "RE4 - Standard",  "Resident Evil 4 Remake: body/cloth character materials"),
    ('RE4_HAIR',      "RE4 - Hair",      "Resident Evil 4 Remake: hair material"),
    ('RE4_EMISSIVE',  "RE4 - Emissive",  "Resident Evil 4 Remake: general-purpose emissive material"),
    # MHRS has no cloth/skin/hair split to make -- one general-purpose
    # material covers essentially everything in practice (confirmed by the
    # user) -- so it is a single entry like MHWI, not a family like MHWS/RE4.
    ('MHRS', "MHRS (MDF2)", "Monster Hunter Rise: general-purpose material"),
    # RE9 mirrors RE4's split: Standard/Skin/Hair (different Master Material
    # Path each, from real PBR_Cloth/PBR_Skin/PBR_Hair.json presets) plus a
    # general-purpose Emissive archetype -- see games/re9/shader_defs.py's
    # module docstring.
    ('RE9_STANDARD',  "RE9 - Standard",  "Resident Evil 9: body/cloth character materials"),
    ('RE9_SKIN',      "RE9 - Skin",      "Resident Evil 9: skin material"),
    ('RE9_HAIR',      "RE9 - Hair",      "Resident Evil 9: hair material"),
    ('RE9_EMISSIVE',  "RE9 - Emissive",  "Resident Evil 9: general-purpose emissive material"),
]

#: Every MHWS variant ident -- kept in one place so spec_for()/_resolve_spec()
#: can't drift out of sync with VARIANTS as new archetypes are added.
#: Basic first: it is MHWILDS's own general-purpose fallback ("use this one
#: if you don't know which material to use" -- the user's words), so it is
#: also the prefab dropdown's default (dynamic EnumProperty with no explicit
#: default resolves to index 0 of whatever items() returns -- see
#: _prefab_enum_items, which iterates this tuple's own order).
_MHWS_GAMES = ('MHWS_BASIC', 'MHWS_STANDARD', 'MHWS_WEAPON', 'MHWS_SKIN', 'MHWS_HAIR')

#: Every RE4 variant ident, same reasoning as _MHWS_GAMES.
_RE4_GAMES = ('RE4_STANDARD', 'RE4_HAIR', 'RE4_EMISSIVE')

#: Every RE9 variant ident, same reasoning as _MHWS_GAMES.
_RE9_GAMES = ('RE9_STANDARD', 'RE9_SKIN', 'RE9_HAIR', 'RE9_EMISSIVE')


def spec_for(game):
    if game == 'MHWI':
        from ..games.mhwi.shader_defs import SPEC
        return SPEC
    if game in _MHWS_GAMES:
        from ..games.mhws.shader_defs import VARIANTS
        return VARIANTS[game]
    if game in _RE4_GAMES:
        from ..games.re4.shader_defs import VARIANTS
        return VARIANTS[game]
    if game == 'MHRS':
        from ..games.mhrs.shader_defs import SPEC
        return SPEC
    if game in _RE9_GAMES:
        from ..games.re9.shader_defs import VARIANTS
        return VARIANTS[game]
    raise ValueError(f"no packed shader spec for game {game!r}")


def slot_types_for(spec):
    return [s.name for s in spec.slots]


def _family_for(game):
    """Which _FAMILY_CONFIG entry a game ident belongs to, or None."""
    if game in _MHWS_GAMES:
        return 'MHWS'
    if game in _RE4_GAMES:
        return 'RE4'
    if game in _RE9_GAMES:
        return 'RE9'
    if game == 'MHRS':
        return 'MHRS'
    return None


# ── Prefab / external preset resolution ─────────────────────────────────────
# The "使用插件预制材质" checkbox in MTK_OT_ConvertToPackedShader's dialog picks
# between two different sources for the same decision -- which spec, and which
# MDF preset that spec implies -- rather than two independent axes. This is
# the same mechanism for every family (MHWS, RE4, RE9, MHRS): a per-family
# folder under assets/mdf_presets/, and a per-family classify() that reads an
# externally-picked preset's own declared Texture Bindings to guess which
# spec it matches -- see each games/*/shader_defs.py module docstring for the
# facts each family's classifier is built from, and
# core/mdf_generator_base.py's load_preset_enum_items for the external-preset
# scan itself (the same one the generator dialogs already use, reused as-is
# rather than duplicated).
#
# Which family a given dialog resolves against comes from the operator's own
# `family` property, set explicitly by whichever button invokes it (MHWS's,
# RE4's, RE9's) -- deliberately NOT derived from `game`: resolving a dynamic
# EnumProperty read (self.game) requires Blender to call that property's own
# items() callback to turn the stored index back into a string, so an
# items() callback that read self.game to decide family (an earlier version
# of this) recursed into itself forever and froze Blender on every click of
# "Convert to Packed Shader" -- any caller, not just the family-aware ones,
# since _resolve_spec() and draw()'s old layout.prop(self, 'game') both read
# self.game too. `game` is a plain static EnumProperty again for exactly this
# reason.

def _mhws_gen_game():
    from ..games.mhws.mdf_generator import MHWS_GEN_GAME
    return MHWS_GEN_GAME


def _re4_gen_game():
    from ..games.re4.mdf_generator import RE4_GEN_GAME
    return RE4_GEN_GAME


def _re9_gen_game():
    from ..games.re9.mdf_generator import RE9_GEN_GAME
    return RE9_GEN_GAME


def _mhrs_gen_game():
    from ..games.mhrs.mdf_generator import MHRS_GEN_GAME
    return MHRS_GEN_GAME


def _preset_texture_types(preset_path):
    """{Texture Type, ...} declared in an MDF preset JSON, or None if it
    can't be read."""
    import json
    try:
        with open(preset_path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return {b.get('Texture Type') for b in data.get('Texture Bindings', [])}


def _classify_mhws_preset_spec(preset_path):
    """Which MHWS spec an externally-picked RE Mesh Editor preset corresponds
    to, read from that preset's *own* declared Texture Bindings -- the same
    facts games/mhws/shader_defs.py's five specs were built from, not a
    structural guess: SkinMap/BlendNormalMap only ever appear on skin.json,
    BaseAlphaMap (in place of BaseDielectricMap) only on hair.json, and
    MultiBlend_ALBDMap/MultiBlend_NRMMap only on Character.json (Basic) --
    checked before the Weapon/GpuWind check below, since Basic *also* carries
    Wind_Effect_VolumeMap/GpuWind_MaskMap (Character.json has both) and would
    otherwise misclassify as Weapon. Wind_Effect_VolumeMap/GpuWind_MaskMap
    without MultiBlend narrows it to weapon.json specifically (cloth.json has
    neither). Standard (cloth-shaped) is the default for anything else
    opaque, since it's the more common case (most armour and character
    parts) than Weapon.
    """
    names = _preset_texture_types(preset_path)
    if names is None:
        return 'MHWS_STANDARD'
    if 'BaseAlphaMap' in names:
        return 'MHWS_HAIR'
    if 'SkinMap' in names or 'BlendNormalMap' in names:
        return 'MHWS_SKIN'
    if 'MultiBlend_ALBDMap' in names or 'MultiBlend_NRMMap' in names:
        return 'MHWS_BASIC'
    if 'Wind_Effect_VolumeMap' in names or 'GpuWind_MaskMap' in names:
        return 'MHWS_WEAPON'
    return 'MHWS_STANDARD'


def _classify_re4_preset_spec(preset_path):
    """Which RE4 spec an externally-picked preset corresponds to -- see
    games/re4/shader_defs.py's module docstring for where these facts come
    from: BaseShiftMap only appears on Hair (pbr_hair.json), and
    NormalRoughnessCavityMap/OcclusionMap only appear on Emissive
    (Eye_EMI.json) -- Standard's NormalRoughnessMap has neither."""
    names = _preset_texture_types(preset_path)
    if names is None:
        return 'RE4_STANDARD'
    if 'BaseShiftMap' in names:
        return 'RE4_HAIR'
    if 'NormalRoughnessCavityMap' in names or 'OcclusionMap' in names:
        return 'RE4_EMISSIVE'
    return 'RE4_STANDARD'


def _classify_re9_preset_spec(preset_path):
    """Which RE9 spec an externally-picked preset corresponds to -- see
    games/re9/shader_defs.py's module docstring: BaseShiftMap only appears on
    Hair, SSSCavityOcclusionTranslucentMap only on Skin, and
    NormalRoughnessCavityMap/OcclusionMap only on Emissive."""
    names = _preset_texture_types(preset_path)
    if names is None:
        return 'RE9_STANDARD'
    if 'BaseShiftMap' in names:
        return 'RE9_HAIR'
    if 'SSSCavityOcclusionTranslucentMap' in names:
        return 'RE9_SKIN'
    if 'NormalRoughnessCavityMap' in names or 'OcclusionMap' in names:
        return 'RE9_EMISSIVE'
    return 'RE9_STANDARD'


def _classify_mhrs_preset_spec(preset_path):
    """MHRS has only one archetype -- nothing to classify."""
    return 'MHRS'


#: Per-family config for the prefab/external-preset dialog: which game
#: idents belong to it, its bundled-prefab function to find the RE Mesh
#: Editor Presets/ subfolder name (for external scanning), its
#: assets/mdf_presets/ subfolder (for bundled prefabs) and its
#: preset -> spec classifier.
_FAMILY_CONFIG = {
    'MHWS': {'idents': _MHWS_GAMES, 'folder': 'mhws', 'gen_game': _mhws_gen_game,
             'classify': _classify_mhws_preset_spec},
    'RE4':  {'idents': _RE4_GAMES,  'folder': 're4',  'gen_game': _re4_gen_game,
             'classify': _classify_re4_preset_spec},
    'RE9':  {'idents': _RE9_GAMES,  'folder': 're9',  'gen_game': _re9_gen_game,
             'classify': _classify_re9_preset_spec},
    'MHRS': {'idents': ('MHRS',),   'folder': 'mhrs', 'gen_game': _mhrs_gen_game,
             'classify': _classify_mhrs_preset_spec},
}

#: Per-ident (short label key, tooltip key) for the prefab dropdown --
#: deliberately its own labels rather than GAME_ITEMS' ("MHWS - Standard"):
#: this dropdown is already scoped to one family by `family`, so repeating
#: the game name on every entry is just noise, and the tooltip here can be
#: prefab-specific (slot composition + which real RE Mesh Editor preset it
#: was bundled from) in a way GAME_ITEMS' own cross-game description isn't.
_PREFAB_LABELS = {
    'MHWS_STANDARD': ("core.shader_ops.prefab_standard", "core.shader_ops.prefab_standard_desc"),
    'MHWS_WEAPON':   ("core.shader_ops.prefab_weapon",   "core.shader_ops.prefab_weapon_desc"),
    'MHWS_SKIN':      ("core.shader_ops.prefab_skin",     "core.shader_ops.prefab_skin_desc"),
    'MHWS_HAIR':      ("core.shader_ops.prefab_hair",     "core.shader_ops.prefab_hair_desc"),
    'MHWS_BASIC':     ("core.shader_ops.prefab_basic",    "core.shader_ops.prefab_basic_desc"),
    'RE4_STANDARD':   ("core.shader_ops.prefab_re4_standard",  "core.shader_ops.prefab_re4_standard_desc"),
    'RE4_HAIR':       ("core.shader_ops.prefab_re4_hair",      "core.shader_ops.prefab_re4_hair_desc"),
    'RE4_EMISSIVE':   ("core.shader_ops.prefab_re4_emissive",  "core.shader_ops.prefab_re4_emissive_desc"),
    'RE9_STANDARD':   ("core.shader_ops.prefab_re9_standard",  "core.shader_ops.prefab_re9_standard_desc"),
    'RE9_SKIN':       ("core.shader_ops.prefab_re9_skin",      "core.shader_ops.prefab_re9_skin_desc"),
    'RE9_HAIR':       ("core.shader_ops.prefab_re9_hair",      "core.shader_ops.prefab_re9_hair_desc"),
    'RE9_EMISSIVE':   ("core.shader_ops.prefab_re9_emissive",  "core.shader_ops.prefab_re9_emissive_desc"),
}

_prefab_items_cache = []
_external_items_cache = []


def _prefab_enum_items(self, context):
    """The calling button's own family's bundled prefabs -- values are the
    same idents GAME_ITEMS/VARIANTS already use, not a separate namespace.
    See _PREFAB_LABELS for why labels/descriptions come from their own keys
    rather than GAME_ITEMS'."""
    global _prefab_items_cache
    cfg = _FAMILY_CONFIG.get(self.family)
    idents = cfg['idents'] if cfg else ()
    items = []
    for ident in idents:
        if not spec_for(ident).preset_filename:
            continue
        label_key, desc_key = _PREFAB_LABELS.get(ident, (None, None))
        label = T(label_key) if label_key else ident
        desc = T(desc_key) if desc_key else ""
        items.append((ident, label, desc))
    _prefab_items_cache = items
    return _prefab_items_cache


def _external_preset_enum_items(self, context):
    global _external_items_cache
    from .mdf_generator_base import load_preset_enum_items
    cfg = _FAMILY_CONFIG.get(self.family)
    game_name = cfg['gen_game']() if cfg else _mhws_gen_game()
    _external_items_cache = load_preset_enum_items(game_name)
    return _external_items_cache


def _preset_choice_items(self, context):
    """items= callback for MTK_OT_ConvertToPackedShader.preset_choice -- which
    list it shows switches on the use_prefab checkbox, but it is one property,
    not two: choosing a prefab picks the spec *and* the preset in one step,
    exactly like picking an external preset does via each family's classify()."""
    return (_prefab_enum_items(self, context) if self.use_prefab
            else _external_preset_enum_items(self, context))


def _prefab_preset_path(spec, family):
    """Absolute path to the bundled MDF preset a prefab spec implies."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = _FAMILY_CONFIG.get(family, _FAMILY_CONFIG['MHWS'])['folder']
    return os.path.join(root, "assets", "mdf_presets", folder, spec.preset_filename)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _material_output(node_tree):
    return (next((n for n in node_tree.nodes
                  if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
            or next((n for n in node_tree.nodes
                     if n.type == 'OUTPUT_MATERIAL'), None))


#: Vertical gap left between the shifted-away tree and the converted cluster.
_CLEAR_MARGIN = 400.0
#: Spacing apply_ir uses between the Image Texture nodes it stacks.
_TEX_ROW_STEP = 300.0


def _make_room(tree, x_offset=520.0, rows=12):
    """Shift the existing tree up and return where the new cluster goes.

    The converted node is the one the user now cares about, so it takes the
    space they are already looking at and the old nodes move out of the way —
    rather than the new node being exiled below a tree that can be thousands of
    units tall.

    Material Output stays put: it is the fixed end of every material, the new
    group is about to connect to it, and moving it would drag the one landmark
    the user navigates by.

    Only top-level nodes move.  A node parented to a frame has a location
    relative to that frame, so moving the frame carries its children and moving
    them individually would double the offset.
    """
    nodes = list(tree.nodes)
    if not nodes:
        return (0.0, 0.0)

    outputs = [n for n in nodes if n.type == 'OUTPUT_MATERIAL']
    movable = [n for n in nodes if n not in outputs]
    if not movable:
        out = outputs[0]
        return (out.location[0] - x_offset - 260.0, out.location[1])

    anchor_y = outputs[0].location[1] if outputs else max(
        n.location[1] for n in movable)

    # The cluster hangs *downward* from the anchor -- apply_ir stacks its Image
    # Texture nodes below the group -- and the old tree can already reach far
    # below the anchor. So the shift has to clear both, not a fixed amount: a
    # constant was enough for a shallow tree and overlapped a deep one.
    depth_below_anchor = max(0.0, anchor_y - min(n.location[1] for n in movable))
    cluster_depth = rows * _TEX_ROW_STEP
    shift = depth_below_anchor + cluster_depth + _CLEAR_MARGIN

    for n in movable:
        if getattr(n, 'parent', None) is None:
            n.location = (n.location[0], n.location[1] + shift)

    # Sit just left of Material Output, in the space the old shader occupied.
    if outputs:
        out = outputs[0]
        return (out.location[0] - x_offset - 260.0, out.location[1])
    return (min(n.location[0] for n in movable) + x_offset, anchor_y)


class AlreadyConverted(Exception):
    """The material already has a packed shader; nothing to do."""

    def __init__(self, material, node):
        super().__init__(f"'{material.name}' already uses a packed shader")
        self.material = material
        self.node = node


def convert_material(material, spec):
    """Replace ``material``'s shader with a packed group filled from its content.

    Returns (group_node, MaterialIR).  Raises ValueError when the material has
    no node tree, and AlreadyConverted when one is already in place.

    Converting twice would add a second group reading nothing: the first
    conversion moved the source nodes off Material Output, so there is no longer
    a Principled or a flat tree to read, and the result is an empty shader wired
    over a working one.  A batch over a mixed selection is the normal case, so
    this is reported and skipped rather than treated as an error.
    """
    if not material.use_nodes:
        material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise ValueError(f"'{material.name}' has no node tree")

    from .slot_sources import find_packed_shader_node
    existing = find_packed_shader_node(material)
    if existing is not None:
        raise AlreadyConverted(material, existing)

    # Read before touching anything: the reader walks the very links that are
    # about to be rewired.
    ir = shader_readers.read_material(material, slot_types_for(spec))

    out = _material_output(tree)
    if out is None:
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        out.location = (600.0, 0.0)

    # Move the old tree out of the way and take its place. The upstream
    # importers build very wide trees, so trying to sit beside one always lands
    # on something; and sitting below one leaves the useful node off-screen.
    # Upper bound on the rows apply_ir will stack: every slot plus every PBR
    # input could carry an image.
    rows = len(spec.slots) + len(spec.pbr)
    node = shader_pack.add_group_node(
        tree, spec, location=_make_room(tree, rows=rows))
    shader_pack.apply_ir(node, spec, ir, node_tree=tree)

    surface = out.inputs.get('Surface')
    if surface is not None:
        for link in list(surface.links):
            tree.links.remove(link)
        tree.links.new(node.outputs['BSDF'], surface)

    for n in tree.nodes:
        n.select = False
    node.select = True
    tree.nodes.active = node
    return node, ir


def _read_preset_state(node):
    """(shader_id, preset_path, locked) already stamped on a packed-shader
    node instance, for comparing against a freshly resolved choice."""
    tree = node.node_tree
    shader_id = tree.get(shader_pack.TAG) if tree else None
    return (shader_id, node.get(shader_pack.PRESET_PATH_KEY),
            bool(node.get(shader_pack.PRESET_LOCKED_KEY, False)))


def _stamp_preset(node, preset_path, locked):
    if preset_path is not None:
        node[shader_pack.PRESET_PATH_KEY] = preset_path
    node[shader_pack.PRESET_LOCKED_KEY] = bool(locked)


def _reconvert_in_place(material, spec, old_node):
    """Replace an already-packed material's group instance with a different
    spec, carrying over every socket the two share by name.

    Not a fresh shader_readers.read_material() pass: the *first* conversion
    already moved the original tree off Material Output (see convert_material's
    docstring), so there is nothing left to re-read from except the old group
    instance itself. Copying socket-to-socket instead is not a lossy shortcut
    here -- MHWS's three specs share the entire PBR panel (same tuple object)
    and most slot names (BaseDielectricMap, NormalRoughnessOcclusionMap,
    AlphaTranslucentOcclusionSSSMap, ...), so a name match carries over both
    linked images and typed-in constants exactly, for anything the new spec
    still has a socket for.
    """
    tree = material.node_tree
    new_node = shader_pack.add_group_node(tree, spec, location=old_node.location)

    dropped = []
    for old_sock in old_node.inputs:
        new_sock = new_node.inputs.get(old_sock.name)
        if new_sock is None:
            if old_sock.is_linked:
                dropped.append(old_sock.name)
            continue
        if old_sock.is_linked:
            tree.links.new(old_sock.links[0].from_socket, new_sock)
        else:
            try:
                new_sock.default_value = old_sock.default_value
            except (TypeError, ValueError):
                pass

    out = _material_output(tree)
    if out is not None:
        surface = out.inputs.get('Surface')
        if surface is not None:
            for link in list(surface.links):
                tree.links.remove(link)
            tree.links.new(new_node.outputs['BSDF'], surface)

    tree.nodes.remove(old_node)
    for n in tree.nodes:
        n.select = False
    new_node.select = True
    tree.nodes.active = new_node

    warnings = []
    if dropped:
        warnings.append(
            f"re-converted to a spec without: {', '.join(dropped)} -- the "
            f"images that fed them are still in the node tree, just no "
            f"longer connected to anything")
    new_node.label = f"{spec.group_name} ← {material.name}"
    return new_node, warnings


def convert_or_update_material(material, spec, *, preset_path=None, locked=False):
    """Convert ``material``, or -- if it already carries a packed shader --
    replace it only when the newly resolved (spec, preset) differs from what
    is already stamped on the node.

    Returns (node, warnings, reconverted). Raises AlreadyConverted when the
    resolution is identical to what is already there (matches
    convert_material's plain behaviour for callers, like MHWI's, that never
    pass a preset_path at all: shader_id alone decides then).
    """
    from .slot_sources import find_packed_shader_node
    existing = find_packed_shader_node(material)

    if existing is None:
        node, ir = convert_material(material, spec)
        _stamp_preset(node, preset_path, locked)
        return node, list(ir.warnings), False

    new_state = (spec.shader_id, preset_path, locked)
    if _read_preset_state(existing) == new_state:
        raise AlreadyConverted(material, existing)

    node, warnings = _reconvert_in_place(material, spec, existing)
    _stamp_preset(node, preset_path, locked)
    return node, warnings, True


def _iter_target_materials(context, scope):
    """Materials to act on, de-duplicated, in a stable order."""
    seen, out = set(), []

    def take(mat):
        if mat is not None and mat.name not in seen:
            seen.add(mat.name)
            out.append(mat)

    if scope == 'ACTIVE_MATERIAL':
        obj = context.active_object
        if obj is not None:
            take(obj.active_material)
    elif scope == 'ACTIVE_OBJECT':
        obj = context.active_object
        if obj is not None and obj.type == 'MESH':
            for mat in obj.data.materials:
                take(mat)
    else:  # SELECTED
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                for mat in obj.data.materials:
                    take(mat)
    return out


# ── Operators ─────────────────────────────────────────────────────────────────

class MTK_OT_AddPackedShader(bpy.types.Operator):
    """Add a packed shader group at the cursor"""
    bl_idname  = "mtk.add_packed_shader"
    bl_label   = "Packed Shader"
    bl_options = {'REGISTER', 'UNDO'}

    game: EnumProperty(name="Game", items=GAME_ITEMS, default='MHWI')
    #: True from the Add menu (mouse is over the canvas, so follow it and let the
    #: user place the node).  False from the sidebar, where the mouse is nowhere
    #: near the node view and a modal grab would fling the node somewhere odd.
    at_cursor: BoolProperty(default=True, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (MTK_SHADER_AVAILABLE
                and space is not None
                and getattr(space, 'type', None) == 'NODE_EDITOR'
                and getattr(space, 'tree_type', None) == 'ShaderNodeTree'
                and space.edit_tree is not None)

    @classmethod
    def description(cls, context, properties):
        return T("core.shader_ops.add_desc")

    def invoke(self, context, event):
        if self.at_cursor:
            # Drop it where the mouse is, like Blender's own Add menu entries.
            context.space_data.cursor_location_from_region(
                event.mouse_region_x, event.mouse_region_y)
        return self.execute(context)

    def execute(self, context):
        tree = context.space_data.edit_tree
        try:
            spec = spec_for(self.game)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        location = (tuple(context.space_data.cursor_location) if self.at_cursor
                    else _make_room(tree, x_offset=0.0))

        for n in tree.nodes:
            n.select = False
        node = shader_pack.add_group_node(tree, spec, location=location)
        node.select = True
        tree.nodes.active = node
        if self.at_cursor:
            # Let the user place it, matching use_transform on node.add_node.
            bpy.ops.transform.translate('INVOKE_DEFAULT')
        return {'FINISHED'}


class MTK_OT_ConvertToPackedShader(bpy.types.Operator):
    """Convert materials to the packed shader, keeping the old nodes"""
    bl_idname  = "mtk.convert_to_packed_shader"
    bl_label   = "Convert to Packed Shader"
    bl_options = {'REGISTER', 'UNDO'}

    #: A plain static list -- resolving this must never depend on reading
    #: `game` itself (see the "Prefab / external preset resolution" comment
    #: block above for why that recursed and froze Blender).
    game: EnumProperty(name="Game", items=GAME_ITEMS, default='MHWI')
    scope: EnumProperty(
        name="Scope",
        items=[
            ('SELECTED', "Selected objects", "Every material on every selected mesh"),
            ('ACTIVE_OBJECT', "Active object", "Every material on the active mesh"),
            ('ACTIVE_MATERIAL', "Active material", "Only the active material slot"),
        ],
        default='SELECTED',
    )
    #: False for callers that already pin an exact spec via `game` (MHWI's
    #: button, the sidebar's "convert active") -- nothing to choose, so no
    #: dialog. True is the MHWS main-panel button's way of saying "let the
    #: user pick a spec/preset here" without needing `is_property_set`, which
    #: this Blender build's bpy_struct does not support for operator
    #: properties (raises TypeError; confirmed with a throwaway test operator,
    #: not specific to this one).
    show_dialog: BoolProperty(default=True, options={'SKIP_SAVE'})
    use_prefab: BoolProperty(name="Use Prefab", default=True)
    preset_choice: EnumProperty(name="Preset", items=_preset_choice_items)
    #: Which _FAMILY_CONFIG entry the use_prefab/preset_choice dialog
    #: resolves against (e.g. 'RE4'). Set by the calling button -- MHWS's,
    #: RE4's, RE9's -- alongside show_dialog. Ignored when show_dialog is
    #: False (MHWI's and MHRS's pinned buttons; MHRS has only one archetype,
    #: nothing to choose either way).
    family: EnumProperty(
        name="Family",
        items=[('MHWS', "MHWS", ""), ('RE4', "RE4", ""), ('RE9', "RE9", "")],
        default='MHWS',
    )

    @classmethod
    def poll(cls, context):
        return MTK_SHADER_AVAILABLE

    @classmethod
    def description(cls, context, properties):
        return T("core.shader_ops.convert_desc")

    def invoke(self, context, event):
        if not self.show_dialog:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'use_prefab', text=T("core.shader_ops.use_prefab"))
        layout.prop(self, 'preset_choice', text="")

    def _resolve_spec(self):
        """(spec, preset_path, locked), or raises ValueError with a
        user-facing message."""
        if not self.show_dialog:
            # Pinned callers (MHWI, MHRS): nothing to choose, but a spec
            # with its own bundled prefab still resolves to it automatically
            # -- there is no ambiguity to ask the user about, and doing so
            # lets core.mdf_generator_base pick up the right MDF preset by
            # itself later instead of guessing from the material's name.
            spec = spec_for(self.game)
            if spec.preset_filename:
                return spec, _prefab_preset_path(spec, _family_for(self.game)), True
            return spec, None, False

        cfg = _FAMILY_CONFIG.get(self.family, _FAMILY_CONFIG['MHWS'])

        if self.use_prefab:
            game = self.preset_choice
            if game not in cfg['idents']:
                raise ValueError(T("core.shader_ops.no_preset_selected"))
            spec = spec_for(game)
            return spec, _prefab_preset_path(spec, self.family), True

        preset_path = self.preset_choice
        if not preset_path or preset_path == 'NONE':
            raise ValueError(T("core.shader_ops.no_preset_selected"))
        spec = spec_for(cfg['classify'](preset_path))
        return spec, preset_path, False

    def execute(self, context):
        try:
            spec, preset_path, locked = self._resolve_spec()
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        materials = _iter_target_materials(context, self.scope)
        if not materials:
            self.report({'WARNING'}, T("core.shader_ops.no_materials"))
            return {'CANCELLED'}

        done = failed = reconverted = 0
        warned, skipped = [], []
        for mat in materials:
            try:
                _node, warnings, was_reconverted = convert_or_update_material(
                    mat, spec, preset_path=preset_path, locked=locked)
                done += 1
                if was_reconverted:
                    reconverted += 1
                if warnings:
                    warned.append(mat.name)
                    # Console, not a dialog: forty materials would mean forty
                    # dialogs. The node keeps them for the sidebar to show.
                    print(f"[MTK] {mat.name}: {len(warnings)} warning(s)")
                    for w in warnings:
                        print(f"[MTK]     - {w}")
            except AlreadyConverted:
                skipped.append(mat.name)
                print(f"[MTK] {mat.name}: already a packed shader, left alone")
            except Exception as e:
                failed += 1
                print(f"[MTK] convert failed for '{mat.name}': {e}")
                import traceback
                traceback.print_exc()

        if reconverted:
            print(f"[MTK] {reconverted} material(s) re-converted to a "
                  f"different spec/preset")

        if failed:
            self.report({'WARNING'}, T("core.shader_ops.converted_with_fail").format(
                done=done, failed=failed))
        elif skipped and not done:
            self.report({'INFO'}, T("core.shader_ops.all_already_converted").format(
                skipped=len(skipped)))
        elif skipped:
            self.report({'INFO'}, T("core.shader_ops.converted_some_skipped").format(
                done=done, skipped=len(skipped)))
        elif warned:
            self.report({'WARNING'}, T("core.shader_ops.converted_with_warnings").format(
                done=done, warned=len(warned)))
        else:
            self.report({'INFO'}, T("core.shader_ops.converted").format(done=done))
        return {'FINISHED'}


class MTK_OT_ClearShaderWarnings(bpy.types.Operator):
    """Dismiss the conversion warnings stored on the active node"""
    bl_idname  = "mtk.clear_shader_warnings"
    bl_label   = "Dismiss"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        node = getattr(getattr(context, 'space_data', None), 'edit_tree', None)
        node = node.nodes.active if node else None
        return node is not None and node.get("mtk_warnings")

    def execute(self, context):
        node = context.space_data.edit_tree.nodes.active
        del node["mtk_warnings"]
        return {'FINISHED'}


# ── UI ────────────────────────────────────────────────────────────────────────

class NODE_MT_mtk_packed_shaders(bpy.types.Menu):
    bl_idname = "NODE_MT_mtk_packed_shaders"
    bl_label  = "MOD Toolkit"

    def draw(self, context):
        layout = self.layout
        for ident, label, _desc in GAME_ITEMS:
            layout.operator(MTK_OT_AddPackedShader.bl_idname,
                            text=label).game = ident


class NODE_PT_mtk_packed_shader(bpy.types.Panel):
    """Sidebar panel for the active packed shader node."""
    bl_idname      = "NODE_PT_mtk_packed_shader"
    bl_label       = "MOD Toolkit 着色器"
    bl_space_type  = 'NODE_EDITOR'
    bl_region_type = 'UI'
    #: Its own sidebar tab, not Blender's "Item" — this is addon UI, and mixing
    #: it into the built-in tab makes it look like part of Blender.
    bl_category    = "MOD Toolkit"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (MTK_SHADER_AVAILABLE
                and getattr(space, 'tree_type', None) == 'ShaderNodeTree')

    def draw(self, context):
        layout = self.layout
        layout.label(text=T("core.shader_ops.preview_only"), icon='INFO')

        row = layout.row(align=True)
        # Pins game explicitly: this predates the MHWS prefab dialog and keeps
        # its old behaviour (always MHWI, no dialog) rather than suddenly
        # popping an MHWS-only dialog for whatever material happens to be
        # active. Giving this button its own game-then-dialog flow is future
        # work, not something this change should do as a side effect.
        op = row.operator(MTK_OT_ConvertToPackedShader.bl_idname,
                          text=T("core.shader_ops.convert_active"),
                          icon='NODETREE')
        op.scope = 'ACTIVE_MATERIAL'
        op.game = 'MHWI'
        op.show_dialog = False

        # One add button per registered spec, driven by GAME_ITEMS rather than
        # hardcoded: adding the RE-series spec makes its button appear with no
        # change here.
        col = layout.column(align=True)
        for ident, label, _desc in GAME_ITEMS:
            op = col.operator(
                MTK_OT_AddPackedShader.bl_idname,
                text=T("core.shader_ops.add_shader_named").format(name=label),
                icon='ADD')
            op.game = ident
            op.at_cursor = False

        tree = getattr(context.space_data, 'edit_tree', None)
        node = tree.nodes.active if tree else None
        warnings = node.get("mtk_warnings") if node else None
        if not warnings:
            return

        box = layout.box()
        header = box.row(align=True)
        header.label(text=T("core.shader_ops.warnings_title").format(
            n=len(warnings)), icon='ERROR')
        header.operator(MTK_OT_ClearShaderWarnings.bl_idname, text="", icon='X')
        col = box.column(align=True)
        for w in warnings:
            # Long reader messages: wrap by hand, there is no auto-wrap in a panel.
            for chunk in _wrap(str(w), 56):
                col.label(text=chunk)


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
    if line:
        out.append(line)
    return out or [""]


def _draw_add_menu(self, context):
    self.layout.separator()
    self.layout.menu(NODE_MT_mtk_packed_shaders.bl_idname)


# ── Registration ──────────────────────────────────────────────────────────────

classes = (
    MTK_OT_AddPackedShader,
    MTK_OT_ConvertToPackedShader,
    MTK_OT_ClearShaderWarnings,
    NODE_MT_mtk_packed_shaders,
    NODE_PT_mtk_packed_shader,
)

_menu_attached = False


def register():
    # Hidden rather than made compatible on 3.x: nothing here can degrade
    # gracefully, and hiding costs three lines. See core/compat.py.
    if not MTK_SHADER_AVAILABLE:
        need = '.'.join(str(v) for v in MIN_VERSION['MTK_SHADER'])
        print(f"[MTK] packed shader disabled: needs Blender {need}+")
        return

    for cls in classes:
        bpy.utils.register_class(cls)

    global _menu_attached
    menu = getattr(bpy.types, 'NODE_MT_shader_node_add_all', None)
    if menu is not None:
        menu.append(_draw_add_menu)
        _menu_attached = True
    else:
        # Not fatal: the sidebar and the main panel still work.
        print("[MTK] NODE_MT_shader_node_add_all not found; "
              "Add-menu entry skipped")


def unregister():
    if not MTK_SHADER_AVAILABLE:
        return

    global _menu_attached
    if _menu_attached:
        menu = getattr(bpy.types, 'NODE_MT_shader_node_add_all', None)
        if menu is not None:
            menu.remove(_draw_add_menu)
        _menu_attached = False

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
