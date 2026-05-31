import bpy, mathutils
from .i18n import _
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES, _normalize_bone_name, auto_detect_preset, resolve_preset
from . import weight_utils, bone_utils


def _build_fuzzy_preset_bones(mapper, arm_obj):
    """用模糊匹配在骨架上构建预设骨骼集合，与 get_matches_for_standard 逻辑一致。
    返回的集合元素是骨架上的实际骨骼名，而非 JSON 中的字面量。
    顶级 exclude 字段中的骨骼也会被并入集合（仅用于排除物理骨识别，不参与对齐/随动）。"""
    preset_bones = set()
    for std_key in mapper.mapping_data.keys():
        main_actual, aux_actuals = mapper.get_matches_for_standard(arm_obj, std_key)
        if main_actual:
            preset_bones.add(main_actual)
        preset_bones.update(aux_actuals)
    # exclude 骨骼：直接按名称并入（无需模糊匹配，使用者自行确保名称准确）
    existing = {b.name for b in arm_obj.data.bones}
    preset_bones.update(mapper.exclude_bones & existing)
    return preset_bones


def _apply_bone_color(pb, role):
    pb.color.palette = 'CUSTOM'
    if role == "head":
        pb.color.custom.normal = (0.10, 0.62, 1.00)
        pb.color.custom.select = (0.40, 0.80, 1.00)
        pb.color.custom.active = (0.70, 0.93, 1.00)
    elif role == "branch_head":
        pb.color.custom.normal = (0.70, 0.20, 1.00)
        pb.color.custom.select = (0.83, 0.50, 1.00)
        pb.color.custom.active = (0.93, 0.75, 1.00)
    elif role == "main_continue":
        pb.color.custom.normal = (1.0, 0.70, 0.10)
        pb.color.custom.select = (1.0, 0.85, 0.40)
        pb.color.custom.active = (1.0, 0.95, 0.70)
    else:  # body / _End / untagged
        pb.color.custom.normal = (0.18, 0.42, 0.90)
        pb.color.custom.select = (0.45, 0.65, 1.00)
        pb.color.custom.active = (0.70, 0.85, 1.00)


def _apply_physics_bone_colors(arm_obj, preset_bones):
    """根据 chain_role 自定义属性为物理骨骼应用四色标记系统。
    会切换到姿态模式执行，调用后停留在姿态模式。
    preset_bones: 基础骨骼名称集合（这些骨骼不会被修改颜色）"""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm_obj.pose.bones:
        if pb.name in preset_bones:
            continue
        _apply_bone_color(pb, pb.get("chain_role", "body"))

class MODDER_OT_ApplyStandardX(bpy.types.Operator):
    """执行标准化 X：合并权重并重命名为基础名"""
    bl_idname = "modder.apply_standard_x"
    bl_label = "1. 标准化重命名 (X)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        # 1. 加载预设
        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("预设加载失败"))
            return {'CANCELLED'}

        # 2. 匹配分析
        analysis = {}
        for std_key in STANDARD_BONE_NAMES:
            main, auxs = mapper.get_matches_for_standard(arm_obj, std_key)
            if main or auxs: analysis[std_key] = (main, auxs)

        # 3. 权重合并
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm_obj]
        bpy.ops.object.mode_set(mode='OBJECT')
        for mesh_obj in meshes:
            for std_key, (main_name, aux_list) in analysis.items():
                if aux_list:
                    # 没找到主骨名时，使用标准名作为目标顶点组，方便后续手动处理
                    target_vg = main_name if main_name else std_key
                    weight_utils.merge_vgroups_multi(mesh_obj, aux_list, target_vg)

        # 4. 骨骼重命名 (Edit Mode)
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        rename_count = 0
        deleted_count = 0
        
        for std_key, (main_name, aux_list) in analysis.items():
            # 只有当主骨存在时，才执行重命名
            if main_name and main_name in edit_bones:
                edit_bones[main_name].name = std_key
                rename_count += 1
            
            # 无论主骨是否存在，辅助骨都要清理 (因为权重已经转移了)
            for aux_name in aux_list:
                if aux_name in edit_bones:
                    edit_bones.remove(edit_bones[aux_name])
                    deleted_count += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("标准化完成: 重命名 %d 根, 清理 %d 根辅助骨") % (rename_count, deleted_count))
        return {'FINISHED'}

class MODDER_OT_ApplyStandardY(bpy.types.Operator):
    """执行标准化 Y：将基础名转为目标游戏名"""
    bl_idname = "modder.apply_standard_y"
    bl_label = "2. 转换为游戏名 (Y)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_obj, False)
        if y_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        mapper = BoneMapManager()
        if not mapper.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, _("无法加载 Y 预设"))
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        for std_key in STANDARD_BONE_NAMES:
            if std_key in edit_bones:
                target_data = mapper.mapping_data.get(std_key)
                if target_data and target_data.get("main"):
                    edit_bones[std_key].name = target_data["main"][0]

        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
    
