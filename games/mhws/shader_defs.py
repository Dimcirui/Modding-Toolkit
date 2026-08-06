"""MHWS (MDF2) packed shader specs -- one per material archetype.

Unlike MHWI (one fairly uniform slot set), MHWS's real .mmtr shader templates
diverge by material type -- a skin material carries SkinMap/BlendNormalMap a
Standard material never uses, and hair uses a completely different base-colour
slot. Cramming everything into one node would make the "Game Slots" panel
enormous and mostly irrelevant for any given material, so this defines four
specs instead, each read directly off the user's own curated
Presets/MHWILDS/{cloth,weapon,skin,hair}.json (not just researched), one spec
per preset -- cloth.json and weapon.json share the same core-4 slots and
wiring but are genuinely different compiled shaders (different Master
Material Path, and each carries extras the other does not: cloth has
MultiBlend/ColorLayerDetail/Ripple, weapon has Wind/VFX/GpuWind), so they stay
two specs, not one merged "Standard". A fifth, Jewel, existed briefly but
turned out to be Standard(cloth) under a different mmtr path with no wiring
difference -- folded in. The toon/matcap presets (outline, stockings_matcap,
and the *_toon/*_matcap family) are a different rendering approach entirely
and are out of scope for a Principled-based group; expTransparent/
roughTransparent/lightEmissive are Principled-representable but not wired yet
either -- deferred, not dropped.

Shared reasoning across all four (see also games/mhwi/shader_defs.py for the
general design):

BaseDielectricMap's alpha channel is *not* opacity -- it is inverted metallic
(Metallic = 1 - alpha; RE Mesh Editor sets an explicit "isDielectric" flag and
runs the accumulated metallic layer through an Invert node before the BSDF).
Real opacity for a translucent/cutout material comes from
AlphaTranslucentOcclusionSSSMap's R channel (all four specs carry this slot),
multiplied with BaseAlphaMap's own alpha channel on Hair specifically (Hair
has no BaseDielectricMap at all -- hair isn't metallic, so there is nothing
for an inverted-alpha slot to usefully carry, but BaseAlphaMap gives it a
second real alpha source Standard/Skin/Weapon don't have).

NormalRoughnessOcclusionMap packs Roughness in R and AO in B, which leaves no
room for a conventional two-channel normal (R free, reconstruct Z from R/G) --
so its G/A pair carries a *hemi-octahedral* encoding instead: rotate 45 degrees
and square (sign-preserving) rather than a plain copy. This is not a MHWS
quirk: RE Mesh Editor's own texture packer (texturepacker/image_utils.py)
applies the identical NRMRToNRRX/NRRXToNRMR transform to any RE Engine slot
that packs a third quantity into B, and a plain copy to the ones that don't
(NormalRoughness/NormalRoughnessMap). See core/re_normal_pack.py for the
export-side encode (used by _compose_channels) -- the decode wired below
matches it (verified round-trip: encode then this decode recovers the original
normal, up to RE Mesh Editor's own OpenGL-preview Y flip, which is why this
uses the same sign RE Mesh Editor's decode does, not a "corrected" one; there
is no independent ground truth to correct it against, and getting the sign
wrong here only ever affects the *preview*, not the exported bytes).

Unlike MHWI, AO genuinely round-trips: NormalRoughnessOcclusionMap.B always
reads the 'ao' PBR type (channel_maps_consume_ao() is True for MHWS), so there
is no MHWI-style preview-only caveat needed on the AO socket here.

Everything past each preset's PBR-relevant core (detail maps, VFX, panorama,
ripple, hair flow, ...) has no composition recipe in
core.mdf_tex_processor_base.BASE_SLOT_CHANNEL_MAPS and is display=False --
same treatment as MHWI's ColorMaskMap/FxMap/FurVelocityMap: the socket exists
purely so an existing image on that slot survives the round trip to the
exporter, not because the preview can do anything with it. SkinMap,
BlendNormalMap and HairFlowMap have no known channel recipe at all (not even
in BASE_NULL_TEX_BY_TYPE) and are carried the same way, content unknown.
"""

