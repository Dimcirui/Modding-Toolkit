# translations.py
"""
Bilingual (Chinese/English) translations for Modding Toolkit.
Keys are the exact Chinese strings used in the source code.
No zh_CN entries needed — Blender falls back to the original string.
"""

TRANSLATIONS = {
    "en_US": {
        # -----------------------------------------------
        # MHW_PT_SuiteSettings PropertyGroup — prop names
        # -----------------------------------------------
        ("*", "基础工具"): "Basic Tools",
        ("*", "通用骨架转换"): "Universal Armature Converter",
        ("*", "实验性功能"): "Experimental Features",
        ("*", "来源预设 (X)"): "Source Preset (X)",
        ("*", "目标游戏 (Y)"): "Target Game (Y)",
        ("*", "显示映射细节"): "Show Mapping Details",
        ("*", "姿态转换"): "Pose Convert",
        ("*", "骨架预设"): "Armature Preset",
        ("*", "姿态记录"): "Pose Record",
        ("*", "装备包"): "Armor Pack",
        ("*", "套装种类"): "Suit Type",
        ("*", "装备"): "Armor",
        ("*", "使用 Bonesystem"): "Use Bonesystem",
        ("*", "FBXSkel 定义名"): "FBXSkel Definition Name",
        ("*", "骨架"): "Armature",
        ("*", "隐藏面部"): "Hide Face",
        ("*", "隐藏头发"): "Hide Hair",
        ("*", "隐藏投射器"): "Hide Slinger",
        ("*", "绑定面部"): "Bind Face",
        ("*", "绑定部位"): "Bind Part",
        ("*", "未选项使用空模型"): "Use Blank Model for Unselected",
        ("*", "使用假头法"): "Use FakeBone Method",

        # -----------------------------------------------
        # MHW_PT_SuiteSettings PropertyGroup — descriptions
        # -----------------------------------------------
        ("*", "选择导入模型的骨架结构"): "Select the armature structure of the imported model",
        ("*", "选择要导出的目标游戏"): "Select the target game to export to",
        ("*", "用于识别骨骼名称的预设"): "Preset used to identify bone names",
        ("*", "选择已保存的姿态矩阵记录"): "Select a saved pose matrix record",
        ("*", "选择 MHWs 装备包 JSON"): "Select MHWs armor pack JSON",
        ("*", "选择套装变体（男猎/女猎 × 男套/女套）"): "Select suit variant (male/female hunter x male/female suit)",
        ("*", "选择要导出的装备"): "Select the armor to export",
        ("*", "导出时同时生成 fbxskel.7 和 BoneSystem JSON（需要 Bonesystem 框架）"): "Also generate fbxskel.7 and BoneSystem JSON on export (requires Bonesystem framework)",
        ("*", "写入 JSON 的 FbxPath 字段，同时作为 .fbxskel.7 文件名（如 ch03_000_9000）"): "FbxPath field written to JSON, also used as the .fbxskel.7 filename (e.g. ch03_000_9000)",
        ("*", "用于生成 fbxskel 的 MHWs 角色骨架"): "MHWs character armature used to generate fbxskel",
        ("*", "导出时对未选择集合的栏位，复制内置空文件代替跳过"): "For unselected collection slots on export, copy built-in blank file instead of skipping",
        ("*", "导出 fbxskel 前自动生成身体+手指 End 骨骼（原生骨架由预设 native_skeleton 字段指定）"): "Automatically generate body + finger End bones before exporting fbxskel (native armature specified by preset native_skeleton field)",

        # -----------------------------------------------
        # bone_view_mode enum items
        # -----------------------------------------------
        ("*", "全显"): "Show All",
        ("*", "仅基础骨"): "Base Bones Only",
        ("*", "仅物理骨"): "Physics Bones Only",
        ("*", "显示所有骨骼"): "Show all bones",
        ("*", "隐藏物理骨，只显示预设基础骨"): "Hide physics bones, show only preset base bones",
        ("*", "隐藏基础骨，只显示物理骨"): "Hide base bones, show only physics bones",

        # -----------------------------------------------
        # mhws_bs_bind_part enum items
        # -----------------------------------------------
        ("*", "头盔"): "Helmet",
        ("*", "身体"): "Body",

        # -----------------------------------------------
        # MHW_OT_GeneralTools — operator label & description
        # -----------------------------------------------
        ("*", "通用工具"): "General Tools",
        ("*", "通用工具集合"): "Collection of general utility tools",

        # -----------------------------------------------
        # MHW_OT_GeneralTools — action enum item labels and descriptions
        # -----------------------------------------------
        ("*", "扭转归零"): "Roll to Zero",
        ("*", "递归将选中骨骼的 Roll 设为 0"): "Recursively set Roll to 0 for selected bones",
        ("*", "添加尾骨"): "Add Tail Bone",
        ("*", "在选中骨骼末端添加垂直骨骼"): "Add a vertical bone at the tip of selected bones",
        ("*", "镜像对齐 X"): "Mirror Align X",
        ("*", "以 X+ 为基准镜像对齐 X- 骨骼"): "Mirror-align X- bones using X+ as reference",
        ("*", "骨链简化"): "Simplify Chain",
        ("*", "按链结构两两配对删减骨骼并合并权重，自动跳过尾骨"): "Pair and reduce bones by chain structure, merging weights; tail bones are skipped automatically",
        ("*", "合并到激活骨"): "Merge to Active Bone",
        ("*", "将其余选中骨骼的权重全部合并到激活骨（最后点击的那根），并删除其余骨骼"): "Merge all weights of other selected bones into the active bone (last clicked), then delete them",
        ("*", "骨架对齐 (完全)"): "Align Armatures (Full)",
        ("*", "按骨骼名完全对齐两个骨架 (head+tail)，需选中两个骨架"): "Fully align two armatures by bone name (head+tail); two armatures must be selected",
        ("*", "骨架对齐 (位置)"): "Align Armatures (Position)",
        ("*", "按骨骼名对齐 head 位置，保持骨骼方向，需选中两个骨架"): "Align head positions by bone name, keep bone direction; two armatures must be selected",

        # -----------------------------------------------
        # Main panel — section header labels (layout.label text=)
        # -----------------------------------------------
        ("*", "通用标准转换"): "Universal Standard Converter",
        ("*", "姿态转换 (Pose Convert)"): "Pose Convert",
        ("*", "简易工具:"): "Quick Tools:",
        ("*", "姿态变换记录器:"): "Pose Transform Recorder:",
        ("*", "骨骼显示 [X]:"): "Bone Visibility [X]:",

        # -----------------------------------------------
        # Main panel — operator button texts (layout.operator text=)
        # -----------------------------------------------
        ("*", "扭转归零 (Roll=0)"): "Roll to Zero (Roll=0)",
        ("*", "对齐 (完全)"): "Align (Full)",
        ("*", "对齐 (位置)"): "Align (Position)",
        ("*", "对齐骨骼 [X+Y, 双骨架]"): "Align Bones [X+Y, Dual Armature]",
        ("*", "重命名顶点组 [X+Y]"): "Rename Vertex Groups [X+Y]",
        ("*", "移植物理骨骼 [X+Y, 双骨架]"): "Graft Physics Bones [X+Y, Dual Armature]",
        ("*", "物理权重降级 [X]"): "Downgrade Physics Weights [X]",
        ("*", "剔除非基础骨骼 [X]"): "Remove Non-Base Bones [X]",
        ("*", "基础骨骼改名 [X+Y]"): "Rename Base Bones [X+Y]",
        ("*", "对齐非物理骨骼"): "Align Non-Physics Bones",
        ("*", "Endfield 面部改名"): "Endfield Face Rename",
        ("*", "面部权重简化"): "Simplify Face Weights",
        ("*", "MDF2 + Tex 处理器"): "MDF2 + Tex Processor",
        ("*", "一键创建 RE Chain"): "One-Click Create RE Chain",
        ("*", "生成假骨骼"): "Generate Fake Bones",
        ("*", "同步子级朝向及扭转"): "Sync Child Orientation & Roll",
        ("*", "RE Engine 矩阵归零 (生化9除外)"): "RE Engine Matrix Reset (except RE9)",
        ("*", "录制变换 (选两个骨架)"): "Record Transform (Select Two Armatures)",
        ("*", "▶ 正向 (A→B)"): "Forward (A to B)",
        ("*", "◀ 逆向 (B→A)"): "Inverse (B to A)",

        # -----------------------------------------------
        # Conditional / status labels
        # -----------------------------------------------
        ("*", "缺失"): "Missing",
        ("*", "请选中骨架以预览"): "Select an armature to preview",
        ("*", "需要 RE Mesh Editor!"): "Requires RE Mesh Editor!",
        ("*", "需要 RE Chain Editor!"): "Requires RE Chain Editor!",

        # -----------------------------------------------
        # MHW_OT_GeneralTools bone_view_mode button labels
        # (appear in layout.operator calls in the experimental section)
        # -----------------------------------------------
        ("*", "假头法 (FakeBone)"): "FakeBone Method",

        # === core/ui_config.py ===

        # BONE_DISPLAY_NAMES — torso
        ("*", "胯部 (pelvis)"):    "Pelvis (pelvis)",
        ("*", "腰腹部 (spine_01)"): "Abdomen (spine_01)",
        ("*", "胸腔 (spine_02)"):  "Chest (spine_02)",
        ("*", "上胸 (spine_03)"):  "Upper Chest (spine_03)",
        ("*", "颈部 (neck)"):      "Neck (neck)",
        ("*", "头部 (head)"):      "Head (head)",

        # BONE_DISPLAY_NAMES — left arm
        ("*", "左肩 (clavicle_L)"):    "L Shoulder (clavicle_L)",
        ("*", "左上臂 (upperarm_L)"):   "L Upper Arm (upperarm_L)",
        ("*", "左前臂 (forearm_L)"):    "L Forearm (forearm_L)",
        ("*", "左手掌 (hand_L)"):       "L Palm (hand_L)",

        # BONE_DISPLAY_NAMES — right arm
        ("*", "右肩 (clavicle_R)"):    "R Shoulder (clavicle_R)",
        ("*", "右上臂 (upperarm_R)"):   "R Upper Arm (upperarm_R)",
        ("*", "右前臂 (forearm_R)"):    "R Forearm (forearm_R)",
        ("*", "右手掌 (hand_R)"):       "R Palm (hand_R)",

        # BONE_DISPLAY_NAMES — left leg
        ("*", "左大腿 (thigh_L)"): "L Thigh (thigh_L)",
        ("*", "左小腿 (shin_L)"):  "L Shin (shin_L)",
        ("*", "左脚掌 (foot_L)"): "L Foot (foot_L)",
        ("*", "左脚趾 (toe_L)"):   "L Toes (toe_L)",

        # BONE_DISPLAY_NAMES — right leg
        ("*", "右大腿 (thigh_R)"): "R Thigh (thigh_R)",
        ("*", "右小腿 (shin_R)"):  "R Shin (shin_R)",
        ("*", "右脚掌 (foot_R)"): "R Foot (foot_R)",
        ("*", "右脚趾 (toe_R)"):   "R Toes (toe_R)",

        # BONE_DISPLAY_NAMES — left fingers
        ("*", "左拇指1"): "L Thumb 1",
        ("*", "左拇指2"): "L Thumb 2",
        ("*", "左拇指3"): "L Thumb 3",
        ("*", "左食指1"): "L Index 1",
        ("*", "左食指2"): "L Index 2",
        ("*", "左食指3"): "L Index 3",
        ("*", "左中指1"): "L Middle 1",
        ("*", "左中指2"): "L Middle 2",
        ("*", "左中指3"): "L Middle 3",
        ("*", "左无名指1"): "L Ring 1",
        ("*", "左无名指2"): "L Ring 2",
        ("*", "左无名指3"): "L Ring 3",
        ("*", "左小指1"): "L Pinky 1",
        ("*", "左小指2"): "L Pinky 2",
        ("*", "左小指3"): "L Pinky 3",

        # BONE_DISPLAY_NAMES — right fingers
        ("*", "右拇指1"): "R Thumb 1",
        ("*", "右拇指2"): "R Thumb 2",
        ("*", "右拇指3"): "R Thumb 3",
        ("*", "右食指1"): "R Index 1",
        ("*", "右食指2"): "R Index 2",
        ("*", "右食指3"): "R Index 3",
        ("*", "右中指1"): "R Middle 1",
        ("*", "右中指2"): "R Middle 2",
        ("*", "右中指3"): "R Middle 3",
        ("*", "右无名指1"): "R Ring 1",
        ("*", "右无名指2"): "R Ring 2",
        ("*", "右无名指3"): "R Ring 3",
        ("*", "右小指1"): "R Pinky 1",
        ("*", "右小指2"): "R Pinky 2",
        ("*", "右小指3"): "R Pinky 3",

        # OPTIONAL_BONES — suffix string
        ("*", "可选 | 上胸"): "Optional | Upper Chest",

        # Composite display name for optional bone (as returned by get_display_name)
        ("*", "上胸 (spine_03)  [可选 | 上胸]"): "Upper Chest (spine_03)  [Optional | Upper Chest]",

        # UI_HIERARCHY — top-level section names
        ("*", "躯干和头部"): "Torso & Head",
        ("*", "手臂"):      "Arms",
        ("*", "腿部"):      "Legs",
        ("*", "手指 (左)"): "Fingers (L)",
        ("*", "手指 (右)"): "Fingers (R)",

        # UI_HIERARCHY — subsection names
        ("*", "脊椎"):  "Spine",
        ("*", "上半身"): "Upper Body",
        ("*", "左臂"):  "Left Arm",
        ("*", "右臂"):  "Right Arm",
        ("*", "左腿"):  "Left Leg",
        ("*", "右腿"):  "Right Leg",
        ("*", "拇指"):  "Thumb",
        ("*", "食指"):  "Index",
        ("*", "中指"):  "Middle",
        ("*", "无名指"): "Ring",
        ("*", "小指"):  "Pinky",

        # === ui/editor_panel.py ===

        # MHW_PT_PresetEditor — panel label
        ("*", "预设编辑器"): "Preset Editor",

        # MHW_PT_PresetEditor — section header labels (layout.label text=)
        ("*", "管理现有预设 (Manage):"): "Manage Existing Presets (Manage):",
        ("*", "编辑器工作区:"): "Editor Workspace:",
        ("*", "列表为空，请点击初始化"): "List is empty, click to initialize",

        # MHW_PT_PresetEditor — operator button texts (layout.operator / row.operator text=)
        ("*", "读取/编辑"): "Load / Edit",
        ("*", "打开预设文件夹"): "Open Preset Folder",
        ("*", "复制为 Y 预设 (X转换)"): "Copy as Y Preset (X Convert)",
        ("*", "复制为 X 预设 (Y转换)"): "Copy as X Preset (Y Convert)",
        ("*", "保存"): "Save",
        ("*", "清空并初始化列表"): "Clear and Initialize List",

        # MHW_PT_PresetEditor — prop text label
        ("*", "保存名"): "Save Name",

        # MHW_PT_PresetEditor — slot status label
        ("*", "[未设置]"): "[Not Set]",

        # === core/editor_props.py ===

        # EditorSettings — prop names
        ("*", "预设名称"): "Preset Name",
        ("*", "搜索"): "Search",
        ("*", "编辑模式"): "Edit Mode",

        # EditorSettings — prop descriptions
        ("*", "过滤骨骼名称"): "Filter bone names",

        # EditorSettings — edit_mode enum item labels
        ("*", "X 预设 (来源)"): "X Preset (Source)",
        ("*", "Y 预设 (目标)"): "Y Preset (Target)",

        # EditorSettings — edit_mode enum item descriptions
        ("*", "编辑来源游戏的骨骼映射预设"): "Edit the bone mapping preset for the source game",
        ("*", "编辑目标游戏的骨骼映射预设"): "Edit the bone mapping preset for the target game",

        # === core/editor_ops.py ===

        # Operator bl_label strings
        ("*", "初始化/刷新列表"): "Initialize / Refresh List",
        ("*", "拾取"): "Pick",
        ("*", "清除"): "Clear",
        ("*", "镜像左侧 -> 右侧"): "Mirror Left -> Right",
        ("*", "保存预设"): "Save Preset",
        ("*", "读取预设"): "Load Preset",
        ("*", "删除预设"): "Delete Preset",
        ("*", "转换预设"): "Convert Preset",

        # Operator docstring / bl_description strings
        ("*", "初始化预设编辑器列表"): "Initialize the preset editor list",
        ("*", "将当前选中的骨骼填入指定槽位"): "Fill the specified slot with the currently selected bone",
        ("*", "清除槽位内容"): "Clear slot contents",
        ("*", "将左侧映射规则镜像到右侧"): "Mirror left-side mapping rules to the right side",
        ("*", "保存预设 JSON（根据编辑模式保存为 X 或 Y 预设）"): "Save preset JSON (saves as X or Y preset depending on edit mode)",
        ("*", "读取选中的预设到编辑器中进行修改"): "Load the selected preset into the editor for modification",
        ("*", "删除当前选中的预设文件"): "Delete the currently selected preset file",
        ("*", "在文件管理器中打开当前预设所在的文件夹"): "Open the folder containing the current preset in file manager",
        ("*", "复制当前预设到另一类型目录（X→Y 或 Y→X），文件名加转换标记"): "Copy current preset to the other type directory (X→Y or Y→X), appending a conversion marker to the filename",

        # Static report messages
        ("*", "编辑器已重置"): "Editor has been reset",
        ("*", "请先选中一个骨架"): "Please select an armature first",
        ("*", "请进入 Pose 或 Edit 模式选择骨骼"): "Please enter Pose or Edit mode to select bones",
        ("*", "没有选中任何骨骼"): "No bones selected",
        ("*", "未添加任何新骨骼 (可能是重复或选重了主骨)"): "No new bones added (possibly duplicates or main bone reselected)",
        ("*", "无法确定活动骨骼，请点击具体的一根骨骼"): "Cannot determine active bone, please click a specific bone",
        ("*", "列表为空，未保存"): "List is empty, nothing saved",
        ("*", "未选择任何预设"): "No preset selected",
        ("*", "文件不存在"): "File does not exist",

        # Template report messages (variable substitution with %)
        ("*", "已批量添加 %d 个辅助骨"): "Batch added %d auxiliary bones",
        ("*", "智能镜像完成: 更新 %d 项"): "Smart mirror complete: updated %d items",
        ("*", "%s 预设已保存: %s"): "%s preset saved: %s",
        ("*", "保存失败: %s"): "Save failed: %s",
        ("*", "无法加载文件: %s"): "Cannot load file: %s",
        ("*", "成功加载%s预设: %s (%d 个映射)"): "Successfully loaded %s preset: %s (%d mappings)",
        ("*", "已删除: %s"): "Deleted: %s",
        ("*", "删除失败: %s"): "Delete failed: %s",
        ("*", "文件夹不存在: %s"): "Folder does not exist: %s",
        ("*", "源文件不存在: %s"): "Source file does not exist: %s",
        ("*", "目标文件已存在: %s，已跳过覆盖"): "Target file already exists: %s, skipped overwrite",
        ("*", "已复制 (%s): %s"): "Copied (%s): %s",
        ("*", "转换失败: %s"): "Conversion failed: %s",
    },
}
