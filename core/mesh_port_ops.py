"""RE Mesh port, execution layer: carry out a plan on a real rig, plus the operator.

The planning half is ``core/mesh_port.py``; everything here needs Blender.  Three
decisions shape this file:

**It always works on a copy, and copies the meshes with the armature.**  Two separate
reasons, both load-bearing: editing a rig in place drops the bindings of any RE Chain
data already attached to it, and merging bones has to move *vertex groups*, which live
on the meshes -- copy the armature alone and the weights have nowhere to go.  (The
chain port is the opposite: it edits in place, because duplicating a chain collection
would leave its links pointing at the original's groups by object name.)

**Bone orientation is changed by posing and applying, not by writing edit_bones.**
``core/pose_ops.py`` already solved this shape of problem: pose the bones, then
``_apply_and_rebind()`` bakes the pose into the rest skeleton and re-binds the meshes,
so skinning follows the change instead of tearing.  Writing rest matrices directly
would leave every mesh bound to the old rest.

**The axis correction C is derived from the two rigs at run time, never from a baked
table of constants.**  Bone *positions* differ per character by 130-160 mm between
body types while orientations do not, so anything position-shaped must be measured on
the actual asset.  C itself is gated by ``core.bone_correction``: bones whose derived C
is not a signed permutation fall back to the validated table or are reported -- never
silently replaced by identity, which would leave that bone in the source game's
convention with nothing to show for it until an animation twists it in-game.
"""

import bpy
from mathutils import Matrix, Vector

from . import bone_utils
from .bone_correction import (DEFAULT_TOLERANCE_DEG, derive_bone_correction,
                              same_convention_set)
from .bone_mapper import BoneMapManager, auto_detect_preset, build_cross_game_map
from .i18n import T
from .mesh_port import build_port_plan
from .ref_skeleton import get_reference_skeleton_items, import_reference_armature
from .weight_utils import merge_weights_and_delete_bones

#: Games sharing one axis convention: a port between any two of them needs no C.
#: RE9 is the only registered member of the other family.
FAMILY_A = frozenset({"MHWS", "RE4", "SF6", "DMC5", "MHR", "MHWR"})

#: Ported rigs are offered for the same three games the chain port covers -- the ones
#: with a reference skeleton to derive against and hand-made ground truth to check.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9")

#: Reference skeletons live under assets/reference_skeletons/<lowercased game_code>/.
_REF_DIRS = {"MHWS": "mhws", "RE4": "re4", "RE9": "re9"}

_TEMP_PREFIX = "__port_tmp__"


def mhws_insert_rules():
    """MHWilds helper placement, borrowed rather than restated.

    ``MHWS_OT_OptimizeAuxBones`` already carries the tables for all 39 ``_HJ_`` /
    ``Palm`` helpers, including the twist bones that sit at a limb's midpoint.  A
    second copy here would drift from it silently, so it is imported -- lazily,
    because ``core`` is otherwise below ``games`` and only this one borrow crosses.
    """
    try:
        from ..games.mhws.operators import _HJ_MOVE_DIRECT, _HJ_MOVE_MIDPOINT
    except Exception:
        return {}
    rules = {hj: ("colocate", base) for hj, base in _HJ_MOVE_DIRECT.items()}
    rules.update({hj: ("midpoint", tuple(pair))
                  for hj, pair in _HJ_MOVE_MIDPOINT.items()})
    return rules


def _preset_by_game():
    """``{game_code: filename}`` for the shipped bone presets."""
    import json
    import os
    out = {}
    mgr = BoneMapManager()
    root = os.path.dirname(mgr.get_preset_path("x.json"))
    if not os.path.isdir(root):
        return out
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(root, fname), "r", encoding="utf-8") as f:
                info = json.load(f).get("preset_info", {})
        except Exception:
            continue
        code = info.get("game_code")
        if code and code not in out:
            out[code] = fname
    return out


def _preset_main_names(fname):
    mgr = BoneMapManager()
    if not mgr.load_preset(fname):
        return set()
    return {n for entry in mgr.mapping_data.values() for n in entry.get("main", ())}


# ── plan execution ──────────────────────────────────────────────────────────────

