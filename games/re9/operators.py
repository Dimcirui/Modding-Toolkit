import bpy
from ...core import bone_utils
from . import data_maps


class RE9_OT_SyncChildOrientation(bpy.types.Operator):
    """Select bones to sync: each selected bone (and its descendants) will align
to its PARENT's orientation. Do not select a bone AND its descendant at the same time"""
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

        def align_to_parent(bone):
            parent = bone.parent
            if parent is None:
                return
            parent_dir = (parent.tail - parent.head).normalized()
            length = bone.length
            bone.tail = bone.head + parent_dir * length
            bone.roll = parent.roll

        def recurse(bone):
            align_to_parent(bone)
            for child in bone.children:
                recurse(child)

        total = 0
        for bone in selected:
            if bone.parent is None:
                continue
            recurse(bone)
            def count(b):
                n = 1
                for c in b.children:
                    n += count(c)
                return n
            total += count(bone)
        self.report({"INFO"}, f"Aligned {total} bones")
        return {"FINISHED"}


# ==========================================
# RE9 FakeBone Tools
# ==========================================

class RE9_OT_FakeBody_Process(bpy.types.Operator):
    """Create body End bones for RE9"""
    bl_idname = "re9.fake_body_process"
    bl_label = "Create Body End Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == "ARMATURE"]
        if len(selected) != 2:
            self.report({"ERROR"}, "Select two armatures (source -> target)")
            return {"CANCELLED"}

        SourceModel_Original = context.active_object
        RulerModel_Original = [o for o in selected if o != SourceModel_Original][0]

        bpy.ops.object.select_all(action="DESELECT")
        SourceModel_Original.select_set(True)
        context.view_layer.objects.active = SourceModel_Original
        bpy.ops.object.duplicate()
        SourceModel = context.active_object

        bpy.ops.object.select_all(action="DESELECT")
        RulerModel_Original.select_set(True)
        context.view_layer.objects.active = RulerModel_Original
        bpy.ops.object.duplicate()
        RulerModel = context.active_object

        BoneName = data_maps.FAKEBONE_BODY_BONES
        armature = RulerModel
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        for bone_name in BoneName:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                crc = bone.constraints.new("COPY_ROTATION")
                crc.target = SourceModel
                crc.subtarget = bone_name

        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints:
                b.constraints.remove(c)

        bpy.ops.pose.armature_apply()
        bpy.ops.object.mode_set(mode="EDIT")

        for b in [b for b in armature.data.edit_bones if "end" in b.name]:
            armature.data.edit_bones.remove(b)

        FakeName = data_maps.FAKEBONE_BODY_FAKES
        ParentName = data_maps.FAKEBONE_BODY_PARENTS

        for fake in FakeName:
            if fake not in armature.data.edit_bones:
                continue
            bone = armature.data.edit_bones[fake]
            for pname in ParentName[fake]:
                if pname not in armature.data.edit_bones:
                    continue
                suffix = "_end"
                if (pname[0] in ["L", "R"]) and len(ParentName[fake]) > 1:
                    suffix = f"_end{pname[0]}"
                new_bone = armature.data.edit_bones.new(bone.name + suffix)
                new_bone.head = bone.head
                new_bone.tail = bone.tail
                new_bone.roll = bone.roll
                new_bone.parent = armature.data.edit_bones[pname]
                new_bone.use_connect = bone.use_connect

        bpy.ops.object.mode_set(mode="POSE")
        for bone_name in BoneName:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                csc = bone.constraints.new("COPY_SCALE")
                csc.target = SourceModel
                csc.subtarget = bone_name
                clc = bone.constraints.new("COPY_LOCATION")
                clc.target = SourceModel
                clc.subtarget = bone_name

        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints:
                b.constraints.remove(c)
        bpy.ops.pose.armature_apply()

        bpy.ops.object.mode_set(mode="EDIT")
        for bone in list(armature.data.edit_bones):
            if "end" not in bone.name:
                armature.data.edit_bones.remove(bone)

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(SourceModel)

        self.report({"INFO"}, "Body End bones created")
        return {"FINISHED"}


