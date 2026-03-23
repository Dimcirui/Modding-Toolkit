import bpy
import os

from .mdf_tex_processor import (
    PBR_TYPES, PBR_TYPE_LABELS, TEXTURE_TYPE_ABBREV,
    COMMON_SLOT_TYPES, PBR_CHANNEL_SELECTABLE, NULL_TEX_BY_TYPE,
)

PROCESSOR_WINDOW_WIDTH = 660


class MHWS_OT_MdfTexProcessorDialog(bpy.types.Operator):
    """MHWs MDF2 + Tex 半自动贴图处理器"""
    bl_idname = "mhws.mdf_tex_processor_dialog"
    bl_label  = "MDF2 + Tex 处理器"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self, width=PROCESSOR_WINDOW_WIDTH)

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        settings = scene.mdf_tex_processor

        # ── Header ──────────────────────────────────────────────────────
        row = layout.row(align=True)
        row.prop(settings, "mdf_collection", text="MDF 集合")
        row.operator("mhws.mdf_tex_refresh", text="", icon='FILE_REFRESH')

        row = layout.row(align=True)
        row.operator("mhws.set_natives_root", text="Mod Root", icon='FILEBROWSER')
        natives_root = scene.get("mhws_natives_root", "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="未设置", icon='ERROR')

        # Base path field with hint when empty
        row = layout.row(align=True)
        row.label(text="natives/STM/Art/")
        row.prop(settings, "texture_base_path", text="")
        if not settings.texture_base_path.strip():
            hint = layout.row()
            hint.label(text="    例：Author/Character/", icon='INFO')

        layout.prop(settings, "generate_mipmaps")

        # ── Early out ───────────────────────────────────────────────────
        if not settings.materials:
            layout.separator()
            layout.label(text="请选择 MDF 集合并点击刷新", icon='INFO')
            return

        layout.separator()

        has_clipboard = bool(settings.clipboard_json)

        # ── Materials ───────────────────────────────────────────────────
        for mi, mat in enumerate(settings.materials):
            box = layout.box()

            # Material header row
            header = box.row(align=False)
            expand_icon = 'TRIA_DOWN' if mat.expanded else 'TRIA_RIGHT'
            header.prop(mat, "expanded", text="", icon=expand_icon, emboss=False)
            header.label(text=mat.material_name, icon='MATERIAL')

            op_copy = header.operator(
                "mhws.mdf_tex_copy_material", text="", icon='COPYDOWN')
            op_copy.mat_index = mi

            paste_row = header.row(align=True)
            paste_row.enabled = has_clipboard
            op_paste = paste_row.operator(
                "mhws.mdf_tex_paste_material", text="", icon='PASTEDOWN')
            op_paste.mat_index = mi

            if not mat.expanded:
                continue

            # ── PBR 输入（折叠） ──
            pbr_header = box.row(align=False)
            pbr_icon = 'TRIA_DOWN' if mat.pbr_expanded else 'TRIA_RIGHT'
            pbr_header.prop(mat, "pbr_expanded", text="", icon=pbr_icon, emboss=False)
            pbr_header.label(text="PBR 转换输入", icon='NODE_COMPOSITING')

            if mat.pbr_expanded:
                pbr_box = box.box()
                for pt in PBR_TYPES:
                    row = pbr_box.row(align=True)
                    row.label(text=PBR_TYPE_LABELS[pt])
                    cur = getattr(mat.pbr, pt)
                    pick_op = row.operator(
                        "mhws.mdf_tex_pick_pbr",
                        text=os.path.basename(bpy.path.abspath(cur)) if cur else "—",
                        icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                    )
                    pick_op.mat_index = mi
                    pick_op.pbr_type  = pt
                    if cur:
                        clr_op = row.operator("mhws.mdf_tex_clear_pbr", text="", icon='X')
                        clr_op.mat_index = mi
                        clr_op.pbr_type  = pt
                    # Channel selector + invert toggle
                    if pt in PBR_CHANNEL_SELECTABLE and cur:
                        ch_sub = row.row(align=True)
                        ch_sub.scale_x = 0.35
                        for ch_val in ('R', 'G', 'B', 'A'):
                            ch_sub.prop_enum(mat.pbr, f"{pt}_ch", ch_val)
                        inv_sub = row.row(align=True)
                        inv_sub.scale_x = 0.4
                        inv_sub.prop(mat.pbr, f"{pt}_inv", text="反相", toggle=True)

            # ── 贴图槽位 ──
            if not mat.slots:
                continue

            common_slots = [(si, s) for si, s in enumerate(mat.slots)
                            if s.texture_type in COMMON_SLOT_TYPES]
            other_slots  = [(si, s) for si, s in enumerate(mat.slots)
                            if s.texture_type not in COMMON_SLOT_TYPES]

            if common_slots:
                box.label(text="常用贴图", icon='TEXTURE')
                self._draw_slots(box, common_slots, mi, mat)

            if other_slots:
                other_header = box.row(align=False)
                other_icon = 'TRIA_DOWN' if mat.other_expanded else 'TRIA_RIGHT'
                other_header.prop(mat, "other_expanded", text="",
                                  icon=other_icon, emboss=False)
                other_header.label(text="其他贴图", icon='TEXTURE_DATA')
                if mat.other_expanded:
                    self._draw_slots(box, other_slots, mi, mat)

    def _draw_slots(self, box, indexed_slots, mi, mat):
        for si, slot in indexed_slots:
            row = box.row(align=True)
            row.label(text=slot.texture_type, icon='TEXTURE_DATA')
            row.prop(slot, "mode", text="")

            if slot.mode == 'DIRECT':
                cur = slot.direct_image
                pick_op = row.operator(
                    "mhws.mdf_tex_pick_direct",
                    text=os.path.basename(bpy.path.abspath(cur)) if cur else "—",
                    icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                )
                pick_op.mat_index  = mi
                pick_op.slot_index = si
                if cur:
                    clr_op = row.operator(
                        "mhws.mdf_tex_clear_direct", text="", icon='X')
                    clr_op.mat_index  = mi
                    clr_op.slot_index = si

            elif slot.mode == 'DEFAULT':
                null_rel = NULL_TEX_BY_TYPE.get(slot.texture_type)
                if null_rel:
                    row.label(text=f"→ {null_rel.split('/')[-1]}", icon='LINKED')
                else:
                    row.label(text="（无默认空贴图）", icon='ERROR')

            elif slot.mode == 'SKIP' and slot.original_path:
                row.label(
                    text=slot.original_path.split('/')[-1],
                    icon='LOOP_BACK',
                )

    def execute(self, context):
        bpy.ops.mhws.mdf_tex_process()
        return {'FINISHED'}


classes = [MHWS_OT_MdfTexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
