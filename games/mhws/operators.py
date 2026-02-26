import bpy

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


def _merge_or_rename_vg(obj, old_name, new_name):
    """将旧顶点组重命名或合并到新名字"""
    old_vg = obj.vertex_groups.get(old_name)
    if old_vg is None:
        return False
    existing_vg = obj.vertex_groups.get(new_name)
    if existing_vg is None:
        old_vg.name = new_name
        return True
    # 合并权重
    mesh = obj.data
    old_idx = old_vg.index
    existing_idx = existing_vg.index
    for vert in mesh.vertices:
        old_w = 0.0
        existing_w = 0.0
        for g in vert.groups:
            if g.group == old_idx:
                old_w = g.weight
            elif g.group == existing_idx:
                existing_w = g.weight
        if old_w > 0.0:
            existing_vg.add([vert.index], min(existing_w + old_w, 1.0), 'REPLACE')
    obj.vertex_groups.remove(old_vg)
    return True


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
                if _merge_or_rename_vg(obj, old_name, new_name):
                    total += 1
        self.report({'INFO'}, f"已处理 {total} 个面部顶点组")
        return {'FINISHED'}


# ============================================================
# 面部权重简化 (通用)
# ============================================================

def _merge_vg_full(obj, source_names, target_name):
    """将源顶点组的权重全部合并到目标"""
    mesh = obj.data
    target_vg = obj.vertex_groups.get(target_name)
    if target_vg is None:
        target_vg = obj.vertex_groups.new(name=target_name)
    target_idx = target_vg.index
    
    for src_name in source_names:
        src_vg = obj.vertex_groups.get(src_name)
        if src_vg is None:
            continue
        src_idx = src_vg.index
        for vert in mesh.vertices:
            src_w = 0.0
            tgt_w = 0.0
            for g in vert.groups:
                if g.group == src_idx:
                    src_w = g.weight
                elif g.group == target_idx:
                    tgt_w = g.weight
            if src_w > 0.0:
                target_vg.add([vert.index], min(tgt_w + src_w, 1.0), 'REPLACE')
        obj.vertex_groups.remove(src_vg)


def _transfer_partial(obj, source_names, targets_with_ratios):
    """从源顶点组按比例分配权重到多个目标，源保留剩余"""
    mesh = obj.data
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
        src_idx = src_vg.index
        for vert in mesh.vertices:
            src_w = 0.0
            for g in vert.groups:
                if g.group == src_idx:
                    src_w = g.weight
                    break
            if src_w <= 0.0:
                continue
            for tgt_vg, ratio in target_vgs:
                tgt_idx = tgt_vg.index
                tgt_w = 0.0
                for g in vert.groups:
                    if g.group == tgt_idx:
                        tgt_w = g.weight
                        break
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
        _merge_vg_full(obj, [
            "L_malarFat_B_LOD01", "R_malarFat_B_LOD01",
            "L_CheekBone_LOD02", "R_CheekBone_LOD02",
            "C_Nose_LOD01", "C_TongueA_LOD01",
            "UpperTeeth", "HeadAll_SCL",
        ], "Head")
        
        # 2. 合并到 C_Chin_LOD01
        _merge_vg_full(obj, [
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


classes = [
    MHWS_OT_EndfieldFaceRename,
    MHWS_OT_FaceWeightSimplify,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)