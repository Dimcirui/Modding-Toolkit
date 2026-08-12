"""Custom split normal tools for face meshes.

Why a cylinder
--------------
Reverse-engineering the shipped face meshes (MHWS `face`, MHWI `f_face002`)
shows the custom split normals are not the mesh's own smooth normals and not a
transfer from a modelled proxy head.  Over the frontal region they are, to
within one degree, the horizontal radial direction from the vertical axis
through the object's local origin — a mathematically exact cylinder.  Nose,
lips and eye sockets vanish from the shading entirely, which is the point: a
cylindrical field gives a purely left-right light falloff with no nose shadow,
and it stays stable when the head tilts.

Outside that region (ears, back of the skull, the neck cap) the mesh keeps its
own angle-weighted smooth normals bit-exact, and the mask is a hard per-face
selection with no feathering.  The front/side transition is not painted: it
falls out of averaging the two fields at the shared boundary vertices, weighted
by corner angle, which makes it exactly one vertex wide.  Reproducing a shipped
head this way lands at 0.57 degrees p90 across the skin.

The mask cannot be derived — an angle threshold, the vertex colour layers and a
frontal-cone isoline were all measured against the shipped meshes and all fail
(the isoline scores well per-loop but cuts across edge loops, so the boundary
comes out visibly jagged).  It has to be a face selection.

Welding
-------
Game meshes are split into separate vertices at UV and material borders, so
plain smooth shading leaves a normal seam wherever an edge loop was cut.
`weld_coincident_normals` averages those back together.  It only touches
positions where two *different* vertices coincide, so hard edges inside a
single vertex fan survive, and it clusters by direction first, so back-to-back
cards (eyelashes, brows — roughly 180 degrees apart) are not averaged into
garbage.
"""

import numpy as np


# ── mesh readback ──────────────────────────────────────────────────────────

def mesh_arrays(me):
    """(vertex coords, loop→vertex, poly loop_start, poly loop_total)."""
    nv, nl, npo = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npo, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npo, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return co.reshape(-1, 3).astype(np.float64), lv, ls, lt


def corner_normals(me):
    a = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", a)
    return a.reshape(-1, 3).astype(np.float64)


def corner_angles(co, lv, ls, lt):
    """Per-loop corner angle — the weight Blender and the DCCs use for vertex
    normals.  Everything here weights by angle, never by area: the shipped
    meshes' untouched regions match angle-weighted normals to a median of
    0.00 degrees, and area-weighted to 2.48."""
    nl = len(lv)
    lface = np.repeat(np.arange(len(ls)), lt)
    start = ls[lface]
    total = lt[lface]
    k = np.arange(nl) - start
    nxt = start + (k + 1) % total
    prv = start + (k - 1) % total
    here = co[lv]
    a = co[lv[prv]] - here
    b = co[lv[nxt]] - here
    la = np.linalg.norm(a, axis=1, keepdims=True)
    lb = np.linalg.norm(b, axis=1, keepdims=True)
    ok = (la[:, 0] > 1e-12) & (lb[:, 0] > 1e-12)
    a = a / np.maximum(la, 1e-12)
    b = b / np.maximum(lb, 1e-12)
    ang = np.arccos(np.clip((a * b).sum(1), -1.0, 1.0))
    ang[~ok] = 0.0
    return ang


# ── vector helpers ─────────────────────────────────────────────────────────

def normalize(v, eps=1e-12):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), eps)


def slerp(a, b, w):
    """Great-circle interpolation; w=0 gives a, w=1 gives b.  Falls back to a
    straight pick when the two are collinear (including antipodal, where the
    arc is undefined)."""
    dot = np.clip((a * b).sum(1), -1.0, 1.0)
    om = np.arccos(dot)
    s = np.sin(om)
    degen = s < 1e-6
    om = om[:, None]
    w = w[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (np.sin((1.0 - w) * om) * a + np.sin(w * om) * b) / np.maximum(s[:, None], 1e-9)
    out = np.where(degen[:, None], np.where(w > 0.5, b, a), out)
    return normalize(out)


# ── coincident-vertex welding ──────────────────────────────────────────────

def weld_coincident_normals(co, lv, base, ang, distance, max_angle):
    """Average corner normals that share a position and point roughly the same
    way.  Returns (normals, number of positions touched).

    Only positions holding two or more *distinct* vertices are considered, so a
    vertex split into several fans by sharp edges is left alone.  Within such a
    position the loops are greedily clustered by direction against
    ``max_angle`` (degrees) before averaging.
    """
    if distance <= 0.0 or len(lv) == 0:
        return base, 0

    key = np.round(co / distance).astype(np.int64)[lv]
    _, gid = np.unique(key, axis=0, return_inverse=True)
    order = np.argsort(gid, kind="stable")
    gs = gid[order]
    cuts = np.flatnonzero(np.diff(gs)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [len(gs)]))

    out = base.copy()
    cos_max = np.cos(np.radians(max_angle))
    touched = 0
    for s, e in zip(starts, ends):
        idx = order[s:e]
        if len(idx) < 2 or len(np.unique(lv[idx])) < 2:
            continue
        rest = list(idx)
        merged = False
        while rest:
            seed = rest[0]
            sel = [i for i in rest if float(base[i] @ base[seed]) >= cos_max]
            rest = [i for i in rest if i not in sel]
            if len(sel) < 2 or len(np.unique(lv[sel])) < 2:
                continue
            n = (base[sel] * ang[sel][:, None]).sum(0)
            ln = float(np.linalg.norm(n))
            if ln > 1e-12:
                out[sel] = n / ln
                merged = True
        if merged:
            touched += 1
    return out, touched


