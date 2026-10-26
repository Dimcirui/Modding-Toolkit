"""Optional editors batch import / export go through: REE JCNS Editor (.jcns) and
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

#: slot -> (operator category, export operator, import operator, collection ~TYPE).
EDITORS = {
    "jcns": ("jcns", "export_file", "import_file", "RE_JCNS_COLLECTION"),
    "gpuc": ("ree_gpuc", "export_file", "import_file", "RE_GPUC_COLLECTION"),
}

#: wd_api.API_VERSION this module is written against.
API_VERSION = 1

_api_cache = {}


def available(slot):
    """True while the editor for *slot* is installed and enabled (it can export)."""
    cat, op, _imp, _type = EDITORS[slot]
    return op_available(cat, op)


def available_slots():
    """The optional slots usable right now, in EDITORS order."""
    return [slot for slot in EDITORS if available(slot)]


def import_available(slot):
    cat, _exp, op, _type = EDITORS[slot]
    return op_available(cat, op)


def import_slots():
    """The optional slots whose editor can import right now, in EDITORS order."""
    return [slot for slot in EDITORS if import_available(slot)]


def collection_type(slot):
    return EDITORS[slot][3]


# A part can ship several .jcns, told apart by what follows the model id in the
# name (``ch03_001_0012_HJ.jcns``): each is its own slot, "jcns:_HJ"; the
# unsuffixed one is plain "jcns".  Other slots are their file type.

def slot_type(slot):
    """The file type of a slot: "jcns" for "jcns:_HJ", else the slot itself."""
    return slot.split(":", 1)[0]


def slot_suffix(slot):
    return slot.split(":", 1)[1] if ":" in slot else ""


def jcns_slot(suffix):
    return f"jcns:{suffix}" if suffix else "jcns"


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


def import_file(slot, filepath, armature=None, mesh_collection=None):
    """Import *filepath* with the editor's own importer; returns the collection it made.

    *armature* (an armature object name) lets the JCNS importer resolve the file's
    bone hashes to names; *mesh_collection* is the RE Mesh Editor collection a GPUC
    cloth is rebuilt on.  Without one the cloth keeps the file's structure.  Raises
    when no collection of the editor's type came out.
    """
    before = set(bpy.data.collections)
    if slot == "jcns":
        kwargs = {"filepath": filepath}
        if armature:
            kwargs.update(resolve_hashes=True, target_armature_name=armature)
        else:
            kwargs.update(resolve_hashes=False)
        result = bpy.ops.jcns.import_file('EXEC_DEFAULT', **kwargs)
    else:
        result = bpy.ops.ree_gpuc.import_file(
            'EXEC_DEFAULT', filepath=filepath, import_mode="REBUILD" if mesh_collection else "KEEP",
            mesh_collection=mesh_collection or "")
    want = collection_type(slot)
    made = [c for c in bpy.data.collections if c not in before and c.get("~TYPE") == want]
    if not made:
        raise RuntimeError(f"{slot} importer returned {sorted(result)} and made no {want}")
    return made[0].name


def _version(filepath):
    return int(filepath.rsplit(".", 1)[1])


# Separate named functions, not lambdas: the scheme exporters cache an export by
# (function name, collection) and copy the file for a second path.
def do_export_jcns(filepath, collection_name):
    export("jcns", filepath, collection_name, _version(filepath))


def do_export_gpuc(filepath, collection_name):
    export("gpuc", filepath, collection_name, _version(filepath))


EXPORTERS = {"jcns": do_export_jcns, "gpuc": do_export_gpuc}


def _vanilla_table(game):
    from . import json_cache
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets", "vanilla_slots", f"{game}.json")
    return json_cache.load(path) or {}


def entry_slots(game, mesh_path, optional=None):
    """``[(slot, natives-relative path)]``: the .jcns / .gpuc the vanilla part of
    *mesh_path* ships (assets/vanilla_slots/<game>.json, built from the game's pak
    list by scripts/build_vanilla_slots.py), for the editors usable -- *optional*,
    default those that can export.  A jcns slot writes over that vanilla file."""
    if optional is None:
        optional = available_slots()
    if not mesh_path:
        return []
    stem = os.path.basename(mesh_path).split(".")[0].lower()
    files = _vanilla_table(game).get(stem, {})
    out = []
    if "jcns" in optional:
        out += [(jcns_slot(os.path.basename(p).split(".")[0][len(stem):]), p) for p in files.get("jcns", [])]
    if "gpuc" in optional:
        out += [("gpuc", p) for p in files.get("gpuc", [])]
    return out


def slot_label(slot):
    """"JCNS _hj" / "GPUC" -- a slot as the export dialogs title it."""
    suffix = slot_suffix(slot)
    return slot_type(slot).upper() + (f" {suffix}" if suffix else "")
