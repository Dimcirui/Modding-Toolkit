import sys
import time
import bpy
import re
from ...core.i18n import T
from ...core import (bone_utils, facial_bones, facial_maps, fork_resolver, preprocess_align,
                     ref_model_ops, ref_skeleton, weight_utils)
from ...core.bone_mapper import BoneMapManager, auto_detect_preset, resolve_preset
from ...core.mhwi_port import SOLE_OFFSET_Z
from ...core.standard_ops import _build_fuzzy_preset_bones, _run_bone_color_refresh, _slot_text
from ...core import mhwi_physics_budget
from . import physics_split
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
# 1.5 一键导入并对齐 MHWI 模型
# ==========================================
class MHWI_OT_PreprocessModel(bpy.types.Operator):
    """The MHWS one-click flow, with the reference first moved onto the ground.

    ``mhws.preprocess_model`` scales the source by the ratio of the two rigs' arm heights
    in *world Z*.  That only means something when both stand on z=0, and MHWI's reference
    does not: its origin is the pelvis, 1.0468 m above the sole (``SOLE_OFFSET_Z`` -- the
    same constant the MHWI -> MHWS port lifts its models by).  So the reference goes up by
    that much, the Wilds steps run unchanged, and both rigs come back down together.
    """
    bl_idname = "mhwi.preprocess_model"
    bl_label = "One-Click Import & Align MHWI Model"
    bl_options = {'REGISTER', 'UNDO'}

    male: bpy.props.BoolProperty(
        name="Male Reference",
        description="Align to the male hunter body instead of the female one",
        default=False,
    )

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.operators.preprocess_model_desc")

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'ARMATURE')

    @staticmethod
    def _select(context, *objs):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        context.view_layer.objects.active = objs[-1]

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        source = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 1. which preset is the source (MMD / VRChat only)
        detected = preprocess_align.detect_source_preset(source)
        if detected is None:
            self.report({'WARNING'}, T("mhws.operators.mmd_vrchat_only"))
            return {'CANCELLED'}
        settings.import_preset_enum = detected
        settings.pose_import_preset_enum = detected

        # 2. MMD stands in A-pose; the reference is a T-pose rig
        if detected == "MMD.json":
            self._select(context, source)
            bpy.ops.modder.mmd_a_to_tpose()

        # 3. import the reference (MHWI's is natively T-pose, and has no facial bones to
        #    merge), then put its soles on z=0 so the world-Z comparison below is fair
        model = "male" if self.male else "female"
        ok, reason = ref_model_ops.model_available("MHWI", model)
        if not ok:
            self.report({'ERROR'}, T(reason))
            return {'CANCELLED'}
        ref = ref_model_ops.import_model("MHWI", model)
        if ref is None:
            self.report({'ERROR'}, T("core.ref_model_ops.import_failed"))
            return {'CANCELLED'}
        ref_z0 = ref.location.z
        ref.location.z = ref_z0 + SOLE_OFFSET_Z
        context.view_layer.update()

        y_preset = auto_detect_preset(ref, False, prefer_game="MHWI")
        if y_preset is None:
            self.report({'WARNING'}, T("mhwi.operators.no_mhwi_preset_detected"))
            ref.location.z = ref_z0
            return {'CANCELLED'}
        settings.target_preset_enum = y_preset

        # 4. scale so the arms stand at the same height.  Setting the object scale is what
        #    ``transform.resize`` does to a lone selected object, without needing a 3D
        #    view to run in.  Applying it afterwards is what the Wilds flow does -- note
        #    that ``transform_apply`` also bakes location and rotation by default.
        scale = preprocess_align.arm_scale(source, ref, detected, y_preset)
        self._select(context, source)
        source.scale = tuple(c * scale for c in source.scale)
        bpy.ops.object.transform_apply(scale=True)

        # 5. Y offset
        context.view_layer.update()
        dy = preprocess_align.arm_offset_y(source, ref, detected, y_preset)
        if abs(dy) > 1e-4:
            source.location.y += dy
            self._select(context, *[c for c in source.children if c.type == 'MESH'], source)
            bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

        # 6. skeleton alignment: source selected, reference active
        self._select(context, source, ref)
        bpy.ops.modder.universal_snap()

        # 7. both back down.  The reference returns to exactly where it was imported; the
        #    source follows by the same amount so the two stay aligned.
        ref.location.z = ref_z0
        source.location.z -= SOLE_OFFSET_Z
        self._select(context, *[c for c in source.children if c.type == 'MESH'], source)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        self._select(context, source, ref)

        self.report({'INFO'}, T("mhws.operators.preprocess_done"))
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