class MODDER_OT_DirectConvert(bpy.types.Operator):
    """将选中网格的顶点组转换成目标游戏的格式"""
    bl_idname = "modder.direct_convert"
    bl_label = "一键转换 (X -> Y)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings

        # 1. 获取选中的所有网格对象
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected_meshes:
            self.report({'ERROR'}, _("请至少选中一个网格 (Mesh)"))
            return {'CANCELLED'}

        if settings.import_preset_enum == 'AUTO' and settings.target_preset_enum == 'AUTO':
            self.report({'WARNING'}, _("重命名顶点组 (X+Y) 无法同时自动识别两个预设，因为操作对象为网格，没有独立的目标骨架来识别 Y 预设。请手动选择其中一个预设"))
            return {'CANCELLED'}

        arm_for_detect = next((m.find_armature() for m in selected_meshes if m.find_armature()), None)

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_for_detect, True)
        if x_preset is None:
            self.report({'WARNING'}, _("来源预设 (X): ") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_for_detect, False)
        if y_preset is None:
            self.report({'WARNING'}, _("目标预设 (Y): ") + err)
            return {'CANCELLED'}

        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载 X 预设"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, _("无法加载 Y 预设"))
            return {'CANCELLED'}

        # 3. 预计算转换规则
        # 需要知道：标准键 -> (源主名, 源辅助列表, 目标主名)
        conversion_rules = []
        
        for std_key in STANDARD_BONE_NAMES:
            # A. 从 X 表获取源信息
            src_entry = mapper_x.mapping_data.get(std_key)
            if not src_entry: continue
            
            src_mains = src_entry.get("main", [])
            src_auxs = src_entry.get("aux", [])
            
            # B. 从 Y 表获取目标信息
            tgt_entry = mapper_y.mapping_data.get(std_key)
            tgt_mains = tgt_entry.get("main", []) if tgt_entry else []
            
            # 降级拦截器 
            if std_key == "spine_03" and not tgt_mains:
                # 目标游戏不支持 spine_03，寻找 Y 预设中的 spine_02 作为降级替代
                fallback_entry = mapper_y.mapping_data.get("spine_02")
                if fallback_entry and fallback_entry.get("main"):
                    fallback_target = fallback_entry["main"][0]
                    # 强行将 spine_03 的源骨骼分配给 spine_02 的目标名
                    conversion_rules.append((src_mains, src_auxs, fallback_target))
                continue

            if src_mains and tgt_mains:
                # 规则：(源主名列表, 源辅助名列表, 目标主名)
                # 取第一个目标主名作为最终名字
                conversion_rules.append((src_mains, src_auxs, tgt_mains[0]))

        if not conversion_rules:
            self.report({'WARNING'}, _("X与Y预设之间没有共同的骨骼映射"))
            return {'CANCELLED'}

        # 4. 开始处理网格 (Object Mode)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        processed_count = 0
        
        for mesh_obj in selected_meshes:
            vgs = mesh_obj.vertex_groups
            mesh_updated = False

            # 归一化顶点组查找表，与骨骼名模糊匹配逻辑保持一致
            norm_vg = {_normalize_bone_name(vg.name): vg.name for vg in vgs}

            def find_vg(name):
                if name in vgs:
                    return name
                return norm_vg.get(_normalize_bone_name(name))

            for src_mains, src_auxs, tgt_name in conversion_rules:
                # 步骤 A: 确定当前网格上实际存在哪个”源主顶点组”
                # (X预设里 main 可能有多个候选，如 [“UpperArm_L”, “Left Arm”]，我们要找 Mesh 上有的那个)
                real_src_main = None
                for candidate in src_mains:
                    actual = find_vg(candidate)
                    if actual:
                        real_src_main = actual
                        break

                # 确定权重的去向：
                # 有 源主组 -> 合并到源主组 (稍后改名)
                # 无 源主组 -> 直接合并到目标名 (tgt_name)
                target_vg = real_src_main if real_src_main else tgt_name

                # 步骤 B: 合并辅助权重
                # 找出当前网格上实际存在的辅助组（模糊匹配）
                real_auxs = [find_vg(aux) for aux in src_auxs if find_vg(aux)]
                if real_auxs:
                    weight_utils.merge_vgroups_multi(mesh_obj, real_auxs, target_vg)
                    mesh_updated = True
                
                # 步骤 C: 重命名主顶点组 -> 目标名
                # 只有当名字不同时才改名，防止报错
                if real_src_main and real_src_main != tgt_name:
                    if tgt_name in vgs: vgs.remove(vgs[tgt_name])
                    vgs[real_src_main].name = tgt_name
                    mesh_updated = True
            
            if mesh_updated:
                processed_count += 1

        self.report({'INFO'}, _("处理完成: 已更新 %d 个网格的顶点组") % processed_count)
        return {'FINISHED'}
    
