import bpy, mathutils, json
from .i18n import T
from .bone_mapper import (BoneMapManager, STANDARD_BONE_NAMES, _normalize_bone_name,
                          auto_detect_preset, resolve_preset, standard_keys, is_aux_key,
                          AUX_PARENT)
from . import (weight_utils, bone_utils, chain_classifier, twist_chain, fork_resolver,
               physics_simplify, mhwi_physics_budget)

#: 用户手动指定、刷新角色时不能被拓扑检测覆盖的角色。no_chain 是分叉判定把超过层数
#: 的子树标成"不生成链"用的。
_STICKY_ROLES = ("main_continue", "no_chain")


def _build_fuzzy_preset_bones(mapper, arm_obj):
    """用模糊匹配在骨架上构建预设骨骼集合，与 get_matches_for_standard 逻辑一致。
    返回的集合元素是骨架上的实际骨骼名，而非 JSON 中的字面量。
    顶级 exclude 字段中的骨骼也会被并入集合（仅用于排除物理骨识别，不参与对齐/随动）。
    若预设游戏名在骨架中找不到（骨架已标准化），则回退到直接匹配标准键名本身。"""
    preset_bones = set()
    existing = {b.name for b in arm_obj.data.bones}
    for std_key in mapper.mapping_data.keys():
        main_actual, aux_actuals = mapper.get_matches_for_standard(arm_obj, std_key)
        if main_actual:
            preset_bones.add(main_actual)
        elif std_key in existing:
            # 回退：预设游戏名未命中，但骨架中有与标准键同名的骨骼（已标准化的情形）
            preset_bones.add(std_key)
        preset_bones.update(aux_actuals)
    # exclude 骨骼：按名称（或 * 通配）并入，不做模糊匹配
    preset_bones.update(mapper.exclude_matches(existing))
    # 姿态驱动修正骨：预设里列了的已经在上面的 aux 里，这里补的是**没列到**的。
    # 它们不是物理骨，落到物理那条路上会被当成链骨（终末地三具各有 28 / 16 / 0 根，
    # 而 arknights.json 列了 58 条 —— 资产之间数量本来就不一样，靠列表兜不住）。
    preset_bones.update(n for n in existing if chain_classifier.is_corrective_name(n))
    return preset_bones


def _load_protected_bones(arm_obj):
    """读取移植保护集合（transplant_protected_bones 自定义属性）。"""
    raw = arm_obj.get("transplant_protected_bones")
    if not raw:
        return set()
    try:
        return set(json.loads(raw))
    except (ValueError, TypeError):
        return set()


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
    elif role == "no_chain":
        pb.color.custom.normal = (0.45, 0.45, 0.45)
        pb.color.custom.select = (0.65, 0.65, 0.65)
        pb.color.custom.active = (0.85, 0.85, 0.85)
    else:  # body / _End / untagged
        pb.color.custom.normal = (0.18, 0.42, 0.90)
        pb.color.custom.select = (0.45, 0.65, 1.00)
        pb.color.custom.active = (0.70, 0.85, 1.00)


def _apply_physics_bone_colors(arm_obj, preset_bones, protected_bones=None):
    """根据 chain_role 自定义属性为物理骨骼应用四色标记系统。
    会切换到姿态模式执行，调用后停留在姿态模式。
    preset_bones: 基础骨骼名称集合（这些骨骼不会被修改颜色）
    protected_bones: 移植保护集合（移植前已存在于目标骨架的骨骼，不参与自动着色）"""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm_obj.pose.bones:
        if pb.name in preset_bones:
            continue
        if protected_bones and pb.name in protected_bones:
            continue
        _apply_bone_color(pb, pb.get("chain_role", "body"))

def _survey_correctives(arm_obj, mesh_objs, mapped_bones):
    """``(confirmed, heavy, suspects)``：可按修正骨处置的、其中权重离群的、以及结构不对的。

    *mapped_bones* 是"有确定去处"的骨名集合（预设 main + 标准键本身），用来判定
    父骨是否已映射。权重足迹按**每个带权重顶点的平均权重**算，不是总权重——总权重
    随网格密度变，均值不变。
    """
    bones = arm_obj.data.bones
    foot = {}
    for m in mesh_objs:
        idx2name = {vg.index: vg.name for vg in m.vertex_groups}
        for v in m.data.vertices:
            for g in v.groups:
                n = idx2name.get(g.group)
                if n is None or g.weight <= 0.0:
                    continue
                e = foot.setdefault(n, [0, 0.0])
                e[0] += 1
                e[1] += g.weight

    confirmed, heavy, suspects = [], [], []
    for b in bones:
        if not chain_classifier.is_corrective_name(b.name):
            continue
        cnt, total = foot.get(b.name, [0, 0.0])
        mean = (total / cnt) if cnt else None
        verdict = chain_classifier.classify_corrective(
            b.name, len(b.children) == 0,
            b.parent is not None and b.parent.name in mapped_bones, mean)
        row = (b.name, mean if mean is not None else 0.0)
        if verdict == "suspect":
            suspects.append(row)
        elif verdict == "heavy":
            # 照修正骨处置，但报出来 —— 权重不影响并入的正确性，只影响"它是不是修正骨"
            confirmed.append(row)
            heavy.append(row)
        elif verdict == "corrective":
            confirmed.append(row)
    return confirmed, heavy, suspects


def _normalize_weights_for(arm_obj):
    """对绑定到 *arm_obj* 的所有网格做形变权重归一化；没有网格时返回 None。

    用 pose_bake.attached_meshes 而不是 find_armature()：修改器目标为空的网格
    find_armature() 看不见，但它照样带着权重（实测某 MHWI 模型 19 个网格里有 5 个
    是这种），漏掉它们等于这个功能对它们无效。
    """
    from . import pose_bake
    meshes = [m for m in pose_bake.attached_meshes(arm_obj) if m.type == 'MESH']
    if not meshes:
        return None
    return weight_utils.normalize_deform_weights(meshes, arm_obj)


def _normalize_weights_message(stats):
    if not stats["fixed"] and not stats["unweighted"]:
        msg = T("core.standard_ops.normalize_weights_clean").format(
            verts=stats["verts"], meshes=stats["meshes"])
    else:
        msg = T("core.standard_ops.normalize_weights_done").format(
            fixed=stats["fixed"], verts=stats["verts"], meshes=stats["meshes"],
            worst=round(stats["worst_before"], 4), name=stats["worst_mesh"] or "-")
        if stats["unweighted"]:
            # 0/0 归一化救不了，只能报：这些顶点根本没被任何骨骼驱动，会留在原地。
            msg += " " + T("core.standard_ops.normalize_weights_unweighted").format(
                n=stats["unweighted"])
    if stats.get("mmd_junk_removed"):
        msg += " " + T("core.standard_ops.normalize_weights_mmd_junk").format(
            n=stats["mmd_junk_removed"])
    return msg


class MODDER_OT_NormalizeDeformWeights(bpy.types.Operator):
    """把骨骼形变权重逐顶点归一化到 1。

    越早做越好，最好在任何刷权重动作之前。归一化本身**不改变外观**——Blender 的
    骨架形变、以及 RE Mesh Editor 与 mod3 的导出器，都是先除以权重总和再用；
    所以总和跑偏可以一直不被发现。代价是在后续编辑里收：一旦在跑偏的顶点上刷一笔，
    Auto Normalize 会把其余组按比例放大，原本 0.02 的幽灵残留变成 0.2，
    从看不见变成看得见的错误影响，那时候再清理就贵了。
    """
    bl_idname = "modder.normalize_deform_weights"
    bl_label = "Normalize Deform Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.normalize_weights_desc")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object
        stats = _normalize_weights_for(arm_obj)
        if stats is None:
            self.report({'WARNING'}, T("core.standard_ops.normalize_weights_no_mesh"))
            return {'CANCELLED'}
        self.report({'INFO'}, _normalize_weights_message(stats))
        return {'FINISHED'}


