"""What the game's null textures actually contain -- measured, not assumed.

The generator replaces a slot whose inputs are all constants with the slot's
null texture, saving a texture, but only when the null holds that very pixel
(core/gen_slot_plan.py). This is the table it checks against. A null that is
not listed here is never substituted: the solid is written instead, which is
always correct, just one texture more.

RE values: first BC block of each systems/rendering/Null*.tex, MHWS and RE9
agree (2026-10-12; also in the comment above SHARED_NULL_TEX_BY_TYPE in
core/mdf_tex_processor_base.py). MHWI values: MHW Model Editor's
Assets/default_tex/null_*.tex from the installed addon (2026-10-13) --
null_black is RGBA8, null_NM BC5 (RG only; B samples 0, A 1), null_RMT BC1.

NullGray is left out on purpose: it is 0.5 *linear*, and a solid written for
an sRGB slot stores 0.5 in sRGB, which is a different value -- a match on the
number would be a false one. Every value below is 0, 1, or a 0.5 in a
non-colour slot, where the encoding question does not arise.
"""

NULL_PIXELS = {
    # RE Engine (MHWS / MHRS / RE4 / RE9 share these paths)
    'systems/rendering/nullblack':                    (0.0, 0.0, 0.0, 1.0),
    'systems/rendering/nullwhite':                    (1.0, 1.0, 1.0, 1.0),
    'systems/rendering/nullatos':                     (1.0, 0.0, 1.0, 1.0),
    'systems/rendering/nullnormalroughness':          (0.5, 0.5, 1.0, 0.5),
    'systems/rendering/nullnormalroughnessocclusion': (0.5, 0.5, 1.0, 0.5),
    'systems/rendering/nullnormal':                   (0.5, 0.5, 1.0, 0.0),
    'systems/rendering/nullblack_alpha_msk4':         (0.0, 0.0, 0.0, 0.0),
    # MHWI (MRL3 values are written without the .tex extension)
    'assets/default_tex/null_black':                  (0.0, 0.0, 0.0, 1.0),
    'assets/default_tex/null_nm':                     (0.5, 0.5, 0.0, 1.0),
    'assets/default_tex/null_rmt':                    (1.0, 0.0, 1.0, 1.0),
}


def null_pixel(path):
    """The measured RGBA of a null texture path, or None when not measured."""
    if not path:
        return None
    key = path.replace("\\", "/").lower()
    if key.endswith(".tex"):
        key = key[:-4]
    return NULL_PIXELS.get(key)
