"""Pre-export check, physics half (docs/pre_export_check_plan.md §5.4).

What makes a chain2 / clsp either refuse to export or do nothing in game, read
off RE Chain Editor's scene objects.  Read-only -- the check runs from a dialog's
``draw()`` -- the fixes are operators in ``pre_export_fix_ops``.

Three facts about the files shape every check here, all read from upstream's
exporters (``blender_re_chain.py:1297 exportChainFile``,
``blender_re_clsp.py:622 exportCLSPFile``):

- **A chain group is written as its last node's bone plus a node count.**  The
  other nodes' ``BoneName`` constraints never reach the file; the engine takes
  that last bone and walks up its parents (upstream's own importer rebuilds a
  chain exactly so, ``getBoneParentsRecursive``).  A missing *last* bone kills
  the whole chain; nodes that disagree with that walk mean the game drives
  other bones than the ones shown.
- **Bones are found by a hash of the name**, case-sensitive, so a reference
  that differs only in case is as dead as a missing one.
- **The structure rules are upstream's** ``chainErrorCheck`` /
  ``clspErrorCheck`` (``blender_re_chain.py:1067``, ``blender_re_clsp.py:523``),
  re-implemented rather than called: those pop a message box, bump IDs and sync
  collision offsets, none of which may happen inside ``draw()``.  A structure
  error is also what makes upstream's export return FINISHED without writing
  the file, so catching it here is what keeps a batch export from counting a
  missing chain as a success (docs §5.4, user's call not to patch that part).
"""

from collections import namedtuple

import bpy

from .i18n import T
from . import pre_export_check as pc
from . import pre_export_report as pr
from . import re_hash

_K = "core.pre_export_physics."

HEADER = "RE_CHAIN_HEADER"
WIND = "RE_CHAIN_WINDSETTINGS"
SETTINGS = "RE_CHAIN_CHAINSETTINGS"
GROUP = "RE_CHAIN_CHAINGROUP"
SUBGROUP = "RE_CHAIN_SUBGROUP"
NODE = "RE_CHAIN_NODE"
FRAME = "RE_CHAIN_NODE_FRAME"
SINGLE = "RE_CHAIN_COLLISION_SINGLE"
CAPSULE = "RE_CHAIN_COLLISION_CAPSULE_ROOT"
CAP_START = "RE_CHAIN_COLLISION_CAPSULE_START"
CAP_END = "RE_CHAIN_COLLISION_CAPSULE_END"
LINK = "RE_CHAIN_LINK"
COLLIDERS = (SINGLE, CAPSULE)

#: ``chainCollisionShape`` enum value for a capsule.
_CAPSULE_SHAPE = "2"

#: More findings than this of one kind in one file collapse into a single line
#: naming the first few -- a chain bound against the wrong mesh would otherwise
#: list every node in the file.
_COLLAPSE_OVER = 5

#: One part's physics, as the batch dialog binds it.  *clsp_slot*: whether the
#: armor set exports a clsp for this part at all.
PhysPart = namedtuple("PhysPart", "label part_id chain clsp mesh clsp_slot")


def kind(obj):
    return obj.get("TYPE") if obj is not None else None


def _objs(col):
    return list(col.all_objects) if col is not None else []


def bone_constraint(obj):
    return obj.constraints.get("BoneName")


def chain_nodes(grp):
    """A group's nodes in the order upstream writes them: down from the first
    node child, taking *every* node child at each level and carrying on from the
    last.  So a node with two node children counts both -- which then shows up
    as a chain that does not match the skeleton, the same way it would in game."""
    node = next((c for c in grp.children if kind(c) == NODE), None)
    if node is None:
        return []
    nodes = [node]
    while True:
        kids = [c for c in node.children if kind(c) == NODE]
        if not kids:
            return nodes
        nodes += kids
        node = kids[-1]


def terminal_ref(nodes):
    """The bone name upstream writes as the group's terminate node."""
    last = nodes[-1]
    con = bone_constraint(last)
    name = con.subtarget if con is not None else last.name.split(".")[0]
    if name.startswith("b") and ":" in name:
        name = name.split(":", 1)[1]
    return name


def collection_armature(col):
    """The armature upstream's .mesh exporter uses: a direct member."""
    if col is None:
        return None
    return next((o for o in col.objects if o.type == 'ARMATURE'), None)


