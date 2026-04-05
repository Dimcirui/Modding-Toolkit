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
        ("*", "合并链到激活链"): "Merge Chains to Active",
        ("*", "选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链，超出部分合并到链末"): "Select heads of multiple chains; merge other chains positionally into the active chain, with overflow merged into the last bone",
        ("*", "未找到有效的待合并链首（请选中其他链的链首骨骼）"): "No valid source chain heads found (select head bones of other chains)",
        ("*", "已将 %d 条链合并到 [%s]，共处理 %d 对骨骼"): "Merged %d chains into [%s], processed %d bone pairs",
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
        ("*", "骨架清理:"): "Armature Cleanup:",
        ("*", "物理链工具:"): "Physics Chain Tools:",

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
        ("*", "合并到父骨"): "Merge into Parent",
        ("*", "标记为主链延伸"): "Mark as Main Continue",
        ("*", "清除标记"): "Clear Mark",
        ("*", "刷新骨骼颜色 [X]"): "Refresh Bone Colors [X]",
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

        # === core/standard_ops.py ===

        # Operator bl_label strings
        ("*", "1. 标准化重命名 (X)"): "1. Standardize Rename (X)",
        ("*", "2. 转换为游戏名 (Y)"): "2. Convert to Game Name (Y)",
        ("*", "一键转换 (X -> Y)"): "One-Click Convert (X -> Y)",
        ("*", "0. 骨架对齐 (Snap)"): "0. Armature Snap",
        ("*", "3. 物理骨移植 (+End Bone)"): "3. Graft Physics Bones (+End Bone)",
        ("*", "物理权重降级"): "Downgrade Physics Weights",
        ("*", "基础骨骼改名 (X->Y)"): "Rename Base Bones (X->Y)",
        ("*", "剔除非基础骨骼"): "Remove Non-Base Bones",
        ("*", "骨骼可见性"): "Bone Visibility",
        ("*", "刷新骨骼颜色"): "Refresh Bone Colors",
        ("*", "清除链角色标记"): "Clear Chain Role Mark",

        # Operator bl_description strings
        ("*", "执行标准化 X：合并权重并重命名为基础名"): "Execute Standard X: merge weights and rename to base names",
        ("*", "执行标准化 Y：将基础名转为目标游戏名"): "Execute Standard Y: convert base names to target game names",
        ("*", "将选中网格的顶点组转换成目标游戏的格式"): "Convert vertex groups of selected meshes to the target game format",
        ("*", "将目标游戏骨架的身体骨骼对齐来源预设骨骼（后选要修改的目标骨架）"): "Align the body bones of the target game armature to the source preset bones (select target armature last)",
        ("*", "将物理骨骼的顶点组权重合并到其最近的基础骨骼上 (通过 X 预设判断)。\n用于不需要物理效果或目标游戏不支持物理的降级场景"): "Merge physics bone vertex group weights into their nearest base bone (determined by X preset).\nFor downgrade scenarios where physics is unsupported or unneeded",
        ("*", "将骨架上的基础骨骼名从来源名 (X) 改为目标游戏名 (Y)。\n用于手动对齐工作流: 改名后骨骼名与目标游戏一致, 方便手动对齐和数据传递"): "Rename base bones on the armature from source name (X) to target game name (Y).\nFor manual alignment workflows: renamed bones match the target game for easier alignment and data transfer",
        ("*", "删除骨架中所有非基础骨骼 (通过 X 预设判断)。\n建议先执行物理权重降级再使用此功能"): "Delete all non-base bones in the armature (determined by X preset).\nRecommended to run Downgrade Physics Weights first",
        ("*", "按模式控制骨骼可见性（全显 / 仅基础骨 / 仅物理骨），后两者需加载 X 预设"): "Control bone visibility by mode (All / Base Only / Physics Only); the latter two require loading the X preset",
        ("*", "根据骨骼的 chain_role 自定义属性刷新物理骨骼的颜色标记"): "Refresh physics bone color marks based on the bone's chain_role custom property",
        ("*", "将选中骨骼标记为主链延伸 (chain_role = main_continue)，并染为琥珀金色。\n在分叉处标记哪个子骨是主链方向，未标记的子骨将被视为支链头"): "Mark selected bones as main chain continue (chain_role = main_continue) and color them amber gold.\nAt forks, mark which child bone continues the main chain; unmarked children will be treated as branch heads",
        ("*", "清除选中骨骼的 chain_role 标记，恢复为普通体骨（深蓝色）"): "Clear the chain_role mark on selected bones, reverting them to regular body bones (deep blue)",
        ("*", "将选中骨骼的顶点权重合并到其父骨骼，并删除选中骨骼。\n用于清理功能性根骨（如 hair_root 等无物理模拟的连接器骨骼）"): "Merge selected bone vertex weights into its parent bone and delete the selected bone.\nFor cleaning up functional root bones (connector bones without physics simulation, such as hair_root)",

        # Static report messages
        ("*", "预设加载失败"): "Preset load failed",
        ("*", "无法加载 Y 预设"): "Cannot load Y preset",
        ("*", "请至少选中一个网格 (Mesh)"): "Please select at least one mesh",
        ("*", "无法加载 X 预设"): "Cannot load X preset",
        ("*", "X与Y预设之间没有共同的骨骼映射"): "No common bone mappings between X and Y presets",
        ("*", "操作对象错误: 请先选中源骨架(X)，再按住Ctrl选中目标骨架(Y)"): "Operation error: please select source armature (X) first, then Ctrl-select target armature (Y)",
        ("*", "无法加载源预设 (In)"): "Cannot load source preset (In)",
        ("*", "无法加载目标预设 (Out)"): "Cannot load target preset (Out)",
        ("*", "未检测到物理骨骼"): "No physics bones detected",
        ("*", "请至少选中一个网格"): "Please select at least one mesh",
        ("*", "选中的网格没有绑定骨架"): "Selected meshes have no bound armature",
        ("*", "未检测到物理骨骼的顶点组"): "No physics bone vertex groups detected",
        ("*", "没有需要改名的骨骼 (来源和目标名称已一致)"): "No bones need renaming (source and target names already match)",
        ("*", "没有需要剔除的骨骼"): "No bones to remove",
        ("*", "骨骼颜色已刷新"): "Bone colors refreshed",
        ("*", "请在姿态模式下选中骨骼"): "Please select bones in Pose Mode",
        ("*", "请在姿态模式或编辑模式下操作"): "Please operate in Pose Mode or Edit Mode",
        ("*", "选中的骨骼没有可用的父骨骼"): "Selected bones have no valid parent bone",

        # Template report messages
        ("*", "标准化完成: 重命名 %d 根, 清理 %d 根辅助骨"): "Standardization complete: renamed %d, cleaned %d auxiliary bones",
        ("*", "处理完成: 已更新 %d 个网格的顶点组"): "Done: updated vertex groups in %d meshes",
        ("*", "刚性对齐完成: %d 根骨骼"): "Rigid snap complete: %d bones",
        ("*", "移植完成: 处理 %d 根骨骼 (含自动生成的末端骨)"): "Graft complete: processed %d bones (including auto-generated end bones)",
        ("*", "物理权重降级完成: 在 %d 个网格上合并了 %d 个物理顶点组"): "Physics weight downgrade complete: merged %d physics vertex groups across %d meshes",
        ("*", "已将 %d 根骨骼改名为目标游戏名"): "Renamed %d bones to target game names",
        ("*", "已剔除 %d 根非基础骨骼"): "Removed %d non-base bones",
        ("*", "骨骼显示: %s"): "Bone display: %s",
        ("*", "已标记 %d 根骨骼为主链延伸"): "Marked %d bones as main continue",
        ("*", "已清除 %d 根骨骼的链角色标记"): "Cleared chain role mark from %d bones",
        ("*", "已合并 %d 根骨骼到父骨"): "Merged %d bones into parent",
        ("*", "操作失败：请先选择 In 骨架，再 Ctrl 加选 Out 骨架(Out需为黄色激活状态)"): "Operation failed: please select the In armature first, then Ctrl-select the Out armature (Out must be the active yellow object)",
        ("*", "操作失败：未找到来源(In)骨架"): "Operation failed: source (In) armature not found",

        # === core/pose_ops.py ===

        # Operator bl_label strings
        ("*", "方向计算 (简单T转A)"): "Direction Calc (Simple T to A)",
        ("*", "RE Engine 矩阵归零"): "RE Engine Matrix Reset",
        ("*", "录制变换"): "Record Transform",
        ("*", "正向 (A->B)"): "Forward (A->B)",
        ("*", "逆向 (B->A)"): "Inverse (B->A)",
        ("*", "删除记录"): "Delete Record",

        # Operator bl_description strings
        ("*", "仅将上臂旋转到水平方向，适用于简单的 A-Pose 骨架（如MMD），如果无法正确运作，请使用更通用的姿态变换记录器"): "Rotate upper arms to horizontal only; suitable for simple A-Pose armatures (e.g. MMD). If it does not work correctly, use the more general Pose Transform Recorder",
        ("*", "RE Engine 专用: 重置肢体骨骼旋转矩阵为 T-Pose (适用于荒野/街霸6/生化4等，生化9除外)"): "RE Engine only: reset limb bone rotation matrices to T-Pose (for Wilds/SF6/RE4 etc., except RE9)",
        ("*", "录制相对变换: 先选 A 姿态骨架，再 Ctrl 选 B 姿态骨架，计算并保存 A->B 的变换"): "Record relative transform: select A-pose armature first, then Ctrl-select B-pose armature, compute and save A->B transform",
        ("*", "正向应用变换 (A->B): 将选中骨架从 A 姿态转换为 B 姿态"): "Apply transform forward (A->B): convert selected armature from A-pose to B-pose",
        ("*", "逆向应用变换 (B->A): 将选中骨架从 B 姿态转换回 A 姿态"): "Apply transform inverse (B->A): convert selected armature from B-pose back to A-pose",
        ("*", "删除选中的变换记录"): "Delete the selected transform record",

        # Static report messages
        ("*", "无法加载骨架预设"): "Cannot load armature preset",
        ("*", "未找到上臂骨骼"): "Upper arm bones not found",
        ("*", "预设中没有匹配到任何骨骼"): "No bones matched in preset",
        ("*", "请选中两个骨架: 先选 A 姿态, 再 Ctrl 选 B 姿态"): "Please select two armatures: A-pose first, then Ctrl-select B-pose",
        ("*", "名称不能为空"): "Name cannot be empty",
        ("*", "请确保选中了两个骨架对象"): "Please make sure two armature objects are selected",
        ("*", "两个骨架没有同名骨骼"): "The two armatures have no bones with the same name",
        ("*", "两个骨架的姿态几乎相同, 没有显著变换可记录"): "The two armatures have nearly identical poses; no significant transform to record",
        ("*", "未选择变换记录"): "No transform record selected",
        ("*", "记录文件中没有变换数据"): "No transform data in record file",
        ("*", "骨架与变换记录之间找不到对应的骨骼 (请检查骨架预设)"): "No matching bones found between armature and transform record (check armature preset)",

        # Template report messages
        ("*", "方向计算完成: %d 根上臂骨骼, %d 个网格"): "Direction calc complete: %d upper arm bones, %d meshes",
        ("*", "RE Engine 矩阵归零完成: %d 根骨骼, %d 个网格"): "RE Engine matrix reset complete: %d bones, %d meshes",
        ("*", "已录制 %d 根骨骼的变换 -> %s"): "Recorded transforms for %d bones -> %s",
        ("*", "文件不存在: %s"): "File does not exist: %s",
        ("*", "读取失败: %s"): "Read failed: %s",
        ("*", "变换完成 (%s): %d 根骨骼, %d 个网格"): "Transform complete (%s): %d bones, %d meshes",

        # === ui/main_panel.py report messages ===
        ("*", "请在编辑模式下至少选中一根骨骼"): "Please select at least one bone in Edit mode",
        ("*", "已重置 %d 根骨骼的 Roll"): "Reset Roll for %d bones",
        ("*", "请选中需要加尾巴的骨骼"): "Please select the bones to add tail bones to",
        ("*", "添加了 %d 根尾骨"): "Added %d tail bones",
        ("*", "请正好选中两个骨骼进行镜像对齐"): "Please select exactly two bones for mirror align",
        ("*", "请选中两个骨骼"): "Please select two bones",
        ("*", "骨骼未找到"): "Bone not found",
        ("*", "已将 %s 对齐到 %s"): "Aligned %s to %s",
        ("*", "至少需要选中两个骨骼"): "Please select at least two bones",
        ("*", "未生成任何配对（骨骼数不足或全为尾骨）"): "No pairs generated (too few bones or all are tail bones)",
        ("*", "骨链简化完成: 处理 %d 对骨骼"): "Chain simplification complete: processed %d bone pairs",
        ("*", "请确保有激活骨骼（最后点击的那根为保留目标）"): "Please ensure there is an active bone (the last clicked one is the merge target)",
        ("*", "请至少选中两根骨骼（激活骨保留，其余骨并入）"): "Please select at least two bones (active bone is kept, others are merged in)",
        ("*", "已将 %d 根骨骼并入 [%s]"): "Merged %d bones into [%s]",
        ("*", "请选中两个骨架（激活的为目标，另一个为源）"): "Please select two armatures (the active one is the target, the other is the source)",
        ("*", "%s: %d 根骨骼"): "%s: %d bones",
        ("*", "完全对齐"): "Full Align",
        ("*", "位置对齐"): "Position Align",

        # === games/mhws/ ===

        ("*", "Settings 模式"):              "Settings Mode",
        ("*", "MHWs 装备批量导出对话框"):    "MHWs Batch Export Dialog",

        # MHWS_OT_EndfieldFaceRename — bl_description
        ("*", "将 Endfield 面部顶点组名称批量转换为 MHWilds 格式"): "Batch-convert Endfield face vertex group names to MHWilds format",

        # MHWS_OT_FaceWeightSimplify — bl_description
        ("*", "简化面部权重: 将 MHWilds 格式的细分面部骨骼权重合并到主要骨骼上"): "Simplify face weights: merge MHWilds subdivided face bone weights into primary bones",

        # MHWS_OT_AutoCreateChains — bl_description
        ("*", "在姿态模式下，根据物理骨骼的 chain_role 属性自动为每条链创建 Chain Settings 和 Chain Group。\n支持分叉物理链，分叉链使用实验模式生成，线性链使用默认模式生成。\n需要 RE Chain Editor 插件，且场景中存在已创建 Chain Header 的 Chain Collection。"): "In pose mode, automatically create Chain Settings and Chain Group for each chain based on bone chain_role properties.\nSupports branching physics chains; branching chains use experimental mode, linear chains use default mode.\nRequires the RE Chain Editor addon, and the scene must have a Chain Collection with a Chain Header already created.",

        # MHWS_OT_AutoCreateChains — chain_collection EnumProperty description
        ("*", "选择要写入的 Chain Collection"): "Select the Chain Collection to write to",

        # MHWS_OT_AutoCreateChains — settings_mode EnumProperty items
        ("*", "各自独立"): "Separate",
        ("*", "每条链拥有独立的 Chain Settings"): "Each chain has its own Chain Settings",
        ("*", "共享同一"): "Shared",
        ("*", "所有链共用同一个 Chain Settings"): "All chains share a single Chain Settings",

        # MHWS_OT_EndfieldFaceRename — self.report (template)
        ("*", "已处理 %d 个面部顶点组"): "Processed %d face vertex groups",

        # MHWS_OT_FaceWeightSimplify — self.report (static)
        ("*", "面部权重简化完成"): "Face weight simplification complete",

        # MHWS_OT_AutoCreateChains — self.report (static)
        ("*", "未找到有效的 Chain Collection（需含 ~TYPE=RE_CHAIN_COLLECTION 且名称含 .chain/.clsp）"): "No valid Chain Collection found (must have ~TYPE=RE_CHAIN_COLLECTION and name containing .chain/.clsp)",
        ("*", "未找到 RE Chain 场景属性，请确认插件已正确加载"): "RE Chain scene property not found, please confirm the addon is loaded correctly",
        ("*", "未找到链首骨骼（chain_role=head/branch_head），请先刷新骨骼颜色"): "No chain-head bones found (chain_role=head/branch_head), please refresh bone colors first",
        ("*", "无法创建 Chain Settings"): "Cannot create Chain Settings",

        # MHWS_OT_AutoCreateChains — self.report (template)
        ("*", "找不到集合: %s"): "Collection not found: %s",
        ("*", "集合 '%s' 中未找到 Chain Header，请先创建"): "No Chain Header found in collection '%s', please create one first",
        ("*", "已创建 %d 条链，跳过 %d 条"): "Created %d chains, skipped %d",

        # games/mhws/batch_export_ui.py — layout label strings
        ("*", "未设置"): "Not set",
        ("*", "请选择装备以配置绑定"): "Please select armor to configure bindings",
        ("*", "FBXSkel 名"): "FBXSkel Name",

        # === games/re4/ ===

        # RE4_OT_FakeBone_OneClick — bl_label, bl_description
        ("*", "(假头法) 生成假骨骼"): "(FakeBone) Generate Fake Bones",
        ("*", "(假头法) 一键为选中骨架生成全套 End 骨骼"): "(FakeBone) One-click generate full End bones for the selected armature",

        # RE4_OT_FakeBone_OneClick — native_skeleton EnumProperty
        ("*", "原生骨架"): "Native Skeleton",
        ("*", "选择对应角色的原生 fbxskel 文件"): "Select the native fbxskel file for the corresponding character",

        # RE4_OT_FakeBone_OneClick — draw prop text
        ("*", "角色原生骨架"): "Character Native Skeleton",

        # get_native_skeletons_callback — fallback enum item label
        ("*", "无可用骨架 (添加至 assets/native_skeletons/re4/)"): "No skeletons available (add files to assets/native_skeletons/re4/)",

        # RE4_OT_FakeBone_OneClick — self.report (static)
        ("*", "请先选中目标骨架"): "Please select the target armature first",
        ("*", "需要 RE Mesh Editor 插件"): "Requires RE Mesh Editor addon",
        ("*", "请选择原生骨架（添加文件到 assets/native_skeletons/re4/）"): "Please select a native skeleton (add files to assets/native_skeletons/re4/)",
        ("*", "假骨骼生成完成"): "Fake bone generation complete",

        # RE4_OT_FakeBone_OneClick — self.report (template)
        ("*", "找不到原生骨架: %s"): "Native skeleton not found: %s",
        ("*", "假骨骼生成失败: %s"): "Fake bone generation failed: %s",

        # games/re4/batch_export_ui.py — layout label strings
        ("*", "预设未配置 native_skeleton"): "Preset has no native_skeleton configured",

        # === core/mdf_tex_processor_ui_base.py ===

        # MdfTexDialogBase — _path_hint default (shown in layout.label when texture_base_path is empty)
        ("*", "例：Author/Character/"): "e.g. Author/Character/",

        # === games/*/mdf_tex_processor_ui.py ===
        # (all game-specific subclasses use English strings only; no additional entries needed)
    },
}
