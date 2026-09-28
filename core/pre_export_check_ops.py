"""Pre-export check, operator layer: run core/pre_export_check.py's rules over
real collections and show the result.

Three operators, because the flow has three moments:

``modder.pre_export_check``
    The input dialog. Picks the .mdf2 collection (required), the .mesh
    collection (optional -- without it there is nothing to match materials
    *against*), and reads the mod root the generator/processor already use.
    Running it hands off to the report.
``modder.pre_export_check_report``
    The two-column report.  Left is a scrollable category list, right is the
    detail for the selected one -- the same shape as MHW Model Editor's export
    error window (``modules/mod3/mod3_export_errors.py``), which solved this
    exact problem already.
``modder.pre_export_check_fix``
    Corrects illegal names and re-runs the check in place.

The checks below produce flat *findings*; ``core/pre_export_report.py`` groups
them into at most four categories, deduplicates them across parts and decides
what the summary line counts.  See ``docs/pre_export_check_plan.md`` for which
problems are shown at all -- the ones the exporter handles itself (weights that
do not sum to 1, extra material slots behind a ``__`` name) are deliberately not.

**Why the report lives on the Scene rather than on the operator.**  MHWME keeps
its list in the operator's own ``CollectionProperty``, which is fine when the
dialog only ever displays.  Here the fix button has to change the data and have
the *already-open* dialog show the new result, so both operators need to reach
the same storage.  A ``bpy.types.Scene`` collection is the one place both can
write.  That this works at all was measured before it was built: an operator
button inside ``invoke_props_dialog`` does **not** close the popup -- ``draw()``
keeps being called after the inner operator's ``execute`` returns (verified in
Blender 5.1.2, 2026-08-15), so the redraw picks up the rewritten entries with no
need to re-invoke the dialog.

*Which* checks can run is not the same question for every game.  The texture
check needs both a mod root and the bundled list of the game's own shipped
texture paths (``assets/<game>/vanilla_tex_paths.txt``, reached through the same
per-game registry the port and processor use).  Without that list every vanilla
path would classify as a missing custom one, so a game that has none skips the
texture check rather than reporting nonsense -- and the dialog says so up front,
because a check that silently did not run reads exactly like one that passed.
"""

import os

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, StringProperty)

from .i18n import T
from .compat import HAS_DIALOG_TITLE
from . import pre_export_check as pc
from . import pre_export_report as pr
from . import export_autofix
from . import mdf_layouts
from . import pre_export_physics as pphys
from .mdf_material_convert_base import _load_vanilla_art_paths
from .mdf_port_tex import get_game_tex_config
from .tex_file import read_tex_size
from .mdf_port_ops import mdf_material_collections, _draw_mod_root_row
from .mesh_port_ops import mesh_collections

from . import weight_utils

_K = "core.pre_export_check_ops."

#: Same geometry MHWME's error window uses -- wide enough that a full texture
#: path fits on one wrapped line, split so the category list stays narrow.
WINDOW_SIZE = 750
SPLIT_FACTOR = 0.35

#: Sentinel for "no mesh collection", which is a legal choice: the user may only
#: want the texture check.
_NONE = "NONE"

#: Group order inside each category, most actionable first.  Errors still
#: always precede notes (pre_export_report.build_report).
_SUB_ORDER = (
    'tex_root_wrong', 'tex_missing', 'tex_wrong_version', 'tex_not_pow2', 'tex_unreadable', 'tex_empty',
    'mat_pair', 'mat_pair_weak', 'mesh_unmatched', 'mat_unused_fixable', 'mat_unused', 'mat_duplicate',
    'mat_outdated', 'name_illegal', 'mesh_multi_color', 'mat_snapshot_stale',
    'mesh_structure', 'bone_non_ascii', 'vgroup_no_bone', 'unweighted',
    'xform_mirrored', 'xform_degenerate',
    'phys_structure', 'phys_parent', 'phys_bone_retarget', 'phys_bone_missing', 'phys_bone_path',
    'phys_collider_bone', 'phys_no_weight', 'phys_duplicate', 'phys_crossing',
    'phys_clsp_unbound', 'phys_link_dangling', 'phys_single_node',
)

#: Category and group codes -> their i18n keys.  Spelled out rather than built
#: by pasting the code onto a prefix: a half-built key is invisible to the table
#: check in tests/test_ui_translated.py, so a renamed code would reach the user
#: as a raw key string instead of failing the suite.
_CAT_KEYS = {
    'tex':  (_K + "cat_tex",  _K + "effect_tex",  _K + "action_tex"),
    'mat':  (_K + "cat_mat",  _K + "effect_mat",  _K + "action_mat"),
    'bone': (_K + "cat_bone", _K + "effect_bone", _K + "action_by_reason"),
    'phys': (_K + "cat_phys", _K + "effect_phys", _K + "action_by_reason"),
    'autofix': (_K + "cat_autofix", _K + "effect_autofix", _K + "action_autofix"),
}
_SUB_KEYS = {
    'tex_root_wrong':   _K + "sub_tex_root_wrong",
    'tex_missing':      _K + "sub_tex_missing",
    'tex_wrong_version': _K + "sub_tex_wrong_version",
    'tex_not_pow2':     _K + "sub_tex_not_pow2",
    'tex_unreadable':   _K + "sub_tex_unreadable",
    'tex_empty':        _K + "sub_tex_empty",
    'mat_pair':         _K + "sub_mat_pair",
    'mesh_unmatched':   _K + "sub_mesh_unmatched",
    'mat_unused':       _K + "sub_mat_unused",
    'mat_unused_fixable': _K + "sub_mat_unused_fixable",
    'mat_pair_weak':    _K + "sub_mat_pair_weak",
    'mat_outdated':     _K + "sub_mat_outdated",
    'mat_snapshot_stale': _K + "sub_mat_snapshot_stale",
    'mesh_multi_color': _K + "sub_mesh_multi_color",
    'mat_duplicate':    _K + "sub_mat_duplicate",
    'name_illegal':     _K + "sub_name_illegal",
    'unweighted':       _K + "sub_unweighted",
    'mesh_structure':   _K + "sub_mesh_structure",
    'bone_non_ascii':   _K + "sub_bone_non_ascii",
    'vgroup_no_bone':   _K + "sub_vgroup_no_bone",
    'xform_mirrored':   _K + "sub_xform_mirrored",
    'xform_degenerate': _K + "sub_xform_degenerate",
    'phys_structure':   _K + "sub_phys_structure",
    'phys_parent':      _K + "sub_phys_parent",
    'phys_bone_retarget': _K + "sub_phys_bone_retarget",
    'phys_bone_missing': _K + "sub_phys_bone_missing",
    'phys_bone_path':   _K + "sub_phys_bone_path",
    'phys_collider_bone': _K + "sub_phys_collider_bone",
    'phys_no_weight':   _K + "sub_phys_no_weight",
    'phys_duplicate':   _K + "sub_phys_duplicate",
    'phys_crossing':    _K + "sub_phys_crossing",
    'phys_clsp_unbound': _K + "sub_phys_clsp_unbound",
    'phys_link_dangling': _K + "sub_phys_link_dangling",
    'phys_single_node': _K + "sub_phys_single_node",
    **{'af_' + i: label for i, label in export_autofix.LABEL_KEYS.items()},
}


def _dialog_kwargs(title_key, confirm_key=None):
    """``title=``/``confirm_text=`` when this Blender has them (4.1+).

    Passing them unconditionally would raise TypeError on the 3.x builds
    ``bl_info["blender"]`` still admits, and the popup is perfectly usable with
    an English heading -- so this degrades rather than gates.
    """
    if not HAS_DIALOG_TITLE:
        return {}
    kwargs = {"title": T(title_key)}
    if confirm_key:
        kwargs["confirm_text"] = T(confirm_key)
    return kwargs


_enum_cache = {}


def _cached(key, items):
    # Blender keeps no reference to a callback's item strings, so a list built
    # fresh on every access can be garbage-collected mid-draw and show corrupted
    # text. Same guard mdf_port_ops uses.
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


# ── The report, as Scene data ────────────────────────────────────────────────

class PEC_ReportItem(bpy.types.PropertyGroup):
    text: StringProperty(name="")
    severity: StringProperty(name="")


class PEC_ReportGroup(bpy.types.PropertyGroup):
    #: Group code (``tex_missing``, ``name_illegal``, ...). Kept as a code so the
    #: fix button can ask "is there anything renameable here" without matching
    #: on translated text.
    sub: StringProperty(name="")
    severity: StringProperty(name="")
    items: CollectionProperty(type=PEC_ReportItem)


