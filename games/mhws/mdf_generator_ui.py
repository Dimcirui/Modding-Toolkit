import bpy

from .mdf_generator import MHWS_GEN_GAME
from ...core.mdf_generator_base import get_preset_dir_for_game, preset_has_emissive_slots

GENERATOR_WINDOW_WIDTH = 580

_STRAT_LABELS = {
    'color':     "基础色",
    'normal':    "法线",
    'roughness': "粗糙度",
    'metallic':  "金属度",
    'alpha':     "Alpha",
    'emissive':  "自发光",
}

_STRAT_ICONS = {
    'Direct': 'IMAGE_DATA',
    'Solid':  'MESH_PLANE',
    'Bake':   'RENDER_STILL',
    '?':      'QUESTION',
}


class MHWS_OT_MdfGeneratorDialog(bpy.types.Operator):
    """MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，并在材质里连好 Principled BSDF"""
    bl_idname  = "mhws.mdf_generator_dialog"
    bl_label   = "MDF2 Generator"
    bl_options = {'REGISTER'}

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
            layout.row().label(text=f"    自动: {auto_name}", icon='INFO')

        # ── Base path ──────────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.label(text="natives/STM/Art/")
        row.prop(settings, "texture_base_path", text="")
        if not settings.texture_base_path.strip():
            layout.row().label(text="    e.g. Author/CharacterName/", icon='INFO')

        # ── Preset dir status ──────────────────────────────────────────────────
        preset_dir = get_preset_dir_for_game(MHWS_GEN_GAME)
        if not preset_dir:
            layout.separator()
            layout.label(text="未找到 RE Mesh Editor MHWILDS 预设目录", icon='ERROR')

        # ── Material list ──────────────────────────────────────────────────────
        if not settings.material_list:
            layout.separator()
            layout.label(text="选择网格集合后点击刷新", icon='INFO')
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
            strat_box.label(text="节点树分析 (贴图来源策略)", icon='NODETREE')
            grid = strat_box.grid_flow(row_major=True, columns=3,
                                       even_columns=True, align=True)
            for pt, label in _STRAT_LABELS.items():
                strat = getattr(mat_entry, f"strat_{pt}", "?")
                icon  = _STRAT_ICONS.get(strat, 'QUESTION')
                cell  = grid.row(align=True)
                cell.label(text=f"{label}:", icon='BLANK1')
                cell.label(text=strat, icon=icon)

            if preset_has_emissive_slots(mat_entry.material_preset):
                box.prop(mat_entry, "use_toon")
            box.prop(mat_entry, "generate_mipmaps")
            box.prop(mat_entry, "skip_textures")


classes = [MHWS_OT_MdfGeneratorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
