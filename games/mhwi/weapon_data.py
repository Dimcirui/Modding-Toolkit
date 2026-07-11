import os
import json


def _addon_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_weapon_sets_dir():
    d = os.path.join(_addon_dir(), "assets", "mhwi", "weapon_sets")
    os.makedirs(d, exist_ok=True)
    return d


# 武器类型定义：(代码, 显示名, 默认附加部位 [(部位代码, 部位显示名), ...])
# 附加部位与主模型共享同一个模型文件夹，仅将代码中的类型前缀替换为对应部位前缀
# 例：one026 -> sld026；swo016 -> saya016；bs_one001 -> bs_sld001
WEAPON_TYPES = [
    ("two",  "大剑",   []),
    ("one",  "片手剑", [("sld", "盾")]),
    ("sou",  "双剑",   [("sou_r", "右手剑")]),
    ("swo",  "太刀",   [("saya", "刀鞘")]),
    ("ham",  "大锤",   []),
    ("hue",  "狩猎笛", []),
    ("lan",  "长枪",   [("sld", "盾")]),
    ("gun",  "铳枪",   [("sld", "盾")]),
    ("saxe", "斩斧",   []),
    ("caxe", "盾斧",   [("sld", "盾")]),
    ("rod",  "操虫棍", []),
    ("bow",  "弓",     []),
    ("hbg",  "重弩炮", []),
    ("lbg",  "轻弩炮", []),
]
WEAPON_TYPE_MAP = {t[0]: t for t in WEAPON_TYPES}

WEAPON_FILE_TYPES = ["mod3", "mrl3"]

PART_LABELS = {
    "main":   "主模型",
    "sld":    "盾",
    "saya":   "刀鞘",
    "sou_r":  "右手剑",
    "saya_r": "右手鞘",
}


def _derive_part_code(main_code, weapon_type, part_code):
    """将主模型代码的类型前缀替换为副部位前缀（保留 bs_ 前缀，如有）"""
    tagged_prefix = "bs_" + weapon_type
    if main_code.startswith(tagged_prefix):
        return "bs_" + part_code + main_code[len(tagged_prefix):]
    if main_code.startswith(weapon_type):
        return part_code + main_code[len(weapon_type):]
    return main_code.replace(weapon_type, part_code, 1)


def get_weapon_parts(weapon_type, entry):
    """返回该武器条目的实际部位列表 [(部位代码, 部位显示名, 模型代码), ...]，含主模型"""
    _, _, default_secondary = WEAPON_TYPE_MAP[weapon_type]
    main_code = entry["id"]
    parts = [("main", "主模型", main_code)]

    secondary = list(default_secondary)
    for code in entry.get("extra_parts", []):
        if not any(c == code for c, _ in secondary):
            secondary.append((code, PART_LABELS.get(code, code)))

    for code, label in secondary:
        parts.append((code, label, _derive_part_code(main_code, weapon_type, code)))
    return parts


def has_patch_model(entry):
    return bool(entry.get("has_patch"))


# ── JSON 加载 ─────────────────────────────────────────────────────

def get_mhwi_weapon_sets_callback(self, context):
    result = []
    d = _get_weapon_sets_dir()
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            name = os.path.splitext(f)[0]
            result.append((f, name, ""))
    if not result:
        result.append(('NONE', "无武器预设组", ""))
    return result


def _load_weapon_sets(filename):
    if not filename or filename == 'NONE':
        return None
    filepath = os.path.join(_get_weapon_sets_dir(), filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_weapon_entry(data, weapon_type, weapon_id):
    if not data:
        return None
    return next(
        (w for w in data.get("weapon_sets", [])
         if w["type"] == weapon_type and w["id"] == weapon_id),
        None,
    )


_weapon_items_cache = {}

def get_mhwi_weapon_callback_for_type(weapon_type, context):
    global _weapon_items_cache
    data = _load_weapon_sets(context.scene.mhw_suite_settings.mhwi_weapon_sets_file)
    items = []
    if data:
        for w in data.get("weapon_sets", []):
            if w["type"] != weapon_type:
                continue
            label = f"{w['name']}  ({w['id']})"
            items.append((w["id"], label, "", len(items)))
    if not items:
        items.append(('NONE', "无武器", "", 0))
    _weapon_items_cache[weapon_type] = items
    return items


# ── 路径构造 ──────────────────────────────────────────────────────

def make_weapon_filepath(natives_root, weapon_type, main_code, filename_code, ext):
    """
    nativePC/wp/{type}/{main_code}/mod/{filename_code}.{ext}
    主模型与所有副部位共享同一个模型文件夹（以主模型代码命名），
    各部位文件名使用自身的 model_code。
    例：nativePC/wp/swo/swo016/mod/swo016.mod3
        nativePC/wp/one/one026/mod/sld026.mod3
    """
    rel = os.path.join(
        "nativePC", "wp", weapon_type, main_code,
        "mod", f"{filename_code}.{ext}",
    )
    return os.path.join(natives_root, rel)


# ── Binding 存取 ──────────────────────────────────────────────────
# Key 格式：mhwi_wp_{type}_{main_code}_{part}_{filetype}

def _wp_bkey(weapon_type, main_code, part_code, filetype):
    return f"mhwi_wp_{weapon_type}_{main_code}_{part_code}_{filetype}".replace(" ", "_")


def get_weapon_binding(scene, weapon_type, main_code, part_code, filetype):
    return scene.get(_wp_bkey(weapon_type, main_code, part_code, filetype), "")


def set_weapon_binding(scene, weapon_type, main_code, part_code, filetype, value):
    scene[_wp_bkey(weapon_type, main_code, part_code, filetype)] = value


# 每种武器类型各自记住上次选择的武器（避免切换类型标签页时选择互相覆盖）

def get_selected_weapon(scene, weapon_type):
    return scene.get(f"mhwi_selected_weapon_{weapon_type}", "")


def set_selected_weapon(scene, weapon_type, value):
    scene[f"mhwi_selected_weapon_{weapon_type}"] = value