class RE9_OT_FakeFingers_Process(bpy.types.Operator):
    """Create finger End bones for RE9"""
    bl_idname = "re9.fake_fingers_process"
    bl_label = "Create Finger End Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_armatures = [obj for obj in context.selected_objects if obj.type == "ARMATURE"]
        if len(selected_armatures) != 2:
            self.report({"ERROR"}, f"Select two armatures (have {len(selected_armatures)})")
            return {"CANCELLED"}

        SourceModel_Original = context.active_object
        RulerModel_Original = [obj for obj in selected_armatures if obj != SourceModel_Original][0]

        bpy.ops.object.select_all(action="DESELECT")
        SourceModel_Original.select_set(True)
        context.view_layer.objects.active = SourceModel_Original
        bpy.ops.object.duplicate()
        SourceModel = context.active_object

        bpy.ops.object.select_all(action="DESELECT")
        RulerModel_Original.select_set(True)
        context.view_layer.objects.active = RulerModel_Original
        bpy.ops.object.duplicate()
        RulerModel = context.active_object

        BoneName = data_maps.FAKEBONE_FINGER_BONES
        ParentName = {}

        armature = RulerModel
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        for bone_name in BoneName:
            if bone_name not in armature.pose.bones:
                continue
            bone = armature.pose.bones[bone_name]
            copy_rotation = bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = SourceModel
            copy_rotation.subtarget = bone_name

        for bone_name in BoneName:
            if bone_name in ("R_Arm_Hand", "L_Arm_Hand"):
                continue
            if bone_name not in armature.pose.bones:
                continue
            bone = armature.pose.bones[bone_name]
            pname = bone.parent.name
            if pname not in ParentName:
                ParentName[pname] = [bone_name]
            else:
                ParentName[pname].append(bone_name)

        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints:
                b.constraints.remove(c)
        bpy.ops.pose.armature_apply()

        bpy.ops.object.mode_set(mode="EDIT")

        for bone in list(armature.data.edit_bones):
            if "end" in bone.name:
                armature.data.edit_bones.remove(bone)

        for fake in ParentName:
            if fake not in armature.data.edit_bones:
                continue
            bone = armature.data.edit_bones[fake]
            for child_name in ParentName[fake]:
                if child_name not in armature.data.edit_bones:
                    continue
                # Determine suffix from child name
                # RE9 naming: L_Hand_IndexF_1 -> extract finger initial from the part after Hand_
                parts = child_name.split("_")
                # Find the finger type letter: ThumbF->T, IndexF->I, MiddleF->M, RingF->R, PinkyF->P, Palm->P
                finger_initial = ""
                for p in parts:
                    if p.startswith("Thumb"):
                        finger_initial = "T"
                        break
                    elif p.startswith("Index"):
                        finger_initial = "I"
                        break
                    elif p.startswith("Middle"):
                        finger_initial = "M"
                        break
                    elif p.startswith("Ring"):
                        finger_initial = "R"
                        break
                    elif p.startswith("Pinky"):
                        finger_initial = "P"
                        break
                    elif p == "Palm":
                        finger_initial = "P"
                        break

                if (child_name.startswith("L") or child_name.startswith("R")) and len(ParentName[fake]) > 1 and finger_initial:
                    suffix = f"_end{finger_initial}"
                else:
                    suffix = "_end"
                new_bone = armature.data.edit_bones.new(bone.name + suffix)
                new_bone.head = bone.head
                new_bone.tail = bone.tail
                new_bone.roll = bone.roll
                parent_bone = armature.data.edit_bones[child_name]
                new_bone.parent = parent_bone
                new_bone.use_connect = bone.use_connect

        bpy.ops.object.mode_set(mode="POSE")

        for bone_name in BoneName:
            if bone_name not in armature.pose.bones:
                continue
            bone = armature.pose.bones[bone_name]
            csc = bone.constraints.new("COPY_SCALE")
            csc.target = SourceModel
            csc.subtarget = bone_name
            clc = bone.constraints.new("COPY_LOCATION")
            clc.target = SourceModel
            clc.subtarget = bone_name

        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints:
                b.constraints.remove(c)
        bpy.ops.pose.armature_apply()

        bpy.ops.object.mode_set(mode="EDIT")
        for bone in list(armature.data.edit_bones):
            if "end" not in bone.name:
                armature.data.edit_bones.remove(bone)

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(SourceModel)

        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        context.view_layer.objects.active = armature

        self.report({"INFO"}, "Finger End bones created")
        return {"FINISHED"}


class RE9_OT_FakeBody_Merge(bpy.types.Operator):
    """Merge body End bones into target armature"""
    bl_idname = "re9.fake_body_merge"
    bl_label = "Merge Body Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == "ARMATURE"]
        if len(selected) != 2:
            return {"CANCELLED"}
        target = context.active_object
        end_arm = [o for o in selected if o != target][0]

        bpy.ops.object.select_all(action="DESELECT")
        target.select_set(True)
        end_arm.select_set(True)
        context.view_layer.objects.active = target
        bpy.ops.object.join()

        bpy.ops.object.mode_set(mode="EDIT")
        arm = target.data

        for bone in arm.edit_bones:
            if "_end" in bone.name:
                base = bone.name.split("_end")[0]
                if base in arm.edit_bones:
                    bone.parent = arm.edit_bones[base]
                    bone.use_connect = False

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, "Body bones merged")
        return {"FINISHED"}


