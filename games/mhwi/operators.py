import sys
import time
import bpy
import re
from ...core.i18n import T
from ...core import bone_utils, facial_bones, facial_maps, fork_resolver, ref_skeleton, weight_utils
from ...core.bone_mapper import BoneMapManager, resolve_preset
from ...core.standard_ops import _build_fuzzy_preset_bones, _run_bone_color_refresh
from ...core.re_chain_utils import _patch_chain_cleanup, _straighten_chain_orientations


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
    bl_idname = "mhwi.align_non_physics"
    bl_label = "Align Non-Physics Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.align_non_physics_desc")

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        if len(selected_objects) != 2 or not context.active_object:
            self.report({'ERROR'}, T("mhwi.operators.select_two_armatures"))
            return {'CANCELLED'}
        target_armature = context.active_object
        source_armature = [obj for obj in selected_objects if obj != target_armature][0]
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        aligned = bone_utils.align_armatures_by_name(
            source_armature, target_armature, skip_fn=_is_mhwi_physics)
        skip = sum(1 for b in target_armature.data.bones if _is_mhwi_physics(b.name))
        self.report({'INFO'}, T("mhwi.operators.align_done").format(aligned=aligned, skip=skip))
        return {'FINISHED'}


# ==========================================
# 2. 一键创建 CTC Chain
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


def _detach_bones(armature, names):
    """进编辑模式，把 names 里的骨骼临时摘成无父骨，返回 {名: (父名, 是否相连)} 供接回。
    结束时停在姿态模式。

    摘的是父子关系，不是位置：编辑骨的头尾存的是骨架空间坐标，断开相连之后再改父级
    不会移动骨骼。"""
    saved = {}
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for name in names:
        eb = edit_bones.get(name)
        if eb is None:
            continue
        saved[name] = (eb.parent.name if eb.parent else None, eb.use_connect)
        eb.use_connect = False
        eb.parent = None
    bpy.ops.object.mode_set(mode='POSE')
    return saved


def _reattach_bones(armature, saved):
    """_detach_bones 的逆操作。先挂父级、再恢复相连（相连会把头吸到父骨尾部，而原本
    就是相连的，位置本来就在那里）。结束时停在姿态模式。"""
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    for name, (parent_name, connected) in saved.items():
        eb = edit_bones.get(name)
        parent = edit_bones.get(parent_name) if parent_name else None
        if eb is None or parent is None:
            continue
        eb.parent = parent
        eb.use_connect = connected
    bpy.ops.object.mode_set(mode='POSE')


