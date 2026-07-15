import os
import re
import sys
import time
import bpy
import mathutils
from ...core.i18n import _
from ...core import weight_utils
from ...core import bone_utils
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
            apply_angle_ramp=self.apply_angle_ramp,
        )

        armature = context.active_object
        status = auto_create_re_chains(context, armature, config)

        if status == {'CANCELLED'}:
            self.report({'ERROR'}, _("创建 RE Chain 失败"))
            return {'CANCELLED'}

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
def _detect_mhws_y_preset(ref_arm_obj=None):
    """Detect the MHWS bone (Y) preset filename.

    Primary:  scan presets/bone/ for the first JSON whose preset_info.game_code
              equals 'MHWS' (filename-agnostic, survives renames/translations).
    Fallback: coverage-based auto-detection against *ref_arm_obj* — the MHWS
              reference armature imported in Step 3 — requires ≥ 95 % coverage.
    Returns the filename string (e.g. "怪猎荒野.json"), or None on failure.
    """
    import json as _json
    from ...core.bone_mapper import auto_detect_preset

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bone_dir = os.path.join(root_dir, "assets", "presets", "bone")
    if os.path.isdir(bone_dir):
        for fname in sorted(os.listdir(bone_dir)):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(bone_dir, fname), encoding='utf-8') as fh:
                    data = _json.load(fh)
                if data.get('preset_info', {}).get('game_code') == 'MHWS':
                    return fname
            except Exception:
                continue

    # Fallback: coverage detection against the imported MHWS reference armature
    if ref_arm_obj is not None:
        return auto_detect_preset(ref_arm_obj, is_import_x=False)
    return None


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

        # Detect Y (bone) preset: game_code first, then coverage fallback
        y_preset = _detect_mhws_y_preset(ref_arm_obj)
        if y_preset is None:
            self.report({'WARNING'}, _("未能自动检测到荒野骨骼预设，请在面板中手动选择目标预设后重试"))
            return {'CANCELLED'}
        settings.target_preset_enum = y_preset

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
# 一键添加表情骨 (从原版荒野骨架移植表情骨到目标骨架)
# ============================================================

_FACIAL_ROOT_BONE = "HeadAll_SCL"
_BLINK_FAKE_OFFSET_Y = 0.05
_BLINK_TARGET_BONES = ("L_UpEyeLidJ_LOD02", "R_UpEyeLidJ_LOD02")

_facial_armature_cache = []


def _get_facial_armature_items(self, context):
    """骨架下拉框回调。保留全局引用防止 Blender 因 GC 出现野指针崩溃。"""
    global _facial_armature_cache
    _facial_armature_cache.clear()
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            _facial_armature_cache.append((obj.name, obj.name, ""))
    if not _facial_armature_cache:
        _facial_armature_cache.append(("NONE", _("无可用骨架"), ""))
    return _facial_armature_cache


def _collect_facial_subtree(ref_arm):
    """返回 (HeadAll_SCL 及其所有子级的骨骼名列表, HeadAll_SCL 原父级骨骼名)。"""
    root_bone = ref_arm.data.bones.get(_FACIAL_ROOT_BONE)
    if root_bone is None:
        return [], None
    names = [_FACIAL_ROOT_BONE] + [b.name for b in root_bone.children_recursive]
    parent_name = root_bone.parent.name if root_bone.parent else None
    return names, parent_name


def _graft_facial_bones(ref_arm, target_arm):
    """将 ref_arm 的 HeadAll_SCL 及其所有子级完整移植到 target_arm。

    直接照搬来源世界坐标下的 head/tail/roll（不做竖直化，也不加尾骨），
    并按来源层级关系重建父子链；HeadAll_SCL 本身挂到目标骨架中与来源同名的父级骨骼上。
    会先清除 target_arm 中已存在的同名旧骨骼。返回新建骨骼数。
    """
    subtree_names, root_parent_name = _collect_facial_subtree(ref_arm)
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
        if name == _FACIAL_ROOT_BONE:
            if root_parent_name and root_parent_name in edit_bones:
                eb.parent = edit_bones[root_parent_name]
        else:
            _h, _t, _r, p_name = src_data[name]
            if p_name and p_name in edit_bones:
                eb.parent = edit_bones[p_name]

    bpy.ops.object.mode_set(mode='OBJECT')
    return created