class MODDER_OT_UniversalSnap(bpy.types.Operator):
    """将目标游戏骨架的身体骨骼对齐来源预设骨骼（后选要修改的目标骨架）"""
    bl_idname = "modder.universal_snap"
    bl_label = "0. 骨架对齐 (Snap)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        selected_objs = [o for o in context.selected_objects if o.type == 'ARMATURE']
        
        # 1. 检查选中项
        if len(selected_objs) != 2 or not context.active_object:
            self.report({'ERROR'}, _("操作对象错误: 请先选中源骨架(X)，再按住Ctrl选中目标骨架(Y)"))
            return {'CANCELLED'}
            
        target_arm = context.active_object  # 活动的是目标 (Y, 如 MHWI)
        source_arm = [o for o in selected_objs if o != target_arm][0]  # 另一个是源 (X, 如 VRC)

        x_preset, err = resolve_preset(settings.import_preset_enum, source_arm, True)
        if x_preset is None:
            self.report({'WARNING'}, _("来源预设 (X): ") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, target_arm, False)
        if y_preset is None:
            self.report({'WARNING'}, _("目标预设 (Y): ") + err)
            return {'CANCELLED'}

        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载 X 预设"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, _("无法加载 Y 预设"))
            return {'CANCELLED'}

        # 3. 预计算源骨骼的世界坐标 (在 Object 模式下进行)
        # 结构: { StandardName: Source_Head_World_Pos }
        source_positions = {} 
        source_mw = source_arm.matrix_world
        
        for std_key in STANDARD_BONE_NAMES:
            src_name, _aux = mapper_x.get_matches_for_standard(source_arm, std_key)
            if src_name:
                try:
                    b = source_arm.data.bones[src_name]
                    # 我们只需要头部坐标即可，尾部会通过刚性移动自动计算
                    source_positions[std_key] = source_mw @ b.head_local
                except KeyError:
                    pass

        # 4. 进入编辑模式执行对齐
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones
        target_mw_inv = target_arm.matrix_world.inverted()
        
        aligned_count = 0
        
        # 按 STANDARD_BONE_NAMES 的顺序遍历 (通常是 Hips -> Spine -> Head)
        # 这样父级移动后，子级会先跟随移动，然后子级再根据自己的目标进行微调
        for std_key in STANDARD_BONE_NAMES:
            if std_key not in source_positions:
                continue
                
            # 获取目标骨名 (从 Y 表)
            tgt_entry = mapper_y.mapping_data.get(std_key)
            if not tgt_entry or not tgt_entry.get('main'):
                continue
            
            # 检查 skip_snap 标记 (某些游戏的特定骨骼不允许移动)
            if tgt_entry.get('skip_snap', False):
                continue
                
            tgt_name = tgt_entry['main'][0]
            if tgt_name not in edit_bones:
                continue
                
            t_bone = edit_bones[tgt_name]
            
            # --- 核心对齐逻辑 ---
            
            # A. 计算目标点 (转为 Target 本地坐标)
            src_head_world = source_positions[std_key]
            target_head_local = target_mw_inv @ src_head_world
            
            # B. 计算移动向量
            old_head = t_bone.head.copy()
            offset = target_head_local - old_head
            
            # C. 移动当前骨骼 (保持长度和方向)
            t_bone.head = target_head_local
            t_bone.tail += offset # 尾部跟随移动，保持骨骼向量不变
            
            # D. 刚性传递：递归移动所有子级
            bone_utils.propagate_movement(t_bone, offset)
            
            aligned_count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("刚性对齐完成: %d 根骨骼") % aligned_count)
        return {'FINISHED'}
    
