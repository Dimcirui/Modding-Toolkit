"""Every vertex-group weight of a mesh as flat arrays, read once per check run.

The pre-export check asks the same per-vertex question in five places (the
weight, vertex-group and structure checks, auto-fix's plan, the physics
coverage).  Each used to walk ``vertex.groups`` through RNA on its own; that
walk is the expensive part, there is no ``foreach_get`` for it, and the five
of them made opening a batch export dialog visibly lag.

``cached()`` scopes one shared read: inside it ``entries()`` walks a mesh once
and every later call gets the same arrays.  Outside it nothing is kept, so code
that writes weights between reads (auto-fix's apply) always sees fresh data.
"""

from contextlib import contextmanager

import numpy as np

_CACHE = None


@contextmanager
def cached():
    """Share ``entries()`` across everything run inside.  Re-entrant: an inner
    ``cached()`` reuses the outer scope.  Only for read-only work."""
    global _CACHE
    if _CACHE is not None:
        yield
        return
    _CACHE = {}
    try:
        yield
    finally:
        _CACHE = None


def _read(me):
    verts, groups, weights = [], [], []
    av, ag, aw = verts.append, groups.append, weights.append
    for v in me.vertices:
        i = v.index
        for g in v.groups:
            av(i)
            ag(g.group)
            aw(g.weight)
    # float64: comparisons against Python-float thresholds then behave exactly
    # as they did on the per-vertex floats.
    return (np.array(verts, np.int64), np.array(groups, np.int64),
            np.array(weights, np.float64))


def entries(me):
    """``(vertex, group, weight)`` arrays, one row per weight entry, in
    ``vertex.groups`` order."""
    if _CACHE is None:
        return _read(me)
    key = me.as_pointer()
    hit = _CACHE.get(key)
    if hit is None:
        hit = _CACHE[key] = _read(me)
    return hit


def _rows(me, groups, min_weight):
    """Mask over ``entries(me)`` of the rows in *groups* (and at or above
    *min_weight*, unless None)."""
    v, g, w = entries(me)
    mask = np.isin(g, np.fromiter(groups, np.int64))
    if min_weight is not None:
        mask &= w >= min_weight
    return v, g, mask


def groups_with_weight(me, groups, min_weight=None):
    """The indices among *groups* that hold at least one vertex (at or above
    *min_weight*, unless None)."""
    _v, g, mask = _rows(me, groups, min_weight)
    return set(np.unique(g[mask]).tolist())


def vertices_without(me, groups, min_weight=None):
    """Sorted indices of the vertices with no entry in *groups* (at or above
    *min_weight*, unless None)."""
    v, _g, mask = _rows(me, groups, min_weight)
    has = np.zeros(len(me.vertices), bool)
    has[v[mask]] = True
    return np.flatnonzero(~has).tolist()
