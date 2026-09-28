"""「导出前自动修正」: the fixes that run on their own before a batch export.

Design: ``docs/pre_export_check_plan.md`` §3.  Only problems whose fix needs no
judgement live here; anything the user has to decide is a finding in the
pre-export report instead.

Every item has two halves:

``plan()``
    Read-only.  Counts what each item *would* touch, and names the objects /
    bindings a fix covers, so the pre-export check can leave those out of the
    problem list (the check judges the state *after* auto-fix).  Called from a
    dialog's ``draw()``, so it must never write.
``apply()`` / ``temporary()``
    The writes.  ``apply()`` makes the persistent fixes and pushes one undo step;
    ``temporary()`` wraps the export itself for the fixes that must not outlive
    it (face triangulation rides on a modifier, filled vertex colours on a layer
    that is removed afterwards).

Scope is MHWS for now (``enabled_items`` returns None for other games, which
keeps their exporters on their own cleanup/triangulate toggles).
"""

import json
import os
from contextlib import contextmanager

import bpy
import bmesh
import numpy as np

from . import pre_export_check as pc
from . import weight_utils
from . import export_prep

#: (id, label key, tooltip key, bit, on by default).  Keys spelled out in full:
#: a key built by concatenation is invisible to tests/test_ui_translated.py.
#: Bits are explicit because the settings property is a dynamic ENUM_FLAG, whose
#: default has to be an integer.
ITEMS = (
    ('TRIANGULATE', "core.export_autofix.item_triangulate", "core.export_autofix.tip_triangulate", 1, True),
    ('WEIGHTS',     "core.export_autofix.item_weights",     "core.export_autofix.tip_weights",     2, True),
    ('MIRROR',      "core.export_autofix.item_mirror",      "core.export_autofix.tip_mirror",      4, True),
    ('TEX_PATHS',   "core.export_autofix.item_tex_paths",   "core.export_autofix.tip_tex_paths",   8, True),
    ('TEX_EMPTY',   "core.export_autofix.item_tex_empty",   "core.export_autofix.tip_tex_empty",   16, True),
    ('VCOLOR',      "core.export_autofix.item_vcolor",      "core.export_autofix.tip_vcolor",      32, True),
    ('MAT_NAMES',   "core.export_autofix.item_mat_names",   "core.export_autofix.tip_mat_names",   128, True),
    ('PHYS_TARGET', "core.export_autofix.item_phys_target", "core.export_autofix.tip_phys_target", 256, True),
    ('LEGACY',      "core.export_autofix.item_legacy",      "core.export_autofix.tip_legacy",      64, False),
)
LABEL_KEYS = {i: label for i, label, _tip, _bit, _on in ITEMS}
DEFAULT_MASK = sum(bit for _i, _k, _t, bit, on in ITEMS if on)

#: Items that only exist for the duration of the export and so cannot be
#: "fixed now" from the report.
TEMPORARY = {'TRIANGULATE', 'VCOLOR'}

#: Items whose problem, when the item is switched off, is not repeated in the
#: 「可自动修复」 category: TEX_PATHS because upstream's own fixTexPath writes the
#: same correction at mdf export, MAT_NAMES because illegal names already have
#: their own group and fix button in the Materials category.
SILENT_WHEN_OFF = {'TEX_PATHS', 'MAT_NAMES'}

#: Upstream ``SIX_WEIGHT_GAMES``/``EXTENDED_WEIGHT_GAMES`` put MH Wilds at 12
#: influences per vertex (6 plus an extended buffer).
MAX_INFLUENCES = {'MHWS': 12}

#: Residual (degrees) above which a mirror fix is taken back.  The carried
#: normals come back with INT16 re-encode error only; anything past this means
#: the carry itself went wrong, and exporting that would be worse than the
#: mirror the report would otherwise show.
MIRROR_MAX_RESIDUAL = 2.0

#: Objects whose mirror fix was taken back this session: the report says why,
#: and plan() stops calling them fixable (it would only fail again).
MIRROR_FAILED = set()

