from . import operators, tex_config


def register():
    operators.register()
    tex_config.register()


def unregister():
    tex_config.unregister()
    operators.unregister()
