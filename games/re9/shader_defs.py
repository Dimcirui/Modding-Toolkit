"""RE9 (MDF2) packed shader specs — four material archetypes.

Built from real RE Mesh Editor presets in RE-Mesh-Editor/Presets/RE9/
(PBR_Cloth.json, PBR_Hair.json, PBR_Skin.json, EMI_Cloth.json, EMI_Body.json,
EMI_Hair.json — provided directly by the user), following the same
real-preset-driven approach games/re4/shader_defs.py settled on (see that
module's docstring for the "don't guess bindings" lesson this repeats).

PBR family: Standard / Skin / Hair
------------------------------------
Each has its own Master Material Path (Ch_Detail_Record_Wet_Burnt.mmtr /
Ch_Skin_Detail_Record_Wet_Burnt.mmtr / Ch_Hair_Record_Wet_Burnt.mmtr) --
genuinely different compiled shaders, same reasoning MHWS uses to keep
cloth/weapon separate even though their core slots overlap -- so three
specs, not one merged "Standard".

All three share:

  * NormalRoughnessMap -- R/G plain tangent-space normal, B unused, A
    roughness. Same layout and decode as RE4 Standard's NormalRoughnessMap
    (BASE_SLOT_CHANNEL_MAPS's generic entry, no RE9-specific override) --
    no hemi-octahedral transform.

Standard and Hair also share:

  * AlphaCavityOcclusionTranslucentMap -- R real opacity, G cavity, B AO, A
    translucency (per BASE_SLOT_CHANNEL_MAPS; A is export-only, no Principled
    input matches it). Same layout as RE4's AlphaTranslucentOcclusionCavityMap
    under a different RE9 name, plus its name's own channel order.

Skin instead uses:

  * SSSCavityOcclusionTranslucentMap -- R is a *constant* 1.0 in
    BASE_SLOT_CHANNEL_MAPS (no alpha data at all -- skin is not meant to be
    transparent), G cavity, B AO. No translucency channel here (confirmed by
    the user), unlike ACOT/ATOSSS. So Skin has no slot-sourced opacity; the
    PBR panel's own Alpha is the only source there, the same treatment RE4's
    Emissive-adjacent presets give a spec with no real opacity slot.

Standard (Ch_Detail, from PBR_Cloth.json) and Skin (Ch_Skin_Detail, from
PBR_Skin.json) both use BaseDielectricMap (RGB colour, A inverted metallic --
same isDielectric convention as MHWS/RE4). Hair (Ch_Hair, from PBR_Hair.json)
uses BaseShiftMap instead (RGB colour, no metallic-alpha convention --
hair.json's own Property List has no Metallic property at all, matching
RE4's hair spec exactly).

None of the three have an EmissiveMap binding -- omitted, following MHWS/RE4's
rule of not adding bindings a real compiled shader doesn't carry. The PBR
panel's Emission/Emission Strength still work standalone.

All three carry an enormous, near-identical "Record system" secondary slot
set (damage decals: LightDamage_*/HeavyDamage_*/BurntMap_*/Blood_NRRA;
RecordSys_rtt/FixMask/ProtectMask/AddMask; FixBloodMask/BloodShed_rtt; rain:
RainDrop_StopDrops/FlickDrops/DropMask; WetMap) plus a smaller
archetype-specific set (Standard: DetailMask/DetailAlbedoMap/DetailMap/
ImperfectDetail_Map/WrinkleMap; Skin: DetailMask/DetailAlbedoMap/DetailMap/
SweatMap; Hair: SecondaryBaseColorMap(_MaskMap)/Specular_FlowMap/
RimLight_FakeNormalMap/DirtMaskMap/DirtWearMap). None of these have a PBR
composition recipe -- carried as display=False sockets so an existing image
on any of them survives the round trip to the exporter, same treatment
MHWS/RE4 give their own detail/VFX slots. One shared slot object per name,
reused across whichever specs' real presets list it, same as MHWS's
_inert() slots.

Emissive
--------
Env_Default_Emissive.mmtr, confirmed by the user as a genuinely
general-purpose emissive master material (not archetype-specific) -- three
sample presets (EMI_Cloth/EMI_Body/EMI_Hair.json) share the exact same
Master Material Path, Property List and 5-slot Texture Bindings list, only
differing in material name and which bindings point to real vs Null
textures, so this is one merged spec covering cloth/body/hair alike, not
three. Its channel packing is identical to RE4's Emissive archetype (RE9 and
RE4 share the exact same RE9_SLOT_CHANNEL_MAPS/RE4_SLOT_CHANNEL_MAPS
overrides in games/re9/mdf_tex_processor.py and games/re4/mdf_tex_processor.py
-- both modules' own comments say "same as RE9"/"same as RE4"):

  * BaseDielectricMap -- same as Standard/Skin.
  * NormalRoughnessCavityMap -- R roughness, G/A hemi-octahedral normal, B
    cavity (confirmed by the user; an earlier version of this module wrongly
    treated B as an unused constant). B is read via a second, independent
    separate() alongside the one used for the normal/roughness decode.
  * AlphaTranslucentOcclusionSSSMap -- R real opacity, B AO, G translucency
    (export-only). Identical recipe to AlphaCavityOcclusionTranslucentMap
    above minus the cavity channel (this slot has none), different RE9 slot
    name.
  * OcclusionMap -- RE9's own dedicated AO slot (R=G=B=ao, plain greyscale;
    RE9_SLOT_CHANNEL_MAPS's override). A second genuine AO source alongside
    AlphaTranslucentOcclusionSSSMap.B, multiplied together the same way
    RE4's Emissive spec (and MHWS's NRRO/ATOS pair) combines two real AO
    sources.
  * EmissiveMap -- the actual point of this master material.

Unlike RE4's Emissive (Eye_EMI.json), none of the three RE9 EMI_* samples
carry FakeSphereMap/RainStreakMaskMap/RainDropsMaskMap or any other
secondary binding -- their Texture Bindings lists are exactly these 5 slots,
nothing else, so this spec has no display=False sockets at all.
"""

