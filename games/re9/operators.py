import bpy


class RE9_OT_SyncChildOrientation(bpy.types.Operator):
    """Select bones to sync: each selected bone (and its descendants) will align to its PARENT's orientation.\nDo not select a bone AND its descendant at the same time"""
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

        # Check: no selected bone should be a descendant of another selected bone
        selected_set = set(b.name for b in selected)
        for bone in selected:
            parent = bone.parent
            while parent:
                if parent.name in selected_set:
                    self.report({"ERROR"}, f"'{bone.name}' is a descendant of selected bone '{parent.name}'. Please only select the first bone in each chain")
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
                self.report({"WARNING"}, f"'{bone.name}' has no parent, skipped")
                continue
            # Align this bone and all its descendants to their respective parents
            recurse(bone)
            # Count this bone + all descendants
            def count(b):
                n = 1
                for c in b.children:
                    n += count(c)
                return n
            total += count(bone)

        self.report({"INFO"}, f"Aligned {total} bones to their parent orientation")
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