class Skeleton:
    """Bone names and parents of one or more armatures, plus names known to
    exist at runtime without being in any of them."""

    def __init__(self, armatures, extra=()):
        self.parent = {}
        for arm in armatures:
            if arm is None:
                continue
            for b in arm.data.bones:
                self.parent.setdefault(b.name, b.parent.name if b.parent else None)
        self.names = set(self.parent) | set(extra)
        self._hashes = None

    def resolve(self, ref):
        """The bone *ref* means here, or None.  A bare number is a hash kept
        from an import that could not name the bone."""
        if ref in self.names:
            return ref
        if ref.isdigit():
            if self._hashes is None:
                self._hashes = {re_hash.hash_wide(n): n for n in self.names}
            return self._hashes.get(int(ref))
        return None


def _mesh_objects(col):
    return [o for o in col.all_objects
            if o.type == 'MESH' and not o.get("MeshExportExclude")] if col is not None else []


def _covered_bones(mesh_col, arm):
    """Bones that move some vertex of the part: weighted (at the exporter's
    cut-off) themselves, or an ancestor of one that is."""
    if arm is None:
        return set()
    bones = arm.data.bones
    weighted = set()
    for obj in _mesh_objects(mesh_col):
        names = {vg.index: vg.name for vg in obj.vertex_groups if vg.name in bones}
        if not names:
            continue
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group in names and g.weight >= pc.EXPORT_MIN_WEIGHT:
                    weighted.add(names[g.group])
    covered = set()
    for name in weighted:
        b = bones.get(name)
        while b is not None and b.name not in covered:
            covered.add(b.name)
            b = b.parent
    return covered


# ── Structure ────────────────────────────────────────────────────────────────

#: Problem code -> i18n key, for the structure findings.
_ST_KEYS = {
    'no_header':            _K + "st_no_header",
    'many_headers':         _K + "st_many_headers",
    'header_parented':      _K + "st_header_parented",
    'node_no_frame':        _K + "st_node_no_frame",
    'node_many_frames':     _K + "st_node_many_frames",
    'parent':               _K + "st_parent",
    'no_constraint':        _K + "st_no_constraint",
    'constraint_no_bone':   _K + "st_constraint_no_bone",
    'constraint_no_target': _K + "st_constraint_no_target",
    'group_empty':          _K + "st_group_empty",
    'capsule_single':       _K + "st_capsule_single",
    'capsule_no_start':     _K + "st_capsule_no_start",
    'capsule_no_end':       _K + "st_capsule_no_end",
    'capsule_many_start':   _K + "st_capsule_many_start",
    'capsule_many_end':     _K + "st_capsule_many_end",
    'link_not_group':       _K + "st_link_not_group",
}

#: What each object type must hang under, and the label naming it.
_VALID_PARENT = {
    NODE:     ((GROUP, NODE, SUBGROUP), _K + "want_group"),
    GROUP:    ((SETTINGS,), _K + "want_settings"),
    WIND:     ((HEADER,), _K + "want_header"),
    SETTINGS: ((HEADER, WIND), _K + "want_header_or_wind"),
    SINGLE:   ((HEADER,), _K + "want_header"),
    CAPSULE:  ((HEADER,), _K + "want_header"),
    LINK:     ((HEADER,), _K + "want_header"),
}


def _constraint_problem(obj):
    con = bone_constraint(obj)
    if con is None:
        return 'no_constraint'
    if not con.subtarget:
        return 'constraint_no_bone'
    if con.target is None:
        return 'constraint_no_target'
    return None


def _collider_problems(obj):
    """upstream's collider rules, shared by chain2 and clsp."""
    out = []
    if kind(obj) == SINGLE:
        cc = getattr(obj, "re_chain_chaincollision", None)
        if cc is not None and cc.chainCollisionShape == _CAPSULE_SHAPE:
            out.append((obj, 'capsule_single'))
        code = _constraint_problem(obj)
        if code:
            out.append((obj, code))
    elif kind(obj) == CAPSULE:
        for end, tag in ((CAP_START, 'start'), (CAP_END, 'end')):
            ends = [c for c in obj.children if kind(c) == end]
            if not ends:
                out.append((obj, 'capsule_no_' + tag))
            elif len(ends) > 1:
                out.append((obj, 'capsule_many_' + tag))
            else:
                code = _constraint_problem(ends[0])
                if code:
                    out.append((ends[0], code))
    return out


