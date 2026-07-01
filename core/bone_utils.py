import json
import os
import bpy
import mathutils

def set_roll_to_zero_recursive(root_bones):
    """递归将骨骼 Roll 设为 0"""
    processed = set()
    for root in root_bones:
        processed.add(root)
        for child in root.children_recursive:
            processed.add(child)
    
    count = 0
    for bone in processed:
        bone.roll = 0
        count += 1
    return count

def add_vertical_tail_bone(edit_bones, selected_bones):
    """
    为选中的末端骨骼添加垂直子骨骼
    """
    count = 0
    for bone in selected_bones:
        
        tail_pos = bone.tail.copy()
        
        # 创建新骨骼
        try:
            new_bone = edit_bones.new(bone.name + "_tail")
            new_bone.head = tail_pos
            # 默认长度为父骨骼长度，若父骨骼长度为0则设为0.1
            length = bone.length if bone.length > 0 else 0.1
            # 垂直向上 (Z轴)
            new_bone.tail = tail_pos + mathutils.Vector((0, 0, length))
            
            new_bone.parent = bone
            new_bone.use_connect = False
            
            count += 1
        except Exception as e:
            print(f"Error adding tail for {bone.name}: {e}")
            
    return count

def mirror_bone_transform(edit_bones, bone_names):
    """以 X+ 为基准镜像对齐 X-"""
    if len(bone_names) != 2:
        return False, "请选中两个骨骼"
    
    b1 = edit_bones.get(bone_names[0])
    b2 = edit_bones.get(bone_names[1])
    
    if not b1 or not b2:
        return False, "骨骼未找到"
        
    # 判定基准 (X > 0 为基准)
    if b1.head.x > 0:
        ref, mirror = b1, b2
    else:
        ref, mirror = b2, b1
        
    # 执行镜像
    mirror.head.x = -ref.head.x
    mirror.head.y = ref.head.y
    mirror.head.z = ref.head.z
    
    mirror.tail.x = -ref.tail.x
    mirror.tail.y = ref.tail.y
    mirror.tail.z = ref.tail.z
    
    # 同步 Roll (通常镜像需要取反或保持，视骨骼轴向而定，这里简单复制处理，视情况可调整)
    mirror.roll = -ref.roll 
    
    return True, "已将 %s 对齐到 %s", mirror.name, ref.name

def propagate_movement(bone, offset_vec):
    """递归移动子骨骼"""
    for child in bone.children:
        if child.use_connect:
            child.tail += offset_vec
        else:
            child.head += offset_vec
            child.tail += offset_vec
        propagate_movement(child, offset_vec)


def align_armatures_by_name(source_arm, target_arm, mode='POS_ONLY', skip_fn=None):
    """
    按骨骼名对齐两个骨架（调用前应处于 OBJECT 模式）。
    mode: 'FULL' = head+tail 全部对齐；'POS_ONLY' = 仅对齐 head，保持长度方向
    skip_fn: callable(bone_name) -> bool，返回 True 则跳过该骨骼
    返回对齐骨骼数。执行后处于 OBJECT 模式，active 对象为 target_arm。
    """
    s_mat = source_arm.matrix_world

    # 在 EDIT 模式读取源骨架，直接取 roll 数值
    bpy.context.view_layer.objects.active = source_arm
    bpy.ops.object.mode_set(mode='EDIT')
    src_data = {}
    for b in source_arm.data.edit_bones:
        src_data[b.name] = (s_mat @ b.head, s_mat @ b.tail, b.roll)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = target_arm
    bpy.ops.object.mode_set(mode='EDIT')
    t_mat_inv = target_arm.matrix_world.inverted()

    count = 0
    for b in target_arm.data.edit_bones:
        if b.name not in src_data:
            continue
        if skip_fn and skip_fn(b.name):
            continue
        src_head, src_tail, src_roll = src_data[b.name]
        old_head = b.head.copy()
        new_head = t_mat_inv @ src_head
        if mode == 'FULL':
            b.head = new_head
            b.tail = t_mat_inv @ src_tail
            # head/tail 完全照抄后骨骼方向与源一致，roll 定义基于骨骼方向，直接照抄即可精确对齐
            b.roll = src_roll
        elif mode == 'POS_ROLL':
            orig_vec = b.tail - b.head
            b.head = new_head
            b.tail = new_head + orig_vec
            b.roll = src_roll
        else:
            orig_vec = b.tail - b.head
            b.head = new_head
            b.tail = new_head + orig_vec
        propagate_movement(b, new_head - old_head)
        count += 1

    bpy.ops.object.mode_set(mode='OBJECT')
    return count

