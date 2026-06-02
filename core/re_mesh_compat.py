"""Compatibility shim for the RE Mesh Editor operator namespace.

The original RE Mesh Editor (NSACloud) registers its mesh operators under the
``re_mesh`` category, e.g. ``bpy.ops.re_mesh.exportfile``.  The community fork
"REME" (TrueShadow01) renames the *entire* mesh operator category to
``re_mesh_cm`` (re_mesh community-maintained) — exportfile, importfile,
delete_loose, solve_repeated_uvs, remove_zero_weight_vertex_groups,
limit_total_normalize, create_mesh_collection, etc. — while leaving the MDF /
chain / clsp / fbxskel / sfur categories under their original names.

This module resolves whichever mesh category is actually registered so callers
don't have to care which build the user has installed.

Note: ``hasattr(bpy.ops.re_mesh, 'exportfile')`` cannot be used to probe for an
operator because ``bpy.ops`` attribute access is lazy and returns a wrapper for
any name.  ``dir(bpy.ops.<category>)`` does list the operators actually
registered in that category, which is what we rely on here.
"""
import bpy

# Order matters only for tie-breaking; both are checked.
_MESH_CATEGORIES = ("re_mesh", "re_mesh_cm")


def _category_has_op(category, op_name):
    submod = getattr(bpy.ops, category, None)
    if submod is None:
        return False
    try:
        return op_name in dir(submod)
    except Exception:
        return False


def get_re_mesh_category(probe_op="exportfile"):
    """Return the registered RE Mesh operator category name, or None.

    *probe_op* must exist in the category for it to count (defaults to
    ``exportfile``, which batch export relies on).
    """
    for cat in _MESH_CATEGORIES:
        if _category_has_op(cat, probe_op):
            return cat
    return None


def re_mesh_op_available(op_name="exportfile"):
    """True if *op_name* is registered under either mesh category."""
    return any(_category_has_op(cat, op_name) for cat in _MESH_CATEGORIES)


def call_re_mesh_op(op_name, *args, **kwargs):
    """Call ``bpy.ops.<mesh_category>.<op_name>(...)`` resolving the namespace.

    Raises RuntimeError if neither ``re_mesh`` nor ``re_mesh_cm`` has the
    operator registered.
    """
    for cat in _MESH_CATEGORIES:
        if _category_has_op(cat, op_name):
            return getattr(getattr(bpy.ops, cat), op_name)(*args, **kwargs)
    raise RuntimeError(
        f"RE Mesh Editor operator '{op_name}' not found under 're_mesh' or "
        f"'re_mesh_cm' (is RE Mesh Editor / REME installed and enabled?)"
    )
