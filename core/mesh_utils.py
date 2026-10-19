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

import contextlib
import itertools
import re

import numpy as np


@contextlib.contextmanager
def object_mode(context):
    """Run a mesh-data edit in Object mode, returning to Edit Mesh afterwards.

    In Edit Mesh mode obj.data still holds the state from before the user entered
    it, and VertexGroup.add() raises -- so a vertex-group tool that polls fine
    there read stale weights and then failed halfway.
    """
    import bpy
    was_edit = context.mode == 'EDIT_MESH'
    if was_edit:
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        yield
    finally:
        if was_edit:
            try:
                bpy.ops.object.mode_set(mode='EDIT')
            except RuntimeError:
                pass

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

    ``TK_Basis`` (see core/shapekey_utils.py) is flat by construction -- it is
    a deliberate snapshot of Basis, not a no-op left over from a split -- so
    it is exempted even though it would otherwise match the same test.
    """
    from .shapekey_utils import FROZEN_BASIS_NAME

    me = obj.data
    if not me.shape_keys:
        return 0
    removed = 0
    for kb in list(me.shape_keys.key_blocks):
        if kb.name != FROZEN_BASIS_NAME and _shape_key_is_flat(kb):
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


def base_color_key(material):
    """Identity of *material*'s base colour texture, or None when it has none.

    Two materials count as "the same" for merging when this matches.  Compared by
    the file on disk, not the datablock: ``tex.png`` and ``tex.png.001`` loading
    one file are the same texture.  Read through shader_readers, so MMDShaderDev,
    Principled and Emission materials all resolve.
    """
    import os
    import bpy
    from .shader_readers import read_material

    if material is None or not material.use_nodes:
        return None
    ref = read_material(material, ()).pbr.get('color')
    img = getattr(ref, 'image', None)
    if img is None:
        return None
    if img.filepath:
        path = bpy.path.abspath(img.filepath, library=img.library)
        return ('file', os.path.normcase(os.path.normpath(path)))
    return ('image', img.name)


def _merge_same_texture(context, fragments):
    """Join fragments of one source whose material uses the same base colour
    texture.  Returns the surviving objects in their original order.

    Joined while the shape keys are still all there: every fragment of one source
    carries the same key names, and join matches keys by name."""
    import bpy

    # Names, not objects: join deletes the merged-in objects, and touching one
    # afterwards raises ReferenceError
    names = [o.name for o in fragments]
    groups = {}
    for obj in fragments:
        mat = obj.data.materials[0] if obj.data.materials else None
        key = base_color_key(mat)
        groups.setdefault(key if key is not None else ('alone', obj.name), []).append(obj.name)
    gone = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        # The biggest fragment receives the rest: join keeps the active object's
        # materials first, and the fragment is later named after material 0, so
        # the face group comes out as "face" rather than as its transparent
        # expression overlay
        members.sort(key=lambda n: -len(bpy.data.objects[n].data.polygons))
        bpy.ops.object.select_all(action='DESELECT')
        for name in members:
            bpy.data.objects[name].select_set(True)
        context.view_layer.objects.active = bpy.data.objects[members[0]]
        bpy.ops.object.join()
        gone.update(members[1:])
    return [bpy.data.objects[n] for n in names if n not in gone]


def separate_by_materials(context, objects, rename=True, prune_keys=True,
                          prune_groups=True, clean_suffix=True, merge_same_texture=False):
    """Split every object in *objects* into one object per material.

    With *merge_same_texture*, fragments of the same source whose materials use
    the same base colour texture are joined back into one object (keeping all
    their materials).  Only within one source: joining across sources would mix
    parents, armature bindings and unrelated shape keys.

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

    # One source at a time, so each fragment's origin is known (merging needs it)
    fragments = []
    for src in sources:
        before = set(bpy.data.objects)
        bpy.ops.object.select_all(action='DESELECT')
        src.select_set(True)
        context.view_layer.objects.active = src

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')

        # The source stays in place holding its first material, so the result is
        # everything new plus the object we started from
        own = [src] + [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
        if merge_same_texture:
            own = _merge_same_texture(context, own)
        fragments += own

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
_OUTLINE_SUFFIX = "_Outline"
#: Weld distance before the push: an imported RE mesh is split at every UV
#: seam, and without welding each copy gets its own normal, so the pushed
#: shell cracks open along the seams.
_OUTLINE_WELD_DIST = 1e-5
#: A face whose three corners all weigh below this sits on the body surface
#: (zero push), so it is dropped instead of Z-fighting with the source.
_OUTLINE_MIN_WEIGHT = 1e-4

_REME_NAME = re.compile(r'^(?P<lod>(?:LOD_\d+_)?)Group_(?P<group>\d+)_Sub_(?P<sub>\d+)__(?P<mat>.+)$')


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


def _outline_object_name(source, material_name):
    """RE Mesh Editor name for the shell: same LOD prefix and Group as the
    source, and a Sub index that makes it sort after every existing submesh of
    that group in the source's collection(s).

    REME orders a group's submeshes by plain string sort of the object name and
    writes vertices in that order, so a shell sorting last leaves every existing
    vertex index unchanged. String sort is not numeric sort ('_' sorts above
    every digit, so 'Sub_9__' beats 'Sub_10__' and any 'Sub_9x__'), hence the
    search rather than max+1.

    Returns (name, sorted_last). A source that isn't REME-named keeps the plain
    "<name>_Outline" (sorted_last True: there is no order to keep). sorted_last
    is False when no Sub index can sort last, e.g. 'Sub_9__zzz' already exists.
    """
    import bpy

    m = _REME_NAME.match(source.name)
    if m is None:
        return source.name + _OUTLINE_SUFFIX, True

    lod, group = m['lod'], m['group']
    siblings = []
    for collection in source.users_collection:
        for obj in collection.all_objects:
            sm = _REME_NAME.match(obj.name)
            if obj.type == 'MESH' and sm and sm['lod'] == lod and sm['group'] == group:
                siblings.append((obj.name, int(sm['sub'])))
    last = max(name for name, _ in siblings)
    used = {sub for _, sub in siblings}
    top = max(used)

    def name_for(sub):
        return f"{lod}Group_{group}_Sub_{sub}__{material_name}"

    for sub in itertools.chain(range(top + 1, top + 1001), range(top + 1)):
        name = name_for(sub)
        if sub not in used and name > last and name not in bpy.data.objects:
            return name, True
    return name_for(top + 1), False


def _build_outline_shell(mesh, weight_group_index, thickness):
    """Turn mesh (a private copy) into an inverted-hull outline shell in place.

    Only the outer layer is kept: every vertex moves along its outward normal by
    thickness * weight (basis and every shape key by the same vector), winding
    is reversed so the faces point inward and get backface-culled from the
    front, and custom normals are set back to the outward normal so the shell is
    lit like the surface it hugs.

    weight_group_index None means uniform thickness (weight 1 everywhere).
    """
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_OUTLINE_WELD_DIST)
        bm.normal_update()

        deform = bm.verts.layers.deform.active
        shape_layers = list(bm.verts.layers.shape.values())
        weight = bm.verts.layers.float.new("mtk_outline_w")
        normal = [bm.verts.layers.float.new(f"mtk_outline_n{i}") for i in range(3)]

        for v in bm.verts:
            if weight_group_index is None:
                w = 1.0
            else:
                w = v[deform].get(weight_group_index, 0.0) if deform is not None else 0.0
            v[weight] = w
            n = v.normal.copy()
            for i in range(3):
                v[normal[i]] = n[i]
            d = n * (thickness * w)
            v.co += d
            for layer in shape_layers:
                v[layer] = v[layer] + d

        if weight_group_index is not None:
            dead = [f for f in bm.faces if all(v[weight] < _OUTLINE_MIN_WEIGHT for v in f.verts)]
            bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')

        # Welding collapses faces that had two corners on one position (hair
        # cards), and dropping faces strands vertices/edges -- REME refuses
        # both (LooseVerticesOnSubMesh).
        bad = [f for f in bm.faces if len(set(f.verts)) < 3 or f.calc_area() < 1e-14]
        bmesh.ops.delete(bm, geom=bad, context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')

        # Split back along the UV seams the weld closed: every copy of a
        # position already got the same push, so nothing cracks, and REME's
        # repeated-UV solver is left with nothing to split.
        uv_layers = list(bm.loops.layers.uv.values())
        seams = []
        for e in bm.edges:
            if len(e.link_loops) != 2:
                continue
            l1, l2 = e.link_loops
            # l1 runs a->b, l2 (other face) runs b->a: compare UVs per vertex
            if any((l1[uv].uv - l2.link_loop_next[uv].uv).length > 1e-6
                   or (l1.link_loop_next[uv].uv - l2[uv].uv).length > 1e-6
                   for uv in uv_layers):
                seams.append(e)
        if seams:
            bmesh.ops.split_edges(bm, edges=seams)

        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))

        bm.verts.ensure_lookup_table()
        outward = [(v[normal[0]], v[normal[1]], v[normal[2]]) for v in bm.verts]
        for layer in normal + [weight]:
            bm.verts.layers.float.remove(layer)
        bm.to_mesh(mesh)
    finally:
        bm.free()

    if hasattr(mesh, "use_auto_smooth"):  # pre-4.1 needs it for custom normals
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set_from_vertices(outward)
    mesh.update()