class MODDER_OT_ApplyStandardX(bpy.types.Operator):
    bl_idname = "modder.apply_standard_x"
    bl_label = "1. Standardize Rename (X)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.apply_standard_x_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        # 先归一化，再动任何权重：标准化本身就要合并 aux 的权重，而合并会把跑偏的
        # 总和搅进目标组里，之后再想分辨哪部分是幽灵残留就没有依据了。这也是用户
        # 对导入的头像按下的第一个按钮，正是"越早越好"的那个时机。
        if getattr(settings, "normalize_weights_first", True):
            stats = _normalize_weights_for(arm_obj)
            if stats and (stats["fixed"] or stats["unweighted"] or stats["mmd_junk_removed"]):
                self.report({'INFO'}, _normalize_weights_message(stats))

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        # 1. 加载预设
        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.preset_load_failed"))
            return {'CANCELLED'}

        # 2. 匹配分析
        # 关掉辅助骨槽位时（默认），遍历的是原来那 52 个键，并把扭转骨/掌骨这些
        # 折回父段的 aux —— 效果与加槽位之前一致。打开时它们各占一个键，于是被
        # **改名保留**而不是并进主骨删掉。
        use_aux = not getattr(settings, "ignore_aux_bones", True)
        analysis = {}
        for std_key in standard_keys(use_aux):
            main, auxs = mapper.get_matches_for_standard(
                arm_obj, std_key, fold_aux=not use_aux)
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
        msg = T("core.standard_ops.standardize_done").format(
            rename=rename_count, clean=deleted_count)

        # 姿态驱动修正骨：并进父骨在静止与刚性跟随上是**恒等**的，丢掉的只有姿态驱动
        # 的修正运动，而那需要源游戏的驱动数据（终末地既没有 jcns，FBX 里也没有约束）。
        # 静悄悄发生的事要说出来，否则使用者会以为修正效果跟着过来了。
        mapped = set(analysis) | {m for m, _a in analysis.values() if m}
        confirmed, heavy, suspects = _survey_correctives(arm_obj, meshes, mapped)
        level = 'INFO'
        if confirmed:
            msg += " " + T("core.standard_ops.correctives_merged").format(
                n=len(confirmed))
        if heavy:
            msg += " " + T("core.standard_ops.correctives_heavy").format(
                n=len(heavy),
                names=", ".join("%s(%.2f)" % (n, w) for n, w in heavy[:3]))
        if suspects:
            # 名字匹配但结构不对：有子骨、父骨没映射、或权重足迹过大。不静默处置。
            level = 'WARNING'
            msg += " " + T("core.standard_ops.correctives_suspect").format(
                n=len(suspects),
                names=", ".join("%s(%.2f)" % (n, w) for n, w in suspects[:3]))
        self.report({level}, msg)
        return {'FINISHED'}

def _resample_twist_slots(arm_obj, mapper):
    """目标游戏装不下的扭转槽，按位置分给**同段留下来的那几根**，而不是整根并进段骨。

    这条路和跨游戏移植的关键差别：标准化只改名、不动骨，所以"目标侧"那几根扭转骨
    就是源骨架自己的骨头，两边坐标都在场景里 —— 不需要参考骨架，也不需要假设等分
    （实测 leon 的上臂扭转在 0.43/0.79，等分假设是错的）。

    刻意**不做跨序号重编号**：目标游戏的 jcns 按骨名给滚转系数，把 slot_02 改名成
    目标的 slot_01 等于静默换掉滚转量，而目标那几根真实的 t 我们并不知道。所以只在
    目标叫得出名字的槽位之间分配；一根都叫不出来时退回并进段骨，也就是今天的行为。

    返回 (分掉的根数, [钳位诊断], [整段无落点的段标签])。
    """
    bones = arm_obj.data.bones
    std_to_bone, positions = {}, {}
    for key in standard_keys(True):
        b = bones.get(key)
        if b is not None:
            std_to_bone[key] = key
            positions[key] = tuple(b.head_local)

    kept = {k for k in std_to_bone
            if is_aux_key(k) and (mapper.mapping_data.get(k) or {}).get("main")}
    splits, reports = twist_chain.plan_slot_resample(std_to_bone, positions, kept)
    if not splits and not reports:
        return 0, [], []

    done = weight_utils.distribute_and_remove(arm_obj, splits) if splits else 0
    clamped, no_target = [], []
    for label, rep in reports.items():
        if rep.get("no_target"):
            no_target.append(label)
            continue
        clamped += rep.get("clamped", [])
    return len(splits) if done or splits else 0, clamped, no_target


class MODDER_OT_ApplyStandardY(bpy.types.Operator):
    bl_idname = "modder.apply_standard_y"
    bl_label = "2. Convert to Game Name (Y)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.apply_standard_y_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_obj, False)
        if y_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        mapper = BoneMapManager()
        if not mapper.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_y_preset"))
            return {'CANCELLED'}

        # 重采样必须在改名之前：一改名就查不到标准键，也就分不清哪根是第几节。
        # 它自己会进出编辑模式并删掉被分掉的骨，所以这里仍是 OBJECT 模式。
        bpy.ops.object.mode_set(mode='OBJECT')
        n_split, clamped, no_target = _resample_twist_slots(arm_obj, mapper)

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        # 这里恒取全部键：骨架上叫 upperarm_twist_01_L 的骨头只可能是上一步标准化
        # 留下的，无论现在勾没勾"忽略辅助骨"，都得给它换回游戏名，否则会以标准名
        # 留在导出的骨架里。
        unmapped_aux = []
        for std_key in standard_keys(True):
            if std_key in edit_bones:
                target_data = mapper.mapping_data.get(std_key)
                if target_data and target_data.get("main"):
                    edit_bones[std_key].name = target_data["main"][0]
                elif is_aux_key(std_key):
                    unmapped_aux.append(std_key)

        bpy.ops.object.mode_set(mode='OBJECT')

        parts, level = [], 'INFO'
        if n_split:
            parts.append(T("core.standard_ops.twist_resampled").format(n=n_split))
        if clamped:
            # 钳位 = 目标链覆盖不到这个位置，滚转量真的丢了一截。必须报。
            level = 'WARNING'
            parts.append(T("core.standard_ops.twist_clamped").format(
                n=len(clamped),
                names=", ".join("%s(%+.2f)" % (c["bone"], c["roll_residual"])
                                for c in clamped[:3])))
        if no_target:
            level = 'WARNING'
            parts.append(T("core.standard_ops.twist_no_target").format(
                n=len(no_target), names=", ".join(sorted(no_target)[:4])))
        if unmapped_aux:
            # 目标游戏没有这个辅助骨槽位。骨头留着、名字还是标准名——不静默，
            # 因为导出前检查看到的是一根陌生名字的骨，追不回这里。
            level = 'WARNING'
            parts.append(T("core.standard_ops.aux_no_target").format(
                n=len(unmapped_aux), names=", ".join(unmapped_aux[:4])))
        if parts:
            self.report({level}, " ".join(parts))
        return {'FINISHED'}

def _plan_twist_splits(arm_obj, mapper_x, mapper_y):
    """一键转换用的扭转链分配表，键是**源游戏骨名**（这条路不改骨名，只动顶点组）。

    返回 (splits, reports, handled)；*handled* 是已经按位置分掉、因此不该再被
    "退回父段"规则整根并进段骨的槽位键。
    """
    bones = arm_obj.data.bones
    std_to_bone, positions = {}, {}
    for key in standard_keys(True):
        main, _aux = mapper_x.get_matches_for_standard(arm_obj, key)
        if main and main in bones:
            std_to_bone[key] = main
            positions[main] = tuple(bones[main].head_local)

    kept = {k for k in std_to_bone
            if is_aux_key(k) and (mapper_y.mapping_data.get(k) or {}).get("main")}
    splits, reports = twist_chain.plan_slot_resample(std_to_bone, positions, kept)
    bone_to_std = {v: k for k, v in std_to_bone.items()}
    handled = {bone_to_std[src] for src, _rows in splits if src in bone_to_std}
    return splits, reports, handled