import math

from ...core.shader_pack import (
    ShaderPackSpec, SlotSocket, PBRSocket, ALPHA_SUFFIX,
)

_K = "re9.shader_defs."

# ── Core slots: plain-normal family (Standard, Skin, Hair) ─────────────────

_NRM = SlotSocket("NormalRoughnessMap", "core.shader_pack.nrm",
                  default_color=(0.5, 0.5, 1.0, 1.0), alpha=True, default_alpha=1.0,
                  supplies=('normal', 'roughness'))

_ALBD = SlotSocket("BaseDielectricMap", "core.shader_pack.albd",
                   default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('color', 'metallic'), non_color=False)

_BASESHIFT = SlotSocket("BaseShiftMap", "core.shader_pack.baseshift",
                        default_color=(1.0, 1.0, 1.0, 1.0), non_color=False,
                        supplies=('color',))

# Standard/Hair: real opacity (R), cavity (G), AO (B), translucency (A).
_ACOT = SlotSocket("AlphaCavityOcclusionTranslucentMap", _K + "acot",
                   default_color=(1.0, 0.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('alpha', 'ao', 'cavity', 'translucency'))

# Skin: R is a BASE_SLOT_CHANNEL_MAPS *constant* (no opacity data) -- only
# cavity (G) and AO (B), per the module docstring. No translucency channel
# here, unlike ACOT/ATOSSS -- confirmed by the user.
_SSSCOT = SlotSocket("SSSCavityOcclusionTranslucentMap", _K + "ssscot",
                     default_color=(1.0, 1.0, 1.0, 1.0),
                     supplies=('ao', 'cavity'))

# ── Core slots: hemi-octahedral-normal family (Emissive) ───────────────────

_NRCM = SlotSocket("NormalRoughnessCavityMap", _K + "nrcm",
                   default_color=(1.0, 0.5, 1.0, 1.0), alpha=True, default_alpha=0.5,
                   supplies=('roughness', 'normal', 'cavity'))

_ATOSSS = SlotSocket("AlphaTranslucentOcclusionSSSMap", "core.shader_pack.atosss",
                     default_color=(1.0, 0.0, 1.0, 1.0),
                     supplies=('alpha', 'ao', 'translucency'))

_OCC = SlotSocket("OcclusionMap", "core.shader_pack.occ",
                  default_color=(1.0, 1.0, 1.0, 1.0),
                  supplies=('ao',))

_EMISSIVE = SlotSocket("EmissiveMap", "core.shader_pack.emissive",
                       default_color=(0.0, 0.0, 0.0, 1.0), alpha=True, default_alpha=1.0,
                       supplies=('emissive',), non_color=False)

# ── Secondary slots: no PBR recipe, carried through untouched -- one
# definition each, matching the real presets' own Texture Bindings. Shared
# across whichever specs' presets list them, same as MHWS's _inert() slots.

def _inert(name, default_color=(1.0, 1.0, 1.0, 1.0), non_color=True):
    return SlotSocket(name, _K + name.lower(), default_color=default_color,
                      non_color=non_color, display=False)

# Shared by Standard/Skin/Hair: the "Record system" damage/wet/rain set.
_WETMAP           = _inert("WetMap")
_RECSYS_FIXMASK   = _inert("RecordSys_FixMask")
_RECSYS_PROTECT   = _inert("RecordSys_ProtectMask", default_color=(0.0, 0.0, 0.0, 1.0))
_RECSYS_ADDMASK   = _inert("RecordSys_AddMask", default_color=(0.0, 0.0, 0.0, 1.0))
_FIXBLOODMASK     = _inert("FixBloodMask", default_color=(0.0, 0.0, 0.0, 1.0))
_BLOODSHED_RTT    = _inert("BloodShed_rtt", default_color=(0.0, 0.0, 0.0, 1.0))
_LIGHTDAMAGE_ALBD = _inert("LightDamage_ALBD", non_color=False)
_BURNTMAP_ALBM    = _inert("BurntMap_ALBM", non_color=False)
_LIGHTDAMAGE_NRRA = _inert("LightDamage_NRRA", default_color=(0.5, 0.5, 1.0, 1.0))
_BURNTMAP_NRMR    = _inert("BurntMap_NRMR", default_color=(0.5, 0.5, 1.0, 1.0))
_HEAVYDAMAGE_ALBD = _inert("HeavyDamage_ALBD", non_color=False)
_HEAVYDAMAGE_NRRA = _inert("HeavyDamage_NRRA", default_color=(0.5, 0.5, 1.0, 1.0))
_BLOOD_NRRA       = _inert("Blood_NRRA", default_color=(0.5, 0.5, 1.0, 1.0))
_RECSYS_RTT       = _inert("RecordSys_rtt", default_color=(0.0, 0.0, 0.0, 1.0))
_RAINDROP_STOP    = _inert("RainDrop_StopDrops", default_color=(0.5, 0.5, 1.0, 1.0))
_RAINDROP_FLICK   = _inert("RainDrop_FlickDrops", default_color=(0.5, 0.5, 1.0, 1.0))
_RAINDROP_MASK    = _inert("RainDrop_DropMask", default_color=(0.0, 0.0, 0.0, 1.0))

_RECORD_SYSTEM_SLOTS = (
    _WETMAP, _RECSYS_FIXMASK, _RECSYS_PROTECT, _RECSYS_ADDMASK,
    _FIXBLOODMASK, _BLOODSHED_RTT,
    _LIGHTDAMAGE_ALBD, _BURNTMAP_ALBM, _LIGHTDAMAGE_NRRA, _BURNTMAP_NRMR,
    _HEAVYDAMAGE_ALBD, _HEAVYDAMAGE_NRRA, _BLOOD_NRRA, _RECSYS_RTT,
    _RAINDROP_STOP, _RAINDROP_FLICK, _RAINDROP_MASK,
)

# Shared by Standard/Skin.
_DETAILMASK      = _inert("DetailMask", default_color=(0.0, 0.0, 0.0, 1.0))
_DETAILALBEDO    = _inert("DetailAlbedoMap", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_DETAILMAP       = _inert("DetailMap", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)

# Standard-only.
_IMPERFECTDETAIL = _inert("ImperfectDetail_Map", default_color=(0.5, 0.5, 0.5, 1.0), non_color=False)
_WRINKLEMAP      = _inert("WrinkleMap", default_color=(0.5, 0.5, 1.0, 1.0))

# Skin-only.
_SWEATMAP        = _inert("SweatMap")

# Hair-only.
_SECONDARY_MASK  = _inert("SecondaryBaseColorMap_MaskMap")
_SECONDARY_BASE  = _inert("SecondaryBaseColorMap", non_color=False)
_SPECULAR_FLOW   = _inert("Specular_FlowMap", default_color=(0.5, 0.5, 1.0, 1.0))
_RIMLIGHT_FAKENRM = _inert("RimLight_FakeNormalMap", default_color=(0.5, 0.5, 1.0, 1.0))
_DIRTMASKMAP     = _inert("DirtMaskMap")
_DIRTWEARMAP     = _inert("DirtWearMap")

SLOTS_STANDARD = (
    _ALBD, _NRM, _ACOT,
) + _RECORD_SYSTEM_SLOTS + (
    _DETAILMASK, _DETAILALBEDO, _DETAILMAP, _IMPERFECTDETAIL, _WRINKLEMAP,
)

SLOTS_SKIN = (
    _ALBD, _NRM, _SSSCOT,
) + _RECORD_SYSTEM_SLOTS + (
    _DETAILMASK, _DETAILALBEDO, _DETAILMAP, _SWEATMAP,
)

SLOTS_HAIR = (
    _BASESHIFT, _NRM, _ACOT,
) + _RECORD_SYSTEM_SLOTS + (
    _SECONDARY_MASK, _SECONDARY_BASE, _SPECULAR_FLOW, _RIMLIGHT_FAKENRM,
    _DIRTMASKMAP, _DIRTWEARMAP,
)

SLOTS_EMISSIVE = (_ALBD, _NRCM, _ATOSSS, _OCC, _EMISSIVE)

# ── Scattered PBR inputs (shared by all four specs) ─────────────────────────

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
    # (AlphaCavityOcclusionTranslucentMap.B / SSSCavityOcclusionTranslucentMap.B
    # / OcclusionMap), unlike MHWI, which needs the strength knob because it
    # has no AO slot at all.
    PBRSocket("AO", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_ao", pbr_type='ao'),
    # 1-neutral (multiplicative), same as AO/Roughness. Standard/Hair's
    # AlphaCavityOcclusionTranslucentMap.G, Skin's
    # SSSCavityOcclusionTranslucentMap.G, and Emissive's
    # NormalRoughnessCavityMap.B all genuinely carry cavity data; all feed
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
    # AlphaCavityOcclusionTranslucentMap.A and Emissive's
    # AlphaTranslucentOcclusionSSSMap.G both genuinely carry translucency
    # data, but Principled has no matching input (not the same thing as
    # Subsurface Scattering, which needs radius data this module does not
    # have) -- same treatment MHWI gives RMTMap's blue channel: the socket
    # exists so the value round-trips to the exporter, the preview does not
    # attempt to show it. Skin's SSSCavityOcclusionTranslucentMap has no
    # translucency channel, so this is the only source there.
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
    """Standard/Skin/Hair: NormalRoughnessMap's R/G is a *plain* 2-channel
    normal (B unused, unlike NormalRoughnessCavityMap below), summed with
    the loose PBR panel's own deviation and reconstructed once. Roughness
    comes from the slot's alpha channel."""
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


def _wire_standard_or_hair(b, base_slot_name):
    """Standard and Hair share everything except their base-colour slot and
    whether Metallic has a slot source."""
    b.column(1)
    base = b.mix('MULTIPLY', b.inp(base_slot_name), b.inp('Base Color'))
    acot_sep = b.separate(b.inp('AlphaCavityOcclusionTranslucentMap'), col=1, row=1)

    alpha = b.math('MULTIPLY', acot_sep.outputs[0], b.inp('Alpha'),
                   clamp=True, col=2, row=3)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    cavity = b.math('MULTIPLY', acot_sep.outputs[1], b.inp('Cavity'), clamp=True, col=2, row=5)

    ao_slot = b.mix('MULTIPLY', acot_sep.outputs[2], b.inp('AO'), col=2, row=1)
    ao_final = b.mix('MULTIPLY', ao_slot.outputs['Color'], cavity.outputs['Value'], col=3, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao_final.outputs['Color'], col=4, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    if base_slot_name == 'BaseDielectricMap':
        albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                            clamp=True, col=1, row=4)
        metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                       clamp=True, col=2, row=4)
        b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))
    else:
        # Hair: no metallic slot at all -- Property List has no Metallic
        # property, so the panel is the only source (same as RE4's hair spec).
        b.link(b.inp('Metallic'), b.bsdf_in('Metallic'))

    _wire_normal_roughness_plain(b, row=6)

    b.link(b.inp('Emission'), b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


def _wire_standard(b):
    _wire_standard_or_hair(b, 'BaseDielectricMap')


def _wire_hair(b):
    _wire_standard_or_hair(b, 'BaseShiftMap')


def _wire_skin(b):
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('BaseDielectricMap'), b.inp('Base Color'))

    # SSSCavityOcclusionTranslucentMap has no real opacity channel (see
    # module docstring) -- only cavity (G) and AO (B).
    ssscot_sep = b.separate(b.inp('SSSCavityOcclusionTranslucentMap'), col=1, row=1)
    cavity = b.math('MULTIPLY', ssscot_sep.outputs[1], b.inp('Cavity'), clamp=True, col=2, row=5)

    ao_slot = b.mix('MULTIPLY', ssscot_sep.outputs[2], b.inp('AO'), col=2, row=1)
    ao_final = b.mix('MULTIPLY', ao_slot.outputs['Color'], cavity.outputs['Value'], col=3, row=1)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao_final.outputs['Color'], col=4, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    b.link(b.inp('Alpha'), b.bsdf_in('Alpha'))

    albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                        clamp=True, col=1, row=4)
    metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                   clamp=True, col=2, row=4)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))

    _wire_normal_roughness_plain(b, row=6)

    b.link(b.inp('Emission'), b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


_COS45 = math.cos(math.radians(45.0))
_SIN45 = math.sin(math.radians(45.0))


def _octahedral_real(b, green, alpha, row):
    """RE Engine's 3-in-1 normal slot (NormalRoughnessCavityMap here; also
    MHWS's NormalRoughnessOcclusionMap, RE4's NormalRoughnessCavityMap):
    decode a packed (green, alpha) pair (0..1) into real tangent-space
    (x, y) in -1..1. Node-for-node copy of games/re4/shader_defs.py's
    _octahedral_real (see that module and core/re_normal_pack.decode_normal_ga
    for why the transform looks like this)."""
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
    """Emissive: NormalRoughnessCavityMap's G/A is hemi-octahedral (its B is
    a constant per RE9's override, but the G/A encoding scheme is a property
    of the slot type). Roughness comes from R, unlike Standard/Skin/Hair's
    alpha-channel roughness."""
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

    # Two genuine AO sources here -- OcclusionMap and
    # AlphaTranslucentOcclusionSSSMap.B -- multiplied together the same way
    # RE4's Emissive spec (and MHWS's NRRO/ATOS pair) combines two real AO
    # sources. Cavity comes from a third source, NormalRoughnessCavityMap.B --
    # a second, independent separate() of that slot alongside the one
    # _wire_normal_roughness_oct does below for its normal/roughness channels.
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
    group_name    = "MTK RE9 Standard",
    shader_id     = "re9_standard_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_standard",
    pbr           = PBR,
    slots         = SLOTS_STANDARD,
    wire          = _wire_standard,
    preset_filename = "standard.json",
)

SPEC_SKIN = ShaderPackSpec(
    group_name    = "MTK RE9 Skin",
    shader_id     = "re9_skin_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_skin",
    pbr           = PBR,
    slots         = SLOTS_SKIN,
    wire          = _wire_skin,
    preset_filename = "skin.json",
)

SPEC_HAIR = ShaderPackSpec(
    group_name    = "MTK RE9 Hair",
    shader_id     = "re9_hair_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_hair",
    pbr           = PBR,
    slots         = SLOTS_HAIR,
    wire          = _wire_hair,
    preset_filename = "hair.json",
)

SPEC_EMISSIVE = ShaderPackSpec(
    group_name    = "MTK RE9 Emissive",
    shader_id     = "re9_emissive_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots_emissive",
    pbr           = PBR,
    slots         = SLOTS_EMISSIVE,
    wire          = _wire_emissive,
    preset_filename = "emissive.json",
)

#: Registry for core/shader_ops.py -- one "game" ident per archetype.
VARIANTS = {
    'RE9_STANDARD': SPEC_STANDARD,
    'RE9_SKIN':     SPEC_SKIN,
    'RE9_HAIR':     SPEC_HAIR,
    'RE9_EMISSIVE': SPEC_EMISSIVE,
}