class PEC_ReportEntry(bpy.types.PropertyGroup):
    """One category row of the report."""
    code: StringProperty(name="")
    severity: StringProperty(name="")
    count: IntProperty(name="")
    groups: CollectionProperty(type=PEC_ReportGroup)
    #: Newline-joined object names, for the "select the problem objects" box.
    objects: StringProperty(name="")


def _cat_label(code):
    keys = _CAT_KEYS.get(code)
    return T(keys[0]) if keys else code


class MODDER_UL_PreExportCheck(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        layout.label(text=f"{_cat_label(item.code)} ({item.count})",
                     icon='ERROR' if item.severity == pr.ERROR else 'INFO')

    def invoke(self, context, event):
        # Kills double-click-to-rename, which would otherwise let the user edit
        # the category label as if it were data.
        return {'PASS_THROUGH'}


#: The inputs of the last run, so the fix operator can redo it without asking
#: again. Module-level rather than Scene data: it is per-session working state,
#: not part of the .blend.
_LAST_RUN = {}


# ── Gathering ────────────────────────────────────────────────────────────────

def _tex_config(game_code):
    """The game's texture config, but only when it can actually support the
    texture check -- see the module docstring on MHRS."""
    cfg = get_game_tex_config(game_code)
    if cfg is None or not cfg.get("vanilla_asset_rel"):
        return None
    return cfg


def _mdf_materials(col):
    return [o for o in col.objects
            if o.get("~TYPE") == "RE_MDF_MATERIAL" and getattr(o, 're_mdf_material', None)]


def _mesh_objects(col):
    # all_objects, not objects: an imported .mesh collection puts its LOD levels
    # in child collections, and those meshes export too, so their names have to
    # be just as valid.  MeshExportExclude is skipped because the exporter skips
    # it (upstream blender_re_mesh.py:1270) -- reporting it would be noise.
    return [o for o in col.all_objects
            if o.type == 'MESH' and not o.get("MeshExportExclude")]


_derived_material = export_autofix.derived_material


def _collection_items(self, context):
    items = [(c.name, f"{c.name}  ({len(_mdf_materials(c))})", "", 'OUTLINER_COLLECTION', i)
             for i, c in enumerate(mdf_material_collections())]
    if not items:
        items = [(_NONE, T(_K + "no_mdf_collection"), "", 'ERROR', 0)]
    return _cached("pec_mdf", items)


def _mesh_collection_items(self, context):
    items = [(_NONE, T(_K + "mesh_collection_none"), "", 'X', 0)]
    items += [(c.name, f"{c.name}  ({len(_mesh_objects(c))})", "", 'OUTLINER_COLLECTION', i + 1)
              for i, c in enumerate(mesh_collections())]
    return _cached("pec_mesh", items)


# ── The checks ───────────────────────────────────────────────────────────────

_REASON_KEYS = {
    pc.SPACE:              _K + "reason_space",
    pc.DOT:                _K + "reason_dot",
    pc.NON_ASCII:          _K + "reason_non_ascii",
    pc.SYMBOL:             _K + "reason_symbol",
    pc.EMPTY:              _K + "reason_empty",
    pc.SINGLE_UNDERSCORE:  _K + "reason_single_underscore",
}


def _reason_text(codes):
    return ", ".join(T(_REASON_KEYS[c]) for c in codes)


def texture_problems(bindings, cfg, natives_root):
    """Classify every binding once; the check and the 「修复贴图」 button read
    the same result.  *bindings* is ``[(part, material object)]``.

    Returns a dict of path -> ``[(part, obj, slot)]`` users per class, plus the
    per-path detail the fixes need (``wrong_version``: the file found under
    another version; ``header``: a right suffix over a wrong header version;
    ``size``; ``kind``: what an unreadable file really is).
    """
    from . import tex_repair
    version = cfg["tex_version"]
    vanilla = _load_vanilla_art_paths(cfg["vanilla_asset_rel"])

    def disk(path):
        return pc.resolve_disk_path(natives_root, path, version)

    def exists(path):
        return os.path.isfile(disk(path))

    res = {'found': {}, 'missing': {}, 'wrong_version': {}, 'header': {},
           'not_pow2': {}, 'unreadable': {}, 'empty': [], 'size': {}, 'kind': {},
           'other': {}, 'disk': {}}
    for part, obj in bindings:
        md = obj.re_mdf_material
        for b in md.textureBindingList_items:
            path = pc.normalize_tex_path(b.path)
            verdict = pc.classify_tex_binding(path, vanilla, exists)
            user = (part, obj, b.textureType)
            if verdict == pc.TEX_EMPTY:
                res['empty'].append((part, obj, md.materialName, b.textureType))
            elif verdict == pc.TEX_MISSING:
                others = tex_repair.other_versions(disk(path), version)
                if others:
                    res['wrong_version'].setdefault(path, []).append(user)
                    res['other'][path] = others[0]
                else:
                    res['missing'].setdefault(path, []).append(user)
                res['disk'][path] = disk(path)
            elif verdict == pc.TEX_FOUND:
                res['found'].setdefault(path, []).append(user)
                res['disk'][path] = disk(path)

    # Only the custom textures that resolved can be read: a vanilla path lives
    # in the game's paks.  A header read per unique path, no mip decompressed.
    for path, users in res['found'].items():
        d = res['disk'][path]
        hv = tex_repair.header_version(d)
        if hv is not None and hv != version:
            res['header'][path] = users
            res['other'][path] = (hv, d)
            continue
        size = read_tex_size(d)
        verdict = pc.classify_tex_size(size)
        if verdict == pc.TEXF_NOT_POW2:
            res['not_pow2'][path] = users
            res['size'][path] = size
        elif verdict == pc.TEXF_UNREADABLE:
            res['unreadable'][path] = users
            res['kind'][path] = tex_repair.sniff(d)
    return res


def _texture_findings(bindings, cfg, natives_root):
    """``[finding]`` for the texture half, over every part at once.

    The verdict ("nothing custom resolved -- wrong root" vs "some files are
    missing") is taken over all parts together: the mod root is one directory,
    so judging it per part could call it wrong for one part and fine for the
    next.  A texture present only under another game's version counts as
    present for that verdict: its cause is the conversion, not the root.
    """
    r = texture_problems(bindings, cfg, natives_root)
    out = []

    def emit(sub, text, path, users):
        for part, obj, _slot in users:
            out.append(pr.finding('tex', sub, text, key=path, part=part, objects=[obj.name]))

    present = len(r['found']) + len(r['wrong_version'])
    verdict = pc.texture_verdict(present, len(r['missing']))
    if verdict == pc.TEXV_ROOT_WRONG:
        # One line for the whole thing -- every path fails for the same single
        # reason -- plus the first few paths so the user can tell a wrong root
        # (complete, plausible paths) from textures never built (a short list).
        n = sum(len(v) for v in r['missing'].values())
        objs = [o.name for users in r['missing'].values() for _p, o, _s in users]
        out.append(pr.finding('tex', 'tex_root_wrong',
                              T(_K + "item_root_wrong").format(n=n, root=natives_root),
                              key='summary', objects=objs))
        for path in list(r['missing'])[:3]:
            out.append(pr.finding('tex', 'tex_root_wrong', path, key=path))
    elif verdict == pc.TEXV_MISSING:
        for path, users in r['missing'].items():
            emit('tex_missing', path, path, users)

    for path, users in r['wrong_version'].items():
        have = r['other'][path][0]
        emit('tex_wrong_version', T(_K + "item_wrong_version").format(path=path, have=have), path, users)
    for path, users in r['header'].items():
        have = r['other'][path][0]
        emit('tex_wrong_version', T(_K + "item_wrong_header").format(path=path, have=have), path, users)
    for path, users in r['not_pow2'].items():
        w, h = r['size'][path]
        emit('tex_not_pow2', f"{w}×{h}  {path}", path, users)
    for path, users in r['unreadable'].items():
        kind = r['kind'].get(path)
        if kind == 'TEX':       # a .tex header, but the size could not be read
            text = T(_K + "item_tex_corrupt").format(path=path)
        elif kind:
            text = T(_K + "item_unreadable_kind").format(path=path, kind=kind)
        else:
            text = T(_K + "item_unreadable").format(path=path)
        emit('tex_unreadable', text, path, users)

    for part, obj, mat, slot in r['empty']:
        out.append(pr.finding('tex', 'tex_empty', f"{mat}  [{slot}]",
                              key=(obj.name, slot), part=part, objects=[obj.name]))
    return out


def collection_armatures(col):
    """Armatures that are *direct* members of a mesh collection -- the only ones
    upstream's exporter looks at (``for obj in targetCollection.objects``)."""
    return [o for o in col.objects if o.type == 'ARMATURE'] if col is not None else []


def export_armature(col, meshes):
    """The armature the exporter will use for *col*: the collection's own, or
    None.  A mesh's modifier pointing elsewhere does not count -- upstream
    reports NoArmatureInCollection then (see ``_check_structure``)."""
    arms = collection_armatures(col)
    return arms[0] if arms else None


def _weighted_group_indices(obj, arm):
    """Vertex groups the exporter treats as bone weights: named after *any*
    bone of *arm* (upstream does not look at use_deform), SHAPEKEY_ groups
    excluded (a DD2 feature)."""
    if arm is None:
        return set()
    bones = arm.data.bones
    return {vg.index for vg in obj.vertex_groups
            if not vg.name.startswith("SHAPEKEY_") and vg.name in bones}


def _mirror_reason(obj):
    """Why a mirrored transform is on the list rather than auto-fixed."""
    if obj.data.users > 1:
        return T(_K + "mirror_shared")
    if obj.matrix_basis.determinant() >= 0:
        return T(_K + "mirror_parent")
    if obj.name in export_autofix.MIRROR_FAILED:
        return T(_K + "mirror_normals")
    return T(_K + "mirror_apply")


def _check_transforms(meshes, part):
    """``[finding]`` for object transforms the exporter cannot bake safely.

    Only the sign of the determinant matters -- see ``classify_transform``.
    Meshes with no authored split normals are still reported when mirrored,
    because a negative determinant also leaves the winding facing inward; they
    just lose less.  Mirrors auto-fix can bake are dropped later
    (``_apply_autofix_plan``); what is left says why it could not be.
    """
    out = []
    for obj in meshes:
        det = obj.matrix_world.determinant()
        verdict = pc.classify_transform(det)
        if verdict == pc.XFORM_MIRRORED:
            text = f"{obj.name} — {_mirror_reason(obj)}"
            if not obj.data.has_custom_normals:
                text += "  " + T(_K + "note_no_custom_normals")
            out.append(pr.finding('bone', 'xform_mirrored', text, key=obj.name,
                                  part=part, objects=[obj.name]))
        elif verdict == pc.XFORM_DEGENERATE:
            out.append(pr.finding('bone', 'xform_degenerate',
                                  T(_K + "item_degenerate").format(obj=obj.name),
                                  key=obj.name, part=part, objects=[obj.name]))
    return out


def unweighted_vertices(obj, arm):
    """Indices of *obj*'s vertices with no usable bone weight: nothing left
    once the exporter has dropped weights below ``pc.EXPORT_MIN_WEIGHT`` --
    their row comes out all zero and then gets the whole 255 added to slot 0,
    so in game they follow bone index 0 (``file_re_mesh.py:1796-1810``)."""
    idx = _weighted_group_indices(obj, arm)
    return [v.index for v in obj.data.vertices
            if not any(g.group in idx and g.weight >= pc.EXPORT_MIN_WEIGHT for g in v.groups)]


def _check_weights(meshes, part, arm):
    """``[finding]`` for vertices that carry no usable bone weight.

    Weights that merely fail to sum to 1 are *not* reported: upstream RE Mesh
    divides by the sum and then adds the rounding gap to each row's largest
    weight (``file_re_mesh.py:1796-1810``).
    """
    out = []
    if arm is None:
        return out
    for obj in meshes:
        if not len(obj.data.polygons):
            continue    # an empty submesh is reported once, under structure
        n = len(unweighted_vertices(obj, arm))
        if not n:
            continue
        text = (T(_K + "item_unweighted_all").format(obj=obj.name)
                if n == len(obj.data.vertices)
                else T(_K + "item_unweighted").format(obj=obj.name, n=n))
        out.append(pr.finding('bone', 'unweighted', text, key=obj.name, part=part,
                              objects=[obj.name]))
    return out


def _check_vertex_groups(meshes, part, arm):
    """Vertex groups with weight whose name is no bone.  Upstream maps every
    such group to remap slot 0 (``remapDict[vgName] = 0``) and keeps its
    weights, so they land on bone index 0 -- a Solidify mask or an outline
    thickness group with weights drags that bone along in game."""
    out = []
    if arm is None:
        return out
    bones = arm.data.bones
    for obj in meshes:
        bad = [vg for vg in obj.vertex_groups
               if not vg.name.startswith("SHAPEKEY_") and vg.name not in bones]
        if not bad:
            continue
        idx = {vg.index: vg.name for vg in bad}
        weighted = set()
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group in idx and g.weight >= pc.EXPORT_MIN_WEIGHT:
                    weighted.add(idx[g.group])
        for name in sorted(weighted):
            out.append(pr.finding('bone', 'vgroup_no_bone',
                                  T(_K + "item_vgroup_no_bone").format(obj=obj.name, vg=name),
                                  key=(obj.name, name), part=part, objects=[obj.name]))
    return out


#: Upstream's weighted-bone limit per .mesh (SIX_WEIGHT_GAMES get 1024).
_MAX_WEIGHTED_BONES = {'MHWS': 1024}


def _check_structure(mesh_col, meshes, part, game_code):
    """What makes upstream refuse the whole .mesh: more than one armature in
    the collection, vertex groups with no armature to map them to, a submesh
    with no vertices or faces, too many weighted bones."""
    out = []
    if mesh_col is None:
        return out
    arms = collection_armatures(mesh_col)
    label = mesh_col.name
    if len(arms) > 1:
        out.append(pr.finding('bone', 'mesh_structure',
                              T(_K + "item_many_armatures").format(col=label, n=len(arms)),
                              key=(label, 'arms'), part=part, objects=[a.name for a in arms]))
    if not arms and any(o.vertex_groups for o in meshes):
        elsewhere = next((o.find_armature() for o in meshes if o.find_armature()), None)
        key = "item_armature_outside" if elsewhere else "item_no_armature"
        out.append(pr.finding('bone', 'mesh_structure',
                              T(_K + key).format(col=label, arm=elsewhere.name if elsewhere else ""),
                              key=(label, 'noarm'), part=part, objects=[o.name for o in meshes]))
    for obj in meshes:
        if not len(obj.data.vertices) or not len(obj.data.polygons):
            out.append(pr.finding('bone', 'mesh_structure',
                                  T(_K + "item_empty_mesh").format(obj=obj.name),
                                  key=(obj.name, 'empty'), part=part, objects=[obj.name]))
    if arms:
        bones = arms[0].data.bones
        weighted = set()
        for obj in meshes:
            names = {vg.index: vg.name for vg in obj.vertex_groups if vg.name in bones}
            for v in obj.data.vertices:
                weighted.update(names[g.group] for g in v.groups if g.group in names)
        limit = _MAX_WEIGHTED_BONES.get(game_code, 256)
        if len(weighted) > limit:
            out.append(pr.finding('bone', 'mesh_structure',
                                  T(_K + "item_too_many_bones").format(col=label, n=len(weighted),
                                                                       limit=limit),
                                  key=(label, 'bones'), part=part))
    return out


def physics_bone_refs(armatures):
    """Bone names RE Chain Editor objects point at on *armatures*: node and
    collider constraint subtargets, plus the plain-string fields
    ``constraintJntName`` / ``jointHash`` Blender does not keep in sync."""
    refs = set()
    targets = set(armatures)
    for obj in bpy.data.objects:
        t = obj.get("TYPE")
        if not t or not str(t).startswith("RE_CHAIN_"):
            continue
        con = obj.constraints.get("BoneName")
        if con is not None and con.target in targets and con.subtarget:
            refs.add(con.subtarget)
        node = getattr(obj, "re_chain_chainnode", None)
        if node is not None:
            for field in ("constraintJntName", "jointHash"):
                v = getattr(node, field, "")
                if v and not v.isdigit():
                    refs.add(v)
    return refs


def _check_bone_names(armatures, part_of_arm):
    """Non-ASCII bone names (§6.2).  An error when physics refers to the bone:
    RE Chain Editor hashes it wrong and the chain points at nothing.  A note
    otherwise -- the .mesh itself carries the name as a string."""
    out = []
    if not armatures:
        return out
    names = [b.name for a in armatures for b in a.data.bones]
    plan = pc.allocate_ascii_names(names, names)
    if not plan:
        return out
    refs = physics_bone_refs(armatures)
    for old, new in plan.items():
        used = old in refs
        text = T(_K + ("item_bone_ascii_physics" if used else "item_bone_ascii")).format(old=old, new=new)
        owners = [a for a in armatures if old in a.data.bones]
        out.append(pr.finding('bone', 'bone_non_ascii', text,
                              severity=pr.ERROR if used else pr.INFO, key=old,
                              part=part_of_arm.get(owners[0].name, "") if owners else "",
                              objects=[a.name for a in owners]))
    return out


def used_materials(obj):
    """The Blender materials *obj*'s faces actually use, in slot order.  Slots no
    face points at -- common after joining and separating -- do not count."""
    me = obj.data
    mats = list(me.materials)
    if not mats:
        return []
    import numpy as np
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    out = []
    for i in sorted(set(int(i) for i in idx)):
        if 0 <= i < len(mats) and mats[i] is not None and mats[i] not in out:
            out.append(mats[i])
    return out


def material_matching(materials, meshes):
    """Everything the name checks and their fix buttons need, computed once.

    One problem is reported once: a half-done rename becomes a single "mesh
    wants X, mdf has Y" line rather than a dangling mesh *and* a dangling
    material, and a pair whose names match once legalised is left to the
    illegal-name group, whose fix resolves it.
    """
    mat_names = [o.re_mdf_material.materialName for o in materials]
    mat_by_name = {}
    for o in materials:
        mat_by_name.setdefault(o.re_mdf_material.materialName, []).append(o)
    mesh_entries = [(o, *_derived_material(o)) for o in meshes]
    illegal = {n for n in mat_names if pc.name_problems(n)}
    illegal |= {m for _o, m, _how in mesh_entries if pc.name_problems(m)}
    paired, rest_meshes, rest_mats = [], [], []
    if meshes:
        unmatched, unused = pc.match_meshes_to_materials(
            [(o.name, mat) for o, mat, _how in mesh_entries], mat_names)
        paired, rest_meshes, rest_mats = pc.pair_unmatched(unmatched, unused)
        paired = [p for p in paired
                  if not ((p[1] in illegal or p[2] in illegal)
                          and pc.fix_name(p[1]) == pc.fix_name(p[2]))]
    # A pair made only because one of each was left over cannot tell a half-done
    # rename from a new material meeting a genuinely unused one (measured: after
    # the other fixes, "Skirt" -- a new material -- got paired with a leftover
    # "cloth", and aligning would have renamed it to cloth). Those stay pairs
    # for the report line, but the generate and delete fixes still see them.
    def similar(a, b):
        a, b = a or '', b or ''
        return a.lower() == b.lower() or pc.fix_name(a).lower() == pc.fix_name(b).lower()
    weak = [p for p in paired if not similar(p[1], p[2])]
    rest_mats = list(dict.fromkeys(rest_mats))
    return {'mat_names': mat_names, 'mat_by_name': mat_by_name,
            'mesh_entries': mesh_entries, 'illegal': illegal,
            'paired': paired, 'weak': weak,
            'rest_meshes': rest_meshes, 'rest_mats': rest_mats,
            'open_meshes': rest_meshes + [(o, w) for o, w, _h in weak],
            'open_mats': rest_mats + [h for _o, _w, h in weak if h not in rest_mats]}


def unused_by_blender_material(name, meshes, mat_names):
    """Meshes in the same collection that can take mdf material *name* because
    their Blender material is called that (Blender's .NNN ignored) -- §5.2
    direction a.  Two ways in: faces joined into a mesh named after another
    material (several used materials: separating fixes it), or a single-material
    mesh named after something the mdf does not have.  A single-material mesh
    that already matches another mdf material is left out: renaming it would
    only move the dangling material somewhere else."""
    out = []
    names = set(mat_names)
    for o in meshes:
        mats = used_materials(o)
        if not any(pc.strip_dedup_suffix(m.name) == name for m in mats):
            continue
        if len(mats) > 1 or _derived_material(o)[0] not in names:
            out.append(o)
    return out


def _elsewhere(name, own_col, part_of):
    """Where else *name* is asked for, as display names (§5.2 direction b)."""
    out = []
    for col in mesh_collections():
        if col is own_col:
            continue
        for o in _mesh_objects(col):
            mat, _how = _derived_material(o)
            if mat == name or any(pc.strip_dedup_suffix(m.name) == name for m in used_materials(o)):
                out.append(part_of.get(col.name, col.name))
                break
    return out


def _check_names_and_matching(materials, meshes, part, mesh_col=None, part_of=None):
    """``[finding]`` for everything that is about names: matching in both
    directions, legality on both sides, and duplicates."""
    out = []
    m = material_matching(materials, meshes)
    mat_by_name = m['mat_by_name']

    # ── legality, both sides ──
    for obj in materials:
        name = obj.re_mdf_material.materialName
        problems = pc.name_problems(name)
        if problems:
            out.append(pr.finding(
                'mat', 'name_illegal',
                f"{T(_K + 'side_mdf')} {name} — {_reason_text(problems)}",
                key=('mdf', obj.name), part=part, objects=[obj.name]))
    for obj, mat, how in m['mesh_entries']:
        problems = list(pc.name_problems(mat))
        if how == 'single_underscore':
            problems.insert(0, pc.SINGLE_UNDERSCORE)
        if problems:
            out.append(pr.finding(
                'mat', 'name_illegal',
                f"{T(_K + 'side_mesh')} {obj.name} — {_reason_text(problems)}",
                key=('mesh', obj.name), part=part, objects=[obj.name]))

    # ── matching, both directions ──
    for obj_name, want, have in m['paired']:
        weak = (obj_name, want, have) in m['weak']
        out.append(pr.finding(
            'mat', 'mat_pair_weak' if weak else 'mat_pair',
            T(_K + ("item_pair_weak" if weak else "item_pair")).format(
                mesh=want or T(_K + "no_name"), mdf=have),
            key=(obj_name, have), part=part,
            objects=[obj_name] + [o.name for o in mat_by_name.get(have, [])]))
    for obj_name, want in m['rest_meshes']:
        out.append(pr.finding(
            'mat', 'mesh_unmatched',
            T(_K + "item_mesh_unmatched").format(obj=obj_name, mat=want or T(_K + "no_name")),
            key=obj_name, part=part, objects=[obj_name]))
    for name in m['rest_mats']:
        text = T(_K + "item_mat_unused").format(mat=name)
        fixable = unused_by_blender_material(name, meshes, m['mat_names'])
        if fixable:
            text += T(_K + "hint_unused_blender").format(obj=fixable[0].name)
        else:
            where = _elsewhere(name, mesh_col, part_of or {})
            if where:
                text += T(_K + "hint_unused_elsewhere").format(where=", ".join(where[:3]))
        out.append(pr.finding(
            'mat', 'mat_unused_fixable' if fixable else 'mat_unused', text,
            key=name, part=part,
            objects=[o.name for o in mat_by_name.get(name, [])] + [o.name for o in fixable]))

    # ── duplicates, each name with how often it repeats ──
    for name in pc.duplicate_material_names(m['mat_names']):
        out.append(pr.finding(
            'mat', 'mat_duplicate',
            T(_K + "item_mat_duplicate").format(mat=name, n=m['mat_names'].count(name)),
            key=name, part=part, objects=[o.name for o in mat_by_name.get(name, [])]))
    return out


# ── Several base colours behind one material name (§5.2.3) ──────────────────

_file_hashes = {}


def _same_file(a, b):
    """Two paths holding the same bytes -- one image copied under two names."""
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    if sa.st_size != sb.st_size:
        return False
    import hashlib

    def digest(p, st):
        key = (p, st.st_mtime_ns, st.st_size)
        if key not in _file_hashes:
            h = hashlib.sha1()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            _file_hashes[key] = h.digest()
        return _file_hashes[key]
    return digest(a, sa) == digest(b, sb)


def base_color_identity(mat):
    """What a material shows as its base colour: ``('IMAGE', path)``,
    ``('SOLID', rgb)`` or ``('UNKNOWN',)``.  Read the way the MDF generator
    reads it -- first an Image Texture named after an albedo slot (what RE Mesh
    Editor's importer writes), then the generator's own shader analysis -- so
    the check and the generator agree on what counts as the same base colour."""
    from .slot_sources import find_slot_images
    from .mdf_generator_base import analyze_material_strategies, _is_albedo_slot
    from .mdf_tex_processor_base import BASE_SLOT_CHANNEL_MAPS
    if mat is None:
        return ('UNKNOWN',)
    albedo = sorted(s for s in BASE_SLOT_CHANNEL_MAPS if _is_albedo_slot(s, BASE_SLOT_CHANNEL_MAPS))
    found = find_slot_images(mat, albedo)
    if found:
        return ('IMAGE', os.path.normcase(os.path.abspath(found[sorted(found)[0]])))
    try:
        strat = analyze_material_strategies(mat).get('color')
    except Exception:
        return ('UNKNOWN',)
    if strat and strat[0] == 'DIRECT' and strat[1]:
        return ('IMAGE', os.path.normcase(os.path.abspath(strat[1])))
    if strat and strat[0] == 'SOLID':
        v = strat[1]
        try:
            return ('SOLID', tuple(round(float(x), 2) for x in list(v)[:3]))
        except TypeError:
            return ('SOLID', (round(float(v), 2),))
    return ('UNKNOWN',)


def distinct_base_colors(mats):
    """How many genuinely different base colours *mats* show; 0 when any of
    them cannot be read (reporting then would be a guess)."""
    ids = [base_color_identity(m) for m in mats]
    if any(i[0] == 'UNKNOWN' for i in ids):
        return 0
    distinct = []
    for i in ids:
        if any(i == d or (i[0] == d[0] == 'IMAGE' and _same_file(i[1], d[1])) for d in distinct):
            continue
        distinct.append(i)
    return len(distinct)


def _check_multi_color(meshes, part):
    out = []
    for obj in meshes:
        mats = used_materials(obj)
        if len(mats) < 2:
            continue
        n = distinct_base_colors(mats)
        if n < 2:
            continue
        _mat, how = _derived_material(obj)
        key = "item_multi_color_fallback" if how == 'no_format' else "item_multi_color"
        out.append(pr.finding('mat', 'mesh_multi_color',
                              T(_K + key).format(obj=obj.name, n=n),
                              severity=pr.INFO, key=obj.name, part=part, objects=[obj.name]))
    return out


# ── Outdated materials (§5.2.2) ───────────────────────────────────────────────

_OUTDATED_KEYS = {
    mdf_layouts.PADDING:  _K + "outdated_padding",
    mdf_layouts.PROPS:    _K + "outdated_props",
    mdf_layouts.ORDER:    _K + "outdated_order",
    mdf_layouts.TEXTURES: _K + "outdated_textures",
}


def _check_outdated(materials, part, game_code):
    out = []
    if mdf_layouts.snapshot(game_code) is None or not materials:
        return out
    if mdf_layouts.freshness(game_code) == mdf_layouts.STALE:
        # Judging against a snapshot older than the installed game would report
        # current materials as outdated. One note instead, pointing at RE Asset
        # Library's own updater, which reads the live paks.
        out.append(pr.finding(
            'mat', 'mat_snapshot_stale',
            T(_K + "item_snapshot_stale").format(snap=mdf_layouts.snapshot_label(game_code)),
            severity=pr.INFO, key='stale'))
        return out
    for obj in materials:
        md = obj.re_mdf_material
        sample = mdf_layouts.sample_for(game_code, md.mmtrPath)
        if sample is None:
            continue
        reasons = mdf_layouts.diff(md, sample)
        if reasons:
            out.append(pr.finding(
                'mat', 'mat_outdated',
                f"{md.materialName} — " + ", ".join(T(_OUTDATED_KEYS[r]) for r in reasons),
                key=obj.name, part=part, objects=[obj.name]))
    return out


def _skipped_notes(game_code, natives_root, any_without_mesh):
    notes = []
    cfg = _tex_config(game_code)
    if cfg is None:
        notes.append(T(_K + "skip_tex_no_config").format(game=game_code))
    elif not natives_root:
        notes.append(T(_K + "skip_tex_no_root"))
    if any_without_mesh:
        notes.append(T(_K + "skip_match_no_mesh"))
    return notes


#: Auto-fix items whose problem is a real error when left unfixed; the rest
#: (triangulation, weight tidying, vertex colour fill) are notes.
_AUTOFIX_SEVERE = {'MIRROR', 'TEX_EMPTY', 'PHYS_TARGET'}

_AUTOFIX_UNITS = {
    'TRIANGULATE': "core.export_autofix.n_meshes",
    'WEIGHTS':     "core.export_autofix.n_meshes",
    'MIRROR':      "core.export_autofix.n_meshes",
    'VCOLOR':      "core.export_autofix.n_meshes",
    'TEX_PATHS':   "core.export_autofix.n_paths",
    'TEX_EMPTY':   "core.export_autofix.n_slots",
    'MAT_NAMES':   "core.export_autofix.n_names",
    'PHYS_TARGET': "core.export_autofix.n_constraints",
}


def _apply_autofix_plan(findings, fx_plan, enabled):
    """Judge the state *after* auto-fix (docs/pre_export_check_plan.md §3.2).

    What a fix covers leaves the problem list either way: switched on, the
    export fixes it; switched off, it moves to the 「可自动修复」 category as one
    line per item, so a problem is still only reported once.  Returns
    ``(findings, number of items the export will fix)``.
    """
    kept = []
    for f in findings:
        if f['sub'] == 'xform_mirrored' and f['objects'] and f['objects'][0] in fx_plan.mirror_fixable:
            continue
        if f['sub'] == 'tex_empty' and f['key'] in fx_plan.empty_fixable:
            continue
        if f['sub'] == 'name_illegal' and 'MAT_NAMES' in enabled:
            continue
        if (f['sub'] == 'phys_structure' and f['key'][2:] == ('constraint_no_target',)
                and f['key'][1] in fx_plan.target_fixable):
            continue
        kept.append(f)

    on = fx_plan.pending(enabled - {'LEGACY'})
    off = fx_plan.pending({i for i in _AUTOFIX_UNITS
                           if i not in enabled and i not in export_autofix.SILENT_WHEN_OFF})
    for item_id, n in off.items():
        kept.append(pr.finding(
            'autofix', 'af_' + item_id,
            T(export_autofix.LABEL_KEYS[item_id]) + " — " + T(_AUTOFIX_UNITS[item_id]).format(n=n),
            severity=pr.ERROR if item_id in _AUTOFIX_SEVERE else pr.INFO, key=item_id))
    return kept, sum(on.values())


def export_armatures(pairs, autofix_pairs=None, physics=None):
    """Every armature this export writes against, once: the mesh collections'
    own, over the check pairs, the auto-fix pairs (mesh-only parts) and the
    physics parts."""
    out = []
    cols = [m for _l, _d, m in list(pairs) + list(autofix_pairs or [])]
    cols += [p.mesh for p in (physics or {}).get('parts', [])]
    for col in cols:
        arm = pphys.collection_armature(col)
        if arm is not None and arm not in out:
            out.append(arm)
    return out


def run_checks_multi(context, game_code, pairs, natives_root, autofix_pairs=None, physics=None):
    """``(report, skipped, autofix_n)`` over ``(part label, mdf_col, mesh_col)`` pairs.

    A single-pair run passes ``""`` as the label, which keeps the part prefix
    off every line.  ``skipped`` is the human-readable reason for each check
    that did not run; it depends on the game and the shared mod root only, so
    it is collected once rather than once per part.  ``autofix_n`` is how many
    items the export's auto-fix will handle (0 for games without auto-fix).

    *autofix_pairs* is what auto-fix itself runs over -- the batch dialogs pass
    every bound part, including mesh-only ones the check pairs leave out.
    *physics* is ``{'parts': [PhysPart], 'runtime_bones': names, ...}`` from a
    dialog that binds chain2 / clsp (MHWS), else None.
    """
    findings = []
    bindings = []
    part_of = {mesh_col.name: label for label, _m, mesh_col in pairs if mesh_col is not None and label}
    armatures, part_of_arm = [], {}
    for label, mdf_col, mesh_col in pairs:
        materials = _mdf_materials(mdf_col)
        meshes = _mesh_objects(mesh_col) if mesh_col is not None else []
        arm = export_armature(mesh_col, meshes)
        if arm is not None and arm not in armatures:
            armatures.append(arm)
            part_of_arm[arm.name] = label
        bindings += [(label, o) for o in materials]
        findings += _check_names_and_matching(materials, meshes, label, mesh_col, part_of)
        findings += _check_multi_color(meshes, label)
        findings += _check_outdated(materials, label, game_code)
        findings += _check_structure(mesh_col, meshes, label, game_code)
        findings += _check_vertex_groups(meshes, label, arm)
        findings += _check_weights(meshes, label, arm)
        findings += _check_transforms(meshes, label)
    findings += _check_bone_names(armatures, part_of_arm)
    if physics:
        findings += pphys.check(physics.get('parts'), export_armatures(pairs, autofix_pairs, physics),
                                physics.get('runtime_bones', ()))

    cfg = _tex_config(game_code)
    if cfg is not None and natives_root:
        findings += _texture_findings(bindings, cfg, natives_root)

    autofix_n = 0
    enabled = export_autofix.enabled_items(context, game_code)
    if enabled is not None:
        fx_plan = export_autofix.plan(context, game_code, autofix_pairs or pairs,
                                      (physics or {}).get('parts'))
        findings, autofix_n = _apply_autofix_plan(findings, fx_plan, enabled)

    skipped = _skipped_notes(game_code, natives_root,
                             any(mesh_col is None for _l, _m, mesh_col in pairs))
    return pr.build_report(findings, _SUB_ORDER), skipped, autofix_n


def run_checks(context, game_code, mdf_col, mesh_col, natives_root):
    """Single-pair form of ``run_checks_multi``, for the standalone dialog."""
    return run_checks_multi(context, game_code, [("", mdf_col, mesh_col)], natives_root)


def _names(pairs):
    return [(label, mdf.name if mdf else "", mesh.name if mesh else "")
            for label, mdf, mesh in pairs]


def _cols_from_names(named):
    out = []
    for label, mdf_name, mesh_name in named:
        mdf = bpy.data.collections.get(mdf_name) if mdf_name else None
        mesh = bpy.data.collections.get(mesh_name) if mesh_name else None
        if mdf is not None or mesh is not None:
            out.append((label, mdf, mesh))
    return out


def _physics_names(physics):
    """*physics* with its collections replaced by names, for ``_LAST_RUN``."""
    if not physics:
        return None
    n = lambda c: c.name if c is not None else ""
    return dict(physics, parts=[(p.label, p.part_id, n(p.chain), n(p.clsp), n(p.mesh), p.clsp_slot)
                                for p in physics.get('parts', [])])


def _physics_from_names(named):
    if not named:
        return None
    get = lambda name: bpy.data.collections.get(name) if name else None
    return dict(named, parts=[pphys.PhysPart(label, pid, get(c), get(s), get(m), slot)
                              for label, pid, c, s, m, slot in named.get('parts', [])])


def gather_and_check(context, game_code, pairs, natives_root, autofix_pairs=None, hints=None,
                     physics=None):
    """Run the aggregated check over ``pairs`` and remember enough in
    ``_LAST_RUN`` -- a plain module dict, not Scene/ID data -- for a later
    "View Details" click to redo the check and populate the Scene-backed
    report.

    Deliberately does **not** call ``_store()`` here: this runs from a batch
    export dialog's ``draw()``, and Blender raises "Writing to ID classes in
    this context is not allowed" if a draw call writes to a Scene property
    such as ``scene.mtk_pec_report`` (measured directly -- the standalone
    check's own input dialog never hit this because it writes from
    ``execute()``, never from ``draw()``). The write has to wait for an
    operator's ``execute()``, which is what ``MODDER_OT_PreExportCheckView``
    is for.
    """
    report, skipped, autofix_n = run_checks_multi(context, game_code, pairs, natives_root,
                                                  autofix_pairs, physics)
    _LAST_RUN.clear()
    _LAST_RUN.update({
        'game': game_code,
        'root': natives_root,
        'pairs': _names(pairs),
        'autofix_pairs': _names(autofix_pairs) if autofix_pairs else None,
        'physics': _physics_names(physics),
    })
    # Context only the calling dialog knows, for the fix buttons -- e.g. the
    # armor's folder as the last-resort texture path for quick generate.
    _LAST_RUN.update(hints or {})
    return report, skipped, autofix_n


def ensure_checked(op, context, game_code, pairs, natives_root, autofix_pairs=None,
                   hints=None, physics=None):
    """Run (or reuse) the aggregated check for ``pairs``, caching the result on
    ``op`` -- the calling batch export dialog operator, whose instance already
    lives exactly as long as the popup does -- keyed by a fingerprint of
    ``(natives_root, pairs)``. Redrawing a dialog happens on far more than
    property changes (hovering a button is enough on some Blender versions),
    and the checks underneath do real disk I/O per texture path, so
    recomputing unconditionally on every draw() would make picking a
    collection feel laggy on a large batch.

    Returns the report, so a caller that flags rows in its own part list can
    pass it to ``pre_export_report.parts_with_errors`` before
    ``draw_summary_row`` draws the total.
    """
    enabled = export_autofix.enabled_items(context, game_code)
    named = _physics_names(physics)
    fingerprint = (natives_root, tuple(_names(pairs)),
                   tuple(_names(autofix_pairs)) if autofix_pairs else None,
                   tuple(sorted(enabled)) if enabled is not None else None,
                   tuple(named['parts']) if named else None)
    if getattr(op, '_pec_fingerprint', None) != fingerprint:
        report, skipped, autofix_n = gather_and_check(context, game_code, pairs, natives_root,
                                                      autofix_pairs, hints, physics)
        op._pec_fingerprint = fingerprint
        op._pec_report = report
        op._pec_summary = pr.summary(report)
        op._pec_autofix_n = autofix_n
        op._pec_has_skips = bool(skipped)
    return op._pec_report


def _draw_summary_label(row, n_err, n_info, n_fix=0):
    """The one-line verdict shared by the batch dialogs and the report:
    ``⚠ 2 类需要处理 · 1 条提示 · 导出时将自动处理 12 项``."""
    fix = (" · " + T(_K + "sum_autofix").format(n=n_fix)) if n_fix else ""
    if n_err:
        text = T(_K + "sum_errors").format(n=n_err)
        if n_info:
            text += " · " + T(_K + "sum_infos").format(n=n_info)
        row.label(text=text + fix, icon='ERROR')
    elif n_info:
        row.label(text=T(_K + "sum_infos").format(n=n_info) + fix, icon='INFO')
    else:
        row.label(text=T(_K + "all_clear") + fix, icon='CHECKMARK')


def draw_summary_row(op, layout):
    """The one-line summary + "view details" button meant to be the very last
    thing a batch export dialog draws, right above Blender's own OK/Cancel.
    Call ``ensure_checked`` first so ``op._pec_summary``/``_pec_has_skips`` are
    current."""
    layout.separator()
    row = layout.row(align=True)
    n_err, n_info = op._pec_summary
    _draw_summary_label(row, n_err, n_info, getattr(op, '_pec_autofix_n', 0))
    if n_err or n_info or op._pec_has_skips:
        row.operator("modder.pre_export_check_view", text=T(_K + "btn_view_details"))


def draw_inline_summary(op, layout, context, game_code, pairs, natives_root,
                        autofix_pairs=None, hints=None, physics=None):
    """``ensure_checked`` + ``draw_summary_row``, for dialogs (MHWS, MHRS) that
    have no per-part list of their own to annotate before the summary line."""
    ensure_checked(op, context, game_code, pairs, natives_root, autofix_pairs, hints, physics)
    draw_summary_row(op, layout)


def _pairs_from_last_run():
    return [p for p in _cols_from_names(_LAST_RUN.get('pairs', [])) if p[1] is not None]


def _autofix_pairs_from_last_run():
    named = _LAST_RUN.get('autofix_pairs')
    return _cols_from_names(named) if named else None


def _physics_from_last_run():
    return _physics_from_names(_LAST_RUN.get('physics'))


def _rerun_and_store(context):
    report, skipped, autofix_n = run_checks_multi(
        context, _LAST_RUN.get('game', ""), _pairs_from_last_run(), _LAST_RUN.get('root', ""),
        _autofix_pairs_from_last_run(), _physics_from_last_run())
    _store(context, report, skipped)
    _LAST_RUN['autofix_n'] = autofix_n


class MODDER_OT_PreExportCheckView(bpy.types.Operator):
    """The batch export dialogs' "View Details" button.

    ``gather_and_check`` (called from ``draw()``) cannot populate
    ``scene.mtk_pec_report`` itself -- Blender rejects a Scene write from a
    draw callback -- so it only leaves ``_LAST_RUN`` with what a real
    ``execute()`` needs to redo the check and store it properly: the game
    code, the mod root, and each pair's collections by name.
    """
    bl_idname = "modder.pre_export_check_view"
    bl_label = "View Pre-export Check"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "report_desc")

    def execute(self, context):
        _rerun_and_store(context)
        bpy.ops.modder.pre_export_check_report('INVOKE_DEFAULT')
        return {'FINISHED'}


