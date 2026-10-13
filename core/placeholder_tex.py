"""Slots that get a bundled placeholder texture instead of a null -- one
definition for the generator, the processor and the cross-game port.

Only SkinMap, and only by the user's choice (2026-10-13): vanilla binds 96% of
its SkinMap slots to Art/Model/Character/ch00/CommonTextures/SkinMap01_skin_ALB,
but that is a 64x128 skin-tone palette (mean ~0.59/0.42/0.35) and reads far too
dark as a stand-in, so the bundled near-flat light tone (~0.99/0.81/0.79) is
written into the mod instead.

BlendNormalMap is deliberately *not* here any more. Vanilla's blend normals are
plain RGB tangent normals -- (0.5, 0.5, 1) on average, A ~ 0 -- while the old
bundled one was NRRO-packed (R 0.70, A 0.51); read the vanilla way that tilts
every normal ~23 degrees. It now gets NullNormal, (0.5, 0.5, 1, 0), which is
vanilla's own average and needs no male/female choice.

When a placeholder cannot be written (no mod root, textures switched off) the
slot falls back to PLACEHOLDER_FALLBACK -- a texture the game ships, never the
prefab's borrowed MK_MODS/... path.
"""

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLACEHOLDER_SLOT_TYPES = {'SkinMap'}

PLACEHOLDER_FALLBACK = {
    'SkinMap': 'systems/rendering/NullGray.tex',          # user's choice, 2026-10-13
}

#: Slots whose MHWS prefab binding is another mod's asset and must never ship:
#: the placeholder slots above, plus BlendNormalMap, which a null covers.
PREFAB_PATH_FALLBACK = {
    **PLACEHOLDER_FALLBACK,
    'BlendNormalMap': 'systems/rendering/NullNormal.tex',
}


def _prefab_borrowed():
    """{slot: lowercase path} the bundled MHWS skin prefab points these slots at --
    another mod's assets (MK_MODS/Eku/Public/...), read from the prefab itself so
    a re-authored prefab is followed."""
    import json
    path = os.path.join(_ROOT, "assets", "mdf_presets", "mhws", "skin.json")
    try:
        with open(path, encoding="utf-8") as f:
            binds = json.load(f).get("Texture Bindings", [])
    except (OSError, ValueError):
        return {}
    return {b["Texture Type"]: b["Texture Path"].replace("\\", "/").lower()
            for b in binds if b.get("Texture Type") in PREFAB_PATH_FALLBACK}


_BORROWED = None


def is_prefab_borrowed(slot_type, path):
    """Is ``path`` the prefab's borrowed asset for this slot? A material made
    from the prefab still carries it; it exists on nobody else's machine, so it
    counts as "nothing set" rather than as the user's own texture."""
    global _BORROWED
    if _BORROWED is None:
        _BORROWED = _prefab_borrowed()
    p = (path or "").replace("\\", "/").lower()
    return bool(p) and _BORROWED.get(slot_type) == p


def placeholder_dds(slot_type):
    """The bundled DDS for a placeholder slot, or None (other slot / missing)."""
    if slot_type not in PLACEHOLDER_SLOT_TYPES:
        return None
    path = os.path.join(_ROOT, "assets", "mdf_presets", "mhws", f"{slot_type}.dds")
    return path if os.path.isfile(path) else None
