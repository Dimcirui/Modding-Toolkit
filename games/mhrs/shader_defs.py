"""MHRS (MDF2) packed shader spec — one general-purpose "Standard" archetype.

Built from the real RE Mesh Editor preset RE-Mesh-Editor/Presets/MHRSB/
Standard.json (provided directly by the user, who noted this is essentially
the only material MHRS modding uses in practice — there is no cloth/skin/
hair split to make here the way MHWS/RE4/RE9 need). Its Master Material Path
is MasterMaterial/Master/Obj/NPC/PL_NPC_mmtrv/PL_Default.mmtr.

games/mhrs/mdf_tex_processor.py's own MHRS_SLOT_CHANNEL_MAPS is *exactly*
BASE_SLOT_CHANNEL_MAPS with no overrides at all -- simpler than every other
game this addon supports:

  * BaseDielectricMap -- RGB colour, A inverted metallic. Same isDielectric
    convention as MHWS/RE4.
  * NRMR_NRRTMap -- BASE_SLOT_CHANNEL_MAPS documents this as "MHRS -- same
    layout as NormalRoughnessMap": R/G plain tangent-space normal, B unused,
    A roughness. Decodes the plain way, same as RE4 Standard's
    NormalRoughnessMap -- no hemi-octahedral transform needed.
  * EmissiveMap -- emissive colour. Standard.json's own Property List
    (S_col_R/S_col_G two-tone colourisation, Emissive_intensity,
    Rim_Emissive_*) confirms this material genuinely uses it, unlike RE4's
    Standard/Hair.

No AO-carrying slot at all in this preset -- no Occlusion*/Cavity*/ATOS-style
binding anywhere in its Texture Bindings, and no Occlusion/Cavity property
in its Property List either. AO is therefore panel-only here (multiplied
straight into base colour, same treatment MHWI gives AO for the same
reason: nowhere to write it back).

AlphaMap has no PBR composition recipe in BASE_SLOT_CHANNEL_MAPS (confirmed:
'AlphaMap' is not a key there at all), even though the null default
(NullMSK1.tex, an explicit MHRSB-specific override in
games/mhrs/mdf_tex_processor.py's MHRS_NULL_TEX_BY_TYPE) and the Nuki/
Nuki_Dissolve properties suggest it drives an alpha-test cutout. Marking it
as supplying 'alpha' anyway would be wrong: apply_ir would then skip filling
the PBR Alpha panel from a read material, and on export nothing actually
composes that slot's image into the 'alpha' PBR type, so the value would
silently be lost. Left as a no-recipe, carried-through slot instead --
same treatment as UserColorchangeMap/FurVelocityMap/FxMap/FurTex.
"""

from ...core.shader_pack import (
    ShaderPackSpec, SlotSocket, PBRSocket, ALPHA_SUFFIX,
)

_K = "mhrs.shader_defs."

_ALBD = SlotSocket("BaseDielectricMap", _K + "albd",
                   default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('color', 'metallic'), non_color=False)

_NRMR = SlotSocket("NRMR_NRRTMap", _K + "nrmr",
                   default_color=(0.5, 0.5, 1.0, 1.0), alpha=True, default_alpha=1.0,
                   supplies=('normal', 'roughness'))

_EMISSIVE = SlotSocket("EmissiveMap", _K + "emissive",
                       default_color=(0.0, 0.0, 0.0, 1.0), alpha=True, default_alpha=1.0,
                       supplies=('emissive',), non_color=False)

# ── Secondary slots: no PBR recipe, carried through untouched ──────────────

def _inert(name, default_color=(1.0, 1.0, 1.0, 1.0), non_color=True):
    return SlotSocket(name, _K + name.lower(), default_color=default_color,
                      non_color=non_color, display=False)

_ALPHAMAP        = _inert("AlphaMap")
_USERCOLORCHANGE = _inert("UserColorchangeMap", default_color=(0.0, 0.0, 0.0, 1.0))
_FURVELOCITY     = _inert("FurVelocityMap")
_FXMAP           = _inert("FxMap", default_color=(0.0, 0.0, 0.0, 1.0))
_FURTEX          = _inert("FurTex", default_color=(0.0, 0.0, 0.0, 1.0))

SLOTS = (
    _ALBD, _NRMR, _EMISSIVE,
    _ALPHAMAP, _USERCOLORCHANGE, _FURVELOCITY, _FXMAP, _FURTEX,
)

# ── Scattered PBR inputs ─────────────────────────────────────────────────────

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
    PBRSocket("Normal", 'NodeSocketColor', (0.5, 0.5, 1.0, 1.0),
              _K + "pbr_normal", pbr_type='normal'),
)

