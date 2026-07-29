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
]


def spec_for(game):
    if game == 'MHWI':
        from ..games.mhwi.shader_defs import SPEC
        return SPEC
    raise ValueError(f"no packed shader spec for game {game!r}")


def slot_types_for(spec):
    return [s.name for s in spec.slots]


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

    @classmethod
    def poll(cls, context):
        return MTK_SHADER_AVAILABLE

    @classmethod
    def description(cls, context, properties):
        return T("core.shader_ops.convert_desc")

    def execute(self, context):
        try:
            spec = spec_for(self.game)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        materials = _iter_target_materials(context, self.scope)
        if not materials:
            self.report({'WARNING'}, T("core.shader_ops.no_materials"))
            return {'CANCELLED'}

        done = failed = 0
        warned, skipped = [], []
        for mat in materials:
            try:
                _node, ir = convert_material(mat, spec)
                done += 1
                if ir.warnings:
                    warned.append(mat.name)
                    # Console, not a dialog: forty materials would mean forty
                    # dialogs. The node keeps them for the sidebar to show.
                    print(f"[MTK] {mat.name}: {ir.summary()}")
                    for w in ir.warnings:
                        print(f"[MTK]     - {w}")
            except AlreadyConverted:
                skipped.append(mat.name)
                print(f"[MTK] {mat.name}: already a packed shader, left alone")
            except Exception as e:
                failed += 1
                print(f"[MTK] convert failed for '{mat.name}': {e}")
                import traceback
                traceback.print_exc()

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
        row.operator(MTK_OT_ConvertToPackedShader.bl_idname,
                     text=T("core.shader_ops.convert_active"),
                     icon='NODETREE').scope = 'ACTIVE_MATERIAL'

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