class MODDER_OT_DirectConvert(bpy.types.Operator):
    bl_idname = "modder.direct_convert"
    bl_label = "One-Click Convert (X -> Y)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.direct_convert_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings

        # 1. 获取选中的所有网格对象
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected_meshes:
            self.report({'ERROR'}, T("core.standard_ops.select_at_least_one_mesh_paren"))
            return {'CANCELLED'}

        if settings.import_preset_enum == 'AUTO' and settings.target_preset_enum == 'AUTO':
            self.report({'WARNING'}, T("core.standard_ops.direct_convert_auto_conflict"))
            return {'CANCELLED'}

        arm_for_detect = next((m.find_armature() for m in selected_meshes if m.find_armature()), None)

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_for_detect, True)
        if x_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.source_preset_x_prefix") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_for_detect, False)
        if y_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.target_preset_y_prefix") + err)
            return {'CANCELLED'}

        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_y_preset"))
            return {'CANCELLED'}

        # 3. 预计算转换规则
        # 需要知道：标准键 -> (源主名, 源辅助列表, 目标主名)
        conversion_rules = []
        use_aux = not getattr(settings, "ignore_aux_bones", True)
        unmapped_aux = []

        # 扭转链先算：目标装不下的那几节按位置分给同段留下来的，而不是整根并进段骨。
        # 必须在 conversion_rules 之前算完，好把已处理的槽位从"退回父段"里摘掉。
        twist_splits, twist_reports, twist_handled = [], {}, set()
        if use_aux and arm_for_detect is not None:
            twist_splits, twist_reports, twist_handled = _plan_twist_splits(
                arm_for_detect, mapper_x, mapper_y)

        for std_key in standard_keys(use_aux):
            # A. 从 X 表获取源信息
            src_mains, src_auxs = mapper_x.entry_for(std_key, fold_aux=not use_aux)
            if not src_mains and not src_auxs: continue

            # B. 从 Y 表获取目标信息
            tgt_mains, _tgt_auxs = mapper_y.entry_for(std_key)
            
            # 目标游戏没有这个辅助骨槽位：不能把源扭转骨改成标准名扔在那里，
            # 退回"并进父段主骨"——也就是关掉槽位时的老行为，然后报出来。
            if use_aux and is_aux_key(std_key) and not tgt_mains:
                if std_key in twist_handled:
                    continue          # 已按位置分掉，不能再整根并进段骨
                parent = AUX_PARENT[std_key]
                p_mains, _pa = mapper_y.entry_for(parent)
                if p_mains:
                    conversion_rules.append(([], src_mains + src_auxs, p_mains[0]))
                    unmapped_aux.append(std_key)
                continue

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
            self.report({'WARNING'}, T("core.standard_ops.no_common_mapping"))
            return {'CANCELLED'}

        # 4. 开始处理网格 (Object Mode)
        bpy.ops.object.mode_set(mode='OBJECT')

        # 先归一化，再动任何权重：一键转换是实际接在 UI 上、真正会被按下的按钮
        # （骨骼标准化(X) modder.apply_standard_x 没有布线到面板，形同虚设）。
        # 顺带清掉 mmd_edge_scale/mmd_vertex_order —— 它们不对应任何骨骼，本不该
        # 参与形变，但会占外部按顶点组数量分配权重槽位的导出路径的名额。
        if getattr(settings, "normalize_weights_first", True) and arm_for_detect is not None:
            stats = _normalize_weights_for(arm_for_detect)
            if stats and (stats["fixed"] or stats["unweighted"] or stats["mmd_junk_removed"]):
                self.report({'INFO'}, _normalize_weights_message(stats))

        # 扭转链的权重分配走在改名之前：分配表的键是**源游戏骨名**，一改名就对不上。
        # remove_bones=False —— 一键转换只动顶点组，骨架留给标准化那两步。
        if twist_splits:
            weight_utils.distribute_and_remove(
                arm_for_detect, twist_splits, meshes=selected_meshes,
                remove_bones=False)

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

        msg = T("core.standard_ops.direct_convert_done").format(n=processed_count)
        clamped = [c for r in twist_reports.values() for c in r.get("clamped", ())]
        if twist_splits:
            msg += " " + T("core.standard_ops.twist_resampled").format(
                n=len(twist_splits))
        if clamped:
            unmapped_aux = unmapped_aux or []
            msg += " " + T("core.standard_ops.twist_clamped").format(
                n=len(clamped),
                names=", ".join("%s(%+.2f)" % (c["bone"], c["roll_residual"])
                                for c in clamped[:3]))
        if unmapped_aux:
            # 目标游戏没有这些辅助骨槽位，源骨已退回并进父段主骨。
            msg += " " + T("core.standard_ops.aux_folded_back").format(
                n=len(unmapped_aux), names=", ".join(unmapped_aux[:4]))
        self.report({'WARNING' if (unmapped_aux or clamped) else 'INFO'}, msg)
        return {'FINISHED'}

class MODDER_OT_UniversalSnap(bpy.types.Operator):
    bl_idname = "modder.universal_snap"
    bl_label = "0. Armature Snap"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.universal_snap_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        selected_objs = [o for o in context.selected_objects if o.type == 'ARMATURE']

        # 1. 检查选中项
        if len(selected_objs) != 2 or not context.active_object:
            self.report({'ERROR'}, T("core.standard_ops.snap_selection_error"))
            return {'CANCELLED'}

        target_arm = context.active_object  # 活动的是目标 (Y, 如 MHWI)
        source_arm = [o for o in selected_objs if o != target_arm][0]  # 另一个是源 (X, 如 VRC)

        x_preset, err = resolve_preset(settings.import_preset_enum, source_arm, True)
        if x_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.source_preset_x_prefix") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, target_arm, False)
        if y_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.target_preset_y_prefix") + err)
            return {'CANCELLED'}

        # 目标预设 (Y) 为 AUTO 时，下拉框里的值不会随解析结果同步（AUTO 不会变成具体文件名），
        # 所以这里直接按解析出的 y_preset 取其默认对齐模式，忽略下拉框当前值；
        # 只有用户明确选中了具体预设时，才尊重下拉框（可能是同步来的，也可能是手动改的）
        if settings.target_preset_enum == 'AUTO':
            align_mode = bone_utils.get_default_align_mode(y_preset)
        else:
            align_mode = getattr(settings, 'align_mode_override', 'POS_ONLY')

        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_y_preset"))
            return {'CANCELLED'}

        # 3. 预计算源骨骼的世界坐标 (在 Object 模式下进行)
        # 结构: { StandardName: (Head_World, Tail_World_or_None, Roll_or_None) }
        # FULL / POS_ROLL 模式还需要 tail 和 roll，这两项只存在于 EditBone 上，需临时切到源骨架的编辑模式读取
        # 对齐是几何操作：辅助骨有自己的坐标，两边都认得出来时对齐它们只会更准。
        align_aux = not getattr(settings, "ignore_aux_bones", True)
        need_full_data = align_mode in ('FULL', 'POS_ROLL')
        source_positions = {}
        source_mw = source_arm.matrix_world

        if need_full_data:
            context.view_layer.objects.active = source_arm
            bpy.ops.object.mode_set(mode='EDIT')
            for std_key in standard_keys(align_aux):
                src_name, _aux = mapper_x.get_matches_for_standard(source_arm, std_key)
                if src_name and src_name in source_arm.data.edit_bones:
                    eb = source_arm.data.edit_bones[src_name]
                    source_positions[std_key] = (source_mw @ eb.head, source_mw @ eb.tail, eb.roll)
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            for std_key in standard_keys(align_aux):
                src_name, _aux = mapper_x.get_matches_for_standard(source_arm, std_key)
                if src_name:
                    try:
                        b = source_arm.data.bones[src_name]
                        # 仅位置模式只需要头部坐标，尾部会通过刚性移动自动计算
                        source_positions[std_key] = (source_mw @ b.head_local, None, None)
                    except KeyError:
                        pass

        # 4. 进入编辑模式执行对齐
        context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones
        target_mw_inv = target_arm.matrix_world.inverted()

        aligned_count = 0

        # 按 STANDARD_BONE_NAMES 的顺序遍历 (通常是 Hips -> Spine -> Head)
        # 这样父级移动后，子级会先跟随移动，然后子级再根据自己的目标进行微调
        for std_key in standard_keys(align_aux):
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
            src_head_world, src_tail_world, src_roll = source_positions[std_key]
            target_head_local = target_mw_inv @ src_head_world

            # B. 计算移动向量
            old_head = t_bone.head.copy()
            offset = target_head_local - old_head

            # C. 移动当前骨骼
            if align_mode == 'FULL' and src_tail_world is not None:
                # 头、尾、扭转全部照抄来源，骨骼长度和方向都会跟随来源
                t_bone.head = target_head_local
                t_bone.tail = target_mw_inv @ src_tail_world
                t_bone.roll = src_roll
            elif align_mode == 'POS_ROLL' and src_roll is not None:
                # 头部对齐 + 复制扭转，长度方向保持目标骨架原有的
                orig_vec = t_bone.tail - t_bone.head
                t_bone.head = target_head_local
                t_bone.tail = target_head_local + orig_vec
                t_bone.roll = src_roll
            else:
                # 仅位置：保持长度和方向，尾部跟随头部整体平移
                t_bone.head = target_head_local
                t_bone.tail += offset

            # D. 刚性传递：按头部位移量平移所有未单独映射的子级
            bone_utils.propagate_movement(t_bone, offset)

            aligned_count += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, T("core.standard_ops.snap_done").format(n=aligned_count))
        return {'FINISHED'}

def _resolve_graft_forks(source_arm, physics_set, mesh_objects, masses=None):
    """对来源骨架的物理骨跑分叉判定，返回 (节点树, 判定结果)。

    权重量取来源网格的顶点组（调用方已经算过可以直接传 *masses*）；没有绑定网格时
    masses 为 None，stub 规则因此不会触发（没数据就不删骨）。手动标了 main_continue 的
    子骨按标记走。"""
    if masses is None and mesh_objects:
        masses = weight_utils.bone_weight_mass(mesh_objects, physics_set)
    mw = source_arm.matrix_world
    pose = source_arm.pose.bones
    nodes = fork_resolver.nodes_from_bones(
        source_arm.data.bones, physics_set,
        head_of=lambda n: tuple(mw @ pose[n].head),
        masses=masses,
        is_marker=lambda n: pose[n].get("chain_role") == "main_continue")
    return nodes, fork_resolver.resolve(nodes)


