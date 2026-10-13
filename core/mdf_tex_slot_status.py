"""What the texture processor will do to one slot -- one rule, shared by the
dialog's status badges and by the export itself.

The rule exists because the old default was a trap: every slot started at
'SKIP' (or 'DEFAULT' if its binding was already a null), and nothing switched
it to 'COMPOSE' when the user picked PBR inputs. Export only composes slots in
COMPOSE mode, so a material whose inputs were all filled in but whose slots
were left alone exported unchanged, with nothing to say so.

'AUTO' resolves from what is actually set:

    direct image set            -> DIRECT
    a recipe input exists       -> COMPOSE
    a feature channel is set    -> COMPOSE   (mask slots like FxMap, which have
                                              per-channel inputs of their own)
    a placeholder slot          -> PLACEHOLDER (MHWS SkinMap: the bundled DDS,
                                              core/placeholder_tex.py)
    otherwise                   -> what the old default was: DEFAULT if the
                                   binding already points at a vanilla null
                                   (and this slot type has one), else SKIP

The last line is deliberate. With no inputs, AUTO does exactly what an
untouched slot did before, so turning AUTO on changes nothing for a material
nobody configured.

Pure Python, no bpy, so tests/test_slot_status.py can pin it.
"""

import os
from collections import namedtuple

#: Every mode a slot can be in. Only AUTO is new; the other four are the
#: explicit overrides they always were, and keep their stored enum numbers.
MODES = ('AUTO', 'COMPOSE', 'DIRECT', 'DEFAULT', 'SKIP')

#: ``mode``: one of COMPOSE / DIRECT / DEFAULT / SKIP / PLACEHOLDER -- never AUTO.
#: ``sources``: the input types a COMPOSE will read (sorted), then ``'ch:R'``-style
#: entries for the feature channels it reads; else ().
#: ``problem``: a short reason key when the slot cannot do what its mode asks
#: (an explicit COMPOSE with no inputs, a DIRECT whose file is gone), else ''.
SlotStatus = namedtuple('SlotStatus', 'mode sources problem auto')


def recipe_inputs(slot_type, channel_maps):
    """The input types slot_type's channel map reads, or None with no recipe."""
    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        return None
    return {src[0] for src in ch_map.values() if isinstance(src, tuple)}


def _present_inputs(needed, pbr_paths, exists):
    # Same test _compose_channels uses to decide a source is usable.
    return tuple(sorted(pt for pt in needed
                        if pbr_paths.get(pt) and exists(pbr_paths[pt])))


def resolve_slot(slot_type, mode, direct_image, original_path, pbr_paths,
                 channel_maps, null_tex_by_type, is_null, exists=os.path.isfile,
                 feature_inputs=None, placeholder=False):
    """SlotStatus for one slot. ``exists`` is injectable for tests.

    ``feature_inputs``: ``{channel: path}`` for a slot with per-channel feature
    inputs (None for any other slot) -- its set channels count as sources."""
    needed = recipe_inputs(slot_type, channel_maps)
    sources = _present_inputs(needed, pbr_paths, exists) if needed else ()
    sources += tuple(f"ch:{c}" for c in sorted((feature_inputs or {}))
                     if feature_inputs[c] and exists(feature_inputs[c]))

    if mode == 'AUTO':
        if direct_image:
            return SlotStatus('DIRECT', (), '' if exists(direct_image) else 'missing_file', True)
        if sources:
            return SlotStatus('COMPOSE', sources, '', True)
        if placeholder:
            return SlotStatus('PLACEHOLDER', (), '', True)
        if slot_type in null_tex_by_type and is_null(original_path):
            return SlotStatus('DEFAULT', (), '', True)
        return SlotStatus('SKIP', (), '', True)

    if mode == 'COMPOSE':
        if needed is None and feature_inputs is None:
            return SlotStatus('COMPOSE', (), 'no_recipe', False)
        return SlotStatus('COMPOSE', sources, '' if sources else 'no_inputs', False)
    if mode == 'DIRECT':
        ok = bool(direct_image) and exists(direct_image)
        return SlotStatus('DIRECT', (), '' if ok else 'missing_file', False)
    if mode == 'DEFAULT':
        return SlotStatus('DEFAULT', (),
                          '' if slot_type in null_tex_by_type else 'no_null', False)
    return SlotStatus('SKIP', (), '', False)


def migrate_saved_mode(saved_mode, original_path, is_null):
    """Map a mode saved before AUTO existed (state without a version key).

    Only the two values the old refresh filled in *by itself* become AUTO --
    SKIP on a real binding, DEFAULT on a null one -- since those say nothing
    about what the user wanted. Anything else was a deliberate choice and is
    kept. (An explicit SKIP on a real binding looks identical to the default
    one, so it migrates too; with no inputs set, AUTO still resolves to SKIP.)
    """
    if saved_mode == 'SKIP' and not is_null(original_path):
        return 'AUTO'
    if saved_mode == 'DEFAULT' and is_null(original_path):
        return 'AUTO'
    return saved_mode
