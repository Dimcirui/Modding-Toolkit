"""Per-bone axis-convention correction C, derived from two rigs and gated by a test.

``C`` answers "how do this bone's axes differ between two games": with
``R_d = R_s · C``, a quantity expressed in the source bone's frame is re-expressed in
the target's as ``C⁻¹ · v``.  Family A games (RE4R, MHWilds, SF6, MHRS, DMC5) share one
convention, so C is identity among them; only crossing to RE9 needs it.

**What this is for.**  Two things need C: validating that a reference skeleton really
is in the pose it claims to be -- the signed-permutation gate below doubles as that
test -- and converting skeletons, where bone orientation drives skinning and animation
and a 20-degree error is ruinous.

**What it is deliberately *not* used for: chain colliders.**  A collider is positioned
from joint coordinates only -- bone rotation and twist do not enter -- and a capsule's
axis comes from the positions of its two joints.  So ``core/chain_convert.py`` inherits
collider parameters verbatim and only rewrites which bone they hang off; applying C
there would be precision theatre on volumes 37-144 mm across.

**C is derivable from two rigs — with one hard precondition.**
``C = R_src⁻¹ · R_dst``, both from ``bone.matrix_local.to_3x3()``.  This is *not* the
derivation that failed twice before (memory ``project_skeleton_convention_families``):
those back-solved from joint positions or limb directions, which pin only 2 of 3
rotational DOF and leave roll arbitrary, whereas two full orientation matrices pin
all 3.  The precondition is that **both rigs are in the same physical pose** — a
T-pose specifically is *not* required, but any pose delta is absorbed into C 1:1 and
silently corrupts it.

**How to establish that precondition: T-pose both rigs first.**  ``modder.ree_to_tpose``
is a rest-level conversion, not a temporary pose — it ends in ``_apply_and_rebind()``,
which runs ``bpy.ops.pose.armature_apply()`` and rebinds the meshes.  Running it on
both rigs removes the pose difference and leaves exactly the quantity wanted here:
with both zeroed to ``M₀ · C_game``, the derivation returns ``C_src⁻¹ · C_dst``, the
pure convention difference, with ``M₀`` cancelling out.

Deriving from *native* rest poses instead conflates convention with pose, which is the
error the gate below keeps catching.

Two limits of that normalisation, both real:

* Bones **outside** the game's T-pose zeroing list (spine, neck, hip, clavicle,
  thumbs) are not normalised, so their C stays confounded and the gate still rejects
  them.  T-posing does not rescue those.
* T-posing a rig that **already carries chain data** moves its colliders: they are
  bound with ``CHILD_OF`` constraints holding a stored ``inverse_matrix``, which goes
  stale the moment the bone's rest orientation changes.  Either T-pose before the
  chain data exists, or re-align the colliders afterwards.

A T-posed rig *is* shippable — RE Engine animation resolves bones by name hash and
only relative parent/child transforms matter, which is what the per-bone matrix work
in ``pose_ops`` preserves.

**The derivation carries its own validity test.**  A genuine axis relabeling must be a
signed permutation matrix (elements in {0, ±1}); a pose difference is not, and the
test is sharp — against an injected synthetic pose delta it fires at 2° (1° still
passes).  Bones that fail are never silently used: they fall back to a validated
table, or are reported and skipped.

Measured on the RE4R / RE9 rig pair (54 mappable bones), which shows how much the
T-pose step is worth:

===========================================  ========  ========
state                                        derived   rejected
===========================================  ========  ========
as authored (RE9 rig 14.86° off M₀·C_table)        11         43
after ``ree_to_tpose`` on the RE9 rig              39         15
===========================================  ========  ========

The 14.86° was a per-bone roll about each bone's own axis — it moves no joint, so it
is invisible in the pose, but it is exactly what the gate was rejecting.  Of the 39
derived, **36 match ``pose_ops``' validated table bit-for-bit** and the other 3 are
``Head`` / ``Hip`` / ``Spine_0``, which the table does not cover — so the derivation
reproduces the table and extends it.  The 15 still rejected are the thumbs (genuinely
not axis-aligned), the clavicles, and spine/neck — all bones outside the T-pose
zeroing list, plus the pinky metacarpal at a borderline 1.5°.

Only the rotation is needed.  The third-party reference script carries 4x4
corrections with translation columns because it rewrites file fields with no target
rig; when the target bone's own position is available, translation comes from the rig.

Deliberately free of ``bpy`` and ``mathutils`` so the geometry is unit-testable
outside Blender.  Matrices are plain row-major 3-tuples of 3-tuples, matching
Blender's ``M[row][col]`` indexing, so ``bone.matrix_local.to_3x3()`` converts with
``as_matrix3()``.
"""

