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
import textwrap

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, StringProperty)

from .i18n import T
from .compat import HAS_DIALOG_TITLE
from . import pre_export_check as pc
from .mdf_material_convert_base import _load_vanilla_art_paths
from .mdf_port_tex import get_game_tex_config
from .mdf_port_ops import mdf_material_collections, _draw_mod_root_row
from .mesh_port_ops import mesh_collections

_K = "core.pre_export_check_ops."

#: Same geometry MHWME's error window uses -- wide enough that a full texture
#: path fits on one wrapped line, split so the category list stays narrow.
WINDOW_SIZE = 750
SPLIT_FACTOR = 0.35

#: Sentinel for "no mesh collection", which is a legal choice: the user may only
#: want the texture check.
_NONE = "NONE"

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

class PEC_ReportEntry(bpy.types.PropertyGroup):
    #: Category code (``tex_missing``, ``name_illegal``, ...). Kept next to the
    #: display label so the fix button can ask "is there anything renameable
    #: here" without matching on translated text.
    code: StringProperty(name="")
    label: StringProperty(name="")
    count: IntProperty(name="")
    detail: StringProperty(name="")
    #: Newline-joined object names, for the "select the problem objects" box.
    objects: StringProperty(name="")


class MODDER_UL_PreExportCheck(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        layout.label(text=f"{item.label} ({item.count})")

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
    # be just as valid.
    return [o for o in col.all_objects if o.type == 'MESH']


def _derived_material(obj):
    """``(material_name, how)`` for one mesh -- the object name first, the
    Blender material as the fallback RE Mesh's exporter also uses."""
    mat_name, how = pc.parse_mesh_name(obj.name)
    if how != 'no_format':
        return mat_name, how
    mats = [m for m in obj.data.materials if m is not None]
    if not mats:
        return '', 'no_format'
    # Multi-material meshes take the first, matching the exporter; the extra
    # slots are reported separately as their own finding.
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

#: Reason code -> its own i18n key. Spelled out rather than built by pasting the
#: code onto a prefix: a half-built key is invisible to the table check in
#: tests/test_ui_translated.py, so a renamed reason code would reach the user as
#: a raw key string instead of failing the suite.
_REASON_KEYS = {
    pc.SPACE:              _K + "reason_space",
    pc.DOT:                _K + "reason_dot",
    pc.LEADING_UNDERSCORE: _K + "reason_leading_underscore",
    pc.EMPTY:              _K + "reason_empty",
    pc.SINGLE_UNDERSCORE:  _K + "reason_single_underscore",
}


def _reason_text(codes):
    return ", ".join(T(_REASON_KEYS[c]) for c in codes)


def _check_textures(materials, cfg, natives_root):
    """``[entry]`` for the texture half. Empty when nothing is wrong."""
    tex_version = cfg["tex_version"]
    vanilla = _load_vanilla_art_paths(cfg["vanilla_asset_rel"])

    def exists(path):
        return os.path.isfile(pc.resolve_disk_path(natives_root, path, tex_version))

    n_found = 0
    missing = []   # (obj, material name, slot, path)
    empty = []     # (obj, material name, slot)
    for obj in materials:
        md = obj.re_mdf_material
        mat_name = md.materialName
        for b in md.textureBindingList_items:
            verdict = pc.classify_tex_binding(b.path, vanilla, exists)
            if verdict == pc.TEX_FOUND:
                n_found += 1
            elif verdict == pc.TEX_MISSING:
                missing.append((obj, mat_name, b.textureType, b.path))
            elif verdict == pc.TEX_EMPTY:
                empty.append((obj, mat_name, b.textureType))

    entries = []
    verdict = pc.texture_verdict(n_found, len(missing))
    if verdict == pc.TEXV_ROOT_WRONG:
        # Deliberately lists no paths: every one of them is wrong for the same
        # single reason, and forty lines would bury it.
        entries.append({
            'code': 'tex_root_wrong',
            'label': T(_K + "cat_tex_root_wrong"),
            'count': len(missing),
            'detail': T(_K + "desc_tex_root_wrong").format(n=len(missing), root=natives_root),
            'objects': [o.name for o, _m, _s, _p in missing],
        })
    elif verdict == pc.TEXV_MISSING:
        entries.append({
            'code': 'tex_missing',
            'label': T(_K + "cat_tex_missing"),
            'count': len(missing),
            'detail': T(_K + "desc_tex_missing") + "\n\n" + "\n".join(
                f"{mat}  [{slot}]  {path}" for _o, mat, slot, path in missing),
            'objects': [o.name for o, _m, _s, _p in missing],
        })

    if empty:
        entries.append({
            'code': 'tex_empty',
            'label': T(_K + "cat_tex_empty"),
            'count': len(empty),
            'detail': T(_K + "desc_tex_empty") + "\n\n" + "\n".join(
                f"{mat}  [{slot}]" for _o, mat, slot in empty),
            'objects': [o.name for o, _m, _s in empty],
        })
    return entries


def _check_names_and_matching(materials, meshes):
    """``[entry]`` for everything that is about names: matching in both
    directions, legality on both sides, duplicates, and multi-material meshes."""
    entries = []
    mat_names = [o.re_mdf_material.materialName for o in materials]
    mat_by_name = {}
    for o in materials:
        mat_by_name.setdefault(o.re_mdf_material.materialName, []).append(o)

    mesh_entries = [(o, *_derived_material(o)) for o in meshes]

    # ── matching, both directions ──
    if meshes:
        pairs = [(o.name, mat) for o, mat, _how in mesh_entries]
        unmatched, unused = pc.match_meshes_to_materials(pairs, mat_names)
        if unmatched:
            entries.append({
                'code': 'mesh_unmatched',
                'label': T(_K + "cat_mesh_unmatched"),
                'count': len(unmatched),
                'detail': T(_K + "desc_mesh_unmatched") + "\n\n" + "\n".join(
                    f"{obj}  ->  {mat or T(_K + 'no_name')}" for obj, mat in unmatched),
                'objects': [obj for obj, _m in unmatched],
            })
        if unused:
            entries.append({
                'code': 'mat_unmatched',
                'label': T(_K + "cat_mat_unmatched"),
                'count': len(unused),
                'detail': T(_K + "desc_mat_unmatched") + "\n\n" + "\n".join(unused),
                'objects': [o.name for n in unused for o in mat_by_name.get(n, [])],
            })

    # ── duplicates: a count only, by decision -- the names add nothing here ──
    dupes = pc.duplicate_material_names(mat_names)
    if dupes:
        entries.append({
            'code': 'mat_duplicate',
            'label': T(_K + "cat_mat_duplicate"),
            'count': len(dupes),
            'detail': T(_K + "desc_mat_duplicate").format(n=len(dupes)),
            'objects': [o.name for n in dupes for o in mat_by_name.get(n, [])],
        })

    # ── legality, both sides ──
    bad = []      # (display line, object name)
    for obj in materials:
        name = obj.re_mdf_material.materialName
        problems = pc.name_problems(name)
        if problems:
            bad.append((T(_K + "side_mdf") + f"  {name}  --  {_reason_text(problems)}", obj.name))
    for obj, mat, how in mesh_entries:
        problems = list(pc.name_problems(mat))
        if how == 'single_underscore':
            problems.insert(0, pc.SINGLE_UNDERSCORE)
        if problems:
            bad.append((T(_K + "side_mesh") + f"  {obj.name}  --  {_reason_text(problems)}",
                        obj.name))
    if bad:
        entries.append({
            'code': 'name_illegal',
            'label': T(_K + "cat_name_illegal"),
            'count': len(bad),
            'detail': T(_K + "desc_name_illegal") + "\n\n" + "\n".join(line for line, _o in bad),
            'objects': [o for _line, o in bad],
        })

    # ── multi-material meshes ──
    multi = [o for o in meshes if len([m for m in o.data.materials if m is not None]) > 1]
    if multi:
        entries.append({
            'code': 'mesh_multi',
            'label': T(_K + "cat_mesh_multi"),
            'count': len(multi),
            'detail': T(_K + "desc_mesh_multi") + "\n\n" + "\n".join(o.name for o in multi),
            'objects': [o.name for o in multi],
        })
    return entries


def run_checks(context, game_code, mdf_col, mesh_col, natives_root):
    """``(entries, skipped)`` -- the findings, and the human-readable reason for
    each check that did not run."""
    materials = _mdf_materials(mdf_col)
    meshes = _mesh_objects(mesh_col) if mesh_col is not None else []

    entries = []
    skipped = []

    cfg = _tex_config(game_code)
    if cfg is None:
        skipped.append(T(_K + "skip_tex_no_config").format(game=game_code))
    elif not natives_root:
        skipped.append(T(_K + "skip_tex_no_root"))
    else:
        entries += _check_textures(materials, cfg, natives_root)

    if mesh_col is None:
        skipped.append(T(_K + "skip_match_no_mesh"))
    entries += _check_names_and_matching(materials, meshes)
    return entries, skipped


def _store(context, entries, skipped):
    scene = context.scene
    scene.mtk_pec_report.clear()
    for e in entries:
        item = scene.mtk_pec_report.add()
        item.code = e['code']
        item.label = e['label']
        item.count = e['count']
        item.detail = e['detail']
        # dict.fromkeys, not set(): the report should list objects in the order
        # they were found, and a set would reshuffle it differently each run.
        item.objects = "\n".join(dict.fromkeys(e['objects']))
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

        entries, skipped = run_checks(context, self.source_game, mdf_col, mesh_col, natives_root)
        _LAST_RUN.update({
            'game': self.source_game,
            'mdf': mdf_col.name,
            'mesh': mesh_col.name if mesh_col else "",
            'root': natives_root,
        })
        _store(context, entries, skipped)
        bpy.ops.modder.pre_export_check_report('INVOKE_DEFAULT')
        return {'FINISHED'}


# ── Report dialog ────────────────────────────────────────────────────────────

def _wrap_width(context):
    ui_scale = context.preferences.view.ui_scale
    return int((WINDOW_SIZE * (1 - SPLIT_FACTOR) * (2 - SPLIT_FACTOR)) // (9 * ui_scale))


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

    def draw(self, context):
        layout = self.layout
        report = context.scene.mtk_pec_report
        total = sum(e.count for e in report)

        if not len(report):
            layout.label(text=T(_K + "all_clear"), icon='CHECKMARK')
        else:
            layout.label(text=T(_K + "n_issues").format(n=total), icon='ERROR')
        for note in _LAST_RUN.get('skipped', []):
            layout.label(text=note, icon='DOT')
        if not len(report):
            return

        layout.separator()
        split = layout.split(factor=SPLIT_FACTOR)
        col1, col2 = split.column(), split.column()

        row_count = 2
        idx = min(context.scene.mtk_pec_report_index, len(report) - 1)
        item = report[idx]
        width = _wrap_width(context)

        box = col2.box()
        for line in item.detail.splitlines():
            line = line.strip()
            if not line:
                box.separator()
                row_count += 1
                continue
            for chunk in textwrap.wrap(line, width=width) or [""]:
                box.label(text=chunk)
                row_count += 1

        # rows follows the detail length so the list never ends up a stub next
        # to a tall box -- and because it scrolls, nothing has to be truncated.
        col1.template_list("MODDER_UL_PreExportCheck", "", context.scene, "mtk_pec_report",
                           context.scene, "mtk_pec_report_index",
                           rows=max(6, min(row_count, 28)))

        layout.separator()
        if any(e.code == 'name_illegal' for e in report):
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

class MODDER_OT_PreExportCheckFix(bpy.types.Operator):
    bl_idname = "modder.pre_export_check_fix"
    bl_label = "Fix Illegal Names"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "fix_desc")

    def execute(self, context):
        mdf_col = bpy.data.collections.get(_LAST_RUN.get('mdf', ""))
        if mdf_col is None:
            self.report({'ERROR'}, T(_K + "no_mdf_collection"))
            return {'CANCELLED'}
        mesh_col = bpy.data.collections.get(_LAST_RUN.get('mesh', "")) or None

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

        # Re-run in place: the popup is still open (an operator button does not
        # close it), so rewriting the Scene collection is all the refresh the
        # report needs.
        entries, skipped = run_checks(context, _LAST_RUN.get('game', ""), mdf_col, mesh_col,
                                      _LAST_RUN.get('root', ""))
        _store(context, entries, skipped)
        _LAST_RUN['skipped'] = skipped

        self.report({'INFO'}, T(_K + "fix_done").format(mat=n_mat, obj=n_obj, data=n_data))
        return {'FINISHED'}


classes = [PEC_ReportEntry, MODDER_UL_PreExportCheck, MODDER_OT_PreExportCheck,
           MODDER_OT_PreExportCheckReport, MODDER_OT_PreExportCheckFix]


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
