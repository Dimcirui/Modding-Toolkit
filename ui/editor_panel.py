import bpy
from ..core import ui_config
from ..core.ui_config import get_display_name

# 分组名 → EditorSettings 折叠属性名的精确映射
_GROUP_PROP_MAP = {
    "躯干和头部": "show_torso",
    "手臂":       "show_arm_l",
    "腿部":       "show_leg_l",
    "手指 (左)":  "show_fingers",
    "手指 (右)":  "show_fingers",
}

class MHW_PT_PresetEditor(bpy.types.Panel):
    bl_label = "预设编辑器"
    bl_idname = "MHW_PT_preset_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        editor_settings = context.scene.mhw_preset_editor
        suite_settings = context.scene.mhw_suite_settings
        is_x = editor_settings.edit_mode == 'X'

        # ===========================
        # 1. 管理现有预设
        # ===========================
        box = layout.box()
        box.label(text="管理现有预设 (Manage):", icon='FILE_FOLDER')

        # 编辑模式切换
        row = box.row(align=True)
        row.prop(editor_settings, "edit_mode", expand=True)

        # 预设选择 + 操作按钮
        row = box.row(align=True)
        if is_x:
            row.prop(suite_settings, "import_preset_enum", text="")
        else:
            row.prop(suite_settings, "target_preset_enum", text="")
        row.operator("modder.load_x_preset", text="读取/编辑", icon='IMPORT')
        row.operator("modder.delete_x_preset", text="", icon='TRASH')

        # 转换按钮
        row = box.row()
        if is_x:
            row.operator("modder.convert_preset", text="复制为 Y 预设 (X转换)", icon='PASTEDOWN')
        else:
            row.operator("modder.convert_preset", text="复制为 X 预设 (Y转换)", icon='PASTEDOWN')

        layout.separator()

        # ===========================
        # 2. 编辑器工作区
        # ===========================
        layout.label(text="编辑器工作区:", icon='EDITMODE_HLT')

        row = layout.row(align=True)
        row.prop(editor_settings, "new_preset_name", text="保存名")
        row.operator("modder.save_x_preset", text="保存", icon='DISK_DRIVE')

        layout.operator("modder.init_editor", text="清空并初始化列表", icon='FILE_NEW')

        row = layout.row()
        row.prop(editor_settings, "search_filter", text="", icon='VIEWZOOM')
        row.operator("modder.mirror_mapping", text="L -> R", icon='MOD_MIRROR')

        layout.separator()

        # --- 骨骼列表 ---
        if len(editor_settings.slots) == 0:
            layout.label(text="列表为空，请点击初始化", icon='INFO')
            return

        slot_map = {s.std_name: i for i, s in enumerate(editor_settings.slots)}
        searching = bool(editor_settings.search_filter)

        for group_name, group_data in ui_config.UI_HIERARCHY.items():
            prop_name = _GROUP_PROP_MAP.get(group_name, "show_torso")
            is_open = searching or getattr(editor_settings, prop_name, True)

            box = layout.box()
            row = box.row()
            row.prop(editor_settings, prop_name,
                     icon="TRIA_DOWN" if is_open else "TRIA_RIGHT",
                     icon_only=True, emboss=False)
            row.label(text=group_name, icon=group_data['icon'])

            if not is_open:
                continue

            for sub_name, bones in group_data['subsections'].items():
                col = box.column(align=True)

                for std_key in bones:
                    if searching and editor_settings.search_filter.lower() not in std_key.lower():
                        continue

                    idx = slot_map.get(std_key)
                    if idx is None:
                        continue

                    slot = editor_settings.slots[idx]
                    row = col.row(align=True)
                    row.label(text=f"{get_display_name(std_key)}:")

                    if slot.source_bone_name:
                        row.label(text=f"[{slot.source_bone_name}]", icon='BONE_DATA')
                        op = row.operator("modder.clear_slot", text="", icon='X')
                        op.slot_index = idx
                        op.target = 'MAIN'
                    else:
                        row.label(text="[未设置]", icon='DOT')

                    op = row.operator("modder.pick_bone", text="", icon='EYEDROPPER')
                    op.slot_index = idx
                    op.is_aux = False

                    aux_count = len(slot.aux_bones)
                    icon_aux = 'TRIA_DOWN' if slot.is_expanded else 'TRIA_RIGHT'
                    row.prop(slot, "is_expanded", text=f"Aux({aux_count})", icon=icon_aux, toggle=True)

                    op = row.operator("modder.pick_bone", text="", icon='ADD')
                    op.slot_index = idx
                    op.is_aux = True

                    if slot.is_expanded and aux_count > 0:
                        aux_box = col.box()
                        for aux in slot.aux_bones:
                            a_row = aux_box.row(align=True)
                            a_row.label(text=f"  ↳ {aux.name}", icon='LINKED')
                            op = a_row.operator("modder.clear_slot", text="", icon='X')
                            op.slot_index = idx
                            op.target = aux.name


classes = [
    MHW_PT_PresetEditor,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
