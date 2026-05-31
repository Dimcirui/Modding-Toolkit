"""
物理链分类器 (Chain Classifier)

根据链首骨骼名（中文/拼音/英文/罗马音）+ 链深度，推测物理类型，
并从 physics_presets.json 取对应物理参数。

用于「猜测分组」模式：先对所有链分类，再按类型分组创建 Chain Settings。
"""

import os
import re
import json

_PRESETS_CACHE = None


def _presets_path():
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_dir, "assets", "presets", "physics", "physics_presets.json")


def _load_presets():
    """加载并缓存 physics_presets.json。"""
    global _PRESETS_CACHE
    if _PRESETS_CACHE is None:
        try:
            with open(_presets_path(), encoding="utf-8") as f:
                _PRESETS_CACHE = json.load(f)
        except (OSError, json.JSONDecodeError):
            _PRESETS_CACHE = {"_meta": {}, "types": {}}
    return _PRESETS_CACHE


def get_physics_params(type_key):
    """按类型键取物理参数字典，未知类型返回 None。"""
    data = _load_presets()
    entry = data.get("types", {}).get(type_key)
    if entry is None:
        return None
    return dict(entry.get("params", {}))


# ============================================================
# 关键字规则表（按优先级从上到下，命中即返回）
# 每条: (type_key, latin_keywords, cjk_keywords)
#   latin: 拉丁字母关键字（英文 / 拼音 / 罗马音），len>=4 用子串匹配，len<=3 用整词匹配
#   cjk:   中文关键字，始终用子串匹配
# ============================================================

_RULES = [
    # —— 配饰（最高优先，避免被 hair/tail 吞掉）——
    ("accessory_ribbon",
     ["ribbon", "ribon", "bow", "bowtie", "hairband", "headband",
      "necktie", "cravat", "chou", "choucho", "bunny", "sidai", "hudiejie"],
     ["丝带", "緞带", "缎带", "蝴蝶结", "蝴蝶", "发带", "髮带", "领带", "領带", "领巾", "兔耳"]),
    ("accessory_bouncy",
     ["earring", "necklace", "pendant", "charm", "bead", "jewel", "ornament",
      "iyaringu", "kazari", "nekkuresu", "erhuan"],
     ["耳饰", "耳環", "耳环", "项链", "項鍊", "项鍊", "吊坠", "吊墜", "饰品", "飾品", "珠"]),

    # —— 发型中的特例（必须在 fur_tail 之前，因含 "tail"）——
    ("hair_twintail",
     ["twintail", "twin", "twinteru", "tsuinteru", "ponytail", "pony", "mawei"],
     ["双马尾", "雙馬尾", "马尾", "馬尾", "双尾", "雙尾"]),
    ("hair_braided",
     ["braid", "braided", "plait", "ami", "mitsuami", "bianzi"],
     ["编发", "編髮", "辫子", "辮子", "麻花", "辫", "辮"]),

    # —— 尾 / 毛 ——
    ("fur_tail",
     ["tail", "shippo", "weiba"],
     ["尾巴", "尾", "尻尾"]),
    ("fur_dense",
     ["fur", "mane", "fluff", "tategami", "maomao"],
     ["鬃毛", "鬃", "体毛", "體毛", "绒毛", "絨毛", "毛发", "毛髮", "毛"]),

    # —— 布料 ——
    ("cloth_skirt",
     ["skirt", "dress", "frill", "ruffle", "sukato", "qunzi", "qun"],
     ["裙摆", "裙襬", "裙子", "裙", "百褶"]),
    ("cloth_coat",
     ["coat", "mantle", "manto", "cape", "cloak", "robe", "jacket", "kooto",
      "hanten", "pifeng", "dayi"],
     ["外套", "斗篷", "披风", "披風", "大衣", "长袍", "長袍", "夹克", "夾克", "披肩"]),
    ("cloth_sleeves",
     ["sleeve", "sleeves", "cuff", "sode", "xiuzi"],
     ["袖口", "宽袖", "寬袖", "袖"]),
    ("cloth_hanging",
     ["drape", "sash", "strap", "loincloth", "apron", "flap", "tassle", "tassel",
      "suibu", "maedare", "yaobu"],
     ["垂布", "腰布", "飘带", "飄帶", "围裙", "圍裙", "缨穗", "纓穗", "穗"]),

    # —— 身体物理 ——
    ("body_jiggle",
     ["breast", "bust", "boob", "butt", "bottom", "belly", "jiggle",
      "mune", "oppai", "ketsu", "hara", "xiong", "tun"],
     ["胸", "乳", "臀", "腹", "肚", "屁股"]),

    # —— 发型（具体描述优先）——
    ("hair_front_bangs",
     ["bang", "bangs", "fringe", "front", "maegami", "liuhai"],
     ["刘海", "瀏海", "前发", "前髮", "额发", "額髮", "鬓", "鬢"]),
    ("hair_long_curly",
     ["curly", "curl", "wave", "fluffy"],
     ["卷发", "捲髮", "卷", "蓬松", "蓬鬆"]),
    ("hair_long_wavy",
     ["wavy", "nami"],
     ["波浪", "波纹", "波紋"]),
    ("hair_long_straight",
     ["straight", "nagagami"],
     ["直发", "直髮", "长直", "長直"]),
    ("hair_short",
     ["short", "bob", "tanpatsu"],
     ["短发", "短髮", "碎发", "碎髮"]),
    ("hair_medium",
     ["side", "yokogami", "sokogami"],
     ["侧发", "側髮", "中发", "中髮"]),
]

