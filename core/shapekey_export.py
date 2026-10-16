"""Shape keys in batch export: the export mode, which keys go out, and the SKS
preset written next to the mod.

Shape-key (blendshape) export exists only in the RE-Mesh-Editor-BlendShape fork.
The fork announces it per game in its module-level ``REME_FEATURES`` and takes the
mode as ``exportfile``'s ``shapeKeyExportMode``; on any other REME the option is
greyed out and nothing extra is passed, so the export is what it always was.

Which keys go out is done without touching the fork: its exporter already skips
muted keys (and ``DUMMY_`` names and locked keys, which it bakes instead), so a
filter mutes the keys it leaves out for the length of one mesh export and puts
the flags back afterwards; the filters that force expression keys out unmute and
unlock them for that time too.  The split between expression (表情) and sculpt
(捏脸) keys is ShapeKeySystem's own, see :mod:`core.sks_profiles`.

For the games SKS supports, the export can also write an SKS preset into the mod
(``reframework/data/ShapeKeySystem/mods/<model>/``): a sculpt preset holding the
current values of the exported sculpt keys, and the model's binding naming the
expression profile and that preset.

The batch exporters wrap their run in :func:`session`; the mesh export helpers
call :func:`filtered` and :func:`export_kwargs`, which do nothing outside one.
"""

import sys
from contextlib import contextmanager

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .i18n import T
from . import sks_profiles
from .re_mesh_compat import get_re_mesh_category

#: game code -> the fork's feature key, the settings attribute on
#: ``scene.mhw_suite_settings``, and for SKS games the adapter id, the Steam
#: folder, and how SKS names the model (None = from the export).
GAMES = {
    "MHWS": {"feature": "wilds_blendshape_export", "prop": "mhws_shapekeys",
             "sks": "mhwilds", "steam": "MonsterHunterWilds"},
    "ONI":  {"feature": "oniwots_blendshape_export", "prop": "oni_shapekeys",
             "sks": "onimusha_wots", "steam": "OnimushaWotS", "model": "musashi"},
    "RE4":  {"feature": "re4_blendshape_export", "prop": "re4_shapekeys"},
    "RE9":  {"feature": "re9_blendshape_export", "prop": "re9_shapekeys"},
    "MHRS": {"feature": "mhrise_blendshape_export", "prop": "mhrs_shapekeys",
             "sks": "mhrise", "steam": "MonsterHunterRise"},
}

#: The fork's shapeKeyExportMode values offered, with their enum numbers (kept
#: from when NO and KEEPNORMALS were offered too, so saved choices still read).
#: "Don't export" is the ``export`` checkbox, passed as NO.  MODE0 is the fork's
#: broken legacy mode and is never passed.
MODES = (("MODE1", 1), ("KEEPNORMALS_SURFACE", 3))
DEFAULT_MODE = "KEEPNORMALS_SURFACE"    # the fork's own default
NO_MODE = "NO"
#: Key filters with their enum numbers (FOLLOW was ALL; EXPR_SCULPT is new).
FILTERS = (("FOLLOW", 0), ("EXPR_SCULPT", 3), ("EXPRESSION", 1), ("SCULPT", 2))
#: Filters that need an expression profile; without one they act as FOLLOW.
NEEDS_PROFILE = ("EXPR_SCULPT", "EXPRESSION")
DUMMY_PREFIX = "DUMMY_"
#: Sculpt keys at this value or below count as 0 (left out by the sculpt filters).
ZERO = 1e-6
#: SKS clamps sculpt values to its slider cap, which goes up to 5 (Sculpt.lua).
SCULPT_MAX = 5.0


# ── What the installed REME can do ───────────────────────────────────────────

def reme_features():
    """The fork's ``REME_FEATURES`` from whichever enabled addon carries it."""
    for name in bpy.context.preferences.addons.keys():
        feats = getattr(sys.modules.get(name), "REME_FEATURES", None)
        if isinstance(feats, dict):
            return feats
    return {}


