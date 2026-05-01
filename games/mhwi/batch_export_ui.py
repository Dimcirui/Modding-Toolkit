import bpy
from .batch_export import (
    MHWI_PARTS, HELM_PART,
    SP_FACE_FILE_TYPES, SP_HAIR_FILE_TYPES,
    _load_armor_sets, get_armor_entry,
    get_binding, set_binding,
    get_blank, set_blank,
    get_export_ccl, set_export_ccl,
)

EXPORTER_WINDOW_WIDTH = 560

_FILETYPE_ICONS = {
    "mod3": 'OUTLINER_OB_MESH',
    "mrl3": 'MATERIAL',
    "ctc":  'LINKED',
}

_FILETYPE_LABELS = {
    "mod3": "MOD3",
    "mrl3": "MRL3",
    "ctc":  "CTC",
}


# ── 集合过滤 ──────────────────────────────────────────────────────

def _get_filtered_collections(filetype):
    type_map = {
        "mod3": "MHW_MOD3_COLLECTION",
        "mrl3": "MHW_MRL3_COLLECTION",
        "ctc":  "MHW_CTC_COLLECTION",
    }
    sfx_map = {
        "mod3": ".mod3",
        "mrl3": ".mrl3",
        "ctc":  ".ctc",
    }
    col_type = type_map.get(filetype, "")
    name_sfx = sfx_map.get(filetype, "")
    result = []
    for c in bpy.data.collections:
        ct = c.get("~TYPE", "")
        if col_type and ct == col_type:
            icon = f"COLLECTION_{c.color_tag}" if c.color_tag != "NONE" else "OUTLINER_COLLECTION"
            result.append((c.name, c.name, "", icon, len(result)))
        elif not ct and name_sfx and c.name.endswith(name_sfx):
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not result:
        result.append(("NONE", "无匹配集合", "", "ERROR", 0))
    return result


# ── Pick / Clear ──────────────────────────────────────────────────

