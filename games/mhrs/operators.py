import bpy

from ...core.i18n import _
from ...core.re_chain_utils import REChainConfig, auto_create_re_chains, _is_valid_chain_collection
from ...core.standard_ops import _run_bone_color_refresh

_mhrs_chain_col_items = []


def _get_mhrs_chain_col_items(self, context):
    return _mhrs_chain_col_items


class MHRS_OT_AutoCreateChains(bpy.types.Operator):
    """一键创建 RE Chain（MHRS 使用 .chain 格式）。"""
    bl_idname = "mhrs.auto_create_chains"
    bl_label = "一键创建 RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="选择要写入的 Chain Collection",
        items=_get_mhrs_chain_col_items,
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
        default=False,
    )
    collection_name: bpy.props.StringProperty(
        name="集合名称",
        default="",
    )
    chain_format: bpy.props.EnumProperty(
        name="Chain 格式",
        items=[
            (".chain", "Chain", "旧格式，用于 MHRS / RE4 等游戏"),
            (".chain2", "Chain2", "新格式，用于 MHWilds / RE9"),
        ],
        default='.chain',
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
        if not self.collection_name:
            col_name = context.scene.get("REMeshLastImportedCollection", "")
            if col_name and ".mesh" in col_name:
                self.collection_name = col_name.split(".mesh")[0]

        global _mhrs_chain_col_items
        _mhrs_chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _mhrs_chain_col_items):
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
            chain_file_type="chain",
            auto_create_collection=self.auto_create_collection,
            collection_name=self.collection_name,
            tuning=None,
            settings_mode=self.settings_mode,
            selected_collection=self.chain_collection,
            straighten_orientation=self.straighten_orientation,
            collider_filter_path="",
            apply_angle_ramp=self.apply_angle_ramp,
        )
        status = auto_create_re_chains(context, armature, config)
        if status == {'CANCELLED'}:
            self.report({'ERROR'}, _("创建 RE Chain 失败"))
            return {'CANCELLED'}
        self.report({'INFO'}, _("RE Chain 创建完成"))
        return {'FINISHED'}


classes = [
    MHRS_OT_AutoCreateChains,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
