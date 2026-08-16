"""RE Mdf port, param layer: which Property List entries survive a game change.

The port rebuilds the material from the target game's prefab, so the new Property
List starts at that prefab's defaults.  Carrying the user's own values across is
worth doing, but only where the two entries are the same knob -- and "same knob"
is decided two different ways here, because the games disagree at two levels:

1. **Same name, same type.**  RE4R and RE9 share a shader vocabulary, so most of
   their overlap falls out of a plain intersection: ``BaseColor``, ``Roughness``,
   ``Metallic``.  No table needed, and none is kept -- a table would just go stale
   against the prefabs.
2. **Same concept, different name.**  MHWS names the same PBR basics
   ``ColorParam`` / ``RoughnessParam`` / ``MetalParam`` / ``TranslucentParam`` /
   ``OcclusionParam``, so the intersection above finds almost nothing between MHWS
   and the other two.  That gap is what ``CANON`` closes, one row per concept
   rather than one row per game pair: three games give six directions, and a
   concept table stays symmetric by construction where six hand-written pair lists
   would not.

**Only HIGH-confidence rows are in ``CANON``.**  Three near-misses were considered
and rejected (user's decision, 2026-08-15), because each maps by name while
differing in meaning, and a wrong param value produces a material that renders
subtly wrong with nothing to trace it back to:

* ``SSSParam`` -> ``SSSChannel``/``SSS_BlendRate`` -- "Channel" reads as a discrete
  selector, not an intensity.
* ``AO_to_Cavity`` -> ``Cavity`` -- MHWS's is *how much AO bleeds into cavity*,
  RE's is cavity strength itself.
* ``Fuzz_Blend`` -> ``Sheen`` -- same family, unverified scale.

``BASIC_EXCLUDE`` is the other half of the same judgement, applied to the *automatic*
name matches: entries that match perfectly but are not the material's authored look
-- shader-internal constants and runtime gameplay state.  They stay out of the basic
mode and come back under 'all'.

Free of ``bpy``: it is a table over the shipped prefabs, checkable offline
(``tests/test_mdf_port_params.py``) and re-derivable
(``scripts/mdf_port_param_xref.py``).
"""

import json

from . import mdf_port

#: One row per concept: ``(label, {game: [candidate names, best first]})``.
#: A game gets a *list* because the same concept is spelled differently per
#: archetype (RE4's ``SSSChannel`` vs ``SSS_Channel``); the first candidate that
#: the actual prefab carries wins, so a missing name is a real "this shader has no
#: such knob" rather than a table bug.
#:
#: MHRS is mostly empty and that is the shader, not an unfinished row.  Its one
#: archetype, ``PL_Default``, drives base colour and roughness from maps
#: (``BaseDielectricMap``, ``NRMR_NRRTMap``) rather than from scalars, so there is
#: no Base Color or Roughness param to pair with -- four concepts are all it
#: exposes.  Filling the blanks with near-misses (``Blend_roughness`` for
#: Roughness, ``S_col_R`` for Base Color) is exactly the kind of matching this
#: module's docstring rejects: same family, different meaning, renders subtly
#: wrong with nothing to trace it to.
CANON = [
    ("Base Color",            {"MHWS": ["ColorParam"],           "RE4": ["BaseColor"],             "RE9": ["BaseColor"], "MHRS": []}),
    ("Roughness",             {"MHWS": ["RoughnessParam"],       "RE4": ["Roughness"],             "RE9": ["Roughness"], "MHRS": []}),
    ("Metallic",              {"MHWS": ["MetalParam"],           "RE4": ["Metallic"],              "RE9": ["Metallic"], "MHRS": ["Metallic_Param"]}),
    ("Translucency",          {"MHWS": ["TranslucentParam"],     "RE4": ["Translucency"],          "RE9": ["Translucency"], "MHRS": ["Translucency_Param", "NoMap_Translucency_Param"]}),
    ("Occlusion Intensity",   {"MHWS": ["OcclusionParam"],       "RE4": ["OcclusionIntensity"],    "RE9": ["Occlusion_Intensity"], "MHRS": []}),
    ("Alpha Test Ref",        {"MHWS": ["AlphaTest_Ref"],        "RE4": ["AlphaTestRef"],          "RE9": ["AlphaTestRef"], "MHRS": []}),
    ("Emissive Color",        {"MHWS": ["Emissive_Color"],       "RE4": ["EmissiveColor"],         "RE9": ["EmissiveColor"], "MHRS": ["Emissive_color"]}),
    ("Emissive Intensity",    {"MHWS": ["Emissive_Intensity"],   "RE4": ["EmissiveIntensity"],     "RE9": ["EmissiveIntensity"], "MHRS": ["Emissive_intensity"]}),
    ("SSS Profile",           {"MHWS": ["SSSProfile"],           "RE4": [],                        "RE9": ["SSS_Profile"], "MHRS": []}),
    ("Primary Specular Color", {"MHWS": ["PrimalySpecularColor"], "RE4": ["PrimalySpecularColor"], "RE9": ["Primaly_SpecularColor"], "MHRS": []}),
    ("Specular Shift Offset", {"MHWS": ["Specular_ShiftOffset"], "RE4": ["SpecularShiftOffset"],   "RE9": ["SpecularShiftOffset"], "MHRS": []}),
    ("Wet Roughness",         {"MHWS": ["Wet_Roughness"],        "RE4": [],                        "RE9": ["Wet_Roughness"], "MHRS": []}),
    # Three spellings of one unambiguous switch -- two of them misspelling it in
    # different directions ("Filp", "Reverse"). Nothing in these shaders is close
    # enough to confuse it with, which is what makes it HIGH-confidence despite no
    # two names matching. Without the row it migrates nowhere, since RE4/RE9 carry
    # it only on hair, the one archetype whose MHWS counterpart spells it
    # differently.
    #
    # MHRS is left out even though it has the param, because it stores it as BOOL
    # where the other three store FLOAT, and migration copies a value into a named
    # field without converting between types -- pairing them would write a float
    # into a bool. Worth revisiting only if migration grows type coercion; the
    # concept is right, the representation is not.
    ("Backface Normal Flip",  {"MHWS": ["BackFaceFlipNormal"],   "RE4": ["BackfaceNormalReverse"], "RE9": ["BackfaceNormalReverse"], "MHRS": []}),
]