import math

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

#: How far from the nearest signed permutation a derived C may sit and still be
#: trusted, in degrees.  Placed in the gap the live measurement showed: on the RE4R /
#: RE9 rig pair the 22 genuinely convention-only bones topped out at **1.03°** while
#: the nearest contaminated one (`Spine_2`) sat at **1.62°**, so 1.3 separates them
#: cleanly.  Consistent with the injected-pose probe, which used an element-wise 0.02
#: threshold (≈1.15° of rotation) and fired at 2° while 1° still passed.
#: Loosening this to 2.0 would start admitting contaminated bones.
DEFAULT_TOLERANCE_DEG = 1.3


def as_matrix3(m):
    """Row-major 3x3 tuple from anything indexable as ``m[row][col]``."""
    return tuple(tuple(float(m[i][j]) for j in range(3)) for i in range(3))


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def mat_apply(m, vec):
    """``m @ vec`` with vec a column vector, matching Blender's convention."""
    return tuple(sum(m[i][j] * vec[j] for j in range(3)) for i in range(3))


def determinant(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def is_rotation(m, tol=1e-3):
    """True when *m* is orthonormal with det +1, i.e. a pure rotation.

    Checked rather than assumed: the inverse is taken as the transpose below, which is
    only the inverse for rotations.  A rig with scaled bones would otherwise produce a
    quietly wrong C.
    """
    if abs(determinant(m) - 1.0) > tol:
        return False
    prod = mat_mul(transpose(m), m)
    return all(abs(prod[i][j] - (1.0 if i == j else 0.0)) < tol
               for i in range(3) for j in range(3))


def inverse_rotation(m):
    return transpose(m)


def angle_between(a, b):
    """Rotation angle in degrees taking *a* to *b*, from the trace of ``aᵀb``.

    Trace-based rather than quaternion-based on purpose: it has no sign double cover
    to cancel, which is a documented trap in this project when comparing orientations.
    """
    r = mat_mul(transpose(a), b)
    t = max(-1.0, min(1.0, (r[0][0] + r[1][1] + r[2][2] - 1.0) / 2.0))
    return math.degrees(math.acos(t))


def mat_to_quat(m):
    """``(w, x, y, z)`` from a 3x3 rotation, via the largest-trace branch.

    Branching on which term is largest keeps the square root away from zero, which the
    naive single-formula version gets wrong for 180-degree rotations -- and several of
    the real corrections here are exactly 180 degrees (RE9's right side is family A
    flipped about X).
    """
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        return ((0.25 * s),
                (m[2][1] - m[1][2]) / s,
                (m[0][2] - m[2][0]) / s,
                (m[1][0] - m[0][1]) / s)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        return ((m[2][1] - m[1][2]) / s, 0.25 * s,
                (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        return ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s,
                0.25 * s, (m[1][2] + m[2][1]) / s)
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
    return ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s,
            (m[1][2] + m[2][1]) / s, 0.25 * s)


def quat_mul(a, b):
    """Hamilton product of two ``(w, x, y, z)`` quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def nearest_signed_permutation(m):
    """``(signed_permutation, deviation_degrees)``, or ``(None, None)``.

    ``None`` means rounding the elements does not land on a valid signed permutation
    at all -- the input is nowhere near an axis relabeling.
    """
    snapped = tuple(tuple(float(round(v)) for v in row) for row in m)
    if abs(determinant(snapped) - 1.0) > 1e-9:
        return None, None
    for i in range(3):
        if sum(1 for v in snapped[i] if v) != 1:
            return None, None
        if sum(1 for r in range(3) if snapped[r][i]) != 1:
            return None, None
    return snapped, angle_between(m, snapped)


class BoneCorrection:
    """C for one bone, where it came from, and how far off the gate it sat.

    origin is ``"derived"`` (from both rigs, passed the gate), ``"table"`` (a
    validated per-game table) or ``"identity"`` (games share a convention family).
    """

    __slots__ = ("bone", "target", "matrix", "origin", "deviation_deg")

    def __init__(self, bone, target, matrix, origin, deviation_deg=None):
        self.bone = bone
        self.target = target
        self.matrix = matrix
        self.origin = origin
        self.deviation_deg = deviation_deg

    @property
    def is_identity(self):
        return all(abs(self.matrix[i][j] - IDENTITY[i][j]) < 1e-6
                   for i in range(3) for j in range(3))

    def apply_to_offset(self, offset):
        """Re-express a local offset from the source bone's frame in the target's."""
        return mat_apply(inverse_rotation(self.matrix), offset)

    def apply_to_rotation(self, quat_wxyz):
        """Re-express a local rotation the same way: ``C⁻¹ ⊗ q``.

        A collider carries an orientation as well as a position (the file's
        ``rotOffset``), and a capsule's axis direction comes from it -- convert only
        the position and a tapered capsule ends up pointing the wrong way.
        """
        return quat_mul(mat_to_quat(inverse_rotation(self.matrix)), tuple(quat_wxyz))

    def __repr__(self):
        dev = "" if self.deviation_deg is None else f" dev={self.deviation_deg:.2f}deg"
        return f"<C {self.bone}->{self.target} {self.origin}{dev}>"


class CorrectionSet:
    """Corrections for a rig pair, plus the bones that could not be trusted.

    corrections : {source_bone: BoneCorrection} -- safe to use
    rejected    : [(bone, target, deviation_deg)] -- the derived C failed the gate and
                  no table entry existed.  **Callers must not fall back to identity
                  for these.**  That silently writes physics data in the wrong
                  convention, and per memory ``reference_mhwmodfixer`` broken chain
                  physics fails at boot only -- no static check will catch it.
    """

    def __init__(self, src_game, dst_game, tolerance_deg=DEFAULT_TOLERANCE_DEG):
        self.src_game = src_game
        self.dst_game = dst_game
        self.tolerance_deg = tolerance_deg
        self.corrections = {}
        self.rejected = []

    def get(self, bone_name):
        return self.corrections.get(bone_name)

    def counts(self):
        n = {"derived": 0, "table": 0, "identity": 0}
        for c in self.corrections.values():
            n[c.origin] = n.get(c.origin, 0) + 1
        return n

    def summary(self):
        n = self.counts()
        parts = [f"{self.src_game}->{self.dst_game}", f"derived {n['derived']}",
                 f"table {n['table']}", f"identity {n['identity']}"]
        if self.rejected:
            parts.append(f"REJECTED {len(self.rejected)}")
        if self.pose_mismatch_suspected:
            parts.append("POSE MISMATCH?")
        return ", ".join(parts)

    @property
    def pose_mismatch_suspected(self):
        """True when over half the bones failed the gate.

        Worth surfacing as one message instead of bone-by-bone: it means the two rigs
        are not in the same physical pose, which is the derivation's precondition --
        the *rigs* are wrong for the job, not a few odd bones.
        """
        total = len(self.corrections) + len(self.rejected)
        return total > 0 and len(self.rejected) > total / 2


def _iter_pairs(cross_map):
    for src_name in sorted(getattr(cross_map, "mapping", cross_map)):
        dst_name = cross_map.get(src_name)
        if dst_name:
            yield src_name, dst_name


def derive_bone_correction(src_arm, dst_arm, cross_map, table=None,
                           tolerance_deg=DEFAULT_TOLERANCE_DEG,
                           src_game=None, dst_game=None):
    """Build a ``CorrectionSet`` for every bone ``cross_map`` can place.

    *src_arm* / *dst_arm* are armature objects **in the same physical pose**; pass
    ``dst_arm=None`` to work from *table* alone when no reference skeleton is
    available for the target game.

    *table* is ``{target_bone_name: 3x3 sequence}``; ``core.pose_ops``'s
    ``_REE_BONE_CORRECTION[game]`` fits directly.  It only covers the bones in that
    game's T-pose zeroing list (limbs, hands, toes) -- spine, neck and hip have no
    table entry and depend on the derivation.
    """
    out = CorrectionSet(src_game or getattr(src_arm, "name", "?"),
                        dst_game or (getattr(dst_arm, "name", None) or "table-only"),
                        tolerance_deg)
    table = table or {}
    src_bones = src_arm.data.bones
    dst_bones = dst_arm.data.bones if dst_arm is not None else None

    for src_name, dst_name in _iter_pairs(cross_map):
        sb = src_bones.get(src_name)
        db = dst_bones.get(dst_name) if dst_bones is not None else None

        if sb is not None and db is not None:
            rs = as_matrix3(sb.matrix_local.to_3x3())
            rd = as_matrix3(db.matrix_local.to_3x3())
            if not (is_rotation(rs) and is_rotation(rd)):
                out.rejected.append((src_name, dst_name, None))
                continue
            c = mat_mul(inverse_rotation(rs), rd)
            snapped, dev = nearest_signed_permutation(c)
            if snapped is not None and dev is not None and dev <= tolerance_deg:
                # keep the snapped integer matrix, not the measured one: it composes
                # without accumulating float noise
                out.corrections[src_name] = BoneCorrection(
                    src_name, dst_name, snapped, "derived", dev)
                continue
            entry = table.get(dst_name)
            if entry is not None:
                out.corrections[src_name] = BoneCorrection(
                    src_name, dst_name, as_matrix3(entry), "table", dev)
            else:
                out.rejected.append((src_name, dst_name, dev))
            continue

        # No target rig, or the bone is missing from it.  Table if we have it;
        # identity only when there is no target rig *and* no table at all, i.e. the
        # caller is knowingly running same-convention.  Never a blind default.
        entry = table.get(dst_name)
        if entry is not None:
            out.corrections[src_name] = BoneCorrection(
                src_name, dst_name, as_matrix3(entry), "table")
        elif dst_arm is None and not table:
            out.corrections[src_name] = BoneCorrection(
                src_name, dst_name, IDENTITY, "identity")
        else:
            out.rejected.append((src_name, dst_name, None))

    return out


#: How far a bone may sit from its ancestor's orientation and still count as "riding"
#: on it.  Rig helpers are rigidly carried by their base bone, so they sit at exactly
#: the same orientation: measured 0.00 degrees for MHWilds' L_Hip_HJ_00,
#: L_Elbow_HJ_00 and R_ThighRX_HJ_01 against their parents.  Hair and cloth, which
#: must *not* inherit, hang at their own angles and fall out on this test.
#: Same criterion and same tolerance as pose_ops._expand_inchain_helpers.
RIDE_TOLERANCE_DEG = 0.5

#: How far the inherited C may leave a *mapped* bone from the target rig's own
#: orientation and still be adopted.  This is measured against the real target bone,
#: so it is a check, not a guess.  Placed in the gap the measurement showed on the
#: MHWS/RE9 pair: the torso -- Spine_0/1/2, Neck_0, Head -- lands 2.0-8.2 degrees out,
#: while the clavicle, which genuinely does *not* share the torso's relabel, lands
#: 94 degrees out.  The torso residual is the two characters' spines curving
#: differently, not a convention difference: their own C snaps to exactly the matrix
#: Hip's does.
INHERIT_TOLERANCE_DEG = 12.0


def expand_corrections(cset, src_parents, src_rots, dst_rots, cross_map,
                       ride_tol_deg=RIDE_TOLERANCE_DEG,
                       inherit_tol_deg=INHERIT_TOLERANCE_DEG):
    """Extend *cset* to bones that have no trustworthy C of their own.

    Two kinds of bone are left behind by a per-bone derivation, and both are wrong to
    leave in the source convention:

    * **rig helpers** (``L_Hip_HJ_00``, ``L_Elbow_HJ_00``, ...) -- not in any preset,
      so nothing maps them, yet they are rigidly carried by a base bone and must turn
      with it.  Leaving them behind is visible immediately: the base bone re-points
      and its helpers stay pointing the old way.  Corroborated by their orientation
      matching the ancestor's to within *ride_tol_deg*, which is what "carried by"
      means geometrically -- this is the criterion ``pose_ops`` already uses.
    * **torso bones** (spine, neck, head) -- mapped, but their own derived C misses the
      signed-permutation gate because the two rigs' spines curve differently.  Their C
      is nonetheless the same relabel their hip uses, so they inherit it, and the
      claim is *checked* against the target rig: adopt only if the result lands within
      *inherit_tol_deg* of that rig's own bone.

    The check is what keeps this from being a blanket "children follow parents" rule.
    The clavicle is mapped, sits 8.6 degrees off its parent, and inheriting the torso
    relabel would put it 94 degrees from RE9's own clavicle -- so it is refused and
    stays reported.

    *src_parents* is ``{bone: parent_or_None}``; *src_rots* / *dst_rots* are
    ``{bone: 3x3}`` in each rig's own naming.  Returns the number of bones added.
    """
    def depth(name):
        n, seen = 0, set()
        while name is not None and name not in seen:
            seen.add(name)
            name = src_parents.get(name)
            n += 1
        return n

    added = 0
    for name in sorted(src_parents, key=depth):
        if cset.get(name) is not None:
            continue
        rot = src_rots.get(name)
        if rot is None:
            continue

        ancestor = src_parents.get(name)
        while ancestor is not None and cset.get(ancestor) is None:
            ancestor = src_parents.get(ancestor)
        if ancestor is None:
            continue
        inherited = cset.get(ancestor)

        dst_name = cross_map.get(name) if cross_map is not None else None
        dst_rot = dst_rots.get(dst_name) if dst_name else None
        if dst_rot is not None:
            # mapped: check the inherited C against the target rig's actual bone
            err = angle_between(mat_mul(as_matrix3(rot), inherited.matrix),
                                as_matrix3(dst_rot))
            if err > inherit_tol_deg:
                continue
            origin, dev = "inherited", err
        else:
            # unmapped: the only available check is that it rides on the ancestor
            anc_rot = src_rots.get(ancestor)
            if anc_rot is None:
                continue
            dev = angle_between(as_matrix3(rot), as_matrix3(anc_rot))
            if dev > ride_tol_deg:
                continue
            origin = "rides"

        cset.corrections[name] = BoneCorrection(
            name, dst_name or name, inherited.matrix, origin, dev)
        cset.rejected = [r for r in cset.rejected if r[0] != name]
        added += 1
    return added


def same_convention_set(cross_map, src_game=None, dst_game=None):
    """Identity corrections for a conversion inside one convention family.

    Family A (RE4R / MHWilds / SF6 / MHRS / DMC5) shares an axis convention exactly,
    so offsets transfer untouched and no rig pair is needed: measured 115 of 143 bones
    within 1 degree between RE4R and MHWilds in the same physical pose.
    """
    out = CorrectionSet(src_game or "familyA", dst_game or "familyA")
    for src_name, dst_name in _iter_pairs(cross_map):
        out.corrections[src_name] = BoneCorrection(
            src_name, dst_name, IDENTITY, "identity")
    return out
