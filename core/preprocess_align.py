"""core/preprocess_align.py — the game-independent measuring done by "one-click import & align".

``mhws.preprocess_model`` carries its own copies of ``_detect_source_preset``,
``_calc_arm_scale`` and ``_calc_y_offset``; they are wired to Wilds' bone names and
left alone.  These are the same measurements with the reference-side bone names taken
from the *target preset* instead, so a second game can use them.

Both scale and offset compare **world-space arm bones** (upper arm, forearm, hand, both
sides), which only means anything when the two rigs stand on the same ground plane.
Wilds' reference does.  A game whose reference has its origin elsewhere has to be moved
onto the ground first -- see ``mhwi.preprocess_model``.
"""

from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from .ui_config import OPTIONAL_BONES

#: The only source rigs the flow is calibrated for.  Both are T-pose-ish humanoids; MMD
#: needs an A -> T conversion first, VRChat does not.
SOURCE_PRESETS = ("MMD.json", "VRChat.json")

#: Below this share of the standard bones matched, a rig is not "an MMD or VRChat model".
MIN_COVERAGE = 0.30

ARM_SLOTS = ("upperarm_L", "upperarm_R", "forearm_L", "forearm_R", "hand_L", "hand_R")


def detect_source_preset(arm_obj):
    """MMD.json / VRChat.json, whichever covers more of *arm_obj*; None if neither is
    plausible."""
    best_preset, best_ratio = None, 0.0
    for filename in SOURCE_PRESETS:
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x=True):
            continue
        total = matched = 0
        for std_key in STANDARD_BONE_NAMES:
            if std_key in OPTIONAL_BONES:
                continue
            total += 1
            main, _ = mapper.get_matches_for_standard(arm_obj, std_key)
            if main:
                matched += 1
        if total and matched / total > best_ratio:
            best_ratio, best_preset = matched / total, filename
    return best_preset if best_ratio >= MIN_COVERAGE else None


def arm_bone_names(arm_obj, preset, is_import_x):
    """The actual names of *arm_obj*'s arm bones under *preset*, in ``ARM_SLOTS`` order,
    leaving out the slots it has no match for."""
    mapper = BoneMapManager()
    if not mapper.load_preset(preset, is_import_x=is_import_x):
        return []
    names = []
    for slot in ARM_SLOTS:
        main, _ = mapper.get_matches_for_standard(arm_obj, slot)
        if main and arm_obj.pose.bones.get(main):
            names.append(main)
    return names


def arm_mean(arm_obj, names, axis):
    """Mean world ``axis`` ('x'/'y'/'z') of the pose-bone heads in *names*; None if empty."""
    if not names:
        return None
    mw = arm_obj.matrix_world
    values = [getattr(mw @ arm_obj.pose.bones[n].head, axis) for n in names]
    return sum(values) / len(values)


def arm_scale(source_obj, ref_obj, source_preset, target_preset):
    """Factor that brings the source's arm height to the reference's (``1.0`` when either
    side has no arm bones to measure)."""
    ref_z = arm_mean(ref_obj, arm_bone_names(ref_obj, target_preset, False), "z")
    src_z = arm_mean(source_obj, arm_bone_names(source_obj, source_preset, True), "z")
    if not ref_z or not src_z:
        return 1.0
    return ref_z / src_z


def arm_offset_y(source_obj, ref_obj, source_preset, target_preset):
    """Mean reference arm Y minus mean source arm Y (``0.0`` when unmeasurable)."""
    ref_y = arm_mean(ref_obj, arm_bone_names(ref_obj, target_preset, False), "y")
    src_y = arm_mean(source_obj, arm_bone_names(source_obj, source_preset, True), "y")
    if ref_y is None or src_y is None:
        return 0.0
    return ref_y - src_y
