"""Reference-model import: which model each game has, and what "merge" means on it.

A reference model is a vanilla body straight from the game -- the thing you rig
against, measure against, and port onto.  Every game ships one somewhere different,
so the table below is the single place that knows where:

===== ====================================== ===========================================
game  source                                 how it is read
===== ====================================== ===========================================
MHWI  Modder Batch Tool's own bundled MOD3   MBT's operator (needs MHW Model Editor too)
MHWS  assets/reference_skeletons/mhws/       Blender's FBX importer
MHRS  assets/mhrs/shadow/                    RE Mesh Editor's mesh importer
RE4   assets/reference_skeletons/re4/        Blender's FBX importer
RE9   assets/reference_skeletons/re9/        Blender's FBX importer
===== ====================================== ===========================================

MHWI is the odd one: its model is not in this repo, so the import is delegated to MBT.

MHWI and MHRS get no post-import options: their bodies have no facial rig and no
auxiliary bones, and both ship in T-pose, so every switch below would be a no-op.

**The two merges.**  Both answer "collapse these bones into the nearest bone that
survives, taking their weights with them", which is the algorithm MBT uses on MHWilds
facial bones and which ``games/mhws/operators.py`` already carries.  They differ only
in which bones are doomed:

* **facial** -- everything under the game's facial root.  MHWilds is listed explicitly
  instead (``_MHWS_FACIAL_MERGE_BONES``, ported from MBT) because its facial rig is
  not one clean subtree.
* **auxiliary** -- every bone the game's *native* skeleton does not have.  The base
  sets are read from the real skeleton files shipped in ``assets/`` and baked into
  ``assets/native_skeletons/base_bones.json`` (MHWS 224 bones, RE4 137, RE9 85), so
  the rule needs no hand-maintained list of helpers.

Auxiliary merging deliberately **excludes the facial subtree**, even though those
bones are absent from the base skeletons too (measured: MHWilds' bonesystem skeleton
has no ``HeadAll_SCL``, no ``fcParam_*``, no ``*_LOD0*``).  Without that exclusion,
ticking only "merge auxiliary" would silently take the whole face with it, and the two
checkboxes would not be independent.

MHWS needs one extra source.  Its native ``bonesystem`` skeleton *contains* the 137
``_HJ_`` helpers (measured: 224 bones, ``Hip_HJ_00`` and friends among them), so "not
in the native skeleton" finds only 5 bones on the reference body and the option would
be a no-op.  What "auxiliary" means for MHWilds is precisely what its bone preset
already registers under ``aux``, so that list is added for MHWS -- and only for MHWS,
because elsewhere ``aux`` holds genuine native joints (RE9's ``L_Leg_Foot`` and
``L_Hand_Palm`` are real bones; merging them would break the rig).

MHRS and MHWI have no native skeleton file here either, which is consistent with them
having no auxiliary bones to merge in the first place.

This module holds no ``bpy`` so the merge planning is unit-testable offline.
"""

import json
import os

#: ``(identifier, label_key, kind, payload)`` per game, in dropdown order.
#:
#: kind ``fbx``    -- payload is ``(reference_skeletons subdir, filename)``
#: kind ``remesh`` -- payload is a repo-relative path, imported through RE Mesh Editor
#: kind ``mbt``    -- payload is a Modder Batch Tool operator id
MODELS = {
    "MHWI": [
        ("female", "core.ref_model.female", "mbt", "mhw.import_female_mesh"),
        ("male", "core.ref_model.male", "mbt", "mhw.import_male_mesh"),
    ],
    "MHWS": [
        ("female", "core.ref_model.female", "fbx", ("mhws", "MHWilds_Female.fbx")),
    ],
    "MHRS": [
        ("female", "core.ref_model.female", "remesh",
         "assets/mhrs/shadow/f_shadow.mesh.2109148288"),
        ("male", "core.ref_model.male", "remesh",
         "assets/mhrs/shadow/m_shadow.mesh.2109148288"),
    ],
    "RE4": [
        ("leon", None, "fbx", ("re4", "leon.fbx")),
        ("ada", None, "fbx", ("re4", "ada.fbx")),
        ("ashley", None, "fbx", ("re4", "ashley.fbx")),
    ],
    "RE9": [
        ("leon", None, "fbx", ("re9", "leon.fbx")),
        ("grace", None, "fbx", ("re9", "grace.fbx")),
    ],
}

