"""Parsed JSON files, re-read only when they change on disk.

The batch export / import dialogs read their scheme and armour tables from
draw() and from enum callbacks, so a single redraw parsed the same file
several times -- MHWS's 154 KB armour pack about four times per redraw, with
the dialog redrawing on every mouse move.  Every caller treats the result as
read-only (checked when this was introduced); keep it that way, the object is
shared.
"""

import json
import os

_cache = {}


def load(path):
    """The parsed JSON at *path*, or None if it does not exist.

    Cached on (mtime, size), so an edit -- a scheme saved from another tool, an
    armour pack updated -- is picked up on the next call.  Invalid JSON raises,
    as json.load did.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = os.path.normcase(os.path.abspath(path))
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _cache.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[key] = (stamp, data)
    return data