# 通用发型关键字（无长度描述时按深度回退）
_GENERIC_HAIR_LATIN = ["hair", "kami", "toufa"]
_GENERIC_HAIR_CJK = ["头发", "頭髮", "头髮", "髪", "发", "髮"]

# 所有发型类型（用于区域二次筛选）
_HAIR_TYPES = {
    "hair_short", "hair_medium", "hair_long_wavy", "hair_long_straight",
    "hair_long_curly", "hair_braided", "hair_twintail", "hair_front_bangs",
}

# 身体父级 → 区域（关键字子串匹配，中英/拼音/罗马音混排）
_REGION_KEYWORDS = {
    "head":  ["head", "atama", "face", "skull", "头", "頭", "脸", "臉"],
    "chest": ["chest", "breast", "bust", "mune", "胸", "乳"],
    "waist": ["waist", "hip", "pelvis", "koshi", "sacrum", "cog", "腰", "骨盆", "臀"],
    "arm":   ["arm", "forearm", "elbow", "wrist", "hand", "shoulder", "clavicle",
              "ude", "kata", "腕", "肘", "手", "肩"],
    "leg":   ["leg", "thigh", "knee", "shin", "calf", "foot", "ashi",
              "腿", "膝", "脚", "足"],
}

# 各区域「解剖上不可能」的类型（保守，仅列明显冲突）。命中则丢弃该猜测
_REGION_IMPLAUSIBLE = {
    "head":  {"fur_tail", "cloth_skirt"},
    "chest": {"fur_tail", "cloth_skirt"} | _HAIR_TYPES,
    "waist": set(_HAIR_TYPES),
    "arm":   {"fur_tail", "cloth_skirt"} | _HAIR_TYPES,
    "leg":   set(_HAIR_TYPES),
}

# 各区域在「无名字匹配」时的兜底类型（'hair' 表示按深度选发型；None 表示不猜）
_REGION_DEFAULT = {
    "head":  "hair",
    "chest": "body_jiggle",
    "waist": "cloth_skirt",
    "arm":   "cloth_sleeves",
    "leg":   None,
}


def _detect_region(parent_name):
    """身体父级名 → 区域键，无法识别返回 None。"""
    if not parent_name:
        return None
    low = parent_name.lower()
    for region, kws in _REGION_KEYWORDS.items():
        if any(kw in low for kw in kws):
            return region
    return None


def _body_parent_name(bone, physics_bones):
    """沿父链向上走到第一个非物理骨（身体锚点），返回其名；无则返回空串。"""
    p = bone.parent
    while p is not None and p.name in physics_bones:
        p = p.parent
    return p.name if p is not None else ""


