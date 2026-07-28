"""Strings for games/mhrs/. Filled in incrementally as the module is migrated.

Key naming convention: "mhrs.<file_without_.py>.<short_purpose>".
"""

STRINGS = {

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/operators.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.operators.auto_create_chains_desc": {
        "EN": "Create RE Chain in one click (MHRS uses the .chain format)",
        "ZH": "一键创建 RE Chain（MHRS 使用 .chain 格式）"},
    # NOTE: chain_collection's description= is a per-property tooltip (operator property, same
    # gap as pattern 6 — no per-draw dynamic-tooltip hook), left as a plain English literal in
    # operators.py rather than routed through T().

    "mhrs.operators.settings_mode_label": {"EN": "Settings Mode", "ZH": "Settings 模式"},
    "mhrs.operators.settings_mode_separate": {"EN": "Separate", "ZH": "各自独立"},
    "mhrs.operators.settings_mode_separate_desc": {
        "EN": "Each chain gets its own independent Chain Settings", "ZH": "每条链拥有独立的 Chain Settings"},
    "mhrs.operators.settings_mode_shared": {"EN": "Shared", "ZH": "共享同一"},
    "mhrs.operators.settings_mode_shared_desc": {
        "EN": "All chains share the same Chain Settings", "ZH": "所有链共用同一个 Chain Settings"},
    "mhrs.operators.settings_mode_guess": {"EN": "Guess Groups", "ZH": "猜测分组"},
    "mhrs.operators.settings_mode_guess_desc": {
        "EN": "Auto-classify by bone name; same-type bones share one Chain Settings with guessed physics "
              "parameters written in, unrecognized bones fall into the first group",
        "ZH": "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组"},

    "mhrs.operators.auto_create_collection_label": {"EN": "Auto-create Collection", "ZH": "自动创建集合"},
    "mhrs.operators.collection_name_label": {"EN": "Collection Name", "ZH": "集合名称"},

    "mhrs.operators.chain_format_label": {"EN": "Chain Format", "ZH": "Chain 格式"},
    "mhrs.operators.chain_format_chain_desc": {
        "EN": "Legacy format, used by MHRS / RE4 etc.", "ZH": "旧格式，用于 MHRS / RE4 等游戏"},
    "mhrs.operators.chain_format_chain2_desc": {
        "EN": "New format, used by MHWilds / RE9", "ZH": "新格式，用于 MHWilds / RE9"},

    "mhrs.operators.straighten_orientation_label": {"EN": "Bone Direction Preprocess", "ZH": "骨骼方向预处理"},
    # NOTE: straighten_orientation/auto_refresh/apply_angle_ramp description= are per-property
    # operator tooltips (same pattern-6 gap), left as plain English literals in operators.py.

    "mhrs.operators.auto_refresh_label": {
        "EN": "Create Directly (Auto-refresh Bone Colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},

    "mhrs.operators.apply_angle_ramp_label": {"EN": "Auto-apply Angle Ramp", "ZH": "自动应用角度坡度"},

    "mhrs.operators.no_markers_warning": {"EN": "The current armature has no markers!", "ZH": "当前骨架没有任何标记！"},
    "mhrs.operators.no_markers_hint": {
        "EN": "It's recommended to manually mark chains with the Physics Chain Tools first before using this feature.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "mhrs.operators.create_failed": {"EN": "Failed to create RE Chain", "ZH": "创建 RE Chain 失败"},
    "mhrs.operators.create_done": {"EN": "RE Chain creation complete", "ZH": "RE Chain 创建完成"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHRS_PART_LABEL_KEYS (part_id -> bilingual display label) ──────────
    "mhrs.batch_export.part_arm":  {"EN": "Arm",   "ZH": "护腕"},
    "mhrs.batch_export.part_body": {"EN": "Body",  "ZH": "躯干"},
    "mhrs.batch_export.part_wst":  {"EN": "Waist", "ZH": "腰带"},
    "mhrs.batch_export.part_helm": {"EN": "Helm",  "ZH": "头盔"},
    "mhrs.batch_export.part_leg":  {"EN": "Leg",   "ZH": "腿部"},

    "mhrs.batch_export.gender_f": {"EN": "Female", "ZH": "女"},
    "mhrs.batch_export.gender_m": {"EN": "Male",   "ZH": "男"},

    # ── get_mhrs_schemes_callback / get_mhrs_armor_callback fallback items ─
    "mhrs.batch_export.no_armor_pack": {"EN": "No armor pack", "ZH": "无装备包"},
    "mhrs.batch_export.no_armor":      {"EN": "No armor", "ZH": "无装备"},

    # ── MHRS_OT_BatchExport / MHRS_OT_SetNativesRoot ────────────────────────
    "mhrs.batch_export.batch_export_desc": {"EN": "Batch-export MHRS armor", "ZH": "MHRS 装备批量导出"},
    "mhrs.batch_export.set_natives_root_desc": {
        "EN": "Select the MHRS mod root folder (the parent of natives). If the selected folder is itself "
              "named natives, its parent is used automatically",
        "ZH": "选择 MHRS Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"},

    "mhrs.batch_export.remesh_not_installed": {
        "EN": "RE Mesh Editor not installed, skipping pre-export cleanup", "ZH": "RE Mesh Editor 未安装，跳过导出前清理"},
    "mhrs.batch_export.set_mod_root_first": {
        "EN": "Please set the Mod Root directory first (the parent folder of natives)",
        "ZH": "请先设置 Mod Root 目录（natives 的上级文件夹）"},
    "mhrs.batch_export.load_scheme_failed": {"EN": "Could not load the armor pack", "ZH": "无法加载装备包"},
    "mhrs.batch_export.select_armor_first": {"EN": "Please select an armor set first", "ZH": "请先选择一套装备"},
    "mhrs.batch_export.armor_not_found_in_scheme": {
        "EN": "Not found in armor pack: {id}", "ZH": "在装备包中未找到: {id}"},
    "mhrs.batch_export.export_done_with_fail": {
        "EN": "Done: exported {export}, failed {fail}, skipped {skip}",
        "ZH": "完成: 导出 {export}, 失败 {fail}, 跳过 {skip}"},
    "mhrs.batch_export.export_done": {
        "EN": "Done: exported {export}, skipped {skip}", "ZH": "完成: 导出 {export}, 跳过 {skip}"},

    "mhrs.batch_export.shadow_need_importer": {
        "EN": "Shadow export: requires RE Mesh Editor's mesh importer", "ZH": "Shadow 导出: 需要 RE Mesh Editor 的网格导入器"},
    "mhrs.batch_export.shadow_need_align_arm": {
        "EN": "Shadow export: please select an armature to align to", "ZH": "Shadow 导出: 请选择一个用于对齐的骨架"},
    "mhrs.batch_export.shadow_missing_asset": {
        "EN": "Shadow export: missing built-in reference model {name} (place it under assets/mhrs/shadow/)",
        "ZH": "Shadow 导出: 缺少内置参考模型 {name}（需放入 assets/mhrs/shadow/）"},
    "mhrs.batch_export.shadow_import_failed": {
        "EN": "Failed to import reference model: {path}", "ZH": "导入参考模型失败: {path}"},
    "mhrs.batch_export.shadow_no_unique_armature": {
        "EN": "No unique armature found in the reference model collection", "ZH": "参考模型集合中未找到唯一骨架"},
    "mhrs.batch_export.shadow_export_done": {"EN": "Shadow export complete: {name}", "ZH": "Shadow 导出完成: {name}"},
    "mhrs.batch_export.shadow_export_failed": {"EN": "Shadow export failed: {err}", "ZH": "Shadow 导出失败: {err}"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.batch_export_ui.pick_armor_desc": {
        "EN": "Search and pick an armor set (avoids the dropdown overflowing the screen when there are many)",
        "ZH": "搜索并选择装备（避免装备过多时下拉表溢出屏幕）"},
    "mhrs.batch_export_ui.batch_export_dialog_desc": {
        "EN": "MHRS armor batch-export dialog", "ZH": "MHRS 装备批量导出对话框"},

    "mhrs.batch_export_ui.armor_pack_label":      {"EN": "Armor Pack", "ZH": "装备包"},
    "mhrs.batch_export_ui.select_armor_placeholder": {"EN": "Select Armor...", "ZH": "选择装备..."},
    "mhrs.batch_export_ui.not_set":               {"EN": "Not set", "ZH": "未设置"},
    "mhrs.batch_export_ui.select_armor_to_configure": {
        "EN": "Select an armor set to configure bindings", "ZH": "请选择装备以配置绑定"},

    "mhrs.batch_export_ui.use_shadow_mesh_label":  {"EN": "Use Shadow Mesh", "ZH": "使用 Shadow Mesh"},
    "mhrs.batch_export_ui.align_armature_label":   {"EN": "Align Armature", "ZH": "对齐骨架"},
    "mhrs.batch_export_ui.shadow_auto_use_hint":   {
        "EN": "Will auto-use when unselected: {name}", "ZH": "未选择时将自动使用: {name}"},
    "mhrs.batch_export_ui.shadow_no_align_arm_error": {
        "EN": "No align armature selected, and it cannot be auto-determined (requires exactly 1 bound Mesh collection)",
        "ZH": "未选择对齐骨架，且无法自动判定（需恰好绑定 1 个 Mesh 集合）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_generator.use_toon_label": {"EN": "Toon Shading", "ZH": "使用三渲二"},
    "mhrs.mdf_generator.generate_mipmaps_label": {"EN": "Generate MipMaps", "ZH": "生成 MipMaps"},
    "mhrs.mdf_generator.skip_textures_label": {"EN": "Material Only", "ZH": "仅生成材质"},
    "mhrs.mdf_generator.use_ao_label": {"EN": "Add AO", "ZH": "添加 AO"},
    "mhrs.mdf_generator.flip_normal_g_label": {"EN": "Normal OpenGL -> DirectX", "ZH": "法线 OpenGL → DirectX"},
    # NOTE: use_toon/skip_textures/use_ao/ao_image/flip_normal_g description= are PropertyGroup
    # property tooltips (pattern 6 — no per-draw dynamic-tooltip hook for regular properties),
    # left as plain English literals in mdf_generator.py.

    "mhrs.mdf_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the Mesh Collection that use the active material (stage 2: smart filter)",
        "ZH": "选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "mhrs.mdf_generator.select_mesh_collection_first": {
        "EN": "Please select a Mesh Collection first", "ZH": "请先选择 Mesh Collection"},
    "mhrs.mdf_generator.active_obj_no_material": {
        "EN": "The active object has no material", "ZH": "激活物体没有材质"},
    "mhrs.mdf_generator.select_same_material_done": {
        "EN": "Selected {n} mesh(es) using '{name}' (including itself: {total} total)",
        "ZH": "已选中 {n} 个使用 '{name}' 的网格（含自身共 {total} 个）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_generator_ui.dialog_desc": {
        "EN": "MHRS MDF2 Generator — creates MDF2 + textures from Blender mesh materials. Requires an existing "
              "mesh collection with a Principled BSDF wired up in the material",
        "ZH": "MHRS MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，并在材质里连好 Principled BSDF"},

    "mhrs.mdf_generator_ui.strat_color":     {"EN": "Base Color", "ZH": "基础色"},
    "mhrs.mdf_generator_ui.strat_normal":    {"EN": "Normal", "ZH": "法线"},
    "mhrs.mdf_generator_ui.strat_roughness": {"EN": "Roughness", "ZH": "粗糙度"},
    "mhrs.mdf_generator_ui.strat_metallic":  {"EN": "Metallic", "ZH": "金属度"},
    "mhrs.mdf_generator_ui.strat_alpha":     {"EN": "Alpha", "ZH": "Alpha"},
    "mhrs.mdf_generator_ui.strat_emissive":  {"EN": "Emissive", "ZH": "自发光"},

    "mhrs.mdf_generator_ui.auto_name_hint": {"EN": "    Auto: {name}", "ZH": "    自动: {name}"},
    "mhrs.mdf_generator_ui.base_path_hint": {"EN": "    e.g. player/mod/f/pl279", "ZH": "    例如 player/mod/f/pl279"},
    "mhrs.mdf_generator_ui.preset_dir_not_found": {
        "EN": "RE Mesh Editor MHRS preset directory not found", "ZH": "未找到 RE Mesh Editor MHRS 预设目录"},
    "mhrs.mdf_generator_ui.select_collection_hint": {
        "EN": "Select a mesh collection, then click refresh", "ZH": "选择网格集合后点击刷新"},
    "mhrs.mdf_generator_ui.strat_analysis_header": {
        "EN": "Node Tree Analysis (Texture Source Strategy)", "ZH": "节点树分析 (贴图来源策略)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_tex_processor_ui.dialog_desc": {
        "EN": "MDF2 Processor — processes textures on top of existing MDF2 materials. Requires an existing, "
              "already-named MDF2 collection",
        "ZH": "MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合"},
}