#: Game code -> key in upstream's tex_bindings_null.json.
_NULL_TABLE_GAME = {'MHWS': 'MHWILDS', 'RE4': 'RE4', 'RE9': 'RE9', 'MHRS': 'MHRSB'}

_enum_cache = []


def enum_items(self, context):
    """Items for the gear's ENUM_FLAG dropdown, translated at draw time.
    Cached module-side: Blender keeps no reference to a callback's strings."""
    from .i18n import T
    _enum_cache[:] = [(i, T(label), T(tip), bit) for i, label, tip, bit, _on in ITEMS]
    return _enum_cache


# ── Settings ─────────────────────────────────────────────────────────────────

def enabled_items(context, game):
    """The set of item ids switched on for *game*, or None when *game* has no
    auto-fix (its exporter keeps its own toggles)."""
    if game != 'MHWS':
        return None
    s = context.scene.mhw_suite_settings
    if not s.mhws_autofix:
        return set()
    return set(s.mhws_autofix_items)


# ── Shared scans ─────────────────────────────────────────────────────────────

def _mesh_objects(mesh_cols):
    seen, out = set(), []
    for col in mesh_cols:
        for o in col.all_objects:
            if o.type == 'MESH' and not o.get("MeshExportExclude") and o.name not in seen:
                seen.add(o.name)
                out.append(o)
    return out


def _mdf_materials(mdf_cols):
    return [o for col in mdf_cols for o in col.objects
            if o.get("~TYPE") == "RE_MDF_MATERIAL" and getattr(o, 're_mdf_material', None)]


def _cols(pairs):
    mdf, mesh = [], []
    for _label, mdf_col, mesh_col in pairs:
        if mdf_col is not None and mdf_col not in mdf:
            mdf.append(mdf_col)
        if mesh_col is not None and mesh_col not in mesh:
            mesh.append(mesh_col)
    return mdf, mesh


def _modifier_groups(obj):
    """Vertex group names a modifier refers to -- an empty one of those still
    means something (an empty Solidify mask is 'nowhere', a missing one is
    'everywhere'), so it must not be removed as dead."""
    names = set()
    for m in obj.modifiers:
        for attr in ('vertex_group', 'vertex_group_a', 'vertex_group_b', 'invert_vertex_group'):
            v = getattr(m, attr, None)
            if isinstance(v, str) and v:
                names.add(v)
    return names


def _weight_issues(obj, max_influences):
    """What the weight cleanup would change on *obj*, as a dict of counts.

    Loose vertices and edges, empty groups (not referenced by a modifier),
    deform weights below the exporter's cut-off, vertices over the influence
    limit, and deform weights that do not sum to 1.
    """
    me = obj.data
    out = {'loose': 0, 'empty_groups': 0, 'tiny': 0, 'over': 0, 'unnormalized': 0}

    n_loops = np.zeros(len(me.vertices), np.int32)
    corner_verts = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", corner_verts)
    np.add.at(n_loops, corner_verts, 1)
    edge_faces = {k for p in me.polygons for k in p.edge_keys}
    out['loose'] = int((n_loops == 0).sum()) + sum(
        1 for e in me.edges if e.key not in edge_faces)

    used = set()
    arm = obj.find_armature()
    idx = weight_utils.deform_group_indices(obj, arm) if arm else set()
    for v in me.vertices:
        rows = []
        for g in v.groups:
            used.add(g.group)
            if g.group in idx:
                rows.append(g.weight)
        if not rows:
            continue
        live = [w for w in rows if w > 0.0]
        if any(0.0 < w < pc.EXPORT_MIN_WEIGHT for w in live) and len(live) > 1:
            out['tiny'] += 1
        if len(live) > max_influences:
            out['over'] += 1
        if pc.classify_weight_sum(sum(rows)) in ("under", "over"):
            out['unnormalized'] += 1
    keep = _modifier_groups(obj)
    out['empty_groups'] = sum(1 for vg in obj.vertex_groups
                              if vg.index not in used and vg.name not in keep)
    return out


