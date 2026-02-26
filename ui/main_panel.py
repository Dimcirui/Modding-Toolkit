import bpy
from ..core import bone_utils, weight_utils, ui_config
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..core.bone_mapper import BoneMapManager

mapper = BoneMapManager()

class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # 顶部开关
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=False)
    show_mhws: bpy.props.BoolProperty(name="Wilds", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    
    # 通用转换器开关
    show_std_converter: bpy.props.BoolProperty(name="通用骨架转换", default=True)
    show_experimental: bpy.props.BoolProperty(name="实验性功能", default=False)

    # 预设选择 (X/Y) - 标准转换用
    import_preset_enum: bpy.props.EnumProperty(
        name="来源预设 (X)",
        description="选择导入模型的骨架结构",
        items=get_import_presets_callback
    )
    
    target_preset_enum: bpy.props.EnumProperty(
        name="目标游戏 (Y)",
        description="选择要导出的目标游戏",
        items=get_target_presets_callback
    )
    
    show_mapping_details: bpy.props.BoolProperty(name="显示映射细节", default=False)
    
    # 姿态转换区域
    show_pose_convert: bpy.props.BoolProperty(name="姿态转换", default=False)
    
    # 姿态转换专用预设（独立于标准转换的 X/Y 预设）
    pose_import_preset_enum: bpy.props.EnumProperty(
        name="骨架预设",
        description="用于识别骨骼名称的预设",
        items=get_import_presets_callback
    )
    
    # 姿态记录文件选择
    pose_preset_enum: bpy.props.EnumProperty(
        name="姿态记录",
        description="选择已保存的姿态矩阵记录",
        items=get_pose_presets_callback
    )


class MHW_OT_GeneralTools(bpy.types.Operator):
    """通用工具集合"""
    bl_idname = "mhw.general_tools"
    bl_label = "通用工具"
    bl_options = {'REGISTER', 'UNDO'}
    
    action: bpy.props.EnumProperty(
        items=[
            ('ROLL_ZERO', "扭转归零", "递归将选中骨骼的 Roll 设为 0"),
            ('ADD_TAIL', "添加尾骨", "在选中骨骼末端添加垂直骨骼"),
            ('MIRROR_X', "镜像对齐 X", "以 X+ 为基准镜像对齐 X- 骨骼"),
            ('SIMPLIFY_CHAIN', "骨链简化", "隔一个删一个并合并权重"),
        ]
    )

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}

        if self.action == 'ROLL_ZERO':
            bpy.ops.object.mode_set(mode='EDIT')
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, "请在编辑模式下至少选中一根骨骼")
                return {'CANCELLED'}
            count = bone_utils.set_roll_to_zero_recursive(selected_bones)
            self.report({'INFO'}, f"已重置 {count} 根骨骼的 Roll")

        elif self.action == 'ADD_TAIL':
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, "请选中需要加尾巴的骨骼")
                return {'CANCELLED'}
            count = bone_utils.add_vertical_tail_bone(edit_bones, selected_bones)
            self.report({'INFO'}, f"添加了 {count} 根尾骨")
            bpy.ops.object.mode_set(mode='POSE') 
            bpy.ops.object.mode_set(mode='EDIT')

        elif self.action == 'MIRROR_X':
            selected_names = []
            if context.mode == 'POSE':
                selected_names = [b.name for b in context.selected_pose_bones]
            elif context.mode == 'EDIT':
                selected_names = [b.name for b in context.selected_editable_bones]
            else:
                selected_names = [b.name for b in arm_obj.data.bones if b.select]

            if len(selected_names) != 2:
                self.report({'ERROR'}, "请正好选中两个骨骼进行镜像对齐")
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            success, msg = bone_utils.mirror_bone_transform(edit_bones, selected_names)
            if success:
                self.report({'INFO'}, msg)
            else:
                self.report({'ERROR'}, msg)

        elif self.action == 'SIMPLIFY_CHAIN':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            all_bone_names = [b.name for b in arm_obj.data.edit_bones]
            selected_names = [b.name for b in context.selected_editable_bones]
            sorted_selection = [name for name in all_bone_names if name in selected_names]
            
            if len(sorted_selection) < 2:
                self.report({'ERROR'}, "至少需要选中两个骨骼")
                return {'CANCELLED'}
            
            pairs = []
            for i in range(0, len(sorted_selection) - 1, 2):
                pairs.append((sorted_selection[i], sorted_selection[i+1]))
            
            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, f"骨链简化完成，合并了 {len(pairs)} 对骨骼")

        return {'FINISHED'}


