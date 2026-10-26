"""Optional editors a batch export can write through: REE JCNS Editor (.jcns) and
RE GPUC Editor (.gpuc).

Unlike the mesh / chain editors these are never required.  A slot for one appears
only while its editor is installed (probed by its Export operator, the same
``dir(bpy.ops.<cat>)`` check every other guard uses); with neither installed a batch
export looks and behaves exactly as it did before they existed.

Both editors publish ``wd_api.export_bytes(collection, version)`` for other addons:
the file as bytes, built from the collection alone, nothing written, no scene
change.  That is used instead of their Export operators, which act on the active
JCNS root (and repoint it at the written file) or rely on ``invoke`` to fill in the
GPUC template -- neither fits a call from a batch loop.

The module is found by scanning the enabled addons for a ``wd_api.py`` whose
``COLLECTION_TYPES`` lists the slot's collection type, so the editor's install name
(extension id, legacy folder) does not matter.  When the operator is there but the
API is not, the export raises -- a visible failure, never a silent no-op.
"""

import importlib
import os
import sys

import bpy

from .compat import op_available

#: slot -> (operator category, operator name, collection ~TYPE).
EDITORS = {
    "jcns": ("jcns", "export_file", "RE_JCNS_COLLECTION"),
    "gpuc": ("ree_gpuc", "export_file", "RE_GPUC_COLLECTION"),
}

#: wd_api.API_VERSION this module is written against.
API_VERSION = 1

_api_cache = {}


def available(slot):
    """True while the editor for *slot* is installed and enabled."""
    cat, op, _type = EDITORS[slot]
    return op_available(cat, op)


def available_slots():
    """The optional slots usable right now, in EDITORS order."""
    return [slot for slot in EDITORS if available(slot)]


def collection_type(slot):
    return EDITORS[slot][2]


def _find_api(slot):
    mod = _api_cache.get(slot)
    if mod is not None and sys.modules.get(mod.__name__) is mod:
        return mod
    want = collection_type(slot)
    for name in bpy.context.preferences.addons.keys():
        pkg = sys.modules.get(name)
        path = getattr(pkg, "__file__", None)
        if not path or not os.path.isfile(os.path.join(os.path.dirname(path), "wd_api.py")):
            continue
        try:
            api = importlib.import_module(name + ".wd_api")
        except Exception:
            continue
        if want in getattr(api, "COLLECTION_TYPES", ()):
            _api_cache[slot] = api
            return api
    return None


def export(slot, filepath, collection_name, version):
    """Write *collection_name* through the editor's wd_api as *filepath*.

    Raises on anything that leaves the file unwritten; batch export counts an
    exception as a failed file.
    """
    api = _find_api(slot)
    if api is None:
        raise RuntimeError(f"{slot} editor is enabled but provides no wd_api with export_bytes")
    if getattr(api, "API_VERSION", None) != API_VERSION:
        raise RuntimeError(f"{slot} editor's wd_api is version {getattr(api, 'API_VERSION', None)}, "
                           f"expected {API_VERSION}")
    coll = bpy.data.collections.get(collection_name)
    if coll is None:
        raise RuntimeError(f"collection '{collection_name}' not found")
    data = api.export_bytes(coll, version)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)
