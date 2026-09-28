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
    'tex_root_wrong', 'tex_missing', 'tex_not_pow2', 'tex_unreadable', 'tex_empty',
    'mat_pair', 'mesh_unmatched', 'mat_unused', 'mat_duplicate', 'name_illegal',
    'unweighted', 'xform_mirrored', 'xform_degenerate',
)

#: Category and group codes -> their i18n keys.  Spelled out rather than built
#: by pasting the code onto a prefix: a half-built key is invisible to the table
#: check in tests/test_ui_translated.py, so a renamed code would reach the user
#: as a raw key string instead of failing the suite.
_CAT_KEYS = {
    'tex':  (_K + "cat_tex",  _K + "effect_tex",  _K + "action_tex"),
    'mat':  (_K + "cat_mat",  _K + "effect_mat",  _K + "action_mat"),
    'bone': (_K + "cat_bone", _K + "effect_bone", _K + "action_by_reason"),
}
_SUB_KEYS = {
    'tex_root_wrong':   _K + "sub_tex_root_wrong",
    'tex_missing':      _K + "sub_tex_missing",
    'tex_not_pow2':     _K + "sub_tex_not_pow2",
    'tex_unreadable':   _K + "sub_tex_unreadable",
    'tex_empty':        _K + "sub_tex_empty",
    'mat_pair':         _K + "sub_mat_pair",
    'mesh_unmatched':   _K + "sub_mesh_unmatched",
    'mat_unused':       _K + "sub_mat_unused",
    'mat_duplicate':    _K + "sub_mat_duplicate",
    'name_illegal':     _K + "sub_name_illegal",
    'unweighted':       _K + "sub_unweighted",
    'xform_mirrored':   _K + "sub_xform_mirrored",
    'xform_degenerate': _K + "sub_xform_degenerate",
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


def _derived_material(obj):
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
    pc.LEADING_UNDERSCORE: _K + "reason_leading_underscore",
    pc.EMPTY:              _K + "reason_empty",
    pc.SINGLE_UNDERSCORE:  _K + "reason_single_underscore",
}


def _reason_text(codes):
    return ", ".join(T(_REASON_KEYS[c]) for c in codes)


def _texture_findings(bindings, cfg, natives_root):
    """``[finding]`` for the texture half, over every part at once.

    *bindings* is ``[(part, material object)]``.  The verdict ("nothing custom
    resolved -- wrong root" vs "some files are missing") is taken over all
    parts together: the mod root is one directory, so judging it per part could
    call it wrong for one part and fine for the next.
    """
    tex_version = cfg["tex_version"]
    vanilla = _load_vanilla_art_paths(cfg["vanilla_asset_rel"])

    def exists(path):
        return os.path.isfile(pc.resolve_disk_path(natives_root, path, tex_version))

    found = {}     # path -> [(part, obj)]; the same file is usually bound many times
    missing = {}   # path -> [(part, obj)]
    empty = []     # (part, obj, material name, slot)
    for part, obj in bindings:
        md = obj.re_mdf_material
        for b in md.textureBindingList_items:
            path = pc.normalize_tex_path(b.path)
            verdict = pc.classify_tex_binding(path, vanilla, exists)
            if verdict == pc.TEX_FOUND:
                found.setdefault(path, []).append((part, obj))
            elif verdict == pc.TEX_MISSING:
                missing.setdefault(path, []).append((part, obj))
            elif verdict == pc.TEX_EMPTY:
                empty.append((part, obj, md.materialName, b.textureType))

    out = []
    verdict = pc.texture_verdict(len(found), len(missing))
    if verdict == pc.TEXV_ROOT_WRONG:
        # One line for the whole thing -- every path fails for the same single
        # reason -- plus the first few paths so the user can tell a wrong root
        # (complete, plausible paths) from textures never built (a short list).
        n = sum(len(v) for v in missing.values())
        objs = [o.name for users in missing.values() for _p, o in users]
        out.append(pr.finding('tex', 'tex_root_wrong',
                              T(_K + "item_root_wrong").format(n=n, root=natives_root),
                              key='summary', objects=objs))
        for path in list(missing)[:3]:
            out.append(pr.finding('tex', 'tex_root_wrong', path, key=path))
    elif verdict == pc.TEXV_MISSING:
        for path, users in missing.items():
            for part, obj in users:
                out.append(pr.finding('tex', 'tex_missing', path, key=path,
                                      part=part, objects=[obj.name]))

    # Only the custom textures that resolved can be read: a vanilla path lives in
    # the game's paks.  One 40-byte header read per unique path.
    for path, users in found.items():
        size = read_tex_size(pc.resolve_disk_path(natives_root, path, tex_version))
        size_verdict = pc.classify_tex_size(size)
        if size_verdict == pc.TEXF_OK:
            continue
        if size_verdict == pc.TEXF_NOT_POW2:
            sub, text = 'tex_not_pow2', f"{size[0]}×{size[1]}  {path}"
        else:
            sub, text = 'tex_unreadable', T(_K + "item_unreadable").format(path=path)
        for part, obj in users:
            out.append(pr.finding('tex', sub, text, key=path, part=part,
                                  objects=[obj.name]))

    for part, obj, mat, slot in empty:
        out.append(pr.finding('tex', 'tex_empty', f"{mat}  [{slot}]",
                              key=(obj.name, slot), part=part, objects=[obj.name]))
    return out