def _store(context, report, skipped):
    scene = context.scene
    scene.mtk_pec_report.clear()
    used_by = T(_K + "item_used_by")
    joiner = T(_K + "part_joiner")
    for cat in report:
        entry = scene.mtk_pec_report.add()
        entry.code = cat['code']
        entry.severity = cat['severity']
        entry.count = cat['count']
        entry.objects = "\n".join(cat['objects'])
        for grp in cat['groups']:
            g = entry.groups.add()
            g.sub = grp['sub']
            g.severity = grp['severity']
            for it in grp['items']:
                row = g.items.add()
                row.text = pr.item_line(it, used_by=used_by, joiner=joiner)
                row.severity = it['severity']
    scene.mtk_pec_report_index = 0
    _LAST_RUN['skipped'] = skipped


# ── Input dialog ─────────────────────────────────────────────────────────────

class MODDER_OT_PreExportCheck(bpy.types.Operator):
    bl_idname = "modder.pre_export_check"
    bl_label = "Pre-export Check"
    #: No 'UNDO': it only reads, and the report it opens is a separate operator.
    bl_options = {'REGISTER'}

    source_game: StringProperty(options={'HIDDEN'})
    mdf_collection: EnumProperty(name="MDF Collection", items=_collection_items)
    mesh_collection: EnumProperty(name="Mesh Collection", items=_mesh_collection_items)

    @classmethod
    def description(cls, context, properties):
        return T(_K + "desc")

    @classmethod
    def poll(cls, context):
        return bool(mdf_material_collections())

    def _prefill(self, context):
        """Default both pickers off the active object's own collections.

        A .mesh and its .mdf2 are separate collections, so the active object can
        only ever fill one of them -- but they are conventionally named after
        the same asset (``ch03_012_0012.mesh`` / ``ch03_012_0012.mdf2``), so the
        stem of whichever one was found is used to look for its counterpart.
        """
        obj = context.active_object
        if obj is None:
            return
        stem = ""
        for col in obj.users_collection:
            if col in mdf_material_collections():
                self.mdf_collection = col.name
                stem = col.name.rsplit(".", 1)[0]
            elif col in mesh_collections():
                self.mesh_collection = col.name
                stem = col.name.rsplit(".", 1)[0]
        if not stem:
            return
        for col in mdf_material_collections():
            if col.name.rsplit(".", 1)[0] == stem:
                self.mdf_collection = col.name
                break
        for col in mesh_collections():
            if col.name.rsplit(".", 1)[0] == stem:
                self.mesh_collection = col.name
                break

    def invoke(self, context, event):
        self._prefill(context)
        return context.window_manager.invoke_props_dialog(
            self, width=460,
            **_dialog_kwargs(_K + "title", _K + "confirm_run"))

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "mdf_collection", text=T(_K + "label_mdf_collection"))
        col.prop(self, "mesh_collection", text=T(_K + "label_mesh_collection"))

        col.separator()
        cfg = _tex_config(self.source_game)
        natives_root = ""
        if cfg is not None:
            natives_root = context.scene.get(cfg["natives_root_key"], "")
            _draw_mod_root_row(col, context, self.source_game, cfg, show_hint=True)

        # What this click will actually do, recomputed as the inputs change --
        # a skipped check has to be visible *before* the report comes back
        # empty, or an untouched check reads as a passed one.
        col.separator()
        box = col.box()
        box.label(text=T(_K + "will_run"), icon='CHECKMARK')
        if cfg is None:
            box.label(text=T(_K + "skip_tex_no_config").format(game=self.source_game),
                      icon='DOT')
        elif not natives_root:
            box.label(text=T(_K + "skip_tex_no_root"), icon='DOT')
        else:
            box.label(text=T(_K + "run_tex"), icon='CHECKMARK')
        if self.mesh_collection == _NONE:
            box.label(text=T(_K + "skip_match_no_mesh"), icon='DOT')
        else:
            box.label(text=T(_K + "run_match"), icon='CHECKMARK')
        box.label(text=T(_K + "run_names"), icon='CHECKMARK')

    def execute(self, context):
        mdf_col = bpy.data.collections.get(self.mdf_collection)
        if mdf_col is None:
            self.report({'ERROR'}, T(_K + "no_mdf_collection"))
            return {'CANCELLED'}
        mesh_col = (None if self.mesh_collection == _NONE
                    else bpy.data.collections.get(self.mesh_collection))

        cfg = _tex_config(self.source_game)
        natives_root = context.scene.get(cfg["natives_root_key"], "") if cfg else ""

        _LAST_RUN.clear()
        _LAST_RUN.update({
            'game': self.source_game,
            'root': natives_root,
            'pairs': [("", mdf_col.name, mesh_col.name if mesh_col else "")],
            'autofix_pairs': None,
        })
        _rerun_and_store(context)
        bpy.ops.modder.pre_export_check_report('INVOKE_DEFAULT')
        return {'FINISHED'}