def _source_forward(arm, mapper):
    """来源模型的正前方（世界坐标、水平）：脚跟到脚尖的方向，两只脚取平均。
    认不出脚时按 Blender 的惯例 -Y。"""
    mw = arm.matrix_world
    acc = mathutils.Vector((0.0, 0.0, 0.0))
    for side in ("L", "R"):
        foot, _ = mapper.get_matches_for_standard(arm, f"foot_{side}")
        toe, _ = mapper.get_matches_for_standard(arm, f"toe_{side}")
        if foot and toe:
            v = mw @ arm.data.bones[toe].head_local - mw @ arm.data.bones[foot].head_local
            v.z = 0.0
            if v.length > 1e-4:
                acc += v.normalized()
    if acc.length < 1e-4:
        return (0.0, -1.0, 0.0)
    return tuple(acc.normalized())


class _GraftSimplifyPlan:
    """移植到 MHWI 前的精简规划：哪些骨不移植、权重怎么拆，以及按此估算的名额。只读。"""

    def __init__(self):
        self.helpers = set()        # 整棵子树都没权重的辅助骨：不移植
        self.centres = []           # physics_simplify.CentreChain
        self.centre_nodes = set()   # 中央链子树：权重拆给左右链后不移植
        self.decimated = {}         # 抽稀删掉的骨 -> (前一根保留骨, 后一根保留骨)
        self.physics = set()        # 规划完剩下要进分叉判定的物理骨
        self.masses = {}
        self.fork_nodes = None
        self.fork_res = None
        self.items = []             # mhwi_physics_budget.Item


def _plan_graft_simplify(source_arm, physics, mesh_objects, src_mapper,
                         dissolve_centre, decimate):
    plan = _GraftSimplifyPlan()
    bones = source_arm.data.bones
    mw = source_arm.matrix_world

    def children_of(n):
        return [c.name for c in bones[n].children]

    def rest_head(n):
        return tuple(mw @ bones[n].head_local)

    masses = (weight_utils.bone_weight_mass(mesh_objects, physics)
              if mesh_objects else None)
    weighted = {n for n, m in (masses or {}).items() if m > 1e-6}
    # 没有网格就不知道谁有权重：辅助骨、中央链都无从判断，一律不动
    if masses is not None:
        plan.helpers = physics_simplify.helper_bones(physics, children_of, weighted)
    phys = set(physics) - plan.helpers
    nodes, res = _resolve_graft_forks(source_arm, phys, mesh_objects, masses)

    if dissolve_centre and masses is not None:
        dropped = set(res.dropped)
        heads = [n for n, nd in nodes.items()
                 if n not in dropped and (nd.parent is None or nd.parent in dropped)]

        def anchor_of(h):
            p = bones[h].parent
            while p is not None and p.name in phys:
                p = p.parent
            return p.name if p is not None else None

        # 中央链的问题是它会垂到两腿之间。所以只认：圈心在身体中线上、且这条链最低点
        # 低于大腿根的。头上一圈刘海、领口的领结垂不到裆部，手腕一圈手镯不在中线上。
        # 不看锚点挂在哪：祀的裙子挂在 上半身 下面。
        def head_of(std):
            name, _ = src_mapper.get_matches_for_standard(source_arm, std)
            if name is None and std in bones:
                name = std
            return mathutils.Vector(rest_head(name)) if name else None

        thighs = [v for v in (head_of("thigh_L"), head_of("thigh_R")) if v is not None]
        pelvis = head_of("pelvis")
        midline = (sum(thighs, mathutils.Vector()) / len(thighs)) if thighs else pelvis
        crotch_z = midline.z if midline is not None else None

        def lowest(head):
            return min(min((mw @ bones[n].head_local).z, (mw @ bones[n].tail_local).z)
                       for n in physics_simplify.depth_index(head, children_of, phys))

        forward = _source_forward(source_arm, src_mapper)
        rings = physics_simplify.find_rings(heads, anchor_of, rest_head, forward)
        plan.centres = [
            c for c in physics_simplify.find_centre_chains(
                rings, midline=tuple(midline) if midline is not None else None,
                forward=forward)
            if crotch_z is None or lowest(c.head) < crotch_z]
        for c in plan.centres:
            plan.centre_nodes.update(physics_simplify.depth_index(c.head, children_of, phys))
        if plan.centre_nodes:
            phys -= plan.centre_nodes
            nodes, res = _resolve_graft_forks(source_arm, phys, mesh_objects, masses)

    if decimate:
        protected = {f.bone for f in res.forks} | set(res.continues)
        protected.update(c.nodes[0] for c in res.chains)
        for root in res.skipped:
            protected.update(fork_resolver.subtree(nodes, root))
        plan.decimated = physics_simplify.decimate(
            [c.nodes for c in res.chains], children_of, phys - set(res.dropped), protected)

    plan.physics, plan.masses = phys, masses or {}
    plan.fork_nodes, plan.fork_res = nodes, res

    # 名额估算：按移植后的样子数（被删的主干 / 抽掉的骨不在了，权重落到保留骨上）
    removed = set(res.dropped) | set(plan.decimated)
    final = phys - removed
    got_weight = set(weighted)
    for r, (prev, nxt) in plan.decimated.items():
        if r in weighted:
            got_weight.update((prev, nxt))
    for c in plan.centres:
        got_weight.update(t for pair in physics_simplify.centre_targets(
            c, children_of, phys | plan.centre_nodes).values() for t in pair)

    def eff_children(n):
        return physics_simplify.effective_children(n, children_of, final, plan.decimated)

    def is_root(n):
        p = bones[n].parent
        while p is not None and p.name in removed:
            p = p.parent
        return p is None or p.name not in final

    roots = [n for n in final if is_root(n)]
    items = mhwi_physics_budget.tree_items(
        roots, eff_children, got_weight,
        fork_ends={c.nodes[-1] for c in res.chains if c.ends_at_fork})
    # 和拆分一样按权重交叉并组再装：共用顶点的链拆不开，按单条链估会过于乐观
    # （莉奈娅：单链估全放得下，拆分时三块裙摆各超 51 根非末端，实际差 66 根）。
    owner = {}
    for r in roots:
        for n in physics_simplify.depth_index(r, children_of, phys | plan.centre_nodes):
            owner[n] = r
    for c in plan.centres:
        for n in physics_simplify.depth_index(c.head, children_of, phys | plan.centre_nodes):
            owner[n] = owner.get(c.left, c.left)
    if mesh_objects:
        mass, pair = weight_utils.co_weight(mesh_objects, owner)
        groups = mhwi_physics_budget.group_roots(roots, pair, mass)
        items = mhwi_physics_budget.merge_items(groups, {i.root: i for i in items})
    plan.items = items
    return plan


def mhwi_unlock_prefs(context=None):
    """装着 ``mhwi_physics_unlocked`` 的偏好对象，给 ``layout.prop`` 用。"""
    from .console_export import get_preferences
    return get_preferences(context)


def mhwi_physics_unlocked(context=None):
    """这个 mod 是否要求玩家装解锁插件（插件偏好，永久保存）。"""
    return bool(getattr(mhwi_unlock_prefs(context), "mhwi_physics_unlocked", False))


def _slot_text(packing, slot):
    """``body 120/169``；不装插件的小部位另注物理骨和末端骨的用量：
    ``arm 90/169 (物理 50/50，末端 40/86)``。"""
    nt, t = packing.used[slot]
    cap_nt, cap_t, cap_total = packing.capacity[slot]
    text = f"{slot} {nt + t}/{cap_total}"
    if cap_nt is not None:
        text += " " + T("core.standard_ops.graft_slot_physics").format(
            n=nt, cap=cap_nt, t=t, cap_t=cap_t)
    return text


def _slot_full(packing, slot):
    nt, t = packing.used[slot]
    cap_nt, cap_t, cap_total = packing.capacity[slot]
    return (nt + t >= cap_total or (cap_nt is not None and nt >= cap_nt)
            or (cap_t is not None and t >= cap_t))


def _budget_text(packing):
    """一行文字的名额估算，执行完报告用。"""
    text = T("core.standard_ops.graft_budget_line").format(
        slots="  ".join(_slot_text(packing, s) for s in mhwi_physics_budget.SLOTS))
    if packing.overflow:
        text += "  " + T("core.standard_ops.graft_budget_over").format(n=packing.overflow_bones)
    return text


def _draw_budget(layout, plan, base, unlocked):
    packing = mhwi_physics_budget.pack(plan.items, base, unlocked)
    layout.label(text=T("core.standard_ops.graft_budget_header").format(base=base))
    for slot in mhwi_physics_budget.SLOTS:
        full = _slot_full(packing, slot)
        layout.label(text=_slot_text(packing, slot), icon='ERROR' if full and packing.overflow
                     else 'CHECKMARK')
    if packing.overflow:
        layout.label(text=T("core.standard_ops.graft_budget_over").format(
            n=packing.overflow_bones), icon='ERROR')
    else:
        layout.label(text=T("core.standard_ops.graft_budget_fits"), icon='CHECKMARK')
    if plan.helpers:
        layout.label(text=T("core.standard_ops.graft_helpers_note").format(n=len(plan.helpers)))