def _rename_bones(arm_obj, pairs):
    """Rename through a temporary prefix so a rename never collides with a name that
    has not been vacated yet -- Blender would answer a collision by silently appending
    ``.001``, and the export would then hash a name no rig has.

    Vertex groups follow: Blender's bone rename renames the matching groups on every
    mesh bound to the armature, which is why this does not touch them by hand.
    """
    bones = arm_obj.data.bones
    staged = []
    for src, dst in pairs:
        b = bones.get(src)
        if b is None:
            continue
        b.name = _TEMP_PREFIX + dst
        staged.append(dst)
    for dst in staged:
        b = bones.get(_TEMP_PREFIX + dst)
        if b is not None:
            b.name = dst
    return len(staged)


def _insert_bones(arm_obj, inserts, ref_arm):
    """Create the target game's missing base bones, placed by the plan's rules.

    Direction and roll are copied from the reference model's own bone; only the head
    position comes from the rules, since that is the part that has to follow *this*
    character's proportions rather than the reference character's.
    """
    if not inserts:
        return 0
    ref_bones = ref_arm.data.bones if ref_arm is not None else {}
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    made = 0
    try:
        for name, rule, anchor in inserts:
            if name in eb:
                continue
            ref = ref_bones.get(name) if ref_bones else None
            if rule == "colocate":
                a = eb.get(anchor)
                if a is None:
                    continue
                head = a.head.copy()
                parent = eb.get(ref.parent.name) if (ref and ref.parent) else a
            elif rule == "midpoint":
                a, b = (eb.get(n) for n in anchor)
                if a is None or b is None:
                    continue
                head = (a.head + b.head) / 2.0
                parent = eb.get(ref.parent.name) if (ref and ref.parent) else a
            else:                                   # ref_offset
                if ref is None or ref.parent is None:
                    continue
                parent = eb.get(ref.parent.name)
                if parent is None:
                    continue
                head = parent.head + (ref.head_local - ref.parent.head_local)

            new = eb.new(name)
            new.head = head
            if ref is not None:
                vec = ref.tail_local - ref.head_local
                new.tail = head + vec
                new.align_roll(ref.matrix_local.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            else:
                new.tail = head + Vector((0.0, 0.0, 0.01))
            new.parent = parent if parent is not None else None
            new.use_connect = False

            # A base bone inserted mid-chain has to take over its children, or it
            # ends up a dangling sibling: measured on a real MHWS -> RE4 run, the
            # inserted Neck_0 sat under Spine_2 next to Neck_1 instead of between
            # them, so RE4's Neck_0 animation channel would have driven nothing.
            # Which bones are its children is read from the reference rig, and only
            # bones currently parented to the *same* parent are moved -- so this
            # re-links the chain without re-shaping anything else.
            #
            # Compared by name, not by identity: Blender hands out a fresh Python
            # wrapper on each RNA access, so ``child.parent is parent`` is False even
            # for the same bone, which silently skipped every re-parent (that is how
            # the dangling Neck_0 survived the first attempt at this fix).
            if ref is not None and parent is not None:
                for child_ref in ref.children:
                    child = eb.get(child_ref.name)
                    if (child is not None and child.name != name
                            and child.parent is not None
                            and child.parent.name == parent.name):
                        child.parent = new
            made += 1
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return made


def apply_corrections(arm_obj, correction_set):
    """Re-express every mapped bone's rest orientation in the target's convention.

    Joint *positions* are held fixed on purpose: a convention change is a relabeling
    of axes, so no joint may move.  Each bone's world matrix is therefore written
    explicitly, parent first, with the rotation replaced and the original head kept --
    including bones with no correction, whose orientation must be pinned back after a
    corrected parent would otherwise have swung them.  Per-asset hair and cloth bones
    ride along that way, unchanged in both position and orientation.

    Ends by baking the pose into the rest skeleton and re-binding the meshes, exactly
    as ``modder.ree_to_tpose`` does.
    """
    from .pose_ops import _apply_and_rebind

    bones = list(arm_obj.data.bones)
    original = {}
    for b in bones:
        original[b.name] = (b.matrix_local.to_3x3().copy(), b.head_local.copy())

    def depth(b):
        n, p = 0, b.parent
        while p is not None:
            n, p = n + 1, p.parent
        return n

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    changed = 0
    for b in sorted(bones, key=depth):
        pb = arm_obj.pose.bones.get(b.name)
        if pb is None:
            continue
        rot, head = original[b.name]
        c = correction_set.get(b.name) if correction_set is not None else None
        if c is not None and not c.is_identity:
            rot = rot @ Matrix([list(r) for r in c.matrix])
            changed += 1
        m = rot.to_4x4()
        m.translation = head
        pb.matrix = m
        bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='OBJECT')

    _apply_and_rebind(arm_obj)
    return changed


