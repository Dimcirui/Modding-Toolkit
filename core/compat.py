"""Blender version capability gates.

Single source of truth for "can this Blender build do X".  The addon targets
4.x (4.3 recommended); 3.x is not supported but must not crash on load.

Policy: a feature that cannot degrade gracefully is *hidden*, not made
cross-version compatible — return early from its ``register()`` and have its
panels/operators ``poll()`` False.  Hiding costs three lines and needs no
per-API dual branches; the upstream importers took the compatibility route and
pay for it with a ``bpy.app.version`` check at every socket creation.

Read paths are the exception: they must stay tolerant regardless of gate
state, because a .blend authored in a newer Blender can carry datablocks this
build cannot rebuild.  Fall back and warn — never raise.
"""

import bpy

_V = bpy.app.version

# node_tree.interface.new_panel() — collapsible socket groups in a node group's
# interface.  Without it a packed shader's slot sockets and PBR sockets cannot
# be visually separated, which is the whole point of the layout.
HAS_NODE_PANELS = _V >= (4, 0, 0)

# node_tree.interface (new_socket / items_tree).  Pre-4.0 used the flat
# node_tree.inputs / .outputs collections instead.
HAS_NODE_INTERFACE = _V >= (4, 0, 0)

# ShaderNodeSeparateColor / ShaderNodeCombineColor.  3.3 marked the RGB
# variants legacy.
HAS_SEPARATE_COLOR = _V >= (3, 3, 0)

# ── Feature gates ─────────────────────────────────────────────────────────────

# The packed ("打包") shader node group.
MTK_SHADER_AVAILABLE = HAS_NODE_PANELS and HAS_NODE_INTERFACE

# Minimum Blender version each gate needs, for UI messaging.  Kept as data so
# this module stays free of user-facing copy — that belongs to core.i18n.
MIN_VERSION = {
    'MTK_SHADER': (4, 0, 0),
}


def version_string():
    return ".".join(str(p) for p in _V)
