import os
import re
import sys
import time
import bpy
from ...core.i18n import _
from ...core import weight_utils
from ...core.bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from ...core.re_chain_utils import (
    REChainConfig,
    _decompose_chains,
    _is_valid_chain_collection,
    _patch_chain_cleanup,
    _build_physics_bones_set,
    auto_create_re_chains,
)
from ...core.standard_ops import _run_bone_color_refresh

# ============================================================
# Endfield 面部顶点组改名 (Endfield → MHWilds)
# ============================================================

ENDFIELD_FACE_RENAME_MAP = [
    ("face_Head", "HeadAll_SCL"),
    ("browLf01Joint", "L_EyeBrow_A_LOD01"),
    ("browLf02Joint", "L_EyeBrow_B_LOD01"),
    ("browLf03Joint", "L_EyeBrow_B_LOD01"),
    ("browLf04Joint", "L_EyeBrow_B_LOD01"),
    ("browLf05Joint", "L_EyeBrow_C_LOD01"),
    ("browLineLfUp01Joint", "L_EyeBrow_A_LOD01"),
    ("browLineLfUp02Joint", "L_EyeBrow_B_LOD01"),
    ("browLineLfUp03Joint", "L_EyeBrow_C_LOD01"),
    ("browLineLf01Joint", "L_DoubleEyeLid_A_LOD00"),
    ("browLineLf02Joint", "L_DoubleEyeLid_LOD01"),
    ("browLineLf03Joint", "L_DoubleEyeLid_B_LOD00"),
    ("browRt01Joint", "R_EyeBrow_A_LOD01"),
    ("browRt02Joint", "R_EyeBrow_B_LOD01"),
    ("browRt03Joint", "R_EyeBrow_B_LOD01"),
    ("browRt04Joint", "R_EyeBrow_B_LOD01"),
    ("browRt05Joint", "R_EyeBrow_C_LOD01"),
    ("browLineRtUp01Joint", "R_EyeBrow_A_LOD01"),
    ("browLineRtUp02Joint", "R_EyeBrow_B_LOD01"),
    ("browLineRtUp03Joint", "R_EyeBrow_C_LOD01"),
    ("browLineRt01Joint", "R_DoubleEyeLid_A_LOD00"),
    ("browLineRt02Joint", "R_DoubleEyeLid_LOD01"),
    ("browLineRt03Joint", "R_DoubleEyeLid_B_LOD00"),
    ("faceLfIrisJoint", "L_EyeJ_LOD02"),
    ("faceLfHighlightJoint", "L_EyeJ_LOD02"),
    ("faceLfHighlightJointA", "L_EyeJ_LOD02"),
    ("faceLfHighlightJointB", "L_EyeJ_LOD02"),
    ("faceLfPupilJoint", "L_EyeJ_LOD02"),
    ("eyeLf01Joint", "L_InnerEyeJ_LOD02"),
    ("eyeLf01EyelashJoint", "L_UpEyeLid_A_LOD00"),
    ("eyeLf02Joint", "L_UpEyeLid_A_LOD00"),
    ("eyeLf02EyelashJoint", "L_UpEyeLid_A_LOD00"),
    ("eyeLf03Joint", "L_UpEyeLid_LOD01"),
    ("eyeLf03EyelashJoint", "L_UpEyeLid_LOD01"),
    ("eyeLf03IrissdJoint", "L_UpEyeLid_LOD01"),
    ("eyeLf04Joint", "L_UpEyeLid_B_LOD00"),
    ("eyeLf04EyelashJoint", "L_UpEyeLid_B_LOD00"),
    ("eyeLf05Joint", "L_OuterEyeJ_LOD02"),
    ("eyeLf05EyelashJoint", "L_UpEyeLid_B_LOD00"),
    ("eyeLf06Joint", "L_LoEyeLid_B_LOD00"),
    ("eyeLf07Joint", "L_LoEyeLid_LOD01"),
    ("eyeLf08Joint", "L_LoEyeLid_A_LOD00"),
    ("faceRtIrisJoint", "R_EyeJ_LOD02"),
    ("faceRtHighlightJoint", "R_EyeJ_LOD02"),
    ("faceRtHighlightJointA", "R_EyeJ_LOD02"),
    ("faceRtHighlightJointB", "R_EyeJ_LOD02"),
    ("faceRtPupilJoint", "R_EyeJ_LOD02"),
    ("eyeRt01Joint", "R_InnerEyeJ_LOD02"),
    ("eyeRt01EyelashJoint", "R_UpEyeLid_A_LOD00"),
    ("eyeRt02Joint", "R_UpEyeLid_A_LOD00"),
    ("eyeRt02EyelashJoint", "R_UpEyeLid_A_LOD00"),
    ("eyeRt03Joint", "R_UpEyeLid_LOD01"),
    ("eyeRt03EyelashJoint", "R_UpEyeLid_LOD01"),
    ("eyeRt03IrissdJoint", "R_UpEyeLid_LOD01"),
    ("eyeRt04Joint", "R_UpEyeLid_B_LOD00"),
    ("eyeRt04EyelashJoint", "R_UpEyeLid_B_LOD00"),
    ("eyeRt05Joint", "R_OuterEyeJ_LOD02"),
    ("eyeRt05EyelashJoint", "R_UpEyeLid_B_LOD00"),
    ("eyeRt06Joint", "R_LoEyeLid_B_LOD00"),
    ("eyeRt07Joint", "R_LoEyeLid_LOD01"),
    ("eyeRt08Joint", "R_LoEyeLid_A_LOD00"),
    ("NoseMd01Joint", "C_Nose_LOD01"),
    ("lineJoint", "HeadAll_SCL"),
    ("faceMdToothUpJoint", "UpperTeeth"),
    ("line_toothJoint", "UpperTeeth"),
    ("faceMdToothDnJoint", "LowerTeeth"),
    ("TongueMd04Joint", "C_TongueC_LOD01"),
    ("TongueMd03Joint", "C_TongueB_LOD01"),
    ("TongueMd02Joint", "C_TongueB_LOD01"),
    ("TongueMd01Joint", "C_TongueA_LOD01"),
    ("lipLdn1Joint", "L_cornerLip_B_LOD01"),
    ("lipLdn2Joint", "L_loLip_BT_LOD00"),
    ("lipLdn3Joint", "L_loLip_T_LOD01"),
    ("lipLdn4Joint", "L_loLip_AT_LOD00"),
    ("lipMdnJoint", "C_loLip_T_LOD01"),
    ("lipRdn1Joint", "R_cornerLip_B_LOD01"),
    ("lipRdn2Joint", "R_loLip_BT_LOD00"),
    ("lipRdn3Joint", "R_loLip_T_LOD01"),
    ("lipRdn4Joint", "R_loLip_AT_LOD00"),
    ("lipLup1Joint", "L_cornerLip_B_LOD01"),
    ("lipLup2Joint", "L_upLip_BT_LOD00"),
    ("lipLup3Joint", "L_upLip_T_LOD01"),
    ("lipLup4Joint", "L_upLip_AT_LOD00"),
    ("lipMupJoint", "C_upLip_T_LOD01"),
    ("lipRup1Joint", "R_cornerLip_B_LOD01"),
    ("lipRup2Joint", "R_upLip_BT_LOD00"),
    ("lipRup3Joint", "R_upLip_T_LOD01"),
    ("lipRup4Joint", "R_upLip_AT_LOD00"),
    ("faceMdJawDnJoint", "C_Chin_LOD01"),
    ("faceLfCheekOtDnJoint", "L_JawLine_LOD01"),
    ("faceLfCheekOtInJoint", "L_malarFat_B_LOD01"),
    ("faceLfCheekOtJoint", "L_Cheek_LOD02"),
    ("faceLfCheekOtUpJoint", "L_CheekBone_LOD02"),
    ("faceRtCheekOtDnJoint", "R_JawLine_LOD01"),
    ("faceRtCheekOtInJoint", "R_malarFat_B_LOD01"),
    ("faceRtCheekOtJoint", "R_Cheek_LOD02"),
    ("faceRtCheekOtUpJoint", "R_CheekBone_LOD02"),
]