def _create_outline_object(context, source, vertex_group_name, thickness):
    """Full object duplicate (same modifier stack, vertex groups, shape keys,
    parenting -- everything obj.copy()+data.copy() carries over), so an
    Armature modifier on the source keeps the shell deforming with it. Only
    the material, the name and the geometry (see _build_outline_shell) differ.

    No link back to source is kept -- this is a plain, disposable duplicate,
    same as any other object.copy().

    Returns (new_object, sorted_last); see _outline_object_name."""
    material = _get_or_create_outline_material()
    name, sorted_last = _outline_object_name(source, material.name)

    new_obj = source.copy()
    new_obj.data = source.data.copy()
    new_obj.name = name
    new_obj.data.name = name

    for collection in source.users_collection:
        collection.objects.link(new_obj)
    if not new_obj.users_collection:
        context.scene.collection.objects.link(new_obj)

    # Object.copy() carries over the source's current "selected" flag -- clear
    # it now that new_obj is in the view layer, or a second run over the same
    # selection (without reselecting in between) would sweep up every shell
    # the first run made too, cascading into outlines-of-outlines-of-outlines.
    new_obj.select_set(False)

    # A dedicated shell only ever needs the one outline material -- no
    # material_offset juggling to keep the source's other slots intact
    new_obj.data.materials.clear()
    new_obj.data.materials.append(material)

    group = new_obj.vertex_groups.get(vertex_group_name) if vertex_group_name else None
    _build_outline_shell(new_obj.data, group.index if group else None, thickness)
    return new_obj, sorted_last


