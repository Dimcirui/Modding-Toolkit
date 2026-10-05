"""games/mhwi/physics_split.py — 把 MHWI 骨架的物理骨按部位拆开，连同网格一起。

名额规则见 core/mhwi_physics_budget.py。这里做三件事：

1. **规划**：物理子树按权重交叉并成组（同组必须进同一部位，否则网格拆开会撕裂），
   再按区域 / 名额分到 body / arm / wst / leg。
2. **骨架**：每个用到的部位一份骨架（原骨架就是 body），删掉不属于该部位的物理骨。
3. **网格**：每个面看它的顶点上哪个部位的物理权重最多，就归哪个部位；没有物理权重的面
   归 body。整块只属于一个部位的网格直接移过去，跨部位的按面拆成几份。每份网格上别的
   部位的物理权重并进那根骨的锚点（最近的本体骨），即那一小部分跟着身体刚性移动。

MHW Model Editor 以 ``.mod3`` 集合为单位导出，集合里只能有一个骨架（两个会报
MoreThanOneArmature），网格放在 ``LOD ALL - `` / ``LOD n - `` 子集合里。所以每个部位
另建一个 mod3 集合，照原集合的 LOD 子集合结构摆放。
"""

import re

import bmesh
import bpy

from ...core import mhwi_physics_budget as budget
from ...core import weight_utils

REGIONS = ("head", "upper", "lower")
#: 装了插件时的默认去向。头盔槽被 helmface 占用且无物理，头部只能借一个部位放。
DEFAULT_REGION_SLOT = {"head": "arm", "upper": "body", "lower": "wst"}
SPARE_SLOT = "leg"

MOD3_TYPE = "MHW_MOD3_COLLECTION"
_LOD_RE = re.compile(r"^LOD (ALL|\d+) - ")


def region_of_std(std):
    if std in ("head", "neck"):
        return "head"
    if std == "pelvis" or std.startswith(("thigh", "shin", "foot", "toe")):
        return "lower"
    return "upper"


def child_meshes(armature):
    return [o for o in armature.children_recursive if o.type == 'MESH']


class SplitPlan:
    def __init__(self):
        self.physics = []           # 父在前的物理骨序列
        self.roots = []
        self.root_of = {}           # 物理骨 -> 所在子树的链首
        self.anchor_of = {}         # 物理骨 -> 锚点本体骨（并权重用）
        self.items = []             # 合并成组后的 budget.Item
        self.group_of_root = {}     # 链首 -> 所在组的 Item.root
        self.region_totals = {r: 0 for r in REGIONS}
        self.base_bones = 0


def plan_split(armature, mapper, physics_ordered):
    """只读。*physics_ordered* 是父在前的物理骨名序列。"""
    plan = SplitPlan()
    bones = armature.data.bones
    ps = set(physics_ordered)
    plan.physics = list(physics_ordered)
    plan.base_bones = len(bones) - len(ps)

    std_by_name = {}
    for std in mapper.mapping_data:
        main, aux = mapper.get_matches_for_standard(armature, std)
        if main:
            std_by_name[main] = std
        for a in aux:
            std_by_name[a] = std
    fallback_anchor = next((b.name for b in bones if b.parent is None and b.name not in ps), None)

    plan.roots = [n for n in plan.physics
                  if bones[n].parent is None or bones[n].parent.name not in ps]
    region_of_root, items_by_root = {}, {}
    for r in plan.roots:
        p = bones[r].parent
        anchor = p.name if p is not None else fallback_anchor
        walk = p
        while walk is not None and walk.name not in std_by_name:
            walk = walk.parent
        region = region_of_std(std_by_name[walk.name]) if walk is not None else "upper"
        region_of_root[r] = region
        nt = t = 0
        stack = [r]
        while stack:
            n = stack.pop()
            plan.root_of[n] = r
            plan.anchor_of[n] = anchor
            kids = [c.name for c in bones[n].children if c.name in ps]
            if kids:
                nt += 1
            else:
                t += 1
            stack.extend(kids)
        items_by_root[r] = budget.Item(r, nt, t, region=region)
        plan.region_totals[region] += nt + t

    mass, pair = weight_utils.co_weight(child_meshes(armature), plan.root_of)
    groups = budget.group_roots(plan.roots, pair, mass)
    plan.items = budget.merge_items(groups, items_by_root)
    for item in plan.items:
        for r in item.roots:
            plan.group_of_root[r] = item.root
    return plan


def pack(plan, unlocked, region_slot):
    return budget.pack(plan.items, plan.base_bones, unlocked,
                       region_slot=region_slot if unlocked else None, spare=SPARE_SLOT)


def slot_of_bones(plan, packing):
    return {n: packing.placed[plan.group_of_root[plan.root_of[n]]] for n in plan.physics}


# ---------------------------------------------------------------------------
# 集合
# ---------------------------------------------------------------------------