# ── Report dialog ────────────────────────────────────────────────────────────

def _visual_width(ch):
    """1 column for a normal-width glyph, 2 for CJK/fullwidth ones -- Blender's
    UI font renders those roughly twice as wide as Latin glyphs. A plain
    character count under-estimates how much room an all-Chinese line needs
    (measured: a Chinese explanation with no spaces at all, so textwrap's
    word-wrap never got a chance to break it, just sliced every N characters
    regardless of how wide they actually were -- Blender's label widget then
    silently ellipsis-clipped whatever didn't fit)."""
    cp = ord(ch)
    if (0x1100 <= cp <= 0x115F or 0x2E80 <= cp <= 0xA4CF or
            0xAC00 <= cp <= 0xD7A3 or 0xF900 <= cp <= 0xFAFF or
            0xFF00 <= cp <= 0xFF60 or 0xFFE0 <= cp <= 0xFFE6):
        return 2
    return 1


def _wrap_line(line, width):
    """Word-wrap ``line`` to a visual-width budget rather than a character
    count -- a plain ``textwrap.wrap`` treats a CJK glyph the same as a Latin
    one, so a Chinese line reliably overflows the box it was wrapped for."""
    out = []
    cur = ""
    cur_w = 0
    for ch in line:
        w = _visual_width(ch)
        if cur and cur_w + w > width:
            out.append(cur)
            cur = ""
            cur_w = 0
        cur += ch
        cur_w += w
    if cur:
        out.append(cur)
    return out or [""]


