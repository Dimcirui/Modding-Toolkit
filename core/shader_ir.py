"""Normalised material description — the pivot between readers and the group.

Every source a material can come from (Principled BSDF, an Emission shader,
MMDShaderDev, one of the upstream importers' flat trees) is read into this one
shape, and the packed shader group is filled from it.  That is what keeps
"support another source" to writing one reader, instead of another branch in the
group builder.

Deliberately holds Image **datablocks**, not file paths.  Paths are the
exporter's currency (core.slot_sources) but a datablock is what building an
Image Texture node needs, and a packed or generated image has no usable path
while still being perfectly renderable.
"""

from dataclasses import dataclass, field

# Source kinds, mirroring core.mdf_generator_base's SHADER_* constants plus the
# two flat-tree layouts the upstream importers produce.
SRC_PRINCIPLED = 'principled'
SRC_EMISSION   = 'emission'
SRC_MMD_DEV    = 'mmd_shader_dev'
SRC_FLAT_SLOTS = 'flat_slots'
SRC_EMPTY      = 'empty'


@dataclass(frozen=True)
class ImageRef:
    """An image, plus which channel of it was being used.

    ``channel`` is 'R' when the whole colour output was taken, 'A' for the alpha
    output, or 'G'/'B' when the source went through a Separate Color.  It is
    advisory: the packed group wires the image's Color output regardless, since
    the slot's own channel packing decides what each channel means.  Readers
    record it so a reader-level warning can say when a non-obvious channel was
    in play.
    """
    image: object
    channel: str = 'R'

    @property
    def name(self):
        return getattr(self.image, 'name', '<none>')


@dataclass
class MaterialIR:
    #: {slot_type: ImageRef} — packed game slots, ready for the group's slot panel
    slots: dict = field(default_factory=dict)
    #: {pbr_type: ImageRef | float | tuple} — scattered PBR quantities
    pbr: dict = field(default_factory=dict)
    #: {name: value} — scalars that map to group sockets but are not PBR
    #: quantities (emission strength, normal strength, ...)
    params: dict = field(default_factory=dict)
    #: which reader produced this
    source: str = SRC_EMPTY
    #: what could not be represented; surfaced to the user, never swallowed.
    #: Plain strings, because this ends up in a Blender custom property.
    warnings: list = field(default_factory=list)
    #: message -> the pbr_type it concerns, for warnings that are about one
    #: quantity.  Kept alongside rather than inside ``warnings`` so the latter
    #: stays a list of strings.
    _warn_subject: dict = field(default_factory=dict, repr=False)

    def warn(self, message, pbr_type=None):
        if message not in self.warnings:
            self.warnings.append(message)
        if pbr_type:
            self._warn_subject[message] = pbr_type

    def drop_warnings_for(self, pbr_types):
        """Forget warnings about quantities that turned out to be covered.

        A material imported by one of the upstream addons routinely has a normal
        built from several images *and* a NormalMap slot node.  The reader is
        right that it cannot reduce the chain, but the slot supplies the quantity
        anyway, so saying so would just be noise.
        """
        if not pbr_types:
            return self
        drop = {m for m, q in self._warn_subject.items() if q in pbr_types}
        if drop:
            self.warnings = [w for w in self.warnings if w not in drop]
            for m in drop:
                self._warn_subject.pop(m, None)
        return self

    def merge_slots(self, other):
        """Take ``other``'s slots, letting existing entries win.

        Used to layer a flat-tree read (authoritative, lossless) over a
        shader read without letting the latter overwrite it.
        """
        for k, v in other.slots.items():
            self.slots.setdefault(k, v)
        for w in other.warnings:
            self.warn(w)
        return self

    def is_empty(self):
        return not self.slots and not self.pbr

    def summary(self):
        parts = []
        if self.slots:
            parts.append(f"{len(self.slots)} slot(s): "
                         + ", ".join(sorted(self.slots)))
        img = [k for k, v in self.pbr.items() if isinstance(v, ImageRef)]
        const = [k for k, v in self.pbr.items() if not isinstance(v, ImageRef)]
        if img:
            parts.append(f"{len(img)} PBR image(s): " + ", ".join(sorted(img)))
        if const:
            parts.append(f"{len(const)} PBR constant(s)")
        return f"[{self.source}] " + ("; ".join(parts) or "nothing")
