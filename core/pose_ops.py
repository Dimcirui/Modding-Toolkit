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
from .i18n import T
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES, resolve_preset
from .bone_utils import get_import_presets_callback


# ============================================================
# 路径与枚举
# ============================================================

def _get_pose_presets_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(addon_dir, "assets", "presets", "pose")
    os.makedirs(d, exist_ok=True)
    return d

_pose_preset_cache = []

def _read_pose_preset_name(filepath, fallback):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f).get('preset_info', {}).get('name') or fallback
    except Exception:
        return fallback

def get_pose_presets_callback(self, context):
    global _pose_preset_cache
    _pose_preset_cache = []
    d = _get_pose_presets_dir()
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                fallback = f[:-5]  # strip .json
                name = _read_pose_preset_name(os.path.join(d, f), fallback)
                _pose_preset_cache.append((f, name, ""))
    if not _pose_preset_cache:
        _pose_preset_cache.append(('NONE', T("core.pose_ops.no_record"), ""))
    return _pose_preset_cache


# ============================================================
# 1. MMD A转Tpose（固定只服务 MMD 骨架，不经过通用骨架预设）
# ============================================================

class MODDER_OT_MmdAToTPose(bpy.types.Operator):
    bl_idname = "modder.mmd_a_to_tpose"
    bl_label = "MMD A-Pose to T-Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.mmd_a_to_tpose_desc")

    def execute(self, context):
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
            return {'CANCELLED'}

        # 固定使用 MMD 骨骼预设做模糊匹配，不再暴露通用预设下拉框——这个工具天生
        # 只服务 MMD 骨架（旋转上臂到水平方向，为 MMD 的 A-Pose 模型服务）。
        mapper = BoneMapManager()
        if not mapper.load_preset("MMD.json", is_import_x=True):
            self.report({'ERROR'}, T("core.pose_ops.cannot_load_armature_preset"))
            return {'CANCELLED'}

        arm_mw = arm_obj.matrix_world
        targets = [("upperarm_L", 1.0), ("upperarm_R", -1.0)]
        
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        pose_bones = arm_obj.pose.bones
        count = 0
        
        for std_key, sign in targets:
            main_name, __ = mapper.get_matches_for_standard(arm_obj, std_key)
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
            self.report({'WARNING'}, T("core.pose_ops.upperarm_not_found"))
            return {'CANCELLED'}

        mesh_count = _apply_and_rebind(arm_obj)
        self.report({'INFO'}, T("core.pose_ops.mmd_a_to_tpose_done").format(bones=count, meshes=mesh_count))
        return {'FINISHED'}


