import bpy

def merge_weights_and_delete_bones(armature_obj, bone_pairs):
    """
    bone_pairs: List of (keep_bone_name, delete_bone_name)
    """
    # 1. 找到受该骨架影响的所有网格
    mesh_objects = [o for o in bpy.data.objects 
                   if o.type == 'MESH' and 
                   any(m.type == 'ARMATURE' and m.object == armature_obj for m in o.modifiers)]
    
    # 2. 遍历网格处理权重
    for obj in mesh_objects:
        # 激活物体以确保修改器操作正常
        bpy.context.view_layer.objects.active = obj
        vg = obj.vertex_groups
        
        for keep, delete in bone_pairs:
            # 检查两个组是否都存在于该网格
            if keep not in vg or delete not in vg:
                continue
            
            # 添加混合修改器
            mod = obj.modifiers.new(name="TempMerge", type='VERTEX_WEIGHT_MIX')
            mod.vertex_group_a = keep
            mod.vertex_group_b = delete
            mod.mix_mode = 'ADD'
            mod.mix_set = 'ALL'
            
            # 应用修改器
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e:
                print(f"Warning: Failed to apply modifier on {obj.name}: {e}")
                # 如果应用失败，移除修改器以防堆积
                if mod.name in obj.modifiers:
                    obj.modifiers.remove(mod)
                continue
            
            if delete in vg:
                vg.remove(vg[delete])
            
    # 3. 删除骨骼
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_obj.data.edit_bones
    
    deleted_count = 0
    for _, delete in bone_pairs:
        if delete in edit_bones:
            edit_bones.remove(edit_bones[delete])
            deleted_count += 1
            
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"Deleted {deleted_count} bones.")
    
def merge_vgroups_multi(obj, source_names, target_name):
    """
    将多个源顶点组权重合并到目标组（单次顶点遍历，上限1.0），合并后删除源组。
    obj: Mesh 对象
    source_names: 源顶点组名列表
    target_name: 目标顶点组名
    """
    target_vg = obj.vertex_groups.get(target_name)
    if target_vg is None:
        target_vg = obj.vertex_groups.new(name=target_name)

    active_sources = [vg for vg in (obj.vertex_groups.get(n) for n in source_names) if vg is not None]
    if not active_sources:
        return

    for vert in obj.data.vertices:
        total_src_w = 0.0
        for src_vg in active_sources:
            try:
                total_src_w += src_vg.weight(vert.index)
            except RuntimeError:
                pass
        if total_src_w <= 0.0:
            continue
        try:
            tgt_w = target_vg.weight(vert.index)
        except RuntimeError:
            tgt_w = 0.0
        target_vg.add([vert.index], min(tgt_w + total_src_w, 1.0), 'REPLACE')

    for src_vg in active_sources:
        obj.vertex_groups.remove(src_vg)


def rename_or_merge_vgroup(obj, old_name, new_name):
    """
    将顶点组重命名（目标不存在时）或合并权重（目标已存在时），合并后删除旧组。
    返回 True 表示执行了操作，False 表示旧组不存在。
    """
    old_vg = obj.vertex_groups.get(old_name)
    if old_vg is None:
        return False
    existing_vg = obj.vertex_groups.get(new_name)
    if existing_vg is None:
        old_vg.name = new_name
        return True
    for vert in obj.data.vertices:
        try:
            old_w = old_vg.weight(vert.index)
        except RuntimeError:
            continue
        try:
            existing_w = existing_vg.weight(vert.index)
        except RuntimeError:
            existing_w = 0.0
        existing_vg.add([vert.index], min(existing_w + old_w, 1.0), 'REPLACE')
    obj.vertex_groups.remove(old_vg)
    return True


def bone_has_weights(bone_name, mesh_objects):
    """检查骨骼在绑定网格中是否有任何顶点权重（用于尾骨判断）"""
    for obj in mesh_objects:
        vg = obj.vertex_groups.get(bone_name)
        if vg is None:
            continue
        for v in obj.data.vertices:
            try:
                if vg.weight(v.index) > 0:
                    return True
            except RuntimeError:
                pass
    return False


def build_bone_chains(selected_names, arm_obj):
    """
    从选中骨骼中重建链结构（需在 EDIT 模式下调用）。
    返回 list of lists，每个子列表是一条从根到末的骨骼名链。
    分叉点处截断当前链，每个分支各自开始新链。
    """
    selected_set = set(selected_names)
    bones = arm_obj.data.edit_bones
    chains = []

    def traverse(name, current_chain):
        current_chain.append(name)
        bone = bones.get(name)
        if not bone:
            chains.append(list(current_chain))
            return
        sel_children = [c.name for c in bone.children if c.name in selected_set]
        if len(sel_children) == 0:
            chains.append(list(current_chain))
        elif len(sel_children) == 1:
            traverse(sel_children[0], current_chain)
        else:
            # 分叉：当前链在此截断，每个分支独立开始
            chains.append(list(current_chain))
            for child_name in sel_children:
                traverse(child_name, [])

    roots = [n for n in selected_names
             if bones.get(n) and
             (bones[n].parent is None or bones[n].parent.name not in selected_set)]

    for root in roots:
        traverse(root, [])

    return chains