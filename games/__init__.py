from . import mhwi, mhws, mhrs, re4, re9, oni

modules = [
    mhwi,
    mhws,
    mhrs,
    re4,
    re9,
    oni,
]

def register():
    for mod in modules:
        mod.register()

def unregister():
    for mod in reversed(modules):
        mod.unregister()