def create_outline_shell(context, objects, vertex_group_name="", thickness=0.001, ignore_collection_name="IgnoreExport"):
    """Create a brand new dedicated inverted-hull outline shell object for
    each source mesh.

    The shell is a full duplicate of the source (vertex group weights, shape
    keys, modifier stack incl. any Armature binding) whose geometry is pushed
    out along the normal by thickness and whose faces point inward, with its
    materials replaced by a single backface-culled black material. The source
    mesh itself is never touched.

    Every call is independent: there's no tracking back to the source and no
    re-use of a previous shell, so running this several times over the same
    source just adds more shells rather than guessing which one to replace.

    vertex_group_name, when non-empty, scales the push per vertex by its
    weight, and faces weighing ~0 at all three corners are dropped -- sources
    missing a group by that name still get a shell, just with uniform
    thickness, and are counted in the returned tally instead of silently
    doing nothing.

    Returns (created, missing_vertex_group, not_last) counts -- not_last is
    REME-named shells that couldn't be given a name sorting after every
    existing submesh of their group (see _outline_object_name).
    """
    import bpy

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    ignore_collection = bpy.data.collections.get(ignore_collection_name) if ignore_collection_name else None

    added = missing_vg = not_last = 0

    for obj in objects:
        if obj.type != 'MESH':
            continue

        if ignore_collection and _object_in_collection(obj, ignore_collection):
            continue

        if vertex_group_name and vertex_group_name not in obj.vertex_groups:
            missing_vg += 1

        _, sorted_last = _create_outline_object(context, obj, vertex_group_name, thickness)
        if not sorted_last:
            not_last += 1
        added += 1

    return added, missing_vg, not_last