#: invoke 算好的各种勾选组合下的估算，给弹窗 draw 用（draw 每帧都会调，不能重算权重）。
#: 键是 (来源骨架名, 目标骨架名)，值是 {(拆中央链, 抽稀): 规划}。
_GRAFT_PREVIEW = {}


class MODDER_OT_SmartGraftBones(bpy.types.Operator):
    bl_idname = "modder.smart_graft"
    bl_label = "3. Graft Physics Bones (+End Bone)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.smart_graft_desc")

    #: 只在移植目标是 MHWI 时起作用；不弹窗直接执行时用默认值，弹窗 / 调整上次操作面板里可改
    dissolve_centre: bpy.props.BoolProperty(
        name="Dissolve Front Centre Chain", default=True,
        description="Split the front centre skirt chain's weights onto its two neighbours, then drop it")
    decimate: bpy.props.BoolProperty(
        name="Decimate Chains", default=False,
        description="Keep the first and last bone of each chain and every other bone between")

    def _gather(self, context):
        """场景校验、加载预设、筛出物理骨。出错时已 report，返回 None。"""
        # --- 1. 场景校验 ---
        sel_objs = context.selected_objects
        target_arm = context.active_object # Out (目标)

        if not target_arm or target_arm.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.graft_no_target_arm"))
            return None

        source_arm = None # In (来源)
        for obj in sel_objs:
            if obj != target_arm and obj.type == 'ARMATURE':
                source_arm = obj
                break

        if not source_arm:
            self.report({'ERROR'}, T("core.standard_ops.graft_no_source_arm"))
            return None

        # --- 2. 加载预设 (仅用于排除非物理骨) ---
        from .bone_mapper import BoneMapManager
        settings = context.scene.mhw_suite_settings

        x_preset, err = resolve_preset(settings.import_preset_enum, source_arm, True)
        if x_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.source_preset_x_prefix") + err)
            return None

        y_preset, err = resolve_preset(settings.target_preset_enum, target_arm, False)
        if y_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.target_preset_y_prefix") + err)
            return None

        src_mapper = BoneMapManager()
        if not src_mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_source_in"))
            return None

        tgt_mapper = BoneMapManager()
        if not tgt_mapper.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_target_out"))
            return None

        # --- 3. 构建查找表 ---
        # 用 get_matches_for_standard 做模糊匹配，与对齐功能保持一致，
        # 避免命名习惯不同的基础骨（如 UpperLeg.L vs UpperLeg_L）被误判为物理骨
        src_to_std = {}

        for std_key in src_mapper.mapping_data.keys():
            main_actual, aux_actuals = src_mapper.get_matches_for_standard(source_arm, std_key)
            if main_actual:
                src_to_std[main_actual] = std_key
            elif std_key in source_arm.data.bones:
                # 与 _build_fuzzy_preset_bones 的回退一致：骨架已标准化，骨名就是标准键
                src_to_std[std_key] = std_key
            for aux_actual in aux_actuals:
                src_to_std[aux_actual] = std_key

        std_to_tgt_bone = {}
        for std_key, entry in tgt_mapper.mapping_data.items():
            mains = entry.get('main', [])
            if mains:
                std_to_tgt_bone[std_key] = mains[0]

        # --- 4. 筛选物理骨 ---
        # 只要不在预设里的，都算物理骨。"预设里"必须和拆分 / 重命名用同一个判定
        # （_build_fuzzy_preset_bones：含 exclude 与姿态修正骨），否则 MMD 的
        # 全ての親 / センター / 足IK 在这里被当成物理骨移植过去，到拆分时又不算物理骨。
        # src_to_std 仍只收 main / aux：被排除的骨在目标上没有对应，父级重建时越过它们。
        all_preset_bones_src = _build_fuzzy_preset_bones(src_mapper, source_arm)
        physics_bones_names = [b.name for b in source_arm.data.bones if b.name not in all_preset_bones_src]
        physics_bones_set = set(physics_bones_names) # 用于快速查找

        if not physics_bones_names:
            self.report({'WARNING'}, T("core.standard_ops.no_physics_bones_detected"))
            return None

        mesh_objects = [o for o in bpy.data.objects
                        if o.type == 'MESH'
                        and any(m.type == 'ARMATURE' and m.object == source_arm
                                for m in o.modifiers)]
        return dict(source_arm=source_arm, target_arm=target_arm,
                    src_mapper=src_mapper, tgt_mapper=tgt_mapper,
                    src_to_std=src_to_std, std_to_tgt_bone=std_to_tgt_bone,
                    all_preset_bones_src=all_preset_bones_src,
                    physics_bones_names=physics_bones_names,
                    mesh_objects=mesh_objects,
                    is_mhwi=tgt_mapper.preset_info.get("game_code") == "MHWI")

    @staticmethod
    def _preview_key(g):
        return (g["source_arm"].name, g["target_arm"].name)

    def invoke(self, context, _event):
        g = self._gather(context)
        if g is None:
            return {'CANCELLED'}
        if not g["is_mhwi"]:
            return self.execute(context)
        physics = set(g["physics_bones_names"])
        plans = {(c, d): _plan_graft_simplify(g["source_arm"], physics, g["mesh_objects"],
                                              g["src_mapper"], c, d)
                 for c in (False, True) for d in (False, True)}
        base = len(g["target_arm"].data.bones)
        _GRAFT_PREVIEW.clear()
        _GRAFT_PREVIEW[self._preview_key(g)] = (plans, base)
        has_centre = bool(plans[(True, False)].centres)
        unlocked = mhwi_physics_unlocked(context)
        over = mhwi_physics_budget.pack(
            plans[(has_centre, False)].items, base, unlocked).overflow_bones > 0
        self.dissolve_centre = True
        self.decimate = over
        if not has_centre and not over:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(
            self, width=440, title=T("ui.main_panel.btn_smart_graft"))

    def draw(self, context):
        layout = self.layout
        g_key = None
        sel = [o for o in context.selected_objects if o.type == 'ARMATURE']
        tgt = context.active_object
        src = next((o for o in sel if o != tgt), None)
        if src is not None and tgt is not None:
            g_key = (src.name, tgt.name)
        cached = _GRAFT_PREVIEW.get(g_key)
        layout.prop(mhwi_unlock_prefs(context), "mhwi_physics_unlocked",
                    text=T("core.standard_ops.graft_unlocked_plugin"))
        if cached is None:
            layout.prop(self, "dissolve_centre", text=T("core.standard_ops.graft_dissolve_centre"))
            layout.prop(self, "decimate", text=T("core.standard_ops.graft_decimate"))
            return
        plans, base = cached
        centres = plans[(True, False)].centres
        if centres:
            names = ", ".join(c.head for c in centres)
            layout.prop(self, "dissolve_centre",
                        text=T("core.standard_ops.graft_dissolve_centre_named").format(names=names))
        layout.prop(self, "decimate", text=T("core.standard_ops.graft_decimate"))
        plan = plans[(bool(centres) and self.dissolve_centre, self.decimate)]
        unlocked = mhwi_physics_unlocked(context)
        _draw_budget(layout.box(), plan, base, unlocked)

    def execute(self, context):
        g = self._gather(context)
        if g is None:
            return {'CANCELLED'}
        source_arm, target_arm = g["source_arm"], g["target_arm"]
        tgt_mapper = g["tgt_mapper"]
        src_to_std, std_to_tgt_bone = g["src_to_std"], g["std_to_tgt_bone"]
        all_preset_bones_src = g["all_preset_bones_src"]
        physics_bones_names = g["physics_bones_names"]
        physics_bones_set = set(physics_bones_names)
        mesh_objects = g["mesh_objects"]

        # --- 4.5 来源预标记：若来源骨架物理骨尚未标记，自动补一次拓扑检测 ---
        already_marked = any(
            source_arm.pose.bones.get(b.name) and (
                source_arm.pose.bones[b.name].color.palette == 'CUSTOM' or
                source_arm.pose.bones[b.name].get("chain_role") is not None
            )
            for b in source_arm.data.bones
            if b.name not in all_preset_bones_src
        )
        if not already_marked:
            bpy.context.view_layer.objects.active = source_arm
            bpy.ops.object.mode_set(mode='POSE')
            _detect_chain_roles(source_arm, all_preset_bones_src)
            bpy.ops.object.mode_set(mode='OBJECT')

        # --- 4.55 被 exclude 排除的骨不移植，它们的权重并进最近的映射祖先 ---
        # 控制骨大多零权重，但不全是：首リボン操作 这种把手同时蒙着缎带结。不并的话
        # 目标上没有这根骨，那片顶点就失去了驱动。并进的祖先和下面父级重建时越过它
        # 去找的是同一根，所以并完以后结点跟着它原来跟随的身体部位走，行为不变。
        excluded_merge = {}
        for name in g["src_mapper"].exclude_matches(b.name for b in source_arm.data.bones):
            if name in src_to_std:
                continue
            anc = source_arm.data.bones[name].parent
            while anc is not None and anc.name not in src_to_std:
                anc = anc.parent
            if anc is not None:
                excluded_merge[name] = anc.name
        weighted = set()
        for obj in mesh_objects:
            idx = {obj.vertex_groups[n].index: n for n in excluded_merge
                   if n in obj.vertex_groups}
            if idx:
                weighted.update(idx[gr.group] for v in obj.data.vertices
                                for gr in v.groups if gr.weight > 0 and gr.group in idx)
        merged_weighted = [n for n in excluded_merge if n in weighted]
        if merged_weighted:
            weight_utils.merge_vertex_groups(
                mesh_objects, {n: excluded_merge[n] for n in merged_weighted})

        # --- 4.6 快照目标骨架现有骨骼，写入移植保护集合 ---
        existing_protected = _load_protected_bones(target_arm)
        current_tgt_bones = {b.name for b in target_arm.data.bones}
        target_arm["transplant_protected_bones"] = json.dumps(
            list(existing_protected | current_tgt_bones)
        )

        # --- 4.7 精简 + 分叉判定（仅目标为 MHWI）---
        # MHWI 的 CTC 链不能分叉，且几乎没人手动标主链延续，所以这里按拓扑自动判定：
        # 主干很轻就删、一支明显是延续就当延续、其余各自成链，第二层分支不生成链。
        # 在那之前先精简（见 physics_simplify）：辅助骨不移植，正前方中央链的权重拆给
        # 左右链，按勾选抽稀。名额估算和弹窗用的是同一份规划。
        fork_nodes = fork_res = plan = None
        dropped, auto_continue, skipped_set, promoted_heads = {}, set(), set(), set()
        collapsed = {}      # 抽稀删掉的骨 -> 它的父骨（父级重建时越过它）
        if g["is_mhwi"]:
            plan = _plan_graft_simplify(source_arm, physics_bones_set, mesh_objects,
                                        g["src_mapper"], self.dissolve_centre, self.decimate)
            bones = source_arm.data.bones
            mw = source_arm.matrix_world
            if plan.centres:
                full = plan.physics | plan.centre_nodes
                splits = {}
                for c in plan.centres:
                    centroid = mathutils.Vector(c.ring.centroid)
                    forward = _source_forward(source_arm, g["src_mapper"])
                    for node, (left, right) in physics_simplify.centre_targets(
                            c, lambda n: [ch.name for ch in bones[n].children], full).items():
                        def share(co, c=c, left=left, right=right, centroid=centroid,
                                  forward=forward):
                            f = physics_simplify.side_fraction(
                                tuple(co - centroid), c.ring, c, forward, (0.0, 0.0, 1.0))
                            return [(left, f), (right, 1.0 - f)]
                        splits[node] = share
                weight_utils.split_vertex_groups(mesh_objects, splits)
            if plan.decimated:
                splits = {}
                for r, (prev, nxt) in plan.decimated.items():
                    a, b = tuple(mw @ bones[prev].head_local), tuple(mw @ bones[nxt].head_local)
                    def share(co, a=a, b=b, prev=prev, nxt=nxt):
                        t = physics_simplify.segment_fraction(tuple(co), a, b)
                        return [(prev, 1.0 - t), (nxt, t)]
                    splits[r] = share
                weight_utils.split_vertex_groups(mesh_objects, splits)
                collapsed = {r: bones[r].parent.name for r in plan.decimated}
            gone = plan.helpers | plan.centre_nodes | set(collapsed)
            physics_bones_names = [n for n in physics_bones_names if n not in gone]
            physics_bones_set -= gone

            fork_nodes, fork_res = plan.fork_nodes, plan.fork_res
            auto_continue = set(fork_res.continues)
            for root in fork_res.skipped:
                skipped_set.update(fork_resolver.subtree(fork_nodes, root))
            for name in fork_res.dropped:
                # 权重并进最近的、不会被删的祖先；链首的 can_drop 保证它有非物理父骨
                anc = source_arm.data.bones[name].parent
                while anc is not None and anc.name in fork_res.dropped:
                    anc = anc.parent
                if anc is not None:
                    dropped[name] = anc.name
            if dropped:
                promoted_heads = {c for n in dropped for c in fork_nodes[n].children
                                  if c not in dropped}
                weight_utils.merge_vertex_groups(mesh_objects, dropped)
                physics_bones_names = [n for n in physics_bones_names if n not in dropped]
                physics_bones_set -= set(dropped)

        # --- 5. 核心移植逻辑 ---
        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones

        tgt_mat_inv = target_arm.matrix_world.inverted()
        tgt_root_name = next((eb.name for eb in edit_bones
                              if eb.parent is None and eb.name in current_tgt_bones), None)

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
        end_bone_names = []  # 记录本次生成的 End 骨骼名，供 Phase 7 着色使用

        for p_name in physics_bones_names:
            src_bone = source_arm.data.bones.get(p_name)

            # 需要 _End 的情况：
            # A. 分叉骨：有 ≥2 个物理子骨，但没有子骨标记为 main_continue
            # B. 叶骨：在物理骨集合中没有子级 且 有顶点权重（无权重视为已到尾骨）
            #    线性链（恰好一个物理子骨）不需要 _End
            # 抽稀删掉的骨不在了：它的子骨算作上一级的子骨
            physics_children = physics_simplify.effective_children(
                p_name, lambda n: [c.name for c in source_arm.data.bones[n].children],
                physics_bones_set, collapsed)
            is_leaf = len(physics_children) == 0
            is_fork = len(physics_children) >= 2
            has_main_continue_child = any(
                c in auto_continue or (
                    source_arm.pose.bones.get(c) and
                    source_arm.pose.bones[c].get("chain_role") == "main_continue")
                for c in physics_children
            )
            if p_name in skipped_set:
                needs_end = False   # 不生成链的子树，补 _End 没有意义
            elif is_leaf:
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
                end_bone_names.append(end_bone_name)

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
            # 被判定删掉的主干、抽稀删掉的骨都不在目标里：子骨改挂到最近的、仍然存在的祖先上
            while src_p_name in dropped or src_p_name in collapsed:
                src_p_name = source_arm.data.bones[src_p_name].parent.name
            target_parent_name = None

            # A. 父级是物理骨
            if src_p_name in new_bones_map:
                target_parent_name = new_bones_map[src_p_name]
            # B. 父级是映射骨 (Main/Aux)，或是被预设排除的非物理骨（exclude / 姿态修正骨）：
            #    沿父链向上找第一根在目标骨架上有对应的映射骨。目标骨架没有该标准骨
            #    （如 spine_03 在 MHWI/MHWS 中不存在）时也是同样往上走。
            else:
                walk = source_arm.data.bones.get(src_p_name)
                while walk:
                    std_key = src_to_std.get(walk.name)
                    if std_key in std_to_tgt_bone:
                        target_parent_name = std_to_tgt_bone[std_key]
                        break
                    walk = walk.parent
                else:
                    # 一路到顶都没有映射骨：挂在模型根上（MMD 的 全ての親 下直接挂翅膀），
                    # 目标上对应的就是骨架根
                    target_parent_name = tgt_root_name

            if target_parent_name and target_parent_name in edit_bones:
                eb.parent = edit_bones[target_parent_name]
                eb.use_connect = False 

        # --- 7. 从源骨骼复制 chain_role 并着色 ---
        bpy.ops.object.mode_set(mode='POSE')
        for src_name, tgt_name in new_bones_map.items():
            src_pb = source_arm.pose.bones.get(src_name)
            tgt_pb = target_arm.pose.bones.get(tgt_name)
            if src_pb and tgt_pb:
                role = src_pb.get("chain_role")
                if src_name in skipped_set:
                    role = "no_chain"
                elif src_name in auto_continue:
                    role = "main_continue"
                elif src_name in promoted_heads:
                    role = "head"   # 父骨（被删的主干）没了，它现在是主链首
                if role:
                    tgt_pb["chain_role"] = role
                _apply_bone_color(tgt_pb, tgt_pb.get("chain_role", "body"))
        for end_name in end_bone_names:
            end_pb = target_arm.pose.bones.get(end_name)
            if end_pb:
                _apply_bone_color(end_pb, "body")

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, T("core.standard_ops.graft_done").format(n=created_count))
        if merged_weighted:
            names = ", ".join(merged_weighted[:5]) + ("…" if len(merged_weighted) > 5 else "")
            self.report({'INFO'}, T("core.standard_ops.graft_excluded_merged").format(
                n=len(merged_weighted), names=names))
        if fork_res is not None:
            stats = fork_resolver.summary(fork_res)
            if any(stats.values()):
                self.report({'INFO'}, T("core.standard_ops.graft_fork_summary").format(**stats))
            if fork_res.skipped:
                names = ", ".join(fork_res.skipped[:5]) + ("…" if len(fork_res.skipped) > 5 else "")
                self.report({'WARNING'}, T("core.standard_ops.graft_fork_skipped").format(
                    n=len(fork_res.skipped), names=names))
        if plan is not None:
            if plan.helpers or plan.centres or plan.decimated:
                self.report({'INFO'}, T("core.standard_ops.graft_simplify_summary").format(
                    helpers=len(plan.helpers), centre=len(plan.centres),
                    decimated=len(plan.decimated)))
            unlocked = mhwi_physics_unlocked(context)
            packing = mhwi_physics_budget.pack(plan.items, len(current_tgt_bones), unlocked)
            level = {'WARNING'} if packing.overflow else {'INFO'}
            self.report(level, _budget_text(packing))
        return {'FINISHED'}



