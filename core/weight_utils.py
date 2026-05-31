import bpy
from mathutils import Vector

def merge_weights_and_delete_bones(armature_obj, bone_pairs):
    """
    bone_pairs: List of (keep_bone_name, delete_bone_name)
    """
    # 构建辅助结构：被删除骨骼集合，以及子→父映射
    deleted_set = {delete for _, delete in bone_pairs}
    child_to_parent = {child: parent for parent, child in bone_pairs}

    def find_final_target(bone_name):
        """沿父骨链向上，找到第一个不被删除的骨骼（最终存活祖先）。"""
        visited = set()
        current = bone_name
        while current in deleted_set and current not in visited:
            visited.add(current)
            parent = child_to_parent.get(current)
            if parent is None:
                break
            current = parent
        return current

    # 为每个被删除骨骼，直接计算其最终存活祖先（跳过中间已删除的骨骼）
    merge_map = {delete: find_final_target(parent)
                 for parent, delete in bone_pairs}

    # 1. 找到受该骨架影响的所有网格
    # 主：通过姿态修改器绑定
    bound_meshes = {o for o in bpy.data.objects
                    if o.type == 'MESH' and
                    any(m.type == 'ARMATURE' and m.object == armature_obj for m in o.modifiers)}
    # 补充：未绑定修改器但作为该骨架子级、且含有待删除骨骼同名顶点组的网格
    delete_names = set(merge_map.keys())
    extra_meshes = {o for o in bpy.data.objects
                    if o.type == 'MESH' and o not in bound_meshes and
                    o.parent == armature_obj and
                    any(vg.name in delete_names for vg in o.vertex_groups)}
    mesh_objects = bound_meshes | extra_meshes

    # 2. 遍历网格，将每个被删除骨骼的权重直接合并到其最终存活祖先
    for obj in mesh_objects:
        vg = obj.vertex_groups
        for delete, final_target in merge_map.items():
            delete_vg = vg.get(delete)
            if delete_vg is None:
                continue
            target_vg = vg.get(final_target) or vg.new(name=final_target)
            for vert in obj.data.vertices:
                try:
                    del_w = delete_vg.weight(vert.index)
                except RuntimeError:
                    continue
                try:
                    keep_w = target_vg.weight(vert.index)
                except RuntimeError:
                    keep_w = 0.0
                target_vg.add([vert.index], min(keep_w + del_w, 1.0), 'REPLACE')
            vg.remove(delete_vg)

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


def shape_key_to_weights(obj, active_kb, basis_kb, ignore_threshold=0.001,
                         weight_strength=1.0, smooth_factor=0.5,
                         smooth_iters=10, sync_seams=True, direction=None,
                         vg_name=None):
    """
    Convert a shape key to a vertex group using normalized, Laplacian-smoothed weights.

    Weights are normalized so the vertex with the largest displacement always gets 1.0,
    with others scaled proportionally. Coincident vertices (UV seam duplicates) are
    synced after each smoothing pass to prevent tearing.

    direction: optional normalized Vector. When set, only vertices whose displacement
    projects positively onto this axis contribute; weight = dot product magnitude.
    This lets you split a single shape key (e.g. blink) into per-direction groups
    (upper eyelid vs lower eyelid) by running the operator twice with opposite signs.

    Returns the number of affected vertices, or None if no valid displacement is found.
    """
    vertices = obj.data.vertices
    v_count = len(vertices)
    raw_weights = [0.0] * v_count
    max_val = 0.0
    valid_count = 0

    filter_dir = Vector(direction).normalized() if direction is not None else None

    seam_groups = []
    if sync_seams:
        coincident = {}
        for i, v in enumerate(vertices):
            key = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
            coincident.setdefault(key, []).append(i)
        seam_groups = [g for g in coincident.values() if len(g) > 1]

    for i in range(v_count):
        disp = active_kb.data[i].co - basis_kb.data[i].co
        if filter_dir is not None:
            val = disp.dot(filter_dir)
            if val <= ignore_threshold:
                continue
        else:
            val = disp.length
            if val <= ignore_threshold:
                continue
        if val > max_val:
            max_val = val
        raw_weights[i] = val
        valid_count += 1

    if valid_count == 0 or max_val == 0:
        return None

    for i in range(v_count):
        if raw_weights[i] > 0:
            raw_weights[i] = min(1.0, (raw_weights[i] / max_val) * weight_strength)

    for group in seam_groups:
        avg = sum(raw_weights[idx] for idx in group) / len(group)
        for idx in group:
            raw_weights[idx] = avg

    if smooth_iters > 0:
        adj = {i: [] for i in range(v_count)}
        for edge in obj.data.edges:
            adj[edge.vertices[0]].append(edge.vertices[1])
            adj[edge.vertices[1]].append(edge.vertices[0])

        for _ in range(smooth_iters):
            new_weights = raw_weights.copy()
            for i in range(v_count):
                neighbors = adj[i]
                if not neighbors:
                    continue
                avg_n = sum(raw_weights[n] for n in neighbors) / len(neighbors)
                new_weights[i] = (raw_weights[i] * (1.0 - smooth_factor)
                                  + avg_n * smooth_factor)
            if sync_seams:
                for group in seam_groups:
                    avg = sum(new_weights[idx] for idx in group) / len(group)
                    for idx in group:
                        new_weights[idx] = avg
            raw_weights = new_weights

    if vg_name is None:
        vg_name = active_kb.name
    existing = obj.vertex_groups.get(vg_name)
    if existing:
        obj.vertex_groups.remove(existing)
    vg = obj.vertex_groups.new(name=vg_name)

    for i, w in enumerate(raw_weights):
        if w > 0.001:
            vg.add([i], min(1.0, w), 'REPLACE')

    return valid_count


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


def build_chain_from_head(head_name, arm_obj):
    """
    从 head_name 骨骼向下遍历，返回骨骼名列表（从根到末）。
    遇到分叉（多个子骨）时截断，不进入任何分支。
    需在 EDIT 模式下调用。
    """
    bones = arm_obj.data.edit_bones
    chain = []
    current = head_name
    while current:
        bone = bones.get(current)
        if bone is None:
            break
        chain.append(current)
        children = bone.children
        if len(children) == 1:
            current = children[0].name
        else:
            break
    return chain