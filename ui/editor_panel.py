import bpy
from ..core import ui_config

class MHW_PT_PresetEditor(bpy.types.Panel):
    bl_label = "预设编辑器 (X Preset)"
    bl_idname = "MHW_PT_preset_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        editor_settings = context.scene.mhw_preset_editor
        # 引用主设置以获取 Enum 列表
        suite_settings = context.scene.mhw_suite_settings
        
        # ===========================
        # 1. 现有预设管理 (新增区域)
        # ===========================
        box = layout.box()
        box.label(text="管理现有预设 (Manage):", icon='FILE_FOLDER')
        
        row = box.row(align=True)
        row.prop(suite_settings, "import_preset_enum", text="")
        
        # 编辑与删除按钮
        row.operator("modder.load_x_preset", text="读取/编辑", icon='IMPORT')
        row.operator("modder.delete_x_preset", text="", icon='TRASH')

        layout.separator()

        # ===========================
        # 2. 编辑器控制 (原有区域)
        # ===========================
        layout.label(text="编辑器工作区:", icon='EDITMODE_HLT')
        
        # 保存名称框
        row = layout.row(align=True)
        row.prop(editor_settings, "new_preset_name", text="保存名")
        row.operator("modder.save_x_preset", text="保存", icon='DISK_DRIVE')
        
        # 初始化按钮
        layout.operator("modder.init_editor", text="清空并初始化列表", icon='FILE_NEW')
        
        # --- 搜索与镜像 ---
        row = layout.row()
        row.prop(editor_settings, "search_filter", text="", icon='VIEWZOOM')
        row.operator("modder.mirror_mapping", text="L -> R", icon='MOD_MIRROR')
        
        layout.separator()

        # --- 列表绘制 (使用 ui_config 分组) ---
        if len(editor_settings.slots) == 0:
            layout.label(text="列表为空，请点击初始化", icon='INFO')
            return

        # 建立 slot 索引字典以便按名字查找
        slot_map = {s.std_name: i for i, s in enumerate(editor_settings.slots)}
        
        # 遍历层级结构 (Torso, Arms, Legs...)
        for group_name, group_data in ui_config.UI_HIERARCHY.items():
            # 搜索过滤：如果搜索框有内容，且该分组下没有匹配的骨骼，则不显示整个分组（简化逻辑）
            # 这里的实现略简单，如果需要精准过滤每行显示会更复杂一点
            
            # 使用折叠属性
            prop_name = "show_" + group_name.split()[0].lower() # 简易映射 show_torso 等
            # 如果找不到属性名，默认为展开
            is_open = getattr(editor_settings, "show_torso", True) 
            if "Arm" in group_name and "L" in group_name: is_open = editor_settings.show_arm_l
            elif "Arm" in group_name and "R" in group_name: is_open = editor_settings.show_arm_r
            elif "Leg" in group_name and "L" in group_name: is_open = editor_settings.show_leg_l
            elif "Leg" in group_name and "R" in group_name: is_open = editor_settings.show_leg_r
            elif "Finger" in group_name: is_open = editor_settings.show_fingers
            
            box = layout.box()
            row = box.row()
            row.prop(editor_settings, "show_fingers" if "Finger" in group_name else "show_torso", # 这里需要根据 group_name 动态指定
                     icon="TRIA_DOWN" if is_open else "TRIA_RIGHT",
                     icon_only=True, emboss=False)
            row.label(text=group_name, icon=group_data['icon'])
            
            # 如果未展开，跳过内容绘制
            # (由于 getattr 的复杂性，建议你在 draw 里写死几个 if/else 块，或者简化为全部展开)
            # 这里为了演示，我们假设全部展开，你可以后续完善折叠逻辑
            
            for sub_name, bones in group_data['subsections'].items():
                col = box.column(align=True)
                # sub_col.label(text=sub_name) # 子标题
                
                for std_key in bones:
                    # 搜索过滤逻辑
                    if editor_settings.search_filter and editor_settings.search_filter.lower() not in std_key.lower():
                        continue

                    idx = slot_map.get(std_key)
                    if idx is None: continue
                    
                    slot = editor_settings.slots[idx]
                    
                    # === 单行布局 ===
                    row = col.row(align=True)
                    
                    # 1. 标准名
                    row.label(text=f"{std_key}:")
                    
                    # 2. 主骨显示框
                    if slot.source_bone_name:
                        row.label(text=f"[{slot.source_bone_name}]", icon='BONE_DATA')
                        # 清除按钮
                        op = row.operator("modder.clear_slot", text="", icon='X')
                        op.slot_index = idx
                        op.target = 'MAIN'
                    else:
                        row.label(text="[未设置]", icon='DOT')
                    
                    # 3. 拾取按钮 (EYEDROPPER)
                    op = row.operator("modder.pick_bone", text="", icon='EYEDROPPER')
                    op.slot_index = idx
                    op.is_aux = False
                    
                    # 4. 辅助骨折叠/添加按钮
                    aux_count = len(slot.aux_bones)
                    icon_aux = 'TRIA_DOWN' if slot.is_expanded else 'TRIA_RIGHT'
                    text_aux = f"Aux({aux_count})"
                    
                    # 这里放一个 Operator 来添加 Aux，或者 Toggle 展开
                    # 建议：左键点击展开，Shift点击添加当前骨骼
                    row.prop(slot, "is_expanded", text=text_aux, icon=icon_aux, toggle=True)
                    
                    # 快速添加 Aux 按钮
                    op = row.operator("modder.pick_bone", text="", icon='ADD')
                    op.slot_index = idx
                    op.is_aux = True
                    
                    # === 辅助骨展开区域 ===
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