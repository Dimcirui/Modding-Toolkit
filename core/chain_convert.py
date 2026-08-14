"""Cross-game chain/chain2 conversion, scene-side: re-attach colliders.

Why this works on bone *names* and not hashes: RE-Chain-Editor computes a
collider's ``jointNameHash`` at export time from the object's bone constraint --
``hash_wide(obj.constraints["BoneName"].subtarget)``
(``re_chain_propertyGroups.py``) -- and on import it *skips* any collider whose
hash resolves to no bone on the armature (``blender_re_chain.py``, which also
raises a warning).  So a collider that exists in the scene is always bound to a
real bone by name, and converting it means rewriting that name.  ``core/re_hash.py``
is not on this path; it is for offline file inspection and tests.

Scope is deliberately narrow.  Chain physics itself never attaches to base
skeleton bones -- only colliders do.  Node-side references (``jointHash``,
``constraintJntNameHash``, ``terminateNodeNameHash``) point at per-asset
hair/cloth bones that travel with the model, so their names, and therefore their
hashes, are already identical in the target game.  Measured on shipped files:
24/24 collider attach points resolve to standard skeleton bones, while 0/196
terminate-node hashes resolve against 5272 pooled bones from 21 armatures.

**Every other collider parameter is inherited verbatim, including the local offset.**
No axis-convention correction is applied even when crossing convention families, and
that is deliberate: a collider is positioned from **joint coordinates only** -- bone
rotation and twist do not enter -- and a capsule's axis comes from the positions of
its two joints (``jointNameHash`` and ``pairJointNameHash``), not from any rotation.
So the only thing that has to be right is that the bone a collider lands on means the
same body part, which is what the mapping above guarantees.  Positions need not match
a hand-made port exactly; colliders are coarse volumes (measured radii 37-144 mm) and
the small residual is the user's to nudge if it ever matters.

``core/bone_correction.py`` exists for the cases that *do* need C -- validating a
reference skeleton's pose, and converting skeletons, where bone orientation drives
skinning and animation.  It is intentionally not wired in here.

Validated against hand-made ground truth (one model shipped as MHWS, RE4R and
RE9 mods, authored independently per game): mapping the 18 MHWS collider attach
points gives, at bone-slot level, **no destination the author did not also use**
in either target -- every difference is a collider they chose to add or drop.
"""

import bpy

#: Collider object markers RE-Chain-Editor puts in ``obj["TYPE"]``.
COLLIDER_TYPES = frozenset({
    "RE_CHAIN_COLLISION_SINGLE",
    "RE_CHAIN_COLLISION_CAPSULE_ROOT",
})

#: The bone constraint RE-Chain-Editor binds every collider through.
BONE_CONSTRAINT = "BoneName"


class RemapReport:
    """What a re-attach pass did, or would do in a dry run.

    remapped        : [(obj_name, old_bone, new_bone)] -- bone actually changed
    unchanged       : count of bindings whose bone name is the same in both games
    unmapped        : [(obj_name, bone)] -- no cross-game mapping for this bone.
                      **This is the case to surface to the user**: exporting it
                      would hash a name the target skeleton does not have, and
                      the game would get a collider bound to nothing.  Node-side
                      pass-through is fine, collider-side is not.
    missing_in_target: [(obj_name, new_bone)] -- mapped, but the target armature
                      has no such bone (stale preset, or wrong armature passed)
    collapsed       : {new_bone: [old_bone, ...]} -- several distinct attach
                      points merged onto one target bone.  Their local offsets
                      may need compensating; measured ~28 mm for MHWilds
                      L_Knee/L_Shin, about 40 % of a typical capsule radius.
                      Must be measured per asset -- the sign flips between rigs.
    """

    def __init__(self):
        self.remapped = []
        self.unchanged = 0
        self.unmapped = []
        self.missing_in_target = []
        self.collapsed = {}

    @property
    def ok(self):
        """True when every collider binding landed on a bone the target has."""
        return not self.unmapped and not self.missing_in_target

    def summary(self):
        parts = [f"{len(self.remapped)} re-attached", f"{self.unchanged} unchanged"]
        if self.unmapped:
            parts.append(f"{len(self.unmapped)} UNMAPPED")
        if self.missing_in_target:
            parts.append(f"{len(self.missing_in_target)} MISSING IN TARGET")
        if self.collapsed:
            parts.append(f"{len(self.collapsed)} merged target bone(s)")
        return ", ".join(parts)


def iter_collider_bindings(collection):
    """Yield ``(obj, constraint)`` for every collider bone binding in a collection.

    Capsule colliders keep their two endpoints as child objects, each with its own
    ``BoneName`` constraint, so children are walked too -- a capsule spans two
    bones and both ends need converting.
    """
    for obj in collection.all_objects:
        if obj.get("TYPE") not in COLLIDER_TYPES:
            continue
        for candidate in (obj, *obj.children):
            con = candidate.constraints.get(BONE_CONSTRAINT)
            if con is not None and getattr(con, "subtarget", ""):
                yield candidate, con


def remap_collider_attachments(collection, cross_map, target_armature=None,
                               dry_run=False):
    """Re-attach every collider in *collection* from the source game's bones to
    the target game's, using a ``CrossGameBoneMap`` from
    ``core.bone_mapper.build_cross_game_map``.

    *target_armature* is optional but strongly recommended: without it a mapping
    onto a bone the target rig lacks cannot be detected here, and the failure
    surfaces only in-game -- where, per the MHWmodfixer findings, broken chain
    physics fails *at boot only* and no static check catches it.

    Only the bone binding is rewritten.  Offsets, radii and every other parameter stay
    as authored -- see the module docstring for why an axis correction is neither
    applied nor needed here.

    With ``dry_run=True`` nothing is written; the report says what would happen.
    Use that to inspect a conversion before touching the scene.
    """
    report = RemapReport()
    target_bones = None
    if target_armature is not None and target_armature.type == 'ARMATURE':
        target_bones = set(target_armature.data.bones.keys())

    for obj, con in iter_collider_bindings(collection):
        old = con.subtarget
        new = cross_map.get(old)

        if new is None:
            report.unmapped.append((obj.name, old))
            continue

        if target_bones is not None and new not in target_bones:
            report.missing_in_target.append((obj.name, new))
            continue

        if new == old:
            report.unchanged += 1
        else:
            report.remapped.append((obj.name, old, new))
            if not dry_run:
                con.subtarget = new
                if target_armature is not None:
                    con.target = target_armature

        report.collapsed.setdefault(new, [])
        if old not in report.collapsed[new]:
            report.collapsed[new].append(old)

    report.collapsed = {new: sorted(olds)
                        for new, olds in report.collapsed.items() if len(olds) > 1}
    return report


def collider_attach_bones(collection):
    """The distinct bone names every collider in *collection* is bound to.

    Handy for auditing an asset before conversion, and for comparing a converted
    result against a hand-made one.
    """
    return sorted({con.subtarget for _obj, con in iter_collider_bindings(collection)})
