"""core/physics_simplify.py — 移植物理骨骼时的精简规划（纯拓扑 / 几何，不依赖 bpy）。

为什么要有它
------------
VRC / MMD 模型的物理骨远超 MHWI 的名额：MMD 为了舞蹈里的布料效果把裙摆做成 16 列 ×
11 节的网格，相邻列之间还靠刚体关节横向连着。MHWI 的 CTC 链没有横向连接，这么密的
网格只是白占名额。这里规划三件事，执行（改权重、删骨）由调用方做：

1. **辅助骨**：自己没有权重、整棵子树也没有权重的物理骨（IK、_dummy_、_shadow_、
   3ds Max 的 Bip001 扭转骨）。它们不该进游戏，直接不移植。
2. **正前方中央链**：裙摆一圈链里正对前方的那一条。它几乎全靠碰撞防穿模，MHWI 做碰撞
   代价大，还可能穿过两腿碰撞跑到中间，所以把它的权重拆给左右两条链、整条删掉。
3. **抽稀**：每条线性链保留首尾，中间隔一根删一根；被删骨的权重按顶点在前后两根保留骨
   之间的位置线性分配。整根并给父骨会在每两节之间留下一道硬折痕。

中央链要先于抽稀做：拆权重按"同一节"对到左右链上，抽稀之后左右链的节数就对不上了。
"""

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 辅助骨
# ---------------------------------------------------------------------------

def helper_bones(physics, children_of, weighted):
    """自己没有权重、所有物理后代也都没有权重的物理骨。

    *children_of(name)* 返回子骨名序列；*weighted* 是有权重的骨名集合。"""
    memo = {}

    def has_weight(n):
        if n not in memo:
            memo[n] = n in weighted or any(
                has_weight(c) for c in children_of(n) if c in physics)
        return memo[n]

    return {n for n in physics if not has_weight(n)}


# ---------------------------------------------------------------------------
# 正前方中央链
# ---------------------------------------------------------------------------

@dataclass
class Ring:
    anchor: str
    centroid: tuple             # 链首在水平面上的中心
    azimuth: dict               # 链首 -> 相对正前方的方位角（度，+ 为 +side 一侧）
    spacing: float              # 相邻链首方位角间距的中位数
    radius: float = 0.0         # 链首到中心的平均水平距离


@dataclass
class CentreChain:
    head: str
    left: str                   # 方位角为正一侧最近的链首
    right: str                  # 方位角为负一侧最近的链首
    ring: Ring = None


def _horizontal(v, up):
    d = sum(a * b for a, b in zip(v, up))
    return tuple(a - d * b for a, b in zip(v, up))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def azimuth(vec, forward, up):
    """vec 在水平面上相对 forward 的方位角（度，-180..180）。正方向是 up × forward 一侧。"""
    h = _horizontal(vec, up)
    side = _cross(up, forward)
    x = sum(a * b for a, b in zip(h, side))
    y = sum(a * b for a, b in zip(h, forward))
    return math.degrees(math.atan2(x, y))


