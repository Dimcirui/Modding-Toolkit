"""core/mhwi_physics_budget.py — MHWI 物理骨名额估算（纯逻辑，不依赖 bpy）。

名额规则
--------
- 每个部位的 mod3 总骨数上限 255，其中本体骨（参考模型 86 根）每个部位都有一份，所以
  一个部位能放的物理骨 = 255 − 本体骨数。
- **不装解锁插件**：只有 body 用 300–511，受的就是上面这个总数限制；arm / wst / leg
  上**物理实际生效的只有 150–199（50 个）**。末端骨没有物理、只标结束，只要不占
  150–199 放哪都行；这里规定 200–245，满了接 260–299（共 86 个）。跳过的 246–259 里
  有参考骨架的本体骨（247–254），300+ 留给无限制的部位，两边都不冲突。
  （早先的代码把非末端写成 150–200 共 51 个，第 51 根落在 200 上，游戏里没有物理。）
- **装了解锁插件**：arm / wst / leg 与 body 等同，都用 300–511，各自受 255 总数限制。
- 头盔槽另有用途（helmface）、本身无物理，不参与。

末端骨按移植后的样子数：有权重的叶骨会补一根 ``_End``（叶骨本身变成非末端骨），没权重
的叶骨自己就是末端，分叉处收尾的链也补一根 ``_End``。
"""

from dataclasses import dataclass, field

BONE_LIMIT = 255
SLOTS = ("body", "arm", "wst", "leg")

#: 编号范围（含两端）。重命名按这里分配，名额按这里算。
BODY_IDS = ((300, 511),)
SLOT_PHYSICS_IDS = ((150, 199),)            # 不装插件时 arm / wst / leg 物理生效的范围
SLOT_TAIL_IDS = ((200, 245), (260, 299))    # 末端骨：不占 150–199、不碰本体骨和 300+
SLOT_NON_TAIL = sum(b - a + 1 for a, b in SLOT_PHYSICS_IDS)     # 50
SLOT_TAIL = sum(b - a + 1 for a, b in SLOT_TAIL_IDS)            # 86


@dataclass
class Item:
    root: str
    non_tail: int
    tail: int
    roots: tuple = ()           # 合并成组时组内全部链首；单棵子树时为空
    region: str = ""            # head / upper / lower，拆分时用来就近归类

    @property
    def total(self):
        return self.non_tail + self.tail


@dataclass
class Packing:
    used: dict = field(default_factory=dict)      # 槽位 -> (非末端, 末端)
    capacity: dict = field(default_factory=dict)  # 槽位 -> (非末端上限, 末端上限, 总数上限)；前两个 None 表示不单独限
    placed: dict = field(default_factory=dict)    # 链首 -> 槽位
    overflow: list = field(default_factory=list)  # 放不下的 Item

    @property
    def overflow_bones(self):
        return sum(i.total for i in self.overflow)


def tree_items(roots, children_of, weighted, fork_ends=()):
    """每棵物理子树移植后的 (非末端, 末端) 数。

    *children_of(name)* 只返回物理子骨；*fork_ends* 是会在分叉处收尾、补 ``_End`` 的骨。"""
    fork_ends = set(fork_ends)
    items = []
    for r in roots:
        nt = t = 0
        stack = [r]
        while stack:
            n = stack.pop()
            kids = list(children_of(n))
            if kids:
                nt += 1
            elif n in weighted:
                nt += 1
                t += 1
            else:
                t += 1
            if n in fork_ends:
                t += 1
            stack.extend(kids)
        items.append(Item(r, nt, t))
    return items


def group_roots(roots, pair_mass, root_mass, threshold=0.10):
    """把权重交叉明显的子树并成一组：同一组必须进同一个部位，否则网格拆开后会撕裂。

    *pair_mass* {(链首a, 链首b): 两者在同一顶点上较小一方权重之和}，*root_mass* {链首: 整
    棵子树的权重量}。交叉量 >= *threshold* × 两者中较小的权重量才合并：零星几个顶点的
    交叉（实测多数模型 0.1%–2% 的顶点）拆开时改挂锚点骨就行，不值得把两大块绑死。"""
    parent = {r: r for r in roots}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), w in pair_mass.items():
        if a in parent and b in parent:
            small = min(root_mass.get(a, 0.0), root_mass.get(b, 0.0))
            if small > 0 and w >= threshold * small:
                parent[find(a)] = find(b)
    groups = {}
    for r in roots:
        groups.setdefault(find(r), []).append(r)
    return list(groups.values())


def merge_items(groups, items_by_root):
    """按 group_roots 的分组把单棵子树的 Item 合并；区域取权重最大的那一类（按骨数）。"""
    out = []
    for roots in groups:
        parts = [items_by_root[r] for r in roots]
        by_region = {}
        for it in parts:
            by_region[it.region] = by_region.get(it.region, 0) + it.total
        out.append(Item(roots[0], sum(i.non_tail for i in parts), sum(i.tail for i in parts),
                        roots=tuple(roots), region=max(by_region, key=by_region.get)))
    return out


def pack(items, base_bones, unlocked, region_slot=None, spare="leg"):
    """把各组装进四个部位，大的先放。

    不装插件：能进 arm / wst / leg 的优先放进去（同区域已经在的那个小槽优先，其次放进
    已经最满、但还放得下的那个，把整块空间留给后面的大块），放不下的进 body。

    装了插件：四个部位都是 body 那样的总数上限。给了 *region_slot*（区域 -> 槽位）时
    按区域就近放，放不下先进 *spare*，再放任何还有空的槽；没给时只回答放不放得下。"""
    room = BONE_LIMIT - base_bones
    p = Packing()
    if unlocked:
        p.capacity = {s: (None, None, room) for s in SLOTS}
    else:
        p.capacity = {"body": (None, None, room)}
        p.capacity.update({s: (SLOT_NON_TAIL, SLOT_TAIL, room) for s in SLOTS[1:]})
    p.used = {s: (0, 0) for s in SLOTS}
    regions_in = {s: set() for s in SLOTS}

    def fits(slot, item):
        nt, t = p.used[slot]
        cap_nt, cap_t, cap_total = p.capacity[slot]
        if nt + t + item.total > cap_total:
            return False
        if cap_nt is not None and nt + item.non_tail > cap_nt:
            return False
        return cap_t is None or t + item.tail <= cap_t

    def fill(slot):
        nt, t = p.used[slot]
        return nt + t

    def choose(item):
        if unlocked:
            if region_slot:
                order = [region_slot.get(item.region), spare] + list(SLOTS)
                return next((s for s in order if s in p.used and fits(s, item)), None)
            cands = [s for s in SLOTS if fits(s, item)]
            return max(cands, key=fill) if cands else None
        small = [s for s in SLOTS[1:] if fits(s, item)]
        same = [s for s in small if item.region and item.region in regions_in[s]]
        if same:
            return max(same, key=fill)
        if small:
            return max(small, key=fill)
        return "body" if fits("body", item) else None

    for item in sorted(items, key=lambda i: -i.total):
        slot = choose(item)
        if slot is None:
            p.overflow.append(item)
            continue
        nt, t = p.used[slot]
        p.used[slot] = (nt + item.non_tail, t + item.tail)
        p.placed[item.root] = slot
        regions_in[slot].add(item.region)
    return p
