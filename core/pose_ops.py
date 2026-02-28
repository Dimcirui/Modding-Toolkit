"""
姿态转换模块 (Pose Convert)

三层架构：
1. 方向计算: 简易工具，仅旋转上臂到水平
2. RE Engine 矩阵归零: RE Engine 专用的绝对矩阵覆盖
3. 姿态变换记录器: 通用相对变换系统
   - 录制: 从 A 姿态和 B 姿态骨架计算每根骨骼的相对旋转变换
   - 正向应用 (A→B): 施加变换
   - 逆向应用 (B→A): 施加逆变换
"""

import bpy
import json
import os
import copy
import mathutils
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from .bone_utils import get_import_presets_callback


# ============================================================
# 路径与枚举
# ============================================================

def _get_pose_presets_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(addon_dir, "assets", "pose_presets")
    os.makedirs(d, exist_ok=True)
    return d

_pose_preset_cache = []

def get_pose_presets_callback(self, context):
    global _pose_preset_cache
    _pose_preset_cache = []
    d = _get_pose_presets_dir()
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                name = f.replace('.json', '')
                _pose_preset_cache.append((f, name, ""))
    if not _pose_preset_cache:
        _pose_preset_cache.append(('NONE', "无记录", ""))
    return _pose_preset_cache


# ============================================================
# 1. 方向计算（独立简易工具）
# ============================================================

class MODDER_OT_TPoseDirection(bpy.types.Operator):
    """仅将上臂旋转到水平方向，适用于简单的 A-Pose 骨架（如MMD），如果无法正确运作，请使用更通用的姿态变换记录器"""
    bl_idname = "modder.tpose_direction"
    bl_label = "方向计算 (简单T转A)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}
        
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.pose_import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "无法加载骨架预设")
            return {'CANCELLED'}
        
        arm_mw = arm_obj.matrix_world
        targets = [("upperarm_L", 1.0), ("upperarm_R", -1.0)]
        
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        pose_bones = arm_obj.pose.bones
        count = 0
        
        for std_key, sign in targets:
            main_name, _ = mapper.get_matches_for_standard(arm_obj, std_key)
            if not main_name or main_name not in pose_bones:
                continue
            
            pb = pose_bones[main_name]
            bone = arm_obj.data.bones[main_name]
            bone_vec = (arm_mw.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()
            target_dir = mathutils.Vector((sign, 0.0, 0.0))
            rotation = bone_vec.rotation_difference(target_dir)
            
            current_mat = pb.matrix.copy()
            rot_mat = rotation.to_matrix().to_4x4()
            new_mat = rot_mat @ current_mat
            new_mat[0][3] = current_mat[0][3]
            new_mat[1][3] = current_mat[1][3]
            new_mat[2][3] = current_mat[2][3]
            pb.matrix = new_mat
            bpy.context.view_layer.update()
            count += 1
        
        if count == 0:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'WARNING'}, "未找到上臂骨骼")
            return {'CANCELLED'}
        
        mesh_count = _apply_and_rebind(arm_obj)
        self.report({'INFO'}, f"方向计算完成: {count} 根上臂骨骼, {mesh_count} 个网格")
        return {'FINISHED'}


# ============================================================
# 2. RE Engine 矩阵归零（独立特殊功能）
# ============================================================