#: Kept out of 'basic', not out of 'all'.  Each entry is a name or a name prefix,
#: with why it is not part of the authored look.
BASIC_EXCLUDE_NAMES = {
    # A shader-internal lighting constant, not a per-material appearance knob --
    # it matches by name across all three games and is the single most tempting
    # wrong migration in the whole table.
    "LightDirection",
    # Driven by the game at runtime (dissolve/fade effects); the source's value is
    # whatever state it was authored in, not a setting to carry.
    "DissolveRate",
}

#: Same reasoning, applied to whole families: per-game damage/wear systems that the
#: game drives, whose sensible value is the target prefab's own default.
BASIC_EXCLUDE_PREFIXES = (
    "Blood_", "Burnt_", "Injury_", "Stain", "Wrinkle", "LightDamage_", "HeavyDamage_",
)

MODES = ("BASIC", "ALL")


def _is_excluded(name):
    return name in BASIC_EXCLUDE_NAMES or name.startswith(BASIC_EXCLUDE_PREFIXES)


_prefab_props_cache = {}


def prefab_props(game_code, archetype):
    """``{property name: data type}`` for a game's prefab, read from the shipped JSON."""
    key = (game_code, archetype)
    if key in _prefab_props_cache:
        return _prefab_props_cache[key]
    info = mdf_port.load_prefabs(game_code).get(archetype)
    out = {}
    if info:
        try:
            with open(info["path"], "r", encoding="utf-8") as f:
                data = json.load(f)
            out = {p["Property Name"]: p["Data Type"]
                   for p in data.get("Property List") or []}
        except Exception:
            out = {}
    _prefab_props_cache[key] = out
    return out


def canon_pairs(src_game, src_props, dst_game, dst_props):
    """``[(label, src_name, dst_name)]`` for the cross-naming concept table.

    Both sides are ``{name: data type}`` dicts, taken from the *live* materials
    rather than from the prefabs: a source material whose shader matched no
    archetype (``plan_material``'s "unsupported" case) has no prefab to look up,
    but it still has a Property List, and its ``ColorParam`` is still the same
    knob.

    A row contributes only when both sides carry one of its candidate names **and**
    agree on Data Type -- the same bar the runtime copy enforces, applied here so a
    row cannot silently claim a pair that will not take.
    """
    sp, dp = src_props, dst_props
    pairs = []
    for label, names in CANON:
        s = next((n for n in names.get(src_game, []) if n in sp), None)
        d = next((n for n in names.get(dst_game, []) if n in dp), None)
        if s and d and s != d and sp[s] == dp[d]:
            pairs.append((label, s, d))
    return pairs


def name_matches(src_props, dst_props):
    """``[(name, name)]`` for entries both sides already share verbatim."""
    return [(n, n) for n in sorted(src_props)
            if n in dst_props and src_props[n] == dst_props[n]]


def migration_pairs(src_game, src_props, dst_game, dst_props, mode):
    """``[(src_name, dst_name)]`` to attempt, for 'BASIC' or 'ALL'.

    'BASIC' is the material's authored look: the concept table plus the verbatim
    matches minus ``BASIC_EXCLUDE_*``.  'ALL' is everything that lines up at all.
    Both still go through ``migrate_property_value``, which re-checks the type on
    the live property rather than trusting these dicts.
    """
    pairs = [(s, d) for _, s, d in canon_pairs(src_game, src_props, dst_game, dst_props)]
    seen = {s for s, _ in pairs}
    for s, d in name_matches(src_props, dst_props):
        if s in seen:
            continue
        if mode == "BASIC" and _is_excluded(s):
            continue
        pairs.append((s, d))
    return pairs