# ============================================================
# 2. REE转Tpose（私有 RE Engine 骨架名单，自动识别游戏，不经过通用骨架预设）
# ============================================================
# 目前只收录荒野 (MHWS)；名单直接照搬 MBT (Modder-Batch-Tool) MHWildstpose 算子里的完整
# 骨骼名单——跨游戏通用的 standard-key 预设系统只覆盖主链骨骼，没有 Knee/Instep/Palm 和
# 全部扭转/物理辅助骨 (_HJ_) 的标准键，归零后这些子骨仍停留在原始姿态，父骨被摆正后会跟
# 着扭曲。注意名单里没有锁骨和拇指——锁骨保持原朝向（UpperArm 挂在其骨尾上，一起摆正反而
# 会带偏位置），拇指天生斜向生长，用同一套"零"朝向硬掰只会拉直变形，因此也不包含它们。
# 以后要支持其他 RE Engine 游戏，在这里加一个新的 {game_code: bone_tuple} 条目即可。
_REE_TPOSE_BONES = {
    "MHWS": (
        "L_UpperArm", "R_UpperArm", "L_Forearm", "R_Forearm", "L_Hand", "R_Hand",
        "L_Palm", "R_Palm",
        "L_IndexF1", "L_IndexF2", "L_IndexF3", "R_IndexF1", "R_IndexF2", "R_IndexF3",
        "L_MiddleF1", "L_MiddleF2", "L_MiddleF3", "R_MiddleF1", "R_MiddleF2", "R_MiddleF3",
        "L_RingF1", "L_RingF2", "L_RingF3", "R_RingF1", "R_RingF2", "R_RingF3",
        "L_PinkyF1", "L_PinkyF2", "L_PinkyF3", "R_PinkyF1", "R_PinkyF2", "R_PinkyF3",
        "L_HandRZ_HJ_00", "R_HandRZ_HJ_00",
        "L_IndexF_HJ_00", "L_IndexF_HJ_01", "L_IndexF_HJ_02", "L_IndexF_HJ_03", "L_IndexF_HJ_04",
        "R_IndexF_HJ_00", "R_IndexF_HJ_01", "R_IndexF_HJ_02", "R_IndexF_HJ_03", "R_IndexF_HJ_04",
        "L_MiddleF_HJ_00", "L_MiddleF_HJ_01", "L_MiddleF_HJ_02", "L_MiddleF_HJ_03", "L_MiddleF_HJ_04",
        "R_MiddleF_HJ_00", "R_MiddleF_HJ_01", "R_MiddleF_HJ_02", "R_MiddleF_HJ_03", "R_MiddleF_HJ_04",
        "L_RingF_HJ_00", "L_RingF_HJ_01", "L_RingF_HJ_02", "L_RingF_HJ_03", "L_RingF_HJ_04",
        "R_RingF_HJ_00", "R_RingF_HJ_01", "R_RingF_HJ_02", "R_RingF_HJ_03", "R_RingF_HJ_04",
        "L_PinkyF_HJ_00", "L_PinkyF_HJ_01", "L_PinkyF_HJ_02", "L_PinkyF_HJ_03", "L_PinkyF_HJ_04",
        "R_PinkyF_HJ_00", "R_PinkyF_HJ_01", "R_PinkyF_HJ_02", "R_PinkyF_HJ_03", "R_PinkyF_HJ_04",
        "L_Hand_HJ_00", "L_Hand_HJ_01", "R_Hand_HJ_00", "R_Hand_HJ_01",
        "L_ForearmTwist_HJ_00", "L_ForearmTwist_HJ_01", "L_ForearmTwist_HJ_02",
        "R_ForearmTwist_HJ_00", "R_ForearmTwist_HJ_01", "R_ForearmTwist_HJ_02",
        "L_ForearmRY_HJ_00", "L_ForearmRY_HJ_01", "R_ForearmRY_HJ_00", "R_ForearmRY_HJ_01",
        "L_Elbow_HJ_00", "R_Elbow_HJ_00",
        "L_UpperArmTwist_HJ_01", "L_UpperArmTwist_HJ_02", "R_UpperArmTwist_HJ_01", "R_UpperArmTwist_HJ_02",
        "L_Triceps_HJ_00", "R_Triceps_HJ_00",
        "L_Biceps_HJ_00", "L_Biceps_HJ_01", "R_Biceps_HJ_00", "R_Biceps_HJ_01",
        "L_Deltoid_HJ_00", "L_Deltoid_HJ_01", "L_Deltoid_HJ_02",
        "R_Deltoid_HJ_00", "R_Deltoid_HJ_01", "R_Deltoid_HJ_02",
        "L_Thigh", "R_Thigh", "L_Knee", "R_Knee", "L_Shin", "R_Shin",
        "L_Foot", "R_Foot", "L_Instep", "R_Instep", "L_Toe", "R_Toe",
        "L_Foot_HJ_00", "R_Foot_HJ_00", "L_Calf_HJ_00", "R_Calf_HJ_00",
        "L_Shin_HJ_00", "L_Shin_HJ_01", "R_Shin_HJ_00", "R_Shin_HJ_01",
        "L_Knee_HJ_00", "R_Knee_HJ_00", "L_KneeRX_HJ_00", "R_KneeRX_HJ_00",
        "L_ThighTwist_HJ_00", "L_ThighTwist_HJ_01", "L_ThighTwist_HJ_02",
        "R_ThighTwist_HJ_00", "R_ThighTwist_HJ_01", "R_ThighTwist_HJ_02",
        "L_ThighRZ_HJ_00", "L_ThighRZ_HJ_01", "R_ThighRZ_HJ_00", "R_ThighRZ_HJ_01",
        "L_ThighRX_HJ_00", "L_ThighRX_HJ_01", "R_ThighRX_HJ_00", "R_ThighRX_HJ_01",
        "L_Hip_HJ_00", "L_Hip_HJ_01", "R_Hip_HJ_00", "R_Hip_HJ_01",
    ),
}

