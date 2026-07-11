import bpy
from .batch_export import (
    MHRS_PARTS, MHRS_GENDERS,
    _load_scheme, _resolve_part_file_types, _canonical_order_file_types,
    get_binding, set_binding,
    get_mhrs_armor_callback,
    _find_auto_align_armature,
)

EXPORTER_WINDOW_WIDTH = 580

_FILETYPE_ICONS = {
    "mesh":  'OUTLINER_OB_MESH',
    "mdf2":  'MATERIAL',
    "chain": 'CONSTRAINT_BONE',
    "user":  'FILE_BLANK',
}

_FILETYPE_LABELS = {
    "mesh":  "MESH",
    "mdf2":  "MDF2",
    "chain": "CHAIN",
    "user":  "USER",
}


def _get_filtered_collections(filetype):
    result = []
    type_map = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION", "chain": "RE_CHAIN_COLLECTION"}
    sfx_map  = {"mesh": ".mesh", "mdf2": ".mdf2", "chain": ".chain"}
    col_type = type_map.get(filetype, "")
    name_sfx = sfx_map.get(filetype, "")
    for c in bpy.data.collections:
        ct = c.get("~TYPE", "")
        if col_type and ct == col_type:
            icon = f"COLLECTION_{c.color_tag}" if c.color_tag != "NONE" else "OUTLINER_COLLECTION"
            result.append((c.name, c.name, "", icon, len(result)))
            continue
        if not ct and name_sfx and c.name.endswith(name_sfx):
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not result:
        result.append(("NONE", "No matching collections", "", "ERROR", 0))
    return result


# ── Pick Collection ────────────────────────────────────────────

class MHRS_OT_PickCollection(bpy.types.Operator):
    bl_idname = "mhrs.pick_collection"
    bl_label = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    armor_id: bpy.props.StringProperty()
    gender:   bpy.props.StringProperty()
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
            set_binding(context.scene, self.armor_id, self.gender, self.part, self.filetype, self.collection_name)
        return {'FINISHED'}


# ── Pick Armor ──────────────────────────────────────────────────

def _get_armor_label(context, armor_id):
    """根据当前装备包解析 armor_id 对应的显示名，找不到则回退为原始 id"""
    if not armor_id or armor_id == 'NONE':
        return None
    settings = context.scene.mhw_suite_settings
    for item_id, label, *_ in get_mhrs_armor_callback(settings, context):
        if item_id == armor_id:
            return label
    return armor_id


