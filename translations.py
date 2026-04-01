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
    },
}