class MODDER_OT_SmartGraftBones(bpy.types.Operator):
    """
    智能物理骨移植 (末端延伸版):
    1. 复制物理骨骼 (直接世界坐标对齐)。
    2. 【新功能】自动为物理链末端添加 _End 骨骼 (在竖直重置前生成)。
    3. 强制断开连接，防止位置吸附。
    4. 统一将所有移植骨骼重置为竖直向上 (Z+)。
    """
    bl_idname = "modder.smart_graft"
    bl_label = "3. 物理骨移植 (+End Bone)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # --- 1. 场景校验 ---
        sel_objs = context.selected_objects
        target_arm = context.active_object # Out (目标)

        if not target_arm or target_arm.type != 'ARMATURE':
            self.report({'ERROR'}, _("操作失败：请先选择 In 骨架，再 Ctrl 加选 Out 骨架(Out需为黄色激活状态)"))
            return {'CANCELLED'}
        
        source_arm = None # In (来源)
        for obj in sel_objs:
            if obj != target_arm and obj.type == 'ARMATURE':
                source_arm = obj
                break
        
        if not source_arm:
            self.report({'ERROR'}, _("操作失败：未找到来源(In)骨架"))
            return {'CANCELLED'}

        # --- 2. 加载预设 (仅用于排除非物理骨) ---
        from .bone_mapper import BoneMapManager
        settings = context.scene.mhw_suite_settings

        x_preset, err = resolve_preset(settings.import_preset_enum, source_arm, True)
        if x_preset is None:
            self.report({'WARNING'}, _("来源预设 (X): ") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, target_arm, False)
        if y_preset is None:
            self.report({'WARNING'}, _("目标预设 (Y): ") + err)
            return {'CANCELLED'}

        src_mapper = BoneMapManager()
        if not src_mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载源预设 (In)"))
            return {'CANCELLED'}

        tgt_mapper = BoneMapManager()
        if not tgt_mapper.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, _("无法加载目标预设 (Out)"))
            return {'CANCELLED'}

        # --- 3. 构建查找表 ---
        # 用 get_matches_for_standard 做模糊匹配，与对齐功能保持一致，
        # 避免命名习惯不同的基础骨（如 UpperLeg.L vs UpperLeg_L）被误判为物理骨
        src_to_std = {}
        all_preset_bones_src = set()

        for std_key in src_mapper.mapping_data.keys():
            main_actual, aux_actuals = src_mapper.get_matches_for_standard(source_arm, std_key)
            if main_actual:
                src_to_std[main_actual] = std_key
                all_preset_bones_src.add(main_actual)
            for aux_actual in aux_actuals:
                src_to_std[aux_actual] = std_key
                all_preset_bones_src.add(aux_actual)

        std_to_tgt_bone = {}
        for std_key, entry in tgt_mapper.mapping_data.items():
            mains = entry.get('main', [])
            if mains:
                std_to_tgt_bone[std_key] = mains[0]

        # --- 4. 筛选物理骨 ---
        # 只要不在预设里的，都算物理骨
        physics_bones_names = [b.name for b in source_arm.data.bones if b.name not in all_preset_bones_src]
        physics_bones_set = set(physics_bones_names) # 用于快速查找

        if not physics_bones_names:
            self.report({'WARNING'}, _("未检测到物理骨骼"))
            return {'FINISHED'}

        # --- 5. 核心移植逻辑 ---
        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones
        
        tgt_mat_inv = target_arm.matrix_world.inverted()
        import mathutils

        created_count = 0
        new_bones_map = {} # {src_name: new_bone_name}
        
        # 临时列表：存储所有新生成的骨骼对象（包括标准物理骨和End骨）以便稍后统一竖直化
        # 格式: (edit_bone, length_to_use)
        bones_to_verticalize = []

        # 5.1 第一轮：创建所有基础物理骨
        for p_name in physics_bones_names:
            src_bone = source_arm.data.bones.get(p_name)
            src_pb = source_arm.pose.bones.get(p_name)
            if not src_bone or not src_pb: continue
            
            if p_name in edit_bones:
                eb = edit_bones[p_name]
            else:
                eb = edit_bones.new(p_name)
            new_bones_map[p_name] = eb.name
            
            # 基础定位 (Head)
            src_world_head = source_arm.matrix_world @ src_pb.head
            eb.head = tgt_mat_inv @ src_world_head
            # 暂时随便给个 Tail，稍后会被竖直化覆盖
            eb.tail = eb.head + mathutils.Vector((0, 0, 0.1))
            
            # 加入待处理列表
            bones_to_verticalize.append((eb, src_bone.length))

        # 5.2 第二轮：检测末端并创建 _End 骨骼
        # (此时所有基础物理骨已创建，位置对应 Source Head)

        # 收集源骨架的绑定网格对象，用于尾骨权重检测
        mesh_objects = [o for o in bpy.data.objects
                        if o.type == 'MESH'
                        and any(m.type == 'ARMATURE' and m.object == source_arm
                                for m in o.modifiers)]

        for p_name in physics_bones_names:
            src_bone = source_arm.data.bones.get(p_name)

            # 需要 _End 的情况：
            # A. 分叉骨：有 ≥2 个物理子骨，但没有子骨标记为 main_continue
            # B. 叶骨：在物理骨集合中没有子级 且 有顶点权重（无权重视为已到尾骨）
            #    线性链（恰好一个物理子骨）不需要 _End
            physics_children = [c for c in src_bone.children if c.name in physics_bones_set]
            is_leaf = len(physics_children) == 0
            is_fork = len(physics_children) >= 2
            has_main_continue_child = any(
                source_arm.pose.bones.get(c.name) and
                source_arm.pose.bones[c.name].get("chain_role") == "main_continue"
                for c in physics_children
            )
            if is_leaf:
                needs_end = weight_utils.bone_has_weights(p_name, mesh_objects)
            elif is_fork and not has_main_continue_child:
                needs_end = True
            else:
                needs_end = False

            if needs_end:
                # 这是一个末端骨骼，需要生成 _End
                end_bone_name = f"{p_name}_End"
                if end_bone_name in edit_bones:
                    end_eb = edit_bones[end_bone_name]
                else:
                    end_eb = edit_bones.new(end_bone_name)
                
                # 【关键逻辑】：End 骨骼的头部 = 原 Source 骨骼的尾部
                src_pb = source_arm.pose.bones.get(p_name)
                src_world_tail = source_arm.matrix_world @ src_pb.tail
                
                end_eb.head = tgt_mat_inv @ src_world_tail
                # 暂时给个 Tail
                end_eb.tail = end_eb.head + mathutils.Vector((0, 0, 0.05))
                
                # 建立与父级的连接 (逻辑连接)
                if p_name in new_bones_map:
                    end_eb.parent = edit_bones[new_bones_map[p_name]]
                
                # 加入待处理列表 (End 骨骼长度固定为 0.05 或其他小数值)
                bones_to_verticalize.append((end_eb, 0.05))

        # 5.3 第三轮：统一竖直化 (Vertical Reset)
        # 这一步会覆盖刚才的 Tail 位置
        for eb, length in bones_to_verticalize:
            # 强制断连
            eb.use_connect = False
            
            # 竖直化 (保持 Head 不动)
            # 防止长度为 0
            safe_length = length if length > 0.001 else 0.05
            
            # 简单粗暴：Tail = Head + (0, 0, Length)
            # 由于断开了连接，这不会影响父子关系中的位置
            eb.tail = eb.head + mathutils.Vector((0, 0, safe_length))
            eb.roll = 0
            
            created_count += 1

        # --- 6. 智能重建父级 (仅针对基础物理骨，End骨刚才已处理) ---
        for src_name, tgt_name in new_bones_map.items():
            eb = edit_bones.get(tgt_name)
            src_bone = source_arm.data.bones.get(src_name)
            
            if not src_bone or not src_bone.parent: continue
            
            src_p_name = src_bone.parent.name
            target_parent_name = None

            # A. 父级是物理骨
            if src_p_name in new_bones_map:
                target_parent_name = new_bones_map[src_p_name]
            # B. 父级是映射骨 (Main/Aux)
            elif src_p_name in src_to_std:
                std_key = src_to_std[src_p_name]
                if std_key in std_to_tgt_bone:
                    target_parent_name = std_to_tgt_bone[std_key]
                else:
                    # 目标骨架没有该标准骨（如 spine_03 在 MHWI/MHWS 中不存在）
                    # 沿源预设骨父链向上查找第一个有目标映射的祖先
                    walk = source_arm.data.bones.get(src_p_name)
                    while walk and walk.parent:
                        walk = walk.parent
                        if walk.name in src_to_std:
                            fallback_key = src_to_std[walk.name]
                            if fallback_key in std_to_tgt_bone:
                                target_parent_name = std_to_tgt_bone[fallback_key]
                                break

            if target_parent_name and target_parent_name in edit_bones:
                eb.parent = edit_bones[target_parent_name]
                eb.use_connect = False 

        # --- 7. 从源骨骼复制 chain_role 属性到目标骨骼 ---
        bpy.ops.object.mode_set(mode='POSE')
        for src_name, tgt_name in new_bones_map.items():
            src_pb = source_arm.pose.bones.get(src_name)
            tgt_pb = target_arm.pose.bones.get(tgt_name)
            if src_pb and tgt_pb:
                role = src_pb.get("chain_role")
                if role:
                    tgt_pb["chain_role"] = role

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("移植完成: 处理 %d 根骨骼 (含自动生成的末端骨)") % created_count)
        return {'FINISHED'}