_FLAT = 0.5


def _normal_deviation(b, socket, row):
    sep = b.separate(socket, col=1, row=row)
    dr = b.math('SUBTRACT', sep.outputs[0], _FLAT, col=2, row=row)
    dg = b.math('SUBTRACT', sep.outputs[1], _FLAT, col=2, row=row + 1)
    return dr.outputs['Value'], dg.outputs['Value']


def _wire(b):
    b.column(1)

    # No AO-carrying slot -- panel AO multiplies straight into base colour,
    # same as MHWI (there is nowhere to write it back either).
    ao = b.mix('MIX', (1.0, 1.0, 1.0, 1.0), b.inp('AO'),
              fac=b.inp('AO Strength'), col=2, row=1)
    base = b.mix('MULTIPLY', b.inp('BaseDielectricMap'), b.inp('Base Color'), col=1, row=0)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao.outputs['Color'], col=3, row=0)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    # No slot carries real opacity either -- see module docstring for why
    # AlphaMap does not qualify. Panel is the only source.
    b.link(b.inp('Alpha'), b.bsdf_in('Alpha'))

    albd_metal = b.math('SUBTRACT', 1.0, b.inp('BaseDielectricMap' + ALPHA_SUFFIX),
                        clamp=True, col=1, row=4)
    metal = b.math('ADD', albd_metal.outputs['Value'], b.inp('Metallic'),
                   clamp=True, col=2, row=4)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))

    # NRMR_NRRTMap: plain 2-channel normal (R/G), roughness from A -- same
    # layout and decode as RE4 Standard's NormalRoughnessMap.
    nrmr_sep = b.separate(b.inp('NRMR_NRRTMap'), col=1, row=6)
    slot_dr = b.math('SUBTRACT', nrmr_sep.outputs[0], _FLAT, col=2, row=6)
    slot_dg = b.math('SUBTRACT', nrmr_sep.outputs[1], _FLAT, col=2, row=7)
    pbr_dr, pbr_dg = _normal_deviation(b, b.inp('Normal'), row=9)

    sum_r = b.math('ADD', slot_dr.outputs['Value'], pbr_dr, col=3, row=6)
    sum_g = b.math('ADD', slot_dg.outputs['Value'], pbr_dg, col=3, row=7)
    r = b.math('ADD', sum_r.outputs['Value'], _FLAT, col=4, row=6)
    g = b.math('ADD', sum_g.outputs['Value'], _FLAT, col=4, row=7)

    x = b.math('MULTIPLY_ADD', r.outputs['Value'], 2.0, col=5, row=6)
    x.inputs[2].default_value = -1.0
    y = b.math('MULTIPLY_ADD', g.outputs['Value'], 2.0, col=5, row=7)
    y.inputs[2].default_value = -1.0
    xx = b.math('MULTIPLY', x.outputs['Value'], x.outputs['Value'], col=6, row=6)
    yy = b.math('MULTIPLY', y.outputs['Value'], y.outputs['Value'], col=6, row=7)
    xxyy = b.math('ADD', xx.outputs['Value'], yy.outputs['Value'], col=7, row=6)
    zsq = b.math('SUBTRACT', 1.0, xxyy.outputs['Value'], clamp=True, col=8, row=6)
    z = b.math('SQRT', zsq.outputs['Value'], col=9, row=6)
    zenc = b.math('MULTIPLY_ADD', z.outputs['Value'], 0.5, col=10, row=6)
    zenc.inputs[2].default_value = 0.5

    ncomb = b.combine(r.outputs['Value'], g.outputs['Value'],
                      zenc.outputs['Value'], col=11, row=6)
    nmap = b.node('ShaderNodeNormalMap', col=12, row=6)
    nmap.inputs['Strength'].default_value = 1.0
    b.link(ncomb.outputs[0], nmap.inputs['Color'])
    b.link(nmap.outputs['Normal'], b.bsdf_in('Normal'))

    rough = b.math('MULTIPLY', b.inp('NRMR_NRRTMap' + ALPHA_SUFFIX),
                   b.inp('Roughness'), clamp=True, col=1, row=11)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))

    emi = b.mix('ADD', b.inp('EmissiveMap'), b.inp('Emission'), col=1, row=14)
    b.link(emi.outputs['Color'], b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))


SPEC = ShaderPackSpec(
    group_name    = "MTK MHRS Standard",
    shader_id     = "mhrs_standard_v1",
    pbr_panel_key = _K + "panel_pbr",
    slot_panel_key= _K + "panel_slots",
    pbr           = PBR,
    slots         = SLOTS,
    wire          = _wire,
)
