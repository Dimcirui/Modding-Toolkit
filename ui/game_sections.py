"""Per-game tool sections of the main panel, as data plus one draw pass.

These five sections were five hand-written blocks that had drifted: the same
button appeared with different neighbours, in a different order, and guarded
differently from one game to the next.  Adding anything meant editing five
places, and forgetting one of them is exactly how the generator's slot-priority
toggle ended up covering four games out of five.

So the layout is a table now, and every game gets the same groups in the
same order:

    导入 & 导出       getting the asset in and out of the game
    骨架 & 网格处理    skeleton and mesh preparation
    材质 & 贴图处理    materials and textures
    物理处理          physics: chains, and the bone work that feeds them
    跨游戏移植        behind the port notice (core/port_consent.py)

One game is active at a time (the picker at the top of the sidebar, stored in
the addon preferences), and each group is a native sub-panel of the root
panel.  Because only one game is drawn, five panel classes cover every game:
each one looks the active game up in this table, and its ``poll`` hides it when
that game has nothing in the group -- which is why Onimusha shows two groups.

Dependency guards stay per entry: several tools only work when one of the
upstream addons is installed, and a disabled button plus one explanatory line
is far better than a button that fails when pressed.
"""

import bpy

from ..core.i18n import T
from ..core.compat import MTK_SHADER_AVAILABLE, op_available
from ..core.re_mesh_compat import re_mesh_op_available
from ..core.port_consent import draw_gate


# ── Dependency guards ─────────────────────────────────────────────────────────
# name -> (probe, i18n key explaining what is missing).  Probed once per draw.

def _has_mhw_model():
    return op_available('mhw_mod3', 'export_mhw_mod3')


def _has_mhw_ctc():
    return op_available('mhw_ctc', 'create_chain_from_bone')


def _has_re_chain():
    return op_available('re_chain', 'create_chain_settings')


def _has_re_fbxskel():
    return op_available('re_fbxskel', 'exportfile')


GUARDS = {
    'mhw_model':      (_has_mhw_model,  "ui.main_panel.label_need_mhw_model_editor"),
    'mhw_ctc':        (_has_mhw_ctc,    "ui.main_panel.label_need_mhw_model_editor"),
    're_chain':       (_has_re_chain,   "ui.main_panel.label_need_re_chain_editor"),
    're_mesh':        (lambda: re_mesh_op_available('exportfile'),
                        "ui.main_panel.label_need_re_mesh_editor"),
    're_mesh_import': (lambda: re_mesh_op_available('importfile'),
                        "ui.main_panel.label_need_re_mesh_editor"),
    're_fbxskel':     (_has_re_fbxskel, "ui.main_panel.label_need_re_mesh_editor"),
}


# ── Entry helper ──────────────────────────────────────────────────────────────

def op(idname, text_key, icon, *, needs=None, props=None, only_if=None):
    """One button.  ``props`` are set on the returned operator properties."""
    return {'op': idname, 'text': text_key, 'icon': icon,
            'needs': needs, 'props': props or {}, 'only_if': only_if}


#: Groups, in the order every game draws them.
GROUP_ORDER = ('io', 'rig', 'material', 'physics', 'port')

GROUP_LABELS = {
    'io':       ("ui.game_sections.group_io",       'FILE'),
    'rig':      ("ui.game_sections.group_rig",      'ARMATURE_DATA'),
    'material': ("ui.game_sections.group_material", 'MATERIAL'),
    'physics':  ("ui.game_sections.group_physics",  'PHYSICS'),
    'port':     ("ui.game_sections.group_port",     'UV_SYNC_SELECT'),
}


def _port(game_code):
    """The cross-game port entries, identical for every RE Engine game.

    The section fixes the source game; the dialog picks the target.  MHWI is not one
    of these: it is not RE Engine, so it has no target to pick and no shared chain
    format.  Its one-way rebuild to MHWilds is a separate operator with its own
    entry, ``mhwi.port_to_mhws``.
    """
    return [op("modder.port_mesh_cross_game",
               "ui.main_panel.btn_port_mesh_cross_game", 'ARMATURE_DATA',
               props={'source_game': game_code}),
            op("modder.convert_chain_cross_game",
               "ui.main_panel.btn_convert_chain_cross_game", 'UV_SYNC_SELECT',
               needs='re_chain', props={'source_game': game_code}),
            op("modder.port_mdf_material_cross_game",
               "ui.main_panel.btn_port_mdf_material_cross_game", 'MATERIAL',
               props={'source_game': game_code})]