def available_modes(game):
    """Modes the installed REME takes for *game* (from :data:`MODES`); [] when
    it exports none or cannot be told not to."""
    if reme_features().get(GAMES[game]["feature"], 0) < 1:
        return []
    cat = get_re_mesh_category()
    if cat is None:
        return []
    try:
        props = getattr(bpy.ops, cat).exportfile.get_rna_type().properties
        ids = {i.identifier for i in props["shapeKeyExportMode"].enum_items}
    except (AttributeError, KeyError, RuntimeError):
        return []
    if NO_MODE not in ids:
        return []
    return [m for m, _n in MODES if m in ids]


def is_sks_game(game):
    return bool(GAMES.get(game, {}).get("sks"))


def local_roots(game, mod_root=None):
    """Folders whose ``reframework/data/ShapeKeySystem`` profiles count: the
    game install, then the mod being exported (a mod may ship its own)."""
    g = GAMES[game]
    roots = [sks_profiles.find_game_dir(g["steam"])] if g.get("steam") else []
    if mod_root:
        roots.append(mod_root)
    return [r for r in roots if r]


def library(game, mod_root=None):
    return sks_profiles.library(GAMES[game]["sks"], local_roots(game, mod_root))


# ── Settings ─────────────────────────────────────────────────────────────────

# Dynamic enum items live at module level: Blender keeps pointers into them, and
# a local list's strings can be freed while it still reads them (CJK breaks first).
_MODE_ITEMS = []
_FILTER_ITEMS = []


_MODE_LABELS = {
    "MODE1": ("core.shapekey_export.mode_mode1", "core.shapekey_export.mode_mode1_desc"),
    "KEEPNORMALS_SURFACE": ("core.shapekey_export.mode_keepnormals_surface",
                            "core.shapekey_export.mode_keepnormals_surface_desc"),
}
_FILTER_LABELS = {
    "FOLLOW": ("core.shapekey_export.filter_follow", "core.shapekey_export.filter_follow_desc"),
    "EXPR_SCULPT": ("core.shapekey_export.filter_expr_sculpt",
                    "core.shapekey_export.filter_expr_sculpt_desc"),
    "EXPRESSION": ("core.shapekey_export.filter_expression",
                   "core.shapekey_export.filter_expression_desc"),
    "SCULPT": ("core.shapekey_export.filter_sculpt", "core.shapekey_export.filter_sculpt_desc"),
}


def _mode_items(self, context):
    _MODE_ITEMS[:] = [(m, T(_MODE_LABELS[m][0]), T(_MODE_LABELS[m][1]), n) for m, n in MODES]
    return _MODE_ITEMS


def _filter_items(self, context):
    _FILTER_ITEMS[:] = [(f, T(_FILTER_LABELS[f][0]), T(_FILTER_LABELS[f][1]), n)
                        for f, n in FILTERS]
    return _FILTER_ITEMS


class MT_ShapeKeyExportSettings(bpy.types.PropertyGroup):
    export: BoolProperty(
        name="Export Shape Keys", description="Export the meshes' shape keys as blendshapes",
        default=True)
    mode: EnumProperty(
        name="Normal Format", description="How the shape keys' normals are exported",
        items=_mode_items, default=dict(MODES)[DEFAULT_MODE])
    use_sks: BoolProperty(
        name="Use ShapeKeySystem",
        description="Sort keys into expression / sculpt by an SKS expression profile and write an "
                    "SKS preset; off = keys export as ticked / locked",
        default=True)
    key_filter: EnumProperty(
        name="Keys", description="Which shape keys are exported",
        items=_filter_items, default=0)
    profile: StringProperty(
        name="Expression Profile",
        description="SKS expression profile that decides which keys are expression keys; "
                    "empty = the best match")
    write_preset: BoolProperty(
        name="Write SKS Preset",
        description="Also write an SKS sculpt preset with the current values and a binding into the mod",
        default=True)
    preset_name: StringProperty(
        name="Preset Name",
        description="Name of the sculpt preset; empty = the Bonesystem FBXSkel name when that "
                    "is in use, else the body part's export ID")