import math

from ...core.shader_pack import (
    ShaderPackSpec, SlotSocket, PBRSocket, ALPHA_SUFFIX,
)

_K = "mhws.shader_defs."

# non_color mirrors SRGB_SLOT_TYPES = {'BaseDielectricMap', 'BaseAlphaMap',
# 'EmissiveMap', 'Emissive_ColorMap', 'BaseShiftMap'}: colour vs packed data.

# ── Core slots (PBR-recipe-bearing, actually wired) ─────────────────────────

_ALBD = SlotSocket("BaseDielectricMap", _K + "albd",
                   default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('color', 'metallic'), non_color=False)

# R roughness, G/A hemi-octahedral normal, B AO. G=0.5/A=0.5 decodes to a flat
# normal (see decode_normal_ga) -- the same "identity" property the combiner
# rule wants from every neutral default.
_NRRO = SlotSocket("NormalRoughnessOcclusionMap", _K + "nrro",
                   default_color=(1.0, 0.5, 1.0, 1.0), alpha=True, default_alpha=0.5,
                   supplies=('roughness', 'normal', 'ao'))

_EMI = SlotSocket("EmissiveMap", _K + "emissive",
                  default_color=(0.0, 0.0, 0.0, 1.0), alpha=True, default_alpha=1.0,
                  supplies=('emissive',), non_color=False)

# G/A are constants in BASE_SLOT_CHANNEL_MAPS (not used by any PBR type); only
# R (alpha/opacity) and B (AO) carry real data.
_ATOS = SlotSocket("AlphaTranslucentOcclusionSSSMap", _K + "atos",
                   default_color=(1.0, 1.0, 1.0, 1.0),
                   supplies=('alpha', 'ao'))

# Hair's base slot: RGB colour, A real opacity (unlike BaseDielectricMap).
_BASEALPHA = SlotSocket("BaseAlphaMap", _K + "basealpha",
                        default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                        supplies=('color', 'alpha'), non_color=False)

# ── Secondary slots (display=False: carried for export, not previewed) ────
# One definition each, shared across whichever specs' presets list them.

def _inert(name, default_color=(1.0, 1.0, 1.0, 1.0), non_color=True):
    return SlotSocket(name, _K + name.lower(), default_color=default_color,
                      non_color=non_color, display=False)