class MODDER_OT_TPoseMatrixZero(bpy.types.Operator):
    """RE Engine 专用: 重置肢体骨骼旋转矩阵为 T-Pose (适用于荒野/街霸6/生化4等)"""
    bl_idname = "modder.tpose_matrix_zero"
    bl_label = "RE Engine 矩阵归零"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}
        
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.pose_import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "无法加载骨架预设")
            return {'CANCELLED'}
        
        tpose_std_keys = [
            "clavicle_L", "upperarm_L", "forearm_L", "hand_L",
            "clavicle_R", "upperarm_R", "forearm_R", "hand_R",
            "thumb_01_L", "thumb_02_L", "thumb_03_L",
            "index_01_L", "index_02_L", "index_03_L",
            "middle_01_L", "middle_02_L", "middle_03_L",
            "ring_01_L", "ring_02_L", "ring_03_L",
            "pinky_01_L", "pinky_02_L", "pinky_03_L",
            "thumb_01_R", "thumb_02_R", "thumb_03_R",
            "index_01_R", "index_02_R", "index_03_R",
            "middle_01_R", "middle_02_R", "middle_03_R",
            "ring_01_R", "ring_02_R", "ring_03_R",
            "pinky_01_R", "pinky_02_R", "pinky_03_R",
            "thigh_L", "shin_L", "foot_L", "toe_L",
            "thigh_R", "shin_R", "foot_R", "toe_R",
        ]
        
        bone_names = []
        existing = arm_obj.data.bones.keys()
        for std_key in tpose_std_keys:
            main_name, _ = mapper.get_matches_for_standard(arm_obj, std_key)
            if main_name and main_name in existing:
                bone_names.append(main_name)
        
        if not bone_names:
            self.report({'ERROR'}, "预设中没有匹配到任何骨骼")
            return {'CANCELLED'}
        
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        pose_bones = arm_obj.pose.bones
        count = 0
        
        for bone_name in bone_names:
            if bone_name not in pose_bones:
                continue
            pb = pose_bones[bone_name]
            zero = copy.deepcopy(pb.matrix)
            zero[0][0] = 1.0;  zero[0][1] = 0.0;  zero[0][2] = 0.0
            zero[1][0] = 0.0;  zero[1][1] = 0.0;  zero[1][2] = -1.0
            zero[2][0] = 0.0;  zero[2][1] = 1.0;  zero[2][2] = 0.0
            zero[3][0] = 0.0;  zero[3][1] = 0.0;  zero[3][2] = 0.0;  zero[3][3] = 1.0
            pb.matrix = zero
            bpy.context.view_layer.update()
            count += 1
        
        mesh_count = _apply_and_rebind(arm_obj)
        self.report({'INFO'}, f"RE Engine 矩阵归零完成: {count} 根骨骼, {mesh_count} 个网格")
        return {'FINISHED'}


# ============================================================
# 3. 姿态变换记录器（相对变换系统）
# ============================================================

class MODDER_OT_RecordTransform(bpy.types.Operator):
    """录制相对变换: 先选 A 姿态骨架，再 Ctrl 选 B 姿态骨架，计算并保存 A->B 的变换"""
    bl_idname = "modder.record_transform"
    bl_label = "录制变换"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_name: bpy.props.StringProperty(
        name="名称",
        default="新姿态变换",
        description="保存的变换记录文件名 (例: MMD A-Pose到T-Pose)"
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "preset_name")
        self.layout.label(text="先选 A 姿态骨架, 再 Ctrl 选 B 姿态骨架", icon='INFO')
    
    def execute(self, context):
        # 1. 获取两个骨架
        selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected_arms) < 2:
            self.report({'ERROR'}, "请选中两个骨架: 先选 A 姿态, 再 Ctrl 选 B 姿态")
            return {'CANCELLED'}
        
        if not self.preset_name.strip():
            self.report({'ERROR'}, "名称不能为空")
            return {'CANCELLED'}
        
        # 活动对象 = B 姿态 (后选的), 另一个 = A 姿态 (先选的)
        arm_b = context.active_object
        arm_a = None
        for obj in selected_arms:
            if obj != arm_b:
                arm_a = obj
                break
        
        if not arm_a or not arm_b or arm_a.type != 'ARMATURE' or arm_b.type != 'ARMATURE':
            self.report({'ERROR'}, "请确保选中了两个骨架对象")
            return {'CANCELLED'}
        
        # 2. 收集 A 骨架每根骨骼的局部朝向 (相对于父级的 rest pose 朝向)
        local_rots_a = {}
        for bone in arm_a.data.bones:
            if bone.parent:
                local_mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_mat = bone.matrix_local.copy()
            local_rots_a[bone.name] = local_mat.to_quaternion()
        
        # 3. 收集 B 骨架每根骨骼的局部朝向
        local_rots_b = {}
        for bone in arm_b.data.bones:
            if bone.parent:
                local_mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_mat = bone.matrix_local.copy()
            local_rots_b[bone.name] = local_mat.to_quaternion()
        
        # 4. 计算相对变换: delta = Qb × Qa⁻¹ (每根骨骼各自的局部旋转差异)
        #    这是骨骼相对于自身父级的旋转变化量, 不含父子累积
        transforms = {}
        common_bones = set(local_rots_a.keys()) & set(local_rots_b.keys())
        
        if not common_bones:
            self.report({'ERROR'}, "两个骨架没有同名骨骼")
            return {'CANCELLED'}
        
        significant_count = 0
        for bone_name in common_bones:
            qa = local_rots_a[bone_name]
            qb = local_rots_b[bone_name]
            
            # delta = Qb × Qa⁻¹ (从 A 朝向旋转到 B 朝向的变化量)
            qa_inv = qa.copy()
            qa_inv.invert()
            delta = qb @ qa_inv
            
            # 检查是否接近单位四元数 (即几乎没有变化的骨骼)
            identity_dot = abs(delta.w)
            if identity_dot > 0.9999:
                continue
            
            transforms[bone_name] = [delta.w, delta.x, delta.y, delta.z]
            significant_count += 1
        
        if significant_count == 0:
            self.report({'WARNING'}, "两个骨架的姿态几乎相同, 没有显著变换可记录")
            return {'CANCELLED'}
        
        # 5. 保存 JSON
        data = {
            "type": "pose_relative_transform",
            "version": "2.0",
            "source_a": arm_a.data.name,
            "source_b": arm_b.data.name,
            "description": f"{arm_a.name} -> {arm_b.name}",
            "bone_count": significant_count,
            "transforms": transforms
        }
        
        filename = self.preset_name.strip()
        for ch in '<>:"/\\|?*':
            filename = filename.replace(ch, '')
        filepath = os.path.join(_get_pose_presets_dir(), filename + ".json")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.report({'INFO'}, f"已录制 {significant_count} 根骨骼的变换 -> {filename}.json")
        except Exception as e:
            self.report({'ERROR'}, f"保存失败: {e}")
            return {'CANCELLED'}
        
        # 恢复活动对象
        bpy.context.view_layer.objects.active = arm_b
        return {'FINISHED'}