def _mirror_fixable(obj):
    """True when the negative determinant sits in the object's own transform,
    so baking that transform fixes it.  A mirror coming from the parent chain
    (an armature scaled -1) or a mesh shared by several objects is left to the
    report."""
    if obj.matrix_world.determinant() >= 0:
        return False
    if obj.matrix_basis.determinant() >= 0:
        return False
    return obj.data.users == 1 and obj.name not in MIRROR_FAILED


_null_cache = {}


def _null_table():
    if 'table' in _null_cache:
        return _null_cache['table']
    table = {}
    from .mdf_generator_base import _get_re_mesh_editor_addon_dir
    root = _get_re_mesh_editor_addon_dir()
    if root:
        path = os.path.join(root, "modules", "workspace", "texturepacker", "tex_bindings_null.json")
        try:
            with open(path, encoding="utf-8") as fh:
                table = json.load(fh)
        except (OSError, ValueError):
            table = {}
    _null_cache['table'] = table
    return table


def null_path(game, slot):
    """Upstream's null texture for *slot* in *game*, falling back to its
    ``generic`` entry the way ``re_mdf.nullify_texture_bindings`` does."""
    entry = _null_table().get(slot) or {}
    return entry.get(_NULL_TABLE_GAME.get(game, ''), entry.get('generic'))


def _has_vcolor(obj):
    # The exporter reads the legacy vertex_colors collection (byte colour on the
    # corner domain) and nothing else (upstream blender_re_mesh.py:1513).
    return len(obj.data.vertex_colors) > 0


def _vcolor_targets(mesh_cols):
    """[(obj, layer name)] for meshes that would get upstream's near-black fill:
    no colour layer of their own while another submesh of the same .mesh has
    one (file_re_mesh.py:2101-2102 fills 255 and then multiplies by 255 again)."""
    out = []
    for col in mesh_cols:
        objs = _mesh_objects([col])
        with_color = [o for o in objs if _has_vcolor(o)]
        if not with_color:
            continue
        name = with_color[0].data.vertex_colors[0].name
        out += [(o, name) for o in objs if not _has_vcolor(o)]
    return out


def _needs_triangulate(obj):
    counts = np.empty(len(obj.data.polygons), np.int32)
    obj.data.polygons.foreach_get("loop_total", counts)
    return bool((counts > 3).any()) and not any(m.type == 'TRIANGULATE' for m in obj.modifiers)


# ── Material names (also the report's 「修复不合法命名」 button) ────────────

def derived_material(obj):
    """``(material_name, how)`` for one mesh -- the object name first, the
    Blender material as the fallback RE Mesh's exporter also uses."""
    mat_name, how = pc.parse_mesh_name(obj.name)
    if how != 'no_format':
        return mat_name, how
    mats = [m for m in obj.data.materials if m is not None]
    if not mats:
        return '', 'no_format'
    # Multi-material meshes take the first, matching the exporter.
    return pc.strip_dedup_suffix(mats[0].name), 'no_format'


def _name_plan(mdf_col, mesh_col):
    materials = _mdf_materials([mdf_col])
    meshes = _mesh_objects([mesh_col]) if mesh_col is not None else []
    return pc.plan_name_fixes(
        [o.re_mdf_material.materialName for o in materials],
        [(o.name, mat, how) for o in meshes for mat, how in [derived_material(o)]])


def _count_renames(mdf_col, mesh_col):
    plan = _name_plan(mdf_col, mesh_col)
    return len(plan['materials']) + len(plan['objects']) + len(plan['datablocks'])


