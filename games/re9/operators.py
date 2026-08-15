import bpy
from ...core.i18n import T
from ...core.re_chain_utils import REChainConfig, auto_create_re_chains, _is_valid_chain_collection
from ...core.bone_mapper import auto_detect_preset, BoneMapManager
from ...core.standard_ops import _build_fuzzy_preset_bones, _run_bone_color_refresh
from ...core import bone_utils, ref_skeleton, facial_bones


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


def _get_settings_mode_items(self, context):
    return [
        ('SHARED',   T("core.re_chain_utils.settings_mode_shared"),   T("core.re_chain_utils.settings_mode_shared_desc")),
        ('SEPARATE', T("core.re_chain_utils.settings_mode_separate"), T("re9.operators.settings_mode_separate_desc")),
        ('GUESS',    T("re9.operators.settings_mode_guess"),    T("re9.operators.settings_mode_guess_desc")),
    ]


def _get_chain_format_items(self, context):
    return [
        (".chain2", "Chain2", T("core.re_chain_utils.chain_format_chain2_desc")),
        (".chain", "Chain", T("re9.operators.chain_format_chain_desc")),
    ]


class RE9_OT_AutoCreateChains(bpy.types.Operator):
    bl_idname = "re9.auto_create_chains"
    bl_label = "Auto Create RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("re9.operators.auto_create_chains_desc")

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="Select the Chain Collection to write into",
        items=_get_re9_chain_col_items,
    )
    settings_mode: bpy.props.EnumProperty(
        name="Settings Mode",
        items=_get_settings_mode_items,
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="Auto Create Collection",
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
    sync_orientation: bpy.props.BoolProperty(
        name="Sync Chain Head Orientation",
        description="Automatically align all physics chain heads (and their physics descendants) "
                    "to their body parent's orientation and twist before creating chains",
        default=False,
    )
    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="Auto Create (Refresh Bone Colors)",
        description="Automatically run bone color refresh first, then attempt to create",
        default=False,
    )
    apply_angle_ramp: bpy.props.BoolProperty(
        name="Auto Apply Angle Ramp",
        description="Automatically call apply_angle_limit_ramp after chain creation (max 60°, 4 gradient levels)",
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
            col.label(text=T("re9.operators.no_markers_warning"), icon='ERROR')
            col.label(text=T("re9.operators.no_markers_suggestion"))
            layout.prop(self, "auto_refresh", text=T("re9.operators.auto_refresh"))
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text=T("re9.operators.auto_create_collection"))
        if self.auto_create_collection:
            layout.prop(self, "collection_name", text=T("core.re_chain_utils.collection"))
            layout.prop(self, "chain_format", expand=True)
        else:
            layout.prop(self, "chain_collection")
        layout.prop(self, "settings_mode", expand=True)
        layout.prop(self, "sync_orientation", text=T("re9.operators.sync_orientation"))
        layout.prop(self, "apply_angle_ramp", text=T("re9.operators.apply_angle_ramp"))

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
            self.report({'ERROR'}, T("core.re_chain_utils.create_chain_failed"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("re9.operators.create_chain_done"))
        return {'FINISHED'}


# ============================================================
# 一键添加表情骨 (从原生角色骨架移植表情骨到目标骨架)
# ============================================================

_RE9_FACIAL_ROOT_BONE = "FacialJnt_Face"
_RE9_BLINK_TARGET_BONES = ("L_UprLdEdge_02", "R_UprLdEdge_02")


class RE9_OT_AddFacialBones(bpy.types.Operator):
    bl_idname = "re9.add_facial_bones"
    bl_label = "Add Facial Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("re9.operators.add_facial_bones_desc")

    target_armature: bpy.props.EnumProperty(
        name="Armature",
        description="Select the armature to add facial bones to",
        items=bone_utils.get_armature_enum_items,
    )
    reference_character: bpy.props.EnumProperty(
        name="Reference Character",
        description="Select the reference character armature to use as the facial bone source",
        items=lambda self, ctx: ref_skeleton.get_reference_skeleton_items('re9'),
    )
    increase_blink_amplitude: bpy.props.BoolProperty(
        name="Increase Blink Amplitude",
        description="Use the fake-head trick on the upper eyelid bones, increasing the "
                    "deformation amplitude of the blink motion",
        default=False,
    )
    blink_radius_mult: bpy.props.FloatProperty(
        name="Blink Sweep Radius",
        description="Blink sweep radius as a multiple of the eyeball radius; 1 is the anatomically natural pivot, higher makes the lid slide further",
        # The pivot only slides along +/-Y, so it can never get closer to the lid than
        # the perpendicular distance to the rotation axis -- measured at 0.22-0.32 eyeball
        # radii across all five reference skeletons. 0.5 keeps the whole range live.
        default=4.0, min=0.5, max=10.0,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in bpy.data.objects)

    def invoke(self, context, event):
        active = context.active_object
        if active and active.type == 'ARMATURE':
            self.target_armature = active.name
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        note = layout.row()
        note.active = False
        note.label(text=T("re9.operators.facial_bones_warning"))
        layout.separator()
        layout.prop(self, "target_armature", text=T("re9.operators.target_armature"))
        layout.prop(self, "reference_character", text=T("core.re_chain_utils.reference_character"))
        layout.prop(self, "increase_blink_amplitude", text=T("re9.operators.increase_blink_amplitude"))
        if self.increase_blink_amplitude:
            row = layout.row()
            row.prop(self, "blink_radius_mult", text=T("core.facial_bones.blink_radius_mult"), slider=True)

    def execute(self, context):
        target_arm = bpy.data.objects.get(self.target_armature)
        if target_arm is None or target_arm.type != 'ARMATURE':
            self.report({'WARNING'}, T("core.re_chain_utils.select_valid_armature"))
            return {'CANCELLED'}

        if not self.reference_character or self.reference_character == 'NONE':
            self.report({'ERROR'}, T("re9.operators.select_reference_character"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Step 1: import the reference character armature (bundled asset, no external add-on dependency)
        ref_arm_obj = ref_skeleton.import_reference_armature('re9', self.reference_character)
        if ref_arm_obj is None:
            self.report({'ERROR'}, T("re9.operators.reference_import_failed").format(name=self.reference_character))
            return {'CANCELLED'}

        try:
            # Step 2: align the reference armature to the selected armature (by matching bone names, position only)
            bone_utils.align_armatures_by_name(target_arm, ref_arm_obj, mode='POS_ONLY')

            # Step 3: graft the facial bone root and all its children
            created = facial_bones.graft_facial_bones(ref_arm_obj, target_arm, _RE9_FACIAL_ROOT_BONE)
            if created == 0:
                self.report({'WARNING'}, T("re9.operators.facial_root_not_found").format(name=_RE9_FACIAL_ROOT_BONE))
                return {'CANCELLED'}

            # Step 4: fake-head trick to increase blink amplitude
            fake_count = 0
            if self.increase_blink_amplitude:
                for bone_name in _RE9_BLINK_TARGET_BONES:
                    if facial_bones.apply_blink_fake_bone(target_arm, bone_name, self.blink_radius_mult):
                        fake_count += 1
        finally:
            # The reference armature is only used to source the graft data; discard it once done
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            if ref_arm_obj.name in bpy.data.objects:
                bpy.data.objects.remove(ref_arm_obj, do_unlink=True)

        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_arm.select_set(True)

        msg = T("core.facial_bones.facial_bones_added").format(n=created)
        if self.increase_blink_amplitude:
            msg += T("re9.operators.blink_amplitude_added").format(n=fake_count)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


classes = [
    RE9_OT_SyncChildOrientation,
    RE9_OT_AutoCreateChains,
    RE9_OT_AddFacialBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