def find_bone_smart(bones, name):
    """
    智能查找骨骼：
    1. 精确查找
    2. 尝试互换 'MhBone_' 和 'bonefunction_' 前缀
    3. 忽略大小写查找 (兼容 3.x)
    """
    # 1. 精确匹配
    if name in bones:
        return bones[name]
    
    # 2. 前缀互换
    alt_name = None
    if "MhBone_" in name:
        alt_name = name.replace("MhBone_", "bonefunction_")
    elif "bonefunction_" in name:
        alt_name = name.replace("bonefunction_", "MhBone_")
    
    if alt_name and alt_name in bones:
        return bones[alt_name]
    
    # 3. 最后的手段：忽略大小写遍历 (较慢，仅作兜底)
    target_lower = name.lower()
    alt_lower = alt_name.lower() if alt_name else ""
    
    for b in bones:
        b_lower = b.name.lower()
        if b_lower == target_lower or (alt_lower and b_lower == alt_lower):
            return b
            
    return None

# 【关键】：全局缓存列表，防止 Blender C 层持有的字符串指针因 Python GC 变成野指针
# 这是 Blender EnumProperty 动态回调的已知陷阱：回调返回的列表必须有持久引用
_import_preset_cache = []
_target_preset_cache = []

def _read_preset_meta(filepath):
    """读取 preset_info 中的 name 和 category，文件损坏时 fallback。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            pi = json.load(f).get('preset_info', {})
        return pi.get('name', ''), pi.get('category', '')
    except Exception:
        return '', ''

def get_preset_items(subdir):
    """
    扫描指定子目录下的所有 .json 文件，按分类分组并插入分隔标题。
    subdir: "presets/import" 或 "presets/bone"
    显示名和分类均从 JSON 内 preset_info 读取，与文件名无关。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    preset_dir = os.path.join(root_dir, "assets", subdir)

    if not os.path.exists(preset_dir):
        return [('NONE', "未找到文件夹", "请检查 assets 目录")]

    files = sorted(f for f in os.listdir(preset_dir) if f.endswith('.json'))
    if not files:
        return [('NONE', "无预设文件", "")]

    # 按分类分组，name/category 均从 JSON 内读取
    grouped = {}
    cat_order = ['怪猎系', 'Capcom RE引擎', '通用平台', '其他游戏']
    for f in files:
        filepath = os.path.join(preset_dir, f)
        name, cat = _read_preset_meta(filepath)
        if not name:
            name = os.path.splitext(f)[0]  # fallback 到文件名 stem
        if not cat or cat not in cat_order:
            cat = '其他游戏'               # fallback 分类
        grouped.setdefault(cat, []).append((f, name))

    items = []
    for cat in cat_order:
        if cat not in grouped:
            continue
        items.append(('', cat, ''))  # 分组标题（不可选）
        for f, display_name in grouped[cat]:
            items.append((f, display_name, f"加载 {display_name} 预设"))

    return items if items else [('NONE', "无预设文件", "")]

# --- 回调函数接口 ---

def get_import_presets_callback(self, context):
    _import_preset_cache.clear()
    _import_preset_cache.append(("AUTO", "自动识别", "根据骨架骨骼覆盖率自动选择最匹配的预设"))
    _import_preset_cache.extend(get_preset_items("presets/import"))
    return _import_preset_cache

def get_target_presets_callback(self, context):
    _target_preset_cache.clear()
    _target_preset_cache.append(("AUTO", "自动识别", "根据骨架骨骼覆盖率自动选择最匹配的预设"))
    _target_preset_cache.extend(get_preset_items("presets/bone"))
    return _target_preset_cache

_VALID_ALIGN_MODES = ('FULL', 'POS_ONLY', 'POS_ROLL')

def get_default_align_mode(filename):
    """读取目标(Y)预设 preset_info.default_align_mode，未指定或预设不存在时回退 POS_ONLY。"""
    if not filename or filename in ("NONE", "AUTO"):
        return 'POS_ONLY'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    filepath = os.path.join(root_dir, "assets", "presets", "bone", os.path.basename(filename))
    if not os.path.exists(filepath):
        return 'POS_ONLY'
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        mode = data.get('preset_info', {}).get('default_align_mode', 'POS_ONLY')
        return mode if mode in _VALID_ALIGN_MODES else 'POS_ONLY'
    except Exception:
        return 'POS_ONLY'