def _check_transforms(meshes, part):
    """``[finding]`` for object transforms the exporter cannot bake safely.

    Only the sign of the determinant matters -- see ``classify_transform``.
    Meshes with no authored split normals are still reported when mirrored,
    because a negative determinant also leaves the winding facing inward; they
    just lose less.
    """
    out = []
    for obj in meshes:
        det = obj.matrix_world.determinant()
        verdict = pc.classify_transform(det)
        if verdict == pc.XFORM_MIRRORED:
            text = f"{obj.name}  det={det:.3f}"
            if not obj.data.has_custom_normals:
                text += "  " + T(_K + "note_no_custom_normals")
            out.append(pr.finding('bone', 'xform_mirrored', text, key=obj.name,
                                  part=part, objects=[obj.name]))
        elif verdict == pc.XFORM_DEGENERATE:
            out.append(pr.finding('bone', 'xform_degenerate',
                                  T(_K + "item_degenerate").format(obj=obj.name),
                                  key=obj.name, part=part, objects=[obj.name]))
    return out


def _check_weights(meshes, part):
    """``[finding]`` for vertices that carry no usable deform weight.

    Weights that merely fail to sum to 1 are *not* reported: upstream RE Mesh
    divides by the sum and then adds the rounding gap to each row's largest
    weight (``file_re_mesh.py:1796-1810``).  What does break is a vertex with
    nothing left once the exporter has dropped weights below
    ``pc.EXPORT_MIN_WEIGHT`` -- its row comes out all zero, then gets the whole
    255 added to slot 0, so in game it follows bone index 0.
    """
    out = []
    for obj in meshes:
        arm = obj.find_armature()
        if arm is None:
            continue
        idx = weight_utils.deform_group_indices(obj, arm)
        if not idx:
            continue
        n = 0
        for v in obj.data.vertices:
            if not any(g.group in idx and g.weight >= pc.EXPORT_MIN_WEIGHT for g in v.groups):
                n += 1
        if n:
            out.append(pr.finding('bone', 'unweighted',
                                  T(_K + "item_unweighted").format(obj=obj.name, n=n),
                                  key=obj.name, part=part, objects=[obj.name]))
    return out


