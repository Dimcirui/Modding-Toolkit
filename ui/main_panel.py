import bpy
from bpy.app.translations import pgettext as _
from ..core import bone_utils, weight_utils, ui_config
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..games.re9.batch_export import get_schemes_callback
from ..games.re4.batch_export import get_schemes_callback as get_re4_schemes_callback
from ..games.mhws.batch_export import get_mhws_schemes_callback, get_mhws_armor_callback, MHWS_VARIANTS
from ..games.mhwi.batch_export import (
    get_mhwi_armor_sets_callback,
    get_mhwi_hr_armor_callback,
    get_mhwi_mr_armor_callback,
)
from ..core.bone_mapper import BoneMapManager

# 映射详情预览缓存：{(x_preset, y_preset): (mapper_x, mapper_y)}
_mapping_detail_cache = {}

class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # 顶部开关
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=False)
    show_mhws: bpy.props.BoolProperty(name="Wilds", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    show_re9: bpy.props.BoolProperty(name="RE9", default=False)
    
    # 基础工具开关
    show_basic_tools: bpy.props.BoolProperty(name="基础工具", default=True)

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

    bone_view_mode: bpy.props.EnumProperty(
        items=[
            ('ALL',     '全显',    '显示所有骨骼'),
            ('BASE',    '仅基础骨', '隐藏物理骨，只显示预设基础骨'),
            ('PHYSICS', '仅物理骨', '隐藏基础骨，只显示物理骨'),
        ],
        default='ALL'
    )
    
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
    
    # RE9 batch export scheme
    re9_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE9",
        items=get_schemes_callback
    )

    # MHWI batch export
    mhwi_armor_sets_file: bpy.props.EnumProperty(
        name="装备包",
        description="选择 MHWI 装备包 JSON",
        items=get_mhwi_armor_sets_callback,
    )
    mhwi_rank_tab: bpy.props.EnumProperty(
        name="位阶",
        items=[
            ('HR', "上下位", "低位/高位装备"),
            ('MR', "大师位", "冰原大师位装备"),
        ],
        default='HR',
    )
    mhwi_gender: bpy.props.EnumProperty(
        name="性别",
        items=[
            ('F',    "女",   "仅导出女猎装备文件"),
            ('M',    "男",   "仅导出男猎装备文件"),
            ('BOTH', "双性", "同时导出男女猎装备文件"),
        ],
        default='F',
    )
    mhwi_selected_hr_armor: bpy.props.EnumProperty(
        name="上下位装备",
        description="选择要导出的上下位装备",
        items=get_mhwi_hr_armor_callback,
    )
    mhwi_selected_mr_armor: bpy.props.EnumProperty(
        name="大师位装备",
        description="选择要导出的大师位装备",
        items=get_mhwi_mr_armor_callback,
    )

    # MHWs batch export
    mhws_armor_scheme: bpy.props.EnumProperty(
        name="装备包",
        description="选择 MHWs 装备包 JSON",
        items=get_mhws_schemes_callback
    )
    mhws_armor_variant: bpy.props.EnumProperty(
        name="套装种类",
        description="选择套装变体（男猎/女猎 × 男套/女套）",
        items=MHWS_VARIANTS,
        default='ff'
    )
    mhws_selected_armor: bpy.props.EnumProperty(
        name="装备",
        description="选择要导出的装备",
        items=get_mhws_armor_callback
    )

    # MHWs Bonesystem
    mhws_use_bonesystem: bpy.props.BoolProperty(
        name="使用 Bonesystem",
        description="导出时同时生成 fbxskel.7 和 BoneSystem JSON（需要 Bonesystem 框架）",
        default=False,
    )
    mhws_fbxskel_name: bpy.props.StringProperty(
        name="FBXSkel 定义名",
        description="写入 JSON 的 FbxPath 字段，同时作为 .fbxskel.7 文件名（如 ch03_000_9000）",
    )
    mhws_bs_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="骨架",
        description="用于生成 fbxskel 的 MHWs 角色骨架",
    )
    mhws_bs_hide_face: bpy.props.BoolProperty(
        name="隐藏面部",    default=True)
    mhws_bs_hide_hair: bpy.props.BoolProperty(
        name="隐藏头发",    default=True)
    mhws_bs_hide_slinger: bpy.props.BoolProperty(
        name="隐藏投射器",  default=True)
    mhws_bs_bind_face: bpy.props.BoolProperty(
        name="绑定面部",    default=True)
    mhws_bs_bind_part: bpy.props.EnumProperty(
        name="绑定部位",
        items=[("1", "头盔", ""), ("2", "身体", "")],
        default="1",
    )
    mhws_use_blank_export: bpy.props.BoolProperty(
        name="未选项使用空模型",
        description="导出时对未选择集合的栏位，复制内置空文件代替跳过",
        default=False,
    )
    re9_use_blank_export: bpy.props.BoolProperty(
        name="未选项使用空模型",
        description="导出时对未选择集合的栏位，复制内置空文件代替跳过",
        default=True,
    )

    # RE4 batch export
    re4_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE4",
        items=get_re4_schemes_callback
    )
    re4_use_blank_export: bpy.props.BoolProperty(
        name="未选项使用空模型",
        description="导出时对未选择集合的栏位，复制内置空文件代替跳过",
        default=True,
    )
    re4_use_fakebone: bpy.props.BoolProperty(
        name="使用假头法",
        description="导出 fbxskel 前自动生成身体+手指 End 骨骼（原生骨架由预设 native_skeleton 字段指定）",
        default=False,
    )


