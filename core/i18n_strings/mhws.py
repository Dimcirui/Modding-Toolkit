"""
core/i18n_strings/mhws.py — bilingual STRINGS table for games/mhws/*.py.

Covers: games/mhws/operators.py, games/mhws/batch_export.py,
games/mhws/batch_export_ui.py, games/mhws/mdf_generator.py,
games/mhws/mdf_generator_ui.py, games/mhws/mdf_tex_processor_ui.py.
(games/mhws/fbxskel.py, games/mhws/mdf_tex_processor.py and
games/mhws/data_maps.py have no UI-facing Chinese text.)

Key naming convention: "mhws.<module_without_.py>.<short_purpose>".
"""

STRINGS = {

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/operators.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHWS_OT_EndfieldFaceRename ──────────────────────────────────────────
    "mhws.operators.endfield_face_rename_desc": {
        "EN": "Batch-convert Endfield facial vertex group names to MHWilds format",
        "ZH": "将 Endfield 面部顶点组名称批量转换为 MHWilds 格式"},
    "mhws.operators.endfield_face_rename_label": {"EN": "Endfield Face Rename", "ZH": "Endfield 面部改名"},
    "mhws.operators.endfield_processed": {
        "EN": "Processed {n} facial vertex group(s)", "ZH": "已处理 {n} 个面部顶点组"},

    # ── MHWS_OT_FaceWeightSimplify ───────────────────────────────────────────
    "mhws.operators.face_weight_simplify_desc": {
        "EN": "Simplify face weights: merge MHWilds' fine facial bone weights onto the primary bones",
        "ZH": "简化面部权重: 将 MHWilds 格式的细分面部骨骼权重合并到主要骨骼上"},
    "mhws.operators.face_weight_simplify_label": {"EN": "Face Weight Simplify", "ZH": "面部权重简化"},
    "mhws.operators.face_weight_simplify_done": {
        "EN": "Face weight simplification complete", "ZH": "面部权重简化完成"},

    # ── MHWS_OT_AutoCreateChains ─────────────────────────────────────────────
    "mhws.operators.auto_create_chains_desc": {
        "EN": "One-click create RE Chain. Supports auto-creating the collection + MHWilds-tuned header.",
        "ZH": "一键创建 RE Chain。支持自动创建集合 + MHWilds 特调 Header。"},
    "mhws.operators.auto_create_chains_label": {"EN": "One-Click Create RE Chain", "ZH": "一键创建 RE Chain"},
    "mhws.operators.chain_collection_desc": {
        "EN": "Select the Chain Collection to write to", "ZH": "选择要写入的 Chain Collection"},
    "mhws.operators.settings_mode_name": {"EN": "Settings Mode", "ZH": "Settings 模式"},
    "mhws.operators.settings_mode_separate": {"EN": "Separate", "ZH": "各自独立"},
    "mhws.operators.settings_mode_separate_desc": {
        "EN": "Each chain has its own independent Chain Settings", "ZH": "每条链拥有独立的 Chain Settings"},
    "mhws.operators.settings_mode_shared": {"EN": "Shared", "ZH": "共享同一"},
    "mhws.operators.settings_mode_shared_desc": {
        "EN": "All chains share the same Chain Settings", "ZH": "所有链共用同一个 Chain Settings"},
    "mhws.operators.settings_mode_guess": {"EN": "Guess Grouping", "ZH": "猜测分组"},
    "mhws.operators.settings_mode_guess_desc": {
        "EN": "Auto-classify by bone name; chains of the same type share one Chain Settings group with inferred "
              "physics parameters written in; unrecognized bones fall into the first group",
        "ZH": "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组"},
    "mhws.operators.auto_create_collection_name": {"EN": "Auto-create Collection", "ZH": "自动创建集合"},
    "mhws.operators.auto_create_collection_desc": {
        "EN": "When checked, automatically create the Chain Collection and Header, no manual prep needed",
        "ZH": "勾选后自动创建 Chain Collection 及 Header，无需预先手动准备"},
    "mhws.operators.collection_name_name": {"EN": "Collection Name", "ZH": "集合名称"},
    "mhws.operators.collection_name_desc": {
        "EN": "Name of the newly created Chain Collection (without extension)",
        "ZH": "新创建的 Chain Collection 名称（不含扩展名）"},
    "mhws.operators.chain_format_name": {"EN": "Chain Format", "ZH": "Chain 格式"},
    "mhws.operators.chain_format_chain_desc": {
        "EN": "Old format, used by RE4 and other earlier games", "ZH": "旧格式，用于 RE4 等早期游戏"},
    "mhws.operators.chain_format_chain2_desc": {
        "EN": "New format, used by MHWilds / RE9", "ZH": "新格式，用于 MHWilds / RE9"},
    "mhws.operators.apply_mhwilds_tuning_name": {"EN": "Use Wilds-Tuned Header", "ZH": "使用荒野特调Header"},
    "mhws.operators.apply_mhwilds_tuning_desc": {
        "EN": "Override Header parameters with MHWilds calibration values (calculateMode=Quality, etc.)",
        "ZH": "将 Header 参数覆盖为 MHWilds 校准值（calculateMode=Quality 等）"},
    "mhws.operators.straighten_orientation_name": {"EN": "Bone Orientation Preprocessing", "ZH": "骨骼方向预处理"},
    "mhws.operators.straighten_orientation_desc": {
        "EN": "Before creation, reset all physics bones to point straight up with zero twist",
        "ZH": "创建前将所有物理骨骼调整为竖直向上、扭转归零"},
    "mhws.operators.auto_refresh_name": {
        "EN": "Create Directly (auto-refresh bone colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},
    "mhws.operators.auto_refresh_desc": {
        "EN": "Automatically run bone color refresh first, then attempt to create",
        "ZH": "先自动运行骨骼颜色刷新，再尝试创建"},
    "mhws.operators.apply_angle_ramp_name": {"EN": "Auto-apply Angle Ramp", "ZH": "自动应用角度坡度"},
    "mhws.operators.apply_angle_ramp_desc": {
        "EN": "After chain creation, automatically call apply_angle_limit_ramp (max 60°, 4-step ramp)",
        "ZH": "链创建完成后自动调用 apply_angle_limit_ramp（最大60°，4级梯度）"},
    "mhws.operators.no_markers_warning1": {
        "EN": "The current armature has no markers!", "ZH": "当前骨架没有任何标记！"},
    "mhws.operators.no_markers_warning2": {
        "EN": "It's recommended to manually mark it with the Physics Chain tool first before using this feature.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "mhws.operators.chain_create_failed": {"EN": "Failed to create RE Chain", "ZH": "创建 RE Chain 失败"},
    "mhws.operators.chain_create_done": {"EN": "RE Chain created successfully", "ZH": "RE Chain 创建完成"},

    # ── MHWS_OT_PreprocessModel ──────────────────────────────────────────────
    "mhws.operators.preprocess_model_desc": {
        "EN": "Auto-detect MMD/VRChat -> pose correction -> import reference skeleton -> "
              "scale/Y-offset calibration -> skeleton alignment",
        "ZH": "自动识别 MMD/VRChat → 姿态校正 → 导入参考骨架 → 缩放/Y轴偏移校准 → 骨架对齐"},
    "mhws.operators.preprocess_model_label": {
        "EN": "One-Click Import & Align Wilds Model", "ZH": "一键导入并对齐荒野模型"},
    "mhws.operators.select_armature_first": {"EN": "Please select an armature first", "ZH": "请先选中一个骨架"},
    "mhws.operators.mmd_vrchat_only": {
        "EN": "This feature currently only supports MMD and VRChat models!",
        "ZH": "目前该功能只适用于MMD和VRChat模型！"},
    "mhws.operators.ref_skeleton_import_failed": {
        "EN": "Reference skeleton import failed (please make sure assets/reference_skeletons/mhws/{name} exists)",
        "ZH": "参考骨架导入失败（请确认 assets/reference_skeletons/mhws/{name} 存在）"},
    "mhws.operators.no_wilds_preset_detected": {
        "EN": "Could not auto-detect a Wilds bone preset; please manually select the target preset in the panel "
              "and retry",
        "ZH": "未能自动检测到荒野骨骼预设，请在面板中手动选择目标预设后重试"},
    "mhws.operators.preprocess_done": {"EN": "Model preprocessing complete", "ZH": "模型预处理完成"},

    # ── MHWS_OT_AddFacialBones ───────────────────────────────────────────────
    "mhws.operators.add_facial_bones_desc": {
        "EN": "Graft facial bones from the original Wilds armature onto the current armature; optionally use the "
              "fake-head method to adjust blink amplitude",
        "ZH": "将原版荒野骨架的表情骨骼移植到当前骨架，可选择使用假头法调整眨眼幅度"},
    "mhws.operators.add_facial_bones_label": {"EN": "One-Click Add Facial Bones", "ZH": "一键添加表情骨"},
    "mhws.operators.target_armature_name": {"EN": "Armature", "ZH": "骨架"},
    "mhws.operators.target_armature_desc": {
        "EN": "Select the armature to add facial bones to", "ZH": "选择要添加表情骨的骨架"},
    "mhws.operators.increase_blink_amplitude_name": {
        "EN": "Increase Blink Amplitude (for anime-style models)", "ZH": "增加眨眼幅度（二次元模型用）"},
    "mhws.operators.increase_blink_amplitude_desc": {
        "EN": "Apply the fake-head method to the upper eyelid bones, increasing the deformation amplitude of the "
              "eye-closing motion",
        "ZH": "对上眼皮骨骼使用假头法，增大闭眼动作的形变幅度"},
    "mhws.operators.facial_bones_note": {
        "EN": "Using this feature will clear any existing facial bones!", "ZH": "使用该功能将清除原本存在的表情骨！"},
    "mhws.operators.select_valid_armature": {"EN": "Please select a valid armature", "ZH": "请选择一个有效的骨架"},
    "mhws.operators.no_facial_root_bone": {
        "EN": "Facial bone root bone not found in the reference skeleton ({name})",
        "ZH": "参考骨架中未找到表情骨根骨骼 ({name})"},
    "mhws.operators.facial_bones_added": {"EN": "Added {n} facial bone(s)", "ZH": "已添加 {n} 根表情骨"},
    "mhws.operators.blink_amplitude_added": {
        "EN": "; blink amplitude increased on {n} side(s)", "ZH": "，{n} 侧已增加眨眼幅度"},

    # ── MHWS_OT_OptimizeSkeleton ─────────────────────────────────────────────
    "mhws.operators.optimize_skeleton_desc": {
        "EN": "Adjust certain bone positions to alleviate bent-leg issues, etc. Not recommended for non-anime-style "
              "models",
        "ZH": "调整部分骨骼的位置，以缓解曲腿等问题，非二次元模型不建议使用"},
    "mhws.operators.optimize_skeleton_label": {"EN": "Optimize Wilds Skeleton", "ZH": "优化荒野骨架"},
    "mhws.operators.optimize_skeleton_done": {
        "EN": "Wilds skeleton optimization complete", "ZH": "荒野骨架优化完成"},

    # ── MHWS_OT_OptimizeAuxBones ─────────────────────────────────────────────
    "mhws.operators.optimize_aux_bones_desc": {
        "EN": "Snap all HJ auxiliary bones to their corresponding base bone positions (twist-type bones use "
              "limb-segment midpoints), and transfer body weights to the primary auxiliary bones. This usually "
              "makes motion in these areas more natural",
        "ZH": "将全部 HJ 辅助骨吸附到对应基础骨位置（扭转类取肢段中点），并把身体权重转移至主要辅助骨。通常能让这些部位的运动更自然"},
    "mhws.operators.optimize_aux_bones_label": {
        "EN": "Optimize Auxiliary Bones & Weights", "ZH": "优化辅助骨骼及权重"},
    "mhws.operators.optimize_aux_bones_done": {
        "EN": "Done: {moved} auxiliary bone(s) snapped, {renamed} vertex group(s) had weights transferred",
        "ZH": "完成：{moved} 根辅助骨已吸附，{renamed} 个顶点组已转移权重"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHWS_PARTS labels (draw-site lookup, keyed by part id) ─────────────
    "mhws.batch_export.part_arm":    {"EN": "Arm",    "ZH": "手臂"},
    "mhws.batch_export.part_body":   {"EN": "Body",   "ZH": "身体"},
    "mhws.batch_export.part_helmet": {"EN": "Helmet", "ZH": "头盔"},

    "mhws.batch_export.variant_ff": {"EN": "Female Hunter (Female Set)", "ZH": "女猎 (女套)"},
    "mhws.batch_export.variant_fm": {"EN": "Female Hunter (Male Set)",   "ZH": "女猎 (男套)"},
    "mhws.batch_export.variant_mf": {"EN": "Male Hunter (Female Set)",   "ZH": "男猎 (女套)"},
    "mhws.batch_export.variant_mm": {"EN": "Male Hunter (Male Set)",    "ZH": "男猎 (男套)"},
    "mhws.batch_export.part_leg":    {"EN": "Leg",    "ZH": "腿"},
    "mhws.batch_export.part_waist":  {"EN": "Waist",  "ZH": "腰"},

    # ── Dynamic EnumProperty item fallbacks (get_mhws_schemes_callback /
    #    get_mhws_armor_callback; already callbacks, just wrap literals) ────
    "mhws.batch_export.no_armor_pack": {"EN": "No armor pack", "ZH": "无装备包"},
    "mhws.batch_export.no_armor":      {"EN": "No armor", "ZH": "无装备"},

    # ── Bonesystem export ────────────────────────────────────────────────────
    "mhws.batch_export.bonesystem_fill_name": {
        "EN": "Bonesystem: please fill in the FBXSkel definition name", "ZH": "Bonesystem: 请填写 FBXSkel 定义名"},
    "mhws.batch_export.bonesystem_select_armature": {
        "EN": "Bonesystem: please select an armature object", "ZH": "Bonesystem: 请选择一个骨架对象"},
    "mhws.batch_export.bonesystem_ref_not_found": {
        "EN": "Bonesystem: reference skeleton file not found: {path}", "ZH": "Bonesystem: 找不到参考骨架文件: {path}"},
    "mhws.batch_export.bonesystem_done": {
        "EN": "Bonesystem complete: {fbxskel}.fbxskel.7 / {json}.json",
        "ZH": "Bonesystem 完成: {fbxskel}.fbxskel.7 / {json}.json"},
    "mhws.batch_export.bonesystem_failed": {"EN": "Bonesystem failed: {err}", "ZH": "Bonesystem 失败: {err}"},

    # ── MHWS_OT_BatchExport ──────────────────────────────────────────────────
    "mhws.batch_export.batch_export_desc": {"EN": "MHWs armor batch export", "ZH": "MHWs 装备批量导出"},
    "mhws.batch_export.re_mesh_not_installed_cleanup_skip": {
        "EN": "RE Mesh Editor not installed, skipping pre-export cleanup", "ZH": "RE Mesh Editor 未安装，跳过导出前清理"},
    "mhws.batch_export.set_mod_root_first": {
        "EN": "Please set the Mod Root directory first (the parent folder of natives)",
        "ZH": "请先设置 Mod Root 目录（natives 的上级文件夹）"},
    "mhws.batch_export.cannot_load_armor_pack": {"EN": "Could not load the armor pack", "ZH": "无法加载装备包"},
    "mhws.batch_export.select_armor_set_first": {"EN": "Please select an armor set first", "ZH": "请先选择一套装备"},
    "mhws.batch_export.armor_not_found_in_pack": {
        "EN": "Not found in armor pack: {id}", "ZH": "在装备包中未找到: {id}"},
    "mhws.batch_export.armor_no_variant": {
        "EN": "Armor {id} has no variant: {variant}", "ZH": "装备 {id} 没有变体: {variant}"},
    "mhws.batch_export.done_with_fail": {
        "EN": "Done: exported {export}, failed {fail}, skipped {skip}",
        "ZH": "完成: 导出 {export}, 失败 {fail}, 跳过 {skip}"},
    "mhws.batch_export.done": {
        "EN": "Done: exported {export}, skipped {skip}", "ZH": "完成: 导出 {export}, 跳过 {skip}"},

    # ── MHWS_OT_SetNativesRoot ───────────────────────────────────────────────
    "mhws.batch_export.set_natives_root_desc": {
        "EN": "Select the MHWs Mod root directory (parent of natives). If the selected folder is itself named "
              "natives, its parent is used automatically",
        "ZH": "选择 MHWs Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"},

    # ── MHWS_OT_BonesystemSettings ───────────────────────────────────────────
    "mhws.batch_export.bonesystem_settings_desc": {
        "EN": "Adjust Bonesystem JSON export parameters", "ZH": "调整 Bonesystem JSON 导出参数"},
    "mhws.batch_export.bonesystem_settings_label": {
        "EN": "Bonesystem Export Settings", "ZH": "Bonesystem 导出设置"},
    "mhws.batch_export.hide_options": {"EN": "Hide Options:", "ZH": "隐藏选项:"},
    "mhws.batch_export.bind_options": {"EN": "Bind Options:", "ZH": "绑定选项:"},
    "mhws.batch_export.bind_part":    {"EN": "Bind Part:", "ZH": "绑定部位:"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhws.batch_export_ui.pick_armor_desc": {
        "EN": "Search and select armor (avoids the dropdown overflowing the screen when there are too many armors)",
        "ZH": "搜索并选择装备（避免装备过多时下拉表溢出屏幕）"},
    "mhws.batch_export_ui.batch_export_dialog_desc": {
        "EN": "MHWs armor batch export dialog", "ZH": "MHWs 装备批量导出对话框"},
    "mhws.batch_export_ui.armor_pack_label": {"EN": "Armor Pack", "ZH": "装备包"},
    "mhws.batch_export_ui.pick_armor_placeholder": {"EN": "Select armor...", "ZH": "选择装备..."},
    "mhws.batch_export_ui.not_set": {"EN": "Not set", "ZH": "未设置"},
    "mhws.batch_export_ui.select_armor_to_configure": {
        "EN": "Select an armor to configure bindings", "ZH": "请选择装备以配置绑定"},
    "mhws.batch_export_ui.use_bonesystem_label": {"EN": "Use Bonesystem", "ZH": "使用 Bonesystem"},
    "mhws.batch_export_ui.armature_label": {"EN": "Armature", "ZH": "骨架"},
    "mhws.batch_export_ui.fbxskel_name_label": {"EN": "FBXSkel Name", "ZH": "FBXSkel 名"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/mdf_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "mhws.mdf_generator.use_toon_name": {"EN": "Use Toon Shading", "ZH": "使用三渲二"},
    "mhws.mdf_generator.use_toon_desc": {
        "EN": "Skip emissive texture processing; set the emissive slot path the same as the base color slot",
        "ZH": "跳过自发光贴图处理，将自发光槽位路径设为与基础色槽位相同"},
    "mhws.mdf_generator.generate_mipmaps_name": {"EN": "Generate MipMaps", "ZH": "生成 MipMaps"},
    "mhws.mdf_generator.skip_textures_name": {"EN": "Material Only", "ZH": "仅生成材质"},
    "mhws.mdf_generator.skip_textures_desc": {
        "EN": "Skip texture composition/conversion; only create the material definition and fill in texture paths",
        "ZH": "跳过贴图合成与转换，仅创建材质定义并填入贴图路径"},
    "mhws.mdf_generator.use_ao_name": {"EN": "Add AO", "ZH": "添加 AO"},
    "mhws.mdf_generator.use_ao_desc": {
        "EN": "Manually specify an AO texture (Blender has no built-in AO node)",
        "ZH": "手动指定 AO 贴图 (Blender 无内置 AO 节点)"},
    "mhws.mdf_generator.ao_image_desc": {"EN": "AO texture path", "ZH": "AO 贴图路径"},
    "mhws.mdf_generator.flip_normal_g_name": {"EN": "Normal OpenGL -> DirectX", "ZH": "法线 OpenGL → DirectX"},
    "mhws.mdf_generator.flip_normal_g_desc": {
        "EN": "When enabled, connected OpenGL normal maps are converted directly to DX format, without needing to "
              "manually flip the G channel in the shader",
        "ZH": "启用后，将连接的 OpenGL 法线贴图直接转为 DX 格式，不再需要在着色器内手动进行 G 通道反相"},
    "mhws.mdf_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the Mesh Collection using the current material (stage 2: smart filter)",
        "ZH": "选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "mhws.mdf_generator.select_mesh_collection_first": {
        "EN": "Please select a Mesh Collection first", "ZH": "请先选择 Mesh Collection"},
    "mhws.mdf_generator.active_obj_no_material": {
        "EN": "The active object has no material", "ZH": "激活物体没有材质"},
    "mhws.mdf_generator.selected_meshes_report": {
        "EN": "{count} mesh(es) using '{mat}' selected (including itself, {total} total)",
        "ZH": "已选中 {count} 个使用 '{mat}' 的网格（含自身共 {total} 个）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/mdf_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhws.mdf_generator_ui.strat_color":     {"EN": "Base Color", "ZH": "基础色"},
    "mhws.mdf_generator_ui.strat_normal":    {"EN": "Normal",     "ZH": "法线"},
    "mhws.mdf_generator_ui.strat_roughness": {"EN": "Roughness",  "ZH": "粗糙度"},
    "mhws.mdf_generator_ui.strat_metallic":  {"EN": "Metallic",   "ZH": "金属度"},
    "mhws.mdf_generator_ui.strat_alpha":     {"EN": "Alpha",      "ZH": "Alpha"},
    "mhws.mdf_generator_ui.strat_emissive":  {"EN": "Emissive",   "ZH": "自发光"},
    "mhws.mdf_generator_ui.dialog_desc": {
        "EN": "MDF2 Generator — creates MDF2 + textures from Blender mesh materials. Requires an existing mesh "
              "collection with a Principled BSDF wired up in the material",
        "ZH": "MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，并在材质里连好 Principled BSDF"},
    "mhws.mdf_generator_ui.auto_name": {"EN": "Auto: {name}", "ZH": "自动: {name}"},
    "mhws.mdf_generator_ui.preset_dir_not_found": {
        "EN": "RE Mesh Editor MHWILDS preset directory not found", "ZH": "未找到 RE Mesh Editor MHWILDS 预设目录"},
    "mhws.mdf_generator_ui.select_mesh_collection_hint": {
        "EN": "Select a mesh collection, then click Refresh", "ZH": "选择网格集合后点击刷新"},
    "mhws.mdf_generator_ui.node_tree_analysis": {
        "EN": "Node Tree Analysis (texture source strategy)", "ZH": "节点树分析 (贴图来源策略)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/mdf_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhws.mdf_tex_processor_ui.dialog_desc": {
        "EN": "MDF2 Processor — process textures on top of existing MDF2 materials. Requires an existing, "
              "properly named MDF2 collection",
        "ZH": "MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhws/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), which are baked
    # into the datablock when the group is first built. Switching language
    # therefore does not retranslate an already-built group; it only affects
    # groups created afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "mhws.shader_defs.panel_pbr": {"EN": "PBR Inputs", "ZH": "PBR 输入"},
    "mhws.shader_defs.panel_slots_standard": {
        "EN": "Game Slots (packed) — Standard", "ZH": "游戏槽位 (打包) — 标准"},
    "mhws.shader_defs.panel_slots_weapon": {
        "EN": "Game Slots (packed) — Weapon", "ZH": "游戏槽位 (打包) — 武器"},
    "mhws.shader_defs.panel_slots_skin": {
        "EN": "Game Slots (packed) — Skin", "ZH": "游戏槽位 (打包) — 皮肤"},
    "mhws.shader_defs.panel_slots_hair": {
        "EN": "Game Slots (packed) — Hair", "ZH": "游戏槽位 (打包) — 毛发"},

    "mhws.shader_defs.albd": {
        "EN": "BaseDielectricMap — RGB base colour, A inverted metallic (not opacity)",
        "ZH": "BaseDielectricMap — RGB 基础色, A 反转金属度 (不是透明度)"},
    "mhws.shader_defs.nrro": {
        "EN": "NormalRoughnessOcclusionMap — R roughness, G/A hemi-octahedral normal, B AO",
        "ZH": "NormalRoughnessOcclusionMap — R 粗糙度, G/A 半八面体编码法线, B 环境光遮蔽"},
    "mhws.shader_defs.emissive": {
        "EN": "EmissiveMap — emissive colour",
        "ZH": "EmissiveMap — 自发光颜色"},
    "mhws.shader_defs.atos": {
        "EN": "AlphaTranslucentOcclusionSSSMap — R alpha (real opacity), B AO",
        "ZH": "AlphaTranslucentOcclusionSSSMap — R 透明度 (真正的不透明度), B 环境光遮蔽"},
    "mhws.shader_defs.basealpha": {
        "EN": "BaseAlphaMap — RGB base colour, A real opacity. Hair's equivalent of "
              "BaseDielectricMap (hair is not metallic, so no inverted-alpha slot is needed)",
        "ZH": "BaseAlphaMap — RGB 基础色, A 为真实透明度。是毛发用来代替 BaseDielectricMap 的槽位"
              "（毛发不是金属，不需要反转 Alpha 表示金属度）"},

    # ── Secondary slots: no composition recipe, carried through untouched so
    # an existing image on the slot survives the round trip to the exporter.
    "mhws.shader_defs.mp_noise": {
        "EN": "MP_noise — a shared noise mask used by several VFX blends; carried for "
              "export, not used by the preview",
        "ZH": "MP_noise — 多个 VFX 混合共用的噪声遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.wind_effect_volumemap": {
        "EN": "Wind_Effect_VolumeMap — wind/cloth simulation volume texture; carried for "
              "export, not used by the preview",
        "ZH": "Wind_Effect_VolumeMap — 风力/布料模拟体积贴图；仅为导出保留，预览不使用"},
    "mhws.shader_defs.fxmap": {
        "EN": "FxMap — secondary effect mask; carried for export, not used by the preview",
        "ZH": "FxMap — 附加特效遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.noisemap": {
        "EN": "noisemap — generic noise texture used by several effects; carried for "
              "export, not used by the preview",
        "ZH": "noisemap — 多个效果共用的通用噪声贴图；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detailmaskmap": {
        "EN": "DetailMaskMap — masks in the four Detail_ALBD/NRRH layers; carried for "
              "export, not used by the preview",
        "ZH": "DetailMaskMap — 用来遮罩混合四组 Detail_ALBD/NRRH 细节层；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_albd_r": {
        "EN": "Detail_ALBD_R — a detail-layer colour texture, masked in by "
              "DetailMaskMap.R; carried for export, not used by the preview",
        "ZH": "Detail_ALBD_R — 细节层颜色贴图，由 DetailMaskMap.R 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_albd_g": {
        "EN": "Detail_ALBD_G — a detail-layer colour texture, masked in by "
              "DetailMaskMap.G; carried for export, not used by the preview",
        "ZH": "Detail_ALBD_G — 细节层颜色贴图，由 DetailMaskMap.G 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_albd_b": {
        "EN": "Detail_ALBD_B — a detail-layer colour texture, masked in by "
              "DetailMaskMap.B; carried for export, not used by the preview",
        "ZH": "Detail_ALBD_B — 细节层颜色贴图，由 DetailMaskMap.B 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_albd_a": {
        "EN": "Detail_ALBD_A — a detail-layer colour texture, masked in by "
              "DetailMaskMap.A; carried for export, not used by the preview",
        "ZH": "Detail_ALBD_A — 细节层颜色贴图，由 DetailMaskMap.A 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_nrrh_r": {
        "EN": "Detail_NRRH_R — a detail-layer normal/roughness texture, masked in by "
              "DetailMaskMap.R; carried for export, not used by the preview",
        "ZH": "Detail_NRRH_R — 细节层法线/粗糙度贴图，由 DetailMaskMap.R 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_nrrh_g": {
        "EN": "Detail_NRRH_G — a detail-layer normal/roughness texture, masked in by "
              "DetailMaskMap.G; carried for export, not used by the preview",
        "ZH": "Detail_NRRH_G — 细节层法线/粗糙度贴图，由 DetailMaskMap.G 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_nrrh_b": {
        "EN": "Detail_NRRH_B — a detail-layer normal/roughness texture, masked in by "
              "DetailMaskMap.B; carried for export, not used by the preview",
        "ZH": "Detail_NRRH_B — 细节层法线/粗糙度贴图，由 DetailMaskMap.B 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.detail_nrrh_a": {
        "EN": "Detail_NRRH_A — a detail-layer normal/roughness texture, masked in by "
              "DetailMaskMap.A; carried for export, not used by the preview",
        "ZH": "Detail_NRRH_A — 细节层法线/粗糙度贴图，由 DetailMaskMap.A 控制遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.panoramamap": {
        "EN": "PanoramaMap — reflection/environment panorama texture; carried for "
              "export, not used by the preview",
        "ZH": "PanoramaMap — 反射/环境全景贴图；仅为导出保留，预览不使用"},
    "mhws.shader_defs.vectoremitmap": {
        "EN": "VectorEmitMap — particle emission vector field; carried for export, not "
              "used by the preview",
        "ZH": "VectorEmitMap — 粒子发射矢量场贴图；仅为导出保留，预览不使用"},
    "mhws.shader_defs.colorlayer_maskmap": {
        "EN": "ColorLayer_MaskMap — colour-layer blend mask; carried for export, not "
              "used by the preview",
        "ZH": "ColorLayer_MaskMap — 颜色层混合遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.vfx_texture2d": {
        "EN": "VFX_Texture2D — a VFX shader's 2D texture input; carried for export, "
              "not used by the preview",
        "ZH": "VFX_Texture2D — VFX 着色器的 2D 贴图输入；仅为导出保留，预览不使用"},
    "mhws.shader_defs.vfx_texture3d": {
        "EN": "VFX_Texture3D — a VFX shader's 3D texture input; carried for export, "
              "not used by the preview",
        "ZH": "VFX_Texture3D — VFX 着色器的 3D 贴图输入；仅为导出保留，预览不使用"},
    "mhws.shader_defs.gpuwind_maskmap": {
        "EN": "GpuWind_MaskMap — GPU wind simulation mask; carried for export, not "
              "used by the preview",
        "ZH": "GpuWind_MaskMap — GPU 风力模拟遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.skinmap": {
        "EN": "SkinMap — a subsurface/skin-shading lookup texture. No PBR recipe and no "
              "vanilla default exists for this slot, so it is left at the plugin's own "
              "bundled placeholder unless overridden",
        "ZH": "SkinMap — 次表面/皮肤着色查找贴图。这个槽位没有 PBR 合成方案，也没有官方默认贴图，"
              "除非手动覆盖，否则使用插件内置的占位贴图"},
    "mhws.shader_defs.blendnormalmap": {
        "EN": "BlendNormalMap — a secondary blend normal map. No PBR recipe and no "
              "vanilla default exists for this slot, so it is left at the plugin's own "
              "bundled placeholder unless overridden",
        "ZH": "BlendNormalMap — 附加混合法线贴图。这个槽位没有 PBR 合成方案，也没有官方默认贴图，"
              "除非手动覆盖，否则使用插件内置的占位贴图"},
    "mhws.shader_defs.hairflowmap": {
        "EN": "HairFlowMap — hair strand flow-direction map; carried for export, not "
              "used by the preview",
        "ZH": "HairFlowMap — 毛发流向贴图；仅为导出保留，预览不使用"},
    "mhws.shader_defs.hair_height_specmask_shift_map": {
        "EN": "Hair_Height_SpecMask_Shift_Map — hair height/specular-shift mask; "
              "carried for export, not used by the preview",
        "ZH": "Hair_Height_SpecMask_Shift_Map — 毛发高度/高光偏移遮罩；仅为导出保留，预览不使用"},
    "mhws.shader_defs.hairovermap": {
        "EN": "HairOverMap — hair overlay/highlight map; carried for export, not used "
              "by the preview",
        "ZH": "HairOverMap — 毛发叠加/高光贴图；仅为导出保留，预览不使用"},

    "mhws.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with BaseDielectricMap",
        "ZH": "基础色。与 BaseDielectricMap 相乘"},
    "mhws.shader_defs.pbr_alpha": {
        "EN": "Alpha. Multiplied with AlphaTranslucentOcclusionSSSMap.R, the slot that "
              "actually carries opacity (BaseDielectricMap's alpha is metallic, not opacity)",
        "ZH": "透明度。与 AlphaTranslucentOcclusionSSSMap.R 相乘——真正带不透明度的是这个槽位，"
              "不是 BaseDielectricMap 的 Alpha (那个是金属度)"},
    "mhws.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with NormalRoughnessOcclusionMap.R",
        "ZH": "粗糙度。与 NormalRoughnessOcclusionMap.R 相乘"},
    "mhws.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to BaseDielectricMap's inverted alpha (1 - alpha)",
        "ZH": "金属度。与 BaseDielectricMap 反转后的 Alpha (1 - alpha) 相加"},
    "mhws.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour for preview. Unlike MHWI this "
              "genuinely exports: both NormalRoughnessOcclusionMap.B and "
              "AlphaTranslucentOcclusionSSSMap.B carry it",
        "ZH": "环境光遮蔽，预览时正片叠底到基础色上。和 MHWI 不同，这个是真的能导出的——"
              "NormalRoughnessOcclusionMap.B 和 AlphaTranslucentOcclusionSSSMap.B 都会带上它"},
    "mhws.shader_defs.pbr_ao_strength": {
        "EN": "AO strength: 0 = off, 1 = the full map",
        "ZH": "AO 强度：0 为关闭，1 为完整应用"},
    "mhws.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap",
        "ZH": "自发光颜色。与 EmissiveMap 相加"},
    "mhws.shader_defs.pbr_emission_strength": {
        "EN": "Emission strength",
        "ZH": "自发光强度"},
    "mhws.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to "
              "NormalRoughnessOcclusionMap's decoded normal",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量会和 NormalRoughnessOcclusionMap 解码出的法线相加"},
}