def _check_names_and_matching(materials, meshes, part):
    """``[finding]`` for everything that is about names: matching in both
    directions, legality on both sides, and duplicates.

    One problem is reported once: a half-done rename becomes a single "mesh
    wants X, mdf has Y" line rather than a dangling mesh *and* a dangling
    material, and a pair whose names match once legalised is left to the
    illegal-name group, whose fix button resolves it.
    """
    out = []
    mat_names = [o.re_mdf_material.materialName for o in materials]
    mat_by_name = {}
    for o in materials:
        mat_by_name.setdefault(o.re_mdf_material.materialName, []).append(o)
    mesh_entries = [(o, *_derived_material(o)) for o in meshes]

    # ── legality, both sides ──
    illegal_names = set()
    for obj in materials:
        name = obj.re_mdf_material.materialName
        problems = pc.name_problems(name)
        if problems:
            illegal_names.add(name)
            out.append(pr.finding(
                'mat', 'name_illegal',
                f"{T(_K + 'side_mdf')} {name} — {_reason_text(problems)}",
                key=('mdf', obj.name), part=part, objects=[obj.name]))
    for obj, mat, how in mesh_entries:
        problems = list(pc.name_problems(mat))
        if how == 'single_underscore':
            problems.insert(0, pc.SINGLE_UNDERSCORE)
        if problems:
            illegal_names.add(mat)
            out.append(pr.finding(
                'mat', 'name_illegal',
                f"{T(_K + 'side_mesh')} {obj.name} — {_reason_text(problems)}",
                key=('mesh', obj.name), part=part, objects=[obj.name]))

    # ── matching, both directions ──
    if meshes:
        pairs = [(o.name, mat) for o, mat, _how in mesh_entries]
        unmatched, unused = pc.match_meshes_to_materials(pairs, mat_names)
        paired, rest_meshes, rest_mats = pc.pair_unmatched(unmatched, unused)
        for obj_name, want, have in paired:
            if (want in illegal_names or have in illegal_names) \
                    and pc.fix_name(want) == pc.fix_name(have):
                continue    # the name fix makes them match
            out.append(pr.finding(
                'mat', 'mat_pair',
                T(_K + "item_pair").format(mesh=want or T(_K + "no_name"), mdf=have),
                key=(obj_name, have), part=part,
                objects=[obj_name] + [o.name for o in mat_by_name.get(have, [])]))
        for obj_name, want in rest_meshes:
            out.append(pr.finding(
                'mat', 'mesh_unmatched',
                T(_K + "item_mesh_unmatched").format(obj=obj_name,
                                                     mat=want or T(_K + "no_name")),
                key=obj_name, part=part, objects=[obj_name]))
        for name in rest_mats:
            out.append(pr.finding(
                'mat', 'mat_unused', T(_K + "item_mat_unused").format(mat=name),
                key=name, part=part,
                objects=[o.name for o in mat_by_name.get(name, [])]))

    # ── duplicates, each name with how often it repeats ──
    for name in pc.duplicate_material_names(mat_names):
        out.append(pr.finding(
            'mat', 'mat_duplicate',
            T(_K + "item_mat_duplicate").format(mat=name, n=mat_names.count(name)),
            key=name, part=part, objects=[o.name for o in mat_by_name.get(name, [])]))
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


def run_checks_multi(context, game_code, pairs, natives_root):
    """``(report, skipped)`` over ``(part label, mdf_col, mesh_col)`` pairs.

    A single-pair run passes ``""`` as the label, which keeps the part prefix
    off every line.  ``skipped`` is the human-readable reason for each check
    that did not run; it depends on the game and the shared mod root only, so
    it is collected once rather than once per part.
    """
    findings = []
    bindings = []
    for label, mdf_col, mesh_col in pairs:
        materials = _mdf_materials(mdf_col)
        meshes = _mesh_objects(mesh_col) if mesh_col is not None else []
        bindings += [(label, o) for o in materials]
        findings += _check_names_and_matching(materials, meshes, label)
        findings += _check_weights(meshes, label)
        findings += _check_transforms(meshes, label)

    cfg = _tex_config(game_code)
    if cfg is not None and natives_root:
        findings += _texture_findings(bindings, cfg, natives_root)

    skipped = _skipped_notes(game_code, natives_root,
                             any(mesh_col is None for _l, _m, mesh_col in pairs))
    return pr.build_report(findings, _SUB_ORDER), skipped


def run_checks(context, game_code, mdf_col, mesh_col, natives_root):
    """Single-pair form of ``run_checks_multi``, for the standalone dialog."""
    return run_checks_multi(context, game_code, [("", mdf_col, mesh_col)], natives_root)