class MODDER_OT_ApplyTransformForward(bpy.types.Operator):
    """正向应用变换 (A->B): 将选中骨架从 A 姿态转换为 B 姿态"""
    bl_idname = "modder.apply_transform_forward"
    bl_label = "正向 (A->B)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        return _apply_transform(self, context, inverse=False)


class MODDER_OT_ApplyTransformInverse(bpy.types.Operator):
    """逆向应用变换 (B->A): 将选中骨架从 B 姿态转换回 A 姿态"""
    bl_idname = "modder.apply_transform_inverse"
    bl_label = "逆向 (B->A)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        return _apply_transform(self, context, inverse=True)


def _apply_transform(operator, context, inverse=False):
    """应用相对变换的核心逻辑 (正向或逆向)"""
    settings = context.scene.mhw_suite_settings
    arm_obj = context.active_object
    
    if not arm_obj or arm_obj.type != 'ARMATURE':
        operator.report({'ERROR'}, "请先选中一个骨架")
        return {'CANCELLED'}
    
    selected_file = settings.pose_preset_enum
    if not selected_file or selected_file == 'NONE':
        operator.report({'ERROR'}, "未选择变换记录")
        return {'CANCELLED'}
    
    # 读取 JSON
    filepath = os.path.join(_get_pose_presets_dir(), selected_file)
    if not os.path.exists(filepath):
        operator.report({'ERROR'}, f"文件不存在: {selected_file}")
        return {'CANCELLED'}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        operator.report({'ERROR'}, f"读取失败: {e}")
        return {'CANCELLED'}
    
    transforms = data.get("transforms", {})
    if not transforms:
        operator.report({'ERROR'}, "记录文件中没有变换数据")
        return {'CANCELLED'}
    
    # 通过骨架预设建立骨骼名映射 (变换记录中的名字 -> 目标骨架的名字)
    mapper = BoneMapManager()
    bone_mapping = {}  # {target_bone_name: transform_bone_name}
    
    if mapper.load_preset(settings.pose_import_preset_enum, is_import_x=True):
        # 通过预设的标准键做桥接
        # 先建立: transform_bone_name -> std_key 的映射
        # 再建立: std_key -> target_bone_name 的映射
        # 注意: transforms 里的骨骼名来自录制时的骨架, 可能和目标骨架不同
        for std_key in STANDARD_BONE_NAMES:
            tgt_name, _ = mapper.get_matches_for_standard(arm_obj, std_key)
            if tgt_name:
                # 检查 transforms 里有没有这个名字
                if tgt_name in transforms:
                    bone_mapping[tgt_name] = tgt_name
    
    # 同名匹配兜底
    if not bone_mapping:
        for bone in arm_obj.data.bones:
            if bone.name in transforms:
                bone_mapping[bone.name] = bone.name
    
    if not bone_mapping:
        operator.report({'ERROR'}, "骨架与变换记录之间找不到对应的骨骼 (请检查骨架预设)")
        return {'CANCELLED'}
    
    # 按骨骼层级顺序排列 (从根到叶)
    # 使用骨架自身的骨骼顺序, 它天然是父级在前子级在后
    ordered_bones = []
    for bone in arm_obj.data.bones:
        if bone.name in bone_mapping:
            ordered_bones.append(bone.name)
    
    # 应用变换
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')
    pose_bones = arm_obj.pose.bones
    count = 0
    
    for tgt_name in ordered_bones:
        if tgt_name not in pose_bones:
            continue
        
        transform_name = bone_mapping[tgt_name]
        quat_data = transforms[transform_name]
        delta = mathutils.Quaternion((quat_data[0], quat_data[1], quat_data[2], quat_data[3]))
        
        if inverse:
            delta.invert()
        
        pb = pose_bones[tgt_name]
        bone = arm_obj.data.bones[tgt_name]
        
        # delta 是在父级空间中的旋转差 (parent-relative)
        # matrix_basis 是在骨骼自身的 rest 朝向空间中的变换
        # 需要将 delta 从父级空间转换到骨骼 rest 朝向空间:
        #   basis_rot = rest_rot⁻¹ × delta × rest_rot
        # 其中 rest_rot 是骨骼相对于父级的 rest 朝向
        if bone.parent:
            rest_local = bone.parent.matrix_local.inverted() @ bone.matrix_local
        else:
            rest_local = bone.matrix_local.copy()
        
        rest_rot = rest_local.to_quaternion()
        rest_rot_inv = rest_rot.copy()
        rest_rot_inv.invert()
        
        # 转换到骨骼局部空间
        local_delta = rest_rot_inv @ delta @ rest_rot
        
        # 构建旋转矩阵并应用到 matrix_basis
        rot_mat = local_delta.to_matrix().to_4x4()
        current_basis = pb.matrix_basis.copy()
        new_basis = rot_mat @ current_basis
        # 保留局部位移
        new_basis[0][3] = current_basis[0][3]
        new_basis[1][3] = current_basis[1][3]
        new_basis[2][3] = current_basis[2][3]
        
        pb.matrix_basis = new_basis
        count += 1
    
    bpy.context.view_layer.update()
    
    direction = "B->A" if inverse else "A->B"
    mesh_count = _apply_and_rebind(arm_obj)
    operator.report({'INFO'}, f"变换完成 ({direction}): {count} 根骨骼, {mesh_count} 个网格")
    return {'FINISHED'}