# 部位分配选项
_SLOT_ITEMS = [
    ('body', "body", ""),
    ('arm',  "arm",  ""),
    ('wst',  "wst",  ""),
    ('leg',  "leg",  ""),
]

_MHBONE_RE = re.compile(r"^MhBone_(\d+)$")


def _is_tail_bone(bone, physics_bones_set):
    """尾骨骼：在物理骨集合中没有物理子骨的骨骼（即链末端）。"""
    return not any(c.name in physics_bones_set for c in bone.children)


def _mhbone_id(name):
    m = _MHBONE_RE.match(name)
    return int(m.group(1)) if m else None


def _in_ranges(idx, ranges):
    return any(a <= idx <= b for a, b in ranges)


def _rename_batches(armature, physics, rule):
    """按编号规则把物理骨分成 [(骨名序列, 编号范围), ...]。

    *rule* 为 ``'BODY'``：全部进 300–511。``'SLOT'``（不装插件的 arm / wst / leg）：非末端
    进 150–199——只有这一段有物理；末端放哪都行，只要不占 150–199，先 200–249 再 300–511。"""
    budget = mhwi_physics_budget
    if rule == 'BODY':
        return [(list(physics), budget.BODY_IDS)]
    ps = set(physics)
    bones = armature.data.bones
    non_tail = [n for n in physics if not _is_tail_bone(bones[n], ps)]
    tail = [n for n in physics if _is_tail_bone(bones[n], ps)]
    return [(non_tail, budget.SLOT_PHYSICS_IDS), (tail, budget.SLOT_TAIL_IDS)]


def _plan_renumber(armature, batches):
    """给每批骨分配编号，返回 [(旧名, 新名或 None), ...]。

    只有**不参与这次改名**的 MhBone 才算占用编号（本体骨，比如参考骨架自带的 249–253）；
    这次要改的骨不管现在叫什么都会让出编号。若按批次各算各的占用，某根尾骨此刻恰好叫
    MhBone_150，改非末端时 150 就会被当成占用跳过，白白少一个有物理的编号。"""
    renaming = {n for names, _r in batches for n in names}
    used = {i for i in (_mhbone_id(b.name) for b in armature.data.bones
                        if b.name not in renaming) if i is not None}
    out = []
    for names, ranges in batches:
        free = (i for a, b in ranges for i in range(a, b + 1) if i not in used)
        for n in names:
            new_id = next(free, None)
            if new_id is None:
                out.append((n, None))
            else:
                used.add(new_id)
                out.append((n, f"MhBone_{new_id:03d}"))
    return out


def _count_rename_failures(armature, batches):
    """预检：(成功数, 失败数)，不改名。"""
    plan = _plan_renumber(armature, batches)
    fail = sum(1 for _o, new in plan if new is None)
    return len(plan) - fail, fail


def _child_meshes(armature):
    """返回骨架的所有子级网格对象（递归，不要求已绑定为姿态修改器）。"""
    return [obj for obj in armature.children_recursive if obj.type == 'MESH']


def _rename_physics_bones(armature, batches):
    """按 *batches*（见 _rename_batches）把物理骨重命名为 MhBone_xxx，返回 (成功数, 失败数)。

    采用两步改名（临时名 → 正式名）避免同序列内的命名冲突：
    若直接逐一改名，前面的骨骼抢占了后面骨骼的当前名称对应的 ID，
    Blender 会自动给被顶替的骨骼追加 .001 后缀，导致后续查找失败。

    骨架子级网格若已绑定姿态（Armature）修改器指向本骨架，Blender 会在改名时
    自动同步其顶点组名；未绑定的子级网格不会被自动处理，因此这里对所有子级
    网格额外做一次同名顶点组的手动改名（已被自动同步的网格此时对应顶点组已
    不存在，手动步骤会直接跳过，不会重复处理或产生冲突）。
    """
    assignments = _plan_renumber(armature, batches)
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


def _slot_suffix(name):
    base = name[:-5] if name.endswith('.mod3') else name
    for slot in mhwi_physics_budget.SLOTS:
        if base.endswith('_' + slot):
            return slot
    return None


