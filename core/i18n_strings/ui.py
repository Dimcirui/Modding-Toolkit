"""Strings for ui/main_panel.py and ui/editor_panel.py.
Filled in incrementally as each panel is migrated."""

STRINGS = {
    # ── MHW_PT_SuiteSettings collapsible section headers ───────────────────────
    "ui.main_panel.basic_tools_header":     {"EN": "Basic Tools",               "ZH": "基础工具"},
    "ui.main_panel.std_converter_header":   {"EN": "Universal Standard Conversion", "ZH": "通用标准转换"},
    "ui.main_panel.experimental_header":    {"EN": "Experimental Features",     "ZH": "实验性功能"},
    "ui.main_panel.pose_convert_header":    {"EN": "Pose Convert",              "ZH": "姿态转换 (Pose Convert)"},

    # ── MHW_PT_SuiteSettings property draw-site label overrides ────────────────
    # (property name= stays a short English fallback; these T() keys are the
    # bilingual label shown at the actual layout.prop() call site)
    "ui.main_panel.import_preset_label":       {"EN": "Source Preset (X)", "ZH": "来源预设 (X)"},
    "ui.main_panel.target_preset_label":       {"EN": "Target Game (Y)",   "ZH": "目标游戏 (Y)"},
    "ui.main_panel.show_mapping_details_label":{"EN": "Show Mapping Details", "ZH": "显示映射细节"},
    "ui.main_panel.pose_preset_field_label":   {"EN": "Skeleton Preset",   "ZH": "骨架预设"},

    # ── align_mode_override EnumProperty items (dynamic callback) ──────────────
    "ui.main_panel.align_mode_pos_only":      {"EN": "Position Only",   "ZH": "仅位置"},
    "ui.main_panel.align_mode_pos_only_desc": {"EN": "Align only the bone head position; keep the target skeleton's original direction and length",
                                                "ZH": "只对齐骨骼头部位置，保留目标骨架原有的方向和长度"},
    "ui.main_panel.align_mode_pos_roll":      {"EN": "Position + Roll", "ZH": "位置+扭转"},
    "ui.main_panel.align_mode_pos_roll_desc": {"EN": "Align head position and copy the source bone's roll; direction/length unchanged",
                                                "ZH": "对齐头部位置并复制来源骨骼的扭转(Roll)，长度方向不变"},
    "ui.main_panel.align_mode_full":          {"EN": "Full Align",      "ZH": "完全对齐"},
    "ui.main_panel.align_mode_full_desc":     {"EN": "Align head, tail, and roll fully to the source bone (bone length and direction follow the source too)",
                                                "ZH": "头部、尾部、扭转全部对齐到来源骨骼 (骨骼长度和方向都会跟随来源)"},

    # ── mhwi_export_mode / mhwi_rank_tab / mhwi_gender EnumProperty items ──────
    "ui.main_panel.mhwi_mode_armor":       {"EN": "Armor",  "ZH": "装备"},
    "ui.main_panel.mhwi_mode_armor_desc":  {"EN": "Export character armor (equipment/transmog)", "ZH": "导出人物装备（护甲/幻化）"},
    "ui.main_panel.mhwi_mode_weapon":      {"EN": "Weapon", "ZH": "武器"},
    "ui.main_panel.mhwi_mode_weapon_desc": {"EN": "Export weapon model (blank-model replacement not yet supported)", "ZH": "导出武器模型（暂不支持空模替换）"},
    "ui.main_panel.mhwi_rank_hr":          {"EN": "LR/HR",         "ZH": "上下位"},
    "ui.main_panel.mhwi_rank_hr_desc":     {"EN": "Low Rank / High Rank armor", "ZH": "低位/高位装备"},
    "ui.main_panel.mhwi_rank_mr":          {"EN": "Master Rank",   "ZH": "大师位"},
    "ui.main_panel.mhwi_rank_mr_desc":     {"EN": "Iceborne Master Rank armor", "ZH": "冰原大师位装备"},
    "ui.main_panel.mhwi_rank_sp":          {"EN": "Full Transmog", "ZH": "整套幻化"},
    "ui.main_panel.mhwi_rank_sp_desc":     {"EN": "Standalone transmog set (includes head/hair models)", "ZH": "独立幻化套装（含头部/头发模型）"},
    "ui.main_panel.mhwi_gender_f":         {"EN": "Female", "ZH": "女"},
    "ui.main_panel.mhwi_gender_f_desc":    {"EN": "Export female hunter equipment files only", "ZH": "仅导出女猎装备文件"},
    "ui.main_panel.mhwi_gender_m":         {"EN": "Male",   "ZH": "男"},
    "ui.main_panel.mhwi_gender_m_desc":    {"EN": "Export male hunter equipment files only", "ZH": "仅导出男猎装备文件"},
    "ui.main_panel.mhwi_gender_both":      {"EN": "Both",   "ZH": "双性"},
    "ui.main_panel.mhwi_gender_both_desc": {"EN": "Export both male and female hunter equipment files", "ZH": "同时导出男女猎装备文件"},

    # ── mhws_bs_bind_part EnumProperty items ────────────────────────────────────
    "ui.main_panel.mhws_bind_part_helmet": {"EN": "Helmet", "ZH": "头盔"},
    "ui.main_panel.mhws_bind_part_body":   {"EN": "Body",   "ZH": "身体"},

    # ── bone_view_mode custom toggle buttons (line ~669-674) ────────────────────
    "ui.main_panel.bone_view_all":      {"EN": "Show All",    "ZH": "全显"},
    "ui.main_panel.bone_view_base":     {"EN": "Base Only",   "ZH": "仅基础骨"},
    "ui.main_panel.bone_view_physics":  {"EN": "Physics Only","ZH": "仅物理骨"},

    # ── MHW_OT_GeneralTools: action EnumProperty items + per-action tooltips ───
    # (label keys feed the dynamic items= callback AND the matching toolbar
    # buttons in MHW_PT_MainPanel.draw() that invoke this operator; desc keys
    # feed both the enum item description and the operator's dynamic
    # classmethod description() hook)
    "ui.main_panel.gt_action_roll_zero":         {"EN": "Zero Roll",              "ZH": "扭转归零"},
    "ui.main_panel.gt_desc_roll_zero":           {"EN": "Recursively zero the Roll value of the selected bones and all their children",
                                                   "ZH": "递归将选中骨骼及其所有子骨的 Roll 值归零"},
    "ui.main_panel.gt_action_add_tail":          {"EN": "Add Tail Bone",          "ZH": "添加尾骨"},
    "ui.main_panel.gt_desc_add_tail":            {"EN": "Add a vertical tail bone to the end of each selected bone",
                                                   "ZH": "在每根选中骨骼的末端添加一根垂直向上的尾骨"},
    "ui.main_panel.gt_action_mirror_x":          {"EN": "Mirror Align X",         "ZH": "镜像对齐 X"},
    "ui.main_panel.gt_desc_mirror_x":            {"EN": "Select exactly two bones: mirror the X- side bone's position and roll onto the X+ side bone",
                                                   "ZH": "正好选中两根骨骼：以 X+ 侧那根为基准，镜像覆盖 X- 侧那根的位置与扭转"},
    "ui.main_panel.gt_action_simplify_chain":    {"EN": "Simplify Chain",         "ZH": "骨链简化"},
    "ui.main_panel.gt_desc_simplify_chain":      {"EN": "Pair up bones along each chain, merge their weights, and delete the redundant bones; unweighted tail bones are skipped automatically",
                                                   "ZH": "按链结构将骨骼两两配对合并权重并删除多余骨骼；链末无权重骨（尾骨）自动跳过不参与配对"},
    "ui.main_panel.gt_action_merge_to_active":   {"EN": "Merge into Active Bone", "ZH": "合并到激活骨"},
    "ui.main_panel.gt_desc_merge_to_active":     {"EN": "Merge the weights of the other selected bones into the active bone (last clicked), then delete the other bones",
                                                   "ZH": "将其余选中骨骼的权重全部并入激活骨（最后点击的那根），然后删除其余骨骼"},
    "ui.main_panel.gt_action_align_pos":         {"EN": "Align (Position)",       "ZH": "对齐 (位置)"},
    "ui.main_panel.gt_desc_align_pos":           {"EN": "Select two armatures: align the active armature's same-named bone head positions to the source armature, without changing bone length/direction",
                                                   "ZH": "选中两个骨架：将激活骨架中同名骨骼的 head 位置对齐到源骨架，不改变骨骼长度与方向"},
    "ui.main_panel.gt_action_align_pos_roll":    {"EN": "Align (Position + Roll)","ZH": "对齐 (位置+扭转)"},
    "ui.main_panel.gt_desc_align_pos_roll":      {"EN": "Select two armatures: align same-named bones' head position and roll, without changing bone length/direction",
                                                   "ZH": "选中两个骨架：对齐同名骨骼的 head 位置和 roll 扭转，不改变骨骼长度与方向"},
    "ui.main_panel.gt_action_align_full":        {"EN": "Align (Full)",           "ZH": "对齐 (完全)"},
    "ui.main_panel.gt_desc_align_full":          {"EN": "Fully align head, tail, and roll between two armatures by bone name (bone length follows the source too)",
                                                   "ZH": "选中两个骨架：按骨骼名完全对齐 head、tail 和 roll（骨骼长度也会跟随源骨架）"},
    "ui.main_panel.gt_action_merge_chains":      {"EN": "Merge Chains into Active Chain", "ZH": "合并链到激活链"},
    "ui.main_panel.gt_desc_merge_chains":        {"EN": "Select the heads of multiple chains: merge the other chains bone-by-bone by position into the active bone's chain; overflow is merged into the chain's last bone",
                                                   "ZH": "选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链；源链超出长度的部分并入链末骨"},

    # ── MHW_OT_GeneralTools toolbar-button-only short labels ───────────────────
    # (distinct wording from the action items above — shown in a context where
    # the section header already says "Armature Align")
    "ui.main_panel.gt_btn_align_pos":   {"EN": "Position", "ZH": "位置"},
    "ui.main_panel.gt_btn_align_full":  {"EN": "Full",     "ZH": "完全"},

    # ── MHW_OT_GeneralTools.execute() report messages ──────────────────────────
    "ui.main_panel.gt_err_select_armature":      {"EN": "Please select an armature first", "ZH": "请先选中一个骨架"},
    "ui.main_panel.gt_warn_select_bone_edit":    {"EN": "Please select at least one bone in Edit Mode", "ZH": "请在编辑模式下至少选中一根骨骼"},
    "ui.main_panel.gt_info_roll_reset":          {"EN": "Reset Roll on {n} bone(s)", "ZH": "已重置 {n} 根骨骼的 Roll"},
    "ui.main_panel.gt_warn_select_tail_bone":    {"EN": "Please select the bone(s) to add a tail to", "ZH": "请选中需要加尾巴的骨骼"},
    "ui.main_panel.gt_info_tail_added":          {"EN": "Added {n} tail bone(s)", "ZH": "添加了 {n} 根尾骨"},
    "ui.main_panel.gt_err_mirror_need_two":      {"EN": "Please select exactly two bones for mirror align", "ZH": "请正好选中两个骨骼进行镜像对齐"},
    "ui.main_panel.gt_err_need_two_bones":       {"EN": "Please select at least two bones", "ZH": "至少需要选中两个骨骼"},
    "ui.main_panel.gt_warn_no_pairs":            {"EN": "No pairs were generated (not enough bones, or all are tail bones)", "ZH": "未生成任何配对（骨骼数不足或全为尾骨）"},
    "ui.main_panel.gt_info_chain_simplified":    {"EN": "Chain simplification complete: processed {n} bone pair(s)", "ZH": "骨链简化完成: 处理 {n} 对骨骼"},
    "ui.main_panel.gt_err_need_active_bone":     {"EN": "Please make sure there is an active bone (the last one clicked is kept)", "ZH": "请确保有激活骨骼（最后点击的那根为保留目标）"},
    "ui.main_panel.gt_err_need_two_for_merge":   {"EN": "Please select at least two bones (the active bone is kept, the rest are merged in)", "ZH": "请至少选中两根骨骼（激活骨保留，其余骨并入）"},
    "ui.main_panel.gt_info_merged_into":         {"EN": "Merged {n} bone(s) into [{name}]", "ZH": "已将 {n} 根骨骼并入 [{name}]"},
    "ui.main_panel.gt_warn_no_valid_chain_heads":{"EN": "No valid chain head found to merge (select the head bone of another chain)", "ZH": "未找到有效的待合并链首（请选中其他链的链首骨骼）"},
    "ui.main_panel.gt_info_chains_merged":       {"EN": "Merged {chains} chain(s) into [{name}], processed {pairs} bone pair(s) in total", "ZH": "已将 {chains} 条链合并到 [{name}]，共处理 {pairs} 对骨骼"},
    "ui.main_panel.gt_err_need_two_armatures":   {"EN": "Please select two armatures (active one is the target, the other is the source)", "ZH": "请选中两个骨架（激活的为目标，另一个为源）"},
    "ui.main_panel.gt_label_align_pos":          {"EN": "Position Align", "ZH": "位置对齐"},
    "ui.main_panel.gt_info_align_result":        {"EN": "{label}: {n} bone(s)", "ZH": "{label}：{n} 根骨骼"},

    # ── bridge entries: bone_utils.mirror_bone_transform() returns fixed
    # Chinese message templates (that file is out of this migration's scope);
    # keyed by the literal template text itself so T() can translate them
    # without touching core/bone_utils.py ──────────────────────────────────────
    "请选中两个骨骼":        {"EN": "Please select two bones", "ZH": "请选中两个骨骼"},
    "骨骼未找到":            {"EN": "Bone not found",          "ZH": "骨骼未找到"},
    "已将 %s 对齐到 %s":     {"EN": "Aligned %s to %s",        "ZH": "已将 %s 对齐到 %s"},

    # ── MHW_PT_MainPanel.draw() section headers / static labels ────────────────
    "ui.main_panel.label_bone_merge":            {"EN": "Bone Merge",       "ZH": "骨骼合并"},
    "ui.main_panel.label_bone_processing":       {"EN": "Bone Processing",  "ZH": "骨骼处理"},
    "ui.main_panel.label_armature_align":        {"EN": "Armature Align",   "ZH": "骨架对齐"},
    "ui.main_panel.label_weight_processing":     {"EN": "Weight Processing","ZH": "权重处理"},
    "ui.main_panel.label_skeleton_cleanup":      {"EN": "Skeleton Cleanup:","ZH": "骨架清理:"},
    "ui.main_panel.label_physics_chain_tools":   {"EN": "Physics Chain Tools:", "ZH": "物理链工具:"},
    "ui.main_panel.label_bone_visibility":       {"EN": "Bone Visibility [X]:", "ZH": "骨骼显示 [X]:"},
    "ui.main_panel.label_mapping_preview_need_preset": {"EN": "Mapping detail preview requires a specific preset (not Auto-Detect)", "ZH": "映射详情预览需要选定具体预设（非自动识别）"},
    "ui.main_panel.label_missing":                {"EN": "Missing", "ZH": "缺失"},
    "ui.main_panel.label_select_armature_preview":{"EN": "Select an armature to preview", "ZH": "请选中骨架以预览"},
    "ui.main_panel.label_simple_tools":           {"EN": "Simple Tools:", "ZH": "简易工具:"},
    "ui.main_panel.label_pose_recorder":          {"EN": "Pose Transform Recorder:", "ZH": "姿态变换记录器:"},
    "ui.main_panel.label_fakebone_section":       {"EN": "Fake Head Method (FakeBone)", "ZH": "假头法 (FakeBone)"},
    "ui.main_panel.label_need_mhw_model_editor":  {"EN": "Requires MHW Model Editor!", "ZH": "需要 MHW Model Editor!"},
    "ui.main_panel.label_need_re_chain_editor":   {"EN": "Requires RE Chain Editor!",  "ZH": "需要 RE Chain Editor!"},
    "ui.main_panel.label_need_re_mesh_editor":    {"EN": "Requires RE Mesh Editor!",   "ZH": "需要 RE Mesh Editor!"},

    # ── MHW_PT_MainPanel.draw() operator button labels ──────────────────────────
    "ui.main_panel.btn_sk_to_weights":            {"EN": "Shape Key to Weights",  "ZH": "形态键转权重"},
    "ui.main_panel.btn_merge_renamed_vgroups":    {"EN": "Merge Renamed Vertex Groups", "ZH": "合并重名顶点组"},
    "ui.main_panel.btn_universal_snap":           {"EN": "Align Bones [X+Y, dual armature]", "ZH": "对齐骨骼 [X+Y, 双骨架]"},
    "ui.main_panel.btn_direct_convert":           {"EN": "Rename Vertex Groups [X+Y]", "ZH": "重命名顶点组 [X+Y]"},
    "ui.main_panel.btn_merge_physics_weights":    {"EN": "Downgrade Physics Weights [X]", "ZH": "物理权重降级 [X]"},
    "ui.main_panel.btn_remove_non_base_bones":    {"EN": "Remove Non-Base Bones [X]", "ZH": "剔除非基础骨骼 [X]"},
    "ui.main_panel.btn_rename_bones_to_target":   {"EN": "Rename Base Bones [X+Y]", "ZH": "基础骨骼改名 [X+Y]"},
    "ui.main_panel.btn_smart_graft":              {"EN": "Graft Physics Bones [X+Y, dual armature]", "ZH": "移植物理骨骼 [X+Y, 双骨架]"},
    "ui.main_panel.btn_merge_into_parent":        {"EN": "Merge into Parent Bone", "ZH": "合并到父骨"},
    "ui.main_panel.btn_mark_main_continue":       {"EN": "Mark as Main Chain Continuation", "ZH": "标记为主链延伸"},
    "ui.main_panel.btn_clear_chain_role":         {"EN": "Clear Mark", "ZH": "清除标记"},
    "ui.main_panel.btn_refresh_bone_colors":      {"EN": "Refresh Bone Colors", "ZH": "刷新骨骼颜色"},
    "ui.main_panel.btn_tpose_matrix_zero":        {"EN": "Zero RE Engine Matrix (excl. RE9)", "ZH": "RE Engine 矩阵归零 (生化9除外)"},
    "ui.main_panel.btn_record_transform":         {"EN": "Record Transform (select two armatures)", "ZH": "录制变换 (选两个骨架)"},
    "ui.main_panel.btn_apply_forward":            {"EN": "▶ Forward (A→B)", "ZH": "▶ 正向 (A→B)"},
    "ui.main_panel.btn_apply_inverse":            {"EN": "◀ Inverse (B→A)", "ZH": "◀ 逆向 (B→A)"},
    "ui.main_panel.btn_tex_process":              {"EN": "Texture Processing", "ZH": "贴图处理"},
    "ui.main_panel.btn_align_non_physics":        {"EN": "Align Non-Physics Bones", "ZH": "对齐非物理骨骼"},
    "ui.main_panel.btn_split_physics_bones":      {"EN": "Split Physics Bones", "ZH": "拆分物理骨"},
    "ui.main_panel.btn_batch_rename_physics":     {"EN": "One-Click Rename", "ZH": "一键重命名"},
    "ui.main_panel.btn_mrl3_tex_processor":       {"EN": "MRL3 Processor", "ZH": "MRL3 处理器"},
    "ui.main_panel.btn_mrl3_generator":           {"EN": "MRL3 Generator", "ZH": "MRL3 生成器"},
    # ── shared property labels drawn via prop(text=...) ────────────────────
    # Blender shows a property's static name= when prop() has no text=, which
    # bypasses T() entirely. These are the labels that needed routing through it.
    "ui.prop.export_mode": {"EN": "Export Mode", "ZH": "导出模式"},
    "ui.prop.gender": {"EN": "Gender", "ZH": "性别"},
    "ui.prop.rank": {"EN": "Rank", "ZH": "位阶"},
    "ui.prop.cleanup_before_export": {"EN": "Clean Mesh Before Export", "ZH": "导出前清理网格"},
    "ui.prop.anti_plagiarism": {"EN": "Anti-Plagiarism", "ZH": "防石化"},
    "ui.prop.use_blank_export": {"EN": "Use Blank Model for Unselected", "ZH": "未选部位使用空模"},
    "ui.prop.ao_image": {"EN": "AO Map", "ZH": "AO 贴图"},
    "ui.prop.use_ao": {"EN": "Add AO", "ZH": "添加 AO"},
    "ui.prop.use_fakebone": {"EN": "Use Fake Head Method", "ZH": "使用假头法"},
    "ui.prop.use_body_armature": {"EN": "Use Body Armature", "ZH": "使用身体骨架"},
    "ui.prop.filter_axis": {"EN": "Axis", "ZH": "轴向"},
    "ui.prop.filter_direction": {"EN": "Direction", "ZH": "方向"},
    "ui.prop.edit_mode": {"EN": "Edit Mode", "ZH": "编辑模式"},

    # ── ui/game_sections.py — per-game tool groups ─────────────────────────
    "ui.game_sections.group_io":       {"EN": "Import & Export",          "ZH": "导入 & 导出"},
    "ui.game_sections.group_rig":      {"EN": "Skeleton & Mesh",          "ZH": "骨架 & 网格处理"},
    "ui.game_sections.group_material": {"EN": "Material & Texture",       "ZH": "材质 & 贴图处理"},
    "ui.game_sections.group_physics":  {"EN": "Physics",                  "ZH": "物理处理"},
    "ui.game_sections.btn_batch_export_mhws": {"EN": "MHWs Batch Exporter", "ZH": "MHWs 批量导出"},
    "ui.game_sections.btn_batch_export_re4":  {"EN": "RE4 Batch Exporter",  "ZH": "RE4 批量导出"},
    "ui.game_sections.btn_batch_export_mhrs": {"EN": "MHRS Batch Exporter", "ZH": "MHRS 批量导出"},
    "ui.game_sections.btn_batch_export_re9":  {"EN": "RE9 Batch Exporter",  "ZH": "RE9 批量导出"},

    "ui.main_panel.btn_convert_packed_shader":    {"EN": "Convert Selected to Packed Shader",
                                                   "ZH": "选中物体转为打包着色器"},
    "ui.main_panel.btn_create_chain":             {"EN": "One-Click Create Chain", "ZH": "一键创建 Chain"},
    "ui.main_panel.btn_mmd_face_weights":         {"EN": "MMD Shape Key to Face Weights", "ZH": "MMD 形态键转表情权重"},
    "ui.main_panel.btn_batch_export":             {"EN": "Batch Export", "ZH": "批量导出"},
    "ui.main_panel.btn_batch_import":             {"EN": "Batch Import", "ZH": "批量导入"},
    "ui.main_panel.btn_mhws_preprocess":          {"EN": "One-Click Import & Align Wilds Model", "ZH": "一键导入并对齐荒野模型"},
    "ui.main_panel.btn_mhws_optimize_skeleton":   {"EN": "Optimize Wilds Skeleton", "ZH": "优化荒野骨架"},
    "ui.main_panel.btn_mhws_optimize_aux":        {"EN": "Optimize Auxiliary Bones & Weights", "ZH": "优化辅助骨骼及权重"},
    "ui.main_panel.btn_add_facial_bones":         {"EN": "One-Click Add Facial Bones", "ZH": "一键添加表情骨"},
    "ui.main_panel.btn_mdf_tex_processor":        {"EN": "MDF2 Processor", "ZH": "MDF2 处理器"},
    "ui.main_panel.btn_mdf_generator":            {"EN": "MDF2 Generator", "ZH": "MDF2 生成器"},
    "ui.main_panel.btn_create_re_chain":          {"EN": "One-Click Create RE Chain", "ZH": "一键创建 RE Chain"},
    "ui.main_panel.btn_gen_fakebone":             {"EN": "Generate Fake Bones", "ZH": "生成假骨骼"},
    "ui.main_panel.btn_sync_child_orientation":   {"EN": "Sync Child Orientation & Roll", "ZH": "同步子级朝向及扭转"},

    # ── MHW_OT_ShapeKeyToWeights ─────────────────────────────────────────────────
    "ui.main_panel.sk_sign_pos":                  {"EN": "+ (positive)", "ZH": "+（正向）"},
    "ui.main_panel.sk_sign_neg":                  {"EN": "- (negative)", "ZH": "-（负向）"},
    "ui.main_panel.sk_field_shape_key":           {"EN": "Shape Key",         "ZH": "形态键"},
    "ui.main_panel.sk_field_ignore_threshold":    {"EN": "Ignore Threshold",  "ZH": "忽略阈值"},
    "ui.main_panel.sk_field_weight_strength":     {"EN": "Weight Strength",   "ZH": "权重强度"},
    "ui.main_panel.sk_field_smooth_factor":       {"EN": "Smooth Factor",     "ZH": "平滑扩散率"},
    "ui.main_panel.sk_field_smooth_iters":        {"EN": "Smooth Iterations", "ZH": "平滑迭代次数"},
    "ui.main_panel.sk_field_sync_seams":          {"EN": "Sync Seam Vertices","ZH": "缝合重合顶点"},
    "ui.main_panel.sk_field_direction_filter":    {"EN": "Direction Filter",  "ZH": "方向过滤"},
    "ui.main_panel.sk_err_select_non_basis":      {"EN": "Please select a non-Basis shape key", "ZH": "请选择一个非 Basis 的形态键"},
    "ui.main_panel.sk_warn_no_deformation":       {"EN": "Shape key '{name}' has no detectable deformation; try lowering the ignore threshold",
                                                    "ZH": "形态键 '{name}' 未检测到有效形变，请调低忽略阈值"},
    "ui.main_panel.sk_info_generated":            {"EN": "Generated vertex group '{name}' ({n} valid vertex/vertices)",
                                                    "ZH": "已生成顶点组 '{name}'（{n} 个有效顶点）"},

    # ── MHW_OT_MMDFaceWeights ────────────────────────────────────────────────────
    "ui.main_panel.mmd_face_weights_tip":         {"EN": "Split MMD eyelid/mouth shape keys by direction into target-game facial vertex groups",
                                                    "ZH": "将 MMD 眼皮/嘴型形态键按方向拆分为目标游戏表情顶点组"},
    "ui.main_panel.mmd_target_game_label":        {"EN": "Target Game",        "ZH": "目标游戏"},
    "ui.main_panel.mmd_sync_seams_label":         {"EN": "Sync Seam Vertices", "ZH": "缝合重合顶点"},
    "ui.main_panel.mmd_part_l_upper_eyelid":      {"EN": "L Upper Eyelid",  "ZH": "左眼上眼皮"},
    "ui.main_panel.mmd_part_l_lower_eyelid":      {"EN": "L Lower Eyelid",  "ZH": "左眼下眼皮"},
    "ui.main_panel.mmd_part_r_upper_eyelid":      {"EN": "R Upper Eyelid",  "ZH": "右眼上眼皮"},
    "ui.main_panel.mmd_part_r_lower_eyelid":      {"EN": "R Lower Eyelid",  "ZH": "右眼下眼皮"},
    "ui.main_panel.mmd_part_upper_lip":           {"EN": "Upper Lip",       "ZH": "上嘴唇"},
    "ui.main_panel.mmd_part_lower_lip":           {"EN": "Lower Lip",       "ZH": "下嘴唇"},
    "ui.main_panel.mmd_part_l_mouth_corner":      {"EN": "L Mouth Corner",  "ZH": "左嘴角"},
    "ui.main_panel.mmd_part_r_mouth_corner":      {"EN": "R Mouth Corner",  "ZH": "右嘴角"},
    "ui.main_panel.mmd_warn_no_valid_shapekeys":  {"EN": "No valid shape keys found; check the MMD shape key names", "ZH": "未找到任何有效形态键，请检查 MMD 形态键名称"},
    "ui.main_panel.mmd_info_generated":           {"EN": "Generated {n} facial vertex group(s): {parts}", "ZH": "已生成 {n} 个表情顶点组：{parts}"},
    "ui.main_panel.mmd_info_skipped_suffix":      {"EN": "; skipped: {parts}", "ZH": "；跳过：{parts}"},

    # ── MHW_OT_MergeRenamedVGroups ───────────────────────────────────────────────
    "ui.main_panel.merge_vg_done": {"EN": "Merge complete: {merged} vertex group(s) merged, {skipped} skipped (matches a real bone)",
                                     "ZH": "合并完成: {merged} 个顶点组已合并，{skipped} 个已跳过（对应真实骨骼）"},

    # ── MODDER_OT_AutoDetectPreset ───────────────────────────────────────────────
    "ui.main_panel.auto_detect_preset_tip":   {"EN": "Detect the selected armature's bone coverage and auto-match the best-fitting preset",
                                                "ZH": "检测当前选中骨架的骨骼覆盖率，自动匹配最合适的预设"},
    "ui.main_panel.err_select_armature_first":{"EN": "Please select an armature first", "ZH": "请先选中骨架"},
    "ui.main_panel.info_detected":            {"EN": "Detected: {name}", "ZH": "已识别: {name}"},
    "ui.main_panel.warn_no_preset_found":     {"EN": "No preset with >= 95% coverage found; please select manually", "ZH": "未找到覆盖率 >= 95% 的预设，请手动选择"},

    # ── ui/editor_panel.py — MHW_PT_PresetEditor ────────────────────────────────
    "ui.editor_panel.panel_title":          {"EN": "Preset Editor", "ZH": "预设编辑器"},
    "ui.editor_panel.manage_header":        {"EN": "Manage Existing Presets:", "ZH": "管理现有预设 (Manage):"},
    "ui.editor_panel.load_edit":            {"EN": "Load/Edit", "ZH": "读取/编辑"},
    "ui.editor_panel.open_preset_folder":   {"EN": "Open Preset Folder", "ZH": "打开预设文件夹"},
    "ui.editor_panel.convert_to_y":         {"EN": "Copy as Y Preset (X Conversion)", "ZH": "复制为 Y 预设 (X转换)"},
    "ui.editor_panel.convert_to_x":         {"EN": "Copy as X Preset (Y Conversion)", "ZH": "复制为 X 预设 (Y转换)"},
    "ui.editor_panel.workspace_header":     {"EN": "Editor Workspace:", "ZH": "编辑器工作区:"},
    "ui.editor_panel.save_name_label":      {"EN": "Save Name", "ZH": "保存名"},
    "ui.editor_panel.save_btn":             {"EN": "Save", "ZH": "保存"},
    "ui.editor_panel.init_list_btn":        {"EN": "Clear & Initialize List", "ZH": "清空并初始化列表"},
    "ui.editor_panel.list_empty":           {"EN": "List is empty, click Initialize", "ZH": "列表为空，请点击初始化"},
    "ui.editor_panel.unset_label":          {"EN": "[Unset]", "ZH": "[未设置]"},
}