def execute_port(arm_obj, plan, ref_arm=None, correction_set=None):
    """Run *plan* on *arm_obj* (already a copy).  Returns a counts dict."""
    counts = {"merged": 0, "renamed": 0, "inserted": 0, "corrected": 0}

    if plan.merges:
        # (keep, delete) is the order merge_weights_and_delete_bones expects; it also
        # resolves chains of merges onto the final survivor.
        merge_weights_and_delete_bones(arm_obj, [(into, src) for src, into in plan.merges])
        counts["merged"] = len(plan.merges)

    counts["renamed"] = _rename_bones(arm_obj, plan.renames)
    counts["inserted"] = _insert_bones(arm_obj, plan.inserts, ref_arm)
    if correction_set is not None:
        counts["corrected"] = apply_corrections(arm_obj, correction_set)
    return counts


# ── operator ────────────────────────────────────────────────────────────────────

_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _target_game_items(self, context):
    presets = _preset_by_game()
    items = [(c, c, "", i) for i, c in enumerate(
        c for c in PORTABLE_GAMES if c != self.source_game and c in presets)]
    if not items:
        items = [("NONE", "-", "", 0)]
    return _cached("target_game", items)


def _reference_items(self, context):
    game = _REF_DIRS.get(self.target_game, "")
    return _cached("reference", list(get_reference_skeleton_items(game)))