def _rename_rule(armature, physics, unlocked):
    """这副骨架用哪套编号：``'BODY'``（300–511）还是 ``'SLOT'``（不装插件的小部位）。

    1. 勾了解锁插件：一律 BODY。
    2. 已经有编号的看**非末端骨**的编号：有一根在 300 以上就是 BODY，都在 150–299 就是
       SLOT。只看非末端，因为不装插件时末端骨也可以放到 300+，看全部会把小部位误判成
       body，物理骨就会被编到没有物理的 300+ 上。
    3. 都还是原名（手动拆的骨架）：按骨架名后缀，_body 或没有后缀是 BODY，其余 SLOT。"""
    if unlocked:
        return 'BODY'
    ps = set(physics)
    bones = armature.data.bones
    ids = [i for i in (_mhbone_id(n) for n in physics if not _is_tail_bone(bones[n], ps))
           if i is not None]
    if any(i >= 300 for i in ids):
        return 'BODY'
    if any(150 <= i < 300 for i in ids):
        return 'SLOT'
    return 'SLOT' if _slot_suffix(armature.name) in ('arm', 'wst', 'leg') else 'BODY'


def _make_slot_name(original_name, slot):
    """生成带槽位后缀的骨架名，若含 .mod3 后缀则插在其前面。"""
    suffix = f"_{slot}"
    if original_name.endswith('.mod3'):
        return f"{original_name[:-5]}{suffix}.mod3"
    return f"{original_name}{suffix}"


def _duplicate_armature(source, new_name, collection):
    """复制骨架对象并重命名，放进 *collection*，返回新对象。

    不能和原骨架放在同一个集合：MHW Model Editor 按 .mod3 集合导出，集合里有两个骨架
    会报 MoreThanOneArmature。"""
    new_data = source.data.copy()
    new_obj = source.copy()
    new_obj.data = new_data
    new_obj.name = new_name
    new_data.name = new_name
    collection.objects.link(new_obj)
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


# 装了解锁插件时各区域（head / upper / lower）的去向，场景属性，供弹窗读写
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


#: invoke 算好的拆分规划，给弹窗 draw 用（draw 每帧都会调，不能重算权重）。键是骨架名。
_SPLIT_PREVIEW = {}

_REGION_LABEL = {
    "head": "mhwi.operators.region_head",
    "upper": "mhwi.operators.region_upper",
    "lower": "mhwi.operators.region_lower",
}