def fix_names(mdf_col, mesh_col):
    """Correct illegal names on one (mdf_col, mesh_col) pair in place.
    Returns ``(n_mat, n_obj, n_data)``."""
    materials = _mdf_materials([mdf_col])
    meshes = _mesh_objects([mesh_col]) if mesh_col is not None else []
    mesh_entries = [(o, *derived_material(o)) for o in meshes]

    plan = pc.plan_name_fixes(
        [o.re_mdf_material.materialName for o in materials],
        [(o.name, mat, how) for o, mat, how in mesh_entries])

    n_mat = n_obj = n_data = 0
    for obj in materials:
        new = plan['materials'].get(obj.re_mdf_material.materialName)
        if new:
            obj.re_mdf_material.materialName = new
            n_mat += 1
    for obj in meshes:
        new = plan['objects'].get(obj.name)
        if new:
            obj.name = new
            n_obj += 1
    # Datablocks are renamed through the meshes that fell back to them
    # rather than by looking the name up in bpy.data.materials: two
    # datablocks can share a stripped name, and only the one this mesh
    # actually uses should move.
    for obj, mat, how in mesh_entries:
        if how != 'no_format':
            continue
        new = plan['datablocks'].get(mat)
        if not new:
            continue
        slots = [m for m in obj.data.materials if m is not None]
        if slots and pc.strip_dedup_suffix(slots[0].name) != new:
            slots[0].name = new
            n_data += 1
    return n_mat, n_obj, n_data


# ── Plan ─────────────────────────────────────────────────────────────────────

class Plan:
    """What each item would touch.  ``counts[id]`` is the number of meshes /
    bindings; the two sets let the pre-export check drop what a fix covers."""

    def __init__(self):
        self.counts = {}
        self.mirror_fixable = set()     # object names
        self.empty_fixable = set()      # (material object name, slot)
        self.target_fixable = set()     # chain object names

    def pending(self, ids):
        return {i: n for i, n in self.counts.items() if i in ids and n}


def _armatures(mesh_cols, physics):
    from .pre_export_physics import collection_armature
    out = []
    for col in list(mesh_cols) + [p.mesh for p in physics or []]:
        arm = collection_armature(col)
        if arm is not None and arm not in out:
            out.append(arm)
    return out


def plan(context, game, pairs, physics=None):
    """Read-only: count what every item would do over *pairs*
    (``(label, mdf_col, mesh_col)``) and *physics* (``[PhysPart]``).  Safe to
    call from ``draw()``."""
    p = Plan()
    mdf_cols, mesh_cols = _cols(pairs)
    meshes = _mesh_objects(mesh_cols)
    limit = MAX_INFLUENCES.get(game, 12)

    p.counts['TRIANGULATE'] = sum(
        1 for o in export_prep.find_head_meshes(meshes, game.lower()) if _needs_triangulate(o))
    p.counts['WEIGHTS'] = sum(1 for o in meshes if any(_weight_issues(o, limit).values()))
    p.counts['LEGACY'] = 0      # a variant of WEIGHTS, never counted on its own
    p.mirror_fixable = {o.name for o in meshes if _mirror_fixable(o)}
    p.counts['MIRROR'] = len(p.mirror_fixable)
    p.counts['VCOLOR'] = len(_vcolor_targets(mesh_cols))

    n_paths = 0
    for obj in _mdf_materials(mdf_cols):
        for b in obj.re_mdf_material.textureBindingList_items:
            if not (b.path or '').strip():
                if null_path(game, b.textureType):
                    p.empty_fixable.add((obj.name, b.textureType))
            elif pc.fix_tex_path(b.path) != b.path:
                n_paths += 1
    p.counts['TEX_PATHS'] = n_paths
    p.counts['TEX_EMPTY'] = len(p.empty_fixable)
    p.counts['MAT_NAMES'] = sum(_count_renames(mdf, mesh) for _l, mdf, mesh in pairs
                                if mdf is not None)
    if physics:
        from .pre_export_physics import target_fixes
        p.target_fixable = {o.name for o, _c, _a in target_fixes(physics, _armatures(mesh_cols, physics))}
    p.counts['PHYS_TARGET'] = len(p.target_fixable)
    return p


# ── Apply ────────────────────────────────────────────────────────────────────