class MHW_PT_MainPanel(bpy.types.Panel):
    bl_label = "MOD Toolkit"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        # =========================================
        # 1. 顶部开关区域
        # =========================================
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="Wilds")
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        
        layout.separator()

        # =========================================
        # 2. 通用基础工具
        # =========================================
        box = layout.box()
        box.label(text="基础工具", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        col.operator("mhw.general_tools", text="扭转归零 (Roll=0)").action = 'ROLL_ZERO'
        row = col.row(align=True)
        row.operator("mhw.general_tools", text="添加尾骨").action = 'ADD_TAIL'
        row.operator("mhw.general_tools", text="镜像对齐 X").action = 'MIRROR_X'
        col.operator("mhw.general_tools", text="骨链简化 (隔1删1)").action = 'SIMPLIFY_CHAIN'

        layout.separator()

        # =========================================
        # 3. 通用骨架转换系统
        # =========================================
        main_box = layout.box()
        row = main_box.row()
        row.prop(settings, "show_std_converter", 
                 icon="TRIA_DOWN" if settings.show_std_converter else "TRIA_RIGHT", 
                 icon_only=True, emboss=False)
        row.label(text="通用标准转换", icon='ARMATURE_DATA')

        if settings.show_std_converter:
            col = main_box.column(align=True)
            col.prop(settings, "import_preset_enum", icon='IMPORT')
            col.prop(settings, "target_preset_enum", icon='EXPORT')
            
            col.separator()
            
            # 核心功能（带预设依赖提示）
            row = col.row(align=True)
            row.operator("modder.universal_snap", text="对齐骨骼 [X+Y, 双骨架]", icon='SNAP_ON')
            
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("modder.direct_convert", text="重命名顶点组 [X+Y]", icon='MOD_VERTEX_WEIGHT')
            
            # 实验性功能（折叠）
            col.separator()
            row = col.row()
            row.prop(settings, "show_experimental",
                     icon="TRIA_DOWN" if settings.show_experimental else "TRIA_RIGHT",
                     icon_only=True, emboss=False)
            row.label(text="实验性功能", icon='ERROR')
            
            if settings.show_experimental:
                exp_col = col.column(align=True)
                exp_col.operator("modder.smart_graft", text="移植物理骨骼 [X+Y, 双骨架]", icon='BONE_DATA')
                exp_col.operator("modder.merge_physics_weights", text="物理权重降级 [X]", icon='TRASH')
            
            # 映射详情预览
            col.separator()
            row = col.row()
            row.prop(settings, "show_mapping_details", 
                     icon='TRIA_DOWN' if settings.show_mapping_details else 'TRIA_RIGHT', 
                     emboss=False)
            
            if settings.show_mapping_details:
                if arm_obj and arm_obj.type == 'ARMATURE':
                    mapper.load_preset(settings.import_preset_enum, is_import_x=True)
                    
                    mapper_y = BoneMapManager()
                    mapper_y.load_preset(settings.target_preset_enum, is_import_x=False)
                    
                    preview_box = col.box()
                    for group_name, group_data in ui_config.UI_HIERARCHY.items():
                        g_box = preview_box.box()
                        g_box.label(text=group_name, icon=group_data['icon'])
                        
                        for sub_name, bones in group_data['subsections'].items():
                            sub_col = g_box.column(align=True)
                            sub_col.label(text=sub_name)
                            
                            for std_key in bones:
                                if std_key in ui_config.OPTIONAL_BONES:
                                    if std_key not in mapper_y.mapping_data:
                                        continue
                                
                                main_bone, aux_list = mapper.get_matches_for_standard(arm_obj, std_key)
                                m_row = sub_col.row(align=True)
                                m_row.label(text=f"  {ui_config.get_display_name(std_key)}")
                                
                                if main_bone:
                                    status = f"{main_bone}"
                                    if aux_list: status += f" (+{len(aux_list)})"
                                    m_row.label(text=status, icon='CHECKMARK')
                                else:
                                    m_row.label(text="缺失", icon='CANCEL')
                else:
                    col.label(text="请选中骨架以预览", icon='INFO')

        layout.separator()

        # =========================================
        # 4. 姿态转换 (独立区块)
        # =========================================
        pose_box = layout.box()
        row = pose_box.row()
        row.prop(settings, "show_pose_convert",
                 icon="TRIA_DOWN" if settings.show_pose_convert else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="姿态转换 (Pose Convert)", icon='OUTLINER_OB_ARMATURE')
        
        if settings.show_pose_convert:
            col = pose_box.column(align=True)
            
            col.prop(settings, "pose_import_preset_enum", text="骨架预设", icon='IMPORT')
            
            col.separator()
            col.label(text="简易工具:")
            col.operator("modder.tpose_direction", icon='EMPTY_SINGLE_ARROW')
            col.operator("modder.tpose_matrix_zero", icon='MESH_GRID')
            
            col.separator()
            col.label(text="姿态变换记录器:")
            
            row = col.row(align=True)
            row.prop(settings, "pose_preset_enum", text="")
            row.operator("modder.delete_pose_preset", text="", icon='TRASH')
            
            col.operator("modder.record_transform", text="录制变换 (选两个骨架)", icon='REC')
            
            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("modder.apply_transform_forward", text="▶ 正向 (A→B)", icon='PLAY')
            row.operator("modder.apply_transform_inverse", text="◀ 逆向 (B→A)", icon='LOOP_BACK')

        layout.separator()

        # =========================================
        # 5. 游戏专用工具栏
        # =========================================
        
        if settings.show_mhwi:
            box = layout.box()
            box.label(text="MHWI Tools", icon='ARMATURE_DATA')
            col = box.column(align=True)
            col.operator("mhwi.align_non_physics", text="对齐非物理骨骼", icon='BONE_DATA')

        if settings.show_mhws:
            box = layout.box()
            box.label(text="MHWilds Tools", icon='WORLD')
            col = box.column(align=True)
            col.operator("mhws.endfield_face_rename", text="Endfield 面部改名", icon='SORTALPHA')
            col.operator("mhws.face_weight_simplify", text="面部权重简化", icon='MOD_VERTEX_WEIGHT')
             
        if settings.show_re4:
            box = layout.box()
            box.label(text="RE4 Tools", icon='GHOST_ENABLED')

            box_fake = layout.box()
            box_fake.label(text="假骨与对齐 (FakeBone)", icon='BONE_DATA')
            col_fake = box_fake.column(align=True)
            col_fake.label(text="1. 创建 End 骨骼:")
            row1 = col_fake.row(align=True)
            row1.operator("re4.fake_body_process", text="身体", icon='ARMATURE_DATA')
            row1.operator("re4.fake_fingers_process", text="手指", icon='VIEW_PAN')
            
            col_fake.label(text="2. 合并与绑定:")
            row2 = col_fake.row(align=True)
            row2.operator("re4.fake_body_merge", text="身体", icon='LINKED')
            row2.operator("re4.fake_fingers_merge", text="手指", icon='LINKED')
            
            col_fake.label(text="3. 骨骼对齐 (含子级):")
            row3 = col_fake.row(align=True)
            row3.operator("re4.align_bones_full", text="完全对齐", icon='SNAP_ON')
            row3.operator("re4.align_bones_pos", text="仅对齐位置", icon='SNAP_VERTEX')


# ==========================================
# 注册/注销
# ==========================================
classes = [
    MHW_PT_SuiteSettings,
    MHW_OT_GeneralTools,
    MHW_PT_MainPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)