class MHW_OT_GeneralTools(bpy.types.Operator):
    """通用工具集合"""
    bl_idname = "mhw.general_tools"
    bl_label = "通用工具"
    bl_options = {'REGISTER', 'UNDO'}
    
    action: bpy.props.EnumProperty(
        items=[
            ('ROLL_ZERO',     "扭转归零",     "递归将选中骨骼的 Roll 设为 0"),
            ('ADD_TAIL',      "添加尾骨",     "在选中骨骼末端添加垂直骨骼"),
            ('MIRROR_X',      "镜像对齐 X",   "以 X+ 为基准镜像对齐 X- 骨骼"),
            ('SIMPLIFY_CHAIN',"骨链简化",     "按链结构两两配对删减骨骼并合并权重，自动跳过尾骨"),
            ('MERGE_TO_ACTIVE',"合并到激活骨","将其余选中骨骼的权重全部合并到激活骨（最后点击的那根），并删除其余骨骼"),
            ('MERGE_CHAINS',  "合并链到激活链","选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链，超出部分合并到链末"),
            ('ALIGN_FULL',    "骨架对齐 (完全)","按骨骼名完全对齐两个骨架 (head+tail)，需选中两个骨架"),
            ('ALIGN_POS',     "骨架对齐 (位置)","按骨骼名对齐 head 位置，保持骨骼方向，需选中两个骨架"),
        ]
    )

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, _("请先选中一个骨架"))
            return {'CANCELLED'}

        if self.action == 'ROLL_ZERO':
            bpy.ops.object.mode_set(mode='EDIT')
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, _("请在编辑模式下至少选中一根骨骼"))
                return {'CANCELLED'}
            count = bone_utils.set_roll_to_zero_recursive(selected_bones)
            self.report({'INFO'}, _("已重置 %d 根骨骼的 Roll") % count)

        elif self.action == 'ADD_TAIL':
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, _("请选中需要加尾巴的骨骼"))
                return {'CANCELLED'}
            count = bone_utils.add_vertical_tail_bone(edit_bones, selected_bones)
            self.report({'INFO'}, _("添加了 %d 根尾骨") % count)

        elif self.action == 'MIRROR_X':
            selected_names = []
            if context.mode == 'POSE':
                selected_names = [b.name for b in context.selected_pose_bones]
            elif context.mode == 'EDIT':
                selected_names = [b.name for b in context.selected_editable_bones]
            else:
                selected_names = [b.name for b in arm_obj.data.bones if b.select]

            if len(selected_names) != 2:
                self.report({'ERROR'}, _("请正好选中两个骨骼进行镜像对齐"))
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            result = bone_utils.mirror_bone_transform(edit_bones, selected_names)
            success = result[0]
            msg_template = result[1]
            msg_args = result[2:] if len(result) > 2 else ()
            translated = _(msg_template) % msg_args if msg_args else _(msg_template)
            if success:
                self.report({'INFO'}, translated)
            else:
                self.report({'ERROR'}, translated)

        elif self.action == 'SIMPLIFY_CHAIN':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            selected_bones = list(context.selected_editable_bones)
            if len(selected_bones) < 2:
                self.report({'ERROR'}, _("至少需要选中两个骨骼"))
                return {'CANCELLED'}

            selected_names = [b.name for b in selected_bones]

            # 获取绑定网格（用于尾骨检测）
            mesh_objects = [o for o in bpy.data.objects
                            if o.type == 'MESH' and
                            any(m.type == 'ARMATURE' and m.object == arm_obj
                                for m in o.modifiers)]

            # 按链结构分组
            chains = weight_utils.build_bone_chains(selected_names, arm_obj)

            # 对每条链生成配对，末端无权重骨骼视为尾骨跳过
            pairs = []
            for chain in chains:
                if len(chain) < 2:
                    continue
                effective = list(chain)
                # 检测尾骨：链末尾骨骼无顶点权重则排除出配对（保留但不删除）
                if not weight_utils.bone_has_weights(effective[-1], mesh_objects):
                    effective = effective[:-1]
                for i in range(0, len(effective) - 1, 2):
                    pairs.append((effective[i], effective[i + 1]))

            if not pairs:
                self.report({'WARNING'}, _("未生成任何配对（骨骼数不足或全为尾骨）"))
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, _("骨链简化完成: 处理 %d 对骨骼") % len(pairs))

        elif self.action == 'MERGE_TO_ACTIVE':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            active = context.active_bone
            if not active:
                self.report({'ERROR'}, _("请确保有激活骨骼（最后点击的那根为保留目标）"))
                return {'CANCELLED'}

            others = [b for b in context.selected_editable_bones if b.name != active.name]
            if not others:
                self.report({'ERROR'}, _("请至少选中两根骨骼（激活骨保留，其余骨并入）"))
                return {'CANCELLED'}

            active_name = active.name
            pairs = [(active_name, b.name) for b in others]
            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, _("已将 %d 根骨骼并入 [%s]") % (len(pairs), active_name))

        elif self.action in ('ALIGN_FULL', 'ALIGN_POS'):
            selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
            if len(selected_arms) != 2:
                self.report({'ERROR'}, _("请选中两个骨架（激活的为目标，另一个为源）"))
                return {'CANCELLED'}
            target = arm_obj
            source = [o for o in selected_arms if o != target][0]
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            mode = 'FULL' if self.action == 'ALIGN_FULL' else 'POS_ONLY'
            count = bone_utils.align_armatures_by_name(source, target, mode=mode)
            label = _("完全对齐") if self.action == 'ALIGN_FULL' else _("位置对齐")
            self.report({'INFO'}, _("%s: %d 根骨骼") % (label, count))

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
        row.prop(settings, "show_re9", toggle=True, text="RE9")
        
        layout.separator()

        # =========================================
        # 2. 通用基础工具
        # =========================================
        basic_box = layout.box()
        row = basic_box.row()
        row.prop(settings, "show_basic_tools",
                 icon="TRIA_DOWN" if settings.show_basic_tools else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="基础工具", icon='TOOL_SETTINGS')

        if settings.show_basic_tools:
            col = basic_box.column(align=True)
            col.operator("mhw.general_tools", text=_("扭转归零 (Roll=0)")).action = 'ROLL_ZERO'
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=_("添加尾骨")).action = 'ADD_TAIL'
            row.operator("mhw.general_tools", text=_("镜像对齐 X")).action = 'MIRROR_X'
            col.operator("mhw.general_tools", text=_("骨链简化")).action = 'SIMPLIFY_CHAIN'
            col.operator("mhw.general_tools", text=_("合并到激活骨")).action = 'MERGE_TO_ACTIVE'
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=_("对齐 (完全)")).action = 'ALIGN_FULL'
            row.operator("mhw.general_tools", text=_("对齐 (位置)")).action = 'ALIGN_POS'

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
            row.scale_y = 1.2
            row.operator("modder.universal_snap", text=_("对齐骨骼 [X+Y, 双骨架]"), icon='SNAP_ON')
            
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("modder.direct_convert", text=_("重命名顶点组 [X+Y]"), icon='MOD_VERTEX_WEIGHT')
            
            # 实验性功能（折叠）
            col.separator()
            row = col.row()
            row.prop(settings, "show_experimental",
                     icon="TRIA_DOWN" if settings.show_experimental else "TRIA_RIGHT",
                     icon_only=True, emboss=False)
            row.label(text="实验性功能", icon='ERROR')
            
            if settings.show_experimental:
                exp_col = col.column(align=True)

                exp_col.label(text="骨架清理:", icon='TOOL_SETTINGS')
                exp_col.operator("modder.merge_physics_weights", text=_("物理权重降级 [X]"), icon='TRASH')
                exp_col.operator("modder.remove_non_base_bones", text=_("剔除非基础骨骼 [X]"), icon='X')
                exp_col.operator("modder.rename_bones_to_target", text=_("基础骨骼改名 [X+Y]"), icon='SORTALPHA')

                exp_col.separator()
                exp_col.label(text="物理链工具:", icon='BONE_DATA')
                exp_col.operator("modder.smart_graft", text=_("移植物理骨骼 [X+Y, 双骨架]"), icon='BONE_DATA')
                exp_col.operator("modder.merge_into_parent", text=_("合并到父骨"), icon='SNAP_MIDPOINT')
                row = exp_col.row(align=True)
                row.operator("modder.mark_as_main_continue", text=_("标记为主链延伸"), icon='HANDLE_ALIGNED')
                row.operator("modder.clear_chain_role", text=_("清除标记"), icon='X')
                exp_col.operator("modder.refresh_physics_bone_colors", text=_("刷新骨骼颜色 [X]"), icon='COLOR')
                exp_col.separator()
                row = exp_col.row(align=True)
                row.label(text="骨骼显示 [X]:", icon='HIDE_OFF')
                row = exp_col.row(align=True)
                row.operator("modder.set_bone_visibility", text=_("全显"),
                             depress=(settings.bone_view_mode == 'ALL')).mode = 'ALL'
                row.operator("modder.set_bone_visibility", text=_("仅基础骨"),
                             depress=(settings.bone_view_mode == 'BASE')).mode = 'BASE'
                row.operator("modder.set_bone_visibility", text=_("仅物理骨"),
                             depress=(settings.bone_view_mode == 'PHYSICS')).mode = 'PHYSICS'
            
            # 映射详情预览
            col.separator()
            row = col.row()
            row.prop(settings, "show_mapping_details", 
                     icon='TRIA_DOWN' if settings.show_mapping_details else 'TRIA_RIGHT', 
                     emboss=False)
            
            if settings.show_mapping_details:
                if arm_obj and arm_obj.type == 'ARMATURE':
                    cache_key = (settings.import_preset_enum, settings.target_preset_enum)
                    if cache_key not in _mapping_detail_cache:
                        m_x = BoneMapManager()
                        m_y = BoneMapManager()
                        m_x.load_preset(settings.import_preset_enum, is_import_x=True)
                        m_y.load_preset(settings.target_preset_enum, is_import_x=False)
                        _mapping_detail_cache.clear()
                        _mapping_detail_cache[cache_key] = (m_x, m_y)
                    mapper, mapper_y = _mapping_detail_cache[cache_key]
                    
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
            col.operator("modder.tpose_matrix_zero", text=_("RE Engine 矩阵归零 (生化9除外)"), icon='MESH_GRID')
            
            col.separator()
            col.label(text="姿态变换记录器:")
            
            row = col.row(align=True)
            row.prop(settings, "pose_preset_enum", text="")
            row.operator("modder.delete_pose_preset", text="", icon='TRASH')
            
            col.operator("modder.record_transform", text=_("录制变换 (选两个骨架)"), icon='REC')

            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("modder.apply_transform_forward", text=_("▶ 正向 (A→B)"), icon='PLAY')
            row.operator("modder.apply_transform_inverse", text=_("◀ 逆向 (B→A)"), icon='LOOP_BACK')

        layout.separator()

        # =========================================
        # 5. 游戏专用工具栏
        # =========================================
        
        if settings.show_mhwi:
            box = layout.box()
            box.label(text="MHWI Tools", icon='ARMATURE_DATA')
            col = box.column(align=True)
            col.operator("mhwi.align_non_physics", text=_("对齐非物理骨骼"), icon='BONE_DATA')

            col.separator()
            col.operator("mhwi.normalize_physics_bones", text=_("物理骨骼规范化"), icon='BONE_DATA')

            col.separator()
            has_mhw_ctc = hasattr(bpy.ops, 'mhw_ctc') and hasattr(bpy.ops.mhw_ctc, 'create_chain_from_bone')
            row = col.row()
            row.enabled = has_mhw_ctc
            row.operator("mhwi.auto_create_chains", text=_("一键创建 Chain"), icon='LINKED')
            if not has_mhw_ctc:
                col.label(text="需要 MHW Model Editor!", icon='ERROR')

            col.separator()
            has_mhw_model = hasattr(bpy.ops, 'mhw_mod3') and hasattr(bpy.ops.mhw_mod3, 'export_mhw_mod3')
            row = col.row()
            row.enabled = has_mhw_model
            row.operator("mhwi.batch_export_dialog", text=_("批量导出装备"), icon='EXPORT')
            row = col.row()
            row.enabled = has_mhw_model
            row.operator("mhwi.mrl3_tex_processor_dialog", text=_("MRL3 + Tex 处理器"), icon='TEXTURE')

        if settings.show_mhws:
            box = layout.box()
            box.label(text="MHWilds Tools", icon='WORLD')
            col = box.column(align=True)
            col.operator("mhws.endfield_face_rename", text=_("Endfield 面部改名"), icon='SORTALPHA')
            col.operator("mhws.face_weight_simplify", text=_("面部权重简化"), icon='MOD_VERTEX_WEIGHT')

            col.separator()
            has_re_mesh = hasattr(bpy.ops, 're_mesh') and hasattr(bpy.ops.re_mesh, 'exportfile')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("mhws.batch_export_dialog", text="MHWs Batch Exporter", icon='EXPORT')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("mhws.mdf_tex_processor_dialog", text=_("MDF2 + Tex 处理器"), icon='TEXTURE')
            if not has_re_mesh:
                col.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("mhws.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

        if settings.show_re4:
            box = layout.box()
            box.label(text="RE4 Tools", icon='GHOST_ENABLED')

            box_fake = box.box()
            box_fake.label(text="假头法 (FakeBone)", icon='BONE_DATA')
            has_re_fbxskel = hasattr(bpy.ops, 're_fbxskel') and hasattr(bpy.ops.re_fbxskel, 'exportfile')
            row_fb = box_fake.row()
            row_fb.enabled = has_re_fbxskel
            row_fb.operator("re4.fakebone_one_click", text=_("生成假骨骼"), icon='ARMATURE_DATA')
            if not has_re_fbxskel:
                box_fake.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col = box.column(align=True)
            col.separator()
            has_re_mesh = hasattr(bpy.ops, 're_mesh') and hasattr(bpy.ops.re_mesh, 'exportfile')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re4.batch_export_dialog", text="RE4 Batch Exporter", icon='EXPORT')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re4.mdf_tex_processor_dialog", text=_("MDF2 + Tex 处理器"), icon='TEXTURE')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("mhws.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

        if settings.show_re9:
            box = layout.box()
            box.label(text="RE9 Tools", icon='GHOST_ENABLED')
            col = box.column(align=True)
            col.operator("re9.sync_child_orientation", text=_("同步子级朝向及扭转"), icon='CON_ROTLIKE')

            col.separator()
            has_re_mesh = hasattr(bpy.ops, 're_mesh') and hasattr(bpy.ops.re_mesh, 'exportfile')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re9.batch_export_dialog", text="RE9 Batch Exporter", icon='EXPORT')
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re9.mdf_tex_processor_dialog", text=_("MDF2 + Tex 处理器"), icon='TEXTURE')
            if not has_re_mesh:
                col.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("mhws.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')


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