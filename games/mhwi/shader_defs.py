"""MHWI (MRL3) packed shader spec.

Slot set and channel packing follow mrl3_tex_processor.MHWI_MRL3_SLOT_DEFS and
MHWI_SLOT_CHANNEL_MAPS; the preview wiring follows MHW Model Editor's
mrl3_nodes.py so the viewport looks like what users already get on import.

Only 4 of MHWI's 7 slots have a PBR composition recipe.  The other three
(ColorMaskMap, FxMap, FurVelocityMap) are display-inert here — a colour mask
means nothing without the mrl3 material's CMM colour properties — but they get
sockets anyway, because carrying their images to the exporter is the point.

MHWI has no AO *slot*: MHWI_SLOT_CHANNEL_MAPS never references 'ao', and
RMTMap's blue channel is translucency, not occlusion.  The PBR panel still
offers AO, multiplied into base colour with a 0..1 strength — and that
multiply is not preview-only: mdf_generator_base.py auto-adopts whatever is
plugged into this socket (image + strength) and, since
channel_maps_consume_ao() sees MHWI's channel maps never reference 'ao',
bake_ao_into_color folds the same multiply into AlbedoMap's colour channels at
export time. So the data survives, just not as its own texture — there is
nowhere to write a standalone AO map for MHWI.  The RE-series specs will be
able to write theirs back losslessly instead, via NRRO.B.
"""

from ...core.shader_pack import (
    ShaderPackSpec, SlotSocket, PBRSocket, ALPHA_SUFFIX,
)

_K = "mhwi.shader_defs."

# non_color mirrors MHWI_SRGB_SLOT_TYPES = {'AlbedoMap', 'EmissiveMap'}:
# only those two are colour, everything else is packed data.

# ── Packed game slots ─────────────────────────────────────────────────────────
# Defaults are the *packed* neutral values, matching the game's own null
# textures (Assets\default_tex\null_NM, null_RMT, null_black).

# ``supplies`` mirrors MHWI_SLOT_CHANNEL_MAPS: the PBR quantities each slot
# already packs.  apply_ir uses it to avoid filling a slot and its PBR
# equivalent at once, which would apply the quantity twice.

SLOTS = (
    SlotSocket("AlbedoMap", _K + "albedo",
               default_color=(1.0, 1.0, 1.0, 1.0), alpha=True, default_alpha=1.0,
               supplies=('color', 'alpha'), non_color=False),
    SlotSocket("NormalMap", _K + "normal",
               default_color=(0.5, 0.5, 1.0, 1.0),
               supplies=('normal',)),
    # R roughness, G metallic, B translucency.  Fully rough / non-metal.
    SlotSocket("RMTMap", _K + "rmt",
               default_color=(1.0, 0.0, 0.0, 1.0),
               supplies=('roughness', 'metallic')),
    SlotSocket("EmissiveMap", "core.shader_pack.emissive",
               default_color=(0.0, 0.0, 0.0, 1.0), alpha=True, default_alpha=1.0,
               supplies=('emissive',), non_color=False),
    SlotSocket("ColorMaskMap", _K + "colormask",
               default_color=(0.0, 0.0, 0.0, 1.0), display=False),
    SlotSocket("FxMap", _K + "fx",
               default_color=(0.0, 0.0, 0.0, 1.0), display=False),
    SlotSocket("FurVelocityMap", _K + "furvelocity",
               default_color=(0.0, 0.0, 0.0, 1.0), display=False),
)

# ── Scattered PBR inputs ──────────────────────────────────────────────────────
# Defaults are the neutral element of each quantity's combiner, so that filling
# in only this panel gives exactly the typed value.

