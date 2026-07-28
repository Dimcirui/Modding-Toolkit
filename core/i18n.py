"""
core/i18n.py — bilingual (EN/中文) infrastructure, addon-owned switch.

Design
------
- Language state is a module-level global `_LANG` ('EN' / 'ZH'), not tied to
  Blender's own Interface Language preference — toggling it never touches
  Blender's native UI, only this addon's own panels.
- Persistence: a plain text file in Blender's user config dir
  (modding_toolkit_lang.txt), read back in register(), written on toggle.
- First run (no config file yet): infer a sensible default from Blender's
  current interface locale (bpy.app.translations.locale) rather than
  hardcoding one language. After this one-time inference the choice is
  fully addon-owned.
- T(key) looks up STRINGS by the current language; missing language falls
  back to the other language, then to the raw key itself (so a missed
  migration is visible/grep-able instead of silently wrong).
- STRINGS itself lives in core/i18n_strings/ (split by area) and is merged
  here at import time.
"""

import os

import bpy
from bpy.props import StringProperty

from .i18n_strings import STRINGS


_LANG = "EN"          # current language: 'EN' / 'ZH'
_DEFAULT_LANG = "EN"


def _config_path() -> str:
    """Language preference file path (user config dir, stable across Blender versions)."""
    try:
        cfg = bpy.utils.user_resource("CONFIG")
    except Exception:
        cfg = os.path.expanduser("~")
    return os.path.join(cfg, "modding_toolkit_lang.txt")


def _infer_default_lang() -> str:
    """First-run only: guess a starting language from Blender's own interface
    locale, without ever consulting it again afterward."""
    try:
        locale = bpy.app.translations.locale
    except Exception:
        locale = ""
    return "ZH" if locale.lower().startswith("zh") else _DEFAULT_LANG


def load_lang() -> str:
    """Read back the persisted language preference (called from register())."""
    global _LANG
    path = _config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            val = f.read().strip().upper()
        _LANG = val if val in ("EN", "ZH") else _DEFAULT_LANG
    except Exception:
        _LANG = _infer_default_lang()
    return _LANG


def save_lang(lang: str) -> None:
    """Write the language preference to the config file."""
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            f.write(lang)
    except Exception:
        pass


def get_lang() -> str:
    """Return the current language, 'EN' / 'ZH'."""
    return _LANG


def set_lang(lang: str) -> None:
    """Set the current language and persist it."""
    global _LANG
    _LANG = lang if lang in ("EN", "ZH") else _DEFAULT_LANG
    save_lang(_LANG)


def T(key: str) -> str:
    """
    Look up `key` in STRINGS for the current language.
    Falls back to the other language, then to the key itself
    (missing keys surface visibly instead of silently showing the wrong text).
    """
    entry = STRINGS.get(key)
    if entry is None:
        return key
    other = "ZH" if _LANG == "EN" else "EN"
    return entry.get(_LANG) or entry.get(other) or key


# ─────────────────────────────────────────────────────────────────────────────
# Language toggle operator + UI helper
# ─────────────────────────────────────────────────────────────────────────────

class MT_OT_set_language(bpy.types.Operator):
    """Toggle the Modding Toolkit UI language between English and 中文"""

    bl_idname = "mt.set_language"
    bl_label = "Modding Toolkit Language"
    bl_options = {"REGISTER"}

    lang: StringProperty(default="")  # 'EN' / 'ZH' / '' = toggle

    @classmethod
    def description(cls, context, properties):
        return T("i18n.toggle_tip")

    def execute(self, context):
        target = self.lang
        if target not in ("EN", "ZH"):
            target = "ZH" if get_lang() == "EN" else "EN"
        set_lang(target)
        try:
            for win in context.window_manager.windows:
                for area in win.screen.areas:
                    area.tag_redraw()
        except Exception:
            pass
        return {"FINISHED"}


def draw_language_toggle(layout):
    """Draw a [English][中文] row, highlighting the current language."""
    cur = get_lang()
    row = layout.row(align=True)
    op_en = row.operator("mt.set_language", text="English", depress=(cur == "EN"))
    op_en.lang = "EN"
    op_zh = row.operator("mt.set_language", text="中文", depress=(cur == "ZH"))
    op_zh.lang = "ZH"


# ─────────────────────────────────────────────────────────────────────────────
# register / unregister
# ─────────────────────────────────────────────────────────────────────────────

def register():
    bpy.utils.register_class(MT_OT_set_language)
    load_lang()


def unregister():
    bpy.utils.unregister_class(MT_OT_set_language)