class MHWS_OT_EndfieldFaceRename(bpy.types.Operator):
    """将 Endfield 面部顶点组名称批量转换为 MHWilds 格式"""
    bl_idname = "mhws.endfield_face_rename"
    bl_label = "Endfield 面部改名"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)
    
    def execute(self, context):
        total = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for old_name, new_name in ENDFIELD_FACE_RENAME_MAP:
                if weight_utils.rename_or_merge_vgroup(obj, old_name, new_name):
                    total += 1
        self.report({'INFO'}, _("已处理 %d 个面部顶点组") % total)
        return {'FINISHED'}


# ============================================================
# 面部权重简化 (通用)
# ============================================================



def _transfer_partial(obj, source_names, targets_with_ratios):
    """从源顶点组按比例分配权重到多个目标，源保留剩余"""
    total_ratio = sum(r for __, r in targets_with_ratios)
    remain_ratio = 1.0 - total_ratio

    target_vgs = []
    for tgt_name, ratio in targets_with_ratios:
        tgt_vg = obj.vertex_groups.get(tgt_name)
        if tgt_vg is None:
            tgt_vg = obj.vertex_groups.new(name=tgt_name)
        target_vgs.append((tgt_vg, ratio))

    for src_name in source_names:
        src_vg = obj.vertex_groups.get(src_name)
        if src_vg is None:
            continue
        for vert in obj.data.vertices:
            try:
                src_w = src_vg.weight(vert.index)
            except RuntimeError:
                continue
            if src_w <= 0.0:
                continue
            for tgt_vg, ratio in target_vgs:
                try:
                    tgt_w = tgt_vg.weight(vert.index)
                except RuntimeError:
                    tgt_w = 0.0
                tgt_vg.add([vert.index], min(tgt_w + src_w * ratio, 1.0), 'REPLACE')
            src_vg.add([vert.index], src_w * remain_ratio, 'REPLACE')


