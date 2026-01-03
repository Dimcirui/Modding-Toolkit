import bpy
import json
import os
import re
from . import ui_config, bone_mapper
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES

# === 初始化/刷新列表 ===
class MODDER_OT_InitEditor(bpy.types.Operator):
    """初始化预设编辑器列表"""
    bl_idname = "modder.init_editor"
    bl_label = "初始化/刷新列表"

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        settings.slots.clear()
        
        # 按照标准骨骼顺序填充槽位
        for std_key in bone_mapper.STANDARD_BONE_NAMES:
            item = settings.slots.add()
            item.std_name = std_key
            item.ui_name = std_key # 这里可以做得更美观，比如 "UpperArm L"
            
        self.report({'INFO'}, "编辑器已重置")
        return {'FINISHED'}

# === 拾取骨骼 (核心功能) ===
class MODDER_OT_PickBone(bpy.types.Operator):
    """将当前选中的骨骼填入指定槽位"""
    bl_idname = "modder.pick_bone"
    bl_label = "拾取"
    
    slot_index: bpy.props.IntProperty()
    is_aux: bpy.props.BoolProperty(default=False) 

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        slot = settings.slots[self.slot_index]
        arm_obj = context.active_object
        
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}
            
        # 1. 获取选中的骨骼名称列表
        selected_names = []
        active_name = ""
        
        if context.mode == 'POSE':
            selected_names = [b.name for b in context.selected_pose_bones]
            if context.active_pose_bone:
                active_name = context.active_pose_bone.name
        elif context.mode == 'EDIT':
            selected_names = [b.name for b in context.selected_editable_bones]
            if context.active_bone:
                active_name = context.active_bone.name
        else:
            self.report({'WARNING'}, "请进入 Pose 或 Edit 模式选择骨骼")
            return {'CANCELLED'}
            
        if not selected_names and not active_name:
            self.report({'WARNING'}, "没有选中任何骨骼")
            return {'CANCELLED'}

        # 2. 执行逻辑
        if self.is_aux:
            # === 多选批量添加 ===
            added_count = 0
            for name in selected_names:
                # 过滤1: 不要把自己加进去 (主骨)
                if name == slot.source_bone_name:
                    continue
                # 过滤2: 查重 (不要重复添加)
                if any(aux.name == name for aux in slot.aux_bones):
                    continue
                
                # 添加
                new_aux = slot.aux_bones.add()
                new_aux.name = name
                added_count += 1
            
            if added_count > 0:
                slot.is_expanded = True # 自动展开
                self.report({'INFO'}, f"已批量添加 {added_count} 个辅助骨")
            else:
                self.report({'WARNING'}, "未添加任何新骨骼 (可能是重复或选重了主骨)")
                
        else:
            # === 单选设置主骨 ===
            # 主骨只认“活动骨骼”（最后选中的那个）
            if active_name:
                slot.source_bone_name = active_name
                # 如果这个名字之前在 aux 里，把它删掉（防止自己辅助自己）
                for i, aux in enumerate(slot.aux_bones):
                    if aux.name == active_name:
                        slot.aux_bones.remove(i)
                        break
            else:
                self.report({'WARNING'}, "无法确定活动骨骼，请点击具体的一根骨骼")
                return {'CANCELLED'}
            
        return {'FINISHED'}

# === 清除操作 ===
class MODDER_OT_ClearSlot(bpy.types.Operator):
    """清除槽位内容"""
    bl_idname = "modder.clear_slot"
    bl_label = "清除"
    
    slot_index: bpy.props.IntProperty()
    target: bpy.props.StringProperty() # 'MAIN' or aux_name

    def execute(self, context):
        slot = context.scene.mhw_preset_editor.slots[self.slot_index]
        
        if self.target == 'MAIN':
            slot.source_bone_name = ""
        else:
            # 按名字删除辅助骨
            idx = -1
            for i, aux in enumerate(slot.aux_bones):
                if aux.name == self.target:
                    idx = i
                    break
            if idx != -1:
                slot.aux_bones.remove(idx)
        return {'FINISHED'}