class MODDER_OT_PortMeshCrossGame(bpy.types.Operator):
    bl_idname = "modder.port_mesh_cross_game"
    bl_label = "Port Mesh to Another Game"
    #: No 'UNDO', which would put this in the redo panel where adjusting a property
    #: re-runs the operator.  The port is not idempotent -- a second run would port
    #: the copy it just made -- and it writes through bpy.data, so the undo stack
    #: cannot take the result back either.  It must run exactly once per click.
    bl_options = {'REGISTER'}

    source_game: bpy.props.StringProperty(options={'HIDDEN'})
    #: A name, not an EnumProperty.  A dynamic enum's stored value is an index into a
    #: list rebuilt on every access, and this operator grows the object list mid-run by
    #: importing the reference skeleton -- so the safe thing is a value that cannot be
    #: re-resolved at all.  ``prop_search`` gives the same picker in the dialog.
    source_armature: bpy.props.StringProperty(name="Source Armature")
    target_game: bpy.props.EnumProperty(name="Target Game", items=_target_game_items)
    reference_skeleton: bpy.props.EnumProperty(
        name="Reference Skeleton", items=_reference_items)
    replace_original: bpy.props.BoolProperty(
        name="Replace the Original", default=False,
        description="Convert the original in place instead of converting a copy")

    @classmethod
    def description(cls, context, properties):
        return T("core.mesh_port_ops.desc")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in bpy.data.objects)

    def invoke(self, context, event):
        self._lines = []
        self._blocked = True
        return context.window_manager.invoke_props_dialog(self, width=480)

    def check(self, context):
        self._preflight(context)
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop_search(self, "source_armature", bpy.data, "objects",
                           text=T("core.mesh_port_ops.source_armature"))
        layout.prop(self, "target_game", text=T("core.mesh_port_ops.target_game"))
        layout.prop(self, "reference_skeleton",
                    text=T("core.mesh_port_ops.reference_skeleton"))
        layout.prop(self, "replace_original",
                    text=T("core.port.replace_original"))
        if not getattr(self, "_lines", None):
            self._preflight(context)
        box = layout.box()
        for icon, text in self._lines:
            box.label(text=text, icon=icon)

    # ── preflight ──────────────────────────────────────────────────────────────

    def _plan_for(self, arm, ref_arm):
        presets = _preset_by_game()
        src, dst = presets.get(self.source_game), presets.get(self.target_game)
        if not src or not dst:
            return None, None
        cross = build_cross_game_map(src, dst)
        if cross is None:
            return None, None
        extra = mhws_insert_rules() if self.target_game == "MHWS" else None
        plan = build_port_plan(
            [b.name for b in arm.data.bones], cross,
            src_main_names=_preset_main_names(src),
            dst_bones=({b.name for b in ref_arm.data.bones}
                       if ref_arm is not None else None),
            extra_rules=extra)
        return plan, cross

    def _preflight(self, context):
        self._lines = []
        self._blocked = True
        arm = bpy.data.objects.get(self.source_armature)
        if arm is None or arm.type != 'ARMATURE':
            self._lines = [('INFO', T("core.mesh_port_ops.pick_target"))]
            return

        detected = auto_detect_preset(arm, False)
        if detected:
            mgr = BoneMapManager()
            code = mgr.preset_info.get("game_code") if mgr.load_preset(detected) else None
            if code and self.source_game and code != self.source_game:
                self._lines = [('ERROR', T("core.mesh_port_ops.wrong_source_game").format(
                    found=code, expected=self.source_game))]
                return

        plan, _cross = self._plan_for(arm, None)
        if plan is None:
            self._lines = [('ERROR', T("core.mesh_port_ops.pick_target"))]
            return

        self._lines.append(('INFO', T("core.mesh_port_ops.stat_plan").format(
            renamed=len(plan.renames), merged=len(plan.merges),
            inserted=len(plan.inserts), kept=len(plan.passthrough))))
        if plan.clashes:
            names = ", ".join(f"{s}->{d}" for s, d in plan.clashes[:3])
            self._lines.append(('ERROR', T("core.mesh_port_ops.name_clash").format(
                n=len(plan.clashes), names=names)))
        if plan.uninsertable:
            self._lines.append(('ERROR', T("core.mesh_port_ops.unplaceable").format(
                n=len(plan.uninsertable),
                names=", ".join(plan.uninsertable[:4]))))
        if self.target_game not in FAMILY_A or self.source_game not in FAMILY_A:
            self._lines.append(('INFO', T("core.mesh_port_ops.needs_correction")))
        if plan.ok:
            self._lines.append(('CHECKMARK', T("core.mesh_port_ops.all_resolved")))
        self._blocked = not plan.ok

    # ── execute ────────────────────────────────────────────────────────────────

    def execute(self, context):
        arm = bpy.data.objects.get(self.source_armature)
        if arm is None or arm.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.mesh_port_ops.pick_target"))
            return {'CANCELLED'}

        # Copy unless told otherwise. The meshes come too: merging supernumerary
        # bones moves vertex groups, which live on the mesh, so an armature-only
        # copy would have nothing to transfer the weights on.
        if not self.replace_original:
            arm = bone_utils.duplicate_armature_with_meshes(
                arm, f"{arm.name}_{self.target_game}")

        ref_arm = None
        if self.reference_skeleton and self.reference_skeleton != "NONE":
            ref_arm = import_reference_armature(_REF_DIRS.get(self.target_game, ""),
                                                self.reference_skeleton)
        try:
            plan, cross = self._plan_for(arm, ref_arm)
            if plan is None:
                self.report({'ERROR'}, T("core.mesh_port_ops.pick_target"))
                return {'CANCELLED'}
            if not plan.ok:
                self.report({'ERROR'}, T("core.mesh_port_ops.blocked").format(
                    detail="; ".join(plan.uninsertable)))
                return {'CANCELLED'}

            cross_convention = (self.source_game in FAMILY_A) != (
                self.target_game in FAMILY_A)
            correction_set = None
            if cross_convention:
                from .pose_ops import _REE_BONE_CORRECTION
                if ref_arm is None:
                    self.report({'ERROR'}, T("core.mesh_port_ops.need_reference"))
                    return {'CANCELLED'}
                correction_set = derive_bone_correction(
                    arm, ref_arm, cross,
                    table=_REE_BONE_CORRECTION.get(self.target_game),
                    tolerance_deg=DEFAULT_TOLERANCE_DEG,
                    src_game=self.source_game, dst_game=self.target_game)
                if correction_set.pose_mismatch_suspected:
                    # Over half the bones failed the signed-permutation gate, which
                    # means the two rigs are not in the same physical pose -- the
                    # derivation's precondition.  Running modder.ree_to_tpose on both
                    # fixes it (measured: 11 derived before, 39 after).
                    self.report({'ERROR'}, T("core.mesh_port_ops.pose_mismatch").format(
                        rejected=len(correction_set.rejected)))
                    return {'CANCELLED'}

            counts = execute_port(arm, plan, ref_arm, correction_set)
        finally:
            if ref_arm is not None:
                bpy.data.objects.remove(ref_arm, do_unlink=True)

        msg = T("core.mesh_port_ops.done").format(
            game=self.target_game, name=arm.name, **counts)
        if correction_set is not None and correction_set.rejected:
            msg += " " + T("core.mesh_port_ops.rejected").format(
                n=len(correction_set.rejected),
                names=", ".join(b for b, _t, _d in correction_set.rejected[:4]))
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


classes = [MODDER_OT_PortMeshCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
