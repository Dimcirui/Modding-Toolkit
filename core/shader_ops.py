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
]

#: Every MHWS variant ident -- kept in one place so spec_for()/_resolve_spec()
#: can't drift out of sync with VARIANTS as new archetypes are added.
_MHWS_GAMES = ('MHWS_STANDARD', 'MHWS_WEAPON', 'MHWS_SKIN', 'MHWS_HAIR')


def spec_for(game):
    if game == 'MHWI':
        from ..games.mhwi.shader_defs import SPEC
        return SPEC
    if game in _MHWS_GAMES:
        from ..games.mhws.shader_defs import VARIANTS
        return VARIANTS[game]
    raise ValueError(f"no packed shader spec for game {game!r}")


def slot_types_for(spec):
    return [s.name for s in spec.slots]


# ── Prefab / external preset resolution (MHWS) ─────────────────────────────────
# The "使用插件预制材质" checkbox in MTK_OT_ConvertToPackedShader's dialog picks
# between two different sources for the same decision -- which spec, and which
# MDF preset that spec implies -- rather than two independent axes. See the
# module docstring in games/mhws/shader_defs.py for why Standard/Skin/Hair
# need to diverge at all, and core/mdf_generator_base.py's load_preset_enum_items
# for the external side of this (same RE Mesh Editor preset scan the generator
# already uses, reused as-is rather than duplicated).

#: RE Mesh Editor's own Presets/ subfolder name for MHWS -- imported lazily
#: from games/* for the same load-order reason as spec_for() below.
def _mhws_gen_game():
    from ..games.mhws.mdf_generator import MHWS_GEN_GAME
    return MHWS_GEN_GAME


_prefab_items_cache = []
_external_items_cache = []


def _prefab_enum_items(self, context):
    """The 4 bundled MHWS prefabs -- values are the same idents GAME_ITEMS/
    VARIANTS already use, not a separate namespace."""
    global _prefab_items_cache
    _prefab_items_cache = [
        ('MHWS_STANDARD', T("core.shader_ops.prefab_standard"),
         T("core.shader_ops.prefab_standard_desc")),
        ('MHWS_WEAPON', T("core.shader_ops.prefab_weapon"),
         T("core.shader_ops.prefab_weapon_desc")),
        ('MHWS_SKIN', T("core.shader_ops.prefab_skin"),
         T("core.shader_ops.prefab_skin_desc")),
        ('MHWS_HAIR', T("core.shader_ops.prefab_hair"),
         T("core.shader_ops.prefab_hair_desc")),
    ]
    return _prefab_items_cache


def _external_preset_enum_items(self, context):
    global _external_items_cache
    from .mdf_generator_base import load_preset_enum_items
    _external_items_cache = load_preset_enum_items(_mhws_gen_game())
    return _external_items_cache


def _preset_choice_items(self, context):
    """items= callback for MTK_OT_ConvertToPackedShader.preset_choice -- which
    list it shows switches on the use_prefab checkbox, but it is one property,
    not two: choosing a prefab picks the spec *and* the preset in one step,
    exactly like picking an external preset does via _classify_preset_spec."""
    return (_prefab_enum_items(self, context) if self.use_prefab
            else _external_preset_enum_items(self, context))


def _prefab_preset_path(spec):
    """Absolute path to the bundled MDF preset a prefab spec implies."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", "mdf_presets", "mhws", spec.preset_filename)


def _classify_preset_spec(preset_path):
    """Which MHWS spec an externally-picked RE Mesh Editor preset corresponds
    to, read from that preset's *own* declared Texture Bindings -- the same
    facts games/mhws/shader_defs.py's four specs were built from, not a
    structural guess: SkinMap/BlendNormalMap only ever appear on skin.json,
    BaseAlphaMap (in place of BaseDielectricMap) only on hair.json, and
    Wind_Effect_VolumeMap/GpuWind_MaskMap only on weapon.json (cloth.json has
    neither), so their presence is as good as reading the preset's own name.
    Standard (cloth-shaped) is the default for anything else opaque, since
    it's the more common case (most armour and character parts) than Weapon.
    """
    import json
    try:
        with open(preset_path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 'MHWS_STANDARD'
    names = {b.get('Texture Type') for b in data.get('Texture Bindings', [])}
    if 'BaseAlphaMap' in names:
        return 'MHWS_HAIR'
    if 'SkinMap' in names or 'BlendNormalMap' in names:
        return 'MHWS_SKIN'
    if 'Wind_Effect_VolumeMap' in names or 'GpuWind_MaskMap' in names:
        return 'MHWS_WEAPON'
    return 'MHWS_STANDARD'


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
            return spec_for(self.game), None, False

        if self.use_prefab:
            game = self.preset_choice
            if game not in _MHWS_GAMES:
                raise ValueError(T("core.shader_ops.no_preset_selected"))
            spec = spec_for(game)
            return spec, _prefab_preset_path(spec), True

        preset_path = self.preset_choice
        if not preset_path or preset_path == 'NONE':
            raise ValueError(T("core.shader_ops.no_preset_selected"))
        spec = spec_for(_classify_preset_spec(preset_path))
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