class MHWI_OT_AutoCreateChains(bpy.types.Operator):
    bl_idname = "mhwi.auto_create_chains"
    bl_label = "Auto-Create CTC Chains"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.auto_create_chains_desc")

    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="Create Directly (auto-refresh bone colors)",
        description="Automatically run bone color refresh first, then attempt to create",
        default=False,
    )

    ctc_collection: bpy.props.EnumProperty(
        name="CTC Collection",
        description="Select the CTC Collection to write into",
        items=_get_ctc_col_items,
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="Auto-create Collection",
        description="When checked, automatically create the CTC Collection and Header — no manual preparation needed",
        default=False,
    )
    collection_name: bpy.props.StringProperty(
        name="Collection Name",
        description="Name of the newly created CTC Collection (without extension)",
        default="",
    )
    straighten_orientation: bpy.props.BoolProperty(
        name="Bone Orientation Preprocessing",
        description="Before creating, adjust all physics bones to point straight up with roll reset to zero",
        default=False,
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
        arm = context.active_object
        self.has_no_markers = not any(
            pb.get("chain_role") in ("head", "branch_head")
            for pb in (arm.pose.bones if arm and arm.type == 'ARMATURE' else [])
        )

        global _ctc_col_items
        _ctc_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_ctc_collection(col)
        ]

        if not self.collection_name:
            toolpanel = getattr(context.scene, 'mhw_mod3_toolpanel', None)
            mod3_col = toolpanel.get("lastImportCollection") if toolpanel else None
            if mod3_col and ".mod3" in mod3_col:
                self.collection_name = mod3_col.split(".mod3")[0]

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, _context):
        layout = self.layout
        if self.has_no_markers:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text=T("mhwi.operators.no_markers_warning"), icon='ERROR')
            col.label(text=T("mhwi.operators.no_markers_hint"))
            layout.prop(self, "auto_refresh", text=T("mhwi.operators.auto_refresh_name"))
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text=T("mhwi.operators.auto_create_collection_name"))
        if self.auto_create_collection:
            layout.prop(self, "collection_name", text=T("core.re_chain_utils.collection"))
        else:
            layout.prop(self, "ctc_collection")
        layout.prop(self, "straighten_orientation", text=T("mhwi.operators.straighten_orientation_name"))

    def execute(self, context):
        t_total = time.perf_counter()

        # 在任何可能改变激活对象的操作之前先保存骨架引用
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        if self.has_no_markers:
            if not self.auto_refresh:
                return {'CANCELLED'}
            ok, msg = _run_bone_color_refresh(context, armature)
            if not ok:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}

        if self.auto_create_collection:
            result = bpy.ops.mhw_ctc.create_ctc_collection(collectionName=self.collection_name)
            if result != {'FINISHED'}:
                self.report({'ERROR'}, T("mhwi.operators.auto_create_ctc_failed"))
                return {'CANCELLED'}
            # create_ctc_collection 可能改变了激活对象和模式，恢复骨架并进入姿态模式
            context.view_layer.objects.active = armature
            armature.select_set(True)
            if context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')
        else:
            col = bpy.data.collections.get(self.ctc_collection)
            if col is None:
                self.report({'ERROR'}, T("mhwi.operators.collection_not_found").format(name=self.ctc_collection))
                return {'CANCELLED'}
            toolpanel = getattr(context.scene, 'mhw_ctc_toolpanel', None)
            if toolpanel is None:
                self.report({'ERROR'}, T("mhwi.operators.ctc_toolpanel_missing"))
                return {'CANCELLED'}
            toolpanel.ctcCollection = col

        settings = context.scene.mhw_suite_settings
        mapper = BoneMapManager()
        _x, _unused = resolve_preset(settings.import_preset_enum, armature, True)
        if _x and mapper.load_preset(_x, is_import_x=True):
            preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        else:
            preset_bones = set()
        physics_bones = {b.name for b in armature.data.bones if b.name not in preset_bones}

        if self.straighten_orientation:
            _straighten_chain_orientations(armature, physics_bones)
            context.view_layer.objects.active = armature
            armature.select_set(True)
            if context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')

        col = context.scene.mhw_ctc_toolpanel.ctcCollection
        existing_heads = _get_existing_chain_heads(col)

        pose_bones = armature.pose.bones
        if not any(pb.get("chain_role") in ("head", "branch_head") for pb in pose_bones):
            self.report({'WARNING'}, T("mhwi.operators.no_chain_heads"))
            return {'CANCELLED'}

        # CTC 一条链必须是线性的，所以分叉在这里拆成若干线性链：主链延续穿过分叉，
        # 其余分支另起一条链（单层）；no_chain 的子树不生成。见 core/fork_resolver。
        #
        # 参与规划的只取带链首标记的骨及其全部后代，不用上面的 physics_bones：重命名成
        # MhBone_xxx 之后，导入预设未必还认得出基础骨，那个集合可能把整副身体都算进去。
        plan_set, stack = set(), [b for b in armature.data.bones
                                  if pose_bones[b.name].get("chain_role") in ("head", "branch_head")]
        while stack:
            b = stack.pop()
            if b.name not in plan_set:
                plan_set.add(b.name)
                stack.extend(b.children)
        mw = armature.matrix_world
        plan = fork_resolver.plan_ctc_chains(
            armature.data.bones, plan_set,
            role_of=lambda n: pose_bones[n].get("chain_role"),
            head_of=lambda n: tuple(mw @ pose_bones[n].head))
        to_create = [c for c in plan.chains if c[0] not in existing_heads]
        skipped_existing = len(plan.chains) - len(to_create)

        print(f"[ChainGen CTC] {len(plan.chains)} chains planned "
              f"({len(to_create)} to create), {len(plan.too_short)} too short, "
              f"{len(plan.no_chain_roots) + len(plan.skipped)} subtree(s) without chain",
              file=sys.stderr)

        # create_chain_from_bone 取起始骨的全部后代，并拒绝多子骨的节点：把每条链上
        # 不属于该链的子骨临时摘走，建完再接回，它看到的后代就恰好是链本身。
        detach = fork_resolver.children_to_detach(armature.data.bones, to_create)
        saved_parents = {}

        _patches = _patch_chain_cleanup(disable=True)

        created = 0
        failed = []

        t_loop = time.perf_counter()
        try:
            if detach:
                saved_parents = _detach_bones(armature, detach)
            for idx, names in enumerate(to_create, 1):
                head_pb = pose_bones.get(names[0])
                if head_pb is None:
                    failed.append(names[0])
                    continue

                bpy.ops.pose.select_all(action='DESELECT')
                # Blender 4.x: selection lives on Bone data; 5.x: moved to PoseBone
                if hasattr(head_pb, 'select'):
                    head_pb.select = True
                else:
                    head_pb.bone.select = True
                armature.data.bones.active = head_pb.bone

                t0 = time.perf_counter()
                result = bpy.ops.mhw_ctc.create_chain_from_bone()
                t_chain = time.perf_counter() - t0

                if result == {'FINISHED'}:
                    created += 1
                else:
                    failed.append(names[0])

                print(f"[ChainGen CTC] Chain {idx:3d}/{len(to_create)}  "
                      f"create={t_chain:.4f}s  bones={len(names)}  head={names[0]}",
                      file=sys.stderr)
        finally:
            if saved_parents:
                _reattach_bones(armature, saved_parents)
            _patch_chain_cleanup(disable=False)
            if _patches and created > 0:
                mod, _align, _color = _patches[0]
                _align()
                _color(armature)

        t_loop = time.perf_counter() - t_loop
        t_total = time.perf_counter() - t_total
        print(f"[ChainGen CTC] --- loop: {t_loop:.4f}s  total: {t_total:.4f}s  "
              f"created={created}  skipped_existing={skipped_existing}  failed={len(failed)} ---",
              file=sys.stderr)

        def _names(items):
            return ", ".join(items[:5]) + ("…" if len(items) > 5 else "")

        msg_parts = [T("mhwi.operators.chains_created").format(n=created)]
        if skipped_existing:
            msg_parts.append(T("mhwi.operators.chains_skipped_existing").format(n=skipped_existing))
        if failed:
            msg_parts.append(T("mhwi.operators.chains_failed").format(
                n=len(failed), names=_names(failed)))
        if plan.too_short:
            msg_parts.append(T("mhwi.operators.chains_too_short").format(
                n=len(plan.too_short), names=_names(plan.too_short)))
        self.report({'INFO'}, T("mhwi.operators.list_sep").join(msg_parts))
        no_chain = plan.no_chain_roots + plan.skipped
        if no_chain:
            self.report({'WARNING'}, T("mhwi.operators.chains_no_chain").format(
                n=len(no_chain), names=_names(no_chain)))
        return {'FINISHED'}