class MODDER_OT_MergePhysicsWeights(bpy.types.Operator):
    """将物理骨骼的顶点组权重合并到其最近的基础骨骼上 (通过 X 预设判断)。\n用于不需要物理效果或目标游戏不支持物理的降级场景"""
    bl_idname = "modder.merge_physics_weights"
    bl_label = "物理权重降级"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        
        # 获取选中的网格
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected_meshes:
            self.report({'ERROR'}, _("请至少选中一个网格"))
            return {'CANCELLED'}

        # 需要一个骨架来分析骨骼层级
        arm_obj = None
        for mesh_obj in selected_meshes:
            arm = mesh_obj.find_armature()
            if arm:
                arm_obj = arm
                break

        if not arm_obj:
            self.report({'ERROR'}, _("选中的网格没有绑定骨架"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        # 加载 X 预设，判断哪些是基础骨骼
        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载 X 预设"))
            return {'CANCELLED'}

        # 用模糊匹配构建预设骨骼集合，避免命名习惯不同的基础骨被误判为物理骨
        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        # 为每根物理骨找到其归属的基础骨骼 (沿父级链向上找)
        # physics_to_base: {physics_bone_name: base_bone_name}
        physics_to_base = {}
        
        for bone in arm_obj.data.bones:
            if bone.name in preset_bones:
                continue  # 是基础骨骼，跳过
            
            # 沿父级链向上找第一个基础骨骼
            parent = bone.parent
            while parent:
                if parent.name in preset_bones:
                    physics_to_base[bone.name] = parent.name
                    break
                parent = parent.parent
            # 如果找不到基础父级 (孤儿物理骨)，跳过
        
        if not physics_to_base:
            self.report({'INFO'}, _("未检测到物理骨骼的顶点组"))
            return {'FINISHED'}
        
        # 对每个网格执行权重合并
        bpy.ops.object.mode_set(mode='OBJECT')
        total_merged = 0
        
        for mesh_obj in selected_meshes:
            vgs = mesh_obj.vertex_groups
            merged_in_mesh = 0
            
            for phys_name, base_name in physics_to_base.items():
                if phys_name not in vgs:
                    continue  # 这个网格没有这根物理骨的权重
                
                # 确保基础骨骼的顶点组存在
                if base_name not in vgs:
                    vgs.new(name=base_name)
                
                # 合并权重
                weight_utils.merge_vgroups_multi(mesh_obj, [phys_name], base_name)
                merged_in_mesh += 1
            
            total_merged += merged_in_mesh
        
        self.report({'INFO'}, _("物理权重降级完成: 在 %d 个网格上合并了 %d 个物理顶点组") % (len(selected_meshes), total_merged))
        return {'FINISHED'}


class MODDER_OT_RenameBonesToTarget(bpy.types.Operator):
    """将骨架上的基础骨骼名从来源名 (X) 改为目标游戏名 (Y)。\n用于手动对齐工作流: 改名后骨骼名与目标游戏一致, 方便手动对齐和数据传递"""
    bl_idname = "modder.rename_bones_to_target"
    bl_label = "基础骨骼改名 (X->Y)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        if settings.import_preset_enum == 'AUTO' and settings.target_preset_enum == 'AUTO':
            self.report({'WARNING'}, _("基础骨骼改名 (X+Y) 无法同时自动识别两个预设，因为操作对象为单一骨架，无法区分 X 和 Y。请手动选择其中一个预设"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, _("来源预设 (X): ") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_obj, False)
        if y_preset is None:
            self.report({'WARNING'}, _("目标预设 (Y): ") + err)
            return {'CANCELLED'}

        # 加载 X 和 Y 预设
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载 X 预设"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, _("无法加载 Y 预设"))
            return {'CANCELLED'}

        # 通过标准键桥接: X 实际骨骼名 -> 标准键 -> Y 目标骨骼名
        rename_map = {}  # {当前骨骼名: 目标骨骼名}
        
        for std_key in STANDARD_BONE_NAMES:
            # 在骨架上找到 X 预设匹配的实际骨骼
            src_name, _aux = mapper_x.get_matches_for_standard(arm_obj, std_key)
            if not src_name:
                continue
            
            # 从 Y 预设获取目标名
            tgt_entry = mapper_y.mapping_data.get(std_key)
            if not tgt_entry or not tgt_entry.get('main'):
                continue
            tgt_name = tgt_entry['main'][0]
            
            # 跳过名字相同的
            if src_name != tgt_name:
                rename_map[src_name] = tgt_name
        
        if not rename_map:
            self.report({'INFO'}, _("没有需要改名的骨骼 (来源和目标名称已一致)"))
            return {'FINISHED'}
        
        # 进入编辑模式执行改名
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        renamed_count = 0
        
        for old_name, new_name in rename_map.items():
            if old_name in edit_bones:
                # 如果目标名已被占用 (可能有同名骨骼), 先给它加后缀避让
                if new_name in edit_bones and new_name != old_name:
                    edit_bones[new_name].name = new_name + "_old"
                edit_bones[old_name].name = new_name
                renamed_count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("已将 %d 根骨骼改名为目标游戏名") % renamed_count)
        return {'FINISHED'}


class MODDER_OT_RemoveNonBaseBones(bpy.types.Operator):
    """删除骨架中所有非基础骨骼 (通过 X 预设判断)。\n建议先执行物理权重降级再使用此功能"""
    bl_idname = "modder.remove_non_base_bones"
    bl_label = "剔除非基础骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, _("无法加载 X 预设"))
            return {'CANCELLED'}
        
        # 用模糊匹配构建基础骨骼集合，避免命名习惯不同的基础骨被误删
        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        # 找出所有非基础骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        to_remove = [b.name for b in edit_bones if b.name not in preset_bones]
        
        if not to_remove:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, _("没有需要剔除的骨骼"))
            return {'FINISHED'}
        
        # 删除
        for name in to_remove:
            if name in edit_bones:
                edit_bones.remove(edit_bones[name])
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("已剔除 %d 根非基础骨骼") % len(to_remove))
        return {'FINISHED'}


