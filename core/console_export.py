"""Keep the Windows system console open for the duration of a batch export.

RE Mesh Editor and MHW Model Editor each drive Window > Toggle System Console
themselves around their own import/export calls (gated by a per-addon "Show
Console" preference). ``bpy.ops.wm.console_toggle()`` has no way to query
whether the console is currently visible -- both addons' own docs call this
out as a Blender limitation -- so it's a blind flip: call it once to "open",
call it again to "close".

If our batch export forces the console open and then calls into one of those
addons with their own toggle still enabled, their "open" call actually closes
it (it wasn't closed), and their "close" call reopens it. Over a multi-file
batch the console would flicker open/closed once per file instead of staying
up, defeating the point of watching it live.

The fix: suspend those addons' own toggle for the duration of our batch (by
flipping their preference off and restoring it after), and do our own single
open that is never toggled closed again.
"""
import sys
import bpy
from contextlib import contextmanager

# bl_info["name"] of addons known to blindly console_toggle() around their own
# import/export operators, mapped to the preference that gates it.
_EXTERNAL_CONSOLE_TOGGLERS = {
    "RE Mesh Editor": "showConsole",
    "MHW Model Editor": "showConsole",
}


def get_preferences(context=None):
    """This addon's own AddonPreferences instance."""
    context = context or bpy.context
    addon_key = __name__.split('.')[0]
    return context.preferences.addons[addon_key].preferences


def _find_external_toggler_prefs():
    """(preferences, attr_name) for every installed addon known to do its own
    blind console_toggle(), so it can be suspended for our batch."""
    for mod_key in bpy.context.preferences.addons.keys():
        mod = sys.modules.get(mod_key)
        bl_info = getattr(mod, "bl_info", None) if mod else None
        name = bl_info.get("name") if bl_info else None
        attr = _EXTERNAL_CONSOLE_TOGGLERS.get(name)
        if attr:
            prefs = bpy.context.preferences.addons[mod_key].preferences
            if hasattr(prefs, attr):
                yield prefs, attr


@contextmanager
def kept_open_for_export(enabled):
    """Open the system console for a batch export and leave it open.

    No-op if *enabled* is false or we're not on Windows (console_toggle is a
    Windows-only concept). Like RE Mesh Editor / MHW Model Editor, this can't
    detect whether the console is already open, so if it happens to already
    be open when the batch starts, this will close it instead -- the same
    limitation those addons already live with.
    """
    if not enabled or sys.platform != 'win32':
        yield
        return

    saved = [(prefs, attr, getattr(prefs, attr))
             for prefs, attr in _find_external_toggler_prefs()]
    for prefs, attr, _ in saved:
        setattr(prefs, attr, False)
    try:
        bpy.ops.wm.console_toggle()
        yield
    finally:
        for prefs, attr, value in saved:
            setattr(prefs, attr, value)
