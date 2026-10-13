"""Which null/default texture a slot gets -- one rule for the generator, the
processor and the processor dialog's badges.

The hand-written tables (games/<game>/mdf_tex_processor.py) are one null per
slot type, and measuring every vanilla MHWS material showed that is not how the
game works: the default follows the *master material*, and for several slots
the hand table was simply wrong (DetailMaskMap's NullBlack has A = 1, which
switches detail set A on everywhere; vanilla uses NullBlack_Alpha_MSK4, A = 0).
assets/<game>/vanilla_slot_defaults.json (scripts/build_slot_survey.py) holds
what vanilla actually binds. Lookup order:

    0. a runtime resource (@... / .rtex render target) is never replaced -- a
       null in its place switches the effect off (RE9's CutSceneMirror.rtex)
    1. the current binding, if vanilla itself uses it as a default for this slot
       -- presets are vanilla materials, so their choice is the mmtr's design
    2. this master material's own vanilla default for the slot
    3. the slot's vanilla default across all materials
    4. the hand table -- games without survey data, and slots vanilla never nulls

Pure Python, no bpy: tests/test_slot_defaults.py pins it.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm(path):
    p = (path or "").replace("\\", "/").lower()
    return p[len("natives/stm/"):] if p.startswith("natives/stm/") else p


class SlotNulls:
    """Null lookup for one game. Also answers the two questions the old dict
    did -- ``slot_type in nulls`` and ``nulls.values()`` -- so code that only
    needs "does this slot have a null" / "is this path a null" can take it."""

    def __init__(self, hand_table, survey=None, vanilla_list=None):
        self.hand = dict(hand_table)
        self._vanilla_list = vanilla_list      # path of assets/<game>/vanilla_tex_paths.txt
        self._vanilla = None
        self.slots = (survey or {}).get("slots", {})
        self._seen = {t: {_norm(p) for p in e.get("seen", ())} for t, e in self.slots.items()}
        paths = {_norm(p) for p in self.hand.values()}
        for e in self.slots.values():
            if "default" in e:
                paths.add(_norm(e["default"]))
            paths.update(_norm(p) for p in e.get("by_mmtr", {}).values())
            paths.update(_norm(p) for p in e.get("seen", ()))
        self._null_paths = paths

    @classmethod
    def for_game(cls, game, hand_table):
        path = os.path.join(_ROOT, "assets", game, "vanilla_slot_defaults.json")
        survey = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                survey = json.load(f)
        return cls(hand_table, survey,
                   os.path.join(_ROOT, "assets", game, "vanilla_tex_paths.txt"))

    def null_for(self, slot_type, mmtr="", current=""):
        if self.is_runtime(current):
            return current
        entry = self.slots.get(slot_type)
        if entry:
            if current and _norm(current) in self._seen.get(slot_type, ()):
                return current
            override = entry.get("by_mmtr", {}).get((mmtr or "").lower())
            if override:
                return override
            if "default" in entry:
                return entry["default"]
        return self.hand.get(slot_type)

    def is_null(self, path):
        return _norm(path) in self._null_paths

    @staticmethod
    def is_runtime(path):
        p = _norm(path)
        return p.startswith("@") or p.endswith(".rtex")

    def is_vanilla(self, path):
        """A texture the game itself ships (False when the game has no list)."""
        if self._vanilla is None:
            self._vanilla = set()
            if self._vanilla_list and os.path.isfile(self._vanilla_list):
                with open(self._vanilla_list, encoding="utf-8") as f:
                    self._vanilla = {ln.strip().lower() for ln in f if ln.strip()}
        return _norm(path) in self._vanilla

    # dict-compatible surface for "has a null" / "every null path"
    def __contains__(self, slot_type):
        return "default" in self.slots.get(slot_type, {}) or slot_type in self.hand

    def get(self, slot_type, default=None):
        return self.null_for(slot_type) or default

    def values(self):
        return list(self._null_paths)