class MODDER_OT_SetBoneVisibility(bpy.types.Operator):
    """按模式控制骨骼可见性（全显 / 仅基础骨 / 仅物理骨），后两者需加载 X 预设"""
    bl_idname = "modder.set_bone_visibility"
    bl_label = "骨骼可见性"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        items=[
            ('ALL',     '全显',    '显示所有骨骼'),
            ('BASE',    '仅基础骨', '隐藏物理骨，只显示预设基础骨'),
            ('PHYSICS', '仅物理骨', '隐藏基础骨，只显示物理骨'),
        ],
        default='ALL'
    )

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        preset_bones = set()
        if self.mode != 'ALL':
            x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
            if x_preset is None:
                self.report({'WARNING'}, err)
                return {'CANCELLED'}
            mapper = BoneMapManager()
            if not mapper.load_preset(x_preset, is_import_x=True):
                self.report({'ERROR'}, _("预设加载失败"))
                return {'CANCELLED'}
            preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        bpy.ops.object.mode_set(mode='POSE')
        for bone in arm_obj.data.bones:
            if self.mode == 'ALL':
                bone.hide = False
            elif self.mode == 'BASE':
                bone.hide = bone.name not in preset_bones
            else:  # PHYSICS
                bone.hide = bone.name in preset_bones

        settings.bone_view_mode = self.mode
        labels = {'ALL': '全显', 'BASE': '仅基础骨', 'PHYSICS': '仅物理骨'}
        self.report({'INFO'}, _("骨骼显示: %s") % labels[self.mode])
        return {'FINISHED'}


