"""Onimusha: Way of the Sword's texture conventions, for the cross-game material port.

ONI has no processor or generator of its own yet, so this is the whole of its
texture side: the table ``core/mdf_port_tex.py`` reads for a destination game.
Every value below was read off the vanilla game (pak extract, 2026-10-14):

* ``.tex.251111100``, **not** GDeflate-compressed -- the same version number as
  MHS3, but stored raw.  tex_file only compresses versions it lists, so nothing
  to do beyond not listing this one.
* Paths are MHWilds-shaped: ``natives/stm/art/...`` on disk, ``art/...`` in the
  mdf2.
* Same-named slots pack the same channels as MHWilds' (``BaseDielectricMap``,
  ``NormalRoughnessOcclusionMap`` -- checked on vanilla NRRO, R roughness, G/A
  normal, B AO).  What ONI adds is a split: alpha has a slot of its own.
"""

from ...core.mdf_tex_processor_base import BASE_SLOT_CHANNEL_MAPS, BASE_TEXTURE_TYPE_ABBREV

ONI_TEX_VERSION = 251111100

ONI_TEXTURE_TYPE_ABBREV = {
    **BASE_TEXTURE_TYPE_ABBREV,
    # Vanilla's own suffixes (ch001_00_00_cloth_top_mat_alp / _stcm).
    'AlphaMap': 'ALP',
    'SSSTranslucentCavityDetailMaskMap': 'STCM',
}

ONI_SLOT_CHANNEL_MAPS = {
    **BASE_SLOT_CHANNEL_MAPS,
    # BC4 in vanilla: one channel, read from R.
    'AlphaMap': {
        'R': ('alpha', 0),
        'G': ('alpha', 0),
        'B': ('alpha', 0),
        'A': 1.0,
    },
    # The slot name spells its layout, in channel order (user, 2026-10-14), and
    # vanilla agrees: a skin's B varies like cavity, a kimono's G like
    # translucency, cloth A like a detail mask.  A is written 0: no source game
    # has a detail mask to carry over, and 1 would switch the prefab's own
    # fabric detail normal on across a model that was never authored for it.
    'SSSTranslucentCavityDetailMaskMap': {
        'R': ('sss', 0),
        'G': ('translucency', 0),
        'B': ('cavity', 0),
        'A': 0.0,
    },
}

#: Destination slots fed by a source slot the family match already sent
#: elsewhere -- see mdf_port_tex.extra_feeds.  Sources in priority order: a hair
#: material's alpha is BaseAlphaMap's, not its ATOS's.
ONI_SLOT_EXTRA_FEEDS = {
    'AlphaMap': ('BaseAlphaMap', 'AlphaTranslucentOcclusionSSSMap'),
}


def register():
    from ...core.mdf_port_tex import register_game_tex_config
    register_game_tex_config(
        "ONI",
        abbrev_map=ONI_TEXTURE_TYPE_ABBREV,
        channel_maps=ONI_SLOT_CHANNEL_MAPS,
        tex_version=ONI_TEX_VERSION,
        use_art_prefix=True,
        path_fixed_prefix="",
        null_tex_by_type={},
        natives_root_key="oni_natives_root",
        # Target-only: the vanilla list is read for the *source* game.
        vanilla_asset_rel="",
        slot_extra_feeds=ONI_SLOT_EXTRA_FEEDS,
    )


def unregister():
    from ...core.mdf_port_tex import unregister_game_tex_config
    unregister_game_tex_config("ONI")
