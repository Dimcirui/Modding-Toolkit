import bpy
from .batch_export import (
    MHWI_PARTS, HELM_PART,
    SP_FACE_FILE_TYPES, SP_HAIR_FILE_TYPES,
    _load_armor_sets, get_armor_entry,
    get_binding, set_binding,
    get_blank, set_blank,
    get_export_ccl, set_export_ccl,
    get_mhwi_hr_armor_callback, get_mhwi_mr_armor_callback, get_mhwi_sp_armor_callback,
)
from .weapon_data import (
    WEAPON_FILE_TYPES,
    get_weapon_parts, has_patch_model,
    _load_weapon_sets, get_weapon_entry,
    get_mhwi_weapon_callback_for_type,
    get_weapon_binding, set_weapon_binding,
    get_selected_weapon, set_selected_weapon,
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


# ── Pick / Clear（武器）───────────────────────────────────────────

class MHWI_OT_PickWeaponCollection(bpy.types.Operator):
    bl_idname  = "mhwi.pick_weapon_collection"
    bl_label   = "Pick Collection"
    bl_options = {'INTERNAL'}
    bl_property = "collection_name"

    weapon_type: bpy.props.StringProperty()
    main_code:   bpy.props.StringProperty()
    part:        bpy.props.StringProperty()
    filetype:    bpy.props.StringProperty()
    collection_name: bpy.props.EnumProperty(
        name="Collection",
        items=lambda self, ctx: _get_filtered_collections(self.filetype)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.collection_name and self.collection_name != "NONE":
            set_weapon_binding(context.scene, self.weapon_type, self.main_code,
                                self.part, self.filetype, self.collection_name)
        return {'FINISHED'}


class MHWI_OT_ClearWeaponBinding(bpy.types.Operator):
    bl_idname  = "mhwi.clear_weapon_binding"
    bl_label   = "Clear Binding"
    bl_options = {'INTERNAL'}

    weapon_type: bpy.props.StringProperty()
    main_code:   bpy.props.StringProperty()
    part:        bpy.props.StringProperty()
    filetype:    bpy.props.StringProperty()

    def execute(self, context):
        set_weapon_binding(context.scene, self.weapon_type, self.main_code, self.part, self.filetype, "")
        return {'FINISHED'}


# ── Pick Armor ──────────────────────────────────────────────────

def _mhwi_armor_items_for_rank(rank, context):
    settings = context.scene.mhw_suite_settings
    if rank == 'HR':
        return get_mhwi_hr_armor_callback(settings, context)
    elif rank == 'MR':
        return get_mhwi_mr_armor_callback(settings, context)
    else:
        return get_mhwi_sp_armor_callback(settings, context)


def _get_armor_label(context, rank, armor_id):
    """根据当前装备包解析 armor_id 对应的显示名，找不到则回退为原始 id"""
    if not armor_id or armor_id == 'NONE':
        return None
    for item_id, label, *_ in _mhwi_armor_items_for_rank(rank, context):
        if item_id == armor_id:
            return label
    return armor_id


class MHWI_OT_PickArmor(bpy.types.Operator):
    """搜索并选择装备（避免装备过多时下拉表溢出屏幕）"""
    bl_idname  = "mhwi.pick_armor"
    bl_label   = "Pick Armor"
    bl_options = {'INTERNAL'}
    bl_property = "armor_id"

    rank: bpy.props.StringProperty()   # 'HR' / 'MR' / 'SP'
    armor_id: bpy.props.EnumProperty(
        name="Armor",
        items=lambda self, ctx: _mhwi_armor_items_for_rank(self.rank, ctx)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.armor_id and self.armor_id != 'NONE':
            settings = context.scene.mhw_suite_settings
            if self.rank == 'HR':
                settings.mhwi_selected_hr_armor = self.armor_id
            elif self.rank == 'MR':
                settings.mhwi_selected_mr_armor = self.armor_id
            else:
                settings.mhwi_selected_sp_armor = self.armor_id
        return {'FINISHED'}


# ── Pick Weapon ───────────────────────────────────────────────────

def _get_weapon_label(context, weapon_type, weapon_id):
    """根据当前武器预设组解析 weapon_id 对应的显示名，找不到则回退为原始 id"""
    if not weapon_id or weapon_id == 'NONE':
        return None
    for item_id, label, *_ in get_mhwi_weapon_callback_for_type(weapon_type, context):
        if item_id == weapon_id:
            return label
    return weapon_id


class MHWI_OT_PickWeapon(bpy.types.Operator):
    """搜索并选择武器（避免武器过多时下拉表溢出屏幕）"""
    bl_idname  = "mhwi.pick_weapon"
    bl_label   = "Pick Weapon"
    bl_options = {'INTERNAL'}
    bl_property = "weapon_id"

    weapon_type: bpy.props.StringProperty()
    weapon_id: bpy.props.EnumProperty(
        name="Weapon",
        items=lambda self, ctx: get_mhwi_weapon_callback_for_type(self.weapon_type, ctx)
    )

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.weapon_id and self.weapon_id != 'NONE':
            set_selected_weapon(context.scene, self.weapon_type, self.weapon_id)
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

        # ── 模式切换（装备 / 武器） ──
        layout.row().prop(settings, "mhwi_export_mode", expand=True)

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

        if settings.mhwi_export_mode == 'WEAPON':
            self._draw_weapon_mode(layout, context, scene, settings)
        else:
            self._draw_armor_mode(layout, context, scene, settings)

    def _draw_armor_mode(self, layout, context, scene, settings):
        # ── 预设组 ──
        layout.prop(settings, "mhwi_armor_sets_file", text="预设组")

        # ── 性别 + 位阶标签页 ──
        rank = settings.mhwi_rank_tab
        if rank != 'SP':
            row = layout.row(align=True)
            row.prop(settings, "mhwi_gender", expand=True)

        layout.row().prop(settings, "mhwi_rank_tab", expand=True)

        # ── 装备选择 ──
        if rank == 'HR':
            model_id = settings.mhwi_selected_hr_armor
        elif rank == 'MR':
            model_id = settings.mhwi_selected_mr_armor
        else:
            model_id = settings.mhwi_selected_sp_armor

        cur_armor_label = _get_armor_label(context, rank, model_id)
        op = layout.operator("mhwi.pick_armor", text=cur_armor_label if cur_armor_label else "选择装备...",
                             icon='DOWNARROW_HLT')
        op.rank = rank

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

        layout.separator()
        row = layout.row(align=False)
        row.prop(settings, "mhwi_cleanup_before_export", icon='BRUSH_DATA')

    def _draw_weapon_mode(self, layout, context, scene, settings):
        # ── 预设组 ──
        layout.prop(settings, "mhwi_weapon_sets_file", text="预设组")

        # ── 武器类型 ──
        layout.prop(settings, "mhwi_weapon_type_tab", text="武器类型")
        weapon_type = settings.mhwi_weapon_type_tab

        # ── 武器选择 ──
        weapon_id = get_selected_weapon(scene, weapon_type)
        cur_label = _get_weapon_label(context, weapon_type, weapon_id)
        op = layout.operator("mhwi.pick_weapon", text=cur_label if cur_label else "选择武器...",
                             icon='DOWNARROW_HLT')
        op.weapon_type = weapon_type

        if not weapon_id or weapon_id == 'NONE':
            layout.separator()
            layout.label(text="请选择武器以配置绑定", icon='INFO')
            return

        data  = _load_weapon_sets(settings.mhwi_weapon_sets_file)
        entry = get_weapon_entry(data, weapon_type, weapon_id)
        if not entry:
            # 上次选择属于其他类型或预设组已变更，视为未选择
            layout.separator()
            layout.label(text="请选择武器以配置绑定", icon='INFO')
            return

        layout.separator()
        if has_patch_model(entry):
            sub = layout.row()
            sub.enabled = False
            sub.label(text="该武器拥有贴片模型，不建议替换！", icon='ERROR')

        main_code = entry["id"]
        parts     = get_weapon_parts(weapon_type, entry)

        header = layout.row(align=False)
        header.label(text="")
        for ft in WEAPON_FILE_TYPES:
            header.label(text=_FILETYPE_LABELS[ft], icon=_FILETYPE_ICONS[ft], translate=False)

        for part_code, part_name, model_code in parts:
            row = layout.row(align=False)
            row.label(text=f"{part_name} ({model_code})")
            for ft in WEAPON_FILE_TYPES:
                self._draw_weapon_picker(row, scene, weapon_type, main_code, part_code, ft)

    def _draw_weapon_picker(self, row, scene, weapon_type, main_code, part_code, ft):
        cur = get_weapon_binding(scene, weapon_type, main_code, part_code, ft)
        sub = row.row(align=True)
        pick_op = sub.operator(
            "mhwi.pick_weapon_collection",
            text=cur if cur else "—",
            icon='DOWNARROW_HLT' if not cur else _FILETYPE_ICONS[ft],
        )
        pick_op.weapon_type = weapon_type
        pick_op.main_code   = main_code
        pick_op.part        = part_code
        pick_op.filetype    = ft
        if cur:
            clr_op = sub.operator("mhwi.clear_weapon_binding", text="", icon='X')
            clr_op.weapon_type = weapon_type
            clr_op.main_code   = main_code
            clr_op.part        = part_code
            clr_op.filetype    = ft

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
    MHWI_OT_PickArmor,
    MHWI_OT_ClearBinding,
    MHWI_OT_ToggleBlank,
    MHWI_OT_ToggleCCL,
    MHWI_OT_PickWeaponCollection,
    MHWI_OT_ClearWeaponBinding,
    MHWI_OT_PickWeapon,
    MHWI_OT_BatchExportDialog,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