def _generic_hair():
    """通用发型兜底类型。depth 不可靠（短发可能骨骼密集、长发可能稀疏），
    故不按 depth 切分，统一用 hair_generic（半重力自然下垂的安全默认）。"""
    return "hair_generic"

# 链节点变体后缀（左右镜像 / 编号 / End）
_VARIANT_SUFFIX = re.compile(r'(\.\d+|[._][LRlr]|_[Ee]nd)+$')
# camelCase 分词边界
_CAMEL = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def _base_name(name):
    """去掉变体后缀，得到基名（用于左右/编号变体共享分类）。"""
    return _VARIANT_SUFFIX.sub('', name)


def _tokenize(name):
    """拆分骨骼名为小写 token 集合（按分隔符 + camelCase）。"""
    parts = re.split(r'[_.\s\-]+', _CAMEL.sub(' ', name))
    return {p.lower() for p in parts if p}


def _match_latin(keywords, norm, tokens):
    for kw in keywords:
        if len(kw) <= 3:
            if kw in tokens:
                return True
        elif kw in norm:
            return True
    return False


def _match_cjk(keywords, name):
    return any(kw in name for kw in keywords)


def infer_physics_type(bone_name, depth):
    """根据骨骼名推测类型键，无匹配返回 None。（depth 当前未用于发型细分，保留参数以备扩展）"""
    norm = bone_name.lower()
    tokens = _tokenize(bone_name)

    for type_key, latin_kw, cjk_kw in _RULES:
        if _match_latin(latin_kw, norm, tokens) or _match_cjk(cjk_kw, bone_name):
            return type_key

    # 通用发型（只有 hair/髪/发，无风格词）→ 通用兜底，不按 depth 切分
    if _match_latin(_GENERIC_HAIR_LATIN, norm, tokens) or _match_cjk(_GENERIC_HAIR_CJK, bone_name):
        return _generic_hair()

    return None


def measure_chain_depth(head_data_bone, physics_bones):
    """测量以 head 为根的物理链最大深度（沿物理子骨递归，排除 _End）。"""
    best = [0]

    def walk(bone, d):
        if d > best[0]:
            best[0] = d
        for c in bone.children:
            if c.name in physics_bones and not c.name.endswith("_End"):
                walk(c, d + 1)

    walk(head_data_bone, 1)
    return best[0]


def classify_heads(heads, physics_bones):
    """对链首分类。

    heads: dict {bone_name: data_bone}
    physics_bones: 物理骨骼名集合

    流程：
      1. 按骨骼名 + 链深度推测类型
      2. 身体父级区域二次筛选：丢弃解剖上不可能的猜测（如头部出现尾/裙）
      3. 变体传播：同基名未匹配者继承已匹配兄弟
      4. 区域兜底：仍无匹配的，用身体父级区域给默认类型
    返回 {bone_name: type_key | None}。
    """
    # info[name] = [type_or_None, region, depth]
    info = {}
    for name, bone in heads.items():
        depth = measure_chain_depth(bone, physics_bones)
        t = infer_physics_type(name, depth)
        region = _detect_region(_body_parent_name(bone, physics_bones))
        if t is not None and region is not None and t in _REGION_IMPLAUSIBLE.get(region, ()):
            t = None  # 名字猜测与身体部位矛盾，丢弃
        info[name] = [t, region, depth]

    # 变体传播：同基名的链，未匹配者继承已匹配兄弟的类型
    base_to_type = {}
    for name, rec in info.items():
        if rec[0] is not None:
            base_to_type.setdefault(_base_name(name), rec[0])
    for name, rec in info.items():
        if rec[0] is None:
            b = _base_name(name)
            if b in base_to_type:
                rec[0] = base_to_type[b]

    # 区域兜底：仍为 None 的，按身体父级区域给默认
    for rec in info.values():
        if rec[0] is None and rec[1] is not None:
            default = _REGION_DEFAULT.get(rec[1])
            if default == "hair":
                rec[0] = _generic_hair()
            elif default is not None:
                rec[0] = default

    return {name: rec[0] for name, rec in info.items()}