def _mod3_collection(obj):
    for col in bpy.data.collections:
        if col.get("~TYPE") == MOD3_TYPE and obj.name in col.all_objects:
            return col
    return None


def _parents_of(col, scene):
    out = [c for c in bpy.data.collections if col.name in c.children]
    if col.name in scene.collection.children:
        out.append(scene.collection)
    return out


def _new_like(src, name):
    col = bpy.data.collections.new(name)
    col.color_tag = src.color_tag
    for k in src.keys():
        try:
            col[k] = src[k]
        except TypeError:
            pass
    return col


class SlotCollections:
    """一个部位的集合：顶层 + 原集合里各子集合的对应。"""

    def __init__(self, top, mapping):
        self.top = top
        self.mapping = mapping      # 原集合 -> 新集合

    def target_for(self, obj, parent_of):
        for c in obj.users_collection:
            walk = c
            while walk is not None:
                if walk in self.mapping:
                    return self.mapping[walk]
                walk = parent_of.get(walk)
        return self.top


def make_slot_collections(context, armature, slot):
    """返回 (SlotCollections, 原集合的子->父表, 是否找到了 mod3 集合)。"""
    src = _mod3_collection(armature)
    if src is None:
        top = bpy.data.collections.new(f"{armature.name}_{slot}")
        context.scene.collection.children.link(top)
        return SlotCollections(top, {}), {}, False
    base = src.name[:-5] if src.name.endswith(".mod3") else src.name
    top = _new_like(src, f"{base}_{slot}.mod3")
    parents = _parents_of(src, context.scene) or [context.scene.collection]
    parents[0].children.link(top)
    mapping, parent_of = {src: top}, {}
    stack = [src]
    while stack:
        c = stack.pop()
        for ch in c.children:
            parent_of[ch] = c
            m = _LOD_RE.match(ch.name)
            name = (f"LOD {m.group(1)} - {base}_{slot}" if m
                    else f"{ch.name}_{slot}")
            new = _new_like(ch, name)
            mapping[c].children.link(new)
            mapping[ch] = new
            stack.append(ch)
    return SlotCollections(top, mapping), parent_of, True


# ---------------------------------------------------------------------------
# 网格
# ---------------------------------------------------------------------------

def face_slots(obj, slot_of_bone):
    """每个面归哪个部位：面上各顶点的物理权重按部位累加，取最多的；没有物理权重归 body。"""
    idx_slot = {vg.index: slot_of_bone[vg.name] for vg in obj.vertex_groups
                if vg.name in slot_of_bone}
    vert_slot = []
    for v in obj.data.vertices:
        per = {}
        for g in v.groups:
            s = idx_slot.get(g.group)
            if s is not None and g.weight > 0:
                per[s] = per.get(s, 0.0) + g.weight
        vert_slot.append(per)
    out = []
    for poly in obj.data.polygons:
        acc = {}
        for vi in poly.vertices:
            for s, w in vert_slot[vi].items():
                acc[s] = acc.get(s, 0.0) + w
        out.append(max(acc, key=acc.get) if acc else "body")
    return out


def keep_faces(obj, keep):
    """只保留 keep[i] 为真的面；只被删掉的面用到的边和顶点一起删。

    自定义法向要先按绝对方向存下来、删完再写回：它是相对所在平滑扇区编码的，切口另一侧
    的面一删，扇区变了，同一份数据会解码成另一个方向（实测切口上的角点偏到 120°，其余
    角点不受影响）。删面不改动剩下的面和角点的先后顺序，所以按顺序写回就能对上。"""
    me = obj.data
    saved = None
    if me.has_custom_normals:
        flat = [0.0] * (len(me.loops) * 3)
        me.corner_normals.foreach_get("vector", flat)
        saved = [tuple(flat[3 * li:3 * li + 3])
                 for p in me.polygons if keep[p.index]
                 for li in range(p.loop_start, p.loop_start + p.loop_total)]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if not keep[f.index]]
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(me)
    bm.free()
    if saved is not None:
        me.normals_split_custom_set(saved)
    me.update()


def retarget_mesh(obj, armature):
    obj.parent = armature
    for md in obj.modifiers:
        if md.type == 'ARMATURE':
            md.object = armature


def fold_foreign_weights(obj, slot, plan, slot_of_bone):
    """别的部位的物理权重并进那根骨的锚点本体骨。返回受影响的顶点数。"""
    merge = {vg.name: plan.anchor_of[vg.name] for vg in obj.vertex_groups
             if vg.name in slot_of_bone and slot_of_bone[vg.name] != slot
             and plan.anchor_of.get(vg.name)}
    if not merge:
        return 0
    idx = {obj.vertex_groups[n].index for n in merge}
    touched = sum(1 for v in obj.data.vertices
                  if any(g.group in idx and g.weight > 0 for g in v.groups))
    weight_utils.merge_vertex_groups([obj], merge)
    return touched
