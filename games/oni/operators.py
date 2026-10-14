import bpy

from ...core.i18n import T
from ...core import mod_root


class ONI_OT_SetNativesRoot(bpy.types.Operator):
    """The Onimusha mod root, read by the cross-game material port as the
    destination its textures are written under."""
    bl_idname = "oni.set_natives_root"
    bl_label = "Set Natives Root"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("oni.operators.set_natives_root_desc")

    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # Same normalisation every other game's root picker applies; see
        # core/mod_root.py for the rules.
        mod_root.clear_cache()
        path, status = mod_root.normalize(self.directory.rstrip("/\\"))
        context.scene["oni_natives_root"] = path
        if status == mod_root.AMBIGUOUS:
            self.report({'WARNING'}, T("core.mod_root.ambiguous"))
        else:
            self.report({'INFO'}, f"ONI Mod root: {path}")
        return {'FINISHED'}


classes = [ONI_OT_SetNativesRoot]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
