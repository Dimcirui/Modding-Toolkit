import bpy
from bpy.app.translations import pgettext as _
from ...core import weight_utils
from ...core.bone_mapper import BoneMapManager
from ...core.standard_ops import _build_fuzzy_preset_bones

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
        
        self.report({'INFO'}, _("面部权重简化完成"))
        return {'FINISHED'}


# ============================================================
# 一键创建 RE Chain（实验性）
# ============================================================

# invoke 时动态填充，供 EnumProperty 回调使用
_chain_col_items = []


def _decompose_chains(head_pb, armature, physics_bones):
    """将以 head_pb 为根的物理链递归分解为多条线性路径。

    规则：
    - 在每个分叉处，标记了 chain_role='main_continue' 的子骨继续主路径；
      其余子骨各自成为独立支链的起点（递归分解）。
    - 若分叉处无 main_continue 标记，当前骨骼为主链终点，
      所有物理子骨均视为支链头。
    - 路径末尾若存在对应的 _End 骨骼，则一并纳入路径。

    physics_bones: 物理骨骼名称集合（由预设骨骼集合排除得到）
    返回：list of list[str]，每条路径为按顺序排列的骨骼名列表。
    """
    paths = []

    def walk(pb, current_path):
        current_path = current_path + [pb.name]

        bone_data = armature.data.bones.get(pb.name)
        if not bone_data:
            paths.append(current_path)
            return

        # _End 骨骼作为终结符单独处理，不参与子骨遍历
        physics_children = [
            armature.pose.bones[c.name]
            for c in bone_data.children
            if c.name in physics_bones
            and armature.pose.bones.get(c.name)
            and not c.name.endswith('_End')
        ]

        if not physics_children:
            # 叶骨：追加 _End 后路径结束
            end_pb = armature.pose.bones.get(f"{pb.name}_End")
            if end_pb and end_pb.name in physics_bones:
                current_path = current_path + [end_pb.name]
            paths.append(current_path)
            return

        if len(physics_children) == 1:
            # 线性链：直接继续，不需要 main_continue
            walk(physics_children[0], current_path)
            return

        # 分叉（≥2个物理子骨）：才需要判断 main_continue
        main_child = next(
            (c for c in physics_children if c.get("chain_role") == "main_continue"),
            None
        )

        if main_child:
            walk(main_child, current_path)
            for branch in physics_children:
                if branch != main_child:
                    walk(branch, [])
        else:
            # 分叉无主链标记：当前骨为主链终点，所有子骨各自开始新支链
            end_pb = armature.pose.bones.get(f"{pb.name}_End")
            if end_pb and end_pb.name in physics_bones:
                current_path = current_path + [end_pb.name]
            paths.append(current_path)
            for child in physics_children:
                walk(child, [])

    walk(head_pb, [])
    return paths


def _is_valid_chain_collection(col):
    """与 RE Chain Editor 的 filterChainCollection 逻辑一致"""
    t = col.get("~TYPE", "")
    return (t in ("RE_CHAIN_COLLECTION", "RE_CLSP_COLLECTION")
            and (".chain" in col.name or ".clsp" in col.name))


def _get_chain_col_items(self, context):
    return _chain_col_items


class MHWS_OT_AutoCreateChains(bpy.types.Operator):
    """在姿态模式下，根据物理骨骼的 chain_role 属性自动为每条链创建 Chain Settings 和 Chain Group。
支持分叉物理链，分叉链使用实验模式生成，线性链使用默认模式生成。
需要 RE Chain Editor 插件，且场景中存在已创建 Chain Header 的 Chain Collection。"""
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
        ],
        default='SEPARATE',
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
            self.report({'ERROR'}, _("未找到有效的 Chain Collection（需含 ~TYPE=RE_CHAIN_COLLECTION 且名称含 .chain/.clsp）"))
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
        layout.prop(self, "settings_mode", expand=True)

    def execute(self, context):
        col = bpy.data.collections.get(self.chain_collection)
        if col is None:
            self.report({'ERROR'}, _("找不到集合: %s") % self.chain_collection)
            return {'CANCELLED'}

        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel is None:
            self.report({'ERROR'}, _("未找到 RE Chain 场景属性，请确认插件已正确加载"))
            return {'CANCELLED'}

        toolpanel.chainCollection = col

        header = next(
            (o for o in col.all_objects if o.get("TYPE") == "RE_CHAIN_HEADER"),
            None
        )
        if header is None:
            self.report({'ERROR'}, _("集合 '%s' 中未找到 Chain Header，请先创建") % col.name)
            return {'CANCELLED'}

        armature = context.active_object
        chain_heads = [pb for pb in armature.pose.bones if pb.get("chain_role") in ("head", "branch_head")]

        if not chain_heads:
            self.report({'WARNING'}, _("未找到链首骨骼（chain_role=head/branch_head），请先刷新骨骼颜色"))
            return {'CANCELLED'}

        # 构建物理骨骼集合（非预设骨骼）
        settings = context.scene.mhw_suite_settings
        mapper = BoneMapManager()
        if mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            preset_bones = _build_fuzzy_preset_bones(mapper, armature)
        else:
            preset_bones = set()
        physics_bones = {b.name for b in armature.data.bones if b.name not in preset_bones}

        # 将所有链头分解为线性路径：[(head_pb, paths, path), ...]
        all_entries = []
        for head_pb in chain_heads:
            paths = _decompose_chains(head_pb, armature, physics_bones)
            for path in paths:
                all_entries.append((head_pb, paths, path))

        created = 0
        skipped = 0

        if self.settings_mode == 'SHARED':
            if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                self.report({'ERROR'}, _("无法创建 Chain Settings"))
                return {'CANCELLED'}

        saved_experimental = getattr(toolpanel, 'experimentalPoseModeOptions', False)
        try:
            for head_pb, head_paths, path in all_entries:
                if self.settings_mode == 'SEPARATE':
                    if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                        skipped += 1
                        continue

                bpy.ops.pose.select_all(action='DESELECT')
                use_experimental = len(head_paths) > 1

                if use_experimental:
                    # 分支链：实验模式，选中路径上的全部骨骼
                    for bone_name in path:
                        pb2 = armature.pose.bones.get(bone_name)
                        if pb2:
                            pb2.bone.select = True
                    first_pb = armature.pose.bones.get(path[0]) if path else None
                    if first_pb:
                        armature.data.bones.active = first_pb.bone
                    toolpanel.experimentalPoseModeOptions = True
                else:
                    # 线性链：默认模式，只选链头
                    head_pb.bone.select = True
                    armature.data.bones.active = head_pb.bone
                    toolpanel.experimentalPoseModeOptions = False

                if bpy.ops.re_chain.chain_from_bone() == {'FINISHED'}:
                    created += 1
                else:
                    skipped += 1
        finally:
            toolpanel.experimentalPoseModeOptions = saved_experimental

        self.report({'INFO'}, _("已创建 %d 条链，跳过 %d 条") % (created, skipped))
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