class MHRS_OT_PickArmor(bpy.types.Operator):
    """搜索并选择装备（避免装备过多时下拉表溢出屏幕）"""
    bl_idname = "mhrs.pick_armor"
    bl_label = "Pick Armor"
    bl_options = {'INTERNAL'}
    bl_property = "armor_id"

    armor_id: bpy.props.EnumProperty(
        name="Armor",
        items=lambda self, ctx: get_mhrs_armor_callback(ctx.scene.mhw_suite_settings, ctx)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.armor_id and self.armor_id != 'NONE':
            context.scene.mhw_suite_settings.mhrs_selected_armor = self.armor_id
        return {'FINISHED'}


class MHRS_OT_ClearBinding(bpy.types.Operator):
    bl_idname = "mhrs.clear_binding"
    bl_label = "Clear Binding"
    bl_options = {'INTERNAL'}

    armor_id: bpy.props.StringProperty()
    gender:   bpy.props.StringProperty()
    part:     bpy.props.StringProperty()
    filetype: bpy.props.StringProperty()

    def execute(self, context):
        set_binding(context.scene, self.armor_id, self.gender, self.part, self.filetype, "")
        return {'FINISHED'}


# ── Main Dialog ────────────────────────────────────────────────

class MHRS_OT_BatchExportDialog(bpy.types.Operator):
    """MHRS 装备批量导出对话框"""
    bl_idname = "mhrs.batch_export_dialog"
    bl_label = "MHRS Batch Exporter"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mhw_suite_settings

        # ── Selectors ──
        layout.prop(settings, "mhrs_armor_scheme", text="装备包")
        row = layout.row(align=True)
        row.prop(settings, "mhrs_gender", text="")
        cur_armor_label = _get_armor_label(context, settings.mhrs_selected_armor)
        row.operator("mhrs.pick_armor", text=cur_armor_label if cur_armor_label else "选择装备...",
                     icon='DOWNARROW_HLT')

        # ── Natives Root ──
        natives_root = scene.get("mhrs_natives_root", "")
        row = layout.row(align=True)
        row.operator("mhrs.set_natives_root", text="Mod Root", icon='FILE_FOLDER')
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="未设置", icon='ERROR')

        # ── Early out ──
        gender   = settings.mhrs_gender
        armor_id = settings.mhrs_selected_armor
        if not armor_id or armor_id == 'NONE':
            layout.separator()
            layout.label(text="请选择装备以配置绑定", icon='INFO')
            self._draw_shadow(layout, settings)
            return

        scheme_file = settings.mhrs_armor_scheme
        scheme = _load_scheme(scheme_file) if scheme_file and scheme_file != 'NONE' else None
        armor_set = None
        if scheme:
            armor_set = next(
                (a for a in scheme.get("armor_sets", []) if a["id"] == armor_id), None
            )

        parts_mask = armor_set.get("parts_mask", 0b11111) if armor_set else 0b11111
        active_parts = [(pid, pname) for idx, (pid, pname) in enumerate(MHRS_PARTS)
                        if parts_mask & (1 << idx)]

        per_part_fts = {}
        all_file_types = []
        for part_id, part_name in active_parts:
            fts = _canonical_order_file_types(
                _resolve_part_file_types(armor_set if armor_set else {}, part_id))
            per_part_fts[part_id] = fts
            for ft in fts:
                if ft not in all_file_types:
                    all_file_types.append(ft)
        all_file_types = _canonical_order_file_types(all_file_types)

        layout.separator()

        header = layout.row(align=False)
        header.label(text="")
        for ft in all_file_types:
            header.label(text=_FILETYPE_LABELS.get(ft, ft.upper()), icon=_FILETYPE_ICONS.get(ft, 'DOT'))

        for part_id, part_name in active_parts:
            row = layout.row(align=False)
            row.label(text=f"{part_id}  {part_name}")
            part_fts = per_part_fts[part_id]
            for ft in all_file_types:
                sub = row.row(align=True)
                if ft not in part_fts:
                    sub.label(text="")
                    continue

                if ft == "user":
                    # 不可绑定集合：始终由内置模板复制而来（受"未选项使用空模型"开关控制）
                    sub.label(text="AUTO", icon='FILE_BLANK')
                    continue

                cur = get_binding(scene, armor_id, gender, part_id, ft)
                op = sub.operator(
                    "mhrs.pick_collection",
                    text=cur if cur else "—",
                    icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft]
                )
                op.armor_id = armor_id
                op.gender   = gender
                op.part     = part_id
                op.filetype = ft
                if cur:
                    op_c = sub.operator("mhrs.clear_binding", text="", icon='X')
                    op_c.armor_id = armor_id
                    op_c.gender   = gender
                    op_c.part     = part_id
                    op_c.filetype = ft

        layout.separator()
        row = layout.row(align=True)
        row.prop(settings, "mhrs_use_blank_export", icon='FILE_BLANK')
        row.prop(settings, "mhrs_cleanup_before_export", icon='BRUSH_DATA')

        self._draw_shadow(layout, settings, scene, armor_id, gender, parts_mask)

    def _draw_shadow(self, layout, settings, scene=None, armor_id=None, gender=None, parts_mask=None):
        layout.separator()
        box = layout.box()
        row = box.row(align=True)
        row.prop(settings, "mhrs_use_shadow_export", text="使用 Shadow Mesh", icon='ARMATURE_DATA')
        if not settings.mhrs_use_shadow_export:
            return
        box.prop(settings, "mhrs_shadow_armature", text="对齐骨架")
        if not settings.mhrs_shadow_armature and scene is not None and armor_id and armor_id != 'NONE' and parts_mask is not None:
            auto_arm = _find_auto_align_armature(scene, armor_id, gender, parts_mask)
            if auto_arm:
                box.label(text=f"未选择时将自动使用: {auto_arm.name}", icon='INFO')
            else:
                box.label(text="未选择对齐骨架，且无法自动判定（需恰好绑定 1 个 Mesh 集合）", icon='ERROR')

    def execute(self, context):
        bpy.ops.mhrs.batch_export()
        return {'FINISHED'}


classes = [
    MHRS_OT_PickCollection,
    MHRS_OT_PickArmor,
    MHRS_OT_ClearBinding,
    MHRS_OT_BatchExportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
