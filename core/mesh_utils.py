"""Split a mesh into one object per material.

``bpy.ops.mesh.separate(type='MATERIAL')`` already does the geometry work, and
it carries shape keys and vertex groups over to every fragment on its own.  The
tidying afterwards is what makes the result usable:

* every fragment inherits *all* of the source's vertex groups and shape keys,
  including the ones that only ever touched geometry that ended up in a
  different fragment;
* fragments come out named ``Foo.001``, ``Foo.002`` … rather than after the
  material that defined the split.

Deliberately not copied from the addon this was modelled on: it deletes any
shape key whose name contains ``mmd_`` regardless of content (a VRChat-pipeline
habit that would silently eat real keys here), and it stashes the shape key
order in the armature's ``['CUSTOM']`` property, which nothing in this addon
reads.
"""

import numpy as np

_TEMP_PREFIX = "__mtk_split_"


def _shape_key_is_flat(kb):
    """True when the key moves nothing relative to its reference — which is what
    a key becomes on a fragment that holds none of the geometry it deformed."""
    ref = kb.relative_key
    if ref is None or ref == kb:
        return False  # the basis
    n = len(kb.data) * 3
    a = np.empty(n, np.float32)
    b = np.empty(n, np.float32)
    kb.data.foreach_get("co", a)
    ref.data.foreach_get("co", b)
    return bool(np.array_equal(a, b))


def prune_shape_keys(obj):
    """Drop keys with no effect on this fragment.  Returns how many went.

    A lone basis left behind is dropped too: it carries no information and
    stops the object from being edited normally.
    """
    me = obj.data
    if not me.shape_keys:
        return 0
    removed = 0
    for kb in list(me.shape_keys.key_blocks):
        if _shape_key_is_flat(kb):
            obj.shape_key_remove(kb)
            removed += 1
    if me.shape_keys and len(me.shape_keys.key_blocks) == 1:
        obj.shape_key_remove(me.shape_keys.key_blocks[0])
        removed += 1
    return removed


def prune_vertex_groups(obj):
    """Drop vertex groups nothing in this fragment is weighted to."""
    used = set()
    for v in obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.0:
                used.add(g.group)
    doomed = [vg for vg in obj.vertex_groups if vg.index not in used]
    for vg in doomed:
        obj.vertex_groups.remove(vg)
    return len(doomed)


def strip_material_suffixes(obj):
    """Turn ``mat.001`` back into ``mat`` so fragments get the intended name."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat and "." in mat.name:
            stem, _, tail = mat.name.rpartition(".")
            if stem and tail.isdigit():
                mat.name = stem


def rename_after_materials(objects):
    """Name each object after its first material.

    Done in two passes through temporary names: renaming in place would collide
    with objects further down the list that still hold the wanted name, and
    Blender would answer with a ``.001`` that never goes away.
    """
    wanted = {}
    for i, obj in enumerate(objects):
        mat = obj.data.materials[0] if obj.data.materials else None
        wanted[obj] = mat.name if mat else obj.name
        obj.name = "%s%d" % (_TEMP_PREFIX, i)
    for obj, name in wanted.items():
        obj.name = name


def separate_by_materials(context, objects, rename=True, prune_keys=True,
                          prune_groups=True, clean_suffix=True):
    """Split every object in *objects* into one object per material.

    Returns (fragment count, shape keys removed, vertex groups removed).
    """
    import bpy

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    sources = [o for o in objects if o.type == 'MESH']
    if not sources:
        return 0, 0, 0

    if clean_suffix:
        for obj in sources:
            strip_material_suffixes(obj)

    before = set(bpy.data.objects)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in sources:
        obj.select_set(True)
    context.view_layer.objects.active = sources[0]

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')

    # The sources stay in place holding their first material, so the result is
    # everything new plus everything we started from
    fragments = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    fragments += sources

    keys_gone = groups_gone = 0
    for obj in fragments:
        if prune_keys:
            keys_gone += prune_shape_keys(obj)
        if prune_groups:
            groups_gone += prune_vertex_groups(obj)
    if rename:
        rename_after_materials(fragments)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in fragments:
        obj.select_set(True)
    context.view_layer.objects.active = fragments[0]
    return len(fragments), keys_gone, groups_gone