# ── public operations ──────────────────────────────────────────────────────

def reset_normals(me, weld=True, weld_distance=1e-5, weld_angle=60.0,
                  clear_sharp=True):
    """Drop custom split normals, optionally welding coincident vertices back
    together.  Returns the number of welded positions.

    Removing the ``custom_normal`` attribute is not by itself enough to get back
    to smooth shading: sharp edges and flat-shaded faces split the normals on
    their own, so the mesh keeps its old faceted look even though the custom
    normals are gone (measured on a shipped face mesh: up to 107 degrees off per
    vertex from marked sharp edges, 128 from flat faces).  ``clear_sharp`` also
    clears those flags, which is what makes the result actually smooth.  It has
    to happen before the weld step reads the normals back.
    """
    co, lv, ls, lt = mesh_arrays(me)
    if "custom_normal" in me.attributes:
        me.attributes.remove(me.attributes["custom_normal"])
    if clear_sharp:
        if len(me.edges):
            me.edges.foreach_set("use_edge_sharp", [False] * len(me.edges))
        if len(me.polygons):
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.update()
    if not weld:
        me.update()
        return 0
    ang = corner_angles(co, lv, ls, lt)
    out, touched = weld_coincident_normals(co, lv, corner_normals(me), ang,
                                           weld_distance, weld_angle)
    if touched:
        me.normals_split_custom_set(out.tolist())
    me.update()
    return touched


def apply_cylindrical(me, axis=2, center=None, face_mask=None,
                      smooth_boundary=True, strength=1.0):
    """Replace the masked faces' custom split normals with a cylindrical field.

    ``axis`` is the cylinder's direction in mesh-local space: either an index
    (0/1/2) or a 3-vector, which is what the caller passes once it has mapped
    the user's world axis through the object's rotation.  A vector is needed
    because game meshes are often imported rotated — assuming local Z is
    vertical collapses the field to a near-constant direction on a Y-up mesh.

    ``center`` is a point on the axis in mesh-local space (defaults to the
    origin).  ``face_mask`` is a bool array over polygons; ``None`` means every
    face.  Unmasked faces keep whatever normals they already have.

    There is no proxy geometry and no radius: the target is the normalized
    horizontal offset from the axis, so the result is scale-invariant — the
    same mesh scaled by any factor yields identical normals.

    Returns (masked face count, boundary vertex count).
    """
    co, lv, ls, lt = mesh_arrays(me)
    npo = len(me.polygons)
    if face_mask is None:
        face_mask = np.ones(npo, bool)

    ang = corner_angles(co, lv, ls, lt)
    base = corner_normals(me)

    if center is None:
        center = np.zeros(3)
    if np.isscalar(axis):
        u = np.zeros(3)
        u[int(axis)] = 1.0
    else:
        u = normalize(np.asarray(axis, np.float64).reshape(3))
    d = co - np.asarray(center, np.float64)
    # Strip the along-axis component; for a basis vector this is d[:, axis] = 0
    d -= np.outer(d @ u, u)
    radius = np.linalg.norm(d, axis=1)
    # Relative epsilon so the on-axis test survives any model scale
    extent = float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 0.0
    on_axis = radius < max(1e-12, extent * 1e-6)
    target = d / np.maximum(radius[:, None], 1e-12)

    # Per-vertex weight: the share of the surrounding corner angle that belongs
    # to masked faces.  Boundary vertices land between 0 and 1 on their own,
    # which is where the one-vertex-wide transition comes from.
    lface = np.repeat(np.arange(npo), lt)
    num = np.zeros(len(co))
    den = np.zeros(len(co))
    np.add.at(num, lv, ang * face_mask[lface])
    np.add.at(den, lv, ang)
    w = np.divide(num, den, out=np.zeros(len(co)), where=den > 1e-12)

    if not smooth_boundary:
        w = (w > 0.5).astype(np.float64)
    w[on_axis] = 0.0
    w *= strength

    me.normals_split_custom_set(slerp(base, target[lv], w[lv]).tolist())
    me.update()

    n_boundary = int(((w > 0.02) & (w < 0.98)).sum())
    return int(face_mask.sum()), n_boundary
