"""Per-game tool sections of the main panel, as data plus one draw pass.

These five sections were five hand-written blocks that had drifted: the same
button appeared with different neighbours, in a different order, and guarded
differently from one game to the next.  Adding anything meant editing five
places, and forgetting one of them is exactly how the generator's slot-priority
toggle ended up covering four games out of five.

So the layout is a table now, and every game gets the same four groups in the
same order:

    导入&导出        getting the asset in and out of the game
    骨架&网格处理     skeleton and mesh preparation
    材质&贴图处理     materials and textures
    物理处理          physics: chains, and the bone work that feeds them

A group with no entries for a game is skipped rather than drawn empty, which is
why MHRS shows three headings and the rest show four.

Dependency guards stay per entry: several tools only work when one of the
upstream addons is installed, and a disabled button plus one explanatory line
is far better than a button that fails when pressed.
"""

import bpy

from ..core.i18n import T
from ..core.compat import MTK_SHADER_AVAILABLE
from ..core.re_mesh_compat import re_mesh_op_available


# ── Dependency guards ─────────────────────────────────────────────────────────
# name -> (probe, i18n key explaining what is missing).  Probed once per draw.

def _has_mhw_model():
    return hasattr(bpy.ops, 'mhw_mod3') and hasattr(bpy.ops.mhw_mod3, 'export_mhw_mod3')


def _has_mhw_ctc():
    return hasattr(bpy.ops, 'mhw_ctc') and hasattr(bpy.ops.mhw_ctc, 'create_chain_from_bone')


def _has_re_chain():
    return hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')


def _has_re_fbxskel():
    return hasattr(bpy.ops, 're_fbxskel') and hasattr(bpy.ops.re_fbxskel, 'exportfile')


GUARDS = {
    'mhw_model':  (_has_mhw_model,  "ui.main_panel.label_need_mhw_model_editor"),
    'mhw_ctc':    (_has_mhw_ctc,    "ui.main_panel.label_need_mhw_model_editor"),
    're_chain':   (_has_re_chain,   "ui.main_panel.label_need_re_chain_editor"),
    're_mesh':    (lambda: re_mesh_op_available('exportfile'),
                   "ui.main_panel.label_need_re_mesh_editor"),
    're_fbxskel': (_has_re_fbxskel, "ui.main_panel.label_need_re_mesh_editor"),
}


# ── Entry helper ──────────────────────────────────────────────────────────────

def op(idname, text_key, icon, *, needs=None, props=None, only_if=None):
    """One button.  ``props`` are set on the returned operator properties."""
    return {'op': idname, 'text': text_key, 'icon': icon,
            'needs': needs, 'props': props or {}, 'only_if': only_if}


#: Groups, in the order every game draws them.
GROUP_ORDER = ('io', 'rig', 'material', 'physics')

GROUP_LABELS = {
    'io':       ("ui.game_sections.group_io",       'FILE'),
    'rig':      ("ui.game_sections.group_rig",      'ARMATURE_DATA'),
    'material': ("ui.game_sections.group_material", 'MATERIAL'),
    'physics':  ("ui.game_sections.group_physics",  'PHYSICS'),
}


def _tex_convert(game):
    """The shared image -> .tex tool; every game has it."""
    return op("mt.tex_convert_dialog", "ui.main_panel.btn_tex_process",
              'TEXTURE', props={'game': game})


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


def _batch_export(prefix, label_key, needs='re_mesh'):
    return op(f"{prefix}.batch_export_dialog", label_key, 'EXPORT', needs=needs)


