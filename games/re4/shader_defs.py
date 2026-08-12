"""RE4 (MDF2) packed shader specs — three material archetypes.

Rebuilt from real RE Mesh Editor presets in RE-Mesh-Editor/Presets/RE4/
(pbr_body.json, pbr_cloth.json, pbr_hair.json, Eye_EMI.json — provided
directly by the user), replacing an earlier single "Standard" spec that had
*guessed* NormalRoughnessCavityMap plus a dedicated OcclusionMap slot onto
the body/cloth archetype. Neither actually belongs there — that guess was
wrong, exactly the mistake games/mhws/shader_defs.py's own docstring warns
against ("adding bindings a preset's real compiled shader doesn't carry").
It turned out those two slots *do* belong to a real RE4 archetype, just a
different one (Emissive, below).

Standard (pbr_body.json / pbr_cloth.json)
------------------------------------------
Share the *same* Master Material Path (Character_Detail_Expensive_8weight.mmtr)
and nearly the same Texture Bindings list — unlike MHWS's cloth vs weapon
(different .mmtr each, so kept as two specs), these are the same compiled
shader, so one merged spec is correct here. Both use:

  * BaseDielectricMap — RGB colour, A inverted metallic. Same isDielectric
    convention as MHWS.
  * NormalRoughnessMap — R/G plain tangent-space normal, B unused, A
    roughness. Unlike MHWS's NormalRoughnessOcclusionMap (or RE4's own
    NormalRoughnessCavityMap, used by Emissive below), B carries no third
    quantity in this slot — per BASE_SLOT_CHANNEL_MAPS and
    games/mhws/shader_defs.py's own docstring ("a plain copy to the ones
    that don't [pack a third quantity into B]: NormalRoughness/
    NormalRoughnessMap"), this decodes the *plain* way — reconstruct Z from
    R/G, no hemi-octahedral transform.
  * AlphaTranslucentOcclusionCavityMap — R real opacity, B AO, A cavity, G
    translucency (per BASE_SLOT_CHANNEL_MAPS; G is export-only, no
    Principled input matches it). Same layout as MHWS's
    AlphaTranslucentOcclusionSSSMap under a different RE4 name, plus the two
    extra channels its name promises.

No EmissiveMap in either preset's Texture Bindings — omitted here, following
MHWS's rule of not adding bindings a real compiled shader doesn't carry.
Everything else in their Texture Bindings (DetailMap, MaskMap,
ImperfectDetail_Map, WrinkleNormalMap, the Rec_*/Blood*/Injury_*/Stain_*
scar-and-weather VFX slots, ...) has no PBR composition recipe — carried as
display=False sockets so an existing image on any of them survives the
round trip to the exporter, same treatment MHWS gives its own detail/VFX
slots.

Hair (pbr_hair.json)
--------------------
Structurally different enough to need its own spec, the same way MHWS
splits Hair out: BaseShiftMap instead of BaseDielectricMap (RGB colour, no
metallic-alpha convention — hair's Property List has no Metallic property
at all, only anisotropic specular/shift parameters this shader pack does
not model), plus SecondaryAlbedoMap and RimLight_FakeNormalMap with no
recipe. It shares NormalRoughnessMap and AlphaTranslucentOcclusionCavityMap
with Standard verbatim.

Emissive (Eye_EMI.json)
------------------------
Env_Default_Emissive.mmtr is a genuinely general-purpose emissive master
material (confirmed by the user — not an eye-only hack; Eye_EMI.json just
happens to be an eye repurposing it), so this is its own third archetype
rather than folded into Standard. Its Texture Bindings are exactly what this
module's first draft wrongly guessed for Standard:

  * BaseDielectricMap — same as Standard.
  * NormalRoughnessCavityMap — R roughness, G/A hemi-octahedral normal, B
    cavity (confirmed by the user; an earlier version of this module wrongly
    treated B as an unused constant). Unlike Standard's NormalRoughnessMap,
    this slot *does* pack third/fourth quantities into its G/A/B channels
    (shared with RE9 -- see that module's comment), so its normal decodes
    the hemi-octahedral way, matching games/mhws/shader_defs.py's NRRO decode
    almost exactly, while B is a plain multiplicative cavity value read via a
    second, independent separate() alongside the normal/roughness one.
  * AlphaTranslucentOcclusionSSSMap — R real opacity, B AO, G translucency
    (export-only). Identical recipe to Standard's
    AlphaTranslucentOcclusionCavityMap in BASE_SLOT_CHANNEL_MAPS minus the
    cavity channel (this slot has none), just a different RE4 slot name.
  * OcclusionMap — RE4's own dedicated AO slot (R=G=B=ao, plain greyscale;
    see RE4_SLOT_CHANNEL_MAPS's override). A second genuine AO source
    alongside AlphaTranslucentOcclusionSSSMap.B, multiplied together the
    same way MHWS multiplies NRRO.B and ATOS.B.
  * EmissiveMap — the actual point of this master material.

Roughness=10.0 in Eye_EMI.json's own Property List is not an out-of-range
error to work around: it is the deliberate "push the slider past 1.0 so the
result clamps to fully rough" trick for a toon/cel-shaded (三渲二) look with
no specular highlight, and Roughness already clamps in this shader pack's
combiner -- nothing to special-case.

FakeSphereMap/RainStreakMaskMap/RainDropsMaskMap have no PBR recipe and are
carried through the same way Standard/Hair carry their own no-recipe slots.

Out of scope
------------
Glass.json (Character_ReflectiveTransparent.mmtr) and TextureBlendEmi.json
(Character_Enemy_Default_TextureBlend_Double.mmtr) are deferred, not
dropped -- confirmed with the user. Glass's PBR-looking inputs
(Metallic/Roughness/Occlusion/Cavity) are compiled-in constants, not
textures, in that preset -- nothing for a slot socket to read.
TextureBlendEmi is explicitly "a pbr_body/pbr_cloth that can also be
emissive" *plus* a genuine two-layer texture blend on top (TexBlend_*/
TexBlend2_* duplicate the whole BaseDielectricMap/NormalRoughnessMap/MaskMap
trio with their own blend weights) and monster/creature VFX (Worm/Foam/
Mosquito/BeatAnim/Displacement parameters) -- representing the blend itself
would need real multi-layer compositing logic this shader pack's
single-value-per-quantity combiner does not have, not just more sockets.
"""