def reparent_target(obj, objs):
    """Where 「挂到首个合法父级」 puts *obj*, or None when there is no sure
    answer (a node: which group it belongs to cannot be guessed)."""
    k = kind(obj)
    headers = [o for o in objs if kind(o) == HEADER]
    if k == GROUP:
        settings = sorted((o for o in objs if kind(o) == SETTINGS), key=lambda o: o.name)
        return settings[0] if settings else None
    if k in (WIND, SETTINGS, SINGLE, CAPSULE, LINK):
        return headers[0] if len(headers) == 1 else None
    return None


def structure_problems(col, ftype):
    """``[(obj or None, code)]`` for what upstream's error check rejects in
    *col* exported as *ftype* (``'chain2'`` or ``'clsp'``).  clsp only has the
    collider rules: its exporter needs no header and ignores everything else."""
    objs = _objs(col)
    out = []
    if ftype == 'clsp':
        for o in objs:
            out += _collider_problems(o)
        return out

    headers = [o for o in objs if kind(o) == HEADER]
    if not headers:
        out.append((None, 'no_header'))
    elif len(headers) > 1:
        out.append((None, 'many_headers'))
    scene_objects = bpy.context.scene.objects
    for o in objs:
        k = kind(o)
        if k == HEADER:
            if o.parent is not None:
                out.append((o, 'header_parented'))
            continue
        if k in _VALID_PARENT and kind(o.parent) not in _VALID_PARENT[k][0]:
            out.append((o, 'parent'))
        if k == NODE:
            frames = sum(1 for c in o.children if kind(c) == FRAME)
            if frames == 0:
                out.append((o, 'node_no_frame'))
            elif frames > 1:
                out.append((o, 'node_many_frames'))
            if bone_constraint(o) is None:
                out.append((o, 'no_constraint'))
        elif k == GROUP:
            if not any(kind(c) == NODE for c in o.children):
                out.append((o, 'group_empty'))
        elif k in COLLIDERS:
            out += _collider_problems(o)
        elif k == LINK:
            cl = getattr(o, "re_chain_chainlink", None)
            for attr in ("chainGroupAObject", "chainGroupBObject"):
                target = scene_objects.get(getattr(cl, attr, "") or "") if cl else None
                if target is not None and kind(target) != GROUP:
                    out.append((o, 'link_not_group'))
                    break
    return out


def _structure_findings(part, col, ftype):
    out = []
    objs = _objs(col)
    headers = sum(1 for o in objs if kind(o) == HEADER)
    for obj, code in structure_problems(col, ftype):
        if obj is None:
            text = T(_ST_KEYS[code]).format(n=headers)
            out.append(pr.finding('phys', 'phys_structure', f"{ftype} · {col.name} — {text}",
                                  key=('st', col.name, code), part=part.label))
            continue
        if code == 'parent':
            want = T(_VALID_PARENT[kind(obj)][1])
            text = T(_ST_KEYS[code]).format(want=want)
            sub = 'phys_parent' if reparent_target(obj, objs) is not None else 'phys_structure'
        else:
            text = T(_ST_KEYS[code])
            sub = 'phys_structure'
        out.append(pr.finding('phys', sub, f"{ftype} · {obj.name} — {text}",
                              key=('st', obj.name, code), part=part.label, objects=[obj.name]))
    return out


# ── Bones ────────────────────────────────────────────────────────────────────

def _part_armature(part):
    """Node bones live on the part's own armature: the mesh collection's, or --
    with no mesh bound -- whatever the nodes' constraints point at."""
    arm = collection_armature(part.mesh)
    if arm is not None:
        return arm
    for o in _objs(part.chain):
        if kind(o) == NODE:
            con = bone_constraint(o)
            if con is not None and con.target is not None and con.target.type == 'ARMATURE':
                return con.target
    return None


def chain_groups(col):
    """``[(group, nodes)]`` for every chain group in *col*, sorted by name the
    way the exporter writes them."""
    return [(g, chain_nodes(g)) for g in sorted((o for o in _objs(col) if kind(o) == GROUP),
                                                 key=lambda o: o.name)]


def group_bones(nodes, skel):
    """``(driven, shown, missing)`` for one group.

    *driven*: the bones the game will simulate (head first), or None when the
    last bone is missing or runs out of parents.  *shown*: what the nodes' own
    constraints point at, resolved.  *missing*: ``[(node, ref)]`` whose bone is
    not on the skeleton -- the last node first, if it is one of them.
    """
    term = terminal_ref(nodes)
    missing = []
    term_bone = skel.resolve(term) if term else None
    if term_bone is None:
        missing.append((nodes[-1], term))
    shown = []
    for n in nodes:
        con = bone_constraint(n)
        ref = con.subtarget if con is not None else None
        bone = skel.resolve(ref) if ref else None
        shown.append(bone)
        if bone is None and ref and n is not nodes[-1]:
            missing.append((n, ref))
    driven = pc.driven_bones(term_bone, len(nodes), skel.parent) if term_bone else None
    return driven, shown, missing