def settings_of(scene, game):
    s = getattr(scene, "mhw_suite_settings", None)
    return getattr(s, GAMES[game]["prop"], None) if s is not None else None


# ── Keys ─────────────────────────────────────────────────────────────────────

def _mesh_objects(collection):
    return [o for o in collection.all_objects
            if o.type == 'MESH' and not o.get("MeshExportExclude")
            and o.data.shape_keys is not None and len(o.data.shape_keys.key_blocks) > 1]


def candidate_keys(obj):
    """The keys a filter can send out of *obj*: not the basis, not DUMMY_.
    Whether they are muted (unticked) or locked is up to the filter."""
    blocks = obj.data.shape_keys.key_blocks
    basis = blocks.get("Basis") or blocks[0]
    return [k for k in blocks if k != basis and not k.name.startswith(DUMMY_PREFIX)]


def is_active(k):
    """Ticked and unlocked: what the fork exports as a blendshape (it bakes
    locked keys into the base instead)."""
    return not k.mute and not k.lock_shape


def part_names(collection):
    """Candidate key names of one exported mesh (= one SKS part), in order.
    Unticked and locked keys count, so a forcing filter classifies them too."""
    seen, out = set(), []
    for obj in _mesh_objects(collection):
        for k in candidate_keys(obj):
            if k.name not in seen:
                seen.add(k.name)
                out.append(k.name)
    return out


def ranked_profiles(game, collections, mod_root=None):
    """``[(id, name, hits, channels, source)]`` over every key of every mesh,
    the way SKS ranks profiles for a character."""
    names = []
    for col in collections:
        names.extend(part_names(col))
    return library(game, mod_root).rank(names)


def pick_profile(pg, ranked):
    """The profile in effect: the chosen one while it still exists, else the
    best match with at least one hit, else None."""
    ids = {r[0] for r in ranked}
    if pg.profile and pg.profile in ids:
        return pg.profile
    return ranked[0][0] if ranked and ranked[0][2] > 0 else None


def split_keys(lib, profile_id, collection):
    """(expression names, sculpt names) of one mesh."""
    names = part_names(collection)
    expr = lib.expression_names(profile_id, names) if profile_id else set()
    return [n for n in names if n in expr], [n for n in names if n not in expr]


def effective_filter(key_filter, profile_id):
    """The filter in effect: the ones that need a profile fall back to FOLLOW."""
    if not key_filter or (key_filter in NEEDS_PROFILE and not profile_id):
        return "FOLLOW"
    return key_filter


def exports(k, is_expr, key_filter):
    """Whether *key_filter* sends key *k* out."""
    if key_filter == "FOLLOW":
        return is_active(k)
    if is_expr:     # forced out, ticked or not, locked or not
        return key_filter in ("EXPR_SCULPT", "EXPRESSION")
    if key_filter == "EXPRESSION":
        return False
    return is_active(k) and abs(k.value) > ZERO


def plan(lib, profile_id, collection, key_filter):
    """``[(obj, key, is_expr, exported)]`` for every candidate key of one mesh."""
    expr = set(split_keys(lib, profile_id, collection)[0]) if lib is not None and profile_id else set()
    return [(obj, k, k.name in expr, exports(k, k.name in expr, key_filter))
            for obj in _mesh_objects(collection) for k in candidate_keys(obj)]


def inactive_expression_keys(lib, profile_id, collections):
    """``[(object name, key name, muted, locked)]``: expression keys that a
    FOLLOW export leaves out because they are unticked or locked."""
    out = []
    for col in collections:
        for obj, k, is_expr, _out in plan(lib, profile_id, col, "FOLLOW"):
            if is_expr and not is_active(k):
                out.append((obj.name, k.name, k.mute, k.lock_shape))
    return out


