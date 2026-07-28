"""Strings for games/re9/.

Covers: games/re9/operators.py, games/re9/batch_export.py,
games/re9/batch_export_ui.py, games/re9/mdf_generator.py,
games/re9/mdf_generator_ui.py, games/re9/mdf_tex_processor_ui.py.

Key naming convention: "re9.<file_without_.py>.<short_purpose>".
"""

STRINGS = {

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/operators.py
    # ══════════════════════════════════════════════════════════════════════

    # ── RE9_OT_AutoCreateChains ─────────────────────────────────────────────
    "re9.operators.auto_create_chains_desc": {
        "EN": "One-click create an RE Chain (RE9 defaults to the .chain2 format)",
        "ZH": "一键创建 RE Chain（RE9 默认 .chain2 格式）。"},

    # settings_mode EnumProperty items (callback; label + tooltip)
    "re9.operators.settings_mode_separate": {"EN": "Separate", "ZH": "各自独立"},
    "re9.operators.settings_mode_separate_desc": {
        "EN": "Each chain gets its own independent Chain Settings",
        "ZH": "每条链拥有独立的 Chain Settings"},
    "re9.operators.settings_mode_shared": {"EN": "Shared", "ZH": "共享同一"},
    "re9.operators.settings_mode_shared_desc": {
        "EN": "All chains share the same Chain Settings",
        "ZH": "所有链共用同一个 Chain Settings"},
    "re9.operators.settings_mode_guess": {"EN": "Guess Groups", "ZH": "猜测分组"},
    "re9.operators.settings_mode_guess_desc": {
        "EN": "Auto-classify by bone name; same-type chains share one Chain Settings group with "
              "guessed physics parameters written in; unrecognized chains fall into the first group",
        "ZH": "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组"},

    # chain_format EnumProperty items (callback; tooltip only, labels already EN)
    "re9.operators.chain_format_chain_desc": {
        "EN": "Legacy format, used by RE4 and other early games",
        "ZH": "旧格式，用于 RE4 等早期游戏"},
    "re9.operators.chain_format_chain2_desc": {
        "EN": "New format, used by MHWilds / RE9",
        "ZH": "新格式，用于 MHWilds / RE9"},

    # Draw-site labels for properties whose registered name= is a short EN fallback
    "re9.operators.auto_create_collection": {"EN": "Auto Create Collection", "ZH": "自动创建集合"},
    "re9.operators.collection_name": {"EN": "Collection Name", "ZH": "集合名称"},
    "re9.operators.sync_orientation": {"EN": "Sync Chain Head Orientation", "ZH": "同步链首朝向"},
    "re9.operators.auto_refresh": {"EN": "Auto Create (Refresh Bone Colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},
    "re9.operators.apply_angle_ramp": {"EN": "Auto Apply Angle Ramp", "ZH": "自动应用角度坡度"},

    "re9.operators.no_markers_warning": {
        "EN": "The current armature has no markers!", "ZH": "当前骨架没有任何标记！"},
    "re9.operators.no_markers_suggestion": {
        "EN": "It's recommended to manually mark chains with the physics chain tool before using this feature.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "re9.operators.create_chain_failed": {"EN": "Failed to create RE Chain", "ZH": "创建 RE Chain 失败"},
    "re9.operators.create_chain_done": {"EN": "RE Chain created", "ZH": "RE Chain 创建完成"},

    # ── RE9_OT_AddFacialBones ────────────────────────────────────────────────
    "re9.operators.add_facial_bones_desc": {
        "EN": "Graft facial bones from the native character armature onto the current armature, "
              "with an optional fake-head trick to adjust blink amplitude",
        "ZH": "将原生角色骨架的表情骨骼移植到当前骨架，可选择使用假头法调整眨眼幅度"},
    "re9.operators.target_armature": {"EN": "Armature", "ZH": "骨架"},
    "re9.operators.reference_character": {"EN": "Reference Character", "ZH": "参考角色"},
    "re9.operators.increase_blink_amplitude": {"EN": "Increase Blink Amplitude", "ZH": "增加眨眼幅度（二次元模型用）"},

    "re9.operators.facial_bones_warning": {
        "EN": "Using this feature will remove any existing facial bones!",
        "ZH": "使用该功能将清除原本存在的表情骨！"},
    "re9.operators.select_valid_armature": {"EN": "Please select a valid armature", "ZH": "请选择一个有效的骨架"},
    "re9.operators.select_reference_character": {
        "EN": "Please select a reference character (add files to assets/reference_skeletons/re9/)",
        "ZH": "请选择参考角色（添加文件到 assets/reference_skeletons/re9/）"},
    "re9.operators.reference_import_failed": {
        "EN": "Failed to import reference armature: {name}", "ZH": "参考骨架导入失败: {name}"},
    "re9.operators.facial_root_not_found": {
        "EN": "Facial bone root not found in the reference armature ({name})",
        "ZH": "参考骨架中未找到表情骨根骨骼 ({name})"},
    "re9.operators.facial_bones_added": {"EN": "Added {n} facial bone(s)", "ZH": "已添加 {n} 根表情骨"},
    "re9.operators.blink_amplitude_added": {
        "EN": ", increased blink amplitude on {n} side(s)", "ZH": "，{n} 侧已增加眨眼幅度"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    "re9.batch_export.set_natives_root_desc": {
        "EN": "Select the RE9 mod root folder (the parent of natives). If the selected folder is "
              "itself named natives, its parent is used automatically",
        "ZH": "选择 RE9 Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "re9.batch_export_ui.will_align_native_skeleton": {
        "EN": "Will align to native skeleton: {name}", "ZH": "将对齐原生骨架: {name}"},
    "re9.batch_export_ui.native_skeleton_not_found": {
        "EN": "Native skeleton file not found; the selected armature will be exported directly",
        "ZH": "未找到原生骨架文件，将直接导出选中骨架"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/mdf_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "re9.mdf_tex_processor_ui.dialog_desc": {
        "EN": "MDF2 + Tex Processor — process textures on top of an existing MDF2 material. "
              "Requires an existing, already-named MDF2 collection",
        "ZH": "MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/mdf_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "re9.mdf_generator.use_toon": {"EN": "Use Toon Shading", "ZH": "使用三渲二"},
    "re9.mdf_generator.generate_mipmaps": {"EN": "Generate MipMaps", "ZH": "生成 MipMaps"},
    "re9.mdf_generator.skip_textures": {"EN": "Materials Only", "ZH": "仅生成材质"},
    "re9.mdf_generator.use_ao": {"EN": "Add AO", "ZH": "添加 AO"},
    "re9.mdf_generator.flip_normal_g": {"EN": "Normal OpenGL → DirectX", "ZH": "法线 OpenGL → DirectX"},

    "re9.mdf_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the Mesh Collection that use the current material (stage 2: smart filtering)",
        "ZH": "选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "re9.mdf_generator.select_mesh_collection_first": {
        "EN": "Please select a Mesh Collection first", "ZH": "请先选择 Mesh Collection"},
    "re9.mdf_generator.active_object_no_material": {
        "EN": "The active object has no material", "ZH": "激活物体没有材质"},
    "re9.mdf_generator.selected_same_material_done": {
        "EN": "Selected {n} mesh(es) using '{name}' ({total} total including itself)",
        "ZH": "已选中 {n} 个使用 '{name}' 的网格（含自身共 {total} 个）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/mdf_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "re9.mdf_generator_ui.dialog_desc": {
        "EN": "RE9 MDF2 Generator — create MDF2 + textures from a Blender mesh's materials. "
              "Requires an existing mesh collection with a Principled BSDF wired up in the materials",
        "ZH": "RE9 MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，并在材质里连好 Principled BSDF"},

    "re9.mdf_generator_ui.strat_color": {"EN": "Base Color", "ZH": "基础色"},
    "re9.mdf_generator_ui.strat_normal": {"EN": "Normal", "ZH": "法线"},
    "re9.mdf_generator_ui.strat_roughness": {"EN": "Roughness", "ZH": "粗糙度"},
    "re9.mdf_generator_ui.strat_metallic": {"EN": "Metallic", "ZH": "金属度"},
    "re9.mdf_generator_ui.strat_alpha": {"EN": "Alpha", "ZH": "Alpha"},
    "re9.mdf_generator_ui.strat_emissive": {"EN": "Emissive", "ZH": "自发光"},

    "re9.mdf_generator_ui.auto_name_label": {"EN": "Auto: {name}", "ZH": "自动: {name}"},
    "re9.mdf_generator_ui.preset_dir_not_found": {
        "EN": "RE Mesh Editor RE9 preset directory not found", "ZH": "未找到 RE Mesh Editor RE9 预设目录"},
    "re9.mdf_generator_ui.select_mesh_then_refresh": {
        "EN": "Select a mesh collection, then click refresh", "ZH": "选择网格集合后点击刷新"},
    "re9.mdf_generator_ui.node_tree_analysis": {
        "EN": "Node Tree Analysis (Texture Source Strategy)", "ZH": "节点树分析 (贴图来源策略)"},
}