def _union_skeleton(parts, armatures, extra_bones):
    """Where a collider's bone may live: any armature in this export (a
    collider can sit on the body while its chain belongs to the helm), plus the
    names the game's own skeleton always has."""
    arms = [a for a in armatures if a is not None]
    for p in parts:
        arm = _part_armature(p)
        if arm is not None and arm not in arms:
            arms.append(arm)
    return Skeleton(arms, extra_bones)


def missing_refs(physics, armatures=(), extra_bones=()):
    """``[(obj, constraint, ref, candidates)]`` for every node or collider whose
    bone cannot be found, with the names a case-only retarget would pick from.
    Shared by the check and the 「改指向」 button so both judge the same way."""
    out = []
    parts = physics or []
    everywhere = _union_skeleton(parts, armatures, extra_bones)
    seen = set()
    for p in parts:
        own = Skeleton([_part_armature(p)])
        for _grp, nodes in chain_groups(p.chain):
            if not nodes:
                continue
            _d, _s, missing = group_bones(nodes, own)
            for node, ref in missing:
                con = bone_constraint(node)
                if con is not None and node.name not in seen:
                    seen.add(node.name)
                    out.append((node, con, ref, own.names))
        for ftype, col in (('chain2', p.chain), ('clsp', p.clsp)):
            for obj, con, ref in _collider_refs(col, ftype):
                if obj.name in seen or everywhere.resolve(ref):
                    continue
                seen.add(obj.name)
                out.append((obj, con, ref, everywhere.names))
    return out


def _sequences(part):
    """``[(group name, bones)]`` for the overlap test: the bones the game will
    drive, or -- where that cannot be worked out -- the ones shown."""
    skel = Skeleton([_part_armature(part)])
    out = []
    for grp, nodes in chain_groups(part.chain):
        if nodes:
            driven, shown, _m = group_bones(nodes, skel)
            out.append((grp.name, driven or [b for b in shown if b]))
    return out


def _collider_refs(col, ftype):
    """``[(obj, constraint, bone ref)]`` for the colliders in *col*.  In a clsp
    a ``HASH_<n>`` ref is written as the number itself (a bone the importer
    could not name); chain2 hashes it as a string like any other, so there it
    is simply a name that does not exist."""
    out = []
    for o in _objs(col):
        if kind(o) == SINGLE:
            ends = [o]
        elif kind(o) == CAPSULE:
            ends = [c for c in o.children if kind(c) in (CAP_START, CAP_END)]
        else:
            continue
        for e in ends:
            con = bone_constraint(e)
            if con is None or not con.subtarget:
                continue        # a structure error already
            if ftype == 'clsp' and "HASH_" in con.subtarget:
                continue
            out.append((e, con, con.subtarget))
    return out


def _joiner():
    return T("core.pre_export_check_ops.part_joiner")


def _collapse(findings, sub, ftype, part, text_key):
    """Past _COLLAPSE_OVER findings of one kind, one line naming the first few."""
    if len(findings) <= _COLLAPSE_OVER:
        return findings
    names = _joiner().join(f['_name'] for f in findings[:3])
    text = T(text_key).format(ftype=ftype, n=len(findings), names=names)
    objs = [o for f in findings for o in f['objects']]
    return [pr.finding('phys', sub, text, key=('many', sub, ftype, part.label),
                       part=part.label, objects=objs)]


