import bpy
import re
from bpy.app.translations import pgettext as _
from ...core import bone_utils
from ...core.bone_mapper import BoneMapManager
from ...core.standard_ops import _build_fuzzy_preset_bones


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


# ==========================================
# 2. 一键创建 Chain
# ==========================================

# 供 EnumProperty 回调使用的全局缓存
_ctc_col_items = []


def _get_ctc_col_items(self, _context):
    return _ctc_col_items


def _is_valid_ctc_collection(col):
    """检测 MHW Model Editor 的有效 CTC Collection（含 CTC_HEADER 空物体）"""
    return any(
        obj.get("~TYPE") == "MHW_CTC_HEADER" or obj.get("TYPE") == "MHW_CTC_HEADER"
        for obj in col.all_objects
    )


def _get_existing_chain_heads(col):
    """扫描集合中已存在的 CTC chain，返回已绑定链头骨骼名的集合（用于幂等性检查）。
    每条 CTC chain 曲线的第一个 Hook modifier 对应链头骨骼。"""
    heads = set()
    for obj in col.all_objects:
        if obj.get("~TYPE") != "MHW_CTC_CHAIN":
            continue
        # CTC chain 名称格式: "CTC_CHAIN_xx - HeadBone > TailBone"
        # 从 COPY_LOCATION 约束的 subtarget 无法直接得到链头，改从名称解析
        m = re.search(r' - (.+?) >', obj.name)
        if m:
            heads.add(m.group(1))
    return heads


def _has_branch(head_pb, physics_bones, armature):
    """检测以 head_pb 为根的物理链是否存在分叉（任意骨骼有 >1 个物理子骨）。
    _End 骨骼不计入物理子骨。"""
    def walk(pb):
        children = [
            c for c in pb.bone.children
            if c.name in physics_bones and not c.name.endswith("_End")
        ]
        if len(children) > 1:
            return True
        for child_bone in children:
            child_pb = armature.pose.bones.get(child_bone.name)
            if child_pb and walk(child_pb):
                return True
        return False
    return walk(head_pb)