def _delete_loose(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    edges = [e for e in bm.edges if not e.link_faces]
    if edges:
        bmesh.ops.delete(bm, geom=edges, context='EDGES')
    verts = [v for v in bm.verts if not v.link_faces]
    if verts:
        bmesh.ops.delete(bm, geom=verts, context='VERTS')
    changed = bool(edges or verts)
    if changed:
        bm.to_mesh(me)
        me.update()
    bm.free()
    return changed


def _clean_weights(obj, limit):
    """Tiny weights out (keeping each vertex's largest), over-limit influences
    out, then normalise -- all on deform groups only.  Direct writes rather than
    bpy.ops.object.vertex_group_*: those need mode and active-object juggling,
    and their group_select_mode default falls back to ALL, which would take
    outline-thickness and mask groups down with the bones."""
    arm = obj.find_armature()
    if arm is None:
        return
    idx = weight_utils.deform_group_indices(obj, arm)
    if not idx:
        return
    drop = {}   # group index -> [vertex index]
    for v in obj.data.vertices:
        rows = sorted(((g.weight, g.group) for g in v.groups if g.group in idx and g.weight > 0.0),
                      reverse=True)
        if not rows:
            continue
        keep = [r for r in rows[:limit] if r[0] >= pc.EXPORT_MIN_WEIGHT] or rows[:1]
        kept = {gi for _w, gi in keep}
        for _w, gi in rows:
            if gi not in kept:
                drop.setdefault(gi, []).append(v.index)
    groups = {vg.index: vg for vg in obj.vertex_groups}
    for gi, verts in drop.items():
        groups[gi].remove(verts)
    weight_utils.normalize_deform_weights([obj], arm)


def _remove_empty_groups(obj):
    used = {g.group for v in obj.data.vertices for g in v.groups}
    keep = _modifier_groups(obj)
    for vg in [vg for vg in obj.vertex_groups if vg.index not in used and vg.name not in keep]:
        obj.vertex_groups.remove(vg)


def _fix_mirror(context, obj):
    """Bake the object's own transform with the split normals carried across.
    Returns True if kept, False if taken back (residual too high)."""
    from . import normal_utils
    backup = obj.data.copy()
    old_basis = obj.matrix_basis.copy()
    stashed = normal_utils.stash_normals(obj.data, obj.matrix_world)
    with context.temp_override(active_object=obj, object=obj,
                               selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    resid = normal_utils.unstash_normals(obj.data, obj.matrix_world) if stashed else None
    if resid is not None and len(resid) and float(np.max(resid)) > MIRROR_MAX_RESIDUAL:
        broken = obj.data
        obj.data = backup
        bpy.data.meshes.remove(broken)
        obj.matrix_basis = old_basis
        MIRROR_FAILED.add(obj.name)
        return False
    bpy.data.meshes.remove(backup)
    return True


def _legacy_cleanup(context, mesh_cols):
    """The pre-v2 「导出前清理」, kept verbatim as the compat item: RE Mesh
    Editor's own four operators, one object at a time, on direct members."""
    from .re_mesh_compat import call_re_mesh_op, re_mesh_op_available
    if not re_mesh_op_available('delete_loose'):
        return
    if context.view_layer.objects.active is not None and context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for col in mesh_cols:
        for obj in [o for o in col.objects if o.type == 'MESH']:
            context.view_layer.objects.active = obj
            obj.select_set(True)
            for op, kw in (('delete_loose', {}), ('solve_repeated_uvs', {}),
                           ('remove_zero_weight_vertex_groups', {})):
                try:
                    call_re_mesh_op(op, **kw)
                except Exception:
                    pass
            try:
                call_re_mesh_op('limit_total_normalize', maxWeights='12')
            except Exception:
                try:
                    bpy.ops.object.vertex_group_limit_total(limit=12)
                    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
                except Exception:
                    pass
            obj.select_set(False)


def apply(context, game, pairs, ids, physics=None):
    """Make the persistent fixes in *ids* over *pairs* (and *physics*, the
    ``[PhysPart]`` of a dialog that binds chain2 / clsp) and push one undo step.

    Returns ``{id: count}`` of what was actually changed.  Temporary items are
    ignored here -- see ``temporary()``.
    """
    done = {}
    mdf_cols, mesh_cols = _cols(pairs)
    if context.view_layer.objects.active is not None and context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    meshes = _mesh_objects(mesh_cols)
    limit = MAX_INFLUENCES.get(game, 12)

    if 'WEIGHTS' in ids:
        if 'LEGACY' in ids:
            n = sum(1 for o in meshes if any(_weight_issues(o, limit).values()))
            _legacy_cleanup(context, mesh_cols)
        else:
            n = 0
            for obj in meshes:
                issues = _weight_issues(obj, limit)
                if not any(issues.values()):
                    continue
                if issues['loose']:
                    _delete_loose(obj)
                _clean_weights(obj, limit)
                # Last, and unconditionally: deleting loose vertices and trimming
                # over-limit influences can each empty a group that was in use a
                # moment ago (measured -- the 13th and 14th bone of a 14-influence
                # vertex were left behind as empty groups when this ran first).
                _remove_empty_groups(obj)
                n += 1
        done['WEIGHTS'] = n

    if 'MIRROR' in ids:
        done['MIRROR'] = sum(1 for o in meshes if _mirror_fixable(o) and _fix_mirror(context, o))

    if 'TEX_PATHS' in ids or 'TEX_EMPTY' in ids:
        n_paths = n_empty = 0
        for obj in _mdf_materials(mdf_cols):
            for b in obj.re_mdf_material.textureBindingList_items:
                if not (b.path or '').strip():
                    if 'TEX_EMPTY' in ids:
                        null = null_path(game, b.textureType)
                        if null:
                            b.path = null
                            n_empty += 1
                elif 'TEX_PATHS' in ids:
                    fixed = pc.fix_tex_path(b.path)
                    if fixed != b.path:
                        b.path = fixed
                        n_paths += 1
        done['TEX_PATHS'] = n_paths
        done['TEX_EMPTY'] = n_empty

    if 'MAT_NAMES' in ids:
        done['MAT_NAMES'] = sum(sum(fix_names(mdf, mesh)) for _l, mdf, mesh in pairs
                                if mdf is not None)

    if 'PHYS_TARGET' in ids and physics:
        from .pre_export_physics import target_fixes
        fixes = target_fixes(physics, _armatures(mesh_cols, physics))
        for _obj, con, arm in fixes:
            con.target = arm
        done['PHYS_TARGET'] = len(fixes)

    if any(done.values()):
        bpy.ops.ed.undo_push(message="Auto-fix Before Export")
    return done


def _fill_normal_vcolor(obj, name):
    """A byte-colour corner layer holding the world-space corner normals, the
    way MHW Model Editor's 「烘焙法向到顶点色」 encodes them
    (``mod3_operators.py:389-505``: ``(rotateNeg90X @ matrix_world).to_3x3()``,
    ``n * 0.5 + 0.5``, alpha 1) -- vectorised, ~600x faster, same bytes."""
    from math import radians
    from mathutils import Matrix
    from . import normal_utils
    me = obj.data
    layer = me.vertex_colors.new(name=name)
    m3 = np.array((Matrix.Rotation(radians(-90.0), 4, 'X') @ obj.matrix_world).to_3x3(), np.float64)
    n = normal_utils.corner_normals(me) @ m3.T
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    col = np.ones((len(me.loops), 4), np.float32)
    col[:, :3] = n * 0.5 + 0.5
    layer.data.foreach_set("color", col.ravel())
    return layer.name


@contextmanager
def temporary(context, game, pairs, ids):
    """Wrap the export for the fixes that must not outlive it.  Yields
    ``{id: count}``; everything is undone on the way out, even on error."""
    _mdf_cols, mesh_cols = _cols(pairs)
    added = []
    counts = {}
    try:
        if 'VCOLOR' in ids:
            for obj, name in _vcolor_targets(mesh_cols):
                added.append((obj, _fill_normal_vcolor(obj, name)))
            counts['VCOLOR'] = len(added)
        if 'TRIANGULATE' in ids:
            with export_prep.triangulated_for_export(_mesh_objects(mesh_cols), game.lower()) as touched:
                counts['TRIANGULATE'] = len(touched)
                yield counts
        else:
            yield counts
    finally:
        for obj, name in added:
            layer = obj.data.vertex_colors.get(name)
            if layer is not None:
                obj.data.vertex_colors.remove(layer)
