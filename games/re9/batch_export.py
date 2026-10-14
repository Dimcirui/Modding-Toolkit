"""RE9 scheme batch export -- the exporter itself lives in core/scheme_batch_export.py,
which RE9 shares with Onimusha.  This module holds RE9's spec and its mod-root picker.

Operator ids (``re9.batch_export`` ...) and scene keys (``re9ex_`` / ``re9en_`` /
``re9sg_`` / ``re9se_`` / ``re9_use_simplified``) are the ones RE9 has always used, so
bindings saved in existing .blend files still resolve.
"""

import bpy

from ...core.i18n import T
from ...core import mod_root
from ...core.scheme_batch_export import (
    SchemeExportSpec, SchemeExporter,
    # Borrowed by games/mhws/batch_export.py under these names.
    do_export_mesh as _do_export_mesh, do_export_mdf2 as _do_export_mdf2,
    do_export_sfur as _do_export_sfur, do_export_fbxskel as _do_export_fbxskel,
    do_export_chain2 as _do_export_chain2, do_export_clsp as _do_export_clsp,
)

SPEC = SchemeExportSpec(
    code="RE9", op_prefix="re9", key_prefix="re9", title="RE9 Batch Exporter",
    scheme_dir="re9", blank_dir="re9",
    natives_root_key="re9_natives_root",
    scheme_setting="re9_export_scheme", blank_setting="re9_use_blank_export",
    fbxskel_base="stm/character", native_skeleton_dir="re9",
    mdf_active_game="RE9", check_game="RE9", autofix_game="RE9",
)
EXPORTER = SchemeExporter(SPEC)

get_schemes_callback = EXPORTER.schemes_callback
_load_scheme = EXPORTER.load_scheme
resolve_mesh_mdf2 = EXPORTER.resolve_mesh_mdf2
bound_pairs = EXPORTER.bound_pairs


class RE9_OT_SetNativesRoot(bpy.types.Operator):
    bl_idname = "re9.set_natives_root"
    bl_label = "Set Natives Root"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("re9.batch_export.set_natives_root_desc")

    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        # A root picked one level too deep (…/natives, …/natives/STM) or one
        # too shallow (the folder holding the mod) is corrected here; see
        # core/mod_root.py for the rules.
        mod_root.clear_cache()
        path, status = mod_root.normalize(self.directory.rstrip("/\\"))
        context.scene["re9_natives_root"] = path
        if status == mod_root.AMBIGUOUS:
            self.report({'WARNING'}, T("core.mod_root.ambiguous"))
        else:
            self.report({'INFO'}, f"RE9 Mod root: {path}")
        return {'FINISHED'}


classes = [
    RE9_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
