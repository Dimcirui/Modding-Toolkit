"""Bake an armature's current pose into its rest, carrying the meshes with it.

This exists because ``core/pose_ops._apply_and_rebind()`` cannot be reused for a
cross-game rebuild, and the reason is recorded in
``mesh_port_ops.apply_corrections``' own docstring: that helper bakes the mesh by
running ``bpy.ops.object.convert(target='MESH')``, which applies **every** modifier on
the object, not just the armature.  A subdivision, a mirror, a solidify -- all of them
get flattened into the mesh, and the model is wrecked.  ``mesh_port`` responded by
abandoning pose-and-bake entirely and doing rest-pose edits that provably move no
vertex, which is right for a port whose mesh is already correct.

An MHWI -> MHWS rebuild does not have that luxury: the mesh has to move (different
body proportions, a 29-degree thumb, a 1.05 m origin offset).  So the deformation is
computed here directly instead of being delegated to an operator that overreaches:

* only the armature deformation is applied, other modifiers keep their place in the
  stack untouched,
* shape keys are transformed alongside the base mesh rather than being a reason the
  bake fails (``modifier_apply`` refuses to run on a mesh that has them, which is the
  other obvious route and is a dead end for RE meshes with blend shapes),
* no operator is invoked per mesh, so nothing depends on selection state.

The maths is plain linear blend skinning, the same thing the Armature modifier does::

    S_b   = pose_bone.matrix @ bone.matrix_local.inverted()   # armature space
    v'    = sum_b (w_b * S_b) @ v

with a change of basis either side because vertices live in mesh space and ``S_b``
in armature space.  A vertex whose weights sum to zero is left exactly where it is --
the Armature modifier leaves it alone too, and "helpfully" collapsing it to the origin
is a corruption that only shows up as a stray spike much later.
"""

import bpy
import numpy as np
from mathutils import Matrix


def bound_meshes(arm_obj):
    """Every mesh deformed by *arm_obj*, found through the modifier, not parenting.

    ``find_armature()`` reads the Armature modifier, which is what actually decides
    deformation -- a mesh can be parented to one rig and deformed by another, and it
    is the deforming one that has to be baked.
    """
    return [o for o in bpy.data.objects
            if o.type == 'MESH' and o.find_armature() is arm_obj]


def _skin_matrices(arm_obj, obj):
    """``(V, 4, 4)`` per-vertex transforms in *obj*'s local space, or None.

    None means "no vertex in this mesh is weighted to any bone of this armature",
    which is worth distinguishing from "all identity": the caller can skip the mesh
    entirely instead of rewriting every coordinate with itself.
    """
    bones = arm_obj.pose.bones
    # Vertex group index -> that group's skinning matrix.  Groups naming no bone are
    # left out, so they contribute no weight -- matching the Armature modifier.
    by_group = {}
    for vg in obj.vertex_groups:
        pb = bones.get(vg.name)
        if pb is None:
            continue
        by_group[vg.index] = np.array(
            (pb.matrix @ pb.bone.matrix_local.inverted()), dtype=np.float64)
    if not by_group:
        return None

    n = len(obj.data.vertices)
    acc = np.zeros((n, 4, 4), dtype=np.float64)
    total = np.zeros(n, dtype=np.float64)
    for i, v in enumerate(obj.data.vertices):
        for g in v.groups:
            m = by_group.get(g.group)
            if m is None or g.weight == 0.0:
                continue
            acc[i] += m * g.weight
            total[i] += g.weight

    weighted = total > 1e-12
    if not weighted.any():
        return None
    # Normalise, matching the modifier: weights that do not sum to 1 scale the result
    # rather than shrinking the mesh toward the origin.
    acc[weighted] /= total[weighted, None, None]
    acc[~weighted] = np.eye(4)

    to_arm = np.array(arm_obj.matrix_world.inverted() @ obj.matrix_world,
                      dtype=np.float64)
    from_arm = np.linalg.inv(to_arm)
    # Fold the basis change in so each vertex needs one 4x4 rather than three.
    return from_arm @ acc @ to_arm


def _transform(mats, coords):
    """Apply per-vertex 4x4 *mats* to a flat ``(V*3,)`` coordinate buffer, in place."""
    pts = coords.reshape(-1, 3)
    homo = np.empty((pts.shape[0], 4), dtype=np.float64)
    homo[:, :3] = pts
    homo[:, 3] = 1.0
    pts[:] = np.einsum('vij,vj->vi', mats, homo)[:, :3]


def bake_mesh(arm_obj, obj):
    """Write *arm_obj*'s current deformation of *obj* into *obj*'s vertices.

    Returns True if anything changed.  Shape keys are moved by the same per-vertex
    transform as the base mesh -- their coordinates are absolute positions in the same
    space, so a shape key that survives this stays exactly as far from the basis as it
    was.
    """
    mats = _skin_matrices(arm_obj, obj)
    if mats is None:
        return False

    me = obj.data
    n = len(me.vertices)

    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    _transform(mats, co)
    me.vertices.foreach_set("co", co)

    if me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            kco = np.empty(n * 3, dtype=np.float64)
            kb.data.foreach_get("co", kco)
            _transform(mats, kco)
            kb.data.foreach_set("co", kco)

    me.update()
    return True


def bake_pose_to_rest(arm_obj, context=None):
    """Make *arm_obj*'s current pose its rest pose, moving its meshes to match.

    Order matters and is not interchangeable: every mesh is baked to where the pose
    puts it *first*, then the pose becomes the rest.  Do it the other way round and
    the rest change silently redefines the deformation the meshes were about to be
    baked with, which reads as the model exploding by roughly twice the intended
    motion.

    Returns the number of meshes that moved.  Leaves the scene in OBJECT mode with
    *arm_obj* active, since the callers chain several of these.
    """
    context = context or bpy.context
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    moved = sum(1 for obj in bound_meshes(arm_obj) if bake_mesh(arm_obj, obj))

    prev_active = context.view_layer.objects.active
    context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    # selected=False applies every bone; the operator's default depends on the pose
    # selection otherwise, and a half-applied rest is far worse than none.
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    if prev_active is not None:
        context.view_layer.objects.active = prev_active
    return moved