_MP_NOISE       = _inert("MP_noise")
_WIND_VOLUME    = _inert("Wind_Effect_VolumeMap")
_FX             = _inert("FxMap", default_color=(0.0, 0.0, 0.0, 1.0))
_NOISEMAP       = _inert("noisemap", default_color=(0.5, 0.5, 0.5, 1.0))
_DETAIL_MASK    = _inert("DetailMaskMap", default_color=(0.0, 0.0, 0.0, 1.0))
_DETAIL_ALBD_R  = _inert("Detail_ALBD_R", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_DETAIL_NRRH_R  = _inert("Detail_NRRH_R", default_color=(1.0, 0.5, 1.0, 1.0))
_DETAIL_ALBD_G  = _inert("Detail_ALBD_G", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_DETAIL_NRRH_G  = _inert("Detail_NRRH_G", default_color=(1.0, 0.5, 1.0, 1.0))
_DETAIL_ALBD_B  = _inert("Detail_ALBD_B", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_DETAIL_NRRH_B  = _inert("Detail_NRRH_B", default_color=(1.0, 0.5, 1.0, 1.0))
_DETAIL_ALBD_A  = _inert("Detail_ALBD_A", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_DETAIL_NRRH_A  = _inert("Detail_NRRH_A", default_color=(1.0, 0.5, 1.0, 1.0))
_PANORAMA       = _inert("PanoramaMap", non_color=False)
_VECTOR_EMIT    = _inert("VectorEmitMap")
_COLORLAYER_MASK = _inert("ColorLayer_MaskMap", default_color=(0.0, 0.0, 0.0, 1.0))
_VFX_2D         = _inert("VFX_Texture2D")
_VFX_3D         = _inert("VFX_Texture3D")
_GPUWIND_MASK   = _inert("GpuWind_MaskMap")
_SKIN_MAP       = _inert("SkinMap")
_BLEND_NORMAL   = _inert("BlendNormalMap")
_HAIR_FLOW      = _inert("HairFlowMap")
_HAIR_SPECSHIFT = _inert("Hair_Height_SpecMask_Shift_Map")
_HAIR_OVER      = _inert("HairOverMap", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)

# ── Scattered PBR inputs (shared by all four specs) ─────────────────────────
# Defaults are the neutral element of each quantity's combiner (see module
# docstring in core/shader_pack.py), so filling in only this panel gives
# exactly the typed value.

PBR = (
    PBRSocket("Base Color", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_base_color", pbr_type='color', non_color=False),
    PBRSocket("Alpha", 'NodeSocketFloat', 1.0, _K + "pbr_alpha",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='alpha'),
    PBRSocket("Roughness", 'NodeSocketFloat', 1.0, _K + "pbr_roughness",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='roughness'),
    PBRSocket("Metallic", 'NodeSocketFloat', 0.0, _K + "pbr_metallic",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='metallic'),
    PBRSocket("AO", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_ao", pbr_type='ao'),
    PBRSocket("AO Strength", 'NodeSocketFloat', 0.5, _K + "pbr_ao_strength",
              min_value=0.0, max_value=1.0, subtype='FACTOR'),
    PBRSocket("Emission", 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0),
              _K + "pbr_emission", pbr_type='emissive', non_color=False),
    PBRSocket("Emission Strength", 'NodeSocketFloat', 1.0,
              _K + "pbr_emission_strength", min_value=0.0, max_value=9999.0),
    # A colour, not a vector -- same reasoning as MHWI's spec: the reader hands
    # over the image behind any Normal Map node, which would be wrong to feed
    # into a vector socket (no tangent-space decode done yet).
    PBRSocket("Normal", 'NodeSocketColor', (0.5, 0.5, 1.0, 1.0),
              _K + "pbr_normal", pbr_type='normal'),
)


_COS45 = math.cos(math.radians(45.0))
_SIN45 = math.sin(math.radians(45.0))


def _plain_real(b, socket, row):
    """Plain tangent-space normal-map colour (0..1) -> real (x, y) in -1..1,
    for the loose PBR 'Normal' panel input -- an ordinary normal map, not a
    hemi-octahedral one."""
    sep = b.separate(socket, col=2, row=row)
    x = b.math('MULTIPLY_ADD', sep.outputs[0], 2.0, col=3, row=row)
    x.inputs[2].default_value = -1.0
    y = b.math('MULTIPLY_ADD', sep.outputs[1], 2.0, col=3, row=row + 1)
    y.inputs[2].default_value = -1.0
    return x.outputs['Value'], y.outputs['Value']


def _octahedral_real(b, green, alpha, row):
    """RE Engine's 3-in-1 normal slot (NormalRoughnessOcclusionMap /
    NormalRoughnessCavityMap): decode a packed (green, alpha) pair (0..1)
    into real tangent-space (x, y) in -1..1.

    Node-for-node translation of core/re_normal_pack.decode_normal_ga (see
    that module for why the transform looks like this, and for the
    export-side encode this is the preview counterpart of). Deliberately
    returns *real* coordinates, not a half-scale "deviation" shortcut the way
    MHWI's plain decode can -- the octahedral transform is not linear, so
    there is no equivalent shortcut here; the caller must convert the loose
    PBR panel's own input to real coordinates the same way before summing.
    """
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

    # Rotate +45 degrees: x = nx2*cos45 - ny2*sin45, y = nx2*sin45 + ny2*cos45
    term_x = b.math('MULTIPLY', nx2.outputs['Value'], _COS45, col=5, row=row)
    x = b.math('MULTIPLY_ADD', ny2.outputs['Value'], -_SIN45, col=6, row=row)
    b.link(term_x.outputs['Value'], x.inputs[2])

    term_y = b.math('MULTIPLY', ny2.outputs['Value'], _COS45, col=5, row=row + 1)
    y = b.math('MULTIPLY_ADD', nx2.outputs['Value'], _SIN45, col=6, row=row + 1)
    b.link(term_y.outputs['Value'], y.inputs[2])

    return x.outputs['Value'], y.outputs['Value']


def _wire_normal(b, nrro_sep, row=7):
    """Shared by every spec that has NormalRoughnessOcclusionMap: sum the
    slot's octahedral-decoded deviation with the loose PBR panel's plain one,
    reconstruct Z once, feed a real ShaderNodeNormalMap."""
    slot_x, slot_y = _octahedral_real(
        b, nrro_sep.outputs[1], b.inp('NormalRoughnessOcclusionMap' + ALPHA_SUFFIX), row=row)
    pbr_x, pbr_y = _plain_real(b, b.inp('Normal'), row=row + 4)

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


def _wire_dielectric(b):
    """Standard/Weapon/Skin: BaseDielectricMap + NormalRoughnessOcclusionMap +
    AlphaTranslucentOcclusionSSSMap. Emission is the one piece that
    differs (Skin has no EmissiveMap), so the caller wires that itself."""
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseDielectricMap'), b.inp('Base Color'))

    nrro_sep = b.separate(b.inp('NormalRoughnessOcclusionMap'), col=1, row=1)
    atos_sep = b.separate(b.inp('AlphaTranslucentOcclusionSSSMap'), col=1, row=2)

    ao_slots = b.math('MULTIPLY', nrro_sep.outputs[2], atos_sep.outputs[2], col=2, row=1)
    ao_combined = b.mix('MULTIPLY', ao_slots.outputs['Value'], b.inp('AO'), col=3, row=1)
    ao_final = b.mix('MIX', (1.0, 1.0, 1.0, 1.0), ao_combined.outputs['Color'],
                     fac=b.inp('AO Strength'), col=4, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao_final.outputs['Color'], col=5, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    # Alpha from ATOS.R -- BaseDielectricMap's own alpha is metallic, not opacity.
    alpha = b.math('MULTIPLY', atos_sep.outputs[0], b.inp('Alpha'), clamp=True, col=2, row=3)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    # Metallic: inverted BaseDielectricMap alpha + Metallic panel.
    albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                        clamp=True, col=1, row=4)
    metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                   clamp=True, col=2, row=4)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))

    # Roughness: NRRO.R x Roughness panel.
    rough = b.math('MULTIPLY', nrro_sep.outputs[0], b.inp('Roughness'),
                   clamp=True, col=2, row=5)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))

    _wire_normal(b, nrro_sep)