def _wrap_width(context):
    """Visual-width budget for one wrapped line in the detail box (col2, at
    ``SPLIT_FACTOR`` of ``WINDOW_SIZE``), in the same units ``_visual_width``
    counts in. ``PX_PER_UNIT`` is calibrated against Blender's default UI font
    at 100% scale -- live-verified against a real natives_root path mixed with
    an all-Chinese explanation line, both of which used to get clipped."""
    ui_scale = context.preferences.view.ui_scale
    box_px = WINDOW_SIZE * (1 - SPLIT_FACTOR)
    padding_px = 40  # box() margins plus the scrollbar the left column may show
    px_per_unit = 7.5
    return max(10, int((box_px - padding_px) / (px_per_unit * ui_scale)))


def _has_group(report, sub):
    return any(g.sub == sub for e in report for g in e.groups)


#: Fix buttons per group code.  Drawn for the *selected* category only: with a
#: button per repair, showing all of them at once would bury the one that
#: belongs to what the user is looking at.
_ACTIONS = {
    'name_illegal':       ("modder.pre_export_check_fix",   "btn_fix",            'FILE_REFRESH'),
    'mat_pair':           ("modder.pec_align_names",        "btn_align",          'SORTALPHA'),
    'mat_unused_fixable': ("modder.pec_fix_unused_blender", "btn_unused_blender", 'MATERIAL'),
    'mesh_unmatched':     ("modder.pec_quick_generate",     "btn_quick_generate", 'SHADING_TEXTURE'),
    'mesh_multi_color':   ("modder.pec_separate_recheck",   "btn_separate",       'MOD_EXPLODE'),
    'mat_outdated':       ("modder.pec_update_outdated",    "btn_outdated",       'FILE_REFRESH'),
    'bone_non_ascii':     ("modder.pec_ascii_bones",        "btn_ascii_bones",    'BONE_DATA'),
    'tex_wrong_version':  ("modder.pec_fix_textures",       "btn_fix_textures",   'TEXTURE'),
    'tex_not_pow2':       ("modder.pec_fix_textures",       "btn_fix_textures",   'TEXTURE'),
    'tex_unreadable':     ("modder.pec_fix_textures",       "btn_fix_textures",   'TEXTURE'),
    'unweighted':         ("modder.pec_select_unweighted",  "btn_select_unweighted", 'RESTRICT_SELECT_OFF'),
    'phys_parent':        ("modder.pec_phys_reparent",      "btn_phys_reparent",  'CON_CHILDOF'),
    'phys_bone_retarget': ("modder.pec_phys_retarget",      "btn_phys_retarget",  'BONE_DATA'),
    'phys_duplicate':     ("modder.pec_phys_dedupe",        "btn_phys_dedupe",    'TRASH'),
    'phys_crossing':      ("modder.pec_phys_select_crossing", "btn_phys_select_crossing", 'RESTRICT_SELECT_OFF'),
    'phys_clsp_unbound':  ("modder.pec_phys_bind_clsp",     "btn_phys_bind_clsp", 'LINKED'),
    'phys_single_node':   ("modder.pec_phys_remove_single", "btn_phys_remove_single", 'TRASH'),
}