class MHWI_OT_AutoCreateChains(bpy.types.Operator):
    """在姿态模式下，根据物理骨骼的 chain_role 属性自动为每条线性链创建 CTC Chain。
存在分叉的链会被跳过并报告，需用户手动处理分叉后再次运行。
需要 MHW Model Editor 插件。"""
    bl_idname = "mhwi.auto_create_chains"
    bl_label = "一键创建 Chain"
    bl_options = {'REGISTER', 'UNDO'}

    ctc_collection: bpy.props.EnumProperty(
        name="CTC Collection",
        description="选择要写入的 CTC Collection",
        items=_get_ctc_col_items,
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'POSE'
            and context.active_object is not None
            and context.active_object.type == 'ARMATURE'
            and hasattr(bpy.ops, 'mhw_ctc')
            and hasattr(bpy.ops.mhw_ctc, 'create_chain_from_bone')
        )

    def invoke(self, context, _event):
        global _ctc_col_items
        _ctc_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_ctc_collection(col)
        ]
        if not _ctc_col_items:
            self.report({'ERROR'}, _("未找到有效的 CTC Collection（需含 CTC_HEADER 空物体）"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, _context):
        self.layout.prop(self, "ctc_collection")

    def execute(self, context):
        col = bpy.data.collections.get(self.ctc_collection)
        if col is None:
            self.report({'ERROR'}, _("找不到集合: %s") % self.ctc_collection)
            return {'CANCELLED'}

        # 设置 MHW CTC 工具面板的目标集合
        toolpanel = getattr(context.scene, 'mhw_ctc_toolpanel', None)
        if toolpanel is None:
            self.report({'ERROR'}, _("未找到 MHW CTC 场景属性，请确认 MHW Model Editor 已正确加载"))
            return {'CANCELLED'}
        toolpanel.ctcCollection = col

        armature = context.active_object

        # 构建物理骨骼集合
        settings = context.scene.mhw_suite_settings
        mapper = BoneMapManager()
        if mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        else:
            preset_bones = set()
        physics_bones = {b.name for b in armature.data.bones if b.name not in preset_bones}

        # 幂等性：收集已存在的链头骨骼名
        existing_heads = _get_existing_chain_heads(col)

        # 找所有链头
        chain_heads = [
            pb for pb in armature.pose.bones
            if pb.get("chain_role") in ("head", "branch_head")
        ]
        if not chain_heads:
            self.report({'WARNING'}, _("未找到链首骨骼（chain_role=head/branch_head），请先刷新骨骼颜色"))
            return {'CANCELLED'}

        created = 0
        skipped_existing = 0
        skipped_branch = []

        for head_pb in chain_heads:
            if head_pb.name in existing_heads:
                skipped_existing += 1
                continue

            if _has_branch(head_pb, physics_bones, armature):
                skipped_branch.append(head_pb.name)
                continue

            # 选中链头骨骼并调用 CTC chain 创建算子
            bpy.ops.pose.select_all(action='DESELECT')
            head_pb.bone.select = True
            armature.data.bones.active = head_pb.bone

            result = bpy.ops.mhw_ctc.create_chain_from_bone()
            if result == {'FINISHED'}:
                created += 1
            else:
                skipped_branch.append(head_pb.name)  # 创建失败也归入跳过

        # 汇报结果
        msg_parts = [_("已创建 %d 条链") % created]
        if skipped_existing:
            msg_parts.append(_("已存在跳过 %d 条") % skipped_existing)
        if skipped_branch:
            msg_parts.append(_("因分叉跳过 %d 条: %s") % (len(skipped_branch), ", ".join(skipped_branch)))
        self.report({'INFO'}, "，".join(msg_parts))
        return {'FINISHED'}


# ==========================================
# 3. 物理骨骼规范化（拆分 + 重命名）
# ==========================================

def _collect_physics_bones(armature, preset_bones):
    """收集物理骨骼（非基础骨），按层级顺序（父在前子在后）排列。"""
    physics = []
    def walk(bone):
        if bone.name not in preset_bones:
            physics.append(bone.name)
        for child in bone.children:
            walk(child)
    for bone in armature.data.bones:
        if bone.parent is None:
            walk(bone)
    return physics


# 解剖区域映射：标准骨骼名 → 区域
_REGION_MAP = {
    "head":   {"head"},
    "arms":   {
        "clavicle_L", "upperarm_L", "forearm_L", "hand_L",
        "thumb_01_L", "thumb_02_L", "thumb_03_L",
        "index_01_L", "index_02_L", "index_03_L",
        "middle_01_L", "middle_02_L", "middle_03_L",
        "ring_01_L", "ring_02_L", "ring_03_L",
        "pinky_01_L", "pinky_02_L", "pinky_03_L",
        "clavicle_R", "upperarm_R", "forearm_R", "hand_R",
        "thumb_01_R", "thumb_02_R", "thumb_03_R",
        "index_01_R", "index_02_R", "index_03_R",
        "middle_01_R", "middle_02_R", "middle_03_R",
        "ring_01_R", "ring_02_R", "ring_03_R",
        "pinky_01_R", "pinky_02_R", "pinky_03_R",
    },
    "torso":  {"pelvis", "spine_01", "spine_02", "spine_03", "neck"},
    "legs":   {
        "thigh_L", "shin_L", "foot_L", "toe_L",
        "thigh_R", "shin_R", "foot_R", "toe_R",
    },
}
# 反向查找：标准键 → 区域
_STD_TO_REGION = {}
for _region, _keys in _REGION_MAP.items():
    for _k in _keys:
        _STD_TO_REGION[_k] = _region

# 溢出路径部位分配选项
_SLOT_ITEMS = [
    ('body', "body", ""),
    ('arm',  "arm",  ""),
    ('wst',  "wst",  ""),
    ('leg',  "leg",  ""),
]

# 溢出路径 ID 范围
_SLOT_ID_RANGE = {
    'body': (300, 512),
    'arm':  (150, 200),
    'wst':  (150, 200),
    'leg':  (150, 200),
}
_SLOT_CAPACITY = {
    'body': 150,   # 实际受总骨骼数255限制，快速路径已处理，此处仅用于溢出UI显示
    'arm':  50,
    'wst':  50,
    'leg':  50,
}

# 溢出路径区域分配方案存储（场景属性，供 UI 读取）
_overflow_regions = []   # list of dict: {region, bone_count, slot}


def _is_tail_bone(bone, physics_bones_set):
    """尾骨骼：在物理骨集合中没有物理子骨的骨骼（即链末端）。"""
    return not any(c.name in physics_bones_set for c in bone.children)


def _classify_region(bone, _armature, preset_bones, mapper):
    """沿父链向上找最近基础骨，映射到解剖区域。找不到则返回 'torso'（兜底）。"""
    parent = bone.parent
    while parent:
        if parent.name in preset_bones:
            std_key = mapper.reverse_mapping.get(parent.name)
            if std_key:
                return _STD_TO_REGION.get(std_key, "torso")
            # 尝试模糊映射
            from ...core.bone_mapper import _normalize_bone_name
            norm = _normalize_bone_name(parent.name)
            for std_key, entry in mapper.mapping_data.items():
                for cand in entry.get("main", []) + entry.get("aux", []):
                    if _normalize_bone_name(cand) == norm:
                        return _STD_TO_REGION.get(std_key, "torso")
            return "torso"
        parent = parent.parent
    return None  # 孤立骨骼


def _assign_next_id(used_ids, id_range):
    """在 id_range 内找下一个未使用的 ID。"""
    start, end = id_range
    for i in range(start, end + 1):
        if i not in used_ids:
            return i
    return None


def _rename_physics_bones(armature, physics_bones_ordered, id_range):
    """将 physics_bones_ordered（骨骼名列表）重命名为 MhBone_xxx，使用 id_range 范围。
    返回 (成功数, 失败数)。"""
    used_ids = set()
    # 收集已在范围内的 MhBone ID，避免冲突
    for b in armature.data.bones:
        if b.name.startswith("MhBone_"):
            try:
                idx = int(b.name.split("_")[-1])
                if id_range[0] <= idx <= id_range[1]:
                    used_ids.add(idx)
            except (ValueError, IndexError):
                pass

    success = 0
    fail = 0
    # 必须在编辑模式下重命名
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for name in physics_bones_ordered:
        new_id = _assign_next_id(used_ids, id_range)
        if new_id is None:
            fail += 1
            continue
        eb = edit_bones.get(name)
        if eb is None:
            fail += 1
            continue
        eb.name = f"MhBone_{new_id:03d}"
        used_ids.add(new_id)
        success += 1
    bpy.ops.object.mode_set(mode='OBJECT')
    return success, fail


def _make_slot_name(original_name, slot):
    """生成带槽位后缀的骨架名，若含 .mod3 后缀则插在其前面。"""
    suffix = f"_{slot}"
    if original_name.endswith('.mod3'):
        return f"{original_name[:-5]}{suffix}.mod3"
    return f"{original_name}{suffix}"


def _duplicate_armature(source, new_name):
    """复制骨架对象并重命名，加入与原对象相同的集合，返回新对象。"""
    new_data = source.data.copy()
    new_obj = source.copy()
    new_obj.data = new_data
    new_obj.name = new_name
    new_data.name = new_name
    for col in source.users_collection:
        col.objects.link(new_obj)
    return new_obj


def _delete_bones(context, armature, bone_names):
    """从骨架中删除指定骨骼（通过编辑模式操作）。"""
    if not bone_names:
        return
    context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for name in bone_names:
        eb = edit_bones.get(name)
        if eb:
            edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')


# 溢出路径：存储区域分配方案的属性组
class MHWI_RegionAssignment(bpy.types.PropertyGroup):
    region: bpy.props.StringProperty()
    bone_count: bpy.props.IntProperty()
    slot: bpy.props.EnumProperty(
        name="目标部位",
        items=_SLOT_ITEMS,
        default='body',
    )


class MHWI_OT_SplitPhysicsBones(bpy.types.Operator):
    """将物理骨骼按部位拆分到不同骨架（不重命名骨骼）。
骨架对象名会加上部位后缀（_body/_arm/_wst/_leg）。
骨架总数 ≤255 时可选直接重命名或拆分；>255 时必须拆分。"""
    bl_idname = "mhwi.split_physics_bones"
    bl_label = "拆分物理骨"
    bl_options = {'REGISTER', 'UNDO'}

    fast_mode: bpy.props.EnumProperty(
        name="处理方式",
        items=[
            ('DIRECT', "直接重命名", "一步到位，全部物理骨命名到 300~512"),
            ('SPLIT',  "拆分为多个部位", "按部位拆分骨架，后续用「一键重命名」处理"),
        ],
        default='DIRECT',
    )
    is_fast_path: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == 'ARMATURE'
        )

    def _compute_assignments(self, context, armature, physics_bones, preset_bones, mapper):
        """计算区域→槽位分配方案，写入 scene.mhwi_region_assignments。"""
        total_bones = len(armature.data.bones)
        physics_bones_set = set(physics_bones)
        context.scene.mhwi_body_capacity = 255 - (total_bones - len(physics_bones))

        region_bones = {"head": [], "arms": [], "torso": [], "legs": []}
        for name in physics_bones:
            bone = armature.data.bones.get(name)
            if bone is None:
                continue
            region = _classify_region(bone, armature, preset_bones, mapper)
            if region in region_bones:
                region_bones[region].append(name)

        non_empty = {r: b for r, b in region_bones.items() if b}
        sorted_regions = sorted(non_empty.items(), key=lambda x: -len(x[1]))
        slot_iter = iter(['arm', 'wst', 'leg'])

        assignments = context.scene.mhwi_region_assignments
        assignments.clear()
        for i, (region, bones) in enumerate(sorted_regions):
            item = assignments.add()
            item.region = region
            if i == 0:
                item.bone_count = len(bones)
                item.slot = 'body'
            else:
                item.bone_count = sum(
                    1 for n in bones
                    if not _is_tail_bone(armature.data.bones[n], physics_bones_set)
                )
                item.slot = next(slot_iter, 'leg')
        return non_empty

    def _draw_slot_table(self, layout, context):
        """绘制区域→槽位分配表和容量状态。"""
        assignments = context.scene.mhwi_region_assignments
        slot_counts = {'body': 0, 'arm': 0, 'wst': 0, 'leg': 0}
        for item in assignments:
            slot_counts[item.slot] += item.bone_count

        region_labels = {"head": "头部", "arms": "双臂", "torso": "躯干", "legs": "双腿"}
        box = layout.box()
        row = box.row()
        row.label(text="区域")
        row.label(text="物理骨数")
        row.label(text="目标部位")
        for item in assignments:
            row = box.row()
            row.label(text=region_labels.get(item.region, item.region))
            row.label(text=str(item.bone_count))
            row.prop(item, "slot", text="")

        layout.separator()
        layout.label(text=_("容量状态："))
        cap_row = layout.row()
        body_capacity = context.scene.mhwi_body_capacity
        for slot, capacity in _SLOT_CAPACITY.items():
            cap = body_capacity if slot == 'body' else capacity
            count = slot_counts.get(slot, 0)
            icon = 'ERROR' if count > cap else 'CHECKMARK'
            cap_row.label(text=f"{slot}: {count}/{cap}", icon=icon)
        for slot, capacity in _SLOT_CAPACITY.items():
            cap = body_capacity if slot == 'body' else capacity
            if slot_counts.get(slot, 0) > cap:
                layout.label(text=_("警告：%s 超出容量限制，请调整分配") % slot.upper(), icon='ERROR')

    def invoke(self, context, _event):
        armature = context.active_object
        mapper = BoneMapManager()
        if not mapper.load_preset("怪猎世界.json", is_import_x=True):
            self.report({'ERROR'}, _("无法加载怪猎世界预设"))
            return {'CANCELLED'}
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        physics_bones = _collect_physics_bones(armature, preset_bones)
        if not physics_bones:
            self.report({'INFO'}, _("未找到需要处理的物理骨骼"))
            return {'CANCELLED'}

        self.is_fast_path = len(armature.data.bones) <= 255
        non_empty = self._compute_assignments(context, armature, physics_bones, preset_bones, mapper)
        if not non_empty:
            self.report({'WARNING'}, _("物理骨骼均为孤立骨骼，无法自动分配区域"))
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        if self.is_fast_path:
            layout.label(text=_("物理骨数未超出 body 限制范围，如何处理？"))
            layout.prop(self, "fast_mode", expand=True)
            if self.fast_mode == 'DIRECT':
                return
            layout.separator()
            layout.label(text=_("请确认各区域的目标部位："))
        else:
            layout.label(text=_("总骨骼数超过 255，请分配各区域的目标部位："))
        self._draw_slot_table(layout, context)

    def execute(self, context):
        armature = context.active_object
        mapper = BoneMapManager()
        if not mapper.load_preset("怪猎世界.json", is_import_x=True):
            self.report({'ERROR'}, _("无法加载怪猎世界预设"))
            return {'CANCELLED'}
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        physics_bones = _collect_physics_bones(armature, preset_bones)

        # 快速路径 + 直接重命名：一步到位
        if self.is_fast_path and self.fast_mode == 'DIRECT':
            context.view_layer.objects.active = armature
            success, fail = _rename_physics_bones(armature, physics_bones, _SLOT_ID_RANGE['body'])
            self.report({'INFO'}, _("重命名完成：成功 %d 根，失败 %d 根") % (success, fail))
            return {'FINISHED'}

        # 拆分路径
        assignments = context.scene.mhwi_region_assignments
        region_slot = {item.region: item.slot for item in assignments}

        # 溢出路径容量验证
        if not self.is_fast_path:
            slot_counts = {'body': 0, 'arm': 0, 'wst': 0, 'leg': 0}
            for item in assignments:
                slot_counts[item.slot] += item.bone_count
            body_capacity = context.scene.mhwi_body_capacity
            for slot, capacity in _SLOT_CAPACITY.items():
                cap = body_capacity if slot == 'body' else capacity
                if slot_counts.get(slot, 0) > cap:
                    self.report({'ERROR'}, _("%s 超出容量限制（%d/%d），请先调整分配") % (
                        slot.upper(), slot_counts[slot], cap))
                    return {'CANCELLED'}

        # 按槽位收集骨骼
        slot_bones = {}
        for name in physics_bones:
            bone = armature.data.bones.get(name)
            if bone is None:
                continue
            region = _classify_region(bone, armature, preset_bones, mapper)
            if region is None:
                continue
            slot = region_slot.get(region, 'body')
            slot_bones.setdefault(slot, []).append(name)

        # 复制非 body 槽骨架（在修改原骨架前）
        slot_armatures = {'body': armature}
        for slot in slot_bones:
            if slot != 'body':
                slot_armatures[slot] = _duplicate_armature(
                    armature, _make_slot_name(armature.name, slot)
                )

        # 每个槽位骨架删除非本槽物理骨
        for slot, arm_obj in slot_armatures.items():
            slot_phys = set(slot_bones.get(slot, []))
            other_phys = [n for n in physics_bones if n not in slot_phys]
            _delete_bones(context, arm_obj, other_phys)

        # 原骨架重命名为 _body
        armature.name = _make_slot_name(armature.name, 'body')
        armature.data.name = armature.name

        context.view_layer.objects.active = armature
        self.report({'INFO'}, _("拆分完成：已生成 %d 个骨架（%s）") % (
            len(slot_armatures), "、".join(slot_armatures.keys())))
        return {'FINISHED'}


