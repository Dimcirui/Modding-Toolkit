import bpy
from ...core import bone_utils
from . import data_maps

class MHWI_OT_AlignNonPhysics(bpy.types.Operator):
    """对齐 MHWI 非物理骨骼 (跳过 150-245 物理骨)"""
    bl_idname = "mhwi.align_non_physics"
    bl_label = "对齐非物理骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        if len(selected_objects) != 2 or not active_obj:
            self.report({'ERROR'}, "请选择两个骨架 (源 -> 目标)")
            return {'CANCELLED'}

        target_armature = active_obj
        source_armature = [obj for obj in selected_objects if obj != target_armature][0]
        
        # 3.x/4.x 兼容：强制更新数据
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        
        # 预读取源骨骼世界坐标
        source_heads = {}
        s_matrix = source_armature.matrix_world
        for b in source_armature.data.bones:
            source_heads[b.name] = s_matrix @ b.head_local.copy()

        # 进入编辑模式操作目标
        context.view_layer.objects.active = target_armature
        bpy.ops.object.mode_set(mode='EDIT')
        target_edit_bones = target_armature.data.edit_bones
        t_matrix_inv = target_armature.matrix_world.inverted()
        
        aligned_count = 0
        skip_count = 0
        
        # 遍历目标骨骼寻找匹配
        for t_bone in target_edit_bones:
            name = t_bone.name
            
            # 过滤物理骨骼 (MhBone_150 ~ MhBone_245)
            if name.startswith("MhBone_") or name.startswith("bonefunction_"):
                try:
                    # 提取数字部分
                    num_part = name.split("_")[-1]
                    bone_num = int(num_part)
                    if 150 <= bone_num <= 245:
                        skip_count += 1
                        continue
                except (ValueError, IndexError):
                    pass

            # 在源数据中查找
            if name in source_heads:
                s_head_world = source_heads[name]
                
                # 计算新位置
                old_head_local = t_bone.head.copy()
                new_head_local = t_matrix_inv @ s_head_world
                
                # 保持方向和长度移动
                original_vec = t_bone.tail - t_bone.head
                t_bone.head = new_head_local
                t_bone.tail = new_head_local + original_vec
                
                # 递归移动子级 (使用 core 工具)
                offset = new_head_local - old_head_local
                bone_utils.propagate_movement(t_bone, offset)
                
                aligned_count += 1
            
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"对齐: {aligned_count}, 跳过物理骨: {skip_count}")
        return {'FINISHED'}

class MHWI_OT_MMDSnap(bpy.types.Operator):
    """MMD 骨骼吸附 (支持日文/英文)"""
    bl_idname = "mhwi.mmd_snap"
    bl_label = "MMD 骨骼吸附"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            return {'CANCELLED'}
            
        # 检测语言
        all_bone_names = [b.name for b in arm_obj.data.bones]
        if "下半身" in all_bone_names:
            mapping = data_maps.JP_MMD_MAP
        elif "Hips" in all_bone_names:
            mapping = data_maps.EN_MMD_MAP
        else:
            self.report({'WARNING'}, "未识别到 MMD 骨骼特征 (需要 '下半身' 或 'Hips')")
            return {'CANCELLED'}
            
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        # 特殊处理：记录 MhBone_007 (左肘) 移动前的状态，用于修正辅助骨骼
        before_elbow_pos = None
        elbow_bone = bone_utils.find_bone_smart(edit_bones, "MhBone_007")
        if elbow_bone:
            before_elbow_pos = elbow_bone.head.copy()
            
        processed = 0
        
        for src, dst in mapping:
            s_bone = edit_bones.get(src)
            t_bone = bone_utils.find_bone_smart(edit_bones, dst)
            
            if s_bone and t_bone:
                # 简单的位置吸附
                t_bone.head = s_bone.head.copy()
                t_bone.tail = s_bone.tail.copy()
                
                # 脚趾 Y 轴修正
                if dst in ["MhBone_017", "MhBone_021"]:
                    t_bone.head.y = -104.611
                    t_bone.tail.y = -104.607
                
                processed += 1
        
        # 肘部辅助骨骼修正
        if before_elbow_pos and elbow_bone:
            offset = elbow_bone.head - before_elbow_pos
            for aux_name in ["MhBone_101", "MhBone_102", "MhBone_103", "MhBone_104"]:
                aux = bone_utils.find_bone_smart(edit_bones, aux_name)
                if aux:
                    aux.head += offset
                    aux.tail += offset

        # 3.x/4.x 兼容：显示所有骨骼层
        # Blender 4.0+ 使用 bone_collections，3.x 使用 layers
        try:
            if hasattr(arm_obj.data, "collections"): # Blender 4.0+
                for coll in arm_obj.data.collections:
                    coll.is_visible = True
            else: # Blender 3.x
                # 开启所有 32 个层
                arm_obj.data.layers = [True] * 32
        except Exception:
            pass

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"MMD 吸附完成，处理了 {processed} 根骨骼")
        return {'FINISHED'}

classes = [MHWI_OT_AlignNonPhysics, MHWI_OT_MMDSnap]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)