class MODDER_OT_DeletePosePreset(bpy.types.Operator):
    """删除选中的变换记录"""
    bl_idname = "modder.delete_pose_preset"
    bl_label = "删除记录"
    bl_options = {'INTERNAL'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        selected_file = settings.pose_preset_enum
        if not selected_file or selected_file == 'NONE':
            return {'CANCELLED'}
        
        filepath = os.path.join(_get_pose_presets_dir(), selected_file)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self.report({'INFO'}, f"已删除: {selected_file}")
            except Exception as e:
                self.report({'ERROR'}, f"删除失败: {e}")
        return {'FINISHED'}


# ============================================================
# 共用的网格处理函数
# ============================================================

def _apply_and_rebind(arm_obj):
    bpy.ops.object.mode_set(mode='OBJECT')
    
    mesh_children = [obj for obj in bpy.data.objects 
                     if obj.type == 'MESH' and obj.find_armature() == arm_obj]
    
    if mesh_children:
        for child in mesh_children:
            child.hide_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE', extend=True)
        bpy.ops.object.convert(target='MESH')
    
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=True)
    bpy.ops.pose.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    if mesh_children:
        bpy.ops.object.select_hierarchy(direction='CHILD', extend=False)
        if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
            modifier = bpy.context.active_object.modifiers.new(name="Armature", type='ARMATURE')
            modifier.object = arm_obj
            bpy.ops.object.make_links_data(type='MODIFIERS')
        bpy.ops.object.select_hierarchy(direction='PARENT', extend=False)
    
    bpy.ops.object.select_hierarchy(direction='CHILD', extend=True)
    bpy.context.view_layer.objects.active = arm_obj
    return len(mesh_children)


# ============================================================
# 注册
# ============================================================

classes = [
    MODDER_OT_TPoseDirection,
    MODDER_OT_TPoseMatrixZero,
    MODDER_OT_RecordTransform,
    MODDER_OT_ApplyTransformForward,
    MODDER_OT_ApplyTransformInverse,
    MODDER_OT_DeletePosePreset,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)