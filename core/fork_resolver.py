"""core/fork_resolver.py — 物理骨分叉的自动判定（纯拓扑，不依赖 bpy）。

为什么要有它
------------
``modder.smart_graft`` 原先对每个分叉都是同一种处理：分叉骨补一根 ``_End``，之后每个子骨
各自成链。靠用户手动标 ``main_continue`` 来改变这一点，而实际几乎没人标。结果是主干只有
1 节时凭空多出一条 ``A-A_End`` 的两节链，主干很长、其中一支明显是延续时又被拦腰截断。

判定顺序（对每个分叉骨 F，按先后命中第一条）
--------------------------------------------
1. **marker**   子骨里有手动标了 ``main_continue`` 的：照标记走，优先级最高。
2. **stub**     F 本身就是链首（主干只有 F 这 1 节）且权重量相对后代可忽略：删掉 F，
                它的子骨各自升为链首。权重由调用方并进 F 的父骨。
3. **dominant** 有一支的深度 >= ``dominant_depth_ratio`` × 第二深的：它是主链延续。
4. **collinear** 深度不够悬殊时，若有一支与主干几乎同向、其余都明显偏离：它是主链延续。
5. **branches** 都不满足：主干在 F 收尾，每个子骨各自成链（下一层）。

层级
----
主干链是第 0 层；从第 0 层分叉出去的分支链是第 1 层。``max_branch_level`` 之后（默认
1）不再允许分支：落在第 1 层链上的分叉，不论是否命中 branches，都只留一支作延续，其余
子树 **跳过不生成链**（骨骼和权重原样保留，只是没有物理）。跳过比合并删除安全。

输入是一棵只含物理骨的树（``_End`` 骨由调用方排除）。权重量 ``mass`` 可以缺省为 None：
缺省时 stub 一律不触发，不会在没数据的情况下删骨。
"""

import math
from dataclasses import dataclass, field


@dataclass
class Params:
    #: F 的权重量 <= 比例 × 其全部后代的权重量 时视为"很轻"
    light_mass_ratio: float = 0.15
    #: 最深一支的深度 >= 比例 × 第二深的，则它是延续
    dominant_depth_ratio: float = 2.0
    #: 同向判定：最同向的一支偏离主干不超过该角度，且其余都不小于 other_min
    collinear_max_deg: float = 30.0
    collinear_other_min_deg: float = 45.0
    #: 分支链最多几层（0 = 完全不允许分支）
    max_branch_level: int = 1


@dataclass
class Node:
    name: str
    parent: str = None          # 物理父骨名；链首为 None
    children: list = field(default_factory=list)
    head: tuple = None          # 世界坐标
    anchor_head: tuple = None   # 仅链首：非物理父骨的头部，用来估主干方向
    mass: float = None          # 该骨顶点权重之和；未知为 None
    marker: bool = False        # 手动标了 main_continue
    can_drop: bool = True       # 没有非物理父骨就没地方并权重，不能当 stub 删


@dataclass
class Fork:
    bone: str
    level: int
    trunk_len: int              # 本链从链首数到 F 的节点数（含 F）
    outcome: str                # marker / stub / dominant / collinear / branches / forced
    keep: str = None            # 继续主链的子骨
    branches: list = field(default_factory=list)   # 另起一层链的子骨
    skipped: list = field(default_factory=list)    # 超出层数、不生成链的子骨
    features: dict = field(default_factory=dict)   # 子骨 -> (depth, subtree_mass, 偏离角)


@dataclass
class Chain:
    level: int
    nodes: list
    ends_at_fork: bool = False  # 因分叉收尾：F 需要 _End


@dataclass
class Resolution:
    forks: list = field(default_factory=list)
    chains: list = field(default_factory=list)
    dropped: dict = field(default_factory=dict)     # 被删的 stub -> 其物理父骨（可能为 None）
    continues: set = field(default_factory=set)     # 应视为 main_continue 的子骨
    skipped: list = field(default_factory=list)     # 不生成链的子树根


def _angle(a, b):
    la = math.sqrt(sum(c * c for c in a))
    lb = math.sqrt(sum(c * c for c in b))
    if la < 1e-9 or lb < 1e-9:
        return None
    dot = sum(x * y for x, y in zip(a, b)) / (la * lb)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def build_tree(parents, heads=None, masses=None, markers=(), anchors=None):
    """便捷构造：parents 是 {骨: 物理父骨或 None}。dict 顺序即子骨顺序。"""
    nodes = {n: Node(n, p) for n, p in parents.items()}
    for n, p in parents.items():
        if p is not None:
            nodes[p].children.append(n)
    for n, h in (heads or {}).items():
        nodes[n].head = tuple(h)
    for n, m in (masses or {}).items():
        nodes[n].mass = m
    for n in markers:
        nodes[n].marker = True
    for n, a in (anchors or {}).items():
        nodes[n].anchor_head = tuple(a)
    return nodes


def nodes_from_bones(bones, physics, head_of, masses=None, is_marker=lambda n: False):
    """从骨骼对象建树。*bones* 是带 name / parent / children 的对象序列（Blender 的
    ``Bone`` 即可），*physics* 是物理骨名集合，*head_of(name)* 返回世界坐标头部。

    物理父骨不存在（链首）的节点记下非物理父骨的头部作主干方向的起点；没有任何父骨的
    链首 ``can_drop`` 为 False。顺序沿用 *bones* 的顺序。"""
    nodes = {}
    for b in bones:
        if b.name not in physics:
            continue
        par = b.parent
        phys_parent = par.name if par is not None and par.name in physics else None
        node = Node(b.name, phys_parent, head=tuple(head_of(b.name)),
                    mass=(masses or {}).get(b.name), marker=is_marker(b.name))
        if phys_parent is None:
            node.can_drop = par is not None
            if par is not None:
                node.anchor_head = tuple(head_of(par.name))
        nodes[b.name] = node
    for b in bones:
        if b.name in nodes and nodes[b.name].parent is not None:
            nodes[nodes[b.name].parent].children.append(b.name)
    return nodes