def _mdf_pair(prefix):
    """Processor and generator side by side — they are two halves of one job."""
    return [op(f"{prefix}.mdf_tex_processor_dialog",
               "ui.main_panel.btn_mdf_tex_processor", 'TEXTURE'),
            op(f"{prefix}.mdf_generator_dialog",
               "ui.main_panel.btn_mdf_generator", 'SHADERFX')]


def _re_chain(prefix):
    return op(f"{prefix}.auto_create_chains", "ui.main_panel.btn_create_re_chain",
              'LINKED', needs='re_chain')


def _face_weights(game):
    return op("mhw.mmd_face_weights", "ui.main_panel.btn_mmd_face_weights",
              'SHAPEKEY_DATA', props={'target_game': game})


def _configure_shape_keys(game_code):
    """Last in the rig group: set the selected meshes' shape-key ticks / locks
    the way one of batch export's key filters would export them."""
    return op("mt.sks_configure_shape_keys",
              "ui.game_sections.btn_configure_shape_keys", 'SHAPEKEY_DATA',
              props={'game': game_code})


def _batch_export(prefix, label_key, needs='re_mesh'):
    return op(f"{prefix}.batch_export_dialog", label_key, 'EXPORT', needs=needs)


def _pre_export_check(game_code):
    """"匹配检查" -- the single-pair, manually-invoked version. Batch export
    already runs the same checks automatically over every pair it will
    actually export; this button is for checking one mesh/mdf pair on its
    own, e.g. before it is even wired into a batch export job. Kept directly
    above batch export in the panel since that is still a natural place to
    reach for it.

    No dependency guard: the check reads the mdf/mesh collections that are
    already in the file rather than calling into either external addon, so it
    still works on a .blend opened without them installed. Its own poll (is
    there an .mdf2 collection at all) is the real gate.
    """
    return op("modder.pre_export_check", "ui.main_panel.btn_pre_export_check",
              'CHECKMARK', props={'source_game': game_code})


def _ref_model(game_code):
    """Import the game's vanilla reference body -- first in the group, because it is
    where a port or a rig job starts.  Where the model comes from and which of the
    three post-import options a game supports is ``core/ref_model.py``'s business, so
    every game gets the same entry here."""
    return op("modder.import_reference_model",
              "ui.main_panel.btn_import_reference_model", 'OUTLINER_OB_ARMATURE',
              props={'source_game': game_code})


