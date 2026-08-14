"""The "Import Reference Model" button: bring in a vanilla body, optionally simplified.

Modelled on Modder Batch Tool's MHWilds import, which offers exactly two switches --
merge facial bones, convert to T-pose -- and which ``mhws.preprocess_model`` already
copies internally as steps 3a-3c.  This exposes the same thing as a standalone button
for every game, plus a third switch for auxiliary bones, and picks the character where
a game ships more than one (RE4R has Leon / Ada / Ashley, RE9 has Leon / Grace).

Order is not arbitrary.  Merges run **before** the T-pose conversion: T-posing rewrites
rest orientations, and doing it first would mean the merge -- which walks the parent
chain -- runs on a rig whose helper bones have already been swung.  MBT sequences it
the same way.

What each game supports comes from ``core/ref_model.py``; the options a game cannot do
are drawn disabled with the reason, rather than silently ignored.
"""

import os

import bpy

from . import ref_model, ref_skeleton, weight_utils
from .i18n import T
from .re_mesh_compat import call_re_mesh_op, re_mesh_op_available

_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _model_items(self, context):
    """Cached **per game**: one shared cache list would be refilled with another
    game's models while Blender still points at it."""
    game = self.source_game or ""
    entries = ref_model.MODELS.get(game, ())
    items = [(ident, T(label) if label else ident.capitalize(), "", i)
             for i, (ident, label, _kind, _payload) in enumerate(entries)]
    if not items:
        items = [("NONE", "-", "", 0)]
    return _cached("model:" + game, items)


def _entry(game, ident):
    for e in ref_model.MODELS.get(game, ()):
        if e[0] == ident:
            return e
    return None


def _repo_path(rel):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel.replace("/", os.sep))


def _op_available(op_id):
    """Probe an operator with ``dir()``, since attribute access on ``bpy.ops`` is
    lazy and answers True for anything -- the trap ``ui/game_sections.py``'s GUARDS
    and ``core/re_mesh_compat.py`` both document."""
    category, _, name = op_id.partition(".")
    ns = getattr(bpy.ops, category, None)
    try:
        return ns is not None and name in dir(ns)
    except Exception:
        return False


#: MHW Model Editor's MOD3 importer, which reads the bundled MHWI bodies.
_MOD3_IMPORT_OP = "mhw_mod3.import_mhw_mod3"


def model_available(game, ident):
    """(ok, i18n reason key) -- can this model be imported right now?"""
    entry = _entry(game, ident)
    if entry is None:
        return False, "core.ref_model_ops.no_model"
    _ident, _label, kind, payload = entry
    if kind == "fbx":
        subdir, filename = payload
        path = os.path.join(ref_skeleton.get_reference_skeleton_dir(subdir), filename)
        return (True, None) if os.path.isfile(path) else (False, "core.ref_model_ops.file_missing")
    if kind == "remesh":
        if not os.path.isfile(_repo_path(payload)):
            return False, "core.ref_model_ops.file_missing"
        if not re_mesh_op_available("importfile"):
            return False, "ui.main_panel.label_need_re_mesh_editor"
        return True, None
    if kind == "mod3":
        if not os.path.isfile(_repo_path(payload)):
            return False, "core.ref_model_ops.file_missing"
        if not _op_available(_MOD3_IMPORT_OP):
            return False, "ui.main_panel.label_need_mhw_model_editor"
        return True, None
    if kind == "mbt":
        return (True, None) if _op_available(payload) else (False, "core.ref_model_ops.need_mbt")
    return False, "core.ref_model_ops.no_model"


def import_model(game, ident):
    """Import the model and return the armature object, or None.

    The FBX path deliberately does **not** go through
    ``ref_skeleton.import_reference_armature``: that one keeps the armature and
    throws the rest away, which is right for a skeleton used as a measuring stick and
    wrong here -- this button imports a *model*, and the body mesh is most of the
    point.  It is also what the merges act on: without the mesh there are no vertex
    groups, so merging bones would just delete them.
    """
    entry = _entry(game, ident)
    if entry is None:
        return None
    _ident, _label, kind, payload = entry

    before = set(bpy.data.objects)
    if kind == "fbx":
        subdir, filename = payload
        path = os.path.join(ref_skeleton.get_reference_skeleton_dir(subdir), filename)
        if not os.path.isfile(path):
            return None
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.import_scene.fbx(filepath=path, use_custom_props=True,
                                 force_connect_children=False)
        made = [o for o in bpy.data.objects if o not in before]
        return next((o for o in made if o.type == 'ARMATURE'), None)

    if kind == "remesh":
        path = _repo_path(payload)
        call_re_mesh_op('importfile', 'EXEC_DEFAULT',
                        directory=os.path.dirname(path) + os.sep,
                        files=[{"name": os.path.basename(path)}],
                        loadMaterials=False)
    elif kind == "mod3":
        path = _repo_path(payload)
        if not os.path.isfile(path):
            return None
        # directory + files, not filepath: the importer iterates self.files, so a
        # filepath on its own imports nothing and still reports success -- the same
        # reason the remesh branch above is written this way.
        # clearScene stays off: this button adds a reference next to whatever the
        # user is working on, it does not take the file over.
        # Materials off, like the remesh branch: a reference body is imported to
        # measure and rig against, and leaving them on makes the importer warn about
        # the .mrl3 that deliberately is not shipped beside it.
        bpy.ops.mhw_mod3.import_mhw_mod3(
            'EXEC_DEFAULT',
            directory=os.path.dirname(path) + os.sep,
            files=[{"name": os.path.basename(path)}],
            clearScene=False, loadMrl3Data=False, loadMaterials=False)
    elif kind == "mbt":
        category, _, name = payload.partition(".")
        getattr(getattr(bpy.ops, category), name)('EXEC_DEFAULT')
    else:
        return None
    made = [o for o in bpy.data.objects if o not in before]
    return next((o for o in made if o.type == 'ARMATURE'), None)


