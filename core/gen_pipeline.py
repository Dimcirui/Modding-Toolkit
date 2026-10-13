"""Carrying out a generator plan: one material's slots written to disk.

core/gen_slot_plan.py decides what each slot gets; this writes it. Shared by
the RE generator (core/mdf_generator_base.py) and MHWI's
(games/mhwi/mrl3_generator.py), which used to carry their own copies of every
write block. Game differences come in as arguments -- how a slot's file is
named on disk and in the material, which slots are sRGB, how a composition is
parametrised, what the null for a slot is -- never as branches here.

No bpy: everything that touches Blender or texconv is passed in.
"""

import os


class SlotWriter:
    """Source image -> .tex on disk -> the binding the material stores.

    disk_path(slot)  -> absolute path of the slot's .tex
    binding(slot)    -> what the material's binding gets (MDF path / MRL3 value)
    write_tex        -> slot_resolver.write_slot_tex
    dds_to_tex(p, o) -> the game's DDS -> .tex converter
    """

    def __init__(self, *, cache, temp_dir, disk_path, binding, srgb_slots,
                 write_tex, resolve_format, image_to_dds, dds_to_tex,
                 mipmaps, grade_mode, log_tag, mip_quality=None):
        self.cache = cache
        self.temp_dir = temp_dir
        self.disk_path = disk_path
        self.binding = binding
        self.srgb_slots = srgb_slots
        self._write_tex = write_tex
        self._resolve_format = resolve_format
        self.image_to_dds = image_to_dds
        self.dds_to_tex = dds_to_tex
        self.mipmaps = mipmaps
        self.grade_mode = grade_mode
        self.log_tag = log_tag
        # None = the writer's own default (texconv's Fast mips); the processor
        # and, since 2026-10-13, the generator pass the user's choice.
        self.mip_quality = mip_quality

    #: Whether the encode settings are part of every cache key. Two materials
    #: with the same inputs but mipmaps on/off (or a different mip quality)
    #: must not share one texture; until 2026-10-13 the generator let the
    #: second inherit the first's. Only tests switch this off, to compare
    #: against the old behaviour.
    _encode_in_key = True

    def _key(self, key):
        if key is None or not self._encode_in_key:
            return key
        return (key, ('encode', self.mipmaps, self.mip_quality, self.grade_mode))

    def cached(self, key):
        return self.cache.get(self._key(key)) if key is not None else None

    def write(self, slot_type, src, cache_key=None, note=""):
        """Write ``src`` as the slot's texture; returns (binding, src)."""
        disk = self.disk_path(slot_type)
        extra = {} if self.mip_quality is None else {"mip_quality": self.mip_quality}
        self._write_tex(
            src, disk, self.temp_dir,
            dds_fmt=self._resolve_format(slot_type, self.srgb_slots),
            generate_mipmaps=self.mipmaps,
            image_to_dds=self.image_to_dds,
            dds_to_tex=self.dds_to_tex,
            grade_mode=self.grade_mode,
            **extra,
        )
        binding = self.binding(slot_type)
        if cache_key is not None:
            self.cache[self._key(cache_key)] = (src, disk, binding)
        if note is not None:
            print(f"[{self.log_tag}]   {slot_type} -> {os.path.basename(disk)}"
                  + (f" ({note})" if note else ""))
        return binding, src


def composition_cache_key(slot_type, channel_maps, strategies, pbr_channels, source_id):
    """The key a composed/solid slot is cached under, or None when one of its
    inputs cannot be cached (a bake: its file is only valid for this material)."""
    ch_map = channel_maps[slot_type]
    needed = {src[0] for src in ch_map.values() if src is not None and isinstance(src, tuple)}
    parts = []
    for pt in sorted(needed):
        sv = strategies.get(pt)
        sid = source_id(sv) if sv else None
        if sid is None:
            return None
        parts.append((pt, sid))
    ch_ov = frozenset((k, v) for k, v in pbr_channels.items() if k in needed)
    return (slot_type, tuple(parts), ch_ov)


def execute_plan(plan, slot_types, writer, *, channel_maps, strategies, pbr_channels,
                 slot_direct, compose, solid, stage, null_for, source_id,
                 placeholder=None, placeholder_fallback=None,
                 emissive_slots=(), albedo_slots=(), use_toon=False):
    """Write every slot of ``plan``.

    compose(slot)         -> composed image path, or None (nothing to compose)
    solid(rgba, hint)     -> a solid image path, or None
    stage(src, slot)      -> the source copied under a slot-unique name
    null_for(slot)        -> the slot's null, or "" / None
    placeholder(slot)     -> a written placeholder's binding, or None
    placeholder_fallback  -> {slot: binding} when the placeholder is not written

    Returns ({slot: binding}, {slot: source file}) -- a slot missing from the
    first keeps the preset's binding.
    """
    bindings, files = {}, {}
    for slot_type in slot_types:
        p = plan[slot_type]
        if p.kind in ('TOON', 'KEEP'):
            continue                        # TOON is filled from the albedo below
        if p.kind == 'NULL':
            bindings[slot_type] = p.detail
            if p.sources:
                print(f"[{writer.log_tag}]   {slot_type} -> NULL (all-default)")
            continue
        if p.kind == 'PATH':
            bindings[slot_type] = writer.binding(slot_type)
            continue

        if p.kind == 'DIRECT':
            # Lossless: the file goes to the slot as-is, no unpack -> recompose.
            key = (slot_type, 'DIRECT_SLOT', p.detail)
            hit = writer.cached(key)
            if hit is not None:
                bindings[slot_type], files[slot_type] = hit[2], hit[0]
                continue
            auth = slot_direct.get(slot_type, (None, None))[1]
            bindings[slot_type], files[slot_type] = writer.write(
                slot_type, stage(p.detail, slot_type), key, note=f"槽位直连/{auth}")
            continue

        if p.kind == 'PLACEHOLDER':
            # The placeholder is the intended default here, a null only the
            # fallback when it cannot be written (no mod root).
            path = placeholder(slot_type) if placeholder else None
            if path:
                bindings[slot_type] = path
                print(f"[{writer.log_tag}]   {slot_type} -> {os.path.basename(path)} (占位贴图)")
            else:
                bindings[slot_type] = placeholder_fallback[slot_type]
            continue

        # SOLID / COMPOSE
        key = composition_cache_key(slot_type, channel_maps, strategies, pbr_channels, source_id)
        hit = writer.cached(key)
        if hit is not None:
            bindings[slot_type], files[slot_type] = hit[2], hit[0]
            continue
        if p.kind == 'SOLID':
            src = solid(p.detail, f"_{slot_type.lower()}_dg")
            if src:
                bindings[slot_type], files[slot_type] = writer.write(slot_type, src, key, note=None)
                continue
            # A solid that could not be saved falls through to composition.
        src = compose(slot_type)
        if src:
            bindings[slot_type], files[slot_type] = writer.write(slot_type, src, key)
        else:
            null = null_for(slot_type)
            if null:
                bindings[slot_type] = null

    # Toon shading: every emissive slot takes the albedo's binding.
    if use_toon and emissive_slots:
        albedo = next((bindings[st] for st in albedo_slots if st in bindings), None)
        for st in emissive_slots:
            if albedo:
                bindings[st] = albedo
            else:
                null = null_for(st)
                if null:
                    bindings[st] = null
    return bindings, files
