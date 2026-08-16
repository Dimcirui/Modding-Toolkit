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

**Scope is MHWS / RE4R / RE9 / MHRS.**

MHRS is the one game with a single archetype, and that is the game rather than a
gap in what ships (user, 2026-08-16): ``PL_Default`` is the only master material
worth using there, the same way MHWI has only ``pl_mt`` and MHWS's ``Base_Equip``
covers the plain case.  So everything lands on ``standard`` in that direction and
nothing is being flattened that the target could have expressed -- which is why it
is offered rather than withheld.  Coming *out* of MHRS the source is always
``standard`` too, and the target's own map decides where that goes.

The mapping (user's decision, 2026-08-14):

* ``standard`` and ``hair`` exist in all three games and pair one to one.
* ``skin`` -- MHWS and RE9 have it; RE4R's ``standard`` doubles as skin.
* ``emissive`` -- RE4R and RE9 correspond exactly; MHWS has no emissive prefab, so it
  falls back to ``basic``.
* ``weapon`` and ``basic`` are MHWS-only and land on the target's ``standard``.
* ``transparent`` (user's decision, 2026-08-15) exists in all three and pairs one to
  one.  Unlike the others it is *two* shaders per game rather than one, and the
  second one is recognised without being shipped -- see ``_ALSO_CLASSIFIES_AS``.
* Anything unclassified falls back per game -- MHWS ``basic``, RE4R and RE9
  ``standard`` -- **and is reported**, so the user can check those materials by hand.

Free of ``bpy``: the mapping is a table over the shipped prefab files, so it can be
checked offline against the assets that actually ship.
"""

import json
import os

#: Games this is offered for, same set the mesh and chain ports cover.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9", "MHRS")

#: Prefab directory per game, under assets/mdf_presets/.
_PREFAB_DIRS = {"MHWS": "mhws", "RE4": "re4", "RE9": "re9", "MHRS": "mhrs"}

#: Where each source archetype lands, per target game.  A missing entry means the
#: target has no equivalent and the game's fallback is used.
_ARCHETYPE_MAP = {
    "MHWS": {"standard": "standard", "hair": "hair", "skin": "skin",
             "weapon": "standard", "basic": "basic", "transparent": "transparent",
             # MHWS ships no emissive prefab; basic is the closest of what it has.
             "emissive": "basic"},
    "RE4": {"standard": "standard", "hair": "hair", "emissive": "emissive",
            "transparent": "transparent",
            # RE4R has no skin prefab -- its standard doubles as skin.
            "skin": "standard", "weapon": "standard", "basic": "standard"},
    "RE9": {"standard": "standard", "hair": "hair", "skin": "skin",
            "emissive": "emissive", "transparent": "transparent",
            "weapon": "standard", "basic": "standard"},
    # MHRS has one archetype, so every source lands on it. Spelled out rather than
    # left to FALLBACK_ARCHETYPE: the fallback also *reports*, and a hair material
    # arriving at MHRS's standard is not something the user needs to go check by
    # hand -- there is nowhere else it could have gone.
    "MHRS": {"standard": "standard", "hair": "standard", "skin": "standard",
             "emissive": "standard", "transparent": "standard",
             "weapon": "standard", "basic": "standard"},
}

#: Shaders that *mean* an archetype without being the prefab shipped for it.
#:
#: Every other archetype is one shader per game, so the prefab's own
#: ``Master Material Path`` is the whole classification table.  Transparency is not:
#: each game has two half-transparent master materials in general use, and porting
#: has to recognise both while writing only one.  The user picked which one is
#: written (2026-08-15) -- MHWS ``expTransparent``, RE4R ``Glass_Emissive``, RE9
#: ``Glass_Transparent_Ch``, all three shipped under ``transparent.json`` -- and the
#: runner-up is listed here so an incoming material built on it is still classified
#: as ``transparent`` rather than falling back to ``standard``/``basic``.
#:
#: Recognition only, deliberately: shipping the runner-up as a second prefab would
#: put two files under one archetype key and make ``load_prefabs`` ambiguous about
#: which is the destination, which is the one thing this table must not be.
_ALSO_CLASSIFIES_AS = {
    "MHWS": {
        # RE Mesh Editor Presets/MHWILDS/roughTransparent.json
        "materialshader/variation/basealpha_emit_roughtransparent.mmtr": "transparent",
    },
    "RE4": {
        # RE Mesh Editor Presets/RE4/Glass.json
        "_chainsaw/mastermaterial/master/character_reflectivetransparent.mmtr": "transparent",
    },
    "RE9": {
        # RE Mesh Editor Presets/RE9/Glass_Transparent.json
        "materialshader/master/glass_transparent.mmtr": "transparent",
    },
}

#: Used when the source material's shader matches no known archetype.
FALLBACK_ARCHETYPE = {"MHWS": "basic", "RE4": "standard", "RE9": "standard",
                      "MHRS": "standard"}


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

    Matched on the .mmtr path, case-insensitively and slash-normalised, against the
    shipped prefabs first and ``_ALSO_CLASSIFIES_AS`` second.  None is a real answer,
    not a failure: it means "this material is outside the prefab range", which the
    caller must report rather than silently convert.
    """
    if not master_material_path:
        return None
    want = master_material_path.replace("\\", "/").lower()
    for archetype, info in load_prefabs(game_code).items():
        if info["mmtr"] and info["mmtr"].lower() == want:
            return archetype
    return _ALSO_CLASSIFIES_AS.get(game_code, {}).get(want)


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