def count_keys(lib, profile_id, collections, key_filter):
    """(exported, expression, used sculpt, unused sculpt) key counts, by name
    per mesh.  A sculpt key is used when it is ticked, unlocked and not 0."""
    n_out = n_expr = n_used = n_unused = 0
    for col in collections:
        out, expr, used, unused = set(), set(), set(), set()
        for _obj, k, is_expr, exported in plan(lib, profile_id, col, key_filter):
            if exported:
                out.add(k.name)
            if is_expr:
                expr.add(k.name)
            elif is_active(k) and abs(k.value) > ZERO:
                used.add(k.name)
            else:
                unused.add(k.name)
        unused -= used      # a name used on one object of the mesh is used
        n_out += len(out)
        n_expr += len(expr)
        n_used += len(used)
        n_unused += len(unused)
    return n_out, n_expr, n_used, n_unused


def effective_mode(pg, modes):
    """The shapeKeyExportMode to pass: NO when unticked, the chosen mode, else
    the default, else None (pass nothing)."""
    if not pg.export:
        return NO_MODE
    if pg.mode in modes:
        return pg.mode
    return DEFAULT_MODE if DEFAULT_MODE in modes else None


# ── The export run ───────────────────────────────────────────────────────────

class _Session:
    def __init__(self, game, pg, mode, key_filter, profile_id, lib):
        self.game = game
        self.pg = pg
        self.mode = mode                # None = pass nothing (REME default)
        self.key_filter = key_filter
        self.profile_id = profile_id
        self.lib = lib
        self.values = {}                # sculpt key -> value, across all meshes
        self.expression_exported = False
        self.exported_keys = 0


_ACTIVE = None


@contextmanager
def session(context, game, collections=(), mod_root=None):
    """Batch-export scope: the mesh exports inside it take this game's shape-key
    settings.  Yields the session (or None when nothing applies)."""
    global _ACTIVE
    pg = settings_of(context.scene, game)
    s = None
    modes = available_modes(game) if pg is not None else []
    if modes:
        mode = effective_mode(pg, modes)
        key_filter, profile_id, lib = "FOLLOW", None, None
        if is_sks_game(game) and pg.use_sks and mode != NO_MODE:
            lib = library(game, mod_root)
            profile_id = pick_profile(pg, lib.rank(
                [n for c in collections for n in part_names(c)]))
            key_filter = effective_filter(pg.key_filter, profile_id)
        s = _Session(game, pg, mode, key_filter, profile_id, lib)
        print(f"[{game}] shape keys: mode={mode or 'REME default'} filter={key_filter} "
              f"profile={profile_id or '-'}")
    prev, _ACTIVE = _ACTIVE, s
    try:
        yield s
    finally:
        _ACTIVE = prev


def export_kwargs():
    """Extra ``exportfile`` kwargs for the current session."""
    s = _ACTIVE
    return {"shapeKeyExportMode": s.mode} if s is not None and s.mode else {}


@contextmanager
def filtered(collection_name):
    """For the length of this mesh's export, mute the keys the session's filter
    leaves out and unmute / unlock the expression keys it forces out; note the
    sculpt values it exports.  Every flag goes back afterwards."""
    s = _ACTIVE
    col = bpy.data.collections.get(collection_name) if collection_name else None
    if s is None or col is None or s.mode == NO_MODE:
        yield
        return
    changed = []        # (key, mute, lock_shape) as they were
    left_out = forced = 0
    try:
        for _obj, k, is_expr, out in plan(s.lib, s.profile_id, col, s.key_filter):
            if not out:
                if is_active(k):        # inactive keys are already left out (or baked)
                    changed.append((k, k.mute, k.lock_shape))
                    k.mute = True
                    left_out += 1
                continue
            if not is_active(k):
                changed.append((k, k.mute, k.lock_shape))
                k.mute = False
                k.lock_shape = False
                forced += 1
            s.exported_keys += 1
            if is_expr:
                s.expression_exported = True
            else:
                key = sks_profiles.key_of(k.name)
                v = min(max(float(k.value), 0.0), SCULPT_MAX)
                s.values[key] = max(v, s.values.get(key, 0.0))
        if left_out or forced:
            print(f"[{s.game}] {collection_name}: {left_out} shape keys left out, "
                  f"{forced} forced out ({s.key_filter})")
        yield
    finally:
        for k, mute, lock in reversed(changed):
            k.mute = mute
            k.lock_shape = lock