def _bone_findings(part, skel, covered):
    out = []
    missing_lines = {'phys_bone_missing': [], 'phys_bone_retarget': []}
    for grp, nodes in chain_groups(part.chain):
        if not nodes:
            continue            # 'group_empty', a structure error
        if len(nodes) == 1:
            # Useless whatever its bone: nothing else about it is worth a line.
            out.append(pr.finding('phys', 'phys_single_node',
                                  "chain2 · " + T(_K + "item_single_node").format(grp=grp.name),
                                  severity=pr.INFO, key=('single', grp.name),
                                  part=part.label, objects=[grp.name]))
            continue
        driven, shown, missing = group_bones(nodes, skel)
        if missing:
            fixable = all(pc.unique_casefold_match(ref, skel.names) for _n, ref in missing)
            if missing[0][0] is not nodes[-1]:
                key, refs = "item_node_missing", _joiner().join(ref for _n, ref in missing[:3])
            elif missing[0][1]:
                # The last bone is what the file stores; the rest only follow.
                key, refs = "item_terminal_missing", missing[0][1]
            else:
                key, refs = "item_terminal_empty", ""
            f = pr.finding('phys', 'phys_bone_retarget' if fixable else 'phys_bone_missing',
                           "chain2 · " + T(_K + key).format(grp=grp.name, bones=refs),
                           key=('bone', grp.name), part=part.label, objects=[grp.name])
            f['_name'] = grp.name
            missing_lines[f['sub']].append(f)
            continue
        if any(bone_constraint(n) is None for n in nodes):
            continue            # 'no_constraint', a structure error
        if driven is None or driven != shown:
            text = (T(_K + "item_path_short").format(grp=grp.name, n=len(nodes))
                    if driven is None else
                    T(_K + "item_path").format(grp=grp.name, first=driven[0], last=driven[-1],
                                               n=len(driven)))
            out.append(pr.finding('phys', 'phys_bone_path', "chain2 · " + text,
                                  key=('path', grp.name), part=part.label, objects=[grp.name]))
        if part.mesh is not None and driven and not covered.intersection(driven):
            out.append(pr.finding('phys', 'phys_no_weight',
                                  "chain2 · " + T(_K + "item_no_weight").format(grp=grp.name),
                                  key=('weight', grp.name), part=part.label, objects=[grp.name]))
    for sub, lines in missing_lines.items():
        out += _collapse(lines, sub, 'chain2', part, _K + "item_many_chains")

    duplicates, contained, crossing = pc.chain_overlaps(_sequences(part))
    for kept, dropped in duplicates:
        for d in dropped:
            out.append(pr.finding('phys', 'phys_duplicate',
                                  "chain2 · " + T(_K + "item_duplicate").format(a=kept, b=d),
                                  key=('dup', d), part=part.label, objects=[d]))
    for inner, outer in contained:
        out.append(pr.finding('phys', 'phys_duplicate',
                              "chain2 · " + T(_K + "item_contained").format(a=inner, b=outer),
                              key=('dup', inner), part=part.label, objects=[inner]))
    for a, b, n in crossing:
        out.append(pr.finding('phys', 'phys_crossing',
                              "chain2 · " + T(_K + "item_crossing").format(a=a, b=b, n=n),
                              key=('cross', a, b), part=part.label, objects=[a, b]))
    return out


def _collider_findings(part, ftype, col, everywhere):
    lines = {'phys_collider_bone': [], 'phys_bone_retarget': []}
    for obj, _con, ref in _collider_refs(col, ftype):
        if everywhere.resolve(ref):
            continue
        name = obj.parent.name if kind(obj) in (CAP_START, CAP_END) and obj.parent else obj.name
        fix = pc.unique_casefold_match(ref, everywhere.names)
        sub = 'phys_bone_retarget' if fix else 'phys_collider_bone'
        f = pr.finding('phys', sub, f"{ftype} · " + T(_K + "item_collider_bone").format(
            obj=name, bone=ref), key=('col', obj.name), part=part.label, objects=[obj.name])
        f['_name'] = name
        lines[sub].append(f)
    out = []
    for sub, found in lines.items():
        out += _collapse(found, sub, ftype, part, _K + "item_many_colliders")
    return out


def _link_findings(part):
    out = []
    groups = {o.name for o in _objs(part.chain) if kind(o) == GROUP}
    scene_objects = bpy.context.scene.objects
    for o in _objs(part.chain):
        if kind(o) != LINK:
            continue
        cl = getattr(o, "re_chain_chainlink", None)
        if cl is None:
            continue
        for attr in ("chainGroupAObject", "chainGroupBObject"):
            name = getattr(cl, attr, "") or ""
            if not name or name.isdigit() or name in groups:
                continue
            target = scene_objects.get(name)
            if target is not None and kind(target) != GROUP:
                continue        # a structure error already
            out.append(pr.finding('phys', 'phys_link_dangling',
                                  "chain2 · " + T(_K + "item_link_dangling").format(link=o.name, grp=name),
                                  severity=pr.INFO, key=('link', o.name, attr),
                                  part=part.label, objects=[o.name]))
    return out


def colliders_in(col):
    return [o for o in _objs(col) if kind(o) in COLLIDERS]


