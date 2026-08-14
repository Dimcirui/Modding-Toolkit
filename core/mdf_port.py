"""RE Mdf port, planning layer: which target material a source material becomes.

Materials do not survive a game change the way a mesh does.  Each game's shaders are
its own, so a port cannot carry a material across -- it has to *rebuild* it from the
target game's nearest equivalent and move the user's own textures onto it.  The
"nearest equivalent" is already decided: the packed-shader work defined one prefab
material per archetype per game, and those prefabs are what this maps onto.

**Archetype comes from the shader, not from the name.**  Every bundled prefab carries
the ``Master Material Path`` (the .mmtr) of the archetype it represents, so a source
material is classified by matching its own .mmtr against that table.  Exact match
only: a material whose shader is not one of the archetypes is reported as unsupported
rather than guessed at from keywords in its name, because a wrong archetype produces a
material that looks plausible and renders wrong.

**Scope is MHWS / RE4R / RE9.**  MHRS ships a single prefab and no validated pairing,
so it is not offered; the mesh and chain ports cover the same three games.

The mapping (user's decision, 2026-08-14):

* ``standard`` and ``hair`` exist in all three games and pair one to one.
* ``skin`` -- MHWS and RE9 have it; RE4R's ``standard`` doubles as skin.
* ``emissive`` -- RE4R and RE9 correspond exactly; MHWS has no emissive prefab, so it
  falls back to ``basic``.
* ``weapon`` and ``basic`` are MHWS-only and land on the target's ``standard``.
* Anything unclassified falls back per game -- MHWS ``basic``, RE4R and RE9
  ``standard`` -- **and is reported**, so the user can check those materials by hand.

Free of ``bpy``: the mapping is a table over the shipped prefab files, so it can be
checked offline against the assets that actually ship.
"""

import json
import os

#: Games this is offered for, same three the mesh and chain ports cover.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9")

#: Prefab directory per game, under assets/mdf_presets/.
_PREFAB_DIRS = {"MHWS": "mhws", "RE4": "re4", "RE9": "re9"}

#: Where each source archetype lands, per target game.  A missing entry means the
#: target has no equivalent and the game's fallback is used.
_ARCHETYPE_MAP = {
    "MHWS": {"standard": "standard", "hair": "hair", "skin": "skin",
             "weapon": "standard", "basic": "basic",
             # MHWS ships no emissive prefab; basic is the closest of what it has.
             "emissive": "basic"},
    "RE4": {"standard": "standard", "hair": "hair", "emissive": "emissive",
            # RE4R has no skin prefab -- its standard doubles as skin.
            "skin": "standard", "weapon": "standard", "basic": "standard"},
    "RE9": {"standard": "standard", "hair": "hair", "skin": "skin",
            "emissive": "emissive", "weapon": "standard", "basic": "standard"},
}

#: Used when the source material's shader matches no known archetype.
FALLBACK_ARCHETYPE = {"MHWS": "basic", "RE4": "standard", "RE9": "standard"}


def _assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets")


def prefab_dir(game_code):
    sub = _PREFAB_DIRS.get(game_code)
    return None if sub is None else os.path.join(_assets_dir(), "mdf_presets", sub)


def load_prefabs(game_code):
    """``{archetype: {"path": abs path, "mmtr": master material path}}``.

    The archetype key is the prefab's own filename stem, which is what
    ``ShaderPackSpec.preset_filename`` already points at -- so the two systems name
    the same archetypes without a second table to keep in step.
    """
    root = prefab_dir(game_code)
    out = {}
    if not root or not os.path.isdir(root):
        return out
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(root, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        header = data.get("Material Header") or {}
        out[os.path.splitext(fname)[0]] = {
            "path": path,
            "mmtr": (header.get("Master Material Path") or "").replace("\\", "/"),
        }
    return out


def classify(game_code, master_material_path):
    """The source material's archetype, or None when its shader is not one of them.

    Matched on the .mmtr path, case-insensitively and slash-normalised.  None is a
    real answer, not a failure: it means "this material is outside the prefab range",
    which the caller must report rather than silently convert.
    """
    if not master_material_path:
        return None
    want = master_material_path.replace("\\", "/").lower()
    for archetype, info in load_prefabs(game_code).items():
        if info["mmtr"] and info["mmtr"].lower() == want:
            return archetype
    return None


def target_prefab(src_archetype, dst_game):
    """``(archetype, path, exact)`` for the target game.

    *exact* is False when the source archetype had no counterpart and a fallback was
    used -- either because the target game lacks it, or because the source material
    could not be classified at all (``src_archetype`` None).  The caller surfaces
    that; it is the difference between a port and a guess.
    """
    prefabs = load_prefabs(dst_game)
    if not prefabs:
        return None, None, False

    wanted = _ARCHETYPE_MAP.get(dst_game, {}).get(src_archetype) if src_archetype else None
    exact = wanted is not None and wanted == src_archetype
    if wanted is None or wanted not in prefabs:
        wanted = FALLBACK_ARCHETYPE.get(dst_game)
        exact = False
    info = prefabs.get(wanted)
    if info is None:
        return None, None, False
    return wanted, info["path"], exact


def plan_material(game_code, dst_game, master_material_path):
    """``{archetype, target, path, exact, unsupported}`` for one material."""
    src_archetype = classify(game_code, master_material_path)
    target, path, exact = target_prefab(src_archetype, dst_game)
    return {"archetype": src_archetype, "target": target, "path": path,
            "exact": exact, "unsupported": src_archetype is None}