def write_presets(s, mod_root, model, rep_part, default_name):
    """Write the session's SKS preset into *mod_root*.  Returns (paths, message
    key) -- no paths when there was nothing to write or it is switched off.
    *default_name* names the preset when the user left the name empty."""
    if (s is None or not is_sks_game(s.game) or s.mode in (None, NO_MODE)
            or not s.pg.use_sks or not s.pg.write_preset):
        return [], None
    if s.exported_keys == 0:
        return [], "core.shapekey_export.preset_nothing"
    name = s.pg.preset_name.strip() or default_name
    values = {k: round(v, 4) for k, v in sorted(s.values.items())}
    profile = s.profile_id if s.expression_exported else None
    paths = sks_profiles.write_presets(mod_root, model, rep_part, profile, name, values)
    for p in paths:
        print(f"[{s.game}] SKS preset -> {p}")
    return paths, "core.shapekey_export.preset_written" if paths else "core.shapekey_export.preset_nothing"


# ── UI ───────────────────────────────────────────────────────────────────────

_rank_cache = {}        # game -> ranked list from the last draw (for the picker)
_inactive_cache = {}    # game -> inactive expression keys from the last draw
_PROFILE_ITEMS = []


def draw(layout, scene, game, collections, mod_root=None):
    """The shape-key box of a batch export dialog.  *collections* are the mesh
    collections the export would write."""
    pg = settings_of(scene, game)
    if pg is None:
        return
    box = layout.box()
    modes = available_modes(game)
    row = box.row(align=True)
    row.enabled = bool(modes)
    row.prop(pg, "export", text=T("core.shapekey_export.export_toggle"), icon='SHAPEKEY_DATA')
    if not modes:
        box.label(text=T("core.shapekey_export.need_fork"), icon='INFO')
        return
    if not pg.export:
        return
    box.prop(pg, "mode", text=T("core.shapekey_export.mode_label"))
    if pg.mode not in modes:
        box.label(text=T("core.shapekey_export.mode_unsupported"), icon='ERROR')
    if not is_sks_game(game):
        return
    box.prop(pg, "use_sks", text=T("core.shapekey_export.use_sks"))
    if not pg.use_sks:
        return
    box = box.box()     # everything below needs ShapeKeySystem

    lib = library(game, mod_root)
    ranked = ranked_profiles(game, collections, mod_root)
    _rank_cache[game] = ranked
    profile_id = pick_profile(pg, ranked)
    key_filter = effective_filter(pg.key_filter, profile_id)

    box.prop(pg, "key_filter", text=T("core.shapekey_export.filter_label"))
    if key_filter == "SCULPT":
        box.label(text=T("core.shapekey_export.sculpt_only_hint"), icon='INFO')
    else:
        hit = next((r for r in ranked if r[0] == profile_id), None)
        row = box.row(align=True)
        row.label(text=T("core.shapekey_export.profile_label"))
        if hit is None:
            text = T("core.shapekey_export.profile_none")
        else:
            text = T("core.shapekey_export.profile_entry").format(
                name=hit[1], hits=hit[2], total=hit[3])
            if not pg.profile:
                text = T("core.shapekey_export.profile_auto").format(entry=text)
        op = row.operator("mt.sks_pick_profile", text=text, icon='DOWNARROW_HLT')
        op.game = game

    if key_filter == "FOLLOW" and profile_id:
        inactive = inactive_expression_keys(lib, profile_id, collections)
        _inactive_cache[game] = inactive
        if inactive:
            row = box.row(align=True)
            row.alert = True
            row.label(text=T("core.shapekey_export.inactive_expr").format(n=len(inactive)),
                      icon='ERROR')
            op = row.operator("mt.sks_inactive_expression_keys",
                              text=T("core.shapekey_export.inactive_details"))
            op.game = game

    n_out, n_expr, n_used, n_unused = count_keys(lib, profile_id, collections, key_filter)
    box.label(text=T("core.shapekey_export.count").format(
        out=n_out, expr=n_expr, used=n_used, unused=n_unused), icon='INFO')
    if key_filter != pg.key_filter:
        box.label(text=T("core.shapekey_export.filter_needs_profile"), icon='ERROR')

    row = box.row(align=True)
    row.prop(pg, "write_preset", text=T("core.shapekey_export.write_preset"))
    sub = row.row(align=True)
    sub.enabled = pg.write_preset
    sub.prop(pg, "preset_name", text=T("core.shapekey_export.preset_name"))


