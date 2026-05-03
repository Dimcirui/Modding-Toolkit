from . import operators, batch_export, batch_export_ui, batch_import, batch_import_ui, mrl3_tex_processor, mrl3_tex_processor_ui, mrl3_generator, mrl3_generator_ui

def register():
    operators.register()
    batch_export.register()
    batch_export_ui.register()
    batch_import.register()
    batch_import_ui.register()
    mrl3_tex_processor.register()
    mrl3_tex_processor_ui.register()
    mrl3_generator.register()
    mrl3_generator_ui.register()

def unregister():
    mrl3_generator_ui.unregister()
    mrl3_generator.unregister()
    mrl3_tex_processor_ui.unregister()
    mrl3_tex_processor.unregister()
    batch_import_ui.unregister()
    batch_import.unregister()
    batch_export_ui.unregister()
    batch_export.unregister()
    operators.unregister()