def gather_and_check(context, game_code, pairs, natives_root):
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
    report, skipped = run_checks_multi(context, game_code, pairs, natives_root)
    _LAST_RUN.clear()
    _LAST_RUN.update({
        'game': game_code,
        'root': natives_root,
        'pairs': [(label, mdf_col.name, mesh_col.name if mesh_col else "")
                  for label, mdf_col, mesh_col in pairs],
    })
    return report, skipped


def ensure_checked(op, context, game_code, pairs, natives_root):
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
    fingerprint = (natives_root, tuple(
        (label, mdf_col.name, mesh_col.name if mesh_col else "")
        for label, mdf_col, mesh_col in pairs))
    if getattr(op, '_pec_fingerprint', None) != fingerprint:
        report, skipped = gather_and_check(context, game_code, pairs, natives_root)
        op._pec_fingerprint = fingerprint
        op._pec_report = report
        op._pec_summary = pr.summary(report)
        op._pec_has_skips = bool(skipped)
    return op._pec_report


def _draw_summary_label(row, n_err, n_info):
    """The one-line verdict shared by the batch dialogs and the report."""
    if n_err:
        text = T(_K + "sum_errors").format(n=n_err)
        if n_info:
            text += " · " + T(_K + "sum_infos").format(n=n_info)
        row.label(text=text, icon='ERROR')
    elif n_info:
        row.label(text=T(_K + "sum_infos").format(n=n_info), icon='INFO')
    else:
        row.label(text=T(_K + "all_clear"), icon='CHECKMARK')


def draw_summary_row(op, layout):
    """The one-line summary + "view details" button meant to be the very last
    thing a batch export dialog draws, right above Blender's own OK/Cancel.
    Call ``ensure_checked`` first so ``op._pec_summary``/``_pec_has_skips`` are
    current."""
    layout.separator()
    row = layout.row(align=True)
    n_err, n_info = op._pec_summary
    _draw_summary_label(row, n_err, n_info)
    if n_err or n_info or op._pec_has_skips:
        row.operator("modder.pre_export_check_view", text=T(_K + "btn_view_details"))


def draw_inline_summary(op, layout, context, game_code, pairs, natives_root):
    """``ensure_checked`` + ``draw_summary_row``, for dialogs (MHWS, MHRS) that
    have no per-part list of their own to annotate before the summary line."""
    ensure_checked(op, context, game_code, pairs, natives_root)
    draw_summary_row(op, layout)


def _pairs_from_last_run():
    pairs = []
    for label, mdf_name, mesh_name in _LAST_RUN.get('pairs', []):
        mdf_col = bpy.data.collections.get(mdf_name)
        if mdf_col is None:
            continue
        mesh_col = bpy.data.collections.get(mesh_name) or None
        pairs.append((label, mdf_col, mesh_col))
    return pairs


def _rerun_and_store(context):
    report, skipped = run_checks_multi(context, _LAST_RUN.get('game', ""),
                                       _pairs_from_last_run(), _LAST_RUN.get('root', ""))
    _store(context, report, skipped)


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

        _draw_summary_label(layout.row(), n_err, n_info)
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
        if _has_group(report, 'name_illegal'):
            layout.operator("modder.pre_export_check_fix",
                            text=T(_K + "btn_fix"), icon='FILE_REFRESH')
            layout.label(text=T(_K + "fix_datablock_note"), icon='INFO')
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

def _fix_pair(mdf_col, mesh_col):
    """Correct illegal names on one (mdf_col, mesh_col) pair in place.
    Returns ``(n_mat, n_obj, n_data)``."""
    materials = _mdf_materials(mdf_col)
    meshes = _mesh_objects(mesh_col) if mesh_col is not None else []
    mesh_entries = [(o, *_derived_material(o)) for o in meshes]

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


classes = [PEC_ReportItem, PEC_ReportGroup, PEC_ReportEntry, MODDER_UL_PreExportCheck,
           MODDER_OT_PreExportCheck, MODDER_OT_PreExportCheckReport,
           MODDER_OT_PreExportCheckView, MODDER_OT_PreExportCheckFix]


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
