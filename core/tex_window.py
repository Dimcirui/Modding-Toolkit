"""The tool window: an Image Editor in a window of its own, with a sidebar
and a live preview of what the tool will write.

Used by 贴图处理 (core/tex_convert_base.py).  This module owns the window, the
preview image and the redraw-driven recompute.  Previews are display-only --
nothing here is written out, which keeps them clear of the ``Image.save()``
value mangling the export avoids.
"""
import os

import bpy

from .mdf_tex_processor_base import image_to_array, array_to_image

PREVIEW_SIZE = 512
PREVIEW_IMAGE = "MT Tex Preview"
INPUT_IMAGE = "MT Tex Input"
WINDOW_TAG = "mt_tool_window"
#: The sidebar tab the tools live under, in the tool window.
PANEL_CATEGORY = "MOD Toolkit"

#: tag -> key of what the preview image currently holds
_SHOWN = {}
#: (abspath, mtime, size) -> downscaled float array; a handful of entries at most
_SMALL = {}
_PENDING = set()


# ── Window ─────────────────────────────────────────────────────────────────────
#
# The window is found again by a tag on its screen, naming the tool whose
# sidebar it shows.  The tag is saved with the file, so a reopened .blend still
# knows the window.

def tag_window(wm, tag):
    """The open tool window showing *tag*'s sidebar, or None."""
    for win in wm.windows:
        if win.screen and win.screen.get(WINDOW_TAG) == tag:
            return win
    return None


def image_space(win):
    area = next((a for a in win.screen.areas if a.type == 'IMAGE_EDITOR'), None) if win else None
    return area, (area.spaces.active if area else None)


def _select_tab(wm, win, area, tag):
    # The sidebar's tab can only be chosen once it has drawn: until then
    # active_panel_category reads 'UNSUPPORTED' and assigning it fails (5.1).
    tries = 50                  # x 0.2 s: a fresh window can take seconds to draw

    def _pick_tab():
        nonlocal tries
        tries -= 1
        if tag_window(wm, tag) != win:     # bpy wrappers: compare, not `is`
            return None
        region = next((r for r in area.regions if r.type == 'UI'), None)
        try:
            region.active_panel_category = PANEL_CATEGORY
            return None
        except Exception:
            return 0.2 if tries > 0 else None    # not drawn yet; or no such API
    bpy.app.timers.register(_pick_tab, first_interval=0.1)


def open_tool_window(context, tag):
    """Open the tool window with *tag*'s sidebar; returns a note for the report
    ('' when a window was opened).

    ``wm.window_new`` copies only the area it is called from, so the window
    starts with one area -- the same route EFX Editor's UVS editor takes.
    """
    wm = context.window_manager
    if tag_window(wm, tag) is not None:
        return 'window_open'            # Blender has no call to raise a window
    bpy.ops.wm.window_new()
    win = wm.windows[-1]
    win.screen[WINDOW_TAG] = tag
    area = win.screen.areas[0]
    area.type = 'IMAGE_EDITOR'
    space = area.spaces.active
    space.mode = 'VIEW'
    space.show_region_ui = True
    _SHOWN.pop(tag, None)
    _select_tab(wm, win, area, tag)
    return ''


# ── Inputs ─────────────────────────────────────────────────────────────────────

def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def load_small(path, size=PREVIEW_SIZE):
    """*path*'s pixels, raw (Non-Color), fitted inside size x size."""
    path = bpy.path.abspath(path)
    key = (os.path.normcase(path), _mtime(path), size)
    if key[1] is None:
        return None
    if key in _SMALL:
        return _SMALL[key]
    img = bpy.data.images.load(path, check_existing=False)
    try:
        img.colorspace_settings.name = 'Non-Color'
        w, h = img.size
        if not w or not h:
            return None
        scale = min(1.0, size / max(w, h))
        if scale < 1.0:
            img.scale(max(1, round(w * scale)), max(1, round(h * scale)))
        arr = image_to_array(img)
    finally:
        bpy.data.images.remove(img)
    if len(_SMALL) > 24:
        _SMALL.clear()
    _SMALL[key] = arr
    return arr


# ── Showing it ─────────────────────────────────────────────────────────────────

def show_array(win, arr, colour=False):
    """Put *arr* in *win*'s image editor; None clears it, so a stale picture
    is never left up looking like the current one."""
    _area, space = image_space(win)
    if arr is None:
        if space is not None:
            space.image = None
        return None
    img = bpy.data.images.get(PREVIEW_IMAGE)
    h, w = arr.shape[:2]
    if img is None or tuple(img.size) != (w, h):
        if img is not None:
            bpy.data.images.remove(img)
        # Byte buffer, so the colour space below decides how values display:
        # sRGB for colour data, Non-Color (raw) for masks and normals.
        img = bpy.data.images.new(PREVIEW_IMAGE, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'      # alpha is data here, not coverage
    array_to_image(img, arr)
    img.update()
    if space is not None:
        space.image = img
    return img


def show_file(win, path, colour=False):
    """Show a source file as itself, full size; returns a note."""
    path = bpy.path.abspath(path) if path else ""
    if not path or not os.path.isfile(path):
        show_array(win, None)
        return 'no_input'
    # Our own copy, not check_existing: setting its colour space must not
    # touch an image the user's materials already use.
    old = bpy.data.images.get(INPUT_IMAGE)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = INPUT_IMAGE
    if not colour:
        img.colorspace_settings.name = 'Non-Color'
    _area, space = image_space(win)
    if space is not None:
        space.image = img
    return ''


def schedule(tag, key, run):
    """From a panel's draw: when *key* (everything the preview depends on)
    differs from what is showing, recompute via *run(context)* on a timer --
    a draw callback cannot write image data itself."""
    if tag in _PENDING or key == _SHOWN.get(tag):
        return
    _PENDING.add(tag)

    def _run():
        _PENDING.discard(tag)
        try:
            run(bpy.context)
        except Exception as err:
            print(f"[MT Tex] preview failed: {err}")
        _SHOWN[tag] = key               # even on failure: don't retry every redraw
        return None
    bpy.app.timers.register(_run, first_interval=0.05)