PBR = (
    # White, not Principled's 0.8 grey: this is multiplied with AlbedoMap, so
    # anything but the multiplicative identity darkens a slot-only material.
    # A node group cannot tell whether a socket is linked, so the two panels
    # always combine -- the identity is what makes "use only one" exact.
    PBRSocket("Base Color", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_base_color", pbr_type='color', non_color=False),
    PBRSocket("Alpha", 'NodeSocketFloat', 1.0, _K + "pbr_alpha",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='alpha'),
    PBRSocket("Roughness", 'NodeSocketFloat', 1.0, _K + "pbr_roughness",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='roughness'),
    PBRSocket("Metallic", 'NodeSocketFloat', 0.0, _K + "pbr_metallic",
              min_value=0.0, max_value=1.0, subtype='FACTOR', pbr_type='metallic'),
    # Ambient occlusion, multiplied into base colour.  MHWI has no AO slot to
    # write this back to, so it is preview-only here -- said so in the tooltip,
    # because an input that looks exportable and is not would be a trap.
    PBRSocket("AO", 'NodeSocketColor', (1.0, 1.0, 1.0, 1.0),
              _K + "pbr_ao", pbr_type='ao'),
    PBRSocket("AO Strength", 'NodeSocketFloat', 0.5, "core.shader_pack.pbr_ao_strength",
              min_value=0.0, max_value=1.0, subtype='FACTOR'),
    PBRSocket("Emission", 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0),
              _K + "pbr_emission", pbr_type='emissive', non_color=False),
    # Upstream clamps emission to [0, 9999] to keep negatives out of the BSDF.
    # Not a PBR quantity, so it is filled from ir.params instead.
    PBRSocket("Emission Strength", 'NodeSocketFloat', 1.0,
              "core.shader_pack.pbr_emission_strength", min_value=0.0, max_value=9999.0),
    # A *colour*, not a vector: you plug the NM texture straight in, with no
    # Normal Map node in between.  That is also what the readers hand over --
    # read_principled penetrates a Normal Map node and returns the image behind
    # it, which would be wrong to feed into a vector socket (no tangent-space
    # decode).  Default is flat, the identity for the deviation blend below.
    PBRSocket("Normal", 'NodeSocketColor', (0.5, 0.5, 1.0, 1.0),
              _K + "pbr_normal", pbr_type='normal'),
)


#: Tangent-space normal maps encode zero deviation as 0.5 in R and G.
_FLAT = 0.5


def _normal_deviation(b, socket, row):
    """(dR, dG) sockets: how far a normal-map colour bends from flat.

    Working in deviations is what makes the blend below have a proper identity:
    a flat map contributes exactly zero, so plugging in only one of the two
    normal inputs passes it through untouched.  Adding whole normal vectors and
    renormalising — which is what this used to do, following MHW Model Editor's
    detail-normal blend — instead pulls a real normal back toward flat.
    """
    sep = b.separate(socket, col=1, row=row)
    dr = b.math('SUBTRACT', sep.outputs[0], _FLAT, col=2, row=row)
    dg = b.math('SUBTRACT', sep.outputs[1], _FLAT, col=2, row=row + 1)
    return dr.outputs['Value'], dg.outputs['Value']


