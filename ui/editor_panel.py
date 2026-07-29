import bpy
from ..core.i18n import T
from ..core import ui_config
from ..core.ui_config import get_display_name

# Group name -> EditorSettings collapse-property name mapping.
# NOTE: these dict keys are Chinese because they must match ui_config's
# UI_HIERARCHY group names exactly (ui_config.py is out of this migration's
# scope) — they're internal lookup keys, not displayed UI text.
_GROUP_PROP_MAP = {
    "躯干和头部": "show_torso",
    "手臂":       "show_arm_l",
    "腿部":       "show_leg_l",
    "手指 (左)":  "show_fingers",
    "手指 (右)":  "show_fingers",
}

class MHW_PT_PresetEditor(bpy.types.Panel):
    bl_label = ""
    bl_idname = "MHW_PT_preset_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text=T("ui.editor_panel.panel_title"))

    def draw(self, context):
        layout = self.layout
        editor_settings = context.scene.mhw_preset_editor
        suite_settings = context.scene.mhw_suite_settings
        is_x = editor_settings.edit_mode == 'X'

        # ===========================
        # 1. Manage existing presets
        # ===========================
        box = layout.box()
        box.label(text=T("ui.editor_panel.manage_header"), icon='FILE_FOLDER')

        # Edit mode toggle
        row = box.row(align=True)
        row.prop(editor_settings, "edit_mode", text=T("ui.prop.edit_mode"), expand=True)

        # Preset selection + action buttons
        row = box.row(align=True)
        if is_x:
            row.prop(suite_settings, "import_preset_enum", text="")
        else:
            row.prop(suite_settings, "target_preset_enum", text="")
        row.operator("modder.load_x_preset", text=T("ui.editor_panel.load_edit"), icon='IMPORT')
        row.operator("modder.delete_x_preset", text="", icon='TRASH')

        # Open folder button
        row = box.row()
        row.operator("modder.open_preset_folder", text=T("ui.editor_panel.open_preset_folder"), icon='FILE_FOLDER')

        # Convert button
        row = box.row()
        if is_x:
            row.operator("modder.convert_preset", text=T("ui.editor_panel.convert_to_y"), icon='PASTEDOWN')
        else:
            row.operator("modder.convert_preset", text=T("ui.editor_panel.convert_to_x"), icon='PASTEDOWN')

        layout.separator()

        # ===========================
        # 2. Editor workspace
        # ===========================
        layout.label(text=T("ui.editor_panel.workspace_header"), icon='EDITMODE_HLT')

        row = layout.row(align=True)
        row.prop(editor_settings, "new_preset_name", text=T("ui.editor_panel.save_name_label"))
        row.operator("modder.save_x_preset", text=T("ui.editor_panel.save_btn"), icon='DISK_DRIVE')

        layout.operator("modder.init_editor", text=T("ui.editor_panel.init_list_btn"), icon='FILE_NEW')

        row = layout.row()
        row.prop(editor_settings, "search_filter", text="", icon='VIEWZOOM')
        row.operator("modder.mirror_mapping", text="L -> R", icon='MOD_MIRROR')

        layout.separator()

        # --- Bone list ---
        if len(editor_settings.slots) == 0:
            layout.label(text=T("ui.editor_panel.list_empty"), icon='INFO')
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
                        row.label(text=T("ui.editor_panel.unset_label"), icon='DOT')

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