def _parents(arm_obj):
    return {b.name: (b.parent.name if b.parent else None) for b in arm_obj.data.bones}


def _mhws_facial_list():
    """MHWilds' facial bones, borrowed from the operator that already lists them.

    Lazy import for the same reason ``mesh_port_ops`` borrows the helper tables:
    ``core`` sits below ``games``, and this one list is not worth a second copy that
    can drift.
    """
    try:
        from ..games.mhws.operators import _MHWS_FACIAL_MERGE_BONES
    except Exception:
        return ()
    return _MHWS_FACIAL_MERGE_BONES


def apply_merges(arm_obj, game, merge_facial, merge_aux):
    """Run the requested merges.  Returns ``(facial_merged, aux_merged)``."""
    mhws_list = _mhws_facial_list() if game == "MHWS" else ()
    done = [0, 0]

    # Facial first: the auxiliary set is computed against the rig as it stands, and
    # collapsing the face first keeps that set from containing bones that no longer
    # exist by the time it runs.
    if merge_facial:
        parents = _parents(arm_obj)
        pairs = ref_model.plan_merges(
            parents, ref_model.facial_doomed(game, parents, mhws_list))
        if pairs:
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
        done[0] = len(pairs)

    if merge_aux:
        parents = _parents(arm_obj)
        doomed = ref_model.aux_doomed(game, parents, mhws_list)
        if doomed:
            pairs = ref_model.plan_merges(parents, doomed)
            if pairs:
                weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            done[1] = len(pairs)
    return tuple(done)


class MODDER_OT_ImportReferenceModel(bpy.types.Operator):
    bl_idname = "modder.import_reference_model"
    bl_label = "Import Reference Model"
    #: No 'UNDO' for the same reason as the mesh port: the merges go through
    #: ``bpy.data``, so a redo-panel re-run would import a second copy rather than
    #: revise the first.
    bl_options = {'REGISTER'}

    source_game: bpy.props.StringProperty(options={'HIDDEN'})
    model: bpy.props.EnumProperty(name="Model", items=_model_items)
    to_tpose: bpy.props.BoolProperty(name="To T-Pose", default=True)
    merge_facial: bpy.props.BoolProperty(name="Merge Facial Bones", default=True)
    merge_aux: bpy.props.BoolProperty(name="Merge Auxiliary Bones", default=False)

    @classmethod
    def description(cls, context, properties):
        return T("core.ref_model_ops.desc")

    def invoke(self, context, event):
        # Blender remembers an operator's last-used property values, and this one is
        # shared by five sections whose model lists have nothing in common.  Opening
        # RE4R's dialog (model="leon") and then MHWilds' left "leon" in place, which
        # matches no MHWilds entry -- the dialog then reported "no reference model
        # registered" for a game that plainly has one.  Reset to this game's first
        # model whenever the carried-over value does not belong to it.
        self.model = self._valid_model()
        return context.window_manager.invoke_props_dialog(self, width=380)

    def _valid_model(self):
        """The chosen model if this game has it, else its first one."""
        entries = ref_model.MODELS.get(self.source_game, ())
        idents = [e[0] for e in entries]
        try:
            current = self.model
        except (TypeError, ValueError):
            current = None
        if current in idents:
            return current
        return idents[0] if idents else "NONE"

    def draw(self, context):
        layout = self.layout
        game = self.source_game
        if len(ref_model.MODELS.get(game, ())) > 1:
            layout.prop(self, "model", text=T("core.ref_model_ops.model"))

        if game not in ref_model.OPTIONLESS_GAMES:
            col = layout.column(align=True)
            col.prop(self, "to_tpose", text=T("core.ref_model_ops.to_tpose"))
            col.prop(self, "merge_facial", text=T("core.ref_model_ops.merge_facial"))

            aux = layout.row()
            aux.enabled = ref_model.load_base_bones(game) is not None
            aux.prop(self, "merge_aux", text=T("core.ref_model_ops.merge_aux"))
            if not aux.enabled:
                layout.label(text=T("core.ref_model_ops.no_native_skeleton"), icon='INFO')

        ok, reason = model_available(game, self._valid_model())
        if not ok:
            layout.label(text=T(reason), icon='ERROR')

    def execute(self, context):
        game = self.source_game
        model = self._valid_model()
        ok, reason = model_available(game, model)
        if not ok:
            self.report({'ERROR'}, T(reason))
            return {'CANCELLED'}

        arm = import_model(game, model)
        if arm is None:
            self.report({'ERROR'}, T("core.ref_model_ops.import_failed"))
            return {'CANCELLED'}

        facial = aux = 0
        posed = False
        if game not in ref_model.OPTIONLESS_GAMES:
            facial, aux = apply_merges(arm, game, self.merge_facial, self.merge_aux)
            if self.to_tpose:
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')
                arm.select_set(True)
                context.view_layer.objects.active = arm
                bpy.ops.modder.ree_to_tpose()
                posed = True

        self.report({'INFO'}, T("core.ref_model_ops.done").format(
            name=arm.name, facial=facial, aux=aux,
            pose=T("core.ref_model_ops.posed") if posed else "-"))
        return {'FINISHED'}


classes = [MODDER_OT_ImportReferenceModel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
