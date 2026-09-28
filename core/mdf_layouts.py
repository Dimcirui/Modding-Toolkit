"""Outdated mdf2 materials: detect and repair them against a baked snapshot of
the game's vanilla material layouts.

This is RE Asset Library's 「Blender MDF Updater」
(``modules/mdf/re_mdf_updater_utils.batchUpdateMDFCollections``) without its
dependencies: that one reads a sample material out of the game's paks for every
shader, so it needs the asset library installed, extract paths set and a pak
cache built, and it has no read-only mode to check with.  Everything it reads is
static per game version, so ``MHWilds-Offline-Fixer`` baked it once into
``mdflayouts_<GAME>.json.gz`` -- per shader (keyed by the murmur3 of its
lowercased mmtr path): property name, padding, frontPadding and default value,
and texture slot type and default path.  The snapshot is copied here verbatim.

**A snapshot goes stale with the game.**  After a title update an old snapshot
would call current materials outdated and a repair would move them *back*, so
the report always names the snapshot's date, and the repair is a button, never
an auto-fix (``docs/pre_export_check_plan.md`` §5.2.2).

The repair mirrors upstream rule for rule, with three exceptions:

- the vanilla frontPadding is also written to whichever property is first
  *after* the reorder.  Upstream writes it only to the first property *before*
  reordering,
  and only ``propertyList[0].frontPadding`` reaches the file
  (``file_re_mdf.py:547``), so whenever the reorder changes which property
  leads, upstream's output carries a stale front padding and the property data
  offset is wrong -- found by this module's own "diff is empty after update"
  test
- added texture slots are appended in the vanilla order (upstream iterates a
  ``set``, so its order changes between Blender sessions)
- a reorder that meets non-empty mmtrs index data is reported, since upstream
  reorders without updating it
"""

import gzip
import json
import os

from . import re_hash

#: Game code -> snapshot file under assets/.
SNAPSHOTS = {'MHWS': ("mhws", "mdflayouts_MHWILDS.json.gz")}

_cache = {}

# Reason codes, turned into text by the operator layer.
PADDING = 'padding'
PROPS = 'props'
ORDER = 'order'
TEXTURES = 'textures'


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def snapshot(game):
    """The loaded snapshot for *game*, or None if none is bundled."""
    if game in _cache:
        return _cache[game]
    entry = SNAPSHOTS.get(game)
    snap = None
    if entry:
        path = os.path.join(_root(), "assets", *entry)
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                snap = json.load(fh)
        except (OSError, ValueError):
            snap = None
    _cache[game] = snap
    return snap


def snapshot_label(game):
    """``MHWILDS 2026-08-05`` -- what the report prints next to the findings."""
    snap = snapshot(game)
    if not snap:
        return ""
    return f"{snap.get('game', game)} {snap.get('bakedAt', '?')}"


UNKNOWN = 'unknown'
CURRENT = 'current'
STALE = 'stale'


