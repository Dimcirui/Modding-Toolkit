import bpy
import os
from bpy.app.translations import pgettext as _
from . import data_maps

_FINGER_INITIALS = {
    'Index': 'I', 'Thumb': 'T', 'Middle': 'M',
    'Ring': 'R', 'Pinky': 'P',
}

# ==========================================
# 原生骨架目录
# ==========================================

def _get_native_skeletons_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, 'assets', 'native_skeletons', 're4')


_native_skel_cache = []

def get_native_skeletons_callback(self, context):
    global _native_skel_cache
    _native_skel_cache = []
    d = _get_native_skeletons_dir()
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if '.fbxskel.' in f:
                name = f.split('.fbxskel.')[0]
                _native_skel_cache.append((f, name, ""))
            elif '.skeleton.' in f:
                name = f.split('.skeleton.')[0]
                _native_skel_cache.append((f, name, ""))
    if not _native_skel_cache:
        _native_skel_cache.append(('NONE', "无可用骨架 (添加至 assets/native_skeletons/re4/)", ""))
    return _native_skel_cache


# ==========================================
# 假骨法内部函数
# ==========================================

def _fakebone_body(context, source_arm, ruler_arm):
    """
    在 ruler_arm 上应用身体假骨流程（以 source_arm 为约束目标）。
    处理完毕后 ruler_arm 仅保留 end 骨。
    """
    BoneName  = data_maps.FAKEBONE_BODY_BONES
    FakeName  = data_maps.FAKEBONE_BODY_FAKES
    ParentName = data_maps.FAKEBONE_BODY_PARENTS

    context.view_layer.objects.active = ruler_arm
    bpy.ops.object.mode_set(mode='POSE')

    # 1. 旋转约束
    for bone_name in BoneName:
        if bone_name in ruler_arm.pose.bones:
            crc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_ROTATION')
            crc.target = source_arm
            crc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 删除已有 end 骨
    for b in [b for b in ruler_arm.data.edit_bones if "end" in b.name]:
        ruler_arm.data.edit_bones.remove(b)

    # 创建 end 骨
    for fake in FakeName:
        if fake not in ruler_arm.data.edit_bones:
            continue
        bone = ruler_arm.data.edit_bones[fake]
        for pname in ParentName[fake]:
            if pname not in ruler_arm.data.edit_bones:
                continue
            suffix = "_end"
            if len(ParentName[fake]) > 1:
                if pname.startswith("L_") or pname.endswith("_L"):
                    suffix = "_endL"
                elif pname.startswith("R_") or pname.endswith("_R"):
                    suffix = "_endR"
            new_bone = ruler_arm.data.edit_bones.new(bone.name + suffix)
            new_bone.head = bone.head
            new_bone.tail = bone.tail
            new_bone.roll = bone.roll
            new_bone.parent = ruler_arm.data.edit_bones[pname]
            new_bone.use_connect = bone.use_connect

    bpy.ops.object.mode_set(mode='POSE')

    # 2. 缩放 + 位置约束
    for bone_name in BoneName:
        if bone_name in ruler_arm.pose.bones:
            csc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_SCALE')
            csc.target = source_arm
            csc.subtarget = bone_name
            clc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_LOCATION')
            clc.target = source_arm
            clc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 仅保留 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" not in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    bpy.ops.object.mode_set(mode='OBJECT')