def _draw_actions(layout, report, entry):
    from .mdf_generator_base import generator_for
    subs = [g.sub for g in entry.groups]
    drawn = set()
    for sub in subs:
        action = _ACTIONS.get(sub)
        if action is None or action[0] in drawn:
            continue
        if action[0] == "modder.pec_quick_generate" and generator_for(_LAST_RUN.get('game', "")) is None:
            continue
        if action[0] == "modder.pec_phys_bind_clsp" and not callable(
                (_LAST_RUN.get('physics') or {}).get('bind_clsp')):
            continue
        layout.operator(action[0], text=T(_K + action[1]), icon=action[2])
        drawn.add(action[0])
    if 'mat_pair_weak' in subs:
        # Could be a half-done rename or a new material next to an unused one:
        # offer all three and let the user say which.
        for idname, key, icon in (("modder.pec_align_names", "btn_align", 'SORTALPHA'),
                                  ("modder.pec_quick_generate", "btn_quick_generate", 'SHADING_TEXTURE')):
            if idname in drawn:
                continue
            if idname == "modder.pec_quick_generate" and generator_for(_LAST_RUN.get('game', "")) is None:
                continue
            layout.operator(idname, text=T(_K + key), icon=icon)
            drawn.add(idname)
    if {'mat_unused', 'mat_unused_fixable', 'mat_pair_weak'} & set(subs):
        layout.operator("modder.pec_delete_unused", text=T(_K + "btn_delete_unused"), icon='TRASH')
    if 'name_illegal' in subs:
        layout.label(text=T(_K + "fix_datablock_note"), icon='INFO')
    if 'mat_snapshot_stale' in subs and 'blender_mdf_updater' in dir(bpy.ops.re_asset):
        layout.operator("re_asset.blender_mdf_updater", text=T(_K + "btn_upstream_updater"),
                        icon='FILE_REFRESH')
    if 'mat_outdated' in subs:
        layout.label(text=T(_K + "outdated_snapshot").format(
            snap=mdf_layouts.snapshot_label(_LAST_RUN.get('game', ""))), icon='INFO')
    if entry.code == 'autofix':
        listed = _listed_autofix(report)
        if listed - export_autofix.TEMPORARY:
            layout.operator("modder.pre_export_autofix_now",
                            text=T(_K + "btn_autofix_now"), icon='BRUSH_DATA')
        if listed & export_autofix.TEMPORARY:
            layout.label(text=T(_K + "autofix_temp_note"), icon='INFO')