class MHWS_OT_FaceWeightSimplify(bpy.types.Operator):
    """简化面部权重: 将 MHWilds 格式的细分面部骨骼权重合并到主要骨骼上"""
    bl_idname = "mhws.face_weight_simplify"
    bl_label = "面部权重简化"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        
        # 1. 合并到 Head
        weight_utils.merge_vgroups_multi(obj, [
            "L_malarFat_B_LOD01", "R_malarFat_B_LOD01",
            "L_CheekBone_LOD02", "R_CheekBone_LOD02",
            "C_Nose_LOD01", "C_TongueA_LOD01",
            "UpperTeeth", "HeadAll_SCL",
        ], "Head")
        
        # 2. 合并到 C_Chin_LOD01
        weight_utils.merge_vgroups_multi(obj, [
            "L_JawLine_LOD01", "R_JawLine_LOD01",
            "L_Cheek_LOD02", "R_Cheek_LOD02",
            "C_TongueB_LOD01", "C_TongueC_LOD01",
            "LowerTeeth",
        ], "C_Chin_LOD01")
        
        # 3. 下眼睑 60% -> 主骨骼
        _transfer_partial(obj, ["L_LoEyeLid_B_LOD00", "L_LoEyeLid_A_LOD00"],
                          [("L_LoEyeLid_LOD01", 0.6)])
        _transfer_partial(obj, ["R_LoEyeLid_B_LOD00", "R_LoEyeLid_A_LOD00"],
                          [("R_LoEyeLid_LOD01", 0.6)])
        
        # 4. 上眼睑 60% -> 主骨骼
        _transfer_partial(obj, ["R_UpEyeLid_B_LOD00", "R_UpEyeLid_A_LOD00"],
                          [("R_UpEyeLid_LOD01", 0.6)])
        _transfer_partial(obj, ["L_UpEyeLid_B_LOD00", "L_UpEyeLid_A_LOD00"],
                          [("L_UpEyeLid_LOD01", 0.6)])
        
        # 5. 眉毛 60% -> 主骨骼
        _transfer_partial(obj, ["R_EyeBrow_A_LOD01", "R_EyeBrow_C_LOD01"],
                          [("R_EyeBrow_B_LOD01", 0.6)])
        _transfer_partial(obj, ["L_EyeBrow_A_LOD01", "L_EyeBrow_C_LOD01"],
                          [("L_EyeBrow_B_LOD01", 0.6)])
        
        # 6. 双眼皮 60% -> 主骨骼
        _transfer_partial(obj, ["L_DoubleEyeLid_A_LOD00", "L_DoubleEyeLid_LOD01"],
                          [("L_DoubleEyeLid_B_LOD00", 0.6)])
        _transfer_partial(obj, ["R_DoubleEyeLid_A_LOD00", "R_DoubleEyeLid_LOD01"],
                          [("R_DoubleEyeLid_B_LOD00", 0.6)])
        
        # 7. 下嘴唇
        _transfer_partial(obj, ["L_loLip_AT_LOD00"], [("L_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["L_loLip_BT_LOD00"],
                          [("L_loLip_T_LOD01", 0.3), ("L_cornerLip_B_LOD01", 0.3)])
        _transfer_partial(obj, ["R_loLip_AT_LOD00"], [("R_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_loLip_BT_LOD00"],
                          [("R_loLip_T_LOD01", 0.3), ("R_cornerLip_B_LOD01", 0.3)])
        
        # 8. 上嘴唇
        _transfer_partial(obj, ["L_upLip_AT_LOD00"], [("L_upLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["L_upLip_BT_LOD00"],
                          [("L_upLip_T_LOD01", 0.3), ("L_cornerLip_B_LOD01", 0.3)])
        _transfer_partial(obj, ["R_upLip_AT_LOD00"], [("R_upLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_upLip_BT_LOD00"],
                          [("R_upLip_T_LOD01", 0.3), ("R_cornerLip_B_LOD01", 0.3)])
        
        # 9. 左右唇 60% -> 中央唇
        _transfer_partial(obj, ["R_loLip_T_LOD01", "L_loLip_T_LOD01"],
                          [("C_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_upLip_T_LOD01", "L_upLip_T_LOD01"],
                          [("C_upLip_T_LOD01", 0.6)])
        
        self.report({'INFO'}, _("面部权重简化完成"))
        return {'FINISHED'}


# ============================================================
# 一键创建 RE Chain（实验性）
# ============================================================

# invoke 时动态填充，供 EnumProperty 回调使用
_chain_col_items = []


def _get_chain_col_items(self, context):
    return _chain_col_items


_MHWS_TUNING = {
    'calculateMode': '3', 'chainAttrFlags': '4',
    'calculateStepTime': 2.0, 'modelCollisionSearch': 1,
    'highFPSCalculateMode': '2',
    'wilds_unkn1': 1, 'wilds_unkn2': 1,
}


class MHWS_OT_AutoCreateChains(bpy.types.Operator):
    """一键创建 RE Chain。支持自动创建集合 + MHWilds 特调 Header。"""
    bl_idname = "mhws.auto_create_chains"
    bl_label = "一键创建 RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="选择要写入的 Chain Collection",
        items=_get_chain_col_items,
    )
    settings_mode: bpy.props.EnumProperty(
        name="Settings 模式",
        items=[
            ('SEPARATE', "各自独立", "每条链拥有独立的 Chain Settings"),
            ('SHARED',   "共享同一", "所有链共用同一个 Chain Settings"),
            ('GUESS',    "猜测分组", "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组"),
        ],
        default='SHARED',
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="自动创建集合",
        description="勾选后自动创建 Chain Collection 及 Header，无需预先手动准备",
        default=False,
    )
    collection_name: bpy.props.StringProperty(
        name="集合名称",
        description="新创建的 Chain Collection 名称（不含扩展名）",
        default="",
    )
    chain_format: bpy.props.EnumProperty(
        name="Chain 格式",
        items=[
            (".chain", "Chain", "旧格式，用于 RE4 等早期游戏"),
            (".chain2", "Chain2", "新格式，用于 MHWilds / RE9"),
        ],
        default='.chain2',
    )
    apply_mhwilds_tuning: bpy.props.BoolProperty(
        name="使用荒野特调Header",
        description="将 Header 参数覆盖为 MHWilds 校准值（calculateMode=Quality 等）",
        default=False,
    )
    straighten_orientation: bpy.props.BoolProperty(
        name="骨骼方向预处理",
        description="创建前将所有物理骨骼调整为竖直向上、扭转归零",
        default=False,
    )
    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="直接创建（自动刷新骨骼颜色）",
        description="先自动运行骨骼颜色刷新，再尝试创建",
        default=False,
    )
    apply_angle_ramp: bpy.props.BoolProperty(
        name="自动应用角度坡度",
        description="链创建完成后自动调用 apply_angle_limit_ramp（最大60°，4级梯度）",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE'
                and context.active_object is not None
                and context.active_object.type == 'ARMATURE'
                and hasattr(bpy.ops, 're_chain')
                and hasattr(bpy.ops.re_chain, 'create_chain_settings'))

    def invoke(self, context, event):
        arm = context.active_object
        self.has_no_markers = not any(
            pb.get("chain_role") in ("head", "branch_head")
            for pb in (arm.pose.bones if arm and arm.type == 'ARMATURE' else [])
        )

        global _chain_col_items
        _chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]

        # 预填集合名称：取骨架所属 mod3 集合名
        if not self.collection_name:
            col_name = context.scene.get("REMeshLastImportedCollection", "")
            if col_name and ".mesh" in col_name:
                self.collection_name = col_name.split(".mesh")[0]

        # 预选当前 RE Chain 面板已设置的集合
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _chain_col_items):
                self.chain_collection = cur

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        if self.has_no_markers:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text=_("当前骨架没有任何标记！"), icon='ERROR')
            col.label(text=_("建议先使用物理链工具手动标记后再使用此功能。"))
            layout.prop(self, "auto_refresh")
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text="自动创建集合")
        if self.auto_create_collection:
            layout.prop(self, "collection_name")
            layout.prop(self, "chain_format", expand=True)
            if self.chain_format == '.chain2':
                layout.prop(self, "apply_mhwilds_tuning")
        else:
            layout.prop(self, "chain_collection")
        layout.prop(self, "settings_mode", expand=True)
        layout.prop(self, "straighten_orientation")
        layout.prop(self, "apply_angle_ramp")

    def execute(self, context):
        armature = context.active_object
        if self.has_no_markers:
            if not self.auto_refresh:
                return {'CANCELLED'}
            ok, msg = _run_bone_color_refresh(context, armature)
            if not ok:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}

        config = REChainConfig(
            chain_format=self.chain_format,
            chain_file_type="chain2",
            auto_create_collection=self.auto_create_collection,
            collection_name=self.collection_name,
            tuning=_MHWS_TUNING if (self.auto_create_collection and self.apply_mhwilds_tuning) else None,
            settings_mode=self.settings_mode,
            selected_collection=self.chain_collection,
            straighten_orientation=self.straighten_orientation,
            collider_filter_path="System/Collision/Filter/Character/Character_Chain.cfil",
        )

        armature = context.active_object
        status = auto_create_re_chains(context, armature, config)

        if status == {'CANCELLED'}:
            self.report({'ERROR'}, _("创建 RE Chain 失败"))
            return {'CANCELLED'}

        if self.apply_angle_ramp:
            try:
                context.view_layer.objects.active = armature
                armature.select_set(True)
                if context.mode != 'POSE':
                    bpy.ops.object.mode_set(mode='POSE')
                bpy.ops.re_chain.apply_angle_limit_ramp(
                    maxAngleLimit=1.047198, maxIteration=4)
            except Exception as e:
                self.report({'WARNING'}, _("角度坡度应用失败，请在 RE Chain Editor 中手动设置") + f": {e}")

        self.report({'INFO'}, _("RE Chain 创建完成"))
        return {'FINISHED'}


