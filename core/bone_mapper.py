import bpy
import json
import os
import re
from urllib.parse import unquote


def _normalize_bone_name(name):
    """归一化骨骼名：去除分隔符（_ . 空格）并统一小写，用于模糊匹配"""
    return re.sub(r'[_.\s]', '', name).lower()

# --- 1. 标准骨骼定义 (The Standard) ---
STANDARD_BONE_NAMES = [
    # 躯干 (Center)
    "pelvis", "spine_01", "spine_02", "spine_03", "neck", "head",
    
    # 手臂 (Arm) - 左/右
    "clavicle_L", "upperarm_L", "forearm_L", "hand_L",
    "clavicle_R", "upperarm_R", "forearm_R", "hand_R",
    
    # 腿部 (Leg) - 左/右
    "thigh_L", "shin_L", "foot_L", "toe_L",
    "thigh_R", "shin_R", "foot_R", "toe_R",
    
    # 手指 (Fingers) - 左 (Thumb, Index, Middle, Ring, Pinky)
    "thumb_01_L", "thumb_02_L", "thumb_03_L",
    "index_01_L", "index_02_L", "index_03_L",
    "middle_01_L", "middle_02_L", "middle_03_L",
    "ring_01_L",   "ring_02_L",  "ring_03_L",
    "pinky_01_L",  "pinky_02_L", "pinky_03_L",

    # 手指 (Fingers) - 右
    "thumb_01_R", "thumb_02_R", "thumb_03_R",
    "index_01_R", "index_02_R", "index_03_R",
    "middle_01_R", "middle_02_R", "middle_03_R",
    "ring_01_R",   "ring_02_R",  "ring_03_R",
    "pinky_01_R",  "pinky_02_R", "pinky_03_R"
]

class BoneMapManager:
    def __init__(self):
        # 统一后的数据存储
        self.mapping_data = {}      # 存储 JSON 中的 "mappings" 内容
        self.preset_info = {}       # 存储 JSON 中的 "preset_info" 内容
        self.reverse_mapping = {}   # 反向查找表：仅存储每个 Standard Key 对应的第一个 Main Candidate
        self.exclude_bones = set()  # 顶级 "exclude" 字段：不是物理骨，但不属于任何标准骨骼映射

    def get_preset_path(self, filename, is_import_x=False):
        """路径获取"""
        # 当前文件在 core/ 目录下
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 根目录是 core 的上一级
        root_dir = os.path.dirname(current_dir)
        
        sub_folder = os.path.join("presets", "import" if is_import_x else "bone")
        return os.path.join(root_dir, "assets", sub_folder, filename)

    def load_preset(self, filename, is_import_x=False):
        """
        加载预设
        """
        if not filename or filename in ("NONE", "AUTO"):
            return False
        
        real_filename = os.path.basename(unquote(filename))
        filepath = self.get_preset_path(real_filename, is_import_x)
        
        if not os.path.exists(filepath):
            print(f"[Error] Preset file not found: {filepath}")
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.preset_info = data.get("preset_info", {})
            self.mapping_data = data.get("mappings", {})
            self.exclude_bones = set(data.get("exclude", []))

            # 生成反向映射 (主要为了兼容导出逻辑：GameBoneName -> StandardKey)
            # 我们只取 mappings 中每个 standard_key 的 main 列表里的第一个元素作为主键
            self.reverse_mapping = {}
            for std_key, entry in self.mapping_data.items():
                main_list = entry.get("main", [])
                if main_list:
                    primary_game_name = main_list[0]
                    self.reverse_mapping[primary_game_name] = std_key
            
            print(f"[Info] Preset Loaded Successfully: {self.preset_info.get('name')}")
            return True
            
        except Exception as e:
            print(f"[Error] Failed to parse JSON: {e}")
            return False

    def get_matches_for_standard(self, armature_obj, standard_key):
        """
        【抢占式执行核心】
        输入：标准名 (如 'upperarm_L')
        返回：(被选中的主骨名, 需要被合并的辅助骨列表)
        精确匹配优先，失败时归一化模糊匹配（忽略 _ . 空格及大小写）
        """
        if standard_key not in self.mapping_data:
            return None, []

        bone_entry = self.mapping_data[standard_key]
        existing_bones = armature_obj.data.bones.keys()

        # 归一化查找表：{归一化名: 实际骨名}，碰撞时保留第一个
        norm_lookup = {}
        for b in existing_bones:
            norm = _normalize_bone_name(b)
            if norm not in norm_lookup:
                norm_lookup[norm] = b

        def find_bone(name):
            """精确匹配优先，归一化匹配兜底，返回实际骨名"""
            if name in existing_bones:
                return name
            return norm_lookup.get(_normalize_bone_name(name))

        main_candidates = bone_entry.get("main", [])
        aux_candidates = bone_entry.get("aux", [])

        final_main = None
        to_merge = []

        # 1. 查找主骨 (抢占制：列表里第一个匹配的骨骼获胜)
        for cand in main_candidates:
            actual = find_bone(cand)
            if actual:
                if final_main is None:
                    final_main = actual
                else:
                    to_merge.append(actual)

        # 2. 查找辅助骨
        for aux in aux_candidates:
            actual = find_bone(aux)
            if actual and actual != final_main and actual not in to_merge:
                to_merge.append(actual)

        return final_main, to_merge

    # --- 辅助方法 ---
    def get_standard_from_game(self, game_bone_name):
        """输入 MhBone_013 -> 返回 pelvis"""
        return self.reverse_mapping.get(game_bone_name, None)


def _list_preset_files(is_import_x):
    """返回预设目录下所有 .json 文件名列表"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    sub_dir = os.path.join("presets", "import" if is_import_x else "bone")
    preset_dir = os.path.join(root_dir, "assets", sub_dir)
    if not os.path.exists(preset_dir):
        return []
    return sorted(f for f in os.listdir(preset_dir) if f.endswith('.json'))


def auto_detect_preset(armature_obj, is_import_x):
    """遍历所有预设文件，对每个预设在骨架的 47 个标准骨骼上做匹配测试，
    返回覆盖率最高的文件名。覆盖率 >= 95% 才视为匹配成功，否则返回 None。"""
    from .ui_config import OPTIONAL_BONES

    best_preset = None
    best_ratio = 0.0

    for filename in _list_preset_files(is_import_x):
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x):
            continue

        total = 0
        matched = 0
        for std_key in STANDARD_BONE_NAMES:
            if std_key in OPTIONAL_BONES:
                continue
            total += 1
            main, _ = mapper.get_matches_for_standard(armature_obj, std_key)
            if main:
                matched += 1

        if total == 0:
            continue
        ratio = matched / total
        if ratio > best_ratio:
            best_ratio = ratio
            best_preset = filename
        if ratio >= 1.0:
            break

    return best_preset if best_ratio >= 0.95 else None


def resolve_preset(preset_value, arm_obj, is_import_x):
    """若 preset_value 为 'AUTO'，则对 arm_obj 执行自动检测并返回匹配的预设文件名。
    返回 (resolved_filename_or_None, error_msg_or_None)。
    非 AUTO 值直接透传；AUTO 检测失败时 resolved 为 None，error_msg 说明原因。"""
    if preset_value != 'AUTO':
        return preset_value, None
    if not arm_obj or arm_obj.type != 'ARMATURE':
        return None, "自动识别需要骨架对象，但未找到可用骨架"
    result = auto_detect_preset(arm_obj, is_import_x)
    if result:
        return result, None
    return None, "自动识别未找到覆盖率 ≥ 95% 的匹配预设，请手动选择预设或新建预设"