SECTIONS = {
    'mhwi': {
        'io': [
            _ref_model('MHWI'),
            op("mhwi.batch_import_dialog", "ui.main_panel.btn_batch_import",
               'IMPORT', needs='mhw_model'),
            op("mhwi.batch_export_dialog", "ui.main_panel.btn_batch_export",
               'EXPORT', needs='mhw_model'),
        ],
        'rig': [
            op("mhwi.preprocess_model", "ui.main_panel.btn_mhwi_preprocess",
               'ARMATURE_DATA', needs='mhw_model'),
            op("mhwi.align_non_physics", "ui.main_panel.btn_align_non_physics",
               'BONE_DATA'),
            _face_weights('MHWI'),
            op("mhwi.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
            op("mhwi.set_mesh_display_condition",
               "mhwi.operators.btn_set_display_condition", 'HIDE_OFF'),
        ],
        'material': [
            # Above the processor/generator pair because that is the order it is
            # used in: convert the materials first, then generate from them.
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'game': 'MHWI', 'scope': 'SELECTED', 'show_dialog': False},
               only_if=lambda: MTK_SHADER_AVAILABLE),
            [op("mhwi.mrl3_tex_processor_dialog",
                "ui.main_panel.btn_mrl3_tex_processor", 'TEXTURE', needs='mhw_model'),
             op("mhwi.mrl3_generator_dialog",
                "ui.main_panel.btn_mrl3_generator", 'SHADERFX', needs='mhw_model')],
        ],
        'physics': [
            # MHWI's physics bones have to be split and renamed into the ID
            # ranges the game reserves before a chain can be built from them, so
            # they belong with the chains rather than with general rigging.
            # One button for every state of an armature: split + rename when it was
            # never processed, an incremental renumber when it already was (also for
            # several selected armatures at once).  See MHWI_OT_SplitPhysicsBones.
            op("mhwi.split_physics_bones", "ui.main_panel.btn_split_physics_bones",
               'BONE_DATA'),
            op("mhwi.auto_create_chains", "ui.main_panel.btn_create_chain",
               'LINKED', needs='mhw_ctc'),
        ],
        # One-way, unlike the RE-to-RE ports: crossing engines is a rebuild, so
        # MHWI is always the source and never a destination.  The *target* is no
        # longer fixed, though -- each dialog offers MHWilds or MH Rise -- so the
        # three are named after the source format rather than after a destination
        # only one of them would be right about.
        'port': [
            op("mhwi.port_to_mhws", "ui.main_panel.btn_port_mhwi_to_mhws",
               'ARMATURE_DATA'),
            # Guarded on MHW Model Editor as a whole: the decode goes through its
            # modules.tex.tex_function, which ships in the same addon as the mod3
            # and mrl3 support every other MHWI button here needs.
            op("mhwi.port_mrl3_to_mdf2", "ui.main_panel.btn_port_mrl3_to_mdf2",
               'MATERIAL', needs='mhw_model'),
            # Needs *both* companion addons -- it reads MHW Model Editor's ctc/ccl
            # property groups and builds through RE Chain Editor's operators -- but
            # ``needs`` takes one guard, so it names the reader like
            # ``mhwi.auto_create_chains`` above does for the same pair.  Missing
            # RE Chain Editor is caught at run time instead, with its own message:
            # without it there is no ``scene.re_chain_toolpanel`` to build into.
            op("mhwi.port_physics_to_mhws", "ui.main_panel.btn_port_ctc_to_chain2",
               'PHYSICS', needs='mhw_ctc'),
            # Below the three, because it is the same job done to a whole set --
            # someone who wants one part reaches for the buttons above, someone
            # who wants a set reaches past them.  Guarded on MHW Model Editor for
            # the importer it drives; RE Mesh and RE Chain are caught at run time
            # by the operators it hands off to, each with its own message.
            op("mhwi.batch_port_mhrs", "ui.main_panel.btn_batch_port_mhrs",
               'EXPORT', needs='mhw_model'),
        ],
    },
    'mhws': {
        'io': [
            _ref_model('MHWS'),
            op("mhws.batch_import_dialog", "ui.main_panel.btn_batch_import",
               'IMPORT', needs='re_mesh_import'),
            _pre_export_check('MHWS'),
            _batch_export('mhws', "ui.main_panel.btn_batch_export"),
        ],
        'rig': [
            op("mhws.preprocess_model", "ui.main_panel.btn_mhws_preprocess",
               'ARMATURE_DATA'),
            op("mhws.optimize_skeleton", "ui.main_panel.btn_mhws_optimize_skeleton",
               'MOD_ARMATURE'),
            op("mhws.optimize_aux_bones", "ui.main_panel.btn_mhws_optimize_aux",
               'GROUP_VERTEX'),
            _face_weights('MHWS'),
            op("mhws.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
            _configure_shape_keys('MHWS'),
        ],
        'material': [
            # Above the processor/generator pair for the same reason as MHWI:
            # convert the materials first, then generate from them. One
            # button, not one per archetype -- MTK_OT_ConvertToPackedShader's
            # own dialog (use_prefab checkbox + preset dropdown) resolves which
            # spec/preset to use, so no game needs presetting here.
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'scope': 'SELECTED', 'family': 'MHWS'},
               only_if=lambda: MTK_SHADER_AVAILABLE),
            _mdf_pair('mhws'),
            # Below the processor/generator pair: convert an existing MDF
            # material to a different preset, migrating custom textures.
            op("mhws.mdf_convert_material_dialog",
               "ui.game_sections.btn_mdf_convert_material", 'FILE_REFRESH'),
        ],
        'physics': [_re_chain('mhws')],
        'port': _port('MHWS'),
    },
    're4': {
        'io': [_ref_model('RE4'), _pre_export_check('RE4'),
               _batch_export('re4', "ui.game_sections.btn_batch_export_re4")],
        'rig': [
            op("re4.fakebone_one_click", "ui.main_panel.btn_gen_fakebone",
               'ARMATURE_DATA', needs='re_fbxskel'),
            _face_weights('RE4'),
            op("re4.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
            _configure_shape_keys('RE4'),
        ],
        'material': [
            # Above the processor/generator pair for the same reason as
            # MHWI/MHWS: convert the materials first, then generate from
            # them. Same use_prefab/preset_choice dialog as MHWS, scoped to
            # RE4's three bundled prefabs (assets/mdf_presets/re4/) via
            # `family`.
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'scope': 'SELECTED', 'family': 'RE4'},
               only_if=lambda: MTK_SHADER_AVAILABLE),
            _mdf_pair('re4'),
            # Below the processor/generator pair, same placement and same
            # shared label as MHWS: convert an existing MDF material to a
            # different preset, migrating custom textures.
            op("re4.mdf_convert_material_dialog",
               "ui.game_sections.btn_mdf_convert_material", 'FILE_REFRESH'),
        ],
        'physics': [_re_chain('re4')],
        'port': _port('RE4'),
    },
    'mhrs': {
        'io': [_ref_model('MHRS'),
               op("mhrs.batch_import_dialog", "ui.main_panel.btn_batch_import",
                  'IMPORT', needs='re_mesh_import'),
               _pre_export_check('MHRS'),
               _batch_export('mhrs', "ui.game_sections.btn_batch_export_mhrs")],
        'rig': [_configure_shape_keys('MHRS')],
        'material': [
            # MHRS has only one archetype (see games/mhrs/shader_defs.py's
            # module docstring), so this is pinned like MHWI's button --
            # nothing to choose, no dialog.
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'game': 'MHRS', 'scope': 'SELECTED', 'show_dialog': False},
               only_if=lambda: MTK_SHADER_AVAILABLE),
            _mdf_pair('mhrs'),
        ],
        'physics': [_re_chain('mhrs')],
        'port': _port('MHRS'),
    },
    're9': {
        'io': [_ref_model('RE9'), _pre_export_check('RE9'),
               _batch_export('re9', "ui.game_sections.btn_batch_export_re9")],
        'rig': [
            op("re9.sync_child_orientation",
               "ui.main_panel.btn_sync_child_orientation", 'CON_ROTLIKE'),
            _face_weights('RE9'),
            op("re9.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
        ],
        'material': [
            # Same use_prefab/preset_choice dialog as MHWS/RE4, scoped to
            # RE9's four bundled prefabs (assets/mdf_presets/re9/).
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'scope': 'SELECTED', 'family': 'RE9'},
               only_if=lambda: MTK_SHADER_AVAILABLE),
            _mdf_pair('re9'),
            # Below the processor/generator pair, same placement and same
            # shared label as MHWS: convert an existing MDF material to a
            # different preset, migrating custom textures.
            op("re9.mdf_convert_material_dialog",
               "ui.game_sections.btn_mdf_convert_material", 'FILE_REFRESH'),
        ],
        'physics': [_re_chain('re9')],
        'port': _port('RE9'),
    },
    # A port *target* only (see mesh_port_ops.PORTABLE_GAMES), so no port group --
    # the port buttons live in the source game's section.
    'oni': {
        'io': [_ref_model('ONI'),
               _batch_export('oni', "ui.game_sections.btn_batch_export_oni")],
        'rig': [_configure_shape_keys('ONI')],
    },
}