def _detect_chain_roles(arm_obj, preset_bones):
    """根据骨骼拓扑自动写入 chain_role。
    - 主链首（父骨不是物理骨）→ 'head'
    - 分叉子骨（父骨有 ≥2 个物理子骨）→ 'branch_head'（已手动设为 main_continue 的保留）
    - 拓扑已变、不再是链首 → 清除 head/branch_head
    - main_continue 及普通体骨不受影响。
    需在 POSE 模式下调用。"""
    physics_bones = {b.name for b in arm_obj.data.bones if b.name not in preset_bones}
    fork_bones = {
        b.name for b in arm_obj.data.bones
        if b.name in physics_bones
        and sum(1 for c in b.children if c.name in physics_bones) >= 2
    }
    for b in arm_obj.data.bones:
        if b.name not in physics_bones:
            continue
        pb = arm_obj.pose.bones.get(b.name)
        if not pb:
            continue
        is_main_head = (b.parent is None or b.parent.name not in physics_bones)
        is_branch_head = (not is_main_head and b.parent.name in fork_bones)
        current_role = pb.get("chain_role")
        if is_main_head:
            pb["chain_role"] = "head"
        elif is_branch_head:
            if current_role != "main_continue":
                pb["chain_role"] = "branch_head"
        elif current_role in ("head", "branch_head"):
            del pb["chain_role"]


def _run_bone_color_refresh(context, arm_obj):
    """运行骨骼颜色刷新核心逻辑（供其他操作符复用，不含 report）。
    成功返回 (True, preset_name)，失败返回 (False, error_message)。"""
    settings = context.scene.mhw_suite_settings
    mapper = BoneMapManager()
    detected = auto_detect_preset(arm_obj, is_import_x=True)
    if detected:
        if not mapper.load_preset(detected, is_import_x=True):
            return False, _("无法加载自动识别的预设")
    else:
        fallback = settings.import_preset_enum
        if fallback == 'AUTO':
            return False, _("未能自动识别预设，请手动选择 X 预设")
        if not mapper.load_preset(fallback, is_import_x=True):
            return False, _("无法加载 X 预设")
    preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    _detect_chain_roles(arm_obj, preset_bones)
    for b in arm_obj.data.bones:
        if b.name in preset_bones:
            pb = arm_obj.pose.bones.get(b.name)
            if pb:
                if "chain_role" in pb:
                    del pb["chain_role"]
                pb.color.palette = 'DEFAULT'
    _apply_physics_bone_colors(arm_obj, preset_bones)
    return True, mapper.preset_info.get('name', detected or fallback or "")


class MODDER_OT_RefreshPhysicsBoneColors(bpy.types.Operator):
    """根据骨骼的 chain_role 自定义属性刷新物理骨骼的颜色标记"""
    bl_idname = "modder.refresh_physics_bone_colors"
    bl_label = "刷新骨骼颜色"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='POSE')

        selected = context.selected_pose_bones or []
        partial = bool(selected)

        settings = context.scene.mhw_suite_settings
        mapper = BoneMapManager()

        detected = auto_detect_preset(arm_obj, is_import_x=True)
        if detected:
            if not mapper.load_preset(detected, is_import_x=True):
                self.report({'ERROR'}, _("无法加载自动识别的预设"))
                return {'CANCELLED'}
        else:
            fallback = settings.import_preset_enum
            if fallback == 'AUTO':
                self.report({'WARNING'}, _("未能自动识别预设，请手动选择 X 预设"))
                return {'CANCELLED'}
            if not mapper.load_preset(fallback, is_import_x=True):
                self.report({'ERROR'}, _("无法加载 X 预设"))
                return {'CANCELLED'}
            fallback_name = mapper.preset_info.get('name', fallback)
            self.report({'WARNING'}, _("未能自动识别目标游戏预设，回退至来源预设 [%s]，建议手动切换") % fallback_name)

        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        # 始终对全骨架做拓扑分析，保证 chain_role 正确
        _detect_chain_roles(arm_obj, preset_bones)

        if partial:
            selected_names = {pb.name for pb in selected}
            for b in arm_obj.data.bones:
                if b.name not in selected_names:
                    continue
                pb = arm_obj.pose.bones.get(b.name)
                if not pb:
                    continue
                if b.name in preset_bones:
                    if "chain_role" in pb:
                        del pb["chain_role"]
                    pb.color.palette = 'DEFAULT'
                else:
                    _apply_bone_color(pb, pb.get("chain_role", "body"))
        else:
            for b in arm_obj.data.bones:
                if b.name in preset_bones:
                    pb = arm_obj.pose.bones.get(b.name)
                    if pb:
                        if "chain_role" in pb:
                            del pb["chain_role"]
                        pb.color.palette = 'DEFAULT'
            _apply_physics_bone_colors(arm_obj, preset_bones)

        preset_label = ""
        if detected:
            preset_label = _("（自动识别预设：%s）") % mapper.preset_info.get('name', detected)

        if partial:
            self.report({'INFO'}, (_("已刷新 %d 根骨骼") % len(selected)) + preset_label)
        else:
            self.report({'INFO'}, _("骨骼颜色已刷新") + preset_label)
        return {'FINISHED'}