def _cleanup_ref_import(ref_arm_obj):
    """删除猎人模型网格及其所在的导入集合（通常是一个 "xxx.mesh" 集合），
    保留 ref_arm_obj 本体并将其重新挂到场景根集合，避免集合被清理后连同变成孤立对象。
    """
    ref_meshes = [
        o for o in bpy.data.objects
        if o.type == 'MESH'
        and (o.parent == ref_arm_obj
             or any(m.type == 'ARMATURE' and m.object == ref_arm_obj for m in o.modifiers))
    ]

    # 记录猎人模型/参考骨架所在的导入集合，供之后清理
    import_cols = set()
    for o in ref_meshes + [ref_arm_obj]:
        import_cols.update(o.users_collection)

    # 参考骨架先挂回场景根集合，确保它不随导入集合一起被清理掉
    scene_col = bpy.context.scene.collection
    if ref_arm_obj.name not in scene_col.objects:
        scene_col.objects.link(ref_arm_obj)
    for col in list(ref_arm_obj.users_collection):
        if col != scene_col:
            col.objects.unlink(ref_arm_obj)

    for mesh_obj in ref_meshes:
        bpy.data.objects.remove(mesh_obj, do_unlink=True)

    # 清理已变为空的导入集合（跳过场景根集合）
    for col in import_cols:
        if col == scene_col:
            continue
        if col.name in bpy.data.collections and len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)


