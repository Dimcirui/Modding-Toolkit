import bpy
from ..core import bone_utils, weight_utils  # 确保相对导入正常

# ==========================================
# 设置属性 (Settings)
# ==========================================
class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=True)
    show_mhws: bpy.props.BoolProperty(name="MHWs", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)

# ==========================================
# 通用工具操作 (General Tools Operator)
# ==========================================
class MHW_OT_GeneralTools(bpy.types.Operator):
    """通用工具集合 Operator"""
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
            
            if len(selected_names) != 2:
                self.report({'ERROR'}, "请正好选中两个骨骼")
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            success, msg = bone_utils.mirror_bone_transform(edit_bones, selected_names)
            if success: self.report({'INFO'}, msg)
            else: self.report({'ERROR'}, msg)

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
            self.report({'INFO'}, f"简化完成")

        return {'FINISHED'}

# ==========================================
# 主面板 (Main Panel)
# ==========================================
class MHW_PT_MainPanel(bpy.types.Panel):
    bl_label = "MHW Suite"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MHW Suite'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        
        # 1. 顶部游戏切换
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="Wilds")
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        
        # 2. 通用工具栏 (始终显示)
        box = layout.box()
        box.label(text="通用工具", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        col.operator("mhw.general_tools", text="扭转归零 (Roll=0)").action = 'ROLL_ZERO'
        row = col.row(align=True)
        row.operator("mhw.general_tools", text="添加尾骨").action = 'ADD_TAIL'
        row.operator("mhw.general_tools", text="镜像对齐 X").action = 'MIRROR_X'
        col.operator("mhw.general_tools", text="骨链简化 (隔1删1)").action = 'SIMPLIFY_CHAIN'
        
        # 3. 游戏专用区域
        if settings.show_mhwi:
            self.draw_mhwi_tools(layout)
            
        if settings.show_mhws:
            self.draw_mhws_tools(layout)
             
        if settings.show_re4:
            self.draw_re4_tools(layout)

    def draw_mhwi_tools(self, layout):
        box = layout.box()
        box.label(text="MHWI Tools", icon='ARMATURE_DATA')
        col = box.column(align=True)
        col.operator("mhwi.align_non_physics", text="对齐非物理骨骼", icon='BONE_DATA')
        col.separator()
        col.label(text="VRChat / Endfield 转换:")
        row = col.row(align=True)
        row.operator("mhwi.vrc_rename", text="VRC重命名", icon='GROUP_VERTEX')
        row.operator("mhwi.vrc_snap", text="VRC吸附", icon='SNAP_ON')
        col.operator("mhwi.endfield_merge", text="Endfield 一键转 MHWI", icon='MOD_VERTEX_WEIGHT')
        col.separator()
        col.operator("mhwi.mmd_snap", text="MMD 吸附 (日/英)", icon='IMPORT')

    def draw_mhws_tools(self, layout):
        box = layout.box()
        box.label(text="MHWilds Tools", icon='WORLD')
        col = box.column(align=True)
        col.operator("mhwilds.tpose_convert", text="转为 MHWI T-Pose", icon='ARMATURE_DATA')
        col.operator("mhwilds.endfield_snap", text="Endfield -> MHWs 对齐", icon='SNAP_ON')
        col.label(text="选法: 参考骨架 -> Shift+目标骨架", icon='INFO')

    def draw_re4_tools(self, layout):
        box = layout.box()
        box.label(text="RE4 Tools", icon='GHOST_ENABLED')
        
        # 步骤 1 & 2: 转换工具
        col = box.column(align=True)
        col.operator("re4.mhwi_rename", text="MHWI -> RE4 重命名", icon='FONT_DATA')
        col.operator("re4.endfield_convert", text="Endfield -> RE4 权重转换", icon='MOD_VERTEX_WEIGHT')
        
        layout.separator()
        
        # 步骤 3: 假骨工具 (并列排布)
        box_fake = layout.box()
        box_fake.label(text="假骨工具 (FakeBone)", icon='BONE_DATA')
        col_f = box_fake.column(align=True)
        
        col_f.label(text="1. 创建 End 骨骼:")
        row1 = col_f.row(align=True)
        row1.operator("re4.fake_body_process", text="身体", icon='ARMATURE_DATA')
        row1.operator("re4.fake_fingers_process", text="手指", icon='HAND')
        
        col_f.label(text="2. 合并与绑定:")
        row2 = col_f.row(align=True)
        row2.operator("re4.fake_body_merge", text="身体", icon='LINKED')
        row2.operator("re4.fake_fingers_merge", text="手指", icon='LINKED')
        
        col_f.label(text="3. 智能对齐 (含子级):")
        row3 = col_f.row(align=True)
        row3.operator("re4.align_bones_full", text="完全", icon='SNAP_ON')
        row3.operator("re4.align_bones_pos", text="位置", icon='SNAP_VERTEX')

# ==========================================
# 注册/注销 (Registration)
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