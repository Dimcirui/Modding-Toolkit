"""core/mhwi_physics_budget.py — MHWI 物理骨名额估算（纯逻辑，不依赖 bpy）。

名额规则
--------
- 每个部位的 mod3 总骨数上限 255，其中本体骨（参考模型 86 根）每个部位都有一份，所以
  一个部位能放的物理骨 = 255 − 本体骨数。
- **不装解锁插件**：只有 body 用 300–512，受的就是上面这个总数限制；arm / wst / leg
  的非末端骨只能用 150–200（51 个），末端骨用 201–245（45 个）。末端骨没有物理、只标
  结束，挪出 150–199 是为了多省出名额。
- **装了解锁插件**：arm / wst / leg 与 body 等同，都用 300–512，各自受 255 总数限制。
- 头盔槽另有用途（helmface）、本身无物理，不参与。

末端骨按移植后的样子数：有权重的叶骨会补一根 ``_End``（叶骨本身变成非末端骨），没权重
的叶骨自己就是末端，分叉处收尾的链也补一根 ``_End``。
"""

from dataclasses import dataclass, field

BONE_LIMIT = 255
SLOT_NON_TAIL = 51      # 150–200
SLOT_TAIL = 45          # 201–245
SLOTS = ("body", "arm", "wst", "leg")


@dataclass
class Item:
    root: str
    non_tail: int
    tail: int

    @property
    def total(self):
        return self.non_tail + self.tail


@dataclass
class Packing:
    used: dict = field(default_factory=dict)      # 槽位 -> (非末端, 末端)
    capacity: dict = field(default_factory=dict)  # 槽位 -> (非末端上限, 末端上限)；None 表示与非末端共用总数
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


def pack(items, base_bones, unlocked):
    """把各子树装进四个部位，大的先放。

    不装插件：能进 arm / wst / leg 的优先放进去（放进已经最满、但还放得下的那个，把整块
    空间留给后面的大块），放不下的进 body。装了插件：四个部位都是 body 那样的总数上限。
    这里只回答"放不放得下"；按头 / 上身 / 下身归类是拆分时的事。"""
    room = BONE_LIMIT - base_bones
    p = Packing()
    if unlocked:
        p.capacity = {s: (room, None) for s in SLOTS}
    else:
        p.capacity = {"body": (room, None)}
        p.capacity.update({s: (SLOT_NON_TAIL, SLOT_TAIL) for s in SLOTS[1:]})
    p.used = {s: (0, 0) for s in SLOTS}

    def fits(slot, item):
        nt, t = p.used[slot]
        cap_nt, cap_t = p.capacity[slot]
        if cap_t is None:
            return nt + t + item.total <= cap_nt
        return nt + item.non_tail <= cap_nt and t + item.tail <= cap_t

    def fill(slot):
        nt, t = p.used[slot]
        return nt + t

    order = SLOTS if unlocked else SLOTS[1:] + ("body",)
    for item in sorted(items, key=lambda i: -i.total):
        cands = [s for s in order if fits(s, item)]
        if not cands:
            p.overflow.append(item)
            continue
        if unlocked:
            slot = max(cands, key=fill)
        else:
            small = [s for s in cands if s != "body"]
            slot = max(small, key=fill) if small else "body"
        nt, t = p.used[slot]
        p.used[slot] = (nt + item.non_tail, t + item.tail)
        p.placed[item.root] = slot
    return p
