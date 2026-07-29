import bpy

from .mdf_generator import MHWS_GEN_GAME
from ...core.mdf_generator_base import get_preset_dir_for_game, preset_has_emissive_slots
from ...core.i18n import T

GENERATOR_WINDOW_WIDTH = 580
_SETTINGS_ATTR = "mhws_mdf_generator"

_STRAT_LABEL_KEYS = {
    'color':     "mhws.mdf_generator_ui.strat_color",
    'normal':    "mhws.mdf_generator_ui.strat_normal",
    'roughness': "mhws.mdf_generator_ui.strat_roughness",
    'metallic':  "mhws.mdf_generator_ui.strat_metallic",
    'alpha':     "mhws.mdf_generator_ui.strat_alpha",
    'emissive':  "mhws.mdf_generator_ui.strat_emissive",
}

_STRAT_ICONS = {
    'Direct': 'IMAGE_DATA',
    'Solid':  'MESH_PLANE',
    'Bake':   'RENDER_STILL',
    '?':      'QUESTION',
}


class MHWS_OT_MdfGeneratorDialog(bpy.types.Operator):
    bl_idname  = "mhws.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.mdf_generator_ui.dialog_desc")

    def invoke(self, context, event):
        settings = context.scene.mhws_mdf_generator
        # Auto-refresh if collection is set but list is empty
        if settings.mesh_collection and not settings.material_list:
            bpy.ops.mhws.mdf_gen_refresh()
        return context.window_manager.invoke_props_dialog(
            self, width=GENERATOR_WINDOW_WIDTH)

    def execute(self, context):
        bpy.ops.mhws.mdf_gen_process()
        return {'FINISHED'}

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        settings = scene.mhws_mdf_generator

        # ── Mesh collection + refresh ──────────────────────────────────────────
        row = layout.row(align=True)
        row.prop(settings, "mesh_collection", text="Mesh Collection")
        row.operator("mhws.mdf_gen_refresh", text="", icon='FILE_REFRESH')

        # ── Smart selection ───────────────────────────────────────────────────
        row = layout.row(align=True)
        row.operator("mhws.select_same_material", icon='MATERIAL')

        # ── Mod root ───────────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.operator("mhws.set_natives_root", text="Mod Root", icon='FILEBROWSER')
        natives_root = scene.get("mhws_natives_root", "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="Not set", icon='ERROR')

        # ── MDF collection name ────────────────────────────────────────────────
        row = layout.row(align=True)
        row.label(text="MDF Collection:")
        row.prop(settings, "mdf_collection_name", text="")
        if not settings.mdf_collection_name.strip() and settings.mesh_collection:
            mc       = settings.mesh_collection.name
            auto_name = (mc.replace('.mesh', '.mdf2')
                         if '.mesh' in mc else mc + ".mdf2")
            layout.row().label(
                text=f"    {T('mhws.mdf_generator_ui.auto_name').format(name=auto_name)}", icon='INFO')

        # ── Base path ──────────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.label(text="natives/STM/Art/")
        row.prop(settings, "texture_base_path", text="")
        if not settings.texture_base_path.strip():
            layout.row().label(text="    e.g. Author/CharacterName/", icon='INFO')

        layout.prop(settings, "flip_normal_g", text=T("mhws.mdf_generator.flip_normal_g_name"))

        # ── Preset dir status ──────────────────────────────────────────────────
        preset_dir = get_preset_dir_for_game(MHWS_GEN_GAME)
        if not preset_dir:
            layout.separator()
            layout.label(text=T("mhws.mdf_generator_ui.preset_dir_not_found"), icon='ERROR')

        # ── Material list ──────────────────────────────────────────────────────
        if not settings.material_list:
            layout.separator()
            layout.label(text=T("mhws.mdf_generator_ui.select_mesh_collection_hint"), icon='INFO')
            return

        layout.separator()

        for mat_entry in settings.material_list:
            box = layout.box()

            # Header row: expand toggle | material name | preset selector
            row = box.row(align=True)
            icon = 'TRIA_DOWN' if mat_entry.expanded else 'TRIA_RIGHT'
            row.prop(mat_entry, "expanded", text="", icon=icon, emboss=False)
            row.label(text=mat_entry.blender_material, icon='MATERIAL')
            row.prop(mat_entry, "material_preset", text="")

            if not mat_entry.expanded:
                continue

            # Expanded: show per-channel strategy
            strat_box = box.box()
            strat_box.label(text=T("mhws.mdf_generator_ui.node_tree_analysis"), icon='NODETREE')
            grid = strat_box.grid_flow(row_major=True, columns=3,
                                       even_columns=True, align=True)
            for pt, label_key in _STRAT_LABEL_KEYS.items():
                strat       = getattr(mat_entry, f"strat_{pt}", "?")
                icon        = _STRAT_ICONS.get(strat, 'QUESTION')
                native_size = getattr(mat_entry, f"native_size_{pt}", 0)
                override    = getattr(mat_entry, f"bake_size_{pt}", 0)
                cell = grid.row(align=True)
                cell.label(text=f"{T(label_key)}:", icon='BLANK1')
                cell.label(text=strat, icon=icon)
                if strat != 'Solid' and native_size > 0:
                    btn_label = f"→{override}px" if override > 0 and override != native_size else ""
                    op = cell.operator("mhw.set_channel_size", text=btn_label,
                                       icon='FULLSCREEN_ENTER', emboss=True)
                    op.settings_attr = _SETTINGS_ATTR
                    op.mat_name      = mat_entry.blender_material
                    op.channel       = pt
                    op.native_size   = native_size

            # A packed shader already carries the AO map and its strength, and toon
            # mode belongs to the emissive shaders it replaces -- so those options are
            # hidden and a choice of which of its two panels to read appears instead.
            if getattr(mat_entry, "uses_packed_shader", False):
                row = box.row(align=True)
                # A plain prop(expand=True) on this *dynamic* items= enum renders
                # blank button text in Blender, so draw it as two toggle buttons.
                op = row.operator("mhw.set_shader_source",
                                   text=T("core.mdf_generator_base.shader_source_pbr"),
                                   depress=(mat_entry.shader_source == 'PBR'))
                op.settings_attr = _SETTINGS_ATTR
                op.mat_name      = mat_entry.blender_material
                op.value         = 'PBR'
                op = row.operator("mhw.set_shader_source",
                                   text=T("core.mdf_generator_base.shader_source_slot"),
                                   depress=(mat_entry.shader_source == 'SLOT'))
                op.settings_attr = _SETTINGS_ATTR
                op.mat_name      = mat_entry.blender_material
                op.value         = 'SLOT'
                box.prop(mat_entry, "generate_mipmaps", text=T("mhws.mdf_generator.generate_mipmaps_name"))
                box.prop(mat_entry, "skip_textures", text=T("mhws.mdf_generator.skip_textures_name"))
            else:
                if preset_has_emissive_slots(mat_entry.material_preset):
                    box.prop(mat_entry, "use_toon", text=T("mhws.mdf_generator.use_toon_name"))
                box.prop(mat_entry, "generate_mipmaps", text=T("mhws.mdf_generator.generate_mipmaps_name"))
                box.prop(mat_entry, "skip_textures", text=T("mhws.mdf_generator.skip_textures_name"))
                box.prop(mat_entry, "use_ao", text=T("mhws.mdf_generator.use_ao_name"))
                if mat_entry.use_ao:
                    box.prop(mat_entry, "ao_image", text=T("ui.prop.ao_image"))


classes = [MHWS_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