# === 镜像功能 (左 -> 右) ===
class MODDER_OT_MirrorMapping(bpy.types.Operator):
    """将左侧映射规则镜像到右侧 (支持标准格式与紧凑格式)"""
    bl_idname = "modder.mirror_mapping"
    bl_label = "镜像左侧 -> 右侧"

    def execute(self, context):
        slots = context.scene.mhw_preset_editor.slots
        slot_map = {s.std_name: s for s in slots}
        
        # === 定义智能镜像函数 ===
        def get_mirrored_name(name):
            if not name: return None
            
            new_name = name
            
            # 1. 标准分隔符替换 (最安全，优先执行)
            # 例如: _L_ -> _R_, .L -> .R, Left -> Right
            basic_replacements = [
                ("_L_", "_R_"), ("_L.", "_R."), ("_L", "_R"), 
                (".L", ".R"), (" L ", " R "),
                ("Left", "Right"), ("left", "right"),
                ("Lf", "Rt"), ("(L)", "(R)")
            ]
            for old, new in basic_replacements:
                if old in new_name:
                    return new_name.replace(old, new)

            # 2. 紧凑格式/驼峰格式替换 (正则匹配)
            # 场景 A: Bip001LThigh (数字 + L + 大写字母)
            # 场景 B: LThigh (开头 + L + 大写字母)
            
            # 规则：查找 'L'，前提是它后面必须跟着[A-Z]，且前面是[数字]或[开头]
            # re.sub(pattern, replacement, string)
            
            # 匹配: (开头或数字)L(大写字母) -> \1R\2
            # 例如: "1LTwist" -> "1RTwist"
            new_name = re.sub(r'(^|[\d])L(?=[A-Z])', r'\1R', new_name)
            
            # 3. 如果上面都没变，可能是特殊情况，保留原样
            return new_name if new_name != name else None

        count = 0
        
        for l_key in slot_map:
            # 只处理左侧槽位
            if not l_key.endswith("_L"):
                continue
                
            r_key = l_key[:-2] + "_R"
            if r_key not in slot_map:
                continue
                
            l_slot = slot_map[l_key]
            r_slot = slot_map[r_key]
            
            # A. 镜像主骨
            if l_slot.source_bone_name:
                mirrored = get_mirrored_name(l_slot.source_bone_name)
                # 只有当计算出有效且不同的新名字时，才覆盖右侧
                # (避免把 "Spine" 这种无方向的名字强行填进去)
                if mirrored:
                    r_slot.source_bone_name = mirrored
                    count += 1
            
            # B. 镜像辅助骨
            if len(l_slot.aux_bones) > 0:
                # 策略：如果右侧本来是空的，或者强制覆盖模式，则执行
                # 目前逻辑：清空右侧，重新生成
                r_slot.aux_bones.clear()
                r_slot.is_expanded = l_slot.is_expanded
                
                for l_aux in l_slot.aux_bones:
                    mirrored_aux = get_mirrored_name(l_aux.name)
                    if mirrored_aux:
                        new_item = r_slot.aux_bones.add()
                        new_item.name = mirrored_aux
                        count += 1

        self.report({'INFO'}, f"智能镜像完成: 更新 {count} 项")
        return {'FINISHED'}

