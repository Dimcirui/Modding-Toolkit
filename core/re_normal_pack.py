"""Hemi-octahedral normal packing for RE Engine's 3-in-1 normal slots.

RE Engine's NormalRoughnessOcclusionMap / NormalRoughnessCavityMap (and their
MHRS/RE9 siblings sharing the same layout) pack Roughness in R and a second
independent quantity (AO, cavity, ...) in B — which leaves only G and A to
carry the normal. A plain two-channel normal (reconstruct Z from X/Y in R/G,
B free) can't do that, since B is already taken. RE Engine's answer is to
encode the tangent-space X/Y as a *rotated, sign-preserving-squared* pair
first: squaring pulls both components toward 0, which after a 45-degree
rotation redistributes their range so the pair still reconstructs a valid Z
via the usual sqrt(1 - x^2 - y^2) — freeing B for something else.

This is *not* game-specific: RE Mesh Editor's own texture packer applies the
identical transform (NRMRToNRRX/NRRXToNRMR in its texturepacker/image_utils.py)
for any slot that needs the third channel, and applies a plain copy for the
plain two-channel NormalRoughness/NormalRoughnessMap slot that doesn't. Ported
and adapted from that reference (MIT), not re-derived — round-tripping this by
hand from the decode side alone is easy to get subtly wrong (signs, rotation
direction), so this mirrors RE Mesh Editor's own forward (encode) and reverse
(decode) functions rather than inverting one to get the other.

Only concerns the G/A pair; R (roughness) and B (the third quantity) pass
through a plain per-channel copy same as any other slot and are untouched here.
"""

import numpy as np

_COS45 = np.cos(np.deg2rad(45.0))
_SIN45 = np.sin(np.deg2rad(45.0))


def encode_normal_ga(green, alpha):
    """Plain tangent-space normal (G=Y, A=X, both 0..1) -> RE Engine's packed
    G/A pair for a 3-in-1 slot. Inverse of decode_normal_ga.

    ``green``/``alpha``: same-shape float arrays in 0..1 (a normal map's own G
    and A... wait, R and G — see module docstring: X lives in the image's R
    channel, Y in its G channel; the caller is expected to have already routed
    those into these two arguments before the slot-side rotation happens).
    Returns (new_green, new_alpha), both 0..1.
    """
    x = alpha * 2.0 - 1.0
    # No sign correction here, deliberately: this function was already the
    # inverse of *decoding into DirectX*, which is why the fix for the
    # OpenGL/DirectX mismatch lives in decode_normal_ga alone. Negating here too
    # would cancel it out and restore the bug.
    y = green * 2.0 - 1.0

    nr_x = x * _COS45 - y * _SIN45
    nr_y = x * _SIN45 + y * _COS45

    nr_x = np.sign(nr_x) * np.sqrt(np.abs(nr_x))
    nr_y = np.sign(nr_y) * np.sqrt(np.abs(nr_y))

    new_green = np.clip((nr_x + 1.0) * 0.5, 0.0, 1.0)
    new_alpha = np.clip((nr_y + 1.0) * 0.5, 0.0, 1.0)
    return new_green, new_alpha


def decode_normal_ga(green, alpha):
    """RE Engine's packed G/A pair (0..1) -> plain tangent-space normal X/Y in
    -1..1. Inverse of encode_normal_ga. Z is not this function's job — the
    caller reconstructs it with sqrt(clip(1 - x*x - y*y, 0, None)), same as any
    two-channel normal map, since rotation preserves length in the XY-plane.
    """
    nx = green * 2.0 - 1.0
    ny = -(alpha * 2.0 - 1.0)

    nx = np.sign(nx) * nx * nx
    ny = np.sign(ny) * ny * ny

    x = nx * _COS45 - ny * _SIN45
    y = nx * _SIN45 + ny * _COS45
    # RE Mesh Editor's NRRXToNRMR, which this mirrors, exists to feed Blender's
    # *preview*, so it stops here and hands back an OpenGL-convention normal
    # (+Y up). Every texture this addon writes is consumed by the game, which is
    # DirectX (+Y down) -- the two differ in exactly this one sign. Without the
    # flip, encode_normal_ga is not the inverse of this function: round-tripping
    # a vanilla MHWS NRRO came back off by 0.280 per channel, and 0.0007 with it.
    return x, -y
