from . import mhwi, mhws, re4, re9

modules = [
    mhwi,
    mhws,
    re4,
    re9,
]

def register():
    for mod in modules:
        mod.register()

def unregister():
    for mod in reversed(modules):
        mod.unregister()