# ============================================================
# 一键导入并对齐荒野模型 (MHWs)
# ============================================================

_PREPROCESS_X_CANDIDATES = ("MMD.json", "VRChat.json")
_PREPROCESS_MIN_RATIO = 0.30
_PREPROCESS_REF_ARM_PATTERN = re.compile(r"^MHWilds_Female Armature(?:\.(\d+))?$")
_PREPROCESS_REF_ARM_BONES = (
    "L_UpperArm", "R_UpperArm",
    "L_Forearm",  "R_Forearm",
    "L_Hand",     "R_Hand",
)
_PREPROCESS_ARM_SLOTS = (
    "upperarm_L", "upperarm_R",
    "forearm_L",  "forearm_R",
    "hand_L",     "hand_R",
)
_PREPROCESS_Y_PRESET = "怪猎荒野.json"


def _detect_source_preset(source_arm_obj):
    """Check MMD.json / VRChat.json coverage; return filename or None."""
    from ...core.ui_config import OPTIONAL_BONES
    best_preset = None
    best_ratio = 0.0
    for filename in _PREPROCESS_X_CANDIDATES:
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x=True):
            continue
        total = matched = 0
        for std_key in STANDARD_BONE_NAMES:
            if std_key in OPTIONAL_BONES:
                continue
            total += 1
            main, _ = mapper.get_matches_for_standard(source_arm_obj, std_key)
            if main:
                matched += 1
        if total == 0:
            continue
        ratio = matched / total
        if ratio > best_ratio:
            best_ratio = ratio
            best_preset = filename
    return best_preset if best_ratio >= _PREPROCESS_MIN_RATIO else None


