import bpy
import os
from ...core.i18n import T
from . import data_maps
from ...core.re_chain_utils import REChainConfig, auto_create_re_chains, _is_valid_chain_collection
from ...core.standard_ops import _run_bone_color_refresh
from ...core import bone_utils, ref_skeleton, facial_bones

_FINGER_INITIALS = {
    'Index': 'I', 'Thumb': 'T', 'Middle': 'M',
    'Ring': 'R', 'Pinky': 'P',
}

# ==========================================
# 原生骨架目录
# ==========================================

def _get_native_skeletons_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, 'assets', 'native_skeletons', 're4')


_native_skel_cache = []

def get_native_skeletons_callback(self, context):
    global _native_skel_cache
    _native_skel_cache = []
    d = _get_native_skeletons_dir()
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if '.fbxskel.' in f:
                name = f.split('.fbxskel.')[0]
                _native_skel_cache.append((f, name, ""))
            elif '.skeleton.' in f:
                name = f.split('.skeleton.')[0]
                _native_skel_cache.append((f, name, ""))
    if not _native_skel_cache:
        _native_skel_cache.append(('NONE', T("re4.operators.no_native_skeleton"), ""))
    return _native_skel_cache


# ==========================================
# 假骨法内部函数
# ==========================================

def _fakebone_body(context, source_arm, ruler_arm):
    """
    在 ruler_arm 上应用身体假骨流程（以 source_arm 为约束目标）。
    处理完毕后 ruler_arm 仅保留 end 骨。
    """
    BoneName  = data_maps.FAKEBONE_BODY_BONES
    FakeName  = data_maps.FAKEBONE_BODY_FAKES
    ParentName = data_maps.FAKEBONE_BODY_PARENTS

    context.view_layer.objects.active = ruler_arm
    bpy.ops.object.mode_set(mode='POSE')

    # 1. 旋转约束
    for bone_name in BoneName:
        if bone_name in ruler_arm.pose.bones:
            crc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_ROTATION')
            crc.target = source_arm
            crc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 删除已有 end 骨
    for b in [b for b in ruler_arm.data.edit_bones if "end" in b.name]:
        ruler_arm.data.edit_bones.remove(b)

    # 创建 end 骨
    for fake in FakeName:
        if fake not in ruler_arm.data.edit_bones:
            continue
        bone = ruler_arm.data.edit_bones[fake]
        for pname in ParentName[fake]:
            if pname not in ruler_arm.data.edit_bones:
                continue
            suffix = "_end"
            if len(ParentName[fake]) > 1:
                if pname.startswith("L_") or pname.endswith("_L"):
                    suffix = "_endL"
                elif pname.startswith("R_") or pname.endswith("_R"):
                    suffix = "_endR"
            new_bone = ruler_arm.data.edit_bones.new(bone.name + suffix)
            new_bone.head = bone.head
            new_bone.tail = bone.tail
            new_bone.roll = bone.roll
            new_bone.parent = ruler_arm.data.edit_bones[pname]
            new_bone.use_connect = bone.use_connect

    bpy.ops.object.mode_set(mode='POSE')

    # 2. 缩放 + 位置约束
    for bone_name in BoneName:
        if bone_name in ruler_arm.pose.bones:
            csc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_SCALE')
            csc.target = source_arm
            csc.subtarget = bone_name
            clc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_LOCATION')
            clc.target = source_arm
            clc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 仅保留 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" not in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    bpy.ops.object.mode_set(mode='OBJECT')