def _listed_autofix(report):
    """Item ids listed in the 「可自动修复」 category."""
    return {g.sub[3:] for e in report if e.code == 'autofix' for g in e.groups}


class MODDER_OT_PreExportCheckReport(bpy.types.Operator):
    bl_idname = "modder.pre_export_check_report"
    bl_label = "Pre-export Check Report"
    bl_options = {'REGISTER'}

    #: On by default: opening this check at all means the user intends to deal
    #: with what it finds, and one checkbox covers every category so there is no
    #: "which half does OK apply to" ambiguity.
    select_problems: BoolProperty(default=True)

    @classmethod
    def description(cls, context, properties):
        return T(_K + "report_desc")

    def invoke(self, context, event):
        # Centre the popup on the window instead of at the mouse -- at 750px it
        # otherwise opens half off-screen when the click was near an edge.
        window = context.window
        window.cursor_warp(window.width // 2, window.height // 2)
        return context.window_manager.invoke_props_dialog(
            self, width=WINDOW_SIZE,
            **_dialog_kwargs(_K + "report_title", _K + "confirm_done"))

    def _draw_detail(self, box, entry, width):
        """Consequence, what to do, then each group. Returns rows drawn, so the
        category list can be made as tall as the detail beside it."""
        rows = 0
        keys = _CAT_KEYS.get(entry.code)
        if keys:
            for key in keys[1:]:
                for chunk in _wrap_line(T(key), width):
                    box.label(text=chunk)
                    rows += 1
        for grp in entry.groups:
            box.separator()
            title = T(_SUB_KEYS.get(grp.sub, grp.sub))
            box.label(text=f"{title} ({len(grp.items)})",
                      icon='ERROR' if grp.severity == pr.ERROR else 'INFO')
            rows += 2
            for it in grp.items:
                for chunk in _wrap_line(it.text, width - 2):
                    box.label(text="    " + chunk)
                    rows += 1
        return rows

    def draw(self, context):
        layout = self.layout
        report = context.scene.mtk_pec_report
        n_err = sum(1 for e in report if e.severity == pr.ERROR)
        n_info = sum(len(g.items) for e in report for g in e.groups
                     if g.severity == pr.INFO)

        _draw_summary_label(layout.row(), n_err, n_info, _LAST_RUN.get('autofix_n', 0))
        for note in _LAST_RUN.get('skipped', []):
            layout.label(text=note, icon='DOT')
        if not len(report):
            return

        layout.separator()
        split = layout.split(factor=SPLIT_FACTOR)
        col1, col2 = split.column(), split.column()

        idx = min(context.scene.mtk_pec_report_index, len(report) - 1)
        rows = 2 + self._draw_detail(col2.box(), report[idx], _wrap_width(context))

        # rows follows the detail length so the list never ends up a stub next
        # to a tall box -- and because it scrolls, nothing has to be truncated.
        col1.template_list("MODDER_UL_PreExportCheck", "", context.scene, "mtk_pec_report",
                           context.scene, "mtk_pec_report_index",
                           rows=max(4, min(rows, 28)))

        layout.separator()
        _draw_actions(layout, report, report[idx])
        layout.prop(self, "select_problems", text=T(_K + "chk_select"))

    def execute(self, context):
        if not self.select_problems:
            return {'FINISHED'}
        names = set()
        for entry in context.scene.mtk_pec_report:
            names.update(n for n in entry.objects.splitlines() if n)

        selected = 0
        for obj in context.view_layer.objects:
            try:
                obj.select_set(obj.name in names)
            except RuntimeError:
                # Hidden or in an excluded collection -- not selectable, and not
                # worth failing the whole confirm over.
                continue
            if obj.name in names:
                selected += 1
        if selected:
            self.report({'INFO'}, T(_K + "selected_n").format(n=selected))
        return {'FINISHED'}


# ── Fix ──────────────────────────────────────────────────────────────────────

_fix_pair = export_autofix.fix_names


class MODDER_OT_PreExportCheckFix(bpy.types.Operator):
    bl_idname = "modder.pre_export_check_fix"
    bl_label = "Fix Illegal Names"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "fix_desc")

    def execute(self, context):
        pairs = _pairs_from_last_run()
        if not pairs:
            self.report({'ERROR'}, T(_K + "no_mdf_collection"))
            return {'CANCELLED'}
        n_mat = n_obj = n_data = 0
        for _label, mdf_col, mesh_col in pairs:
            a, b, c = _fix_pair(mdf_col, mesh_col)
            n_mat += a; n_obj += b; n_data += c

        # Re-run in place: the popup is still open (an operator button does not
        # close it), so rewriting the Scene collection is all the refresh the
        # report needs.
        _rerun_and_store(context)
        self.report({'INFO'}, T(_K + "fix_done").format(mat=n_mat, obj=n_obj, data=n_data))
        return {'FINISHED'}


