"""What the generator does with each slot of a preset -- decided once, here.

The generators (core/mdf_generator_base.py for the RE games,
games/mhwi/mrl3_generator.py for MHWI) dispatch on this plan, and the
generator dialog's "slot results" section draws it, so what the dialog shows
is the branch the export takes. Only decisions live here: the writing (and the
fallbacks that only a write can discover -- a bake that produced nothing, a
solid that could not be saved) stays in the generators.

No bpy: the inputs are the material's analysed strategies and plain callables.

Kinds, in the order the generators have always tested them:

    TOON         emissive slot under toon shading; gets the albedo's binding
    NULL         a null texture (``detail`` is its path)
    DIRECT       the file plugged into the slot's own socket/slot-named node
    PLACEHOLDER  a bundled DDS (MHWS SkinMap, core/placeholder_tex.py)
    KEEP         left as the preset has it
    PATH         "materials only": the binding path is written, no texture
    SOLID        every input is a constant -> a 256px solid texture
    COMPOSE      composed from the PBR inputs in ``sources``
"""

from collections import namedtuple

SlotPlan = namedtuple("SlotPlan", "kind sources detail")


def _close(a, b):
    return all(abs(x - y) < 1e-4 for x, y in zip(a, b))


def plan_slots(slot_types, channel_maps, *, emissive_slots, use_toon, emi_zero,
               slot_direct, prefer_direct, skip_textures, null_for,
               downgrade, null_rgba=None, placeholder_slots=frozenset(),
               keep_unlisted=lambda st: False):
    """{slot_type: SlotPlan} for every slot in ``slot_types``.

    null_for(st)       -> the slot's null path, or "" / None
    downgrade(st)      -> RGBA when every input of the slot is a constant, else None
    null_rgba(st)      -> the measured pixel of the slot's null, or None when
                          unknown; a downgrade equal to it becomes the null
                          instead of a solid texture (core/null_pixels.py)
    keep_unlisted(st)  -> True to leave a recipe-less slot as the preset has it
    """
    plan = {}
    for st in slot_types:
        plan[st] = _plan_one(
            st, channel_maps, emissive_slots, use_toon, emi_zero, slot_direct,
            prefer_direct, skip_textures, null_for, downgrade, null_rgba,
            placeholder_slots, keep_unlisted)
    return plan


def _null_or_keep(null):
    return SlotPlan('NULL', (), null) if null else SlotPlan('KEEP', (), '')


def _plan_one(st, channel_maps, emissive_slots, use_toon, emi_zero, slot_direct,
              prefer_direct, skip_textures, null_for, downgrade, null_rgba,
              placeholder_slots, keep_unlisted):
    if st in emissive_slots:
        if use_toon:
            return SlotPlan('TOON', (), '')
        if emi_zero:
            return _null_or_keep(null_for(st))

    direct_src, direct_auth = slot_direct.get(st, (None, None))
    if direct_src is not None and (st not in channel_maps or prefer_direct):
        if skip_textures:
            return SlotPlan('PATH', (), direct_src)
        return SlotPlan('DIRECT', (), direct_src)

    if st in placeholder_slots:
        return SlotPlan('PATH' if skip_textures else 'PLACEHOLDER', (), '')

    if st not in channel_maps:
        if keep_unlisted(st):
            return SlotPlan('KEEP', (), '')
        return _null_or_keep(null_for(st))

    if skip_textures:
        return SlotPlan('PATH', (), '')

    sources = tuple(sorted({src[0] for src in channel_maps[st].values()
                            if isinstance(src, tuple)}))
    rgba = downgrade(st)
    if rgba is not None:
        # The null only when it holds this very pixel. (Until 2026-10-13 the
        # test was "equals the all-defaults material", which is not the same
        # thing: NRRO's defaults have roughness 1 where its null has 0.5, and
        # ACOT's have cavity 1 / translucency 0 where NullATOS has 0 / 1.)
        if null_rgba is not None:
            null = null_for(st)
            px = null_rgba(st) if null else None
            if px is not None and _close(rgba, px):
                return SlotPlan('NULL', sources, null)
        return SlotPlan('SOLID', sources, tuple(rgba))
    return SlotPlan('COMPOSE', sources, '')