def _fakebone_fingers(context, source_arm, ruler_arm):
    """
    在 ruler_arm 上应用手指假骨流程（以 source_arm 为约束目标）。
    处理完毕后 ruler_arm 仅保留 end 骨。
    """
    BoneName  = data_maps.FAKEBONE_FINGER_BONES
    ParentName = {}

    context.view_layer.objects.active = ruler_arm
    bpy.ops.object.mode_set(mode='POSE')

    # 1. 旋转约束 + 动态建立父级关系表
    for bone_name in BoneName:
        if bone_name not in ruler_arm.pose.bones:
            continue
        cr = ruler_arm.pose.bones[bone_name].constraints.new('COPY_ROTATION')
        cr.target = source_arm
        cr.subtarget = bone_name

    for bone_name in BoneName:
        if bone_name in ("R_Hand", "L_Hand"):
            continue
        if bone_name not in ruler_arm.pose.bones:
            continue
        pname = ruler_arm.pose.bones[bone_name].parent.name
        ParentName.setdefault(pname, []).append(bone_name)

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 删除已有 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    # 创建 end 骨
    for fake in ParentName:
        if fake not in ruler_arm.data.edit_bones:
            continue
        bone = ruler_arm.data.edit_bones[fake]
        for child_name in ParentName[fake]:
            if child_name not in ruler_arm.data.edit_bones:
                continue
            if (child_name.startswith('L') or child_name.startswith('R')) and len(ParentName[fake]) > 1:
                # 取 L_/R_ 后面的首字母作为 end 骨后缀，如 L_Palm -> P, L_IndexF1 -> I
                finger_initial = child_name.split('_')[1][0] if '_' in child_name else ""
                suffix = f"_end{finger_initial}" if finger_initial else "_end"
            else:
                suffix = "_end"
            new_bone = ruler_arm.data.edit_bones.new(bone.name + suffix)
            new_bone.head = bone.head
            new_bone.tail = bone.tail
            new_bone.roll = bone.roll
            new_bone.parent = ruler_arm.data.edit_bones[child_name]
            new_bone.use_connect = bone.use_connect

    bpy.ops.object.mode_set(mode='POSE')

    # 2. 缩放 + 位置约束
    for bone_name in BoneName:
        if bone_name not in ruler_arm.pose.bones:
            continue
        csc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_SCALE')
        csc.target = source_arm
        csc.subtarget = bone_name
        clc = ruler_arm.pose.bones[bone_name].constraints.new('COPY_LOCATION')
        clc.target = source_arm
        clc.subtarget = bone_name

    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.visual_transform_apply()
    for b in ruler_arm.pose.bones:
        for c in b.constraints[:]:
            b.constraints.remove(c)
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='EDIT')

    # 仅保留 end 骨
    for bone in list(ruler_arm.data.edit_bones):
        if "end" not in bone.name:
            ruler_arm.data.edit_bones.remove(bone)

    bpy.ops.object.mode_set(mode='OBJECT')


def _merge_end_bones(context, main_arm, end_arm, merge_type):
    """
    将 end_arm 合并进 main_arm，并重建父级关系。
    merge_type: 'body' 或 'fingers'
    end_arm 在 join 后被消耗，调用方应将引用置 None。
    """
    for o in list(context.selected_objects):
        o.select_set(False)
    main_arm.select_set(True)
    end_arm.select_set(True)
    context.view_layer.objects.active = main_arm
    bpy.ops.object.join()

    bpy.ops.object.mode_set(mode='EDIT')
    arm = main_arm.data

    if merge_type == 'body':
        # 1. end 骨挂回各自 base 骨（如 Spine_0_end → Spine_0）
        for bone in arm.edit_bones:
            if "_end" in bone.name:
                base_name = bone.name.split("_end")[0]
                if base_name in arm.edit_bones:
                    bone.parent = arm.edit_bones[base_name]
                    bone.use_connect = False
        # 2. 子骨重新挂到 end 骨，形成三连（如 Spine_1 → Spine_0_end → Spine_0）
        for fake, parents in data_maps.FAKEBONE_BODY_PARENTS.items():
            for pname in parents:
                suffix = "_end"
                if len(parents) > 1:
                    if pname.startswith("L_") or pname.endswith("_L"):
                        suffix = "_endL"
                    elif pname.startswith("R_") or pname.endswith("_R"):
                        suffix = "_endR"
                end_bone_name = fake + suffix
                if pname in arm.edit_bones and end_bone_name in arm.edit_bones:
                    arm.edit_bones[pname].parent = arm.edit_bones[end_bone_name]
                    arm.edit_bones[pname].use_connect = False

    elif merge_type == 'fingers':
        # 1. end 骨挂回各自 base 骨
        for fakebone in [b for b in arm.edit_bones if "_end" in b.name]:
            base_name = fakebone.name.split("_end")[0]
            if base_name in arm.edit_bones:
                fakebone.parent = arm.edit_bones[base_name]
                fakebone.use_connect = False
        # 2. 手指第一节 → end 骨 mapping
        for child_name, parent_name in data_maps.FAKEBONE_FINGER_MERGE_MAP.items():
            if child_name in arm.edit_bones and parent_name in arm.edit_bones:
                arm.edit_bones[child_name].parent = arm.edit_bones[parent_name]
                arm.edit_bones[child_name].use_connect = False
        # 3. 手指链规律
        for finger_base, num_segments in data_maps.FAKEBONE_FINGER_PATTERNS:
            for i in range(2, num_segments + 1):
                child_name  = f"{finger_base}{i}"
                parent_name = f"{finger_base}{i-1}_end"
                if child_name in arm.edit_bones and parent_name in arm.edit_bones:
                    arm.edit_bones[child_name].parent = arm.edit_bones[parent_name]
                    arm.edit_bones[child_name].use_connect = False

    bpy.ops.object.mode_set(mode='OBJECT')