# ── Active game ───────────────────────────────────────────────────────────────

#: The picker's two rows: the Monster Hunter games (armour-set export), then the
#: character games (scheme-driven batch export).  The picker draws them in this
#: order, so it is also the order the games are offered in.
GAME_ROWS = (("MHWI", "MHWS", "MHRS"),
             ("RE4", "RE9", "ONI"))

#: Shown before the user has ever picked one.
DEFAULT_GAME = "MHWS"

#: Full game names for the picker's tooltips.
_GAME_NAME_KEYS = {
    "MHWI": "ui.game_sections.game_mhwi",
    "MHWS": "ui.game_sections.game_mhws",
    "MHRS": "ui.game_sections.game_mhrs",
    "RE4":  "ui.game_sections.game_re4",
    "RE9":  "ui.game_sections.game_re9",
    "ONI":  "ui.game_sections.game_oni",
}

#: Persistent backing for the items callback below: Blender's C side keeps the
#: pointers, so a list built fresh inside the callback is freed too early.
_game_item_cache = []


def game_items(self, context):
    """Items for ``MT_Preferences.active_game``: the short code as the button
    text, the full name (translated) as its tooltip."""
    _game_item_cache.clear()
    _game_item_cache.extend(
        (g, g, T(_GAME_NAME_KEYS[g]), i)
        for i, g in enumerate(g for row in GAME_ROWS for g in row))
    return _game_item_cache