# === 保存 JSON ===
class MODDER_OT_SaveXPreset(bpy.types.Operator):
    """保存为 X 预设 JSON"""
    bl_idname = "modder.save_x_preset"
    bl_label = "保存预设"

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        
        # 1. 构建字典
        mappings = {}
        fill_count = 0
        
        for slot in settings.slots:
            # 即使 main 为空，只要有 aux 也可以保存，或者完全为空则跳过
            if not slot.source_bone_name and len(slot.aux_bones) == 0:
                continue
                
            entry = {
                "main": [slot.source_bone_name] if slot.source_bone_name else [],
                "aux": [aux.name for aux in slot.aux_bones]
            }
            mappings[slot.std_name] = entry
            fill_count += 1
            
        if fill_count == 0:
            self.report({'ERROR'}, "列表为空，未保存")
            return {'CANCELLED'}

        # 2. 构建完整 JSON 结构
        final_data = {
            "preset_info": {
                "name": settings.new_preset_name,
                "type": "X_PRESET",
                "version": "2.0",
                "description": "Created with MHW Modding Toolkit Editor"
            },
            "mappings": mappings
        }
        
        # 3. 保存文件
        from .bone_mapper import BoneMapManager
        # 借用 BoneMapManager 找路径，这里我们硬编码存到 assets/import_presets
        addon_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        target_dir = os.path.join(addon_dir, "assets", "import_presets")
        
        filename = settings.new_preset_name + ".json"
        # 简单的文件名清理
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
            
        filepath = os.path.join(target_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            self.report({'INFO'}, f"预设已保存: {filename}")
        except Exception as e:
            self.report({'ERROR'}, f"保存失败: {str(e)}")
            return {'CANCELLED'}
            
        return {'FINISHED'}
    
# === 编辑/读取预设 ===
class MODDER_OT_LoadXPreset(bpy.types.Operator):
    """读取选中的 X 预设到编辑器中进行修改"""
    bl_idname = "modder.load_x_preset"
    bl_label = "读取预设"
    bl_options = {'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings # 获取主设置里的文件名
        editor = context.scene.mhw_preset_editor
        
        filename = settings.import_preset_enum
        if not filename:
            self.report({'ERROR'}, "请先在上方选择一个来源预设")
            return {'CANCELLED'}

        # 1. 使用 BoneMapManager 读取 JSON
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x=True):
            self.report({'ERROR'}, f"无法加载文件: {filename}")
            return {'CANCELLED'}
        
        # 2. 填充编辑器
        # 先清空现有列表并初始化
        bpy.ops.modder.init_editor()
        
        # 建立标准名索引
        slot_map = {s.std_name: s for s in editor.slots}
        
        # 将 JSON 数据填回 Slot
        loaded_count = 0
        for std_key, entry in mapper.mapping_data.items():
            if std_key in slot_map:
                slot = slot_map[std_key]
                
                # 填主骨 (取第一个)
                mains = entry.get("main", [])
                if mains:
                    slot.source_bone_name = mains[0]
                    
                # 填辅助骨
                auxs = entry.get("aux", [])
                for aux_name in auxs:
                    new_aux = slot.aux_bones.add()
                    new_aux.name = aux_name
                
                if mains or auxs:
                    loaded_count += 1
        
        # 3. 同步文件名到“新建名称”框，方便覆盖保存
        # 去掉 .json 后缀
        clean_name = filename.rsplit('.', 1)[0]
        editor.new_preset_name = clean_name
        
        self.report({'INFO'}, f"成功加载预设: {clean_name} (包含 {loaded_count} 个映射)")
        return {'FINISHED'}

# === 删除预设 ===
class MODDER_OT_DeleteXPreset(bpy.types.Operator):
    """删除当前选中的 X 预设文件"""
    bl_idname = "modder.delete_x_preset"
    bl_label = "删除预设"
    bl_options = {'INTERNAL'} # 标记为内部操作，通常加个确认框会更好

    # 简易确认弹窗
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        filename = settings.import_preset_enum
        
        if not filename:
            return {'CANCELLED'}
            
        # 获取真实路径
        mapper = BoneMapManager()
        filepath = mapper.get_preset_path(filename, is_import_x=True)
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                # 强制刷新 UI 列表 (Blender EnumProperty 有缓存，可能需要鼠标晃一下才能刷具体)
                # 这里我们重置一下变量名来触发更新
                settings.import_preset_enum = "" 
                self.report({'INFO'}, f"已删除文件: {filename}")
            except Exception as e:
                self.report({'ERROR'}, f"删除失败: {e}")
        else:
            self.report({'ERROR'}, "文件不存在")
            
        return {'FINISHED'}
    
classes = [
    MODDER_OT_InitEditor,
    MODDER_OT_PickBone,
    MODDER_OT_ClearSlot,
    MODDER_OT_MirrorMapping,
    MODDER_OT_SaveXPreset,
    MODDER_OT_LoadXPreset,
    MODDER_OT_DeleteXPreset,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)