def check(physics, armatures=(), extra_bones=()):
    """``[finding]`` for every bound chain2 / clsp in *physics*
    (``[PhysPart]``).  *armatures* are the export's other armatures and
    *extra_bones* the bone names the game's own skeleton always has (MHWS: the
    base body), so a collider on one of them is not reported just because the
    part it belongs to does not carry that bone."""
    out = []
    parts = [p for p in (physics or []) if p.chain is not None or p.clsp is not None]
    everywhere = _union_skeleton(parts, armatures, extra_bones)
    done_cols = set()
    for p in parts:
        for ftype, col in (('chain2', p.chain), ('clsp', p.clsp)):
            if col is None or (col.name, ftype) in done_cols:
                continue
            done_cols.add((col.name, ftype))
            out += _structure_findings(p, col, ftype)
            out += _collider_findings(p, ftype, col, everywhere)
        if p.chain is None:
            continue
        arm = _part_armature(p)
        if arm is not None:
            out += _bone_findings(p, Skeleton([arm]), _covered_bones(p.mesh, arm))
        out += _link_findings(p)
        n_col = len(colliders_in(p.chain))
        if n_col and p.clsp_slot and p.clsp is None:
            out.append(pr.finding('phys', 'phys_clsp_unbound',
                                  T(_K + "item_clsp_unbound").format(n=n_col),
                                  severity=pr.INFO, key=('clsp', p.part_id), part=p.label,
                                  objects=[p.chain.name]))
    for f in out:
        f.pop('_name', None)
    return out


# ── For the fixes ────────────────────────────────────────────────────────────

def target_fixes(physics, armatures=()):
    """``[(obj, constraint, armature)]`` for bone constraints that name a bone
    but have no target: upstream's error check rejects the whole file for it
    (docs §3.9).  The target is the part's armature when it has the bone (or
    the ref is a bare hash), else any armature in the export that has it."""
    out = []
    pool = [a for a in armatures if a is not None]
    for p in physics or []:
        own = _part_armature(p)
        cands = ([own] if own is not None else []) + [a for a in pool if a is not own]
        seen = set()
        for col in (p.chain, p.clsp):
            for o in _objs(col):
                if o.name in seen or kind(o) not in (NODE, SINGLE, CAP_START, CAP_END):
                    continue
                seen.add(o.name)
                con = bone_constraint(o)
                if con is None or not con.subtarget or con.target is not None:
                    continue
                ref = con.subtarget
                bare = ref.isdigit() or "HASH_" in ref
                arm = next((a for a in cands if ref in a.data.bones), None)
                if arm is None and bare and cands:
                    arm = cands[0]
                if arm is not None:
                    out.append((o, con, arm))
    return out


def overlap_plan(physics):
    """Group names 「清除重复链」 deletes: the dropped duplicates and the
    contained chains, per chain2 collection."""
    out = []
    for p in physics or []:
        duplicates, contained, _x = pc.chain_overlaps(_sequences(p))
        out += [d for _k, ds in duplicates for d in ds]
        out += [inner for inner, _o in contained]
    return out


def crossing_groups(physics):
    names = []
    for p in physics or []:
        for a, b, _n in pc.chain_overlaps(_sequences(p))[2]:
            names += [n for n in (a, b) if n not in names]
    return names


def single_node_groups(physics):
    return [grp.name for p in physics or [] for grp, nodes in chain_groups(p.chain)
            if len(nodes) == 1]


def delete_groups(names):
    """Remove chain groups with everything hanging under them -- nodes, frames,
    their cone helpers, jiggles -- and the sub groups that belong to them.
    Returns how many groups went."""
    groups = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
    doomed, datas = [], []
    for g in groups:
        stack = [g]
        for o in bpy.data.objects:
            sg = getattr(o, "re_chain_chainsubgroup", None)
            if kind(o) == SUBGROUP and sg is not None and sg.parentGroup == g:
                stack.append(o)
        while stack:
            o = stack.pop()
            if o in doomed:
                continue
            doomed.append(o)
            stack += list(o.children)
    for o in doomed:
        if o.data is not None and o.data not in datas:
            datas.append(o.data)
        bpy.data.objects.remove(o, do_unlink=True)
    # Group curves and cone helpers are per-object curve data; nothing else
    # uses them once their object is gone.
    for d in datas:
        if d.users:
            continue
        if isinstance(d, bpy.types.Curve):
            bpy.data.curves.remove(d)
        elif isinstance(d, bpy.types.Mesh):
            bpy.data.meshes.remove(d)
    return len(groups)
