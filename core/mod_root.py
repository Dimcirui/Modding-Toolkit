"""Mod root normalisation: turn whatever folder the user picked into the one
that *contains* ``natives``.

Every exporter builds ``<root>/natives/STM/...``, so a root picked one level too
deep (``.../natives`` or ``.../natives/STM``) silently writes a doubled
``natives/natives`` tree the game never reads.  Rules, from
``docs/pre_export_check_plan.md`` §3.10 (P = the picked folder):

1. P itself is named ``natives`` (any case) -> its parent
2. walking up at most ``UP`` levels, the first ancestor named ``natives`` -> its
   parent.  The first one met is the nearest, i.e. the deeper one when natives
   are nested, which is the one a user nesting them most likely means
3. searching down at most ``DOWN`` levels for folders named ``natives``: exactly
   one -> its parent; several on one path (nested) -> the deepest one's parent;
   several on different branches -> **no guess**, P is kept and the caller is
   told (``AMBIGUOUS``) so it can ask for a specific mod
4. nothing found -> P unchanged.  That is normal: a brand-new mod folder has no
   natives until its first export creates one.

Case (3) walks the disk, and the dialogs that show the root redraw constantly,
so results are cached per path.  A cache entry can go stale if the user creates
or deletes folders mid-session; re-picking the root clears it.
"""

import os

UP = 4
DOWN = 3

OK = 'ok'
AMBIGUOUS = 'ambiguous'

_cache = {}


def _is_natives(name):
    return name.lower() == 'natives'


def _find_down(root, depth):
    """Every ``natives`` folder under *root*, at most *depth* levels down.
    Does not descend into a found ``natives`` beyond the depth budget."""
    found = []
    frontier = [(root, 0)]
    while frontier:
        path, level = frontier.pop()
        if level >= depth:
            continue
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for e in entries:
            if not e.is_dir(follow_symlinks=False):
                continue
            if _is_natives(e.name):
                found.append(e.path)
            frontier.append((e.path, level + 1))
    return found


def normalize(path, use_cache=True):
    """``(root, status)`` for a picked folder; see the module docstring."""
    if not path:
        return path, OK
    key = os.path.normcase(os.path.abspath(path))
    if use_cache and key in _cache:
        return _cache[key]

    p = os.path.abspath(path).rstrip("/\\")
    result = (p, OK)
    if _is_natives(os.path.basename(p)):
        result = (os.path.dirname(p), OK)
    else:
        cur = p
        for _ in range(UP):
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            if _is_natives(os.path.basename(parent)):
                result = (os.path.dirname(parent), OK)
                break
            cur = parent
        if result == (p, OK) and os.path.isdir(p):
            found = _find_down(p, DOWN)
            if len(found) == 1:
                result = (os.path.dirname(found[0]), OK)
            elif found:
                deepest = max(found, key=lambda f: f.count(os.sep))
                nested = all(os.path.normcase(deepest).startswith(os.path.normcase(f) + os.sep)
                             or f == deepest for f in found)
                result = (os.path.dirname(deepest), OK) if nested else (p, AMBIGUOUS)

    _cache[key] = result
    return result


def clear_cache():
    _cache.clear()


def read(scene, key):
    """The stored root for *key*, normalised.  Old .blend files may hold a root
    saved before normalisation existed; reading through this fixes them without
    rewriting the file."""
    return normalize(scene.get(key, ""))[0]