class MODDER_OT_MergePhysicsWeights(bpy.types.Operator):
    bl_idname = "modder.merge_physics_weights"
    bl_label = "Downgrade Physics Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.merge_physics_weights_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings

        # 获取选中的网格
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected_meshes:
            self.report({'ERROR'}, T("core.standard_ops.select_at_least_one_mesh"))
            return {'CANCELLED'}

        # 需要一个骨架来分析骨骼层级
        arm_obj = None
        for mesh_obj in selected_meshes:
            arm = mesh_obj.find_armature()
            if arm:
                arm_obj = arm
                break

        if not arm_obj:
            self.report({'ERROR'}, T("core.standard_ops.mesh_no_armature"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        # 加载 X 预设，判断哪些是基础骨骼
        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
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
            self.report({'INFO'}, T("core.standard_ops.no_physics_vgroups"))
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
        
        self.report({'INFO'}, T("core.standard_ops.merge_physics_done").format(
            meshes=len(selected_meshes), groups=total_merged))
        return {'FINISHED'}


class MODDER_OT_RenameBonesToTarget(bpy.types.Operator):
    bl_idname = "modder.rename_bones_to_target"
    bl_label = "Rename Base Bones (X->Y)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.rename_bones_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        if settings.import_preset_enum == 'AUTO' and settings.target_preset_enum == 'AUTO':
            self.report({'WARNING'}, T("core.standard_ops.rename_bones_auto_conflict"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.source_preset_x_prefix") + err)
            return {'CANCELLED'}

        y_preset, err = resolve_preset(settings.target_preset_enum, arm_obj, False)
        if y_preset is None:
            self.report({'WARNING'}, T("core.standard_ops.target_preset_y_prefix") + err)
            return {'CANCELLED'}

        # 加载 X 和 Y 预设
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
            return {'CANCELLED'}

        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(y_preset, is_import_x=False):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_y_preset"))
            return {'CANCELLED'}

        # 通过标准键桥接: X 实际骨骼名 -> 标准键 -> Y 目标骨骼名
        rename_map = {}  # {当前骨骼名: 目标骨骼名}
        
        for std_key in standard_keys(True):
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
            self.report({'INFO'}, T("core.standard_ops.no_bones_need_rename"))
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
        self.report({'INFO'}, T("core.standard_ops.renamed_to_target_done").format(n=renamed_count))
        return {'FINISHED'}


class MODDER_OT_RemoveNonBaseBones(bpy.types.Operator):
    bl_idname = "modder.remove_non_base_bones"
    bl_label = "Remove Non-Base Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.remove_non_base_desc")

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
        if x_preset is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}

        mapper = BoneMapManager()
        if not mapper.load_preset(x_preset, is_import_x=True):
            self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
            return {'CANCELLED'}
        
        # 用模糊匹配构建基础骨骼集合，避免命名习惯不同的基础骨被误删
        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        # 找出所有非基础骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        to_remove = [b.name for b in edit_bones if b.name not in preset_bones]
        
        if not to_remove:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, T("core.standard_ops.no_bones_to_remove"))
            return {'FINISHED'}

        # 删除
        for name in to_remove:
            if name in edit_bones:
                edit_bones.remove(edit_bones[name])

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, T("core.standard_ops.removed_non_base_bones").format(n=len(to_remove)))
        return {'FINISHED'}


