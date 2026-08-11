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


# ─────────────────────────────────────────────────────────────────────────────
# Toon outline: a dedicated "<name>_Outline" shell object per source mesh
# (backface-culled black material + flipped-normal Solidify), source untouched
# ─────────────────────────────────────────────────────────────────────────────

_OUTLINE_MATERIAL_NAME = "Outline"
_OUTLINE_MODIFIER_NAME = "MTK_Outline"
_OUTLINE_SUFFIX = "_Outline"


def _object_in_collection(obj, collection):
    """True if obj is a member of collection or any of its nested children."""
    if obj.name in collection.objects:
        return True
    return any(_object_in_collection(obj, child) for child in collection.children)


def _get_or_create_outline_material():
    import bpy

    material = bpy.data.materials.get(_OUTLINE_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(name=_OUTLINE_MATERIAL_NAME)
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
            bsdf.inputs[2].default_value = 1.0  # Roughness
        material.use_backface_culling = True
    return material


def _bake_outline_solidify(obj):
    """Apply the shell's Solidify in place, turning the shell edge into real
    geometry instead of a live modifier. Reuses shapekey_utils' shape-key-safe
    apply path (Solidify's output vertex count is a function of topology, not
    vertex position, so it's stable across shape keys the same way any other
    non-topology-changing modifier is).

    Any other modifier copied onto the shell (most commonly an Armature
    binding) is hidden for the duration so it (a) isn't itself baked — that
    would freeze the shell to the current pose and kill future deformation —
    and (b) doesn't feed Solidify posed coordinates instead of the bind pose.
    It's restored to the modifier stack afterwards either way.

    Silently leaves Solidify un-applied (still a perfectly usable live
    modifier) if shapekey_utils' own safety check rejects the bake — never
    destroys shape key data to force it through.

    Returns True if the modifier was actually baked down.
    """
    import bpy

    from . import shapekey_utils

    solidify = obj.modifiers.get(_OUTLINE_MODIFIER_NAME)
    if solidify is None:
        return False

    # Name comparison, not `is`/`in` — separate accesses into a bpy_prop_collection
    # can hand back distinct wrapper objects for the same underlying modifier.
    other_mods = [m for m in obj.modifiers if m.name != solidify.name and m.show_viewport]
    for mod in other_mods:
        mod.show_viewport = False

    try:
        kbs = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
        if len(kbs) >= 2:
            ok, _key, _kwargs = shapekey_utils.check(obj)
            if not ok:
                return False
            shapekey_utils.apply_modifiers_keep_shape_keys(obj)
            return True

        if kbs:
            # Just a lone Basis key with nothing to preserve — drop it so
            # the plain apply operator (which refuses any shape keys at all)
            # stops objecting.
            with bpy.context.temp_override(object=obj, active_object=obj,
                                            selected_editable_objects=[obj]):
                bpy.ops.object.shape_key_remove(all=True)
        with bpy.context.temp_override(object=obj, active_object=obj,
                                        selected_editable_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=solidify.name)
        return True
    finally:
        for mod in other_mods:
            mod.show_viewport = True


def _create_outline_object(context, source, vertex_group_name, thickness):
    """Full object duplicate (same modifier stack, vertex groups, shape keys,
    parenting — everything obj.copy()+data.copy() carries over), so an
    Armature modifier on the source keeps the shell deforming with it.
    Only the material and the trailing Solidify (baked down via
    _bake_outline_solidify) differ from the source.

    No link back to source is kept — this is a plain, disposable duplicate,
    same as any other object.copy(). Naming it after the source is purely a
    starting point; Blender auto-uniquifies (.001, .002, ...) if that name is
    already taken by an earlier shell, so making several passes to join
    together later just works.

    Returns (new_object, baked) where baked is False if the Solidify couldn't
    be safely auto-applied and was left as a live modifier instead."""
    new_obj = source.copy()
    new_obj.data = source.data.copy()
    new_obj.name = source.name + _OUTLINE_SUFFIX
    new_obj.data.name = source.data.name + _OUTLINE_SUFFIX

    for collection in source.users_collection:
        collection.objects.link(new_obj)
    if not new_obj.users_collection:
        context.scene.collection.objects.link(new_obj)

    # Object.copy() carries over the source's current "selected" flag — clear
    # it now that new_obj is in the view layer, or a second run over the same
    # selection (without reselecting in between) would sweep up every shell
    # the first run made too, cascading into outlines-of-outlines-of-outlines.
    new_obj.select_set(False)

    # A dedicated shell only ever needs the one outline material — no
    # material_offset juggling to keep the source's other slots intact
    new_obj.data.materials.clear()
    new_obj.data.materials.append(_get_or_create_outline_material())

    solidify = new_obj.modifiers.new(name=_OUTLINE_MODIFIER_NAME, type='SOLIDIFY')
    solidify.thickness = thickness
    solidify.use_flip_normals = True
    solidify.use_quality_normals = True
    if vertex_group_name:
        solidify.vertex_group = vertex_group_name

    baked = _bake_outline_solidify(new_obj)
    return new_obj, baked


def create_outline_shell(context, objects, vertex_group_name="", thickness=0.001, ignore_collection_name="IgnoreExport"):
    """Create a brand new dedicated outline shell object for each source mesh.

    The shell is a full duplicate of the source (geometry, vertex group
    weights, shape keys, modifier stack incl. any Armature binding) with its
    materials replaced by a single backface-culled black material and a
    flipped-normal Solidify appended and then applied — the source mesh
    itself is never given a new material slot or modifier, and the shell
    keeps only whatever modifiers (e.g. an Armature binding) it copied from
    the source, so it still deforms with the body.

    Every call is independent: there's no tracking back to the source and no
    re-use of a previous shell, so running this several times over the same
    source (e.g. to join the results together afterwards, or to compare
    different thickness/vertex-group settings) just adds more shells rather
    than guessing which one to replace. Deleting a shell you don't want is
    just deleting the object like any other.

    vertex_group_name, when non-empty, drives the shell's Solidify per-vertex
    thickness factor (looked up on the shell, which starts out with the exact
    same groups/weights as the source since it's a straight data copy) —
    sources missing a group by that name still get a shell, just with
    uniform thickness, and are counted in the returned tally instead of
    silently doing nothing (Blender's own vertex_group field doesn't
    validate the name, so a typo would otherwise pass with no feedback).

    Returns (created, missing_vertex_group, not_baked) counts — not_baked is
    shells where auto-applying the Solidify was unsafe (per shapekey_utils'
    own check) and it was left as a live modifier instead.
    """
    import bpy

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    ignore_collection = bpy.data.collections.get(ignore_collection_name) if ignore_collection_name else None

    added = missing_vg = not_baked = 0

    for obj in objects:
        if obj.type != 'MESH':
            continue

        if ignore_collection and _object_in_collection(obj, ignore_collection):
            continue

        if vertex_group_name and vertex_group_name not in obj.vertex_groups:
            missing_vg += 1

        _, baked = _create_outline_object(context, obj, vertex_group_name, thickness)
        if not baked:
            not_baked += 1
        added += 1

    return added, missing_vg, not_baked