# ==========================================
# 3. 物理骨骼规范化（拆分 + 重命名）
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


def _count_rename_failures(armature, physics_bones_ordered, id_range, also_exclude=None):
    """预检重命名会失败的骨骼数量（不实际改名）。
    返回 (成功数, 失败数)。

    also_exclude: 额外要从 used_ids 中排除的骨骼名集合。
    用于多批次顺序重命名时，前一批次的骨骼在执行时已离开当前范围，
    预检阶段需显式告知本函数忽略这些骨骼的当前 ID。
    """
    # 待重命名骨骼即将释放自身 ID，不应计入"已占用"
    physics_bones_set = set(physics_bones_ordered)
    if also_exclude:
        physics_bones_set |= set(also_exclude)
    used_ids = set()
    for b in armature.data.bones:
        if b.name.startswith("MhBone_") and b.name not in physics_bones_set:
            try:
                idx = int(b.name.split("_")[-1])
                if id_range[0] <= idx <= id_range[1]:
                    used_ids.add(idx)
            except (ValueError, IndexError):
                pass
    success = 0
    fail = 0
    existing_names = {b.name for b in armature.data.bones}
    for name in physics_bones_ordered:
        new_id = _assign_next_id(used_ids, id_range)
        if new_id is None or name not in existing_names:
            fail += 1
            continue
        used_ids.add(new_id)
        success += 1
    return success, fail


