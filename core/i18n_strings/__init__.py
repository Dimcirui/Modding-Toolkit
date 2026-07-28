"""
core/i18n_strings/ — bilingual string tables, split by area.

Each sibling module exports a STRINGS dict: {key: {"EN": ..., "ZH": ...}}.
This __init__ merges them all into one flat STRINGS dict for core/i18n.py's
T() to look up. Key naming convention: "<area>.<purpose>", e.g.
"core.standard_ops.bone_visibility_all", "mhwi.batch_export.title".
"""

from . import meta
from . import core
from . import ui
from . import mhwi
from . import mhws
from . import mhrs
from . import re4
from . import re9

STRINGS = {}
for _mod in (meta, core, ui, mhwi, mhws, mhrs, re4, re9):
    STRINGS.update(_mod.STRINGS)