# 覆盖率门槛：匹配到的骨骼数 / 该游戏名单总数，达到此比例才认定为该游戏骨架
_REE_MIN_COVERAGE = 0.3


def _detect_ree_game(arm_obj):
    """在私有 REE 游戏名单里按骨骼名覆盖率找最匹配的游戏，返回 game_code 或 None。"""
    existing = arm_obj.data.bones.keys()
    best_code, best_ratio = None, 0.0
    for code, bone_list in _REE_TPOSE_BONES.items():
        ratio = sum(1 for name in bone_list if name in existing) / len(bone_list)
        if ratio > best_ratio:
            best_code, best_ratio = code, ratio
    return best_code if best_ratio >= _REE_MIN_COVERAGE else None


def zero_pose_bone_rotations(arm_obj, bone_names):
    """将 bone_names 中每根骨骼的姿态旋转矩阵强制设为固定的竖直朝向（保留原有位置不变）。
    调用方需自行处理模式切换前后的上下文；返回实际处理的骨骼数。"""
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
    return count


class MODDER_OT_ReeToTPose(bpy.types.Operator):
    bl_idname = "modder.ree_to_tpose"
    bl_label = "REE to T-Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.ree_to_tpose_desc")

    def execute(self, context):
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
            return {'CANCELLED'}

        game_code = _detect_ree_game(arm_obj)
        if game_code is None:
            self.report({'ERROR'}, T("core.pose_ops.ree_game_not_recognized"))
            return {'CANCELLED'}

        existing = arm_obj.data.bones.keys()
        bone_names = [name for name in _REE_TPOSE_BONES[game_code] if name in existing]

        count = zero_pose_bone_rotations(arm_obj, bone_names)
        mesh_count = _apply_and_rebind(arm_obj)
        self.report(
            {'INFO'},
            T("core.pose_ops.ree_to_tpose_done").format(game=game_code, bones=count, meshes=mesh_count)
        )
        return {'FINISHED'}


# ============================================================
# 3. 姿态变换记录器（相对变换系统）
# ============================================================

class MODDER_OT_RecordTransform(bpy.types.Operator):
    bl_idname = "modder.record_transform"
    bl_label = "Record Transform"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.record_transform_desc")

    preset_name: bpy.props.StringProperty(
        name="Name",
        default="新姿态变换",
        description="Filename for the saved transform record (e.g. MMD A-Pose to T-Pose)"
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name", text=T("core.pose_ops.record_name_label"))
        self.layout.label(text=T("core.pose_ops.record_transform_hint"), icon='INFO')

    def execute(self, context):
        # 1. 获取两个骨架
        selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected_arms) < 2:
            self.report({'ERROR'}, T("core.pose_ops.select_two_armatures"))
            return {'CANCELLED'}

        if not self.preset_name.strip():
            self.report({'ERROR'}, T("core.pose_ops.name_cannot_be_empty"))
            return {'CANCELLED'}

        # 活动对象 = B 姿态 (后选的), 另一个 = A 姿态 (先选的)
        arm_b = context.active_object
        arm_a = None
        for obj in selected_arms:
            if obj != arm_b:
                arm_a = obj
                break

        if not arm_a or not arm_b or arm_a.type != 'ARMATURE' or arm_b.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.ensure_two_armatures"))
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
            self.report({'ERROR'}, T("core.pose_ops.no_common_bones"))
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
            self.report({'WARNING'}, T("core.pose_ops.poses_nearly_identical"))
            return {'CANCELLED'}
        
        filename = self.preset_name.strip()
        for ch in '<>:"/\\|?*':
            filename = filename.replace(ch, '')

        # 5. 保存 JSON
        data = {
            "preset_info": {
                "name": filename,
            },
            "type": "pose_relative_transform",
            "version": "2.0",
            "source_a": arm_a.data.name,
            "source_b": arm_b.data.name,
            "description": f"{arm_a.name} -> {arm_b.name}",
            "bone_count": significant_count,
            "transforms": transforms
        }
        filepath = os.path.join(_get_pose_presets_dir(), filename + ".json")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.report({'INFO'}, T("core.pose_ops.recorded_transform").format(
                n=significant_count, filename=filename + ".json"))
        except Exception as e:
            self.report({'ERROR'}, T("core.pose_ops.save_failed").format(err=e))
            return {'CANCELLED'}
        
        # 恢复活动对象
        bpy.context.view_layer.objects.active = arm_b
        return {'FINISHED'}