def _child_meshes(armature):
    """返回骨架的所有子级网格对象（递归，不要求已绑定为姿态修改器）。"""
    return [obj for obj in armature.children_recursive if obj.type == 'MESH']


def _rename_physics_bones(armature, physics_bones_ordered, id_range):
    """将 physics_bones_ordered（骨骼名列表）重命名为 MhBone_xxx，使用 id_range 范围。
    返回 (成功数, 失败数)。

    采用两步改名（临时名 → 正式名）避免同序列内的命名冲突：
    若直接逐一改名，前面的骨骼抢占了后面骨骼的当前名称对应的 ID，
    Blender 会自动给被顶替的骨骼追加 .001 后缀，导致后续查找失败。

    骨架子级网格若已绑定姿态（Armature）修改器指向本骨架，Blender 会在改名时
    自动同步其顶点组名；未绑定的子级网格不会被自动处理，因此这里对所有子级
    网格额外做一次同名顶点组的手动改名（已被自动同步的网格此时对应顶点组已
    不存在，手动步骤会直接跳过，不会重复处理或产生冲突）。
    """
    # 待重命名骨骼即将释放自身 ID，不应计入"已占用"
    physics_bones_set = set(physics_bones_ordered)
    used_ids = set()
    for b in armature.data.bones:
        if b.name.startswith("MhBone_") and b.name not in physics_bones_set:
            try:
                idx = int(b.name.split("_")[-1])
                if id_range[0] <= idx <= id_range[1]:
                    used_ids.add(idx)
            except (ValueError, IndexError):
                pass

    # 预先计算每根骨骼的目标名称
    assignments = []  # [(old_name, new_name | None), ...]
    for name in physics_bones_ordered:
        new_id = _assign_next_id(used_ids, id_range)
        if new_id is None:
            assignments.append((name, None))
        else:
            assignments.append((name, f"MhBone_{new_id:03d}"))
            used_ids.add(new_id)

    child_meshes = _child_meshes(armature)

    success = 0
    fail = 0
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    # 第一步：全部改成临时名，消除新旧名称之间的冲突
    temp_to_final = {}
    for i, (old_name, new_name) in enumerate(assignments):
        if new_name is None:
            fail += 1
            continue
        eb = edit_bones.get(old_name)
        if eb is None:
            fail += 1
            continue
        tmp = f"__tmp_phys_{i}__"
        eb.name = tmp
        for mesh_obj in child_meshes:
            vg = mesh_obj.vertex_groups.get(old_name)
            if vg is not None:
                vg.name = tmp
        temp_to_final[tmp] = new_name

    # 第二步：从临时名改为正式名
    for tmp, final in temp_to_final.items():
        eb = edit_bones.get(tmp)
        if eb is not None:
            eb.name = final
            success += 1
        else:
            fail += 1
        for mesh_obj in child_meshes:
            vg = mesh_obj.vertex_groups.get(tmp)
            if vg is not None:
                vg.name = final

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
        name="Target Slot",
        items=_SLOT_ITEMS,
        default='body',
    )


def _get_split_fast_mode_items(self, context):
    return [
        ('DIRECT', T("mhwi.operators.fast_mode_direct"), T("mhwi.operators.fast_mode_direct_desc")),
        ('SPLIT',  T("mhwi.operators.fast_mode_split"),  T("mhwi.operators.fast_mode_split_desc")),
    ]