import math

from ...core.shader_pack import (
    ShaderPackSpec, SlotSocket, PBRSocket, ALPHA_SUFFIX,
)

_K = "re4.shader_defs."

# ── Core slots: plain-normal family (Standard, Hair) ────────────────────────

_NRM = SlotSocket("NormalRoughnessMap", "core.shader_pack.nrm",
                  default_color=(0.5, 0.5, 1.0, 1.0), alpha=True, default_alpha=1.0,
                  supplies=('normal', 'roughness'))

# R alpha (1-neutral), G translucency (0-neutral), B ao (1-neutral), A cavity
# (1-neutral) -- all four channels genuinely carry data (confirmed by the
# user; an earlier version of this file assumed G/A were unused constants).
# default_color/default_alpha mix 1s and a 0 because each channel's neutral
# differs -- not a typo.
_ATOCM = SlotSocket("AlphaTranslucentOcclusionCavityMap", _K + "atocm",
                    default_color=(1.0, 0.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                    supplies=('alpha', 'ao', 'translucency', 'cavity'))

_ALBD = SlotSocket("BaseDielectricMap", "core.shader_pack.albd",
                   default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('color', 'metallic'), non_color=False)

# Hair's base slot: no inverted-metallic alpha convention (hair.json's real
# Property List has no Metallic property at all).
_BASESHIFT = SlotSocket("BaseShiftMap", "core.shader_pack.baseshift",
                        default_color=(1.0, 1.0, 1.0, 1.0), non_color=False,
                        supplies=('color',))

# ── Core slots: hemi-octahedral-normal family (Emissive) ───────────────────

# R roughness, G/A hemi-octahedral normal, B genuinely carries cavity data
# (confirmed by the user; an earlier version of this file assumed B was
# forced to a constant). G=0.5/A=0.5 decodes to a flat normal; B=1.0 is
# cavity's own multiplicative neutral -- same value, different reason.
_NRCM = SlotSocket("NormalRoughnessCavityMap", _K + "nrcm",
                   default_color=(1.0, 0.5, 1.0, 1.0), alpha=True, default_alpha=0.5,
                   supplies=('roughness', 'normal', 'cavity'))

# R alpha, G translucency (real data, confirmed shared engine convention),
# B ao. A stays a constant -- no further quantity confirmed there.
_ATOSSS = SlotSocket("AlphaTranslucentOcclusionSSSMap", "core.shader_pack.atosss",
                     default_color=(1.0, 0.0, 1.0, 1.0),
                     supplies=('alpha', 'ao', 'translucency'))

_OCC = SlotSocket("OcclusionMap", "core.shader_pack.occ",
                  default_color=(1.0, 1.0, 1.0, 1.0),
                  supplies=('ao',))

_EMISSIVE = SlotSocket("EmissiveMap", "core.shader_pack.emissive",
                       default_color=(0.0, 0.0, 0.0, 1.0), alpha=True, default_alpha=1.0,
                       supplies=('emissive',), non_color=False)

# ── Secondary slots: no PBR recipe, carried through untouched so an existing
# image on the slot survives the round trip to the exporter. One definition
# each, matching the real presets' own Texture Bindings -- not fabricated.

def _inert(name, default_color=(1.0, 1.0, 1.0, 1.0), non_color=True):
    return SlotSocket(name, _K + name.lower(), default_color=default_color,
                      non_color=non_color, display=False)

_DETAILMAP       = _inert("DetailMap", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_MASKMAP         = _inert("MaskMap", default_color=(0.0, 0.0, 0.0, 1.0))
_IMPERFECTDETAIL = _inert("ImperfectDetail_Map", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_WRINKLENORMAL   = _inert("WrinkleNormalMap", default_color=(0.5, 0.5, 1.0, 1.0))
_WINDMASK        = _inert("Wind_MaskMap")
_NOISE3D         = _inert("Noise3D", default_color=(0.5, 0.5, 0.5, 1.0))
_RECSYS_RTT      = _inert("RecordSys_rtt", default_color=(0.0, 0.0, 0.0, 1.0))
_RECSYS_FIX      = _inert("RecordSys_Fix", default_color=(0.0, 0.0, 0.0, 1.0))
_RECSYS_PROTECT  = _inert("RecordSys_Protect", default_color=(0.0, 0.0, 0.0, 1.0))
_BLOODMASK       = _inert("BloodMask", default_color=(0.0, 0.0, 0.0, 1.0))
_BLOODFLOW_RTT   = _inert("BloodFlow_rtt", default_color=(0.0, 0.0, 0.0, 1.0))
_BLOODFLOW_UV    = _inert("BloodFlow_uv", default_color=(0.0, 0.0, 0.0, 1.0))
_INJURY_ALBA     = _inert("Injury_Map_ALBA", non_color=False)
_INJURY_NRM      = _inert("Injury_Map_NRM", default_color=(0.5, 0.5, 1.0, 1.0))
_STAINCLOTH      = _inert("Stain_Cloth_Map_MSK4", default_color=(0.0, 0.0, 0.0, 1.0))
_CLOTHDAMAGE     = _inert("clothDamagemaskMap")
_DIRTMASK        = _inert("DirtMask_Atex", default_color=(0.0, 0.0, 0.0, 1.0))
_RAIN_RIPPLE     = _inert("Rec_Rain_WaterRiple", default_color=(0.5, 0.5, 1.0, 1.0))
_RAIN_WETMASK    = _inert("Rec_Rain_WetMask")

_SECONDARY_ALBEDO = _inert("SecondaryAlbedoMap", default_color=(0.0, 0.0, 0.0, 1.0), non_color=False)
_RIMLIGHT_FAKENRM = _inert("RimLight_FakeNormalMap", default_color=(0.5, 0.5, 1.0, 1.0))

_FAKESPHERE  = _inert("FakeSphereMap", default_color=(0.0, 0.0, 0.0, 1.0))
_RAINSTREAK  = _inert("RainStreakMaskMap", default_color=(1.0, 0.5, 1.0, 1.0))
_RAINDROPS   = _inert("RainDropsMaskMap", default_color=(1.0, 0.5, 1.0, 1.0))

SLOTS_STANDARD = (
    _ALBD, _NRM, _ATOCM,
    _DETAILMAP, _MASKMAP, _IMPERFECTDETAIL, _WRINKLENORMAL, _WINDMASK, _NOISE3D,
    _RECSYS_RTT, _RECSYS_FIX, _RECSYS_PROTECT,
    _BLOODMASK, _BLOODFLOW_RTT, _BLOODFLOW_UV,
    _INJURY_ALBA, _INJURY_NRM, _STAINCLOTH, _CLOTHDAMAGE, _DIRTMASK,
    _RAIN_RIPPLE, _RAIN_WETMASK,
)

SLOTS_HAIR = (
    _BASESHIFT, _NRM, _ATOCM,
    _SECONDARY_ALBEDO, _RIMLIGHT_FAKENRM,
    _WINDMASK, _NOISE3D, _RAIN_RIPPLE, _RAIN_WETMASK,
)

SLOTS_EMISSIVE = (
    _ALBD, _NRCM, _ATOSSS, _OCC, _EMISSIVE,
    _FAKESPHERE, _RAINSTREAK, _RAINDROPS,
)

# ── Scattered PBR inputs (shared by all three specs) ────────────────────────

PBR = (
    PBRSocket("Base Color", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_base_color", pbr_type='color', non_color=False),
    PBRSocket("Alpha", 'NodeSocketFloat', 1.0, _K + "pbr_alpha",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='alpha'),
    PBRSocket("Roughness", 'NodeSocketFloat', 1.0, _K + "pbr_roughness",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='roughness'),
    PBRSocket("Metallic", 'NodeSocketFloat', 0.0, _K + "pbr_metallic",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='metallic'),
    # A plain multiply, same as Roughness/Metallic -- no separate "strength"
    # lerp knob. Every spec here has a genuine AO-carrying slot
    # (AlphaTranslucentOcclusionCavityMap.B / OcclusionMap), unlike MHWI,
    # which needs the strength knob because it has no AO slot at all.
    PBRSocket("AO", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_ao", pbr_type='ao'),
    # 1-neutral (multiplicative), same as AO/Roughness. Standard/Hair's
    # AlphaTranslucentOcclusionCavityMap.A and Emissive's
    # NormalRoughnessCavityMap.B both genuinely carry cavity data; both feed
    # the same AO-darkening chain their wire() function already builds.
    PBRSocket("Cavity", 'NodeSocketFloat', 1.0, _K + "pbr_cavity",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='cavity'),
    PBRSocket("Emission", 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0),
              _K + "pbr_emission", pbr_type='emissive', non_color=False),
    PBRSocket("Emission Strength", 'NodeSocketFloat', 1.0,
              "core.shader_pack.pbr_emission_strength", min_value=0.0, max_value=9999.0),
    PBRSocket("Normal", 'NodeSocketColor', (0.5, 0.5, 1.0, 1.0),
              _K + "pbr_normal", pbr_type='normal'),
    # 0-neutral (additive), same as Metallic. Standard/Hair's
    # AlphaTranslucentOcclusionCavityMap.G and Emissive's
    # AlphaTranslucentOcclusionSSSMap.G both genuinely carry translucency
    # data, but Principled has no matching input (not the same thing as
    # Subsurface Scattering, which needs radius data this module does not
    # have) -- same treatment MHWI gives RMTMap's blue channel: the socket
    # exists so the value round-trips to the exporter, the preview does not
    # attempt to show it.
    PBRSocket("Translucency", 'NodeSocketFloat', 0.0, _K + "pbr_translucency",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='translucency'),
)

_FLAT = 0.5


def _normal_deviation(b, socket, row):
    """Plain tangent-space normal-map colour (0..1) -> deviation from flat,
    for the loose PBR panel's own 'Normal' input."""
    sep = b.separate(socket, col=1, row=row)
    dr = b.math('SUBTRACT', sep.outputs[0], _FLAT, col=2, row=row)
    dg = b.math('SUBTRACT', sep.outputs[1], _FLAT, col=2, row=row + 1)
    return dr.outputs['Value'], dg.outputs['Value']


def _wire_normal_roughness_plain(b, row):
    """Standard/Hair: NormalRoughnessMap's R/G is a *plain* 2-channel normal
    (its B is unused, unlike NormalRoughnessCavityMap below -- see module
    docstring), summed with the loose PBR panel's own deviation and
    reconstructed once. Roughness comes from the slot's alpha channel."""
    nrm_sep = b.separate(b.inp('NormalRoughnessMap'), col=1, row=row)
    slot_dr = b.math('SUBTRACT', nrm_sep.outputs[0], _FLAT, col=2, row=row)
    slot_dg = b.math('SUBTRACT', nrm_sep.outputs[1], _FLAT, col=2, row=row + 1)
    pbr_dr, pbr_dg = _normal_deviation(b, b.inp('Normal'), row=row + 3)

    sum_r = b.math('ADD', slot_dr.outputs['Value'], pbr_dr, col=3, row=row)
    sum_g = b.math('ADD', slot_dg.outputs['Value'], pbr_dg, col=3, row=row + 1)
    r = b.math('ADD', sum_r.outputs['Value'], _FLAT, col=4, row=row)
    g = b.math('ADD', sum_g.outputs['Value'], _FLAT, col=4, row=row + 1)

    x = b.math('MULTIPLY_ADD', r.outputs['Value'], 2.0, col=5, row=row)
    x.inputs[2].default_value = -1.0
    y = b.math('MULTIPLY_ADD', g.outputs['Value'], 2.0, col=5, row=row + 1)
    y.inputs[2].default_value = -1.0
    xx = b.math('MULTIPLY', x.outputs['Value'], x.outputs['Value'], col=6, row=row)
    yy = b.math('MULTIPLY', y.outputs['Value'], y.outputs['Value'], col=6, row=row + 1)
    xxyy = b.math('ADD', xx.outputs['Value'], yy.outputs['Value'], col=7, row=row)
    zsq = b.math('SUBTRACT', 1.0, xxyy.outputs['Value'], clamp=True, col=8, row=row)
    z = b.math('SQRT', zsq.outputs['Value'], col=9, row=row)
    zenc = b.math('MULTIPLY_ADD', z.outputs['Value'], 0.5, col=10, row=row)
    zenc.inputs[2].default_value = 0.5

    ncomb = b.combine(r.outputs['Value'], g.outputs['Value'],
                      zenc.outputs['Value'], col=11, row=row)
    nmap = b.node('ShaderNodeNormalMap', col=12, row=row)
    nmap.inputs['Strength'].default_value = 1.0
    b.link(ncomb.outputs[0], nmap.inputs['Color'])
    b.link(nmap.outputs['Normal'], b.bsdf_in('Normal'))

    rough = b.math('MULTIPLY', b.inp('NormalRoughnessMap' + ALPHA_SUFFIX),
                   b.inp('Roughness'), clamp=True, col=1, row=row + 6)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))


def _wire_alpha_ao_single(b, atocm_sep, row):
    """Standard/Hair: AlphaTranslucentOcclusionCavityMap.R is real opacity,
    .B is AO, .A is cavity (.G is translucency, export-only -- see module
    docstring). Returns the AO colour output; the caller multiplies it into
    its own base colour."""
    alpha = b.math('MULTIPLY', atocm_sep.outputs[0], b.inp('Alpha'),
                   clamp=True, col=2, row=row + 2)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    cavity = b.math('MULTIPLY', b.inp('AlphaTranslucentOcclusionCavityMap' + ALPHA_SUFFIX),
                    b.inp('Cavity'), clamp=True, col=2, row=row + 4)

    ao_slot = b.mix('MULTIPLY', atocm_sep.outputs[2], b.inp('AO'), col=2, row=row)
    ao_final = b.mix('MULTIPLY', ao_slot.outputs['Color'], cavity.outputs['Value'], col=3, row=row)
    return ao_final.outputs['Color']


def _wire_standard(b):
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseDielectricMap'), b.inp('Base Color'))
    atocm_sep = b.separate(b.inp('AlphaTranslucentOcclusionCavityMap'), col=1, row=1)
    ao = _wire_alpha_ao_single(b, atocm_sep, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao, col=4, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                        clamp=True, col=1, row=4)
    metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                   clamp=True, col=2, row=4)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))

    _wire_normal_roughness_plain(b, row=6)

    # No EmissiveMap in the real presets (see module docstring) -- the PBR
    # panel's own Emission/Emission Strength still work standalone.
    b.link(b.inp('Emission'), b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


def _wire_hair(b):
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseShiftMap'), b.inp('Base Color'))
    atocm_sep = b.separate(b.inp('AlphaTranslucentOcclusionCavityMap'), col=1, row=1)
    ao = _wire_alpha_ao_single(b, atocm_sep, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao, col=4, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    # No metallic slot at all -- hair.json's Property List has no Metallic
    # property, so the panel is the only source (same as MHWS's hair spec).
    b.link(b.inp('Metallic'), b.bsdf_in('Metallic'))

    _wire_normal_roughness_plain(b, row=6)

    b.link(b.inp('Emission'), b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


_COS45 = math.cos(math.radians(45.0))
_SIN45 = math.sin(math.radians(45.0))


def _octahedral_real(b, green, alpha, row):
    """RE Engine's 3-in-1 normal slot (NormalRoughnessCavityMap here; also
    MHWS's NormalRoughnessOcclusionMap): decode a packed (green, alpha) pair
    (0..1) into real tangent-space (x, y) in -1..1.

    Node-for-node copy of games/mhws/shader_defs.py's _octahedral_real (see
    that module and core/re_normal_pack.decode_normal_ga for why the
    transform looks like this)."""
    nx = b.math('MULTIPLY_ADD', green, 2.0, col=2, row=row)
    nx.inputs[2].default_value = -1.0
    ny = b.math('MULTIPLY_ADD', alpha, -2.0, col=2, row=row + 1)
    ny.inputs[2].default_value = 1.0

    nx_sign = b.math('SIGN', nx.outputs['Value'], col=3, row=row)
    nx_sq   = b.math('MULTIPLY', nx.outputs['Value'], nx.outputs['Value'], col=3, row=row + 2)
    nx2     = b.math('MULTIPLY', nx_sign.outputs['Value'], nx_sq.outputs['Value'], col=4, row=row)

    ny_sign = b.math('SIGN', ny.outputs['Value'], col=3, row=row + 1)
    ny_sq   = b.math('MULTIPLY', ny.outputs['Value'], ny.outputs['Value'], col=3, row=row + 3)
    ny2     = b.math('MULTIPLY', ny_sign.outputs['Value'], ny_sq.outputs['Value'], col=4, row=row + 1)

    term_x = b.math('MULTIPLY', nx2.outputs['Value'], _COS45, col=5, row=row)
    x = b.math('MULTIPLY_ADD', ny2.outputs['Value'], -_SIN45, col=6, row=row)
    b.link(term_x.outputs['Value'], x.inputs[2])

    term_y = b.math('MULTIPLY', ny2.outputs['Value'], _COS45, col=5, row=row + 1)
    y = b.math('MULTIPLY_ADD', nx2.outputs['Value'], _SIN45, col=6, row=row + 1)
    b.link(term_y.outputs['Value'], y.inputs[2])

    return x.outputs['Value'], y.outputs['Value']


def _plain_real(b, socket, row):
    """Plain tangent-space normal-map colour (0..1) -> real (x, y) in -1..1,
    for the loose PBR panel's 'Normal' input."""
    sep = b.separate(socket, col=2, row=row)
    x = b.math('MULTIPLY_ADD', sep.outputs[0], 2.0, col=3, row=row)
    x.inputs[2].default_value = -1.0
    y = b.math('MULTIPLY_ADD', sep.outputs[1], 2.0, col=3, row=row + 1)
    y.inputs[2].default_value = -1.0
    return x.outputs['Value'], y.outputs['Value']


def _wire_normal_roughness_oct(b, row):
    """Emissive: NormalRoughnessCavityMap's G/A is hemi-octahedral (its B is a
    constant per RE4's override, but the G/A encoding scheme is a property of
    the slot type, shared with RE9 -- see module docstring). Roughness comes
    from R, unlike Standard/Hair's alpha-channel roughness."""
    nrcm_sep = b.separate(b.inp('NormalRoughnessCavityMap'), col=1, row=row)
    slot_x, slot_y = _octahedral_real(
        b, nrcm_sep.outputs[1], b.inp('NormalRoughnessCavityMap' + ALPHA_SUFFIX), row=row + 1)
    pbr_x, pbr_y = _plain_real(b, b.inp('Normal'), row=row + 5)

    sum_x = b.math('ADD', slot_x, pbr_x, col=8, row=row)
    sum_y = b.math('ADD', slot_y, pbr_y, col=8, row=row + 1)

    xx = b.math('MULTIPLY', sum_x.outputs['Value'], sum_x.outputs['Value'], col=9, row=row)
    yy = b.math('MULTIPLY', sum_y.outputs['Value'], sum_y.outputs['Value'], col=9, row=row + 1)
    xxyy = b.math('ADD', xx.outputs['Value'], yy.outputs['Value'], col=10, row=row)
    zsq = b.math('SUBTRACT', 1.0, xxyy.outputs['Value'], clamp=True, col=11, row=row)
    z = b.math('SQRT', zsq.outputs['Value'], col=12, row=row)

    xenc = b.math('MULTIPLY_ADD', sum_x.outputs['Value'], 0.5, col=13, row=row)
    xenc.inputs[2].default_value = 0.5
    yenc = b.math('MULTIPLY_ADD', sum_y.outputs['Value'], 0.5, col=13, row=row + 1)
    yenc.inputs[2].default_value = 0.5
    zenc = b.math('MULTIPLY_ADD', z.outputs['Value'], 0.5, col=13, row=row + 2)
    zenc.inputs[2].default_value = 0.5

    ncomb = b.combine(xenc.outputs['Value'], yenc.outputs['Value'],
                      zenc.outputs['Value'], col=14, row=row)
    nmap = b.node('ShaderNodeNormalMap', col=15, row=row)
    nmap.inputs['Strength'].default_value = 1.0
    b.link(ncomb.outputs[0], nmap.inputs['Color'])
    b.link(nmap.outputs['Normal'], b.bsdf_in('Normal'))

    rough = b.math('MULTIPLY', nrcm_sep.outputs[0], b.inp('Roughness'),
                   clamp=True, col=1, row=row + 9)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))


def _wire_emissive(b):
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseDielectricMap'), b.inp('Base Color'))

    # Two genuine AO sources here (unlike Standard/Hair's one) -- OcclusionMap
    # and AlphaTranslucentOcclusionSSSMap.B -- multiplied together the same
    # way MHWS multiplies its NRRO.B and ATOS.B. Cavity comes from a third
    # source, NormalRoughnessCavityMap.B -- a second, independent separate()
    # of that slot alongside the one _wire_normal_roughness_oct does below
    # for its normal/roughness channels.
    atosss_sep = b.separate(b.inp('AlphaTranslucentOcclusionSSSMap'), col=1, row=1)
    alpha = b.math('MULTIPLY', atosss_sep.outputs[0], b.inp('Alpha'),
                   clamp=True, col=2, row=3)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    nrcm_cavity_sep = b.separate(b.inp('NormalRoughnessCavityMap'), col=1, row=5)
    cavity = b.math('MULTIPLY', nrcm_cavity_sep.outputs[2], b.inp('Cavity'),
                    clamp=True, col=2, row=5)

    ao_slots = b.mix('MULTIPLY', b.inp('OcclusionMap'), atosss_sep.outputs[2], col=2, row=1)
    ao_cavity = b.mix('MULTIPLY', ao_slots.outputs['Color'], cavity.outputs['Value'], col=3, row=1)
    ao_final = b.mix('MULTIPLY', ao_cavity.outputs['Color'], b.inp('AO'), col=4, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao_final.outputs['Color'], col=5, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                        clamp=True, col=1, row=4)
    metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                   clamp=True, col=2, row=4)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))

    _wire_normal_roughness_oct(b, row=6)

    emi = b.mix('ADD', b.inp('EmissiveMap'), b.inp('Emission'), col=1, row=20)
    b.link(emi.outputs['Color'], b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


SPEC_STANDARD = ShaderPackSpec(
    group_name    = "MTK RE4 Standard",
    shader_id     = "re4_standard_v2",   # v2: rebuilt from real pbr_body/pbr_cloth
                                          # presets (v1 guessed NormalRoughnessCavityMap
                                          # + a dedicated OcclusionMap; those belong to
                                          # Emissive, not Standard)
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_standard",
    pbr           = PBR,
    slots         = SLOTS_STANDARD,
    wire          = _wire_standard,
    preset_filename = "standard.json",
)

SPEC_HAIR = ShaderPackSpec(
    group_name    = "MTK RE4 Hair",
    shader_id     = "re4_hair_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_hair",
    pbr           = PBR,
    slots         = SLOTS_HAIR,
    wire          = _wire_hair,
    preset_filename = "hair.json",
)

SPEC_EMISSIVE = ShaderPackSpec(
    group_name    = "MTK RE4 Emissive",
    shader_id     = "re4_emissive_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_emissive",
    pbr           = PBR,
    slots         = SLOTS_EMISSIVE,
    wire          = _wire_emissive,
    preset_filename = "emissive.json",
)

#: Registry for core/shader_ops.py -- one "game" ident per archetype.
VARIANTS = {
    'RE4_STANDARD': SPEC_STANDARD,
    'RE4_HAIR':     SPEC_HAIR,
    'RE4_EMISSIVE': SPEC_EMISSIVE,
}