_bone_view_mode_items_cache = []

def get_bone_view_mode_items(self, context):
    global _bone_view_mode_items_cache
    _bone_view_mode_items_cache = [
        ('ALL',     T("core.standard_ops.mode_all"),     T("core.standard_ops.mode_all_desc")),
        ('BASE',    T("core.standard_ops.mode_base"),    T("core.standard_ops.mode_base_desc")),
        ('PHYSICS', T("core.standard_ops.mode_physics"), T("core.standard_ops.mode_physics_desc")),
    ]
    return _bone_view_mode_items_cache


class MODDER_OT_SetBoneVisibility(bpy.types.Operator):
    bl_idname = "modder.set_bone_visibility"
    bl_label = "Bone Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.set_bone_visibility_desc")

    mode: bpy.props.EnumProperty(
        items=get_bone_view_mode_items,
    )

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        preset_bones = set()
        if self.mode != 'ALL':
            existing = {b.name for b in arm_obj.data.bones}
            x_preset, err = resolve_preset(settings.import_preset_enum, arm_obj, True)
            if x_preset is not None:
                mapper = BoneMapManager()
                if not mapper.load_preset(x_preset, is_import_x=True):
                    self.report({'ERROR'}, T("core.standard_ops.preset_load_failed"))
                    return {'CANCELLED'}
                preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
            # 兜底：无论预设是否加载成功，标准名骨骼一定是基础骨（处理已标准化骨架 + AUTO 失败）
            preset_bones.update(n for n in standard_keys(True) if n in existing)
            if not preset_bones:
                self.report({'WARNING'}, err or T("core.standard_ops.cannot_recognize_base_bones"))
                return {'CANCELLED'}

        protected_bones = _load_protected_bones(arm_obj) if self.mode == 'PHYSICS' else set()
        bpy.ops.object.mode_set(mode='POSE')
        for bone in arm_obj.data.bones:
            if self.mode == 'ALL':
                bone.hide = False
            elif self.mode == 'BASE':
                bone.hide = bone.name not in preset_bones
            else:  # PHYSICS
                bone.hide = bone.name in preset_bones or bone.name in protected_bones

        settings.bone_view_mode = self.mode
        labels = {
            'ALL': T("core.standard_ops.mode_all"),
            'BASE': T("core.standard_ops.mode_base"),
            'PHYSICS': T("core.standard_ops.mode_physics"),
        }
        self.report({'INFO'}, T("core.standard_ops.bone_display_status").format(mode=labels[self.mode]))
        return {'FINISHED'}


def _detect_chain_roles(arm_obj, preset_bones, protected_bones=None):
    """根据骨骼拓扑自动写入 chain_role。
    - 主链首（父骨不是物理骨）→ 'head'
    - 分叉子骨（父骨有 ≥2 个物理子骨）→ 'branch_head'（已手动设为 main_continue 的保留）
    - 拓扑已变、不再是链首 → 清除 head/branch_head
    - main_continue 及普通体骨不受影响。
    protected_bones: 移植保护集合，这些骨骼被视为非物理骨，不参与拓扑检测也不写入角色。
    需在 POSE 模式下调用。"""
    physics_bones = {
        b.name for b in arm_obj.data.bones
        if b.name not in preset_bones
        and (not protected_bones or b.name not in protected_bones)
    }
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
            if current_role not in _STICKY_ROLES:
                pb["chain_role"] = "branch_head"
        elif current_role in ("head", "branch_head"):
            del pb["chain_role"]


def _refresh_chain_roles_local(arm_obj, preset_bones, merged_pairs):
    """合并骨骼后的局部 chain_role 刷新。
    仅重新评估每个合并目标父级的所有直接物理子级，不触碰其他骨骼。
    merged_pairs: list of (parent_name, deleted_bone_name)，需在骨骼已从骨架移除后调用。"""
    physics_bones = {b.name for b in arm_obj.data.bones if b.name not in preset_bones}
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    processed_parents = set()
    for parent_name, _ in merged_pairs:
        if parent_name in processed_parents:
            continue
        processed_parents.add(parent_name)
        p_bone = arm_obj.data.bones.get(parent_name)
        if not p_bone:
            continue
        phys_children = [c for c in p_bone.children if c.name in physics_bones]
        parent_is_physics = parent_name in physics_bones
        is_fork = len(phys_children) >= 2
        for child_bone in phys_children:
            pb = arm_obj.pose.bones.get(child_bone.name)
            if not pb:
                continue
            is_main_head = not parent_is_physics
            is_branch_head = parent_is_physics and is_fork
            current_role = pb.get("chain_role")
            if is_main_head:
                pb["chain_role"] = "head"
            elif is_branch_head:
                if current_role not in _STICKY_ROLES:
                    pb["chain_role"] = "branch_head"
            elif current_role in ("head", "branch_head"):
                del pb["chain_role"]
            _apply_bone_color(pb, pb.get("chain_role", "body"))