class MHWI_OT_SplitPhysicsBones(bpy.types.Operator):
    bl_idname = "mhwi.split_physics_bones"
    bl_label = "Split Physics Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.split_physics_bones_desc")

    fast_mode: bpy.props.EnumProperty(
        name="Processing Mode",
        items=_get_split_fast_mode_items,
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

        region_labels = {
            "head": "mhwi.operators.region_head",
            "arms": "mhwi.operators.region_arms",
            "torso": "mhwi.operators.region_torso",
            "legs": "mhwi.operators.region_legs",
        }
        box = layout.box()
        row = box.row()
        row.label(text=T("mhwi.operators.col_region"))
        row.label(text=T("mhwi.operators.col_bone_count"))
        row.label(text=T("mhwi.operators.col_target_slot"))
        for item in assignments:
            row = box.row()
            row.label(text=T(region_labels.get(item.region, item.region)))
            row.label(text=str(item.bone_count))
            row.prop(item, "slot", text="")

        layout.separator()
        layout.label(text=T("mhwi.operators.capacity_status"))
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
                layout.label(text=T("mhwi.operators.capacity_exceeded").format(slot=slot.upper()), icon='ERROR')

    def invoke(self, context, _event):
        armature = context.active_object
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
            return {'CANCELLED'}
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        physics_bones = _collect_physics_bones(armature, preset_bones)
        if not physics_bones:
            self.report({'INFO'}, T("mhwi.operators.no_physics_bones_found"))
            return {'CANCELLED'}

        self.is_fast_path = len(armature.data.bones) <= 255
        non_empty = self._compute_assignments(context, armature, physics_bones, preset_bones, mapper)
        if not non_empty:
            self.report({'WARNING'}, T("mhwi.operators.isolated_physics_bones"))
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        if self.is_fast_path:
            layout.label(text=T("mhwi.operators.fast_path_prompt"))
            layout.prop(self, "fast_mode", expand=True)
            if self.fast_mode == 'DIRECT':
                return
            layout.separator()
            layout.label(text=T("mhwi.operators.confirm_region_targets"))
        else:
            layout.label(text=T("mhwi.operators.over_255_prompt"))
        self._draw_slot_table(layout, context)

    def execute(self, context):
        armature = context.active_object
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
            return {'CANCELLED'}
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        physics_bones = _collect_physics_bones(armature, preset_bones)

        # 快速路径 + 直接重命名：一步到位
        if self.is_fast_path and self.fast_mode == 'DIRECT':
            context.view_layer.objects.active = armature
            s, f = _count_rename_failures(armature, physics_bones, _SLOT_ID_RANGE['body'])
            if f > 0:
                self.report({'ERROR'},
                    T("mhwi.operators.exceeds_bone_count").format(n=f))
                return {'CANCELLED'}
            success, fail = _rename_physics_bones(armature, physics_bones, _SLOT_ID_RANGE['body'])
            self.report({'INFO'}, T("mhwi.operators.rename_done").format(success=success, fail=fail))
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
                    self.report({'ERROR'}, T("mhwi.operators.slot_capacity_exceeded").format(
                        slot=slot.upper(), count=slot_counts[slot], cap=cap))
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
        self.report({'INFO'}, T("mhwi.operators.split_done").format(
            n=len(slot_armatures), names=T("mhwi.operators.list_sep").join(slot_armatures.keys())))
        return {'FINISHED'}


class MHWI_OT_BatchRenamePhysicsBones(bpy.types.Operator):
    bl_idname = "mhwi.batch_rename_physics_bones"
    bl_label = "Batch Rename Physics Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.batch_rename_desc")

    fail_count: bpy.props.IntProperty(default=0, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

    @staticmethod
    def _is_body_slot(name):
        base = name[:-5] if name.endswith('.mod3') else name
        return base.endswith('_body')

    @staticmethod
    def _count_failures_for_armature(mapper, arm_obj):
        """预检单个骨架的失败数，但不实际改名。"""
        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
        physics = _collect_physics_bones(arm_obj, preset_bones)
        if not physics:
            return 0

        if MHWI_OT_BatchRenamePhysicsBones._is_body_slot(arm_obj.name):
            _, f = _count_rename_failures(arm_obj, physics, _SLOT_ID_RANGE['body'])
            return f
        else:
            physics_set = set(physics)
            non_tail = [n for n in physics
                        if not _is_tail_bone(arm_obj.data.bones[n], physics_set)]
            tail = [n for n in physics
                    if _is_tail_bone(arm_obj.data.bones[n], physics_set)]
            _, f1 = _count_rename_failures(arm_obj, non_tail, (150, 200))
            # tail 的预检需排除 non_tail：执行时 non_tail 已先行重命名离开 (201, 245)，
            # 若 non_tail 当前有 ID 落在该范围，不应计为 tail 的冲突
            _, f2 = _count_rename_failures(arm_obj, tail, (201, 245), also_exclude=non_tail)
            return f1 + f2

    def invoke(self, context, _event):
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
            return {'CANCELLED'}

        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        total_fail = 0
        for arm_obj in armatures:
            total_fail += self._count_failures_for_armature(mapper, arm_obj)

        if total_fail == 0:
            return self.execute(context)

        self.fail_count = total_fail
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.label(text=T("mhwi.operators.warning_label"), icon='ERROR')
        layout.separator()
        layout.label(
            text=T("mhwi.operators.batch_rename_over_limit").format(n=self.fail_count))
        layout.label(text=T("mhwi.operators.confirm_rename_anyway"))

    def execute(self, context):
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
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

        self.report({'INFO'}, T("mhwi.operators.rename_done").format(success=total_success, fail=total_fail))
        return {'FINISHED'}


# ── 网格显示条件 ────────────────────────────────────────────────────────────
# mod3 把"这个网格什么时候显示"编码在物体名的 Group_<N> 里，没有自定义属性；
# 导入器回读时用的是同一个正则。所以设置显示条件本质就是改名。
_MOD3_NAME_RE = re.compile(r"^Group_\d+_Sub_\d+__.+$")
_MOD3_GROUP_RE = re.compile(r"(Group_)(\d+)(.*)")


def _mhwi_display_condition_items(self, context):
    return [(str(v), T(k), "") for v, k in (
        (0,  "mhwi.operators.disp_cond_0"),
        (1,  "mhwi.operators.disp_cond_1"),
        (2,  "mhwi.operators.disp_cond_2"),
        (30, "mhwi.operators.disp_cond_30"),
        (31, "mhwi.operators.disp_cond_31"),
        (32, "mhwi.operators.disp_cond_32"),
        (33, "mhwi.operators.disp_cond_33"),
        (34, "mhwi.operators.disp_cond_34"),
        (35, "mhwi.operators.disp_cond_35"),
        (-1, "mhwi.operators.disp_cond_custom"),
    )]


def _rename_to_mod3_format(mesh_objs):
    """照搬 MHW Model Editor 的 Rename Meshes：Group_<g>_Sub_<n>__<材质名>。
    保留已能解析出的 group id，解析不到按 0 处理。"""
    group_index = {}
    for obj in mesh_objs:
        m = re.search(r"Group_(\d+)", obj.name)
        group_id = int(m.group(1)) if m else 0
        group_index.setdefault(group_id, 0)
        if obj.data.materials and obj.data.materials[0]:
            mat = obj.data.materials[0].name.split(".", 1)[0].strip()
        else:
            mat = "NO_MATERIAL"
        obj.name = f"Group_{group_id}_Sub_{group_index[group_id]}__{mat}"
        group_index[group_id] += 1


class MHWI_OT_SetMeshDisplayCondition(bpy.types.Operator):
    """设置选中网格的显示条件（写入物体名的 Group ID）"""
    bl_idname = "mhwi.set_mesh_display_condition"
    bl_label = "Set Mesh Display Condition"
    bl_options = {'REGISTER', 'UNDO'}

    preset: bpy.props.EnumProperty(
        name="Preset",
        items=_mhwi_display_condition_items,
        default=0,
    )
    group_id: bpy.props.IntProperty(
        name="Group ID", default=0, min=0, max=65535,
        description="Written into the Group_<N> part of the object name",
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.set_display_condition_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "preset", text=T("mhwi.operators.disp_field_preset"))
        # Only surfaced under "Other" — showing a free number next to the preset
        # list reads as "any value works", but the game only honours these IDs
        if self.preset == "-1":
            col.prop(self, "group_id", text=T("mhwi.operators.disp_field_group_id"))

    def execute(self, context):
        # Selecting a preset syncs the number; CUSTOM (-1) leaves it alone
        if self.preset != "-1":
            self.group_id = int(self.preset)

        mesh_objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objs:
            self.report({'ERROR'}, T("mhwi.operators.disp_no_mesh"))
            return {'CANCELLED'}

        # ".001" duplicate suffixes need no special case: the trailing .+ of the
        # format regex covers them, and the group regex keeps everything after
        # the number untouched
        needs_rename = [o for o in mesh_objs if not _MOD3_NAME_RE.match(o.name)]
        renamed = 0
        if needs_rename:
            _rename_to_mod3_format(needs_rename)
            renamed = len(needs_rename)

        for obj in mesh_objs:
            obj.name = _MOD3_GROUP_RE.sub(
                lambda m: f"{m.group(1)}{self.group_id}{m.group(3)}", obj.name, count=1)

        msg = T("mhwi.operators.disp_done").format(n=len(mesh_objs), gid=self.group_id)
        if renamed:
            msg += T("mhwi.operators.disp_renamed_suffix").format(n=renamed)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# ==========================================
# 终末地面部顶点组改名 (Endfield -> MHWorld)
# ==========================================
# 对应表在 assets/facial_maps/endfield_to_mhwi.json，是作者手工标注的，与荒野那份
# (endfield_to_mhws.json) 各自独立 —— 两家的面部骨集合不同，实测也没有 1:1 的自动
# 对应，所以不能由一份推出另一份。见 core/facial_maps.py。
class MHWI_OT_EndfieldFaceRename(bpy.types.Operator):
    bl_idname = "mhwi.endfield_face_rename"
    bl_label = "Endfield Face Rename"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.endfield_face_rename_desc")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        pairs = facial_maps.load("endfield_to_mhwi")
        if not pairs:
            self.report({'ERROR'}, T("mhwi.operators.endfield_map_missing"))
            return {'CANCELLED'}
        total = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for old_name, new_name in pairs:
                if weight_utils.rename_or_merge_vgroup(obj, old_name, new_name):
                    total += 1
        self.report({'INFO'}, T("mhwi.operators.endfield_processed").format(n=total))
        return {'FINISHED'}


# ==========================================
# 一键添加表情骨 (从原生角色骨架移植表情骨到目标骨架)
# ==========================================
# MHWI 的面部没有统一的根：头骨下直接并列挂着一百多根表情骨（眉、眼睑、嘴唇、
# 舌、牙……），所以把头骨的每个子级都当作一个移植根。不提供假头法——MHWI 骨名是
# 纯编号，没有哪根是"上眼睑"的名字信号，也没有实测过它的睑缘支点位置。
_MHWI_HEAD_BONE_ID = "004"


def _mhwi_bone_prefix(arm_obj):
    """目标骨架用的是 MhBone_ 还是 bonefunction_（mod3 导入有两种命名）。"""
    names = [b.name for b in arm_obj.data.bones]
    if any(n.startswith("MhBone_") for n in names):
        return "MhBone_"
    if any(n.startswith("bonefunction_") for n in names):
        return "bonefunction_"
    return None


class MHWI_OT_AddFacialBones(bpy.types.Operator):
    bl_idname = "mhwi.add_facial_bones"
    bl_label = "Add Facial Bones"
    bl_options = {'REGISTER', 'UNDO'}

    target_armature: bpy.props.EnumProperty(
        name="Skeleton",
        description="Select the skeleton to add facial bones to",
        items=bone_utils.get_armature_enum_items,
    )
    reference_character: bpy.props.EnumProperty(
        name="Reference Character",
        description="Select the reference character skeleton to source facial bones from",
        items=lambda self, ctx: ref_skeleton.get_reference_skeleton_items('mhwi', {
            "f_face000.fbx": T("mhwi.operators.facial_ref_female"),
            "m_face000.fbx": T("mhwi.operators.facial_ref_male"),
        }),
    )

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.add_facial_bones_desc")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in bpy.data.objects)

    def invoke(self, context, event):
        active = context.active_object
        if active and active.type == 'ARMATURE':
            self.target_armature = active.name
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        note = layout.row()
        note.active = False
        note.label(text=T("mhwi.operators.facial_bones_warning"))
        layout.separator()
        layout.prop(self, "target_armature", text=T("mhwi.operators.facial_target_armature"))
        layout.prop(self, "reference_character", text=T("core.re_chain_utils.reference_character"))

    def execute(self, context):
        target_arm = bpy.data.objects.get(self.target_armature)
        if target_arm is None or target_arm.type != 'ARMATURE':
            self.report({'WARNING'}, T("core.re_chain_utils.select_valid_armature"))
            return {'CANCELLED'}

        if not self.reference_character or self.reference_character == 'NONE':
            self.report({'ERROR'}, T("mhwi.operators.facial_no_reference"))
            return {'CANCELLED'}

        prefix = _mhwi_bone_prefix(target_arm)
        head_name = f"{prefix}{_MHWI_HEAD_BONE_ID}" if prefix else None
        if head_name is None or head_name not in target_arm.data.bones:
            self.report({'ERROR'}, T("mhwi.operators.facial_no_head_bone").format(
                bone=f"MhBone_{_MHWI_HEAD_BONE_ID}"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        ref_arm_obj = ref_skeleton.import_reference_armature('mhwi', self.reference_character)
        if ref_arm_obj is None:
            self.report({'ERROR'}, T("mhwi.operators.facial_ref_import_failed").format(
                name=self.reference_character))
            return {'CANCELLED'}

        try:
            # 参考骨架一律是 MhBone_ 命名；目标若是 bonefunction_，先对齐命名，
            # 否则按名字对齐和父级挂接都找不到对应骨骼
            if prefix != "MhBone_":
                for b in ref_arm_obj.data.bones:
                    if b.name.startswith("MhBone_"):
                        b.name = prefix + b.name[len("MhBone_"):]

            # 只让头骨及以上的骨骼参与对齐。表情骨本身要整体照搬参考的坐标，
            # 目标上同名的旧表情骨马上就会被清掉，不该反过来拉动参考
            bone_utils.align_armatures_by_name(
                target_arm, ref_arm_obj, mode='POS_ONLY',
                skip_fn=lambda n: n != head_name and not _is_head_ancestor(target_arm, n, head_name))

            ref_head = ref_arm_obj.data.bones.get(head_name)
            roots = [] if ref_head is None else [
                c.name for c in ref_head.children if not c.name.lower().endswith("_end")]
            created = facial_bones.graft_facial_bones(ref_arm_obj, target_arm, roots)
            if created == 0:
                self.report({'WARNING'}, T("mhwi.operators.facial_ref_empty").format(bone=head_name))
                return {'CANCELLED'}
        finally:
            # 参考骨架只用来取移植数据，用完即清除
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            ref_data = ref_arm_obj.data
            if ref_arm_obj.name in bpy.data.objects:
                bpy.data.objects.remove(ref_arm_obj, do_unlink=True)
            if ref_data.users == 0:
                bpy.data.armatures.remove(ref_data)

        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_arm.select_set(True)

        self.report({'INFO'}, T("core.facial_bones.facial_bones_added").format(n=created))
        return {'FINISHED'}


def _is_head_ancestor(arm_obj, bone_name, head_name):
    """bone_name 是否在 head_name 的祖先链上（只对齐 脊柱→头 这一段，不碰面部）。"""
    head = arm_obj.data.bones.get(head_name)
    p = head.parent if head else None
    while p is not None:
        if p.name == bone_name:
            return True
        p = p.parent
    return False


# 注册所有类
classes = [
    MHWI_OT_AddFacialBones,
    MHWI_OT_AlignNonPhysics,
    MHWI_OT_AutoCreateChains,
    MHWI_RegionAssignment,
    MHWI_OT_SplitPhysicsBones,
    MHWI_OT_BatchRenamePhysicsBones,
    MHWI_OT_SetMeshDisplayCondition,
    MHWI_OT_EndfieldFaceRename,
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