def do_fakebone(context, user_arm_obj, native_fbxskel_path):
    # Method discovered by: Motoka
    """
    对 user_arm_obj 就地执行完整假骨流程（身体 + 手指）。
    batch export 中请先复制骨架再传入。
    成功返回 True，失败抛出异常。
    """
    if not hasattr(bpy.ops, 're_fbxskel') or not hasattr(bpy.ops.re_fbxskel, 'importfile'):
        raise RuntimeError(T("re4.operators.need_re_fbxskel_importer"))

    prev_active   = context.view_layer.objects.active
    prev_selected = [o for o in context.selected_objects]
    for o in prev_selected:
        o.select_set(False)

    native_arm  = None
    body_ruler  = None

    try:
        # 加载原生骨架
        bpy.ops.re_fbxskel.importfile(filepath=native_fbxskel_path)
        native_arm = context.active_object
        if native_arm is None or native_arm.type != 'ARMATURE':
            raise RuntimeError(T("re4.operators.native_import_failed").format(path=native_fbxskel_path))
        native_arm.select_set(False)

        # ── 身体 ──
        # 复制 native 作为 body ruler（native 本体留给手指用）
        context.view_layer.objects.active = native_arm
        native_arm.select_set(True)
        bpy.ops.object.duplicate()
        body_ruler = context.active_object
        native_arm.select_set(False)
        body_ruler.select_set(False)

        _fakebone_body(context, user_arm_obj, body_ruler)
        _merge_end_bones(context, user_arm_obj, body_ruler, 'body')
        body_ruler = None  # 已被 join 消耗

        # ── 手指 ──（直接使用 native_arm，无需再复制）
        _fakebone_fingers(context, user_arm_obj, native_arm)
        _merge_end_bones(context, user_arm_obj, native_arm, 'fingers')
        native_arm = None  # 已被 join 消耗

        return True

    except Exception:
        import traceback
        traceback.print_exc()
        for arm in [body_ruler, native_arm]:
            if arm is not None and arm.name in bpy.data.objects:
                bpy.data.objects.remove(arm, do_unlink=True)
        raise

    finally:
        context.view_layer.objects.active = prev_active
        for o in prev_selected:
            if o.name in bpy.data.objects:
                o.select_set(True)


# ==========================================
# RE4 假骨工具 — 一键式 Operator
# ==========================================