def _draw_split_packing(layout, plan, packing):
    box = layout.box()
    box.label(text=T("core.standard_ops.graft_budget_header").format(base=plan.base_bones))
    for slot in mhwi_physics_budget.SLOTS:
        nt, t = packing.used[slot]
        if not nt and not t and slot != "body":
            continue
        box.label(text=_slot_text(packing, slot), icon='CHECKMARK')
    if packing.overflow:
        names = T("mhwi.operators.list_sep").join(i.root for i in packing.overflow[:4])
        box.label(text=T("mhwi.operators.split_overflow").format(
            n=packing.overflow_bones, names=names), icon='ERROR')


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

    def _physics(self, armature):
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
            return None, None
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        return mapper, _collect_physics_bones(armature, preset_bones)

    @staticmethod
    def _region_slot(context):
        return {item.region: item.slot for item in context.scene.mhwi_region_assignments}

    def invoke(self, context, _event):
        armature = context.active_object
        mapper, physics = self._physics(armature)
        if mapper is None:
            return {'CANCELLED'}
        if not physics:
            self.report({'INFO'}, T("mhwi.operators.no_physics_bones_found"))
            return {'CANCELLED'}
        # 已经拆过的部位骨架（拆完又手动加了骨）：不再拆，只按该部位的规则重新编号。
        # 否则它总数 <=255 会走"直接重命名"，没装插件的 arm / wst / leg 会被编到没有
        # 物理的 300+ 上。
        if _slot_suffix(armature.name) is not None:
            unlocked = getattr(context.scene, "mhwi_physics_unlocked", False)
            rule = _rename_rule(armature, physics, unlocked)
            context.view_layer.objects.active = armature
            s, f = _rename_physics_bones(armature, _rename_batches(armature, physics, rule))
            self.report({'INFO'}, T("mhwi.operators.renumber_only").format(
                name=armature.name, success=s, fail=f))
            return {'FINISHED'}
        plan = physics_split.plan_split(armature, mapper, physics)
        _SPLIT_PREVIEW.clear()
        _SPLIT_PREVIEW[armature.name] = plan
        self.is_fast_path = len(armature.data.bones) <= 255

        assignments = context.scene.mhwi_region_assignments
        previous = {item.region: item.slot for item in assignments}
        assignments.clear()
        for region in physics_split.REGIONS:
            item = assignments.add()
            item.region = region
            item.bone_count = plan.region_totals[region]
            item.slot = previous.get(region, physics_split.DEFAULT_REGION_SLOT[region])
        return context.window_manager.invoke_props_dialog(
            self, width=440, title=T("ui.main_panel.btn_split_physics_bones"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if self.is_fast_path:
            layout.label(text=T("mhwi.operators.fast_path_prompt"))
            layout.prop(self, "fast_mode", expand=True)
            if self.fast_mode == 'DIRECT':
                return
            layout.separator()
        else:
            layout.label(text=T("mhwi.operators.over_255_prompt"))
        layout.prop(scene, "mhwi_physics_unlocked",
                    text=T("core.standard_ops.graft_unlocked_plugin"))
        plan = _SPLIT_PREVIEW.get(context.active_object.name)
        if plan is None:
            return
        unlocked = scene.mhwi_physics_unlocked
        if unlocked:
            layout.label(text=T("mhwi.operators.confirm_region_targets"))
            box = layout.box()
            row = box.row()
            row.label(text=T("mhwi.operators.col_region"))
            row.label(text=T("mhwi.operators.col_bone_count"))
            row.label(text=T("mhwi.operators.col_target_slot"))
            for item in scene.mhwi_region_assignments:
                row = box.row()
                row.label(text=T(_REGION_LABEL.get(item.region, item.region)))
                row.label(text=str(item.bone_count))
                row.prop(item, "slot", text="")
            layout.label(text=T("mhwi.operators.split_spare_note").format(
                slot=physics_split.SPARE_SLOT))
        else:
            layout.label(text=T("mhwi.operators.split_auto_pack"))
        packing = physics_split.pack(plan, unlocked, self._region_slot(context))
        _draw_split_packing(layout, plan, packing)

    def execute(self, context):
        armature = context.active_object
        mapper, physics = self._physics(armature)
        if mapper is None:
            return {'CANCELLED'}
        if not physics:
            self.report({'INFO'}, T("mhwi.operators.no_physics_bones_found"))
            return {'CANCELLED'}

        # 快速路径 + 直接重命名：一步到位
        if self.is_fast_path and self.fast_mode == 'DIRECT':
            context.view_layer.objects.active = armature
            batches = _rename_batches(armature, physics, 'BODY')
            s, f = _count_rename_failures(armature, batches)
            if f > 0:
                self.report({'ERROR'},
                    T("mhwi.operators.exceeds_bone_count").format(n=f))
                return {'CANCELLED'}
            success, fail = _rename_physics_bones(armature, batches)
            self.report({'INFO'}, T("mhwi.operators.rename_done").format(success=success, fail=fail))
            return {'FINISHED'}

        plan = physics_split.plan_split(armature, mapper, physics)
        unlocked = getattr(context.scene, "mhwi_physics_unlocked", False)
        packing = physics_split.pack(plan, unlocked, self._region_slot(context))
        if packing.overflow:
            names = T("mhwi.operators.list_sep").join(i.root for i in packing.overflow[:4])
            self.report({'ERROR'}, T("mhwi.operators.split_overflow").format(
                n=packing.overflow_bones, names=names))
            return {'CANCELLED'}
        slot_of_bone = physics_split.slot_of_bones(plan, packing)
        slots = mhwi_physics_budget.SLOTS
        used = sorted(set(slot_of_bone.values()) | {"body"}, key=slots.index)

        meshes = physics_split.child_meshes(armature)
        # 面的归属要在动骨架之前、按原始权重算
        face_slot = {m: physics_split.face_slots(m, slot_of_bone) for m in meshes}

        base_name = armature.name
        slot_arms, slot_cols, found_mod3 = {"body": armature}, {}, True
        for slot in used[1:]:
            cols, parent_of, ok = physics_split.make_slot_collections(context, armature, slot)
            found_mod3 = found_mod3 and ok
            slot_cols[slot] = (cols, parent_of)
            slot_arms[slot] = _duplicate_armature(
                armature, _make_slot_name(base_name, slot), cols.target_for(armature, parent_of))
        for slot, arm_obj in slot_arms.items():
            _delete_bones(context, arm_obj, [n for n in physics if slot_of_bone[n] != slot])

        moved = split = touched = 0
        for obj in meshes:
            fs = face_slot[obj]
            present = sorted(set(fs) or {"body"}, key=slots.index)
            keeper = "body" if "body" in present else present[0]
            for slot in present:
                if slot == keeper:
                    continue
                cols, parent_of = slot_cols[slot]
                copy = obj.copy()
                copy.data = obj.data.copy()
                cols.target_for(obj, parent_of).objects.link(copy)
                physics_split.retarget_mesh(copy, slot_arms[slot])
                physics_split.keep_faces(copy, [s == slot for s in fs])
                touched += physics_split.fold_foreign_weights(copy, slot, plan, slot_of_bone)
            if len(present) > 1:
                physics_split.keep_faces(obj, [s == keeper for s in fs])
                split += 1
            if keeper != "body":
                cols, parent_of = slot_cols[keeper]
                target = cols.target_for(obj, parent_of)
                for col in list(obj.users_collection):
                    col.objects.unlink(obj)
                target.objects.link(obj)
                physics_split.retarget_mesh(obj, slot_arms[keeper])
                moved += 1
            touched += physics_split.fold_foreign_weights(obj, keeper, plan, slot_of_bone)

        armature.name = _make_slot_name(base_name, 'body')
        armature.data.name = armature.name

        # 拆完直接重命名：每根骨属于哪个部位、用哪套编号，拆分自己最清楚，不用再从骨架名
        # 反推。容量检查已经保证编号够用。
        renamed = rename_fail = 0
        for slot, arm_obj in slot_arms.items():
            names = [n for n in physics if slot_of_bone[n] == slot]
            if not names:
                continue
            rule = 'BODY' if unlocked or slot == 'body' else 'SLOT'
            context.view_layer.objects.active = arm_obj
            s, f = _rename_physics_bones(arm_obj, _rename_batches(arm_obj, names, rule))
            renamed += s
            rename_fail += f
        context.view_layer.objects.active = armature

        self.report({'INFO'}, T("mhwi.operators.split_done").format(
            n=len(slot_arms), names=T("mhwi.operators.list_sep").join(slot_arms)))
        self.report({'WARNING'} if rename_fail else {'INFO'},
                    T("mhwi.operators.rename_done").format(success=renamed, fail=rename_fail))
        self.report({'INFO'}, T("mhwi.operators.split_mesh_summary").format(
            moved=moved, split=split, verts=touched))
        if not found_mod3:
            self.report({'WARNING'}, T("mhwi.operators.split_no_mod3"))
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
    def _count_failures_for_armature(mapper, arm_obj, unlocked=False):
        """预检单个骨架的失败数，但不实际改名。"""
        preset_bones = _build_fuzzy_preset_bones(mapper, arm_obj)
        physics = _collect_physics_bones(arm_obj, preset_bones)
        if not physics:
            return 0
        rule = _rename_rule(arm_obj, physics, unlocked)
        _, f = _count_rename_failures(arm_obj, _rename_batches(arm_obj, physics, rule))
        return f

    def invoke(self, context, _event):
        mapper = BoneMapManager()
        if not mapper.load_preset("mhwi_world.json", is_import_x=True):
            self.report({'ERROR'}, T("mhwi.operators.cannot_load_world_preset"))
            return {'CANCELLED'}

        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        total_fail = 0
        for arm_obj in armatures:
            total_fail += self._count_failures_for_armature(
                mapper, arm_obj, getattr(context.scene, "mhwi_physics_unlocked", False))

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

            rule = _rename_rule(arm_obj, physics,
                                getattr(context.scene, "mhwi_physics_unlocked", False))
            s, f = _rename_physics_bones(arm_obj, _rename_batches(arm_obj, physics, rule))
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
    MHWI_OT_PreprocessModel,
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
    # 游戏端的解锁插件：装了以后 arm / wst / leg 与 body 等同（300–512，各受 255 总数限制）。
    # 插件在游戏侧，Blender 里探测不到，只能由用户声明。移植的名额估算和拆分共用这一个值。
    bpy.types.Scene.mhwi_physics_unlocked = bpy.props.BoolProperty(
        name="Physics Unlock Plugin", default=False)

def unregister():
    del bpy.types.Scene.mhwi_physics_unlocked
    del bpy.types.Scene.mhwi_region_assignments
    del bpy.types.Scene.mhwi_body_capacity
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
