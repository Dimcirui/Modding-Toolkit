import bpy
from ...core import bone_utils
from ...core import weight_utils
from . import data_maps
from ...core.bone_mapper import BoneMapManager, STANDARD_BONE_NAMES


def _is_mhwi_physics(name):
    """MHWI 物理骨判断：编号 150-245 的 MhBone_ / bonefunction_ 骨骼"""
    if not (name.startswith("MhBone_") or name.startswith("bonefunction_")):
        return False
    try:
        return 150 <= int(name.split("_")[-1]) <= 245
    except (ValueError, IndexError):
        return False


# ==========================================
# 1. 对齐 MHWI 非物理骨骼
# ==========================================
class MHWI_OT_AlignNonPhysics(bpy.types.Operator):
    """对齐 MHWI 骨骼 (跳过 150-245 物理骨)"""
    bl_idname = "mhwi.align_non_physics"
    bl_label = "对齐非物理骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        if len(selected_objects) != 2 or not context.active_object:
            self.report({'ERROR'}, "请选择两个骨架 (源 -> 目标)")
            return {'CANCELLED'}
        target_armature = context.active_object
        source_armature = [obj for obj in selected_objects if obj != target_armature][0]
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        aligned = bone_utils.align_armatures_by_name(
            source_armature, target_armature, skip_fn=_is_mhwi_physics)
        skip = sum(1 for b in target_armature.data.bones if _is_mhwi_physics(b.name))
        self.report({'INFO'}, f"对齐: {aligned}, 跳过物理骨: {skip}")
        return {'FINISHED'}

# 注册所有类
classes = [
    MHWI_OT_AlignNonPhysics, 
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)