#: Root of the facial rig per game.  Everything **below** it merges into it.
#: MHWS is absent on purpose: its list is explicit, see the module docstring.
FACIAL_ROOTS = {
    "RE4": "FacialDef_Face",
    "RE9": "FacialJnt_Face",
}

#: Games whose reference model needs no post-import options at all, so the dialog
#: shows none.  MHWI's and MHRS's bodies carry no facial rig and no auxiliary bones,
#: and both are authored in T-pose already -- all three switches would be no-ops.
OPTIONLESS_GAMES = frozenset({"MHWI", "MHRS"})


def _assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets")


def load_base_bones(game_code):
    """The game's native bone names, or None when no native skeleton is shipped.

    Built by reading the real skeleton files (``.fbxskel`` / ``.skeleton`` /
    ``.refskel``, all readable through RE Mesh Editor's fbxskel importer) and pooling
    every bone they declare -- see the JSON's own ``sources`` entry for which files
    and how many bones each contributed.
    """
    path = os.path.join(_assets_dir(), "native_skeletons", "base_bones.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    entry = data.get(game_code)
    if not entry:
        return None
    return set(entry.get("bones", ()))


def descendants(parents, root):
    """Every bone under *root* in a ``{bone: parent_or_None}`` map, root excluded."""
    children = {}
    for name, parent in parents.items():
        if parent is not None:
            children.setdefault(parent, []).append(name)
    out, stack = set(), list(children.get(root, ()))
    while stack:
        name = stack.pop()
        if name in out:
            continue
        out.add(name)
        stack.extend(children.get(name, ()))
    return out


def plan_merges(parents, doomed):
    """``[(keep, delete), ...]`` -- each doomed bone merges into its nearest surviving
    ancestor.

    Walking up rather than deleting outright is what keeps the weights: a doomed bone
    hands its vertex groups to the bone that stays, which for a facial or helper bone
    is the joint that actually moves that flesh.  A doomed bone whose ancestors are
    all doomed too resolves to the first survivor above them, and one with no
    surviving ancestor at all is left alone -- deleting it would drop weights on the
    floor.
    """
    pairs = []
    for name in sorted(doomed):
        if name not in parents:
            continue
        keep = parents.get(name)
        while keep is not None and keep in doomed:
            keep = parents.get(keep)
        if keep is None:
            continue
        pairs.append((keep, name))
    return pairs


def facial_doomed(game_code, parents, mhws_list=()):
    """Bones the facial merge should collapse, for *game_code*."""
    if game_code == "MHWS":
        return {n for n in mhws_list if n in parents}
    root = FACIAL_ROOTS.get(game_code)
    if not root or root not in parents:
        return set()
    return descendants(parents, root)


def preset_aux_bones(game_code):
    """The bone preset's ``aux`` names for *game_code*, or an empty set.

    Only consulted for MHWS -- see the module docstring for why the same list would
    be actively wrong for the other games.
    """
    if game_code != "MHWS":
        return set()
    path = os.path.join(_assets_dir(), "presets", "bone", "mhws.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f).get("mappings", {})
    except Exception:
        return set()
    return {n for entry in data.values() for n in entry.get("aux", ())}


def aux_doomed(game_code, parents, mhws_list=()):
    """Bones the auxiliary merge should collapse: everything the native skeleton does
    not have (plus MHWilds' preset helpers), minus the facial rig, which the other
    option owns."""
    base = load_base_bones(game_code)
    if base is None:
        return None                      # no native skeleton shipped for this game
    facial = facial_doomed(game_code, parents, mhws_list)
    facial_root = FACIAL_ROOTS.get(game_code)
    keep_out = set(facial) | ({facial_root} if facial_root else set())
    if game_code == "MHWS":
        keep_out |= {n for n in mhws_list}
    helpers = preset_aux_bones(game_code)
    return {n for n in parents
            if (n not in base or n in helpers) and n not in keep_out}