def _find_latest_mhwilds_armature():
    """Return the highest-suffixed 'MHWilds_Female Armature[.NNN]' object."""
    best_obj = None
    best_num = -1
    for obj in bpy.data.objects:
        if obj.type != 'ARMATURE':
            continue
        m = _PREPROCESS_REF_ARM_PATTERN.match(obj.name)
        if m:
            num = int(m.group(1)) if m.group(1) else 0
            if num > best_num:
                best_num = num
                best_obj = obj
    return best_obj


def _calc_arm_scale(source_arm_obj, ref_arm_obj, detected_preset):
    """Return source/reference arm-bone average world-Z ratio."""
    mw_ref = ref_arm_obj.matrix_world
    ref_z = [
        (mw_ref @ ref_arm_obj.pose.bones[n].head).z
        for n in _PREPROCESS_REF_ARM_BONES
        if ref_arm_obj.pose.bones.get(n)
    ]

    mapper = BoneMapManager()
    mapper.load_preset(detected_preset, is_import_x=True)
    mw_src = source_arm_obj.matrix_world
    src_z = []
    for slot in _PREPROCESS_ARM_SLOTS:
        main_name, _ = mapper.get_matches_for_standard(source_arm_obj, slot)
        if main_name and source_arm_obj.pose.bones.get(main_name):
            src_z.append((mw_src @ source_arm_obj.pose.bones[main_name].head).z)

    if not ref_z or not src_z:
        return 1.0
    return (sum(ref_z) / len(ref_z)) / (sum(src_z) / len(src_z))


