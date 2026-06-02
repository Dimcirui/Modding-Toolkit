import bpy
from ...core.i18n import _
from ...core.re_chain_utils import REChainConfig, auto_create_re_chains, _is_valid_chain_collection
from ...core.bone_mapper import auto_detect_preset, BoneMapManager
from ...core.standard_ops import _build_fuzzy_preset_bones, _run_bone_color_refresh


class RE9_OT_SyncChildOrientation(bpy.types.Operator):
    """Select bones to sync: each selected bone (and its descendants) will align
to its PARENT's orientation. Body bones (detected via preset) are skipped along
with their subtrees; selecting a body bone as a shared parent will cascade sync
to all its directly-connected physical chains only.
Do not select a physical bone AND its physical ancestor at the same time."""
    bl_idname = "re9.sync_child_orientation"
    bl_label = "Sync Child Orientation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (context.active_object
                and context.active_object.type == "ARMATURE"
                and context.mode == "EDIT_ARMATURE")

    def execute(self, context):
        obj = context.active_object
        selected = [b for b in obj.data.edit_bones if b.select]
        if not selected:
            self.report({"ERROR"}, "No bones selected")
            return {"CANCELLED"}
        selected_set = set(b.name for b in selected)
        for bone in selected:
            parent = bone.parent
            while parent:
                if parent.name in selected_set:
                    self.report({"ERROR"}, f"\'{bone.name}\' is descendant of \'{parent.name}\'. Select only the first bone in each chain")
                    return {"CANCELLED"}
                parent = parent.parent

        # Auto-detect preset to build the body-bone exclusion set.
        # If detection fails, preset_bones stays empty and behaviour is unchanged.
        preset_bones = set()
        detected = auto_detect_preset(obj, is_import_x=True)
        if detected:
            mapper = BoneMapManager()
            if mapper.load_preset(detected, is_import_x=True):
                preset_bones = _build_fuzzy_preset_bones(mapper, obj)

        def align_to_parent(bone):
            parent = bone.parent
            if parent is None:
                return
            parent_dir = (parent.tail - parent.head).normalized()
            length = bone.length
            bone.tail = bone.head + parent_dir * length
            bone.roll = parent.roll

        def recurse(bone, is_selected_root=False):
            if preset_bones and bone.name in preset_bones:
                if is_selected_root:
                    # Selected bone is a body bone acting as shared parent:
                    # don't align it, but cascade into physical children.
                    for child in bone.children:
                        recurse(child)
                # Mid-chain body bone encountered: skip it and its entire subtree.
                return
            align_to_parent(bone)
            for child in bone.children:
                recurse(child)

        def count(bone, is_root=False):
            if preset_bones and bone.name in preset_bones:
                if is_root:
                    return sum(count(c) for c in bone.children)
                return 0
            return 1 + sum(count(c) for c in bone.children)

        total = 0
        for bone in selected:
            is_body = preset_bones and bone.name in preset_bones
            if not is_body and bone.parent is None:
                continue
            recurse(bone, is_selected_root=True)
            total += count(bone, is_root=True)
        self.report({"INFO"}, f"Aligned {total} bones")
        return {"FINISHED"}


_re9_chain_col_items = []


def _get_re9_chain_col_items(self, context):
    return _re9_chain_col_items


class RE9_OT_AutoCreateChains(bpy.types.Operator):
    """一键创建 RE Chain（RE9 默认 .chain2 格式）。"""
    bl_idname = "re9.auto_create_chains"
    bl_label = "一键创建 RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="选择要写入的 Chain Collection",
        items=_get_re9_chain_col_items,
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
            (".chain", "Chain", "旧格式，用于 RE4 等早期游戏"),
            (".chain2", "Chain2", "新格式，用于 MHWilds / RE9"),
        ],
        default='.chain2',
    )
    sync_orientation: bpy.props.BoolProperty(
        name="同步链首朝向",
        description="创建前自动对齐所有物理链首（及其物理子孙）到各自身体父级的朝向和扭转",
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

        global _re9_chain_col_items
        _re9_chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _re9_chain_col_items):
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
        layout.prop(self, "sync_orientation")
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
            tuning=None,
            settings_mode=self.settings_mode,
            selected_collection=self.chain_collection,
            sync_orientation=self.sync_orientation,
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
    RE9_OT_SyncChildOrientation,
    RE9_OT_AutoCreateChains,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