def _fakebone_fingers(context, source_arm, ruler_arm):
    """
    在 ruler_arm 上应用手指假骨流程（以 source_arm 为约束目标）。
    处理完毕后 ruler_arm 仅保留 end 骨。
    """
    BoneName  = data_maps.FAKEBONE_FINGER_BONES
    ParentName = {}

    context.view_layer.objects.active = ruler_arm
    bpy.ops.object.mode_set(mode='POSE')

    # 1. 旋转约束 + 动态建立父级关系表
    for bone_name in BoneName:
        if bone_name not in ruler_arm.pose.bones:
            continue
        cr = ruler_arm.pose.bones[bone_name].constraints.new('COPY_ROTATION')
        cr.target = source_arm
        cr.subtarget = bone_name

    for bone_name in BoneName:
        if bone_name in ("R_Hand", "L_Hand"):
            continue
        if bone_name not in ruler_arm.pose.bones:
            continue
        pname = ruler_arm.pose.bones[bone_name].parent.name
        ParentName.setdefault(pname, []).append(bone_name)

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 删除已有 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    # 创建 end 骨
    for fake in ParentName:
        if fake not in ruler_arm.data.edit_bones:
            continue
        bone = ruler_arm.data.edit_bones[fake]
        for child_name in ParentName[fake]:
            if child_name not in ruler_arm.data.edit_bones:
                continue
            if (child_name.startswith('L') or child_name.startswith('R')) and len(ParentName[fake]) > 1:
                # 取 L_/R_ 后面的首字母作为 end 骨后缀，如 L_Palm -> P, L_IndexF1 -> I
                finger_initial = child_name.split('_')[1][0] if '_' in child_name else ""
                suffix = f"_end{finger_initial}" if finger_initial else "_end"
            else:
                suffix = "_end"
            new_bone = ruler_arm.data.edit_bones.new(bone.name + suffix)
            new_bone.head = bone.head
            new_bone.tail = bone.tail
            new_bone.roll = bone.roll
            new_bone.parent = ruler_arm.data.edit_bones[child_name]
            new_bone.use_connect = bone.use_connect

    bpy.ops.object.mode_set(mode='POSE')

    # 2. 缩放 + 位置约束
    for bone_name in BoneName:
        if bone_name not in ruler_arm.pose.bones:
            continue
        csc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_SCALE')
        csc.target = source_arm
        csc.subtarget = bone_name
        clc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_LOCATION')
        clc.target = source_arm
        clc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 仅保留 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" not in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    bpy.ops.object.mode_set(mode='OBJECT')


def _merge_end_bones(context, main_arm, end_arm, merge_type):
    """
    将 end_arm 合并进 main_arm，并重建父级关系。
    merge_type: 'body' 或 'fingers'
    end_arm 在 join 后被消耗，调用方应将引用置 None。
    """
    for o in list(context.selected_objects):
        o.select_set(False)
    main_arm.select_set(True)
    end_arm.select_set(True)
    context.view_layer.objects.active = main_arm
    bpy.ops.object.join()

    bpy.ops.object.mode_set(mode='EDIT')
    arm = main_arm.data

    if merge_type == 'body':
        for bone in arm.edit_bones:
            if "_end" in bone.name:
                base_name = bone.name.split("_end")[0]
                if base_name in arm.edit_bones:
                    bone.parent = arm.edit_bones[base_name]
                    bone.use_connect = False

    elif merge_type == 'fingers':
        # 1. end 骨挂回各自 base 骨
        for fakebone in [b for b in arm.edit_bones if "_end" in b.name]:
            base_name = fakebone.name.split("_end")[0]
            if base_name in arm.edit_bones:
                fakebone.parent = arm.edit_bones[base_name]
                fakebone.use_connect = False
        # 2. 手指第一节 → end 骨 mapping
        for child_name, parent_name in data_maps.FAKEBONE_FINGER_MERGE_MAP.items():
            if child_name in arm.edit_bones and parent_name in arm.edit_bones:
                arm.edit_bones[child_name].parent = arm.edit_bones[parent_name]
                arm.edit_bones[child_name].use_connect = False
        # 3. 手指链规律
        for finger_base, num_segments in data_maps.FAKEBONE_FINGER_PATTERNS:
            for i in range(2, num_segments + 1):
                child_name  = f"{finger_base}{i}"
                parent_name = f"{finger_base}{i-1}_end"
                if child_name in arm.edit_bones and parent_name in arm.edit_bones:
                    arm.edit_bones[child_name].parent = arm.edit_bones[parent_name]
                    arm.edit_bones[child_name].use_connect = False

    bpy.ops.object.mode_set(mode='OBJECT')


