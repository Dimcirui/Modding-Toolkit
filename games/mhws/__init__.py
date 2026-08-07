from . import operators, batch_export, batch_export_ui, batch_import, batch_import_ui, mdf_tex_processor, mdf_tex_processor_ui, mdf_generator, mdf_generator_ui, mdf_material_convert

def register():
    operators.register()
    batch_export.register()
    batch_export_ui.register()
    batch_import.register()
    batch_import_ui.register()
    mdf_tex_processor.register()
    mdf_tex_processor_ui.register()
    mdf_generator.register()
    mdf_generator_ui.register()
    mdf_material_convert.register()

def unregister():
    mdf_material_convert.unregister()
    mdf_generator_ui.unregister()
    mdf_generator.unregister()
    mdf_tex_processor_ui.unregister()
    mdf_tex_processor.unregister()
    batch_import_ui.unregister()
    batch_import.unregister()
    batch_export_ui.unregister()
    batch_export.unregister()
    operators.unregister()
