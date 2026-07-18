import bpy
import os
import re
from ..core.i18n import _
from ..core import bone_utils, weight_utils, ui_config
from ..core.re_mesh_compat import re_mesh_op_available
from ..core.mdf_generator_base import MHW_OT_SetChannelSize
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..games.re9.batch_export import get_schemes_callback
from ..games.re4.batch_export import get_schemes_callback as get_re4_schemes_callback
from ..games.mhws.batch_export import get_mhws_schemes_callback, get_mhws_armor_callback, MHWS_VARIANTS
from ..games.mhrs.batch_export import get_mhrs_schemes_callback, get_mhrs_armor_callback, MHRS_GENDERS
from ..games.mhwi.batch_export import (
    get_mhwi_armor_sets_callback,
    get_mhwi_hr_armor_callback,
    get_mhwi_mr_armor_callback,
    get_mhwi_sp_armor_callback,
)
from ..games.mhwi.weapon_data import get_mhwi_weapon_sets_callback, WEAPON_TYPES
from ..core.bone_mapper import BoneMapManager

# 映射详情预览缓存：{(x_preset, y_preset): (mapper_x, mapper_y)}
_mapping_detail_cache = {}


class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # 顶部开关
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=False)
    show_mhws: bpy.props.BoolProperty(name="MHWS", default=False)
    show_mhrs: bpy.props.BoolProperty(name="MHRS", default=False)
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
        items=get_import_presets_callback,
    )

    target_preset_enum: bpy.props.EnumProperty(
        name="目标游戏 (Y)",
        description="选择要导出的目标游戏",
        items=get_target_presets_callback,
        update=lambda self, context: setattr(
            self, "align_mode_override", bone_utils.get_default_align_mode(self.target_preset_enum)
        ),
    )

    align_mode_override: bpy.props.EnumProperty(
        name="对齐模式",
        description="骨骼对齐 (Snap) 的对齐方式，切换目标游戏 (Y) 时会自动同步为该预设的默认值",
        items=[
            ('POS_ONLY', "仅位置", "只对齐骨骼头部位置，保留目标骨架原有的方向和长度"),
            ('POS_ROLL', "位置+扭转", "对齐头部位置并复制来源骨骼的扭转(Roll)，长度方向不变"),
            ('FULL', "完全对齐", "头部、尾部、扭转全部对齐到来源骨骼 (骨骼长度和方向都会跟随来源)"),
        ],
        default='POS_ONLY',
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
        items=get_import_presets_callback,
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
    mhwi_export_mode: bpy.props.EnumProperty(
        name="导出模式",
        items=[
            ('ARMOR',  "装备", "导出人物装备（护甲/幻化）"),
            ('WEAPON', "武器", "导出武器模型（暂不支持空模替换）"),
        ],
        default='ARMOR',
    )
    mhwi_armor_sets_file: bpy.props.EnumProperty(
        name="预设组",
        description="选择 MHWI 装备预设组 JSON",
        items=get_mhwi_armor_sets_callback,
    )
    mhwi_weapon_sets_file: bpy.props.EnumProperty(
        name="预设组",
        description="选择 MHWI 武器预设组 JSON",
        items=get_mhwi_weapon_sets_callback,
    )
    mhwi_weapon_type_tab: bpy.props.EnumProperty(
        name="武器类型",
        items=[(code, name, "") for code, name, _secondary in WEAPON_TYPES],
        default='two',
    )
    mhwi_rank_tab: bpy.props.EnumProperty(
        name="位阶",
        items=[
            ('HR', "上下位", "低位/高位装备"),
            ('MR', "大师位", "冰原大师位装备"),
            ('SP', "整套幻化", "独立幻化套装（含头部/头发模型）"),
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
    mhwi_selected_sp_armor: bpy.props.EnumProperty(
        name="整套幻化",
        description="选择要导出的整套幻化",
        items=get_mhwi_sp_armor_callback,
    )
    mhwi_cleanup_before_export: bpy.props.BoolProperty(
        name="导出前清理网格",
        description="导出前对所有已绑定的 mod3 集合执行: 删除松散几何、修复重复UV、清除零权重顶点组、限制并归一化权重（需要 RE Mesh Editor，未安装则静默跳过）",
        default=True,
    )
    mhwi_confuse_before_export: bpy.props.BoolProperty(
        name="防石化",
        description="在 mod3 和 mrl3 中添加一些混淆内容，不影响使用，但可以有效防止一些拿别人 mod 改改就当自己的东西的倒狗",
        default=False,
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
    mhws_cleanup_before_export: bpy.props.BoolProperty(
        name="导出前清理网格",
        description="导出前对所有已绑定的 mesh 集合执行: 删除松散几何、修复重复UV、清除零权重顶点组、限制并归一化权重（需要 RE Mesh Editor）",
        default=True,
    )
    re9_use_blank_export: bpy.props.BoolProperty(
        name="未选项使用空模型",
        description="导出时对未选择集合的栏位，复制内置空文件代替跳过",
        default=True,
    )

    # MHRS batch export
    mhrs_armor_scheme: bpy.props.EnumProperty(
        name="装备包",
        description="选择 MHRS 装备包 JSON",
        items=get_mhrs_schemes_callback
    )
    mhrs_gender: bpy.props.EnumProperty(
        name="性别",
        description="选择猎人性别",
        items=MHRS_GENDERS,
        default='f'
    )
    mhrs_selected_armor: bpy.props.EnumProperty(
        name="装备",
        description="选择要导出的装备",
        items=get_mhrs_armor_callback
    )
    mhrs_use_blank_export: bpy.props.BoolProperty(
        name="未选项使用空模型",
        description="导出时对未选择集合的栏位，复制内置空文件代替跳过",
        default=False,
    )
    mhrs_cleanup_before_export: bpy.props.BoolProperty(
        name="导出前清理网格",
        description="导出前对所有已绑定的 mesh 集合执行: 删除松散几何、修复重复UV、清除零权重顶点组、限制并归一化权重（需要 RE Mesh Editor）",
        default=True,
    )
    mhrs_use_shadow_export: bpy.props.BoolProperty(
        name="使用 Shadow Mesh",
        description="导出时将内置的 Shadow 参考模型骨架对齐到所选骨架，并导出到固定的 mod/{性别}/bone/ 路径",
        default=False,
    )
    mhrs_shadow_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="对齐骨架",
        description="用于对齐 Shadow 参考模型骨架的目标骨架；留空且本次仅绑定了一个 Mesh 集合时，将自动使用该集合内的骨架",
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
    re4_use_body_arm: bpy.props.BoolProperty(
        name="使用身体骨架",
        description="自动从身体 Mesh 集合获取骨架并对齐原生骨架，省去手动绑定 fbxskel 骨架",
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
            ('ALIGN_POS',     "对齐 (位置)",    "将目标骨骼 head 对齐到源，不改变长度方向"),
            ('ALIGN_POS_ROLL',"对齐 (位置+扭转)", "对齐 head 和 roll，不改变长度方向"),
            ('ALIGN_FULL',    "对齐 (完全)",    "按骨骼名完全对齐两个骨架 (head+tail+roll)"),
            ('MERGE_CHAINS',  "合并链到激活链","选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链，超出部分合并到链末"),
        ]
    )

    _ACTION_DESCRIPTIONS = {
        'ROLL_ZERO':      "递归将选中骨骼及其所有子骨的 Roll 值归零",
        'ADD_TAIL':       "在每根选中骨骼的末端添加一根垂直向上的尾骨",
        'MIRROR_X':       "正好选中两根骨骼：以 X+ 侧那根为基准，镜像覆盖 X- 侧那根的位置与扭转",
        'SIMPLIFY_CHAIN': "按链结构将骨骼两两配对合并权重并删除多余骨骼；链末无权重骨（尾骨）自动跳过不参与配对",
        'MERGE_TO_ACTIVE':"将其余选中骨骼的权重全部并入激活骨（最后点击的那根），然后删除其余骨骼",
        'MERGE_CHAINS':   "选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链；源链超出长度的部分并入链末骨",
        'ALIGN_POS':      "选中两个骨架：将激活骨架中同名骨骼的 head 位置对齐到源骨架，不改变骨骼长度与方向",
        'ALIGN_POS_ROLL': "选中两个骨架：对齐同名骨骼的 head 位置和 roll 扭转，不改变骨骼长度与方向",
        'ALIGN_FULL':     "选中两个骨架：按骨骼名完全对齐 head、tail 和 roll（骨骼长度也会跟随源骨架）",
    }

    @classmethod
    def description(cls, context, properties):
        return cls._ACTION_DESCRIPTIONS.get(properties.action, cls.__doc__)

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

        elif self.action == 'MERGE_CHAINS':
            # 获取激活骨名和选中骨名（兼容 EDIT 和 POSE 模式）
            if context.mode == 'EDIT':
                active = context.active_bone
                selected_names = [b.name for b in context.selected_editable_bones]
            elif context.mode == 'POSE':
                active = context.active_pose_bone
                selected_names = [b.name for b in context.selected_pose_bones]
            else:
                bpy.ops.object.mode_set(mode='EDIT')
                active = context.active_bone
                selected_names = [b.name for b in context.selected_editable_bones]

            if not active:
                self.report({'ERROR'}, _("请确保有激活骨骼（最后点击的那根为保留目标）"))
                return {'CANCELLED'}

            active_name = active.name
            selected_set = set(selected_names)

            # 过滤出非激活的候选链首：去除祖先也在选中集合中的骨骼
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            edit_bones = arm_obj.data.edit_bones
            candidate_heads = []
            for name in selected_names:
                if name == active_name:
                    continue
                bone = edit_bones.get(name)
                if bone is None:
                    continue
                # 向上遍历父骨，若父骨在选中集合中则跳过（非链首）
                is_descendant = False
                parent = bone.parent
                while parent:
                    if parent.name in selected_set:
                        is_descendant = True
                        break
                    parent = parent.parent
                if not is_descendant:
                    candidate_heads.append(name)

            if not candidate_heads:
                self.report({'WARNING'}, _("未找到有效的待合并链首（请选中其他链的链首骨骼）"))
                return {'CANCELLED'}

            # 构建激活链和各源链，生成配对列表
            active_chain = weight_utils.build_chain_from_head(active_name, arm_obj)
            pairs = []
            chain_count = 0
            for head in candidate_heads:
                src_chain = weight_utils.build_chain_from_head(head, arm_obj)
                chain_count += 1
                for i, src_bone in enumerate(src_chain):
                    if i < len(active_chain):
                        keep = active_chain[i]
                    else:
                        keep = active_chain[-1]
                    pairs.append((keep, src_bone))

            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, _("已将 %d 条链合并到 [%s]，共处理 %d 对骨骼") % (chain_count, active_name, len(pairs)))

        elif self.action in ('ALIGN_FULL', 'ALIGN_POS', 'ALIGN_POS_ROLL'):
            selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
            if len(selected_arms) != 2:
                self.report({'ERROR'}, _("请选中两个骨架（激活的为目标，另一个为源）"))
                return {'CANCELLED'}
            target = arm_obj
            source = [o for o in selected_arms if o != target][0]
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            
            if self.action == 'ALIGN_FULL':
                mode = 'FULL'
            elif self.action == 'ALIGN_POS_ROLL':
                mode = 'POS_ROLL'
            else:
                mode = 'POS_ONLY'
                
            count = bone_utils.align_armatures_by_name(source, target, mode=mode)
            
            label_map = {
                'ALIGN_FULL': _("完全对齐"),
                'ALIGN_POS': _("位置对齐"),
                'ALIGN_POS_ROLL': _("对齐 (位置+扭转)")
            }
            self.report({'INFO'}, _("%s: %d 根骨骼") % (label_map[self.action], count))

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
        row.prop(settings, "show_mhws", toggle=True, text="MHWS")
        row.prop(settings, "show_mhrs", toggle=True, text="MHRS")
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

            col.label(text="骨骼合并", icon='AUTOMERGE_ON')
            col.operator("mhw.general_tools", text=_("骨链简化")).action = 'SIMPLIFY_CHAIN'
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=_("合并到激活骨")).action = 'MERGE_TO_ACTIVE'
            row.operator("mhw.general_tools", text=_("合并链到激活链")).action = 'MERGE_CHAINS'

            col.separator(factor=0.8)
            col.label(text="骨骼处理", icon='BONE_DATA')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=_("扭转归零")).action = 'ROLL_ZERO'
            row.operator("mhw.general_tools", text=_("镜像对齐 X")).action = 'MIRROR_X'

            col.separator(factor=0.8)
            col.label(text="骨架对齐", icon='ORIENTATION_GIMBAL')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=_("位置")).action = 'ALIGN_POS'
            row.operator("mhw.general_tools", text=_("位置+扭转")).action = 'ALIGN_POS_ROLL'
            row.operator("mhw.general_tools", text=_("完全")).action = 'ALIGN_FULL'

            col.separator(factor=0.8)
            col.label(text="权重处理", icon='GROUP_VERTEX')
            row = col.row(align=True)
            row.operator("mhw.sk_to_weights", text=_("形态键转权重"), icon='SHAPEKEY_DATA')
            row.operator("mhw.merge_renamed_vgroups", text=_("合并重名顶点组"), icon='AUTOMERGE_ON')

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
            row = col.row(align=True)
            row.prop(settings, "import_preset_enum", icon='IMPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'import_preset_enum'
            op.is_import_x = True
            row = col.row(align=True)
            row.prop(settings, "target_preset_enum", icon='EXPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'target_preset_enum'
            op.is_import_x = False
            
            col.separator()
            
            # 核心功能（带预设依赖提示）
            row = col.row(align=True)
            row.scale_y = 1.2
            row.prop(settings, "align_mode_override", text="")
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
                row = exp_col.row(align=True)
                row.operator("modder.merge_into_parent", text=_("合并到父骨"), icon='SNAP_MIDPOINT')
                row.operator("mhw.general_tools", text=_("添加尾骨"), icon='RIGID_BODY').action = 'ADD_TAIL'
                row = exp_col.row(align=True)
                row.operator("modder.mark_as_main_continue", text=_("标记为主链延伸"), icon='HANDLE_ALIGNED')
                row.operator("modder.clear_chain_role", text=_("清除标记"), icon='X')
                exp_col.operator("modder.refresh_physics_bone_colors", text=_("刷新骨骼颜色"), icon='COLOR')
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
                    if 'AUTO' in (settings.import_preset_enum, settings.target_preset_enum):
                        col.label(text="映射详情预览需要选定具体预设（非自动识别）", icon='INFO')
                    else:
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
            
            row = col.row(align=True)
            row.prop(settings, "pose_import_preset_enum", text="骨架预设", icon='IMPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'pose_import_preset_enum'
            op.is_import_x = True
            
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
            col.label(text=_("规范化:"), icon='BONE_DATA')
            col.operator("mhwi.split_physics_bones", text=_("拆分物理骨"), icon='BONE_DATA')
            col.operator("mhwi.batch_rename_physics_bones", text=_("一键重命名"), icon='SORTALPHA')

            col.separator()
            has_mhw_model = hasattr(bpy.ops, 'mhw_mod3') and hasattr(bpy.ops.mhw_mod3, 'export_mhw_mod3')
            sub = col.row(align=True)
            sub.enabled = has_mhw_model
            sub.operator("mhwi.mrl3_tex_processor_dialog", text=_("MRL3 处理器"), icon='TEXTURE')
            sub.operator("mhwi.mrl3_generator_dialog",     text=_("MRL3 生成器"), icon='SHADERFX')

            col.separator()
            has_mhw_ctc = hasattr(bpy.ops, 'mhw_ctc') and hasattr(bpy.ops.mhw_ctc, 'create_chain_from_bone')
            row = col.row()
            row.enabled = has_mhw_ctc
            row.operator("mhwi.auto_create_chains", text=_("一键创建 Chain"), icon='LINKED')
            if not has_mhw_ctc:
                col.label(text="需要 MHW Model Editor!", icon='ERROR')

            col.separator()
            col.operator("mhw.mmd_face_weights", text=_("MMD 形态键转表情权重"), icon='SHAPEKEY_DATA').target_game = 'MHWI'

            col.separator()
            row = col.row()
            row.enabled = has_mhw_model
            row.operator("mhwi.batch_export_dialog", text=_("批量导出"), icon='EXPORT')
            row = col.row()
            row.enabled = has_mhw_model
            row.operator("mhwi.batch_import_dialog", text=_("批量导入"), icon='IMPORT')

        if settings.show_mhws:
            box = layout.box()
            box.label(text="MHWS Tools", icon='WORLD')
            col = box.column(align=True)

            # 一键模型预处理
            has_mbt = hasattr(bpy.ops, 'mbt') and hasattr(bpy.ops.mbt, 'import_mhwilds_fmesh')
            row = col.row()
            row.enabled = has_mbt
            row.operator("mhws.preprocess_model", text=_("一键导入并对齐荒野模型"), icon='ARMATURE_DATA')
            if not has_mbt:
                col.label(text="需要 Modder Batch Tool!", icon='ERROR')

            col.operator("mhws.optimize_skeleton", text=_("优化荒野骨架"), icon='MOD_ARMATURE')
            col.operator("mhws.optimize_aux_bones", text=_("优化辅助骨骼及权重"), icon='GROUP_VERTEX')
            col.operator("mhw.mmd_face_weights", text=_("MMD 形态键转表情权重"), icon='SHAPEKEY_DATA').target_game = 'MHWS'

            row = col.row()
            row.enabled = has_mbt
            row.operator("mhws.add_facial_bones", text=_("一键添加表情骨"), icon='SHAPEKEY_DATA')

            col.separator()
            has_re_mesh = re_mesh_op_available('exportfile')
            sub = col.row(align=True)
            sub.enabled = has_re_mesh
            sub.operator("mhws.mdf_tex_processor_dialog", text=_("MDF2 处理器"), icon='TEXTURE')
            sub.operator("mhws.mdf_generator_dialog",     text=_("MDF2 生成器"), icon='SHADERFX')
            if not has_re_mesh:
                col.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("mhws.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

            col.separator()
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("mhws.batch_export_dialog", text="MHWs Batch Exporter", icon='EXPORT')

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
            has_re_mesh = re_mesh_op_available('exportfile')
            sub = col.row(align=True)
            sub.enabled = has_re_mesh
            sub.operator("re4.mdf_tex_processor_dialog", text=_("MDF2 处理器"), icon='TEXTURE')
            sub.operator("re4.mdf_generator_dialog",     text=_("MDF2 生成器"), icon='SHADERFX')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("re4.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

            col.separator()
            col.operator("mhw.mmd_face_weights", text=_("MMD 形态键转表情权重"), icon='SHAPEKEY_DATA').target_game = 'RE4'

            col.separator()
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re4.batch_export_dialog", text="RE4 Batch Exporter", icon='EXPORT')

        if settings.show_mhrs:
            box = layout.box()
            box.label(text="MHRS Tools", icon='GHOST_ENABLED')
            col = box.column(align=True)

            has_re_mesh = re_mesh_op_available('exportfile')
            sub = col.row(align=True)
            sub.enabled = has_re_mesh
            sub.operator("mhrs.mdf_tex_processor_dialog", text=_("MDF2 处理器"), icon='TEXTURE')
            sub.operator("mhrs.mdf_generator_dialog",     text=_("MDF2 生成器"), icon='SHADERFX')
            if not has_re_mesh:
                col.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("mhrs.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

            col.separator()
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("mhrs.batch_export_dialog", text="MHRS Batch Exporter", icon='EXPORT')

        if settings.show_re9:
            box = layout.box()
            box.label(text="RE9 Tools", icon='GHOST_ENABLED')
            col = box.column(align=True)
            col.operator("re9.sync_child_orientation", text=_("同步子级朝向及扭转"), icon='CON_ROTLIKE')

            col.separator()
            has_re_mesh = re_mesh_op_available('exportfile')
            sub = col.row(align=True)
            sub.enabled = has_re_mesh
            sub.operator("re9.mdf_tex_processor_dialog", text=_("MDF2 处理器"), icon='TEXTURE')
            sub.operator("re9.mdf_generator_dialog",     text=_("MDF2 生成器"), icon='SHADERFX')
            if not has_re_mesh:
                col.label(text="需要 RE Mesh Editor!", icon='ERROR')

            col.separator()
            has_re_chain = hasattr(bpy.ops, 're_chain') and hasattr(bpy.ops.re_chain, 'create_chain_settings')
            row = col.row()
            row.enabled = has_re_chain
            row.operator("re9.auto_create_chains", text=_("一键创建 RE Chain"), icon='LINKED')
            if not has_re_chain:
                col.label(text="需要 RE Chain Editor!", icon='ERROR')

            col.separator()
            col.operator("mhw.mmd_face_weights", text=_("MMD 形态键转表情权重"), icon='SHAPEKEY_DATA').target_game = 'RE9'

            col.separator()
            row = col.row()
            row.enabled = has_re_mesh
            row.operator("re9.batch_export_dialog", text="RE9 Batch Exporter", icon='EXPORT')
# Blender 动态枚举的已知限制：回调返回的列表若为局部变量，Python GC 会回收其中的
# 字符串，C 层继续持有悬空指针，导致非 ASCII 字符（中/日文等）显示乱码。
# 解决方法：将列表保存到模块级变量，阻止 GC 回收。
_sk_enum_cache: list = []


def _sk_enum_items(self, context):
    global _sk_enum_cache
    obj = context.active_object
    if not obj or not obj.data.shape_keys:
        _sk_enum_cache = [('1', 'No shape keys', '', 1)]
        return _sk_enum_cache
    items = []
    for i, kb in enumerate(obj.data.shape_keys.key_blocks):
        if i == 0:
            continue
        items.append((str(i), kb.name, '', i))
    _sk_enum_cache = items or [('1', 'No shape keys', '', 1)]
    return _sk_enum_cache


class MHW_OT_ShapeKeyToWeights(bpy.types.Operator):
    # Method inspired by: 光之影V, 幽玲乃昕
    """Convert a shape key to a vertex group (normalized weights + Laplacian smoothing + seam sync)"""
    bl_idname = "mhw.sk_to_weights"
    bl_label = "形态键转权重"
    bl_options = {'REGISTER', 'UNDO'}

    shape_key_enum: bpy.props.EnumProperty(
        name="形态键",
        items=_sk_enum_items,
        description="Shape key to convert (Basis is excluded)",
    )
    ignore_threshold: bpy.props.FloatProperty(
        name="忽略阈值",
        default=0.001, min=0.0,
        description="Vertices with displacement smaller than this are ignored",
    )
    weight_strength: bpy.props.FloatProperty(
        name="权重强度",
        default=1.0, min=0.1, max=5.0,
        description="Multiplier applied after normalization",
    )
    smooth_factor: bpy.props.FloatProperty(
        name="平滑扩散率",
        default=0.5, min=0.0, max=1.0,
        description="How much weight diffuses to neighbors each Laplacian pass",
    )
    smooth_iters: bpy.props.IntProperty(
        name="平滑迭代次数",
        default=10, min=0, max=100,
        description="Number of Laplacian smoothing passes",
    )
    sync_seams: bpy.props.BoolProperty(
        name="缝合重合顶点",
        default=True,
        description="Force identical weights on spatially coincident vertices to prevent UV seam tearing",
    )
    use_direction_filter: bpy.props.BoolProperty(
        name="方向过滤",
        default=False,
        description="Only include vertices whose displacement projects positively onto the chosen axis",
    )
    filter_axis: bpy.props.EnumProperty(
        name="轴",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    filter_sign: bpy.props.EnumProperty(
        name="方向",
        items=[('+', "+（正向）", ""), ('-', "-（负向）", "")],
        default='+',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        obj = context.active_object
        idx = obj.active_shape_key_index
        if idx > 0:
            self.shape_key_enum = str(idx)
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "shape_key_enum", text="形态键")
        col.separator()
        col.prop(self, "ignore_threshold")
        col.prop(self, "weight_strength", slider=True)
        col.prop(self, "smooth_factor", slider=True)
        col.prop(self, "smooth_iters")
        col.prop(self, "sync_seams")
        col.separator()
        col.prop(self, "use_direction_filter")
        if self.use_direction_filter:
            row = col.row(align=True)
            row.prop(self, "filter_axis", expand=True)
            row = col.row(align=True)
            row.prop(self, "filter_sign", expand=True)

    def execute(self, context):
        obj = context.active_object
        key_blocks = obj.data.shape_keys.key_blocks
        idx = int(self.shape_key_enum)

        if idx <= 0 or idx >= len(key_blocks):
            self.report({'ERROR'}, "请选择一个非 Basis 的形态键")
            return {'CANCELLED'}

        active_kb = key_blocks[idx]
        basis_kb = obj.data.shape_keys.reference_key

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        direction = None
        if self.use_direction_filter:
            sign = 1.0 if self.filter_sign == '+' else -1.0
            direction = {'X': (sign, 0, 0), 'Y': (0, sign, 0), 'Z': (0, 0, sign)}[self.filter_axis]

        result = weight_utils.shape_key_to_weights(
            obj, active_kb, basis_kb,
            ignore_threshold=self.ignore_threshold,
            weight_strength=self.weight_strength,
            smooth_factor=self.smooth_factor,
            smooth_iters=self.smooth_iters,
            sync_seams=self.sync_seams,
            direction=direction,
        )

        if result is None:
            self.report({'WARNING'}, f"形态键 '{active_kb.name}' 未检测到有效形变，请调低忽略阈值")
            return {'CANCELLED'}

        self.report({'INFO'}, f"已生成顶点组 '{active_kb.name}'（{result} 个有效顶点）")
        return {'FINISHED'}


# (shape_key_name, direction_xyz, part_label, mhwi_vg, mhws_vg, re4_vg, re9_vg)
_MMD_FACE_ENTRIES = [
    ("ウィンク２",  ( 0,  0, -1), "左眼上眼皮", "MhBone_321", "L_UpEyeLid_LOD01",    "L_U_Eyelid03",  "L_UprLdEdge_02"),
    ("ウィンク２",  ( 0,  0,  1), "左眼下眼皮", "MhBone_325", "L_LoEyeLid_LOD01",    "L_D_Eyelid03",  "L_LwrLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0, -1), "右眼上眼皮", "MhBone_334", "R_UpEyeLid_LOD01",    "R_U_Eyelid03",  "R_UprLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0,  1), "右眼下眼皮", "MhBone_338", "R_LoEyeLid_LOD01",    "R_D_Eyelid03",  "R_LwrLdEdge_02"),
    ("あ",          ( 0,  0,  1), "上嘴唇",     "MhBone_381", "C_upLip_T_LOD01",     "C_UpperLip",    "C_UprLp_02"),
    ("あ",          ( 0,  0, -1), "下嘴唇",     "MhBone_388", "C_loLip_T_LOD01",     "C_LowerLip",    "C_LwrLp_02"),
    ("あ",          ( 1,  0,  0), "左嘴角",     "MhBone_384", "L_cornerLip_B_LOD01", "L_MouthCorner", "L_LipCorner_02"),
    ("あ",          (-1,  0,  0), "右嘴角",     "MhBone_385", "R_cornerLip_B_LOD01", "R_MouthCorner", "R_LipCorner_02"),
]
_MMD_FACE_GAME_COL = {'MHWI': 3, 'MHWS': 4, 'RE4': 5, 'RE9': 6}

# 不允许自定义忽略阈值/权重强度/平滑扩散率/平滑迭代次数，改为按部位使用固定值；
# 上眼皮单独调高形变捕捉精度 (阈值0、扩散率0，避免眨眼权重被过度平滑)
_MMD_FACE_UPPER_EYELID_LABELS = {"左眼上眼皮", "右眼上眼皮"}
_MMD_FACE_FIXED_PARAMS = {
    True:  dict(ignore_threshold=0.0,   weight_strength=1.0, smooth_factor=0.0, smooth_iters=10),
    False: dict(ignore_threshold=0.001, weight_strength=1.0, smooth_factor=0.5, smooth_iters=10),
}


class MHW_OT_MMDFaceWeights(bpy.types.Operator):
    """将 MMD 眼皮/嘴型形态键按方向拆分为目标游戏表情顶点组"""
    bl_idname = "mhw.mmd_face_weights"
    bl_label = "MMD 形态键转表情权重"
    bl_options = {'REGISTER', 'UNDO'}

    target_game: bpy.props.EnumProperty(
        name="目标游戏",
        items=[
            ('MHWI', "MHWI", ""),
            ('MHWS', "MHWS", ""),
            ('RE4',  "RE4",  ""),
            ('RE9',  "RE9",  ""),
        ],
    )
    sync_seams: bpy.props.BoolProperty(
        name="缝合重合顶点",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "target_game")
        col.separator()
        col.prop(self, "sync_seams")

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        key_blocks = obj.data.shape_keys.key_blocks
        basis_kb = obj.data.shape_keys.reference_key
        vg_col = _MMD_FACE_GAME_COL[self.target_game]

        done, skipped = [], []
        for sk_name, direction, part_label, *vg_names in _MMD_FACE_ENTRIES:
            kb = key_blocks.get(sk_name)
            if kb is None:
                skipped.append(part_label)
                continue
            target_vg = vg_names[vg_col - 3]
            params = _MMD_FACE_FIXED_PARAMS[part_label in _MMD_FACE_UPPER_EYELID_LABELS]

            result = weight_utils.shape_key_to_weights(
                obj, kb, basis_kb,
                sync_seams=self.sync_seams,
                direction=direction,
                vg_name=target_vg,
                **params,
            )
            if result is None:
                skipped.append(part_label)
            else:
                done.append(part_label)

        if not done:
            self.report({'WARNING'}, "未找到任何有效形态键，请检查 MMD 形态键名称")
            return {'CANCELLED'}

        msg = f"已生成 {len(done)} 个表情顶点组：{'、'.join(done)}"
        if skipped:
            msg += f"；跳过：{'、'.join(skipped)}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


_RENAMED_VG_PATTERN = re.compile(r'^(.+)\.\d{3}$')


class MHW_OT_MergeRenamedVGroups(bpy.types.Operator):
    """Merge vertex groups named 'a.001', 'a.002', etc. into 'a' for all selected meshes.
Groups whose suffixed name matches a real bone in the bound armature are skipped."""
    bl_idname = "mhw.merge_renamed_vgroups"
    bl_label = "合并重名顶点组"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        total_merged = 0
        total_skipped = 0

        for obj in mesh_objects:
            bound_arm = next(
                (mod.object for mod in obj.modifiers
                 if mod.type == 'ARMATURE' and mod.object),
                None
            )
            arm_bone_names = {b.name for b in bound_arm.data.bones} if bound_arm else set()

            to_merge = {}
            for vg in obj.vertex_groups:
                m = _RENAMED_VG_PATTERN.match(vg.name)
                if not m:
                    continue
                if vg.name in arm_bone_names:
                    total_skipped += 1
                    continue
                base = m.group(1)
                to_merge.setdefault(base, []).append(vg.name)

            for base_name, suffix_names in to_merge.items():
                weight_utils.merge_vgroups_multi(obj, suffix_names, base_name)
                total_merged += len(suffix_names)

        self.report(
            {'INFO'},
            f"合并完成: {total_merged} 个顶点组已合并，{total_skipped} 个已跳过（对应真实骨骼）"
        )
        return {'FINISHED'}


# ==========================================
# 注册/注销
# ==========================================
classes = [
    MHW_PT_SuiteSettings,
    MHW_OT_GeneralTools,
    MHW_OT_ShapeKeyToWeights,
    MHW_OT_MMDFaceWeights,
    MHW_OT_SetChannelSize,
    MHW_OT_MergeRenamedVGroups,
    MHW_PT_MainPanel,
]


class MODDER_OT_AutoDetectPreset(bpy.types.Operator):
    """检测当前选中骨架的骨骼覆盖率，自动匹配最合适的预设"""
    bl_idname = "modder.auto_detect_preset"
    bl_label = "识别预设"
    bl_options = {'REGISTER', 'UNDO'}

    attr_name: bpy.props.StringProperty()
    is_import_x: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        arm = context.active_object
        if not arm or arm.type != 'ARMATURE':
            self.report({'WARNING'}, "请先选中骨架")
            return {'CANCELLED'}

        from ..core.bone_mapper import auto_detect_preset
        result = auto_detect_preset(arm, self.is_import_x)
        if result:
            settings = context.scene.mhw_suite_settings
            setattr(settings, self.attr_name, result)
            display = os.path.splitext(result)[0]
            self.report({'INFO'}, f"已识别: {display}")
        else:
            self.report({'WARNING'}, "未找到覆盖率 >= 95% 的预设，请手动选择")
        return {'FINISHED'}


classes.append(MODDER_OT_AutoDetectPreset)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)