def _calc_y_offset(source_arm_obj, ref_arm_obj, detected_preset):
    """Return mean(ref_y) - mean(src_y) using arm-bone world-Y positions."""
    mw_ref = ref_arm_obj.matrix_world
    ref_y = [
        (mw_ref @ ref_arm_obj.pose.bones[n].head).y
        for n in _PREPROCESS_REF_ARM_BONES
        if ref_arm_obj.pose.bones.get(n)
    ]

    mapper = BoneMapManager()
    mapper.load_preset(detected_preset, is_import_x=True)
    mw_src = source_arm_obj.matrix_world
    src_y = []
    for slot in _PREPROCESS_ARM_SLOTS:
        main_name, _ = mapper.get_matches_for_standard(source_arm_obj, slot)
        if main_name and source_arm_obj.pose.bones.get(main_name):
            src_y.append((mw_src @ source_arm_obj.pose.bones[main_name].head).y)

    if not ref_y or not src_y:
        return 0.0
    return (sum(ref_y) / len(ref_y)) - (sum(src_y) / len(src_y))


class MHWS_OT_PreprocessModel(bpy.types.Operator):
    """自动识别 MMD/VRChat → 姿态校正 → 导入参考骨架 → 缩放/Y轴偏移校准 → 骨架对齐"""
    bl_idname = "mhws.preprocess_model"
    bl_label = "一键导入并对齐荒野模型"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            hasattr(bpy.ops, 'mbt') and hasattr(bpy.ops.mbt, 'import_mhwilds_fmesh')
            and context.active_object is not None
            and context.active_object.type == 'ARMATURE'
        )

    def execute(self, context):
        settings = context.scene.mhw_suite_settings

        source_arm_obj = context.active_object
        if not source_arm_obj or source_arm_obj.type != 'ARMATURE':
            self.report({'WARNING'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        # Step 1: auto-detect X preset (MMD / VRChat only)
        detected = _detect_source_preset(source_arm_obj)
        if detected is None:
            self.report({'WARNING'}, _("目前该功能只适用于MMD和VRChat模型！"))
            return {'CANCELLED'}

        settings.import_preset_enum = detected
        settings.pose_import_preset_enum = detected
        settings.target_preset_enum = _PREPROCESS_Y_PRESET

        # Step 2: MMD only — 方向计算
        if detected == "MMD.json":
            bpy.ops.object.select_all(action='DESELECT')
            source_arm_obj.select_set(True)
            context.view_layer.objects.active = source_arm_obj
            bpy.ops.modder.tpose_direction()

        # Step 3: import reference skeleton + arm-scale calibration
        mbt_panel = context.scene.mbt_toolpanel
        mbt_panel.mhwilds_convert_to_tpose = True
        mbt_panel.mhwilds_merge_facial_bones = True
        bpy.ops.mbt.import_mhwilds_fmesh()
        ref_arm_obj = _find_latest_mhwilds_armature()

        scale = _calc_arm_scale(source_arm_obj, ref_arm_obj, detected)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        source_arm_obj.select_set(True)
        context.view_layer.objects.active = source_arm_obj
        bpy.ops.transform.resize(value=(scale, scale, scale))
        bpy.ops.object.transform_apply(scale=True)

        # Step 4: Y-axis offset alignment
        context.view_layer.update()
        dy = _calc_y_offset(source_arm_obj, ref_arm_obj, detected)
        if abs(dy) > 1e-4:
            source_arm_obj.location.y += dy
            bpy.ops.object.select_all(action='DESELECT')
            source_arm_obj.select_set(True)
            for child in source_arm_obj.children:
                if child.type == 'MESH':
                    child.select_set(True)
            context.view_layer.objects.active = source_arm_obj
            bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

        # Step 5: skeleton alignment (source selected, ref as active)
        bpy.ops.object.select_all(action='DESELECT')
        source_arm_obj.select_set(True)
        ref_arm_obj.select_set(True)
        context.view_layer.objects.active = ref_arm_obj
        bpy.ops.modder.universal_snap()

        self.report({'INFO'}, _("模型预处理完成"))
        return {'FINISHED'}


# ============================================================
# 身体权重转移至辅助权重 (HJ bones)
# ============================================================

# Pairs of (base_bone, hj_bone). For each pair where the HJ bone exists:
#   1. Translate the HJ bone so its head aligns with the base bone's head.
#   2. Rename the base bone's vertex group to the HJ bone's name.
_HJ_BONE_PAIRS = [
    ("Neck_1",     "Neck_1_HJ_00"),
    ("Neck_0",     "Neck_0_HJ_00"),
    ("L_Shoulder", "L_Shoulder_HJ_00"),
    ("R_Shoulder", "R_Shoulder_HJ_00"),
    ("Spine_2",    "Spine_2_HJ_00"),
    ("Spine_1",    "Spine_1_HJ_00"),
    ("Spine_0",    "Spine_0_HJ_00"),
    ("L_Knee",     "L_Knee_HJ_00"),
    ("R_Knee",     "R_Knee_HJ_00"),
    ("Hip",        "Hip_HJ_00"),
]


class MHWS_OT_BodyWeightToHJ(bpy.types.Operator):
    """将身体权重转移至对应的辅助权重，通常来讲，这样会让这些部位的运动拥有更自然的表现"""
    bl_idname = "mhws.body_weight_to_hj"
    bl_label = "身体权重转移至辅助权重"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object

        # --- Step 1: align HJ bone positions in edit mode ---
        if context.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = arm_obj.data.edit_bones
        active_pairs = []  # pairs where HJ bone actually exists

        for base_name, hj_name in _HJ_BONE_PAIRS:
            base_bone = edit_bones.get(base_name)
            hj_bone = edit_bones.get(hj_name)
            if base_bone is None or hj_bone is None:
                continue
            # Translate HJ bone so head coincides with base bone head.
            offset = base_bone.head - hj_bone.head
            hj_bone.tail = hj_bone.tail + offset
            hj_bone.head = base_bone.head.copy()
            active_pairs.append((base_name, hj_name))

        bpy.ops.object.mode_set(mode='OBJECT')

        if not active_pairs:
            self.report({'INFO'}, "未找到任何 HJ 辅助骨骼，无操作")
            return {'FINISHED'}

        # --- Step 2: rename vertex groups on all bound meshes ---
        mesh_objects = [
            o for o in bpy.data.objects
            if o.type == 'MESH'
            and any(m.type == 'ARMATURE' and m.object == arm_obj for m in o.modifiers)
        ]

        renamed = 0
        for obj in mesh_objects:
            for base_name, hj_name in active_pairs:
                if weight_utils.rename_or_merge_vgroup(obj, base_name, hj_name):
                    renamed += 1

        self.report(
            {'INFO'},
            f"完成：{len(active_pairs)} 根 HJ 骨骼已对齐，{renamed} 个顶点组已重命名"
        )
        return {'FINISHED'}


classes = [
    MHWS_OT_EndfieldFaceRename,
    MHWS_OT_FaceWeightSimplify,
    MHWS_OT_AutoCreateChains,
    MHWS_OT_PreprocessModel,
    MHWS_OT_BodyWeightToHJ,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)