def find_rings(heads, anchor_of, head_pos, forward, up=(0.0, 0.0, 1.0), min_heads=4,
               max_gap=120.0):
    """把挂在同一根锚点骨上、围成一圈的链首找出来。

    一圈的判据：至少 *min_heads* 个链首，且围着中心一周最大的空缺不超过 *max_gap* 度——
    前面一排丝带、后面一束头发都不算圈。不能用 180°：一排共线的链首以自己的中心算方位，
    两端正好各占 ±90°，空缺恰好 180°。真正的裙摆一圈相邻间距只有几十度。"""
    by_anchor = {}
    for h in heads:
        by_anchor.setdefault(anchor_of(h), []).append(h)
    rings = []
    for anchor, hs in by_anchor.items():
        if anchor is None or len(hs) < min_heads:
            continue
        pts = [_horizontal(head_pos(h), up) for h in hs]
        centroid = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        az = {h: azimuth(tuple(a - b for a, b in zip(head_pos(h), centroid)), forward, up)
              for h in hs}
        ordered = sorted(az.values())
        gaps = [b - a for a, b in zip(ordered, ordered[1:])] + [ordered[0] + 360 - ordered[-1]]
        if max(gaps) > max_gap:
            continue
        gaps.sort()
        radius = sum(math.dist(p, centroid) for p in pts) / len(pts)
        rings.append(Ring(anchor, centroid, az, gaps[len(gaps) // 2], radius))
    return rings


def find_centre_chains(rings, tolerance=0.25, midline=None, forward=None,
                       up=(0.0, 0.0, 1.0), max_offset=0.25):
    """每一圈里方位角离正前方不超过 *tolerance* × 间距的那条链。

    奇数列的裙摆正中有一条（方位 0°）；偶数列的两条各偏半个间距，不算中央链。

    给了 *midline*（身体中线上的一点，如 pelvis）时，圈心横向偏离中线超过
    *max_offset* × 半径的圈不算：大腿上围一圈的饰带也是一圈，但它正前方那条不会穿过两腿。"""
    out = []
    for ring in rings:
        if midline is not None:
            side = _cross(up, forward)
            off = sum((a - b) * c for a, b, c in zip(ring.centroid, _horizontal(midline, up), side))
            if abs(off) > max_offset * ring.radius:
                continue
        head = min(ring.azimuth, key=lambda h: abs(ring.azimuth[h]))
        if abs(ring.azimuth[head]) > tolerance * ring.spacing:
            continue
        pos = [h for h, a in ring.azimuth.items() if h != head and a > ring.azimuth[head]]
        neg = [h for h, a in ring.azimuth.items() if h != head and a < ring.azimuth[head]]
        if not pos or not neg:
            continue
        left = min(pos, key=lambda h: ring.azimuth[h])
        right = max(neg, key=lambda h: ring.azimuth[h])
        out.append(CentreChain(head, left, right, ring))
    return out


def main_line(head, children_of, physics):
    """从 head 沿最深的一支走到底，返回节点序列（拆中央链权重时按"第几节"对位用）。"""
    memo = {}

    def depth(n):
        if n not in memo:
            memo[n] = 1 + max((depth(c) for c in children_of(n) if c in physics), default=0)
        return memo[n]

    line, cur = [head], head
    while True:
        kids = [c for c in children_of(cur) if c in physics]
        if not kids:
            return line
        cur = max(kids, key=depth)
        line.append(cur)


def depth_index(head, children_of, physics):
    """head 子树里每个节点离 head 的节数。"""
    out, stack = {}, [(head, 0)]
    while stack:
        n, d = stack.pop()
        out[n] = d
        stack.extend((c, d + 1) for c in children_of(n) if c in physics)
    return out


def centre_targets(centre, children_of, physics):
    """中央链每个节点 -> (左链同节骨, 右链同节骨)。左右链比它短时落到末节。"""
    left = main_line(centre.left, children_of, physics)
    right = main_line(centre.right, children_of, physics)
    return {n: (left[min(d, len(left) - 1)], right[min(d, len(right) - 1)])
            for n, d in depth_index(centre.head, children_of, physics).items()}


def side_fraction(vec, ring, centre, forward, up):
    """顶点（相对圈心的向量 *vec*）应分给左链的比例；右链拿 1 − 它。按方位角在左右两条
    链之间线性插值，超出两侧的钳到 0 / 1。"""
    a = azimuth(vec, forward, up)
    a_left, a_right = ring.azimuth[centre.left], ring.azimuth[centre.right]
    if a_left == a_right:
        return 0.5
    return min(1.0, max(0.0, (a - a_right) / (a_left - a_right)))


# ---------------------------------------------------------------------------
# 抽稀
# ---------------------------------------------------------------------------

def decimate(chains, children_of, physics, protected=(), min_len=4):
    """每条线性链（父在前）保留首尾，中间隔一根删一根。

    返回 {被删骨: (前一根保留骨, 后一根保留骨)}。只删恰好有一个物理子骨、且不在
    *protected* 里的节点——分叉骨、主链延续、分支链首都在 protected 里，删了会改动
    分叉判定已经定下的结构。碰到删不了的节点时从它重新数，保证不会连删两根。"""
    protected = set(protected)
    out = {}
    for nodes in chains:
        if len(nodes) < min_len:
            continue
        last = len(nodes) - 1
        prev_kept, pending, drop_next = nodes[0], [], True
        for n in nodes[1:last]:
            removable = (n not in protected
                         and sum(1 for c in children_of(n) if c in physics) == 1)
            if drop_next and removable:
                pending.append(n)
                drop_next = False
            else:
                for r in pending:
                    out[r] = (prev_kept, n)
                pending, prev_kept, drop_next = [], n, True
        for r in pending:
            out[r] = (prev_kept, nodes[last])
    return out


def segment_fraction(point, a, b):
    """point 在线段 a→b 上的投影参数，钳到 [0, 1]：分给 b 的比例。"""
    ab = tuple(y - x for x, y in zip(a, b))
    ap = tuple(y - x for x, y in zip(a, point))
    ll = sum(c * c for c in ab)
    if ll < 1e-12:
        return 0.5
    return min(1.0, max(0.0, sum(x * y for x, y in zip(ap, ab)) / ll))


def effective_children(name, children_of, physics, removed):
    """name 的物理子骨，越过 *removed* 里被抽掉的骨（它们的子骨上移一级）。"""
    out = []
    for c in children_of(name):
        if c in removed:
            out.extend(effective_children(c, children_of, physics, removed))
        elif c in physics:
            out.append(c)
    return out
