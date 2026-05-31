try:
    from bpy.app.translations import pgettext as _pgt
    _ = _pgt if _pgt is not None else (lambda x: x)
except (ImportError, AttributeError):
    _ = lambda x: x
