"""EnumProperty over a folder of files whose selection survives the folder changing.

A dynamic ``items=`` enum stores the selected item's *number*, and with plain
3-tuples the number is the item's position in the list.  So when the list is a
folder listing, adding a file shifts every selection that sorts after it:
measured on 5.1, an enum set to ``d.json`` read back as ``c.json`` after a
``c.json`` was inserted.  This bit the skeleton presets (v2.7 added
``dmc5_alt.json``: a .blend saved with Target = re4 reopened as dmc5_alt) and
the generator's per-material preset (save a new preset in RE Mesh Editor and
every entry after it in the alphabet generates the wrong material type, with
no error).

Explicit item numbers would fix new selections but orphan every one already
saved in a .blend, which holds the old position.  Instead the property gets
``get``/``set``: the chosen *identifier* is stored as a raw ID property next to
it, and the number is worked out from the current list on every read.  A
property never set through this path -- an old .blend -- still holds its old
raw position under its own name, and that is read exactly as before, so
nothing changes for existing files until the user next picks a value.

The ``items`` callback is called from ``get``, so it must hand back the same
list object while the folder is unchanged (which the callbacks in this addon
do anyway, for Blender's string-lifetime trap).
"""

import bpy


def stable_enum(attr, items, default_index=0, **kwargs):
    """``bpy.props.EnumProperty(items=items, **kwargs)`` storing the identifier.

    *attr* must be the annotation name the property is assigned to -- it is
    where an old .blend kept the raw position.  *default_index* is what reads
    back when nothing valid is stored (the stored file was deleted, say).
    """
    key = attr + "__id"

    def _ids(self):
        try:
            return [it[0] for it in items(self, bpy.context)]
        except Exception:
            return []

    def get(self):
        ids = _ids(self)
        sid = self.get(key)
        if isinstance(sid, str):
            try:
                return ids.index(sid)
            except ValueError:
                pass
        else:
            legacy = self.get(attr)
            if isinstance(legacy, int) and 0 <= legacy < len(ids):
                return legacy
        return default_index if default_index < len(ids) else 0

    def set(self, value):
        ids = _ids(self)
        if 0 <= value < len(ids):
            self[key] = ids[value]

    return bpy.props.EnumProperty(items=items, get=get, set=set, **kwargs)