class MHWI_OT_BatchRenamePhysicsBones(bpy.types.Operator):
    """对选中的所有骨架批量重命名物理骨骼为 MhBone_xxx 格式。
名称含 _body 的骨架使用 300~512 范围；其他骨架使用 150~200（非尾骨）+ 201~245（尾骨）范围。
请先用「拆分物理骨」完成骨架拆分，再运行此操作。"""
    bl_idname = "mhwi.batch_rename_physics_bones"
    bl_label = "一键重命名"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

    @staticmethod
    def _is_body_slot(name):
        base = name[:-5] if name.endswith('.mod3') else name
        return base.endswith('_body')

    def execute(self, context):
        mapper = BoneMapManager()
        if not mapper.load_preset("怪猎世界.json", is_import_x=True):
            self.report({'ERROR'}, _("无法加载怪猎世界预设"))
            return {'CANCELLED'}

        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        total_success = 0
        total_fail = 0

        for arm_obj in armatures:
            context.view_layer.objects.active = arm_obj
            preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
            physics = _collect_physics_bones(arm_obj, preset_bones)
            if not physics:
                continue

            if self._is_body_slot(arm_obj.name):
                s, f = _rename_physics_bones(arm_obj, physics, _SLOT_ID_RANGE['body'])
                total_success += s
                total_fail += f
            else:
                physics_set = set(physics)
                non_tail = [n for n in physics
                            if not _is_tail_bone(arm_obj.data.bones[n], physics_set)]
                tail = [n for n in physics
                        if _is_tail_bone(arm_obj.data.bones[n], physics_set)]
                s, f = _rename_physics_bones(arm_obj, non_tail, (150, 200))
                total_success += s
                total_fail += f
                s, f = _rename_physics_bones(arm_obj, tail, (201, 245))
                total_success += s
                total_fail += f

        self.report({'INFO'}, _("重命名完成：成功 %d 根，失败 %d 根") % (total_success, total_fail))
        return {'FINISHED'}


# 注册所有类
classes = [
    MHWI_OT_AlignNonPhysics,
    MHWI_OT_AutoCreateChains,
    MHWI_RegionAssignment,
    MHWI_OT_SplitPhysicsBones,
    MHWI_OT_BatchRenamePhysicsBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhwi_region_assignments = bpy.props.CollectionProperty(
        type=MHWI_RegionAssignment
    )
    bpy.types.Scene.mhwi_body_capacity = bpy.props.IntProperty(default=150)

def unregister():
    del bpy.types.Scene.mhwi_region_assignments
    del bpy.types.Scene.mhwi_body_capacity
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
