import bpy
from .i18n import T

# 单个辅助骨条目
class AuxBoneItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()

# 单个标准骨骼槽位 (例如 "Hips" 或 "UpperArm_L")
class MappingSlot(bpy.types.PropertyGroup):
    # 标准名 (用于内部索引，如 "upperarm_L")
    std_name: bpy.props.StringProperty()
    
    # UI显示名 (如 "UpperArm_L")
    ui_name: bpy.props.StringProperty()
    
    # 用户指定的主骨名 (对应 main)
    source_bone_name: bpy.props.StringProperty(
        name="Source Bone",
        description="The corresponding main bone name",
        default=""
    )
    
    # 辅助骨列表 (对应 aux)
    aux_bones: bpy.props.CollectionProperty(type=AuxBoneItem)
    
    # UI 状态：是否展开显示辅助骨
    is_expanded: bpy.props.BoolProperty(default=False)

_edit_mode_items_cache = []

def get_edit_mode_items(self, context):
    global _edit_mode_items_cache
    _edit_mode_items_cache = [
        ('X', T("core.editor_props.edit_mode_x"), T("core.editor_props.edit_mode_x_desc")),
        ('Y', T("core.editor_props.edit_mode_y"), T("core.editor_props.edit_mode_y_desc")),
    ]
    return _edit_mode_items_cache


# 编辑器全局设置
class EditorSettings(bpy.types.PropertyGroup):
    # 存放标准骨骼的槽位
    slots: bpy.props.CollectionProperty(type=MappingSlot)
    
    # 新建预设的文件名
    new_preset_name: bpy.props.StringProperty(name="Preset Name", default="New_Game_Preset")

    # 搜索过滤
    search_filter: bpy.props.StringProperty(name="Search", description="Filter bone names", options={'TEXTEDIT_UPDATE'})
    
    # 折叠状态 (UI分组用)
    show_torso: bpy.props.BoolProperty(default=True)
    show_arm_l: bpy.props.BoolProperty(default=True)
    show_arm_r: bpy.props.BoolProperty(default=True)
    show_leg_l: bpy.props.BoolProperty(default=True)
    show_leg_r: bpy.props.BoolProperty(default=True)
    show_fingers: bpy.props.BoolProperty(default=False)

    # 编辑模式：X 预设（来源）或 Y 预设（目标）
    edit_mode: bpy.props.EnumProperty(
        name="Edit Mode",
        items=get_edit_mode_items,
    )

classes = [
    AuxBoneItem,
    MappingSlot,
    EditorSettings,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # 将编辑器设置挂载到场景中
    bpy.types.Scene.mhw_preset_editor = bpy.props.PointerProperty(type=EditorSettings)

def unregister():
    del bpy.types.Scene.mhw_preset_editor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)