def _apply_blink_fake_bone(arm_obj, bone_name):
    """假头法：在 bone_name(A) 与其父级(B) 之间插入一个从 B 原位复制出的假骨骼(B')，
    父子关系变为 B > B' > A，然后将 B' 与 A 一同沿 +Y (世界空间) 位移。
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
    local_offset = mat3.inverted() @ mathutils.Vector((0.0, _BLINK_FAKE_OFFSET_Y, 0.0))

    b_prime.head += local_offset
    b_prime.tail += local_offset
    a.head += local_offset
    a.tail += local_offset

    return True


class MHWS_OT_AddFacialBones(bpy.types.Operator):
    """将原版荒野骨架的表情骨骼移植到当前骨架，可选择使用假头法调整眨眼幅度"""
    bl_idname = "mhws.add_facial_bones"
    bl_label = "一键添加表情骨"
    bl_options = {'REGISTER', 'UNDO'}

    target_armature: bpy.props.EnumProperty(
        name="骨架",
        description="选择要添加表情骨的骨架",
        items=_get_facial_armature_items,
    )
    increase_blink_amplitude: bpy.props.BoolProperty(
        name="增加眨眼幅度（二次元模型用）",
        description="对上眼皮骨骼使用假头法，增大闭眼动作的形变幅度",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return (
            hasattr(bpy.ops, 'mbt') and hasattr(bpy.ops.mbt, 'import_mhwilds_fmesh')
            and any(o.type == 'ARMATURE' for o in bpy.data.objects)
        )

    def invoke(self, context, event):
        active = context.active_object
        if active and active.type == 'ARMATURE':
            self.target_armature = active.name
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        note = layout.row()
        note.active = False
        note.label(text=_("使用该功能将清除原本存在的表情骨！"))
        layout.separator()
        layout.prop(self, "target_armature")
        layout.prop(self, "increase_blink_amplitude")

    def execute(self, context):
        target_arm = bpy.data.objects.get(self.target_armature)
        if target_arm is None or target_arm.type != 'ARMATURE':
            self.report({'WARNING'}, _("请选择一个有效的骨架"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Step 1: 导入猎人骨架+模型（不合并表情骨）
        mbt_panel = context.scene.mbt_toolpanel
        mbt_panel.mhwilds_convert_to_tpose = True
        mbt_panel.mhwilds_merge_facial_bones = False
        bpy.ops.mbt.import_mhwilds_fmesh()
        ref_arm_obj = _find_latest_mhwilds_armature()
        if ref_arm_obj is None:
            self.report({'ERROR'}, _("参考骨架导入失败"))
            return {'CANCELLED'}

        # Step 2: 删除猎人模型及其导入集合，让参考骨架与选中骨架对齐（按同名骨骼对齐，仅位置）
        _cleanup_ref_import(ref_arm_obj)

        bone_utils.align_armatures_by_name(target_arm, ref_arm_obj, mode='POS_ONLY')

        # Step 3: 移植 HeadAll_SCL 及其所有子级
        created = _graft_facial_bones(ref_arm_obj, target_arm)
        if created == 0:
            self.report({'WARNING'}, _("参考骨架中未找到表情骨根骨骼 (HeadAll_SCL)"))
            return {'CANCELLED'}

        # Step 4: 假头法增加眨眼幅度
        fake_count = 0
        if self.increase_blink_amplitude:
            for bone_name in _BLINK_TARGET_BONES:
                if _apply_blink_fake_bone(target_arm, bone_name):
                    fake_count += 1

        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_arm.select_set(True)

        msg = _("已添加 %d 根表情骨") % created
        if self.increase_blink_amplitude:
            msg += _("，%d 侧已增加眨眼幅度") % fake_count
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# ============================================================
# 优化荒野骨架 (对齐后的经验修正，只操作目标骨架自身)
# ============================================================

# 需要移动到 Head/Neck_0 中点的骨骼
_OPT_NECK_BONES = ['Neck_1', 'HeadRX_HJ_01', 'Neck_1_HJ_00']
# Spine_1 头部在荒野骨架 rest 空间的原始局部坐标。
# MBT 里 2 段来源下 Spine_1 不被吸附、停在原位；但我们的 universal_snap 会随动把它平移走，
# 所以这里用死数据还原（编辑骨骼坐标为骨架局部空间，不受物体缩放/位移影响，对标准荒野骨架恒定）。
_OPT_SPINE1_REST_HEAD = (0.0, 0.000001, 1.141)
# Spine_1 相关骨骼（还原到原位）
_OPT_SPINE1_BONES = ['Spine_1', 'Spine_1_HJ_00']
# 需要移动到 Spine_1/Neck_0 中点的骨骼（照搬 MBT：Spine_2 落在 Spine_1 与 Neck_0 之间）
_OPT_SPINE2_BONES = ['Spine_2', 'Spine_2_HJ_00']
# 需要与 Hip 同点的骨骼
_OPT_SPINE0_BONES = ['Spine_0', 'Spine_0_HJ_00']
# 脚背贴地 Z 坐标 (与 MBT 一致)
_OPT_INSTEP_Z = 0.019999


def _opt_move_head_keep_direction(edit_bones, bone_name, new_head):
    """移动骨骼头部到 new_head，保持原有长度和方向。骨骼不存在时忽略。"""
    bone = edit_bones.get(bone_name)
    if bone is None:
        return
    original_length = (bone.tail - bone.head).length
    if original_length == 0:
        bone.head = new_head
        return
    direction = (bone.tail - bone.head).normalized()
    bone.head = new_head
    bone.tail = bone.head + direction * original_length


class MHWS_OT_OptimizeSkeleton(bpy.types.Operator):
    """调整部分骨骼的位置，以缓解曲腿等问题，非二次元模型不建议使用"""
    bl_idname = "mhws.optimize_skeleton"
    bl_label = "优化荒野骨架"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object

        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones

        # Neck_1 应位于 Head 与 Neck_0 的中点
        head_bone = edit_bones.get('Head')
        neck0_bone = edit_bones.get('Neck_0')
        if head_bone and neck0_bone:
            center = (head_bone.head + neck0_bone.head) / 2
            for name in _OPT_NECK_BONES:
                _opt_move_head_keep_direction(edit_bones, name, center)

        # 先把 Spine_1 还原到荒野原始位置（universal_snap 的随动会把它平移走），
        # 再让 Spine_2 落在 Spine_1 与 Neck_0 中点——复刻 MBT
        for name in _OPT_SPINE1_BONES:
            _opt_move_head_keep_direction(edit_bones, name, _OPT_SPINE1_REST_HEAD)
        spine1_bone = edit_bones.get('Spine_1')
        if spine1_bone and neck0_bone:
            center = (spine1_bone.head + neck0_bone.head) / 2
            for name in _OPT_SPINE2_BONES:
                _opt_move_head_keep_direction(edit_bones, name, center)

        # Instep 应位于 Foot 与 Toe 的中点，且 Z 坐标与 Toe 平齐（脚底贴地）
        for side in ('L', 'R'):
            foot_bone = edit_bones.get(f'{side}_Foot')
            toe_bone = edit_bones.get(f'{side}_Toe')
            if foot_bone and toe_bone:
                _opt_move_head_keep_direction(
                    edit_bones, f'{side}_Toe',
                    (toe_bone.head.x, toe_bone.head.y, _OPT_INSTEP_Z)
                )
                center = (
                    (foot_bone.head.x + toe_bone.head.x) / 2,
                    (foot_bone.head.y + toe_bone.head.y) / 2,
                    toe_bone.head.z,
                )
                _opt_move_head_keep_direction(edit_bones, f'{side}_Instep', center)

        # Knee 对齐到膝关节，Shin 在其正下方 0.01：
        # universal_snap 已把 Shin 头对齐到膝关节位置，先把 Knee 平移到该点（保持自身方向长度），
        # 再把 Shin 整体下移 0.01，使 Knee 恰在 Shin 正上方（仅 Z 相差），与 MBT 一致
        for side in ('L', 'R'):
            shin = edit_bones.get(f'{side}_Shin')
            if shin is None:
                continue
            knee = edit_bones.get(f'{side}_Knee')
            if knee is not None:
                offset = shin.head - knee.head
                knee.tail = knee.tail + offset
                knee.head = shin.head.copy()
            shin.head.z -= 0.01
            shin.tail.z -= 0.01

        # Spine_0 应与 Hip 同点，避免骑乘时臀部顶起
        hip_bone = edit_bones.get('Hip')
        if hip_bone:
            hip_head = hip_bone.head.copy()
            for name in _OPT_SPINE0_BONES:
                _opt_move_head_keep_direction(edit_bones, name, hip_head)

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, _("荒野骨架优化完成"))
        return {'FINISHED'}


# ============================================================
# 优化辅助骨骼及权重 (HJ bones)
# ============================================================

# 将 HJ 辅助骨整体平移，使其头部与目标基础骨头部重合（保持 HJ 骨自身方向和长度）。
# 基础骨已由 universal_snap 对齐到位。映射参考 MBT MHWilds 的 HJ 吸附表，
# 转换为游戏骨架内部的基础骨目标。

# 中心骨（无侧别）：HJ 骨 -> 基础骨
_HJ_TO_BASE_CENTER = {
    "Neck_1_HJ_00":  "Neck_1",
    "Neck_0_HJ_00":  "Neck_0",
    "Spine_2_HJ_00": "Spine_2",
    "Spine_1_HJ_00": "Spine_1",
    "Spine_0_HJ_00": "Spine_0",
    "Hip_HJ_00":     "Hip",
}

# 侧别模板 {s} = L / R：HJ 骨 -> 基础骨（吸附到该基础骨头部）
_HJ_TO_BASE_SIDED = {
    # 肩部
    "{s}_Shoulder_HJ_00": "{s}_Shoulder",
    "{s}_Traps_HJ_00":    "{s}_Shoulder",
    "{s}_Traps_HJ_01":    "{s}_Shoulder",
    "{s}_Pec_HJ_00":      "{s}_Shoulder",
    "{s}_Pec_HJ_01":      "{s}_Shoulder",
    "{s}_Lats_HJ_00":     "{s}_Shoulder",
    "{s}_Lats_HJ_01":     "{s}_Shoulder",
    # 上臂
    "{s}_UpperArm_HJ_00":       "{s}_UpperArm",
    "{s}_UpperArmDouble_HJ_00": "{s}_UpperArm",
    "{s}_UpperArmTwist_HJ_00":  "{s}_UpperArm",
    "{s}_Deltoid_HJ_00":        "{s}_UpperArm",
    "{s}_Deltoid_HJ_01":        "{s}_UpperArm",
    "{s}_Deltoid_HJ_02":        "{s}_UpperArm",
    # 肘 / 前臂
    "{s}_Elbow_HJ_00":         "{s}_Forearm",
    "{s}_Forearm_HJ_00":       "{s}_Forearm",
    "{s}_ForearmDouble_HJ_00": "{s}_Forearm",
    "{s}_ForearmRY_HJ_00":     "{s}_Forearm",
    "{s}_ForearmRY_HJ_01":     "{s}_Forearm",
    "{s}_ForearmTwist_HJ_00":  "{s}_Forearm",
    # 手
    "{s}_Hand_HJ_00":   "{s}_Hand",
    "{s}_Hand_HJ_01":   "{s}_Hand",
    "{s}_HandRZ_HJ_00": "{s}_Hand",
    "{s}_Palm":         "{s}_Hand",
    # 大腿
    "{s}_Hip_HJ_00":       "{s}_Thigh",
    "{s}_Hip_HJ_01":       "{s}_Thigh",
    "{s}_ThighRZ_HJ_00":   "{s}_Thigh",
    "{s}_ThighRZ_HJ_01":   "{s}_Thigh",
    "{s}_ThighRX_HJ_00":   "{s}_Thigh",
    "{s}_ThighRX_HJ_01":   "{s}_Thigh",
    "{s}_ThighTwist_HJ_00": "{s}_Thigh",
    "{s}_ThighTwist_HJ_01": "{s}_Thigh",
    # 膝 / 小腿（膝关节位置由 {s}_Shin 头部代表）
    "{s}_ThighTwist_HJ_02": "{s}_Shin",
    "{s}_Calf_HJ_00":       "{s}_Shin",
    "{s}_Shin_HJ_00":       "{s}_Shin",
    "{s}_Shin_HJ_01":       "{s}_Shin",
    "{s}_Knee_HJ_00":       "{s}_Shin",
    "{s}_KneeDouble_HJ_00": "{s}_Shin",
    "{s}_KneeRX_HJ_00":     "{s}_Shin",
    # 脚
    "{s}_Foot_HJ_00": "{s}_Foot",
}

# 扭转类 HJ 骨 -> 两关节头部中点。MBT 里这些吸附到 MMD 的中段扭转骨
# (zArmTwist / zHandTwist)，游戏骨架内无对应参考点，用肢段中点近似。
_HJ_TO_MIDPOINT_SIDED = {
    "{s}_UpperArmTwist_HJ_01": ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_UpperArmTwist_HJ_02": ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Triceps_HJ_00":       ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Biceps_HJ_00":        ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Biceps_HJ_01":        ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_ForearmTwist_HJ_01":  ("{s}_Forearm",  "{s}_Hand"),
    "{s}_ForearmTwist_HJ_02":  ("{s}_Forearm",  "{s}_Hand"),
}


def _build_hj_move_tables():
    """展开侧别模板，返回 (direct, midpoint)。
    direct: {hj_name: base_name}；midpoint: {hj_name: (jointA, jointB)}"""
    direct = dict(_HJ_TO_BASE_CENTER)
    midpoint = {}
    for s in ("L", "R"):
        for hj_t, base_t in _HJ_TO_BASE_SIDED.items():
            direct[hj_t.format(s=s)] = base_t.format(s=s)
        for hj_t, (a_t, b_t) in _HJ_TO_MIDPOINT_SIDED.items():
            midpoint[hj_t.format(s=s)] = (a_t.format(s=s), b_t.format(s=s))
    return direct, midpoint

_HJ_MOVE_DIRECT, _HJ_MOVE_MIDPOINT = _build_hj_move_tables()

# 权重转移仍只针对原本这几对 (base_bone, hj_bone)：把基础骨顶点组改名/合并到 HJ 骨
_HJ_WEIGHT_PAIRS = [
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


class MHWS_OT_OptimizeAuxBones(bpy.types.Operator):
    """将全部 HJ 辅助骨吸附到对应基础骨位置（扭转类取肢段中点），并把身体权重转移至主要辅助骨。通常能让这些部位的运动更自然"""
    bl_idname = "mhws.optimize_aux_bones"
    bl_label = "优化辅助骨骼及权重"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object

        # --- Step 1: 编辑模式下移动 HJ 骨 ---
        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = arm_obj.data.edit_bones
        moved = 0

        def rigid_move(bone, target_head):
            offset = target_head - bone.head
            bone.tail = bone.tail + offset
            bone.head = target_head.copy()

        # 直接吸附到基础骨头部
        for hj_name, base_name in _HJ_MOVE_DIRECT.items():
            hj_bone = edit_bones.get(hj_name)
            base_bone = edit_bones.get(base_name)
            if hj_bone is None or base_bone is None:
                continue
            rigid_move(hj_bone, base_bone.head)
            moved += 1

        # 扭转类吸附到两关节头部中点
        for hj_name, (a_name, b_name) in _HJ_MOVE_MIDPOINT.items():
            hj_bone = edit_bones.get(hj_name)
            a_bone = edit_bones.get(a_name)
            b_bone = edit_bones.get(b_name)
            if hj_bone is None or a_bone is None or b_bone is None:
                continue
            rigid_move(hj_bone, (a_bone.head + b_bone.head) / 2)
            moved += 1

        bpy.ops.object.mode_set(mode='OBJECT')

        # --- Step 2: 权重转移（仅原本几对） ---
        bones = arm_obj.data.bones
        active_pairs = [
            (base, hj) for base, hj in _HJ_WEIGHT_PAIRS
            if bones.get(base) is not None and bones.get(hj) is not None
        ]

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
            f"完成：{moved} 根辅助骨已吸附，{renamed} 个顶点组已转移权重"
        )
        return {'FINISHED'}


classes = [
    MHWS_OT_EndfieldFaceRename,
    MHWS_OT_FaceWeightSimplify,
    MHWS_OT_AutoCreateChains,
    MHWS_OT_PreprocessModel,
    MHWS_OT_AddFacialBones,
    MHWS_OT_OptimizeSkeleton,
    MHWS_OT_OptimizeAuxBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)