class MHWI_OT_PickCollection(bpy.types.Operator):
    bl_idname  = "mhwi.pick_collection"
    bl_label   = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    model_id: bpy.props.StringProperty()
    part:     bpy.props.StringProperty()
    filetype: bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(
        name="Collection",
        items=lambda self, ctx: _get_filtered_collections(self.filetype)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name and self.collection_name != "NONE":
            set_binding(context.scene, self.model_id, self.part, self.filetype, self.collection_name)
        return {'FINISHED'}


class MHWI_OT_ClearBinding(bpy.types.Operator):
    bl_idname  = "mhwi.clear_binding"
    bl_label   = "Clear Binding"
    bl_options = {'INTERNAL'}

    model_id: bpy.props.StringProperty()
    part:     bpy.props.StringProperty()
    filetype: bpy.props.StringProperty()

    def execute(self, context):
        set_binding(context.scene, self.model_id, self.part, self.filetype, "")
        return {'FINISHED'}


class MHWI_OT_ToggleBlank(bpy.types.Operator):
    """切换该部位是否使用空模"""
    bl_idname  = "mhwi.toggle_blank"
    bl_label   = "Toggle Blank"
    bl_options = {'INTERNAL'}

    model_id: bpy.props.StringProperty()
    part:     bpy.props.StringProperty()

    def execute(self, context):
        cur = get_blank(context.scene, self.model_id, self.part)
        set_blank(context.scene, self.model_id, self.part, not cur)
        return {'FINISHED'}


class MHWI_OT_ToggleCCL(bpy.types.Operator):
    """切换该部位 CTC 是否顺带导出 CCL"""
    bl_idname  = "mhwi.toggle_ccl"
    bl_label   = "Toggle CCL"
    bl_options = {'INTERNAL'}

    model_id: bpy.props.StringProperty()
    part:     bpy.props.StringProperty()

    def execute(self, context):
        cur = get_export_ccl(context.scene, self.model_id, self.part)
        set_export_ccl(context.scene, self.model_id, self.part, not cur)
        return {'FINISHED'}


# ── 主对话框 ──────────────────────────────────────────────────────

class MHWI_OT_BatchExportDialog(bpy.types.Operator):
    """MHWI 装备批量导出对话框"""
    bl_idname  = "mhwi.batch_export_dialog"
    bl_label   = "MHWI Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        settings = scene.mhw_suite_settings

        # ── 装备包 ──
        layout.prop(settings, "mhwi_armor_sets_file", text="装备包")

        # ── Mod Root ──
        natives_root = scene.get("mhwi_natives_root", "")
        row = layout.row(align=True)
        row.operator("mhwi.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="未设置", icon='ERROR')

        # ── 性别 + 位阶标签页 ──
        rank = settings.mhwi_rank_tab
        if rank != 'SP':
            row = layout.row(align=True)
            row.prop(settings, "mhwi_gender", expand=True)

        layout.row().prop(settings, "mhwi_rank_tab", expand=True)

        # ── 装备选择 ──
        if rank == 'HR':
            layout.prop(settings, "mhwi_selected_hr_armor", text="装备")
            model_id = settings.mhwi_selected_hr_armor
        elif rank == 'MR':
            layout.prop(settings, "mhwi_selected_mr_armor", text="装备")
            model_id = settings.mhwi_selected_mr_armor
        else:
            layout.prop(settings, "mhwi_selected_sp_armor", text="装备")
            model_id = settings.mhwi_selected_sp_armor

        if not model_id or model_id == 'NONE':
            layout.separator()
            layout.label(text="请选择装备以配置绑定", icon='INFO')
            return

        data        = _load_armor_sets(settings.mhwi_armor_sets_file)
        armor_entry = get_armor_entry(data, model_id)
        if not armor_entry:
            layout.label(text="装备包中未找到该装备", icon='ERROR')
            return

        mask_str  = armor_entry.get("mask", "11111")
        mask      = [c == '1' for c in mask_str.ljust(5, '0')]
        active_parts = [
            (code, name, midx)
            for code, name, midx in MHWI_PARTS
            if mask[midx]
        ]

        layout.separator()
        if rank == 'SP':
            self._draw_parts(layout, scene, model_id, active_parts, sp_helm=True)
            self._draw_sp_standalone(layout, scene, armor_entry)
        else:
            self._draw_parts(layout, scene, model_id, active_parts)

    def _draw_parts(self, layout, scene, model_id, active_parts, sp_helm=False):
        # 表头行
        header = layout.row(align=False)
        header.label(text="")
        for ft in ("mod3", "mrl3", "ctc"):
            header.label(text=_FILETYPE_LABELS[ft], icon=_FILETYPE_ICONS[ft], translate=False)
        header.label(text="")   # 空模列占位

        for part_code, part_name, _ in active_parts:
            is_helm  = (part_code == HELM_PART)
            is_blank = get_blank(scene, model_id, part_code)

            row = layout.row(align=False)
            row.label(text=part_name)

            if is_blank:
                # SP 头盔不写 evhl，所以不显示 "+evhl"
                blank_label = "空模" if (sp_helm or not is_helm) else "空模+evhl"
                sub = row.row()
                sub.enabled = False
                sub.label(text="")
                sub.label(text="")
                sub.label(text="")
                op = row.operator("mhwi.toggle_blank", text=blank_label,
                                  icon='FILE_BLANK', depress=True)
                op.model_id = model_id
                op.part     = part_code
                continue

            # MOD3
            self._draw_picker(row, scene, model_id, part_code, "mod3")
            # MRL3
            self._draw_picker(row, scene, model_id, part_code, "mrl3")
            # CTC（头盔两个禁用按钮对齐列宽）
            if is_helm:
                sub = row.row(align=True)
                sub.enabled = False
                ctc_ph = sub.operator("mhwi.pick_collection", text="不支持物理", icon='LINKED')
                ctc_ph.model_id = model_id
                ctc_ph.part     = part_code
                ctc_ph.filetype = "ctc"
                ccl_ph = sub.operator("mhwi.toggle_ccl", text="CCL", icon='PHYSICS')
                ccl_ph.model_id = model_id
                ccl_ph.part     = part_code
            else:
                ctc_sub = row.row(align=True)
                self._draw_picker(ctc_sub, scene, model_id, part_code, "ctc")
                ccl_on = get_export_ccl(scene, model_id, part_code)
                ccl_op = ctc_sub.operator("mhwi.toggle_ccl", text="CCL",
                                          icon='PHYSICS', depress=ccl_on)
                ccl_op.model_id = model_id
                ccl_op.part     = part_code

            # 空模切换（未激活）
            op = row.operator("mhwi.toggle_blank", text="空模",
                               icon='FILE_BLANK', depress=False)
            op.model_id = model_id
            op.part     = part_code

    def _draw_sp_standalone(self, layout, scene, armor_entry):
        """绘制 SP 独立头部与头发的绑定行"""
        face_id = armor_entry["face_id"]
        hair_id = armor_entry["hair_id"]

        # ── 独立头部 ──
        layout.separator()
        layout.label(text=f"独立头部  ({face_id})", icon='OUTLINER_OB_ARMATURE')
        header = layout.row(align=False)
        header.label(text="")
        for ft in SP_FACE_FILE_TYPES:
            header.label(text=_FILETYPE_LABELS[ft], icon=_FILETYPE_ICONS[ft], translate=False)

        row = layout.row(align=False)
        row.label(text="头部")
        for ft in SP_FACE_FILE_TYPES:
            self._draw_picker(row, scene, face_id, "face", ft)

        # ── 独立头发 ──
        layout.separator()
        layout.label(text=f"独立头发  ({hair_id})", icon='OUTLINER_OB_CURVES')
        header = layout.row(align=False)
        header.label(text="")
        for ft in ("mod3", "mrl3", "ctc"):
            header.label(text=_FILETYPE_LABELS[ft], icon=_FILETYPE_ICONS[ft], translate=False)

        row = layout.row(align=False)
        row.label(text="头发")
        self._draw_picker(row, scene, hair_id, "hair", "mod3")
        self._draw_picker(row, scene, hair_id, "hair", "mrl3")
        ctc_sub = row.row(align=True)
        self._draw_picker(ctc_sub, scene, hair_id, "hair", "ctc")
        ccl_on = get_export_ccl(scene, hair_id, "hair")
        ccl_op = ctc_sub.operator("mhwi.toggle_ccl", text="CCL",
                                  icon='PHYSICS', depress=ccl_on)
        ccl_op.model_id = hair_id
        ccl_op.part     = "hair"

    def _draw_picker(self, row, scene, model_id, part_code, ft):
        cur = get_binding(scene, model_id, part_code, ft)
        sub = row.row(align=True)
        pick_op = sub.operator(
            "mhwi.pick_collection",
            text=cur if cur else "—",
            icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft],
        )
        pick_op.model_id = model_id
        pick_op.part     = part_code
        pick_op.filetype = ft
        if cur:
            clr_op = sub.operator("mhwi.clear_binding", text="", icon='X')
            clr_op.model_id = model_id
            clr_op.part     = part_code
            clr_op.filetype = ft

    def execute(self, context):
        bpy.ops.mhwi.batch_export()
        return {'FINISHED'}


classes = [
    MHWI_OT_PickCollection,
    MHWI_OT_ClearBinding,
    MHWI_OT_ToggleBlank,
    MHWI_OT_ToggleCCL,
    MHWI_OT_BatchExportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