def resolve(nodes, params=None):
    p = params or Params()
    res = Resolution()

    depth_memo, mass_memo = {}, {}

    def depth(n):
        if n not in depth_memo:
            kids = nodes[n].children
            depth_memo[n] = 1 + max((depth(c) for c in kids), default=0)
        return depth_memo[n]

    def sub_mass(n):
        if n not in mass_memo:
            m = nodes[n].mass or 0.0
            mass_memo[n] = m + sum(sub_mass(c) for c in nodes[n].children)
        return mass_memo[n]

    def features(f, prev_head, kids):
        trunk_dir = None
        if prev_head is not None and nodes[f].head is not None:
            trunk_dir = _sub(nodes[f].head, prev_head)
        out = {}
        for c in kids:
            dev = None
            if trunk_dir is not None and nodes[c].head is not None:
                dev = _angle(trunk_dir, _sub(nodes[c].head, nodes[f].head))
            out[c] = (depth(c), sub_mass(c), dev)
        return out

    def is_stub(f):
        node = nodes[f]
        if node.mass is None or not node.can_drop:
            return False
        below = sum(sub_mass(c) for c in node.children)
        return node.mass <= p.light_mass_ratio * below

    def rank_key(feat):
        d, m, dev = feat
        return (d, m, -(dev if dev is not None else 180.0))

    def pick_dominant(feat):
        order = sorted(feat, key=lambda c: rank_key(feat[c]), reverse=True)
        top, second = order[0], order[1]
        if feat[top][0] >= p.dominant_depth_ratio * feat[second][0]:
            return top, "dominant"
        devs = {c: feat[c][2] for c in feat}
        if all(d is not None for d in devs.values()):
            best = min(devs, key=devs.get)
            others = [d for c, d in devs.items() if c != best]
            if devs[best] <= p.collinear_max_deg and all(
                    d >= p.collinear_other_min_deg for d in others):
                return best, "collinear"
        return None, "branches"

    def walk(start, level):
        chain, cur = [], start
        while True:
            chain.append(cur)
            kids = nodes[cur].children
            if not kids:
                res.chains.append(Chain(level, chain))
                return
            if len(kids) == 1:
                cur = kids[0]
                continue

            prev_head = (nodes[chain[-2]].head if len(chain) > 1
                         else nodes[cur].anchor_head)
            feat = features(cur, prev_head, kids)
            fork = Fork(cur, level, len(chain), "", features=feat)
            res.forks.append(fork)

            marked = [c for c in kids if nodes[c].marker]
            if marked:
                keep, fork.outcome = marked[0], "marker"
            elif level == 0 and len(chain) == 1 and is_stub(cur):
                fork.outcome = "stub"
                res.dropped[cur] = nodes[cur].parent
                for c in kids:
                    walk(c, 0)
                return
            else:
                keep, fork.outcome = pick_dominant(feat)

            can_branch = level + 1 <= p.max_branch_level
            if keep is None and not can_branch:
                # 本该各自成链，但层数用尽：留最重的一支，其余跳过
                keep = max(feat, key=lambda c: rank_key(feat[c]))
                fork.outcome = "forced"

            rest = [c for c in kids if c != keep]
            fork.keep = keep
            if can_branch:
                fork.branches = rest
            else:
                fork.skipped = rest
                res.skipped.extend(rest)

            if keep is not None:
                res.continues.add(keep)
                cur = keep
                for c in fork.branches:
                    walk(c, level + 1)
                continue

            res.chains.append(Chain(level, chain, ends_at_fork=True))
            for c in fork.branches:
                walk(c, level + 1)
            return

    for name, node in nodes.items():
        if node.parent is None:
            walk(name, 0)
    return res


def subtree(nodes, root):
    """root 及其全部后代的名字。"""
    out, stack = [], [root]
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(nodes[n].children)
    return out


def summary(res):
    """各类结果的数量，给报告用：删掉的主干、自动选定延续的分叉、保留为分支链的分叉。"""
    return {
        "stubs": len(res.dropped),
        "auto_continue": sum(f.outcome in ("dominant", "collinear") for f in res.forks),
        "branch_forks": sum(f.outcome == "branches" for f in res.forks),
        "skipped": len(res.skipped),
    }


def format_report(res):
    """只读试算的文字报告：每个分叉判成哪类，以及判定用到的数值。"""
    lines = []
    for f in res.forks:
        head = f"[{f.outcome}] {f.bone}  层{f.level}  主干{f.trunk_len}节"
        if f.keep:
            head += f"  延续→{f.keep}"
        lines.append(head)
        for c, (d, m, dev) in f.features.items():
            tag = ("延续" if c == f.keep else "跳过" if c in f.skipped
                   else "分支" if c in f.branches else "升为链首")
            dev_s = "?" if dev is None else f"{dev:.0f}°"
            lines.append(f"    {c:<24} 深{d:<3} 权重量{m:8.2f}  偏离{dev_s:>5}  {tag}")
    if res.dropped:
        lines.append("删主干: " + ", ".join(res.dropped))
    if res.skipped:
        lines.append("跳过(超层): " + ", ".join(res.skipped))
    return "\n".join(lines)