def _wire_emission(b, row=14):
    emi = b.mix('ADD', b.inp('EmissiveMap'), b.inp('Emission'), col=1, row=row)
    b.link(emi.outputs['Color'], b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


def _wire_emission_panel_only(b, row=14):
    """No EmissiveMap slot on this spec (Skin/Hair) -- the PBR panel's own
    Emission/Emission Strength still work standalone."""
    b.link(b.inp('Emission'), b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


def _wire_standard(b):
    _wire_dielectric(b)
    _wire_emission(b)


def _wire_skin(b):
    _wire_dielectric(b)
    _wire_emission_panel_only(b)


def _wire_hair(b):
    """Hair has no BaseDielectricMap (not metallic) and no EmissiveMap, but --
    per hair.json's own real Texture Bindings list -- it does carry
    AlphaTranslucentOcclusionSSSMap alongside BaseAlphaMap, wired exactly the
    way Standard/Skin combine ATOS with their own base slot: R multiplies into
    alpha, B multiplies into AO. BaseAlphaMap supplies colour and its own real
    opacity on top of that (Standard/Skin have no equivalent second alpha
    source, since BaseDielectricMap's alpha is metallic, not opacity)."""
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseAlphaMap'), b.inp('Base Color'))

    nrro_sep = b.separate(b.inp('NormalRoughnessOcclusionMap'), col=1, row=1)
    atos_sep = b.separate(b.inp('AlphaTranslucentOcclusionSSSMap'), col=1, row=2)

    ao_slots = b.math('MULTIPLY', nrro_sep.outputs[2], atos_sep.outputs[2], col=2, row=1)
    ao_combined = b.mix('MULTIPLY', ao_slots.outputs['Value'], b.inp('AO'), col=3, row=1)
    ao_final = b.mix('MIX', (1.0, 1.0, 1.0, 1.0), ao_combined.outputs['Color'],
                     fac=b.inp('AO Strength'), col=4, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao_final.outputs['Color'], col=5, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    alpha_base = b.math('MULTIPLY', b.inp('BaseAlphaMap' + ALPHA_SUFFIX), atos_sep.outputs[0],
                        clamp=True, col=2, row=3)
    alpha = b.math('MULTIPLY', alpha_base.outputs['Value'], b.inp('Alpha'),
                   clamp=True, col=3, row=3)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    # No metallic slot at all -- the panel is the only source.
    b.link(b.inp('Metallic'), b.bsdf_in('Metallic'))

    rough = b.math('MULTIPLY', nrro_sep.outputs[0], b.inp('Roughness'),
                   clamp=True, col=2, row=5)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))

    _wire_normal(b, nrro_sep)
    _wire_emission_panel_only(b)


# ── Standard: BaseDielectricMap / NormalRoughnessOcclusionMap / EmissiveMap /
# AlphaTranslucentOcclusionSSSMap, plus detail maps, colour layer mask. The
# general opaque case: cloth, most armour and character parts. Slot list
# matches Presets/MHWILDS/cloth.json's own Texture Bindings exactly (that
# preset is what gets bundled as the Standard prefab, verbatim -- no
# fabricated bindings), minus MultiBlend_ALBDMap/MultiBlend_NRMMap/
# ColorLayer_DetailMaskMap/Ripple_1Dtex/Ripple_Texture3D: none of them has a
# composition recipe in core.mdf_tex_processor_base.BASE_SLOT_CHANNEL_MAPS
# yet, and adding bindings a preset's real compiled shader doesn't carry is
# exactly the kind of structural mismatch that risks a crash (see
# MHWilds-Offline-Fixer's mmtrsubs_MHWILDS.json). Revisit if the
# processor/generator ever gain a recipe for them. Weapon (below) is cloth's
# closest sibling -- same core-4, different mmtr, different extras -- but is
# its own spec/prefab, not folded into this one. ────────────────────────────

SLOTS_STANDARD = (
    _ALBD, _NRRO, _EMI, _ATOS,
    _MP_NOISE, _FX, _NOISEMAP, _DETAIL_MASK,
    _DETAIL_ALBD_R, _DETAIL_NRRH_R, _DETAIL_ALBD_G, _DETAIL_NRRH_G,
    _DETAIL_ALBD_B, _DETAIL_NRRH_B, _DETAIL_ALBD_A, _DETAIL_NRRH_A,
    _PANORAMA, _VECTOR_EMIT, _COLORLAYER_MASK,
)

SPEC_STANDARD = ShaderPackSpec(
    group_name    = "MTK MHWS Standard",
    shader_id     = "mhws_standard_v4",   # v4: rebuilt from cloth.json, not
                                           # weapon.json (v3's mistake -- weapon
                                           # is its own separate mmtr/spec, see
                                           # SPEC_WEAPON below)
    pbr_panel_key = _K + "panel_pbr",
    slot_panel_key= _K + "panel_slots_standard",
    pbr           = PBR,
    slots         = SLOTS_STANDARD,
    wire          = _wire_standard,
    preset_filename = "standard.json",
)

# ── Weapon: same core-4 + detail/colour-layer slots as Standard, but its own
# Master Material Path (Base_ATOS_FX_SecEmit_VEmit_Detail_ColLayer_VFXwe.mmtr,
# vs cloth's Base_ATOS_Emit_FX_Detail_DetailColLayer_MultiBlend.mmtr) and its
# own extras -- Wind_Effect_VolumeMap/VFX_Texture2D/VFX_Texture3D/
# GpuWind_MaskMap instead of cloth's MultiBlend/ColorLayerDetail/Ripple. Slot
# list matches Presets/MHWILDS/weapon.json's own Texture Bindings exactly. ──

SLOTS_WEAPON = (
    _ALBD, _NRRO, _EMI, _ATOS,
    _MP_NOISE, _WIND_VOLUME, _FX, _NOISEMAP, _DETAIL_MASK,
    _DETAIL_ALBD_R, _DETAIL_NRRH_R, _DETAIL_ALBD_G, _DETAIL_NRRH_G,
    _DETAIL_ALBD_B, _DETAIL_NRRH_B, _DETAIL_ALBD_A, _DETAIL_NRRH_A,
    _PANORAMA, _VECTOR_EMIT, _COLORLAYER_MASK,
    _VFX_2D, _VFX_3D, _GPUWIND_MASK,
)

SPEC_WEAPON = ShaderPackSpec(
    group_name    = "MTK MHWS Weapon",
    shader_id     = "mhws_weapon_v1",
    pbr_panel_key = _K + "panel_pbr",
    slot_panel_key= _K + "panel_slots_weapon",
    pbr           = PBR,
    slots         = SLOTS_WEAPON,
    wire          = _wire_standard,
    preset_filename = "weapon.json",
)

# ── Skin: no EmissiveMap, no detail/multiblend -- adds SkinMap/BlendNormalMap
# and the VFX slots instead. Matches Presets/MHWILDS/skin.json (10 slots). ───

SLOTS_SKIN = (
    _ALBD, _NRRO, _ATOS,
    _MP_NOISE, _NOISEMAP, _VFX_2D, _VFX_3D, _COLORLAYER_MASK,
    _SKIN_MAP, _BLEND_NORMAL,
)

SPEC_SKIN = ShaderPackSpec(
    group_name    = "MTK MHWS Skin",
    shader_id     = "mhws_skin_v1",
    pbr_panel_key = _K + "panel_pbr",
    slot_panel_key= _K + "panel_slots_skin",
    pbr           = PBR,
    slots         = SLOTS_SKIN,
    wire          = _wire_skin,
    preset_filename = "skin.json",
)

# ── Hair: BaseAlphaMap instead of BaseDielectricMap (not metallic, real
# opacity), no EmissiveMap. Still has AlphaTranslucentOcclusionSSSMap, same as
# Standard/Skin. Matches Presets/MHWILDS/hair.json's real Texture Bindings
# exactly (10 slots). ────────────────────────────────────────────────────────

SLOTS_HAIR = (
    _NRRO, _BASEALPHA, _ATOS,
    _MP_NOISE, _NOISEMAP, _VFX_2D, _VFX_3D,
    _HAIR_FLOW, _HAIR_SPECSHIFT, _HAIR_OVER,
)

SPEC_HAIR = ShaderPackSpec(
    group_name    = "MTK MHWS Hair",
    shader_id     = "mhws_hair_v2",   # v2: added AlphaTranslucentOcclusionSSSMap,
                                       # missing from v1 (hair.json's real Texture
                                       # Bindings list has it; v1 had dropped it)
    pbr_panel_key = _K + "panel_pbr",
    slot_panel_key= _K + "panel_slots_hair",
    pbr           = PBR,
    slots         = SLOTS_HAIR,
    wire          = _wire_hair,
    preset_filename = "hair.json",
)


#: Registry for core/shader_ops.py -- one "game" ident per variant.
VARIANTS = {
    'MHWS_STANDARD': SPEC_STANDARD,
    'MHWS_WEAPON':   SPEC_WEAPON,
    'MHWS_SKIN':     SPEC_SKIN,
    'MHWS_HAIR':     SPEC_HAIR,
}