def do_fakebone(context, user_arm_obj, native_fbxskel_path):
    """
    对 user_arm_obj 就地执行完整假骨流程（身体 + 手指）。
    batch export 中请先复制骨架再传入。
    成功返回 True，失败抛出异常。
    """
    if not hasattr(bpy.ops, 're_fbxskel') or not hasattr(bpy.ops.re_fbxskel, 'importfile'):
        raise RuntimeError("需要 RE Mesh Editor 的 fbxskel 导入器 (re_fbxskel.importfile)")

    prev_active   = context.view_layer.objects.active
    prev_selected = [o for o in context.selected_objects]
    for o in prev_selected:
        o.select_set(False)

    native_arm  = None
    body_ruler  = None

    try:
        # 加载原生骨架
        bpy.ops.re_fbxskel.importfile(filepath=native_fbxskel_path)
        native_arm = context.active_object
        if native_arm is None or native_arm.type != 'ARMATURE':
            raise RuntimeError(f"导入原生骨架失败: {native_fbxskel_path}")
        native_arm.select_set(False)

        # ── 身体 ──
        # 复制 native 作为 body ruler（native 本体留给手指用）
        context.view_layer.objects.active = native_arm
        native_arm.select_set(True)
        bpy.ops.object.duplicate()
        body_ruler = context.active_object
        native_arm.select_set(False)
        body_ruler.select_set(False)

        _fakebone_body(context, user_arm_obj, body_ruler)
        _merge_end_bones(context, user_arm_obj, body_ruler, 'body')
        body_ruler = None  # 已被 join 消耗

        # ── 手指 ──（直接使用 native_arm，无需再复制）
        _fakebone_fingers(context, user_arm_obj, native_arm)
        _merge_end_bones(context, user_arm_obj, native_arm, 'fingers')
        native_arm = None  # 已被 join 消耗

        return True

    except Exception:
        import traceback
        traceback.print_exc()
        for arm in [body_ruler, native_arm]:
            if arm is not None and arm.name in bpy.data.objects:
                bpy.data.objects.remove(arm, do_unlink=True)
        raise

    finally:
        context.view_layer.objects.active = prev_active
        for o in prev_selected:
            if o.name in bpy.data.objects:
                o.select_set(True)


# ==========================================
# RE4 假骨工具 — 一键式 Operator
# ==========================================

class RE4_OT_FakeBone_OneClick(bpy.types.Operator):
    """(假头法) 一键为选中骨架生成全套 End 骨骼"""
    bl_idname = "re4.fakebone_one_click"
    bl_label  = "(假头法) 生成假骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    native_skeleton: bpy.props.EnumProperty(
        name="原生骨架",
        description="选择对应角色的原生 fbxskel 文件",
        items=get_native_skeletons_callback,
    )

    def invoke(self, context, event):
        if context.active_object is None or context.active_object.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中目标骨架"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.prop(self, "native_skeleton", text="角色原生骨架")

    def execute(self, context):
        if not hasattr(bpy.ops, 're_fbxskel') or not hasattr(bpy.ops.re_fbxskel, 'exportfile'):
            self.report({'ERROR'}, _("需要 RE Mesh Editor 插件"))
            return {'CANCELLED'}

        user_arm = context.active_object
        if user_arm is None or user_arm.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中目标骨架"))
            return {'CANCELLED'}

        if not self.native_skeleton or self.native_skeleton == 'NONE':
            self.report({'ERROR'}, _("请选择原生骨架（添加文件到 assets/native_skeletons/re4/）"))
            return {'CANCELLED'}

        native_path = os.path.join(_get_native_skeletons_dir(), self.native_skeleton)
        if not os.path.isfile(native_path):
            self.report({'ERROR'}, _("找不到原生骨架: %s") % native_path)
            return {'CANCELLED'}

        try:
            do_fakebone(context, user_arm, native_path)
            self.report({'INFO'}, _("假骨骼生成完成"))
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, _("假骨骼生成失败: %s") % e)
            return {'CANCELLED'}


classes = [
    RE4_OT_FakeBone_OneClick,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
