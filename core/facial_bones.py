import bpy
import mathutils


def _is_end_bone(name):
    """FBX 导出时每个末端关节都会带一个 "_end"（有时嵌套为 "_end_end"）辅助节点，
    仅用于在其他工具里推断骨骼朝向/长度，Blender 骨骼本身自带 head/tail 不需要它，
    移植表情骨时应过滤掉，避免这些辅助节点被当成正常骨骼一并移植。"""
    return name.lower().endswith("_end")


def collect_facial_subtree(ref_arm, root_bone_name):
    """返回 (root_bone_name 及其所有子级的骨骼名列表, root_bone_name 原父级骨骼名)。
    自动过滤 FBX 导出产生的 "_end" 辅助节点。"""
    root_bone = ref_arm.data.bones.get(root_bone_name)
    if root_bone is None:
        return [], None
    names = [root_bone_name] + [
        b.name for b in root_bone.children_recursive if not _is_end_bone(b.name)
    ]
    parent_name = root_bone.parent.name if root_bone.parent else None
    return names, parent_name


def graft_facial_bones(ref_arm, target_arm, root_bone_name):
    """将 ref_arm 的 root_bone_name 及其所有子级完整移植到 target_arm。

    直接照搬来源世界坐标下的 head/tail/roll（不做竖直化，也不加尾骨），
    并按来源层级关系重建父子链；根骨骼本身挂到目标骨架中与来源同名的父级骨骼上。
    会先清除 target_arm 中已存在的同名旧骨骼。返回新建骨骼数。
    """
    subtree_names, root_parent_name = collect_facial_subtree(ref_arm, root_bone_name)
    if not subtree_names:
        return 0

    # 1. 在来源骨架 EDIT 模式下读取世界坐标 head/tail/roll 及父级名
    bpy.context.view_layer.objects.active = ref_arm
    bpy.ops.object.mode_set(mode='EDIT')
    ref_mat = ref_arm.matrix_world
    src_data = {}
    for name in subtree_names:
        eb = ref_arm.data.edit_bones.get(name)
        if eb is None:
            continue
        parent_name = eb.parent.name if eb.parent else None
        src_data[name] = (ref_mat @ eb.head, ref_mat @ eb.tail, eb.roll, parent_name)
    bpy.ops.object.mode_set(mode='OBJECT')

    if not src_data:
        return 0

    # 2. 目标骨架：清除同名旧骨骼，再逐个创建新骨骼
    bpy.context.view_layer.objects.active = target_arm
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = target_arm.data.edit_bones

    for name in subtree_names:
        if name in edit_bones:
            edit_bones.remove(edit_bones[name])

    tgt_mat_inv = target_arm.matrix_world.inverted()
    created = 0
    for name in subtree_names:
        if name not in src_data:
            continue
        head_w, tail_w, roll, _p = src_data[name]
        eb = edit_bones.new(name)
        eb.head = tgt_mat_inv @ head_w
        eb.tail = tgt_mat_inv @ tail_w
        eb.roll = roll
        eb.use_connect = False
        created += 1

    # 3. 按来源层级重建父子关系
    for name in subtree_names:
        eb = edit_bones.get(name)
        if eb is None or name not in src_data:
            continue
        if name == root_bone_name:
            if root_parent_name and root_parent_name in edit_bones:
                eb.parent = edit_bones[root_parent_name]
        else:
            _h, _t, _r, p_name = src_data[name]
            if p_name and p_name in edit_bones:
                eb.parent = edit_bones[p_name]

    bpy.ops.object.mode_set(mode='OBJECT')
    return created


def apply_blink_fake_bone(arm_obj, bone_name, offset_y=0.05):
    """假头法：在 bone_name(A) 与其父级(B) 之间插入一个从 B 原位复制出的假骨骼(B')，
    父子关系变为 B > B' > A，然后将 B' 与 A 一同沿 +Y (世界空间) 位移 offset_y 米。
    返回 True 表示已处理，A 不存在或没有父级时返回 False。
    """
    bpy.context.view_layer.objects.active = arm_obj
    if bpy.context.mode != 'EDIT_ARMATURE':
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_obj.data.edit_bones

    a = edit_bones.get(bone_name)
    if a is None or a.parent is None:
        return False
    b = a.parent

    b_prime = edit_bones.new(b.name + "_Fake")
    b_prime.head = b.head.copy()
    b_prime.tail = b.tail.copy()
    b_prime.roll = b.roll
    b_prime.parent = b
    b_prime.use_connect = False

    a.parent = b_prime
    a.use_connect = False

    mat3 = arm_obj.matrix_world.to_3x3()
    local_offset = mat3.inverted() @ mathutils.Vector((0.0, offset_y, 0.0))

    b_prime.head += local_offset
    b_prime.tail += local_offset
    a.head += local_offset
    a.tail += local_offset

    return True
