from . import main_panel
from . import editor_panel

modules = [
    main_panel,
    editor_panel,
]

def register():
    for mod in modules:
        mod.register()

def unregister():
    for mod in reversed(modules):
        mod.unregister()