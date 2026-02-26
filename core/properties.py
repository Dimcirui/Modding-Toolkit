import bpy
import os

# 为 X 和 Y 预设声明两条完全独立的全局生命线
global import_presetList
import_presetList = []

global target_presetList
target_presetList = []

def get_import_presets(self, context):
    global import_presetList
    # 【关键修复】：用 .clear() 清空同一个列表对象，而非 = [] 创建新对象
    # 这样 Blender C 层缓存的旧指针在列表被重新填充前不会因为
    # 旧列表对象被 GC 而变成野指针
    import_presetList.clear()
    
    addon_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    presets_dir = os.path.join(addon_dir, "assets", "import_presets")
    assets_dir = os.path.join(addon_dir, "assets")
    
    if os.path.exists(presets_dir):
        for entry in os.scandir(presets_dir):
            if entry.name.endswith(".json") and entry.is_file():
                item_id = os.path.relpath(os.path.join(presets_dir, entry.name), start=assets_dir)
                display_name = os.path.splitext(entry.name)[0]
                import_presetList.append((item_id, display_name, ""))
                
    if not import_presetList:
        import_presetList.append(("NONE", "无预设", ""))
        
    return import_presetList

def get_target_presets(self, context):
    global target_presetList
    # 【关键修复】：同上，用 .clear() 而非 = []
    target_presetList.clear()
    
    addon_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    presets_dir = os.path.join(addon_dir, "assets", "bone_presets")
    assets_dir = os.path.join(addon_dir, "assets")
    
    if os.path.exists(presets_dir):
        for entry in os.scandir(presets_dir):
            if entry.name.endswith(".json") and entry.is_file():
                item_id = os.path.relpath(os.path.join(presets_dir, entry.name), start=assets_dir)
                display_name = os.path.splitext(entry.name)[0]
                target_presetList.append((item_id, display_name, ""))
                
    if not target_presetList:
        target_presetList.append(("NONE", "无预设", ""))
        
    return target_presetList

class ModderBatchSettings(bpy.types.PropertyGroup):
    import_preset_enum: bpy.props.EnumProperty(
        name="Source Preset (X)",
        description="Select the source mapping preset",
        items=get_import_presets
    )
    
    target_preset_enum: bpy.props.EnumProperty(
        name="Target Preset (Y)",
        description="Select the target game preset",
        items=get_target_presets
    )