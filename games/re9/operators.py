import bpy


class RE9_OT_SyncChildOrientation(bpy.types.Operator):
    """Sync child bone orientations to be parallel with their direct parent.
Head position and bone length preserved, roll synced from parent.
Select one bone as source in Edit Mode"""
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
        source = obj.data.edit_bones.active

        if source is None:
            self.report({"ERROR"}, "No active bone selected")
            return {"CANCELLED"}

        def count_children(b):
            n = 0
            for c in b.children:
                n += 1 + count_children(c)
            return n

        total = count_children(source)
        if total == 0:
            self.report({"INFO"}, "No children found")
            return {"FINISHED"}

        def align_to_parent(bone):
            parent = bone.parent
            if parent is None:
                return
            parent_dir = (parent.tail - parent.head).normalized()
            length = bone.length
            bone.tail = bone.head + parent_dir * length
            bone.roll = parent.roll

        def recurse(bone):
            for child in bone.children:
                align_to_parent(child)
                recurse(child)

        recurse(source)

        self.report({"INFO"}, f"Aligned {total} child bones")
        return {"FINISHED"}


classes = [
    RE9_OT_SyncChildOrientation,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