def _wire(b):
    # ── Albedo, with AO multiplied in ─────────────────────────────────────────
    # Slot colour x PBR colour. Both default to white, so an untouched node is
    # plain white and either panel alone gives exactly what was put in.
    b.column(1)
    base = b.mix('MULTIPLY', b.inp('AlbedoMap'), b.inp('Base Color'))

    # AO Strength lerps between white (no occlusion) and the AO map, so 0 is
    # genuinely "off" and 1 is the full map. Then plain multiply into base
    # colour, which is what "正片叠底" means here.
    ao = b.mix('MIX', (1.0, 1.0, 1.0, 1.0), b.inp('AO'),
               fac=b.inp('AO Strength'), col=2)
    shaded = b.mix('MULTIPLY', base.outputs['Color'], ao.outputs['Color'], col=3)
    b.link(shaded.outputs['Color'], b.bsdf_in('Base Color'))

    alpha = b.math('MULTIPLY', b.inp('AlbedoMap' + ALPHA_SUFFIX), b.inp('Alpha'),
                   clamp=True, col=1, row=1)
    b.link(alpha.outputs['Value'], b.bsdf_in('Alpha'))

    # ── Normal ────────────────────────────────────────────────────────────────
    # Both inputs are normal-map *colours*: the packed slot and the loose PBR
    # one.  Sum their deviations from flat, reconstruct blue, decode once.
    #
    # Separate/combine rather than an RGB-curve trick follows MHW Model Editor,
    # which settled on it because it behaves the same whether the source arrived
    # as dds, tga or png.
    slot_dr, slot_dg = _normal_deviation(b, b.inp('NormalMap'), row=2)
    pbr_dr,  pbr_dg  = _normal_deviation(b, b.inp('Normal'), row=4)

    sum_r = b.math('ADD', slot_dr, pbr_dr, col=3, row=2)
    sum_g = b.math('ADD', slot_dg, pbr_dg, col=3, row=3)
    r = b.math('ADD', sum_r.outputs['Value'], _FLAT, col=4, row=2)
    g = b.math('ADD', sum_g.outputs['Value'], _FLAT, col=4, row=3)

    # Blue: MRL3 normals are two-channel (BC5) and carry nothing usable there,
    # so it has to be reconstructed rather than passed through.  MHW Model Editor
    # forces it to 1.0 and then sets Strength 2.0 to compensate; forcing 1.0
    # means z is always maximal, which after the Normal Map node's internal
    # normalise leaves every normal flatter than it should be.
    #
    # Solving for it properly instead:  z = sqrt(1 - x^2 - y^2), where
    # x = 2R-1 and y = 2G-1.  Re-encoded as (z+1)/2 for the Normal Map node.
    # With a correct z there is nothing to compensate for, so Strength is 1.0.
    x = b.math('MULTIPLY_ADD', r.outputs['Value'], 2.0, col=5, row=2)
    x.inputs[2].default_value = -1.0
    y = b.math('MULTIPLY_ADD', g.outputs['Value'], 2.0, col=5, row=3)
    y.inputs[2].default_value = -1.0
    xx = b.math('MULTIPLY', x.outputs['Value'], x.outputs['Value'], col=6, row=2)
    yy = b.math('MULTIPLY', y.outputs['Value'], y.outputs['Value'], col=6, row=3)
    xxyy = b.math('ADD', xx.outputs['Value'], yy.outputs['Value'], col=7, row=2)
    # clamp keeps the argument non-negative when the summed deviations exceed
    # unit length, which two stacked normal maps can easily do
    zsq = b.math('SUBTRACT', 1.0, xxyy.outputs['Value'], clamp=True, col=8, row=2)
    z = b.math('SQRT', zsq.outputs['Value'], col=9, row=2)
    zenc = b.math('MULTIPLY_ADD', z.outputs['Value'], 0.5, col=10, row=2)
    zenc.inputs[2].default_value = 0.5

    ncomb = b.combine(r.outputs['Value'], g.outputs['Value'],
                      zenc.outputs['Value'], col=11, row=2)
    nmap  = b.node('ShaderNodeNormalMap', col=12, row=2)
    nmap.inputs['Strength'].default_value = 1.0
    b.link(ncomb.outputs[0], nmap.inputs['Color'])
    b.link(nmap.outputs['Normal'], b.bsdf_in('Normal'))

    # ── Roughness / metallic ──────────────────────────────────────────────────
    # Multiplying roughness by a scalar is what MRL3 itself does with
    # fRoughness__uiUNorm, so the combiner is faithful as well as convenient.
    # rows 2-5 are taken by the normal chain above
    rsep = b.separate(b.inp('RMTMap'), col=1, row=7)
    rough = b.math('MULTIPLY', rsep.outputs[0], b.inp('Roughness'),
                   clamp=True, col=2, row=7)
    b.link(rough.outputs['Value'], b.bsdf_in('Roughness'))
    metal = b.math('ADD', rsep.outputs[1], b.inp('Metallic'),
                   clamp=True, col=2, row=8)
    b.link(metal.outputs['Value'], b.bsdf_in('Metallic'))
    # RMTMap blue is translucency; Principled has no matching input and the
    # preview does not attempt one.  The socket still carries it for export.

    # ── Emission ──────────────────────────────────────────────────────────────
    emi = b.mix('ADD', b.inp('EmissiveMap'), b.inp('Emission'), col=1, row=10)
    b.link(emi.outputs['Color'], b.bsdf_in('Emission Color', 'Emission'))
    b.link(b.inp('Emission Strength'), b.bsdf_in('Emission Strength'))

    # ColorMaskMap / FxMap / FurVelocityMap are intentionally unwired — see the
    # module docstring.  An unconnected group input is harmless, and keeps the
    # image referenced so it survives to the exporter.


SPEC = ShaderPackSpec(
    group_name    = "MTK MHWI Standard",
    shader_id     = "mhwi_standard_v1",
    pbr_panel_key = "core.shader_pack.panel_pbr",
    slot_panel_key= "core.shader_pack.panel_slots",
    pbr           = PBR,
    slots         = SLOTS,
    wire          = _wire,
)