SECTIONS = {
    'mhwi': {
        'label': "MHWI Tools", 'icon': 'ARMATURE_DATA',
        'io': [
            op("mhwi.batch_export_dialog", "ui.main_panel.btn_batch_export",
               'EXPORT', needs='mhw_model'),
            op("mhwi.batch_import_dialog", "ui.main_panel.btn_batch_import",
               'IMPORT', needs='mhw_model'),
        ],
        'rig': [
            op("mhwi.align_non_physics", "ui.main_panel.btn_align_non_physics",
               'BONE_DATA'),
            _face_weights('MHWI'),
        ],
        'material': [
            _tex_convert('MHWI'),
            # Above the processor/generator pair because that is the order it is
            # used in: convert the materials first, then generate from them.
            op("mtk.convert_to_packed_shader",
               "ui.main_panel.btn_convert_packed_shader", 'NODETREE',
               props={'game': 'MHWI', 'scope': 'SELECTED'},
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
            op("mhwi.split_physics_bones", "ui.main_panel.btn_split_physics_bones",
               'BONE_DATA'),
            op("mhwi.batch_rename_physics_bones",
               "ui.main_panel.btn_batch_rename_physics", 'SORTALPHA'),
            op("mhwi.auto_create_chains", "ui.main_panel.btn_create_chain",
               'LINKED', needs='mhw_ctc'),
        ],
    },
    'mhws': {
        'label': "MHWS Tools", 'icon': 'WORLD',
        'io': [_batch_export('mhws', "ui.game_sections.btn_batch_export_mhws")],
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
        ],
        'material': [_tex_convert('MHWS')] + [_mdf_pair('mhws')],
        'physics': [_re_chain('mhws')],
    },
    're4': {
        'label': "RE4 Tools", 'icon': 'GHOST_ENABLED',
        'io': [_batch_export('re4', "ui.game_sections.btn_batch_export_re4")],
        'rig': [
            op("re4.fakebone_one_click", "ui.main_panel.btn_gen_fakebone",
               'ARMATURE_DATA', needs='re_fbxskel'),
            _face_weights('RE4'),
            op("re4.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
        ],
        'material': [_tex_convert('RE4')] + [_mdf_pair('re4')],
        'physics': [_re_chain('re4')],
    },
    'mhrs': {
        'label': "MHRS Tools", 'icon': 'GHOST_ENABLED',
        'io': [_batch_export('mhrs', "ui.game_sections.btn_batch_export_mhrs")],
        'rig': [],
        'material': [_tex_convert('MHRS')] + [_mdf_pair('mhrs')],
        'physics': [_re_chain('mhrs')],
    },
    're9': {
        'label': "RE9 Tools", 'icon': 'GHOST_ENABLED',
        'io': [_batch_export('re9', "ui.game_sections.btn_batch_export_re9")],
        'rig': [
            op("re9.sync_child_orientation",
               "ui.main_panel.btn_sync_child_orientation", 'CON_ROTLIKE'),
            _face_weights('RE9'),
            op("re9.add_facial_bones", "ui.main_panel.btn_add_facial_bones",
               'SHAPEKEY_DATA'),
        ],
        'material': [_tex_convert('RE9')] + [_mdf_pair('re9')],
        'physics': [_re_chain('re9')],
    },
}


# ── Drawing ───────────────────────────────────────────────────────────────────

def _draw_button(layout, entry, guard_state, missing):
    need = entry['needs']
    if need is not None:
        ok = guard_state[need]
        layout.enabled = ok
        if not ok:
            missing.add(need)
    props = layout.operator(entry['op'], text=T(entry['text']), icon=entry['icon'])
    for k, v in entry['props'].items():
        setattr(props, k, v)


def _visible(entry):
    return entry['only_if'] is None or entry['only_if']()


def _draw_group(box, entries, guard_state):
    missing = set()
    col = box.column(align=True)
    for entry in entries:
        if isinstance(entry, list):
            pair = [e for e in entry if _visible(e)]
            if not pair:
                continue
            row = col.row(align=True)
            for e in pair:
                _draw_button(row.row(align=True), e, guard_state, missing)
        elif _visible(entry):
            _draw_button(col.row(align=True), entry, guard_state, missing)
    # One line per missing dependency, not one per button that needs it.
    for need in sorted(missing):
        col.label(text=T(GUARDS[need][1]), icon='ERROR')


def draw_section(layout, game_key):
    """Draw one game's tool box."""
    spec = SECTIONS[game_key]
    guard_state = {name: probe() for name, (probe, _msg) in GUARDS.items()}

    box = layout.box()
    box.label(text=spec['label'], icon=spec['icon'])

    for group in GROUP_ORDER:
        entries = spec.get(group) or []
        if not entries:
            continue
        label_key, icon = GROUP_LABELS[group]
        sub = box.box()
        sub.label(text=T(label_key), icon=icon)
        _draw_group(sub, entries, guard_state)