def installed_exe_crc(game_name):
    """The exe CRC RE Asset Library recorded for the user's installed game, or
    None when that library is not set up.  It is the one place that knows which
    game build the user has, so it is how a stale snapshot gets caught."""
    try:
        import bpy
    except ImportError:
        return None
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        if lib.name != f"RE Assets - {game_name}":
            continue
        path = os.path.join(bpy.path.abspath(lib.path), f"ExtractInfo_{game_name}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh).get("exeCRC")
        except (OSError, ValueError):
            return None
    return None


def freshness(game):
    """``CURRENT`` / ``STALE`` / ``UNKNOWN``: does the snapshot match the game
    the user has installed?  Measured 2026-09-28: a snapshot baked on
    2026-08-05 disagreed with the live paks on 4 of 13 preset materials after
    one title update (one shader went from 181 to 166 properties) -- a repair
    from it would have moved those materials back to the old layout."""
    snap = snapshot(game)
    if not snap or snap.get("exeCRC") is None:
        return UNKNOWN
    crc = installed_exe_crc(snap.get("game", ""))
    if crc is None:
        return UNKNOWN
    return CURRENT if crc == snap["exeCRC"] else STALE


def sample_for(game, mmtr_path):
    """The vanilla layout for a shader, or None (unknown shader, or no snapshot)."""
    snap = snapshot(game)
    if not snap or not mmtr_path:
        return None
    key = str(re_hash.murmur3_32(mmtr_path.lower().encode("utf-8")))
    return snap["layouts"].get(key)


def diff(md, sample):
    """Reason codes for how material data *md* departs from *sample*, in a
    stable order; empty when it is current.  Exactly the differences upstream's
    updater acts on, so "nothing reported" and "the updater would change
    nothing" mean the same thing."""
    props = list(md.propertyList_items)
    sprops = sample["properties"]
    out = []

    # Identical to *some* vanilla material using this shader is not outdated:
    # 12 of 549 MHWS shaders have a rarer second layout in vanilla itself.
    mine = [[p.prop_name, p.padding, p.frontPadding] for p in props]
    mine_tex = sorted(b.textureType for b in md.textureBindingList_items)
    for alt in sample.get("alts", ()):
        if mine == alt["props"] and mine_tex == alt["textures"]:
            return []

    pad = {p["n"]: p["p"] for p in sprops}
    if (props and sprops and props[0].frontPadding != sprops[0]["f"]) or any(
            p.prop_name in pad and p.padding != pad[p.prop_name] for p in props):
        out.append(PADDING)
    old_names = [p.prop_name for p in props]
    new_names = [p["n"] for p in sprops]
    if set(old_names) != set(new_names):
        out.append(PROPS)
    elif old_names != new_names:
        out.append(ORDER)
    if {b.textureType for b in md.textureBindingList_items} != {t["t"] for t in sample["textures"]}:
        out.append(TEXTURES)
    return out


def _set_value(prop, name, value):
    """Upstream's data-type guess for a property it adds (it has only the name
    and the float count to go on; re_mdf_updater_utils.py:354-366)."""
    lower = name.lower()
    if len(value) == 4 and ("color" in lower or "_col_" in lower) and "rate" not in lower:
        prop.data_type = "COLOR"
        prop.color_value = value
    elif len(value) == 1 and ("Use" in name or "_or_" in name or name.startswith("is")):
        prop.data_type = "BOOL"
        prop.bool_value = bool(value[0])
    elif len(value) > 1:
        prop.data_type = "VEC4"
        prop.float_vector_value = tuple(value)
    else:
        prop.data_type = "FLOAT"
        prop.float_value = float(value[0]) if value else 0.0


def update(md, sample):
    """Bring *md* to *sample*'s layout in place.  Returns ``(changed, warnings)``.

    Values the user set are kept; only padding is overwritten, missing
    properties and slots take the vanilla defaults, retired ones go.
    """
    changed = False
    warnings = []
    props = md.propertyList_items
    sprops = sample["properties"]

    # Upstream's own step, kept so the result matches it wherever upstream is
    # right; the after-reorder write below covers where it is not.
    if len(props) and sprops and props[0].frontPadding != sprops[0]["f"]:
        props[0].frontPadding = sprops[0]["f"]
        changed = True
    pad = {p["n"]: p["p"] for p in sprops}
    for p in props:
        want = pad.get(p.prop_name)
        if want is not None and p.padding != want:
            p.padding = want
            changed = True

    new_names = [p["n"] for p in sprops]
    by_name = {p["n"]: p for p in sprops}
    have = {p.prop_name for p in props}
    for name in new_names:
        if name in have:
            continue
        src = by_name[name]
        prop = props.add()
        prop.prop_name = name
        prop.padding = src["p"]
        prop.frontPadding = src["f"]
        _set_value(prop, name, list(src["v"]))
        changed = True
    keep = set(new_names)
    for i in reversed(range(len(props))):
        if props[i].prop_name not in keep:
            props.remove(i)
            changed = True

    current = [p.prop_name for p in props]
    if current != new_names:
        for target, name in enumerate(new_names):
            src = [p.prop_name for p in props].index(name)
            if src != target:
                props.move(src, target)
        changed = True
        if any((getattr(e, "indexString", "") or "").strip() for e in md.mmtrsData_items):
            warnings.append("mmtrs")
    # After the reorder, not before: only the leading property's frontPadding is
    # written (see the module docstring).
    if len(props) and sprops and props[0].frontPadding != sprops[0]["f"]:
        props[0].frontPadding = sprops[0]["f"]
        changed = True

    bindings = md.textureBindingList_items
    stypes = [t["t"] for t in sample["textures"]]
    have_t = {b.textureType for b in bindings}
    for t in sample["textures"]:
        if t["t"] not in have_t:
            b = bindings.add()
            b.textureType = t["t"]
            b.path = t["p"]
            changed = True
    keep_t = set(stypes)
    for i in reversed(range(len(bindings))):
        if bindings[i].textureType not in keep_t:
            bindings.remove(i)
            changed = True
    return changed, warnings
