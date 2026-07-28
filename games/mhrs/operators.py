import bpy

from ...core.i18n import T
from ...core.re_chain_utils import REChainConfig, auto_create_re_chains, _is_valid_chain_collection
from ...core.standard_ops import _run_bone_color_refresh

_mhrs_chain_col_items = []


def _get_mhrs_chain_col_items(self, context):
    return _mhrs_chain_col_items


def _get_settings_mode_items(self, context):
    return [
        ('SHARED',   T("mhrs.operators.settings_mode_shared"),   T("mhrs.operators.settings_mode_shared_desc")),
        ('SEPARATE', T("mhrs.operators.settings_mode_separate"), T("mhrs.operators.settings_mode_separate_desc")),
        ('GUESS',    T("mhrs.operators.settings_mode_guess"),    T("mhrs.operators.settings_mode_guess_desc")),
    ]


def _get_chain_format_items(self, context):
    return [
        ('.chain',  "Chain",  T("mhrs.operators.chain_format_chain_desc")),
        ('.chain2', "Chain2", T("mhrs.operators.chain_format_chain2_desc")),
    ]


class MHRS_OT_AutoCreateChains(bpy.types.Operator):
    """Create RE Chain in one click (MHRS uses the .chain format)."""
    bl_idname = "mhrs.auto_create_chains"
    bl_label = "Create RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.operators.auto_create_chains_desc")

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="Chain Collection to write the result into",
        items=_get_mhrs_chain_col_items,
    )
    settings_mode: bpy.props.EnumProperty(
        name="Settings Mode",
        items=_get_settings_mode_items,
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="Auto-create Collection",
        default=False,
    )
    collection_name: bpy.props.StringProperty(
        name="Collection Name",
        default="",
    )
    chain_format: bpy.props.EnumProperty(
        name="Chain Format",
        items=_get_chain_format_items,
    )
    straighten_orientation: bpy.props.BoolProperty(
        name="Bone Direction Preprocess",
        description="Before creating, adjust all physics bones to point straight up with roll reset to zero",
        default=False,
    )
    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="Create Directly (Auto-refresh Bone Colors)",
        description="Automatically run bone color refresh first, then try creating",
        default=False,
    )
    apply_angle_ramp: bpy.props.BoolProperty(
        name="Auto-apply Angle Ramp",
        description="Automatically call apply_angle_limit_ramp after chain creation (max 60°, 4-step gradient)",
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
            col.label(text=T("mhrs.operators.no_markers_warning"), icon='ERROR')
            col.label(text=T("mhrs.operators.no_markers_hint"))
            layout.prop(self, "auto_refresh", text=T("mhrs.operators.auto_refresh_label"))
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text=T("mhrs.operators.auto_create_collection_label"))
        if self.auto_create_collection:
            layout.prop(self, "collection_name", text=T("mhrs.operators.collection_name_label"))
            layout.prop(self, "chain_format", text=T("mhrs.operators.chain_format_label"), expand=True)
        else:
            layout.prop(self, "chain_collection")
        layout.prop(self, "settings_mode", text=T("mhrs.operators.settings_mode_label"), expand=True)
        layout.prop(self, "straighten_orientation", text=T("mhrs.operators.straighten_orientation_label"))
        layout.prop(self, "apply_angle_ramp", text=T("mhrs.operators.apply_angle_ramp_label"))

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
            self.report({'ERROR'}, T("mhrs.operators.create_failed"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("mhrs.operators.create_done"))
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