def _profile_items(self, context):
    items = [("__AUTO__", T("core.shapekey_export.profile_auto_item"), "")]
    for pid, name, hits, total, source in _rank_cache.get(self.game, []):
        items.append((pid, T("core.shapekey_export.profile_entry").format(
            name=name, hits=hits, total=total), source))
    _PROFILE_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
    return _PROFILE_ITEMS


class MT_OT_SKSPickProfile(bpy.types.Operator):
    bl_idname = "mt.sks_pick_profile"
    bl_label = "Pick Expression Profile"
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_property = "profile"

    game: StringProperty(options={'HIDDEN'})
    profile: EnumProperty(items=_profile_items)

    @classmethod
    def description(cls, context, properties):
        return T("core.shapekey_export.pick_profile_desc")

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = settings_of(context.scene, self.game) if self.game in GAMES else None
        if pg is None:
            return {'CANCELLED'}
        pg.profile = "" if self.profile == "__AUTO__" else self.profile
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        return {'FINISHED'}


_STATE_KEYS = {(True, False): "core.shapekey_export.state_muted",
               (False, True): "core.shapekey_export.state_locked",
               (True, True): "core.shapekey_export.state_both"}
_DETAIL_ROWS = 30


class MT_OT_SKSInactiveExpressionKeys(bpy.types.Operator):
    """The expression keys an "as ticked / locked" export leaves out, and a
    button that ticks and unlocks them all."""
    bl_idname = "mt.sks_inactive_expression_keys"
    bl_label = "Unticked / Locked Expression Keys"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    game: StringProperty(options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        return T("core.shapekey_export.inactive_details_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self, width=420, title=T("core.shapekey_export.inactive_title"),
            confirm_text=T("core.shapekey_export.activate_all"))

    def draw(self, context):
        col = self.layout.column(align=True)
        rows = _inactive_cache.get(self.game, [])
        for obj, key, muted, locked in rows[:_DETAIL_ROWS]:
            r = col.row(align=True)
            r.label(text=T("core.shapekey_export.inactive_row").format(obj=obj, key=key),
                    icon='SHAPEKEY_DATA')
            r.label(text=T(_STATE_KEYS[(bool(muted), bool(locked))]))
        if len(rows) > _DETAIL_ROWS:
            col.label(text=T("core.shapekey_export.inactive_more").format(n=len(rows) - _DETAIL_ROWS))

    def execute(self, context):
        n = 0
        for obj_name, key_name, _m, _l in _inactive_cache.get(self.game, []):
            obj = bpy.data.objects.get(obj_name)
            keys = obj.data.shape_keys if obj is not None and obj.type == 'MESH' else None
            k = keys.key_blocks.get(key_name) if keys is not None else None
            if k is not None and not is_active(k):
                k.mute = False
                k.lock_shape = False
                n += 1
        _inactive_cache.pop(self.game, None)
        self.report({'INFO'}, T("core.shapekey_export.activated").format(n=n))
        return {'FINISHED'}


classes = [MT_OT_SKSPickProfile, MT_OT_SKSInactiveExpressionKeys]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