def default_game_index():
    flat = [g for row in GAME_ROWS for g in row]
    return flat.index(DEFAULT_GAME)


def preferences(context):
    """The addon preferences, or None when they cannot be found (a module-name
    mismatch between installs, see ui/personal_tools_panel.py)."""
    try:
        from ..core.console_export import get_preferences
        return get_preferences(context)
    except Exception:
        return None


def active_game(context):
    """The active game's key into SECTIONS ('mhws', ...)."""
    prefs = preferences(context)
    code = getattr(prefs, "active_game", None) or DEFAULT_GAME
    key = code.lower()
    return key if key in SECTIONS else DEFAULT_GAME.lower()


def draw_game_picker(layout, context):
    prefs = preferences(context)
    if prefs is None:
        return
    col = layout.column(align=True)
    for codes in GAME_ROWS:
        row = col.row(align=True)
        for code in codes:
            row.prop_enum(prefs, "active_game", code)


# ── Drawing ───────────────────────────────────────────────────────────────────

def _draw_button(layout, entry, guard_state, missing, icon=True):
    need = entry['needs']
    if need is not None:
        ok = guard_state[need]
        layout.enabled = ok
        if not ok:
            missing.add(need)
    props = layout.operator(entry['op'], text=T(entry['text']),
                            icon=entry['icon'] if icon else 'NONE')
    for k, v in entry['props'].items():
        setattr(props, k, v)


def _visible(entry):
    return entry['only_if'] is None or entry['only_if']()


def visible_entries(game_key, group):
    """The group's entries that would draw: a pair counts if either half does."""
    out = []
    for entry in SECTIONS[game_key].get(group) or []:
        if isinstance(entry, list):
            pair = [e for e in entry if _visible(e)]
            if pair:
                out.append(pair)
        elif _visible(entry):
            out.append(entry)
    return out


def _draw_group(layout, entries, guard_state):
    missing = set()
    col = layout.column(align=True)
    for entry in entries:
        if isinstance(entry, list):
            row = col.row(align=True)
            # A pair drops its icons: at the default sidebar width the English
            # labels only fit side by side without them.
            for e in entry:
                _draw_button(row.row(align=True), e, guard_state, missing,
                             icon=len(entry) == 1)
        else:
            _draw_button(col.row(align=True), entry, guard_state, missing)
    # One line per missing dependency, not one per button that needs it.
    for need in sorted(missing):
        col.label(text=T(GUARDS[need][1]), icon='ERROR')


def draw_group(layout, game_key, group):
    """Draw one group of one game's tools into a sub-panel's layout."""
    entries = visible_entries(game_key, group)
    if group == 'port' and not draw_gate(layout):
        return
    guard_state = {name: probe() for name, (probe, _msg) in GUARDS.items()}
    _draw_group(layout, entries, guard_state)


# ── Sub-panels ────────────────────────────────────────────────────────────────

#: Groups that start open the first time a user sees them.  Blender remembers
#: each panel's open state from then on.
_OPEN_BY_DEFAULT = {'io'}

def _make_group_panel(group, parent_idname, order):
    label_key, icon = GROUP_LABELS[group]

    def poll(cls, context):
        return bool(visible_entries(active_game(context), group))

    def draw_header(self, context):
        self.layout.label(text=T(label_key), icon=icon)

    def draw(self, context):
        draw_group(self.layout, active_game(context), group)

    attrs = {
        # Empty: the translated header comes from draw_header, and Blender
        # would draw a bl_label next to it.
        'bl_label': "",
        'bl_idname': f"MTK_PT_game_{group}",
        'bl_space_type': 'VIEW_3D',
        'bl_region_type': 'UI',
        'bl_category': 'MOD Toolkit',
        'bl_parent_id': parent_idname,
        'bl_order': order,
        'poll': classmethod(poll),
        'draw_header': draw_header,
        'draw': draw,
    }
    if group not in _OPEN_BY_DEFAULT:
        attrs['bl_options'] = {'DEFAULT_CLOSED'}
    return type(f"MTK_PT_game_{group}", (bpy.types.Panel,), attrs)


def make_group_panels(parent_idname):
    """One sub-panel class per group, in GROUP_ORDER, under ``parent_idname``."""
    return [_make_group_panel(g, parent_idname, i) for i, g in enumerate(GROUP_ORDER)]