class MODDER_OT_ApplyTransformForward(bpy.types.Operator):
    bl_idname = "modder.apply_transform_forward"
    bl_label = "Forward (A->B)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.apply_forward_desc")

    def execute(self, context):
        return _apply_transform(self, context, inverse=False)


class MODDER_OT_ApplyTransformInverse(bpy.types.Operator):
    bl_idname = "modder.apply_transform_inverse"
    bl_label = "Inverse (B->A)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.apply_inverse_desc")

    def execute(self, context):
        return _apply_transform(self, context, inverse=True)


def _apply_transform(operator, context, inverse=False):
    """应用相对变换的核心逻辑 (正向或逆向)"""
    settings = context.scene.mhw_suite_settings
    arm_obj = context.active_object

    if not arm_obj or arm_obj.type != 'ARMATURE':
        operator.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
        return {'CANCELLED'}

    selected_file = settings.pose_preset_enum
    if not selected_file or selected_file == 'NONE':
        operator.report({'ERROR'}, T("core.pose_ops.no_transform_selected"))
        return {'CANCELLED'}

    # 读取 JSON
    filepath = os.path.join(_get_pose_presets_dir(), selected_file)
    if not os.path.exists(filepath):
        operator.report({'ERROR'}, T("core.pose_ops.file_not_found").format(name=selected_file))
        return {'CANCELLED'}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        operator.report({'ERROR'}, T("core.pose_ops.read_failed").format(err=e))
        return {'CANCELLED'}

    transforms = data.get("transforms", {})
    if not transforms:
        operator.report({'ERROR'}, T("core.pose_ops.no_transform_data"))
        return {'CANCELLED'}
    
    # 通过骨架预设建立骨骼名映射 (变换记录中的名字 -> 目标骨架的名字)
    mapper = BoneMapManager()
    bone_mapping = {}  # {target_bone_name: transform_bone_name}
    
    _pose_preset, _resolve_err = resolve_preset(settings.pose_import_preset_enum, arm_obj, True)
    if _pose_preset and mapper.load_preset(_pose_preset, is_import_x=True):
        # 通过预设的标准键做桥接
        # 先建立: transform_bone_name -> std_key 的映射
        # 再建立: std_key -> target_bone_name 的映射
        # 注意: transforms 里的骨骼名来自录制时的骨架, 可能和目标骨架不同
        for std_key in STANDARD_BONE_NAMES:
            tgt_name, __ = mapper.get_matches_for_standard(arm_obj, std_key)
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
        operator.report({'ERROR'}, T("core.pose_ops.no_matching_bones"))
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
    operator.report({'INFO'}, T("core.pose_ops.transform_done").format(
        direction=direction, bones=count, meshes=mesh_count))
    return {'FINISHED'}


class MODDER_OT_DeletePosePreset(bpy.types.Operator):
    bl_idname = "modder.delete_pose_preset"
    bl_label = "Delete Record"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.delete_preset_desc")

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
                self.report({'INFO'}, T("core.pose_ops.deleted").format(name=selected_file))
            except Exception as e:
                self.report({'ERROR'}, T("core.pose_ops.delete_failed").format(err=e))
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
    MODDER_OT_MmdAToTPose,
    MODDER_OT_ReeToTPose,
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