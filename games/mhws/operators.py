import bpy
from ...core import weight_utils

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
        self.report({'INFO'}, f"已处理 {total} 个面部顶点组")
        return {'FINISHED'}


# ============================================================
# 面部权重简化 (通用)
# ============================================================



def _transfer_partial(obj, source_names, targets_with_ratios):
    """从源顶点组按比例分配权重到多个目标，源保留剩余"""
    total_ratio = sum(r for _, r in targets_with_ratios)
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
        
        self.report({'INFO'}, "面部权重简化完成")
        return {'FINISHED'}


# ============================================================
# 一键创建 RE Chain（实验性）
# ============================================================

_CHAIN_HEAD_COLOR = (0.10, 0.62, 1.00)
_COLOR_TOL = 0.01

# invoke 时动态填充，供 EnumProperty 回调使用
_chain_col_items = []


def _is_chain_head(pb):
    c = pb.color
    if c.palette != 'CUSTOM':
        return False
    n = c.custom.normal
    return (abs(n[0] - _CHAIN_HEAD_COLOR[0]) < _COLOR_TOL and
            abs(n[1] - _CHAIN_HEAD_COLOR[1]) < _COLOR_TOL and
            abs(n[2] - _CHAIN_HEAD_COLOR[2]) < _COLOR_TOL)


def _is_valid_chain_collection(col):
    """与 RE Chain Editor 的 filterChainCollection 逻辑一致"""
    t = col.get("~TYPE", "")
    return (t in ("RE_CHAIN_COLLECTION", "RE_CLSP_COLLECTION")
            and (".chain" in col.name or ".clsp" in col.name))


def _get_chain_col_items(self, context):
    return _chain_col_items


class MHWS_OT_AutoCreateChains(bpy.types.Operator):
    """在姿态模式下，根据物理骨骼颜色自动为每条链创建 Chain Settings 和 Chain Group。
需要 RE Chain Editor 插件，且场景中存在已创建 Chain Header 的 Chain Collection。"""
    bl_idname = "mhws.auto_create_chains"
    bl_label = "一键创建 RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="选择要写入的 Chain Collection",
        items=_get_chain_col_items,
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE'
                and context.active_object is not None
                and context.active_object.type == 'ARMATURE'
                and hasattr(bpy.ops, 're_chain')
                and hasattr(bpy.ops.re_chain, 'create_chain_settings'))

    def invoke(self, context, event):
        global _chain_col_items
        _chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]
        if not _chain_col_items:
            self.report({'ERROR'}, "未找到有效的 Chain Collection（需含 ~TYPE=RE_CHAIN_COLLECTION 且名称含 .chain/.clsp）")
            return {'CANCELLED'}

        # 预选当前 RE Chain 面板已设置的集合
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _chain_col_items):
                self.chain_collection = cur

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "chain_collection")

    def execute(self, context):
        col = bpy.data.collections.get(self.chain_collection)
        if col is None:
            self.report({'ERROR'}, f"找不到集合: {self.chain_collection}")
            return {'CANCELLED'}

        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel is None:
            self.report({'ERROR'}, "未找到 RE Chain 场景属性，请确认插件已正确加载")
            return {'CANCELLED'}

        # 将选中的集合设为 RE Chain 的当前工作集合
        toolpanel.chainCollection = col

        header = next(
            (o for o in col.all_objects if o.get("TYPE") == "RE_CHAIN_HEADER"),
            None
        )
        if header is None:
            self.report({'ERROR'}, f"集合 '{col.name}' 中未找到 Chain Header，请先创建")
            return {'CANCELLED'}

        armature = context.active_object
        chain_heads = [pb for pb in armature.pose.bones if _is_chain_head(pb)]

        if not chain_heads:
            self.report({'WARNING'}, "未找到链首骨骼（浅蓝色），请先执行物理骨骼移植")
            return {'CANCELLED'}

        created = 0
        skipped = 0
        for pb in chain_heads:
            if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                skipped += 1
                continue

            bpy.ops.pose.select_all(action='DESELECT')
            pb.bone.select = True
            armature.data.bones.active = pb.bone

            if bpy.ops.re_chain.chain_from_bone() == {'FINISHED'}:
                created += 1
            else:
                skipped += 1

        self.report({'INFO'}, f"已创建 {created} 条链，跳过 {skipped} 条")
        return {'FINISHED'}


classes = [
    MHWS_OT_EndfieldFaceRename,
    MHWS_OT_FaceWeightSimplify,
    MHWS_OT_AutoCreateChains,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)