class RE9_OT_FakeFingers_Merge(bpy.types.Operator):
    """Merge finger End bones and rebuild hierarchy"""
    bl_idname = "re9.fake_fingers_merge"
    bl_label = "Merge Finger Bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_armatures = [obj for obj in context.selected_objects if obj.type == "ARMATURE"]
        if len(selected_armatures) != 2:
            return {"CANCELLED"}

        target_armature = context.active_object
        end_armature = [obj for obj in selected_armatures if obj != target_armature][0]

        bpy.ops.object.select_all(action="DESELECT")
        target_armature.select_set(True)
        end_armature.select_set(True)
        context.view_layer.objects.active = target_armature
        bpy.ops.object.join()

        armature = target_armature
        bpy.ops.object.mode_set(mode="EDIT")

        fakebones = [b for b in armature.data.edit_bones if "_end" in b.name]
        for fakebone in fakebones:
            base_name = fakebone.name.split("_end")[0]
            if base_name in armature.data.edit_bones:
                fakebone.parent = armature.data.edit_bones[base_name]
                fakebone.use_connect = False

        parent_mappings = data_maps.FAKEBONE_FINGER_MERGE_MAP
        for child_name, parent_name in parent_mappings.items():
            if child_name in armature.data.edit_bones and parent_name in armature.data.edit_bones:
                child = armature.data.edit_bones[child_name]
                parent = armature.data.edit_bones[parent_name]
                child.parent = parent
                child.use_connect = False

        finger_patterns = data_maps.FAKEBONE_FINGER_PATTERNS
        for finger_base, num_segments in finger_patterns:
            for i in range(2, num_segments + 1):
                child_name = f"{finger_base}{i}"
                parent_name = f"{finger_base}{i-1}_end"
                if child_name in armature.data.edit_bones and parent_name in armature.data.edit_bones:
                    child = armature.data.edit_bones[child_name]
                    parent = armature.data.edit_bones[parent_name]
                    child.parent = parent
                    child.use_connect = False

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, "Finger bones merged")
        return {"FINISHED"}


class RE9_OT_AlignBones(bpy.types.Operator):
    """Fully align matching bones between two armatures"""
    bl_idname = "re9.align_bones_full"
    bl_label = "Full Align"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == "ARMATURE"]
        if len(selected) != 2:
            return {"CANCELLED"}
        target = active_obj
        source = [o for o in selected if o != target][0]

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.update()

        src_data = {}
        s_mat = source.matrix_world
        for b in source.data.bones:
            src_data[b.name] = {"head": s_mat @ b.head_local.copy(), "tail": s_mat @ b.tail_local.copy()}

        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode="EDIT")
        t_mat_inv = target.matrix_world.inverted()

        count = 0
        for b in target.data.edit_bones:
            if b.name in src_data:
                old_head = b.head.copy()
                new_head = t_mat_inv @ src_data[b.name]["head"]
                b.head = new_head
                b.tail = t_mat_inv @ src_data[b.name]["tail"]
                bone_utils.propagate_movement(b, new_head - old_head)
                count += 1

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, f"Fully aligned {count} bones")
        return {"FINISHED"}


class RE9_OT_AlignBones_Pos(bpy.types.Operator):
    """Align only bone positions (preserve direction)"""
    bl_idname = "re9.align_bones_pos"
    bl_label = "Position Only"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == "ARMATURE"]
        if len(selected) != 2:
            return {"CANCELLED"}
        target = active_obj
        source = [o for o in selected if o != target][0]

        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.update()

        src_heads = {b.name: source.matrix_world @ b.head_local for b in source.data.bones}

        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode="EDIT")
        t_mat_inv = target.matrix_world.inverted()

        count = 0
        for b in target.data.edit_bones:
            if b.name in src_heads:
                old_head = b.head.copy()
                new_head = t_mat_inv @ src_heads[b.name]
                orig_vec = b.tail - b.head
                b.head = new_head
                b.tail = new_head + orig_vec
                bone_utils.propagate_movement(b, new_head - old_head)
                count += 1

        bpy.ops.object.mode_set(mode="OBJECT")
        self.report({"INFO"}, f"Position aligned {count} bones")
        return {"FINISHED"}


classes = [
    RE9_OT_SyncChildOrientation,
    RE9_OT_FakeBody_Process, RE9_OT_FakeFingers_Process,
    RE9_OT_FakeBody_Merge, RE9_OT_FakeFingers_Merge,
    RE9_OT_AlignBones, RE9_OT_AlignBones_Pos,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)