class MODDER_OT_PreExportAutofixNow(bpy.types.Operator):
    """「立即修复」 in the report: run the auto-fix items that are switched off
    but listed, once, without touching the export options.  Temporary items
    (triangulation, vertex colour fill) only exist during an export and are
    skipped.  Re-runs the check in place, like the name fix."""
    bl_idname = "modder.pre_export_autofix_now"
    bl_label = "Fix Now"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "autofix_now_desc")

    def execute(self, context):
        game = _LAST_RUN.get('game', "")
        ids = _listed_autofix(context.scene.mtk_pec_report) - export_autofix.TEMPORARY
        enabled = export_autofix.enabled_items(context, game) or set()
        if 'LEGACY' in enabled:
            ids.add('LEGACY')
        pairs = _autofix_pairs_from_last_run() or _pairs_from_last_run()
        done = export_autofix.apply(context, game, pairs, ids,
                                    (_physics_from_last_run() or {}).get('parts'))
        _rerun_and_store(context)
        self.report({'INFO'}, T(_K + "autofix_done").format(n=sum(done.values())))
        return {'FINISHED'}


classes = [PEC_ReportItem, PEC_ReportGroup, PEC_ReportEntry, MODDER_UL_PreExportCheck,
           MODDER_OT_PreExportCheck, MODDER_OT_PreExportCheckReport,
           MODDER_OT_PreExportCheckView, MODDER_OT_PreExportCheckFix,
           MODDER_OT_PreExportAutofixNow]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mtk_pec_report = CollectionProperty(type=PEC_ReportEntry)
    bpy.types.Scene.mtk_pec_report_index = IntProperty(name="")


def unregister():
    del bpy.types.Scene.mtk_pec_report_index
    del bpy.types.Scene.mtk_pec_report
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
