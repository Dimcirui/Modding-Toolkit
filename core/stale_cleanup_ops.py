"""Operator + confirmation dialog for the leftover-file cleanup.

One operator, not two: the scan runs in ``invoke`` and the dialog it opens *is* the
report, so there is no cached scan result to go stale between "check" and "delete" --
and no state to get wrong if the user cancels.  The full list always goes to the system
console, because a dialog cannot show 13000 paths and the one thing a user must be able
to do before deleting is read what will go.

Planning lives in ``core/stale_cleanup.py`` (no ``bpy``); this file only asks.
"""

import bpy

from .i18n import T
from . import stale_cleanup


def _mb(n):
    return f"{n / 1048576.0:.1f}"


class MODDER_OT_CleanStaleFiles(bpy.types.Operator):
    bl_idname = "modder.clean_stale_files"
    bl_label = "Clean Up Leftover Files"
    #: No UNDO: this deletes files on disk, which the undo stack cannot take back.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.stale_cleanup_ops.desc")

    def invoke(self, context, event):
        self._manifest = stale_cleanup.read_manifest()
        if self._manifest is None:
            self.report({'ERROR'}, T("core.stale_cleanup_ops.no_manifest"))
            return {'CANCELLED'}

        self._stale, self._kept, self._pycache, self._bytes = \
            stale_cleanup.find_stale(manifest=self._manifest)
        if not self._stale and not self._pycache:
            self.report({'INFO'}, T("core.stale_cleanup_ops.none_found"))
            return {'CANCELLED'}

        print(f"[Modding-Toolkit] leftover scan: {len(self._stale)} file(s), "
              f"{_mb(self._bytes)} MB, {len(self._pycache)} __pycache__ folder(s)")
        for rel in self._stale:
            print(f"[Modding-Toolkit]   stale: {rel}")
        for rel in self._kept:
            print(f"[Modding-Toolkit]   kept (assets/presets/): {rel}")
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        col = self.layout.column()
        col.label(text=T("core.stale_cleanup_ops.found").format(
            n=len(self._stale), mb=_mb(self._bytes), pyc=len(self._pycache)),
            icon='TRASH')

        # Top-level grouping rather than the raw list: 13000 paths do not fit, and
        # "which part of the addon" is what tells the user whether this looks right.
        groups = {}
        for rel in self._stale:
            groups[rel.split("/")[0]] = groups.get(rel.split("/")[0], 0) + 1
        box = col.box().column(align=True)
        for top, n in sorted(groups.items(), key=lambda kv: -kv[1])[:12]:
            box.label(text=f"{top}   ({n})")
        extra = len(groups) - 12
        if extra > 0:
            box.label(text=T("core.stale_cleanup_ops.and_more").format(n=extra))

        if self._kept:
            col.separator()
            col.label(text=T("core.stale_cleanup_ops.kept_note").format(n=len(self._kept)),
                      icon='INFO')

        col.separator()
        col.label(text=T("core.stale_cleanup_ops.confirm"), icon='ERROR')

    def execute(self, context):
        files, dirs, errors = stale_cleanup.delete(self._stale, self._pycache)
        for e in errors:
            print(f"[Modding-Toolkit] could not delete {e}")
        if errors:
            self.report({'WARNING'}, T("core.stale_cleanup_ops.done_with_errors").format(
                files=files, n=len(errors)))
        else:
            self.report({'INFO'}, T("core.stale_cleanup_ops.done").format(
                files=files, dirs=dirs, mb=_mb(self._bytes)))
        return {'FINISHED'}


def draw_preferences_row(layout):
    """The row MT_Preferences.draw puts under the updater UI."""
    box = layout.box()
    box.label(text=T("core.stale_cleanup_ops.hint"), icon='INFO')
    box.operator(MODDER_OT_CleanStaleFiles.bl_idname,
                 text=T("core.stale_cleanup_ops.button"), icon='TRASH')


classes = [MODDER_OT_CleanStaleFiles]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
