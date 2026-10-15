"""Why is this button greyed out?

A ``poll()`` that returns False greys its button out and says nothing, so the
user is left guessing -- Create Chain is disabled in Object Mode, Fix Shape Key
Normals without shape keys, Pre-export Check without an .mdf2 collection, and
none of them told you.  ``Operator.poll_message_set()`` (Blender 3.0+) puts the
reason in the disabled button's tooltip.

Each checker below returns True, or sets the message and returns False, so a
poll reads as a chain of requirements::

    @classmethod
    def poll(cls, context):
        return poll_msg.pose_mode_armature(cls, context) and poll_msg.addon(
            cls, 're_chain', 'create_chain_settings', "RE Chain Editor")

The first failing requirement is the one reported.
"""

from .i18n import T
from .compat import op_available


def deny(cls, key, **fmt):
    """Set *key* (an i18n key) as the reason *cls* is disabled; return False."""
    try:
        cls.poll_message_set(T(key).format(**fmt) if fmt else T(key))
    except Exception:
        pass     # Blender < 3.0 has no poll_message_set
    return False


def active_mesh(cls, context):
    obj = context.active_object
    return (obj is not None and obj.type == 'MESH') or deny(cls, "core.poll.need_active_mesh")


def active_armature(cls, context):
    obj = context.active_object
    return (obj is not None and obj.type == 'ARMATURE') or deny(
        cls, "core.poll.need_active_armature")


def selected_mesh(cls, context):
    return any(o.type == 'MESH' for o in context.selected_objects) or deny(
        cls, "core.poll.need_selected_mesh")


def shape_keys(cls, context):
    """Active mesh with at least one shape key besides Basis."""
    if not active_mesh(cls, context):
        return False
    keys = context.active_object.data.shape_keys
    return (keys is not None and len(keys.key_blocks) > 1) or deny(
        cls, "core.poll.need_shape_keys")


def armature_in_scene(cls, context):
    import bpy
    return any(o.type == 'ARMATURE' for o in bpy.data.objects) or deny(
        cls, "core.poll.need_armature_in_file")


def pose_mode_armature(cls, context):
    if not active_armature(cls, context):
        return False
    return context.mode == 'POSE' or deny(cls, "core.poll.need_pose_mode")


def edit_mode_armature(cls, context):
    if not active_armature(cls, context):
        return False
    return context.mode == 'EDIT_ARMATURE' or deny(cls, "core.poll.need_edit_mode")


def addon(cls, category, op_name, addon_name):
    """The companion operator ``bpy.ops.<category>.<op_name>`` is registered."""
    return op_available(category, op_name) or deny(
        cls, "core.poll.need_addon", addon=addon_name)


def require(cls, ok, key, **fmt):
    """Any other condition: True if *ok*, else report *key*."""
    return bool(ok) or deny(cls, key, **fmt)