class MODDER_OT_MarkAsMainContinue(bpy.types.Operator):
    """将选中骨骼标记为主链延伸 (chain_role = main_continue)，并染为琥珀金色。
在分叉处标记哪个子骨是主链方向，未标记的子骨将被视为支链头"""
    bl_idname = "modder.mark_as_main_continue"
    bl_label = "标记为主链延伸"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        selected = context.selected_pose_bones
        if not selected:
            self.report({'WARNING'}, _("请在姿态模式下选中骨骼"))
            return {'CANCELLED'}
        for pb in selected:
            pb["chain_role"] = "main_continue"
            pb.color.palette = 'CUSTOM'
            pb.color.custom.normal = (1.0, 0.70, 0.10)
            pb.color.custom.select = (1.0, 0.85, 0.40)
            pb.color.custom.active = (1.0, 0.95, 0.70)
        self.report({'INFO'}, _("已标记 %d 根骨骼为主链延伸") % len(selected))
        return {'FINISHED'}


class MODDER_OT_ClearChainRole(bpy.types.Operator):
    """清除选中骨骼的 chain_role 标记，恢复为普通体骨（深蓝色）"""
    bl_idname = "modder.clear_chain_role"
    bl_label = "清除链角色标记"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        selected = context.selected_pose_bones
        if not selected:
            self.report({'WARNING'}, _("请在姿态模式下选中骨骼"))
            return {'CANCELLED'}
        for pb in selected:
            if "chain_role" in pb:
                del pb["chain_role"]
        self.report({'INFO'}, _("已清除 %d 根骨骼的链角色标记") % len(selected))
        return {'FINISHED'}


class MODDER_OT_MergeIntoParent(bpy.types.Operator):
    """将选中骨骼的顶点权重合并到其父骨骼，并删除选中骨骼。
用于清理功能性根骨（如 hair_root 等无物理模拟的连接器骨骼）"""
    bl_idname = "modder.merge_into_parent"
    bl_label = "合并到父骨"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        if context.mode == 'POSE':
            selected_names = [pb.name for pb in context.selected_pose_bones]
        elif context.mode == 'EDIT_ARMATURE':
            selected_names = [b.name for b in context.selected_editable_bones]
        else:
            self.report({'ERROR'}, _("请在姿态模式或编辑模式下操作"))
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        bones_data = arm_obj.data.bones
        pairs = []
        for name in selected_names:
            bone = bones_data.get(name)
            if bone and bone.parent:
                pairs.append((bone.parent.name, name))

        if not pairs:
            self.report({'WARNING'}, _("选中的骨骼没有可用的父骨骼"))
            return {'CANCELLED'}

        # 断开子骨连接，防止删除父骨后子骨位置被吸附
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        for _parent_name, delete_name in pairs:
            eb = edit_bones.get(delete_name)
            if eb:
                for child in eb.children:
                    child.use_connect = False

        bpy.ops.object.mode_set(mode='OBJECT')
        weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)

        settings = context.scene.mhw_suite_settings
        mapper = BoneMapManager()
        _x, _unused = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if _x and mapper.load_preset(_x, is_import_x=True):
            preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
            bpy.context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='POSE')
            _detect_chain_roles(arm_obj, preset_bones)
            _apply_physics_bone_colors(arm_obj, preset_bones)
        bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, _("已合并 %d 根骨骼到父骨") % len(pairs))
        return {'FINISHED'}


classes = [
    MODDER_OT_ApplyStandardX,
    MODDER_OT_ApplyStandardY,
    MODDER_OT_DirectConvert,
    MODDER_OT_UniversalSnap,
    MODDER_OT_SmartGraftBones,
    MODDER_OT_MergePhysicsWeights,
    MODDER_OT_RemoveNonBaseBones,
    MODDER_OT_RenameBonesToTarget,
    MODDER_OT_SetBoneVisibility,
    MODDER_OT_RefreshPhysicsBoneColors,
    MODDER_OT_MarkAsMainContinue,
    MODDER_OT_ClearChainRole,
    MODDER_OT_MergeIntoParent,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)