def _run_bone_color_refresh(context, arm_obj):
    """运行骨骼颜色刷新核心逻辑（供其他操作符复用，不含 report）。
    成功返回 (True, preset_name)，失败返回 (False, error_message)。"""
    settings = context.scene.mhw_suite_settings
    mapper = BoneMapManager()
    detected = auto_detect_preset(arm_obj, is_import_x=True)
    if detected:
        if not mapper.load_preset(detected, is_import_x=True):
            return False, T("core.standard_ops.cannot_load_auto_detected")
    else:
        fallback = settings.import_preset_enum
        if fallback == 'AUTO':
            return False, T("core.standard_ops.auto_detect_failed_x")
        if not mapper.load_preset(fallback, is_import_x=True):
            return False, T("core.standard_ops.cannot_load_x_preset")
    preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
    protected_bones = _load_protected_bones(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    _detect_chain_roles(arm_obj, preset_bones, protected_bones)
    for b in arm_obj.data.bones:
        if b.name in preset_bones:
            pb = arm_obj.pose.bones.get(b.name)
            if pb:
                if "chain_role" in pb:
                    del pb["chain_role"]
                pb.color.palette = 'DEFAULT'
    _apply_physics_bone_colors(arm_obj, preset_bones, protected_bones)
    return True, mapper.preset_info.get('name', detected or fallback or "")


class MODDER_OT_RefreshPhysicsBoneColors(bpy.types.Operator):
    bl_idname = "modder.refresh_physics_bone_colors"
    bl_label = "Refresh Bone Colors"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.refresh_colors_desc")

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
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
                self.report({'ERROR'}, T("core.standard_ops.cannot_load_auto_detected"))
                return {'CANCELLED'}
        else:
            fallback = settings.import_preset_enum
            if fallback == 'AUTO':
                self.report({'WARNING'}, T("core.standard_ops.auto_detect_failed_x"))
                return {'CANCELLED'}
            if not mapper.load_preset(fallback, is_import_x=True):
                self.report({'ERROR'}, T("core.standard_ops.cannot_load_x_preset"))
                return {'CANCELLED'}
            fallback_name = mapper.preset_info.get('name', fallback)
            self.report({'WARNING'}, T("core.standard_ops.auto_detect_fallback").format(name=fallback_name))

        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)

        # 全量刷新：未选中任何骨骼，或选中数等于骨架全部骨骼数（视为全选）
        is_full_refresh = not partial or len(selected) == len(arm_obj.data.bones)
        protected_bones = _load_protected_bones(arm_obj) if is_full_refresh else set()

        # 始终对全骨架做拓扑分析，保护集合参与检测（保护骨骼不会被赋予物理角色）
        _detect_chain_roles(arm_obj, preset_bones, protected_bones)

        if partial and not is_full_refresh:
            # 真正的选中刷新：不过滤保护集合，用户主动选中即生效
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
            # 全量刷新（含"全选后刷新"）：保护集合生效
            for b in arm_obj.data.bones:
                if b.name in preset_bones:
                    pb = arm_obj.pose.bones.get(b.name)
                    if pb:
                        if "chain_role" in pb:
                            del pb["chain_role"]
                        pb.color.palette = 'DEFAULT'
            _apply_physics_bone_colors(arm_obj, preset_bones, protected_bones)

        preset_label = ""
        if detected:
            preset_label = T("core.standard_ops.auto_detected_suffix").format(
                name=mapper.preset_info.get('name', detected))

        if partial:
            self.report({'INFO'}, T("core.standard_ops.refreshed_n_bones").format(n=len(selected)) + preset_label)
        else:
            self.report({'INFO'}, T("core.standard_ops.colors_refreshed") + preset_label)
        return {'FINISHED'}


class MODDER_OT_MarkAsMainContinue(bpy.types.Operator):
    bl_idname = "modder.mark_as_main_continue"
    bl_label = "Mark as Main Continue"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.mark_main_continue_desc")

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        selected = context.selected_pose_bones
        if not selected:
            self.report({'WARNING'}, T("core.standard_ops.select_bones_in_pose_mode"))
            return {'CANCELLED'}
        for pb in selected:
            pb["chain_role"] = "main_continue"
            pb.color.palette = 'CUSTOM'
            pb.color.custom.normal = (1.0, 0.70, 0.10)
            pb.color.custom.select = (1.0, 0.85, 0.40)
            pb.color.custom.active = (1.0, 0.95, 0.70)
        self.report({'INFO'}, T("core.standard_ops.marked_main_continue").format(n=len(selected)))
        return {'FINISHED'}


class MODDER_OT_ClearChainRole(bpy.types.Operator):
    bl_idname = "modder.clear_chain_role"
    bl_label = "Clear Chain Role Mark"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.clear_chain_role_desc")

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        selected = context.selected_pose_bones
        if not selected:
            self.report({'WARNING'}, T("core.standard_ops.select_bones_in_pose_mode"))
            return {'CANCELLED'}
        for pb in selected:
            if "chain_role" in pb:
                del pb["chain_role"]
            # The marking operators paint the bone as well as tagging it
            # (palette = 'CUSTOM' plus three custom colours), so clearing only the
            # property left the bone still coloured — it looked marked when it was
            # not, which is worse than either state on its own.
            if pb.color.palette != 'DEFAULT':
                pb.color.palette = 'DEFAULT'
        self.report({'INFO'}, T("core.standard_ops.cleared_chain_role").format(n=len(selected)))
        return {'FINISHED'}


class MODDER_OT_MergeIntoParent(bpy.types.Operator):
    bl_idname = "modder.merge_into_parent"
    bl_label = "Merge into Parent"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.standard_ops.merge_into_parent_desc")

    @staticmethod
    def _armature_of_mesh(obj):
        """网格挂着的骨架：先看父级，再看姿态修改器绑的骨架；都没有返回 None。"""
        if obj.parent is not None and obj.parent.type == 'ARMATURE':
            return obj.parent
        for m in obj.modifiers:
            if m.type == 'ARMATURE' and m.object is not None and m.object.type == 'ARMATURE':
                return m.object
        return None

    def execute(self, context):
        obj = context.active_object
        if obj is not None and obj.type == 'MESH':
            return self._from_vertex_group(context, obj)
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        if context.mode == 'POSE':
            selected_names = [pb.name for pb in context.selected_pose_bones]
        elif context.mode == 'EDIT_ARMATURE':
            selected_names = [b.name for b in context.selected_editable_bones]
        else:
            self.report({'ERROR'}, T("core.standard_ops.pose_or_edit_mode_required"))
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        bones_data = obj.data.bones
        pairs = []
        for name in selected_names:
            bone = bones_data.get(name)
            if bone and bone.parent:
                pairs.append((bone.parent.name, name))

        if not pairs:
            self.report({'WARNING'}, T("core.standard_ops.no_valid_parent_bone"))
            return {'CANCELLED'}
        self._merge(context, obj, pairs)
        return {'FINISHED'}

    def _from_vertex_group(self, context, mesh_obj):
        """选中的是网格：取它的活动顶点组，找到同名骨骼，连骨带权重一起并进父骨。
        Blender 里一个网格同时只有一个活动顶点组，所以一次合并一根。"""
        vg = mesh_obj.vertex_groups.active
        if vg is None:
            self.report({'ERROR'}, T("core.standard_ops.merge_no_active_vgroup"))
            return {'CANCELLED'}
        arm_obj = self._armature_of_mesh(mesh_obj)
        if arm_obj is None:
            self.report({'ERROR'}, T("core.standard_ops.merge_mesh_needs_armature"))
            return {'CANCELLED'}
        if not arm_obj.visible_get():
            # 隐藏的骨架进不了编辑模式（mode_set 的 poll 会失败）
            self.report({'ERROR'}, T("core.standard_ops.merge_armature_hidden").format(
                armature=arm_obj.name))
            return {'CANCELLED'}
        bone = arm_obj.data.bones.get(vg.name)
        if bone is None:
            self.report({'ERROR'}, T("core.standard_ops.merge_vgroup_no_bone").format(
                group=vg.name, armature=arm_obj.name))
            return {'CANCELLED'}
        if bone.parent is None:
            self.report({'WARNING'}, T("core.standard_ops.no_valid_parent_bone"))
            return {'CANCELLED'}

        mode = context.mode
        restore = {'PAINT_WEIGHT': 'WEIGHT_PAINT', 'EDIT_MESH': 'EDIT'}.get(mode, 'OBJECT')
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self._merge(context, arm_obj, [(bone.parent.name, bone.name)])
        # 合并过程中活动物体被切到了骨架上；回到用户原来的网格和模式，好接着点下一个组
        context.view_layer.objects.active = mesh_obj
        if restore != 'OBJECT':
            bpy.ops.object.mode_set(mode=restore)
        return {'FINISHED'}

    def _merge(self, context, arm_obj, pairs):
        # 下面要进骨架的编辑模式：从网格进来时活动物体还是网格
        context.view_layer.objects.active = arm_obj
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
            _refresh_chain_roles_local(arm_obj, preset_bones, pairs)
        bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, T("core.standard_ops.merged_into_parent").format(n=len(pairs)))


classes = [
    MODDER_OT_NormalizeDeformWeights,
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