class RE4_OT_FakeBone_OneClick(bpy.types.Operator):
    """Fakehead Method: one-click generate a full set of End bones"""
    bl_idname = "re4.fakebone_one_click"
    bl_label  = "Generate Fake Bones (Fakehead Method)"
    bl_options = {'REGISTER', 'UNDO'}

    native_skeleton: bpy.props.EnumProperty(
        name="Native Skeleton",
        description="Select the native fbxskel file for the corresponding character",
        items=get_native_skeletons_callback,
    )

    @classmethod
    def description(cls, context, properties):
        return T("re4.operators.fakebone_oneclick_desc")

    def invoke(self, context, event):
        if context.active_object is None or context.active_object.type != 'ARMATURE':
            self.report({'ERROR'}, T("re4.operators.select_target_armature_error"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.prop(self, "native_skeleton", text=T("re4.operators.native_skeleton_prop_label"))

    def execute(self, context):
        if not hasattr(bpy.ops, 're_fbxskel') or not hasattr(bpy.ops.re_fbxskel, 'exportfile'):
            self.report({'ERROR'}, T("re4.operators.need_re_mesh_editor"))
            return {'CANCELLED'}

        user_arm = context.active_object
        if user_arm is None or user_arm.type != 'ARMATURE':
            self.report({'ERROR'}, T("re4.operators.select_target_armature_error"))
            return {'CANCELLED'}

        if not self.native_skeleton or self.native_skeleton == 'NONE':
            self.report({'ERROR'}, T("re4.operators.select_native_skeleton_error"))
            return {'CANCELLED'}

        native_path = os.path.join(_get_native_skeletons_dir(), self.native_skeleton)
        if not os.path.isfile(native_path):
            self.report({'ERROR'}, T("re4.operators.native_skeleton_not_found").format(path=native_path))
            return {'CANCELLED'}

        try:
            do_fakebone(context, user_arm, native_path)
            self.report({'INFO'}, T("re4.operators.fakebone_done"))
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, T("re4.operators.fakebone_failed").format(error=e))
            return {'CANCELLED'}


_re4_chain_col_items = []


def _get_re4_chain_col_items(self, context):
    return _re4_chain_col_items


def _get_settings_mode_items(self, context):
    return [
        ('SHARED',   T("re4.operators.settings_mode_shared_label"),   T("re4.operators.settings_mode_shared_desc")),
        ('SEPARATE', T("re4.operators.settings_mode_separate_label"), T("re4.operators.settings_mode_separate_desc")),
        ('GUESS',    T("re4.operators.settings_mode_guess_label"),    T("re4.operators.settings_mode_guess_desc")),
    ]


def _get_chain_format_items(self, context):
    return [
        (".chain",  "Chain",  T("re4.operators.chain_format_v1_desc")),
        (".chain2", "Chain2", T("re4.operators.chain_format_v2_desc")),
    ]


class RE4_OT_AutoCreateChains(bpy.types.Operator):
    """One-click create RE Chain (RE4 default .chain format)"""
    bl_idname = "re4.auto_create_chains"
    bl_label = "Auto-Create RE Chains"
    bl_options = {'REGISTER', 'UNDO'}

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="Select the Chain Collection to write into",
        items=_get_re4_chain_col_items,
    )
    settings_mode: bpy.props.EnumProperty(
        name="Settings Mode",
        items=_get_settings_mode_items,
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="Auto-Create Collection",
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
        name="Straighten Bone Orientation",
        description="Before creating, adjust all physics bones to point straight up with zeroed twist",
        default=False,
    )
    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="Create Directly (auto-refresh bone colors)",
        description="Automatically run the bone color refresh first, then try to create",
        default=False,
    )
    apply_angle_ramp: bpy.props.BoolProperty(
        name="Auto-Apply Angle Ramp",
        description="After chain creation, automatically call apply_angle_limit_ramp (max 60 degrees, 4-step ramp)",
        default=False,
    )

    @classmethod
    def description(cls, context, properties):
        return T("re4.operators.autocreate_chains_desc")

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

        global _re4_chain_col_items
        _re4_chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _re4_chain_col_items):
                self.chain_collection = cur

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        if self.has_no_markers:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text=T("re4.operators.no_markers_warning1"), icon='ERROR')
            col.label(text=T("re4.operators.no_markers_warning2"))
            layout.prop(self, "auto_refresh", text=T("re4.operators.auto_refresh_label"))
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text=T("re4.operators.auto_create_collection_label"))
        if self.auto_create_collection:
            layout.prop(self, "collection_name", text=T("re4.operators.collection_name_label"))
            layout.prop(self, "chain_format", text=T("re4.operators.chain_format_label"), expand=True)
        else:
            layout.prop(self, "chain_collection")
        layout.prop(self, "settings_mode", text=T("re4.operators.settings_mode_label"), expand=True)
        layout.prop(self, "straighten_orientation", text=T("re4.operators.straighten_orientation_label"))
        layout.prop(self, "apply_angle_ramp", text=T("re4.operators.apply_angle_ramp_label"))

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
            self.report({'ERROR'}, T("re4.operators.create_chain_failed"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("re4.operators.create_chain_done"))
        return {'FINISHED'}


# ============================================================
# 一键添加表情骨 (从原生角色骨架移植表情骨到目标骨架)
# ============================================================

_RE4_FACIAL_ROOT_BONE = "FacialDef_Face"
_RE4_BLINK_FAKE_OFFSET_Y = 0.05
_RE4_BLINK_TARGET_BONES = ("L_U_Eyelid03", "R_U_Eyelid03")


class RE4_OT_AddFacialBones(bpy.types.Operator):
    """Graft facial bones from the native character skeleton onto the current skeleton,
    optionally using the Fakehead Method to adjust blink amplitude"""
    bl_idname = "re4.add_facial_bones"
    bl_label = "Add Facial Bones"
    bl_options = {'REGISTER', 'UNDO'}

    target_armature: bpy.props.EnumProperty(
        name="Skeleton",
        description="Select the skeleton to add facial bones to",
        items=bone_utils.get_armature_enum_items,
    )
    reference_character: bpy.props.EnumProperty(
        name="Reference Character",
        description="Select the reference character skeleton to source facial bones from",
        items=lambda self, ctx: ref_skeleton.get_reference_skeleton_items('re4'),
    )
    increase_blink_amplitude: bpy.props.BoolProperty(
        name="Increase Blink Amplitude (for anime-style models)",
        description="Use the Fakehead Method on the upper eyelid bones to increase the blink deformation amplitude",
        default=False,
    )

    @classmethod
    def description(cls, context, properties):
        return T("re4.operators.add_facial_bones_desc")

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
        note.label(text=T("re4.operators.facial_bones_warning"))
        layout.separator()
        layout.prop(self, "target_armature", text=T("re4.operators.target_armature_label"))
        layout.prop(self, "reference_character", text=T("re4.operators.reference_character_label"))
        layout.prop(self, "increase_blink_amplitude", text=T("re4.operators.increase_blink_amplitude_label"))

    def execute(self, context):
        target_arm = bpy.data.objects.get(self.target_armature)
        if target_arm is None or target_arm.type != 'ARMATURE':
            self.report({'WARNING'}, T("re4.operators.invalid_armature_warning"))
            return {'CANCELLED'}

        if not self.reference_character or self.reference_character == 'NONE':
            self.report({'ERROR'}, T("re4.operators.select_reference_character_error"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Step 1: import the reference character skeleton (bundled asset, no external addon needed)
        ref_arm_obj = ref_skeleton.import_reference_armature('re4', self.reference_character)
        if ref_arm_obj is None:
            self.report({'ERROR'}, T("re4.operators.reference_import_failed").format(name=self.reference_character))
            return {'CANCELLED'}

        # Step 2: align the reference skeleton to the selected skeleton (by matching bone names, position only)
        bone_utils.align_armatures_by_name(target_arm, ref_arm_obj, mode='POS_ONLY')

        # Step 3: graft the facial bone root and all its children
        created = facial_bones.graft_facial_bones(ref_arm_obj, target_arm, _RE4_FACIAL_ROOT_BONE)
        if created == 0:
            self.report({'WARNING'}, T("re4.operators.facial_root_not_found").format(bone=_RE4_FACIAL_ROOT_BONE))
            return {'CANCELLED'}

        # Step 4: Fakehead Method to increase blink amplitude
        fake_count = 0
        if self.increase_blink_amplitude:
            for bone_name in _RE4_BLINK_TARGET_BONES:
                if facial_bones.apply_blink_fake_bone(target_arm, bone_name, _RE4_BLINK_FAKE_OFFSET_Y):
                    fake_count += 1

        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_arm.select_set(True)

        msg = T("re4.operators.facial_bones_added").format(n=created)
        if self.increase_blink_amplitude:
            msg += T("re4.operators.blink_amplitude_added").format(n=fake_count)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


classes = [
    RE4_OT_FakeBone_OneClick,
    RE4_OT_AutoCreateChains,
    RE4_OT_AddFacialBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
