"""
core/i18n_strings/mhwi.py — bilingual STRINGS table for games/mhwi/*.py.

Key naming convention: "mhwi.<module_name_without_.py>.<short_purpose>".
"""

STRINGS = {
    # ── MHWI_OT_EndfieldFaceRename ──────────────────────────────────────────
    "mhwi.operators.endfield_face_rename_desc": {
        "EN": "Batch-convert Endfield facial vertex group names to MHWorld format",
        "ZH": "将 Endfield 面部顶点组名称批量转换为 MHWorld 格式"},
    "mhwi.operators.endfield_face_rename_label": {
        "EN": "Endfield Face Rename", "ZH": "Endfield 面部改名"},
    "mhwi.operators.endfield_processed": {
        "EN": "Renamed / merged {n} vertex group(s)",
        "ZH": "已改名 / 合并 {n} 个顶点组"},
    "mhwi.operators.endfield_map_missing": {
        "EN": "assets/facial_maps/endfield_to_mhwi.json is missing or unreadable",
        "ZH": "读不到 assets/facial_maps/endfield_to_mhwi.json"},


    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/operators.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHWI_OT_AlignNonPhysics ─────────────────────────────────────────────
    "mhwi.operators.align_non_physics_desc": {
        "EN": "Align MHWI bones (skip physics bones numbered 150-245)",
        "ZH": "对齐 MHWI 骨骼 (跳过 150-245 物理骨)"},
    "mhwi.operators.select_two_armatures": {
        "EN": "Please select two armatures (source -> target)",
        "ZH": "请选择两个骨架 (源 -> 目标)"},
    "mhwi.operators.align_done": {
        "EN": "Aligned: {aligned}, skipped physics bones: {skip}",
        "ZH": "对齐: {aligned}, 跳过物理骨: {skip}"},

    # ── MHWI_OT_PreprocessModel ──────────────────────────────────────────────
    "mhwi.operators.preprocess_model_desc": {
        "EN": "Auto-detect MMD/VRChat -> pose correction -> import the MHWI reference body -> lift it so its "
              "soles stand on the ground -> arm-height scale and Y-offset calibration -> skeleton alignment "
              "-> lower both back together.\n"
              "The reference ends up reshaped to the model's proportions. Requires the MHW Model Editor add-on.",
        "ZH": "自动检测 MMD/VRChat → 姿态修正 → 导入猎人参考身体 → 把它抬到脚底着地 → 按手臂高度缩放、"
              "校准 Y 偏移 → 骨架对齐 → 两边一起放回原位。\n"
              "对齐后参考骨架会被吸附成这具模型的比例。需要 MHW Model Editor 插件。"},
    "mhwi.operators.no_mhwi_preset_detected": {
        "EN": "Could not auto-detect an MHWI bone preset; please manually select the target preset in the panel "
              "and retry",
        "ZH": "未能自动检测到猎人骨骼预设，请在面板中手动选择目标预设后重试"},

    # ── MHWI_OT_AutoCreateChains ─────────────────────────────────────────────
    "mhwi.operators.auto_create_chains_desc": {
        "EN": "In Pose Mode, automatically create CTC Chains from the chain_role property of "
              "physics bones.\n"
              "A CTC chain must be linear, so forks are split: a branch marked as the main-chain "
              "continuation (or picked by Graft) carries on through the fork, every other branch "
              "becomes its own chain. Only one level of branches is built; sub-branches tagged "
              "no_chain are left without a chain and reported.\n"
              "Requires the MHW Model Editor add-on.",
        "ZH": "在姿态模式下，根据物理骨骼的 chain_role 属性自动创建 CTC Chain。\n"
              "CTC 的一条链必须是线性的，所以分叉会被拆开：标为主链延伸（或移植时自动选定）的一支"
              "穿过分叉继续，其余分支各自另起一条链。只生成单层分支；标为 no_chain 的子分支"
              "不生成链，并会在结果里报告。\n"
              "需要 MHW Model Editor 插件。"},
    "mhwi.operators.auto_refresh_name": {
        "EN": "Create Directly (auto-refresh bone colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},
    "mhwi.operators.ctc_collection_desc": {
        "EN": "Select the CTC Collection to write into", "ZH": "选择要写入的 CTC Collection"},
    "mhwi.operators.auto_create_collection_name": {
        "EN": "Auto-create Collection", "ZH": "自动创建集合"},
    "mhwi.operators.straighten_orientation_name": {
        "EN": "Bone Orientation Preprocessing", "ZH": "骨骼方向预处理"},
    "mhwi.operators.no_markers_warning": {
        "EN": "This armature has no markers yet!", "ZH": "当前骨架没有任何标记！"},
    "mhwi.operators.no_markers_hint": {
        "EN": "It's recommended to mark chains manually with the physics chain tools first.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "mhwi.operators.auto_create_ctc_failed": {
        "EN": "Failed to auto-create CTC Collection", "ZH": "自动创建 CTC Collection 失败"},
    "mhwi.operators.collection_not_found": {
        "EN": "Collection not found: {name}", "ZH": "找不到集合: {name}"},
    "mhwi.operators.ctc_toolpanel_missing": {
        "EN": "MHW CTC scene properties not found; please confirm MHW Model Editor is loaded correctly",
        "ZH": "未找到 MHW CTC 场景属性，请确认 MHW Model Editor 已正确加载"},
    "mhwi.operators.no_chain_heads": {
        "EN": "No chain head bones found (chain_role=head/branch_head); please refresh bone colors first",
        "ZH": "未找到链首骨骼（chain_role=head/branch_head），请先刷新骨骼颜色"},
    "mhwi.operators.chains_created": {
        "EN": "{n} chain(s) created", "ZH": "已创建 {n} 条链"},
    "mhwi.operators.chains_skipped_existing": {
        "EN": "{n} already existed, skipped", "ZH": "已存在跳过 {n} 条"},
    "mhwi.operators.chains_failed": {
        "EN": "{n} failed to create: {names}", "ZH": "创建失败 {n} 条: {names}"},
    "mhwi.operators.chains_too_short": {
        "EN": "{n} too short (a chain needs at least 2 bones): {names}",
        "ZH": "太短跳过 {n} 条（一条链至少 2 根骨）: {names}"},
    "mhwi.operators.chains_no_chain": {
        "EN": "{n} sub-branch(es) got no chain (bones and weights kept, physics-free): {names}",
        "ZH": "{n} 处子分支不生成链（骨骼与权重保留，无物理）: {names}"},
    "mhwi.operators.list_sep": {"EN": ", ", "ZH": "，"},

    # ── MHWI_OT_SplitPhysicsBones ────────────────────────────────────────────
    "mhwi.operators.split_physics_bones_desc": {
        "EN": "Rename physics bones to MhBone_xxx; split into parts (meshes included) only when they do not fit.\n"
              "Already processed and it fits: renumbered incrementally right away -- bones whose ID fits keep it.\n"
              "Otherwise a dialog asks what to make of it: when using the \"Remove Physics Limit\" plugin, everything follows the\n"
              "no-limit rules (300-511); without it, choose body (no limit) or another part (physics 150-199,\n"
              "tails 200-245 then 260-299). Body over 255 bones in total is split; another part that does not fit\n"
              "is refused -- make it body, use the plugin, or simplify it yourself.\n"
              "With several armatures selected, the processed ones that fit are renumbered and the rest listed.",
        "ZH": "把物理骨重命名为 MhBone_xxx；装不下时才按部位拆分（网格一起处理）。\n"
              "已处理过且装得下：直接增量重新编号——编号已合规的骨保持不动。\n"
              "其余情况弹窗确认要做成什么：使用「解除物理上限」插件时一律按无限制规则（300~511）；\n"
              "不使用时选 body（无限制）或其他部位（物理 150~199，末端 200~245、满了接 260~299）。\n"
              "body 总骨数超 255 时拆分；其他部位装不下时不执行——改做 body、使用插件或自行简化。\n"
              "同时选中多副骨架时：已处理过且装得下的重新编号，其余列出来。"},
    "mhwi.operators.target_body": {"EN": "Body", "ZH": "body"},
    "mhwi.operators.target_body_desc": {
        "EN": "No ID range limit: physics bones go to 300-511; over 255 bones in total is split into parts",
        "ZH": "无编号范围限制：物理骨编到 300~511；总骨数超过 255 时拆分到多个部位"},
    "mhwi.operators.target_part": {"EN": "Other part (arm / wst / leg)", "ZH": "其他部位（arm / wst / leg）"},
    "mhwi.operators.target_part_desc": {
        "EN": "Range-limited: only 150-199 has physics (50 bones); tails 200-245 then 260-299 (86)",
        "ZH": "有范围限制：只有 150~199 有物理（50 根）；末端 200~245、满了接 260~299（86 根）"},
    "mhwi.operators.processed_header": {
        "EN": "Already processed ({state}), but renumbering by its current IDs does not fit:",
        "ZH": "这副骨架已处理过（{state}），但按现有编号直接重命名装不下："},
    "mhwi.operators.outcome_rename": {
        "EN": "Fits: renamed by {rule} rules, no split",
        "ZH": "装得下：按{rule}规则直接重命名，不拆分"},
    "mhwi.operators.outcome_split": {
        "EN": "Over 255 bones in total: split into parts, then rename",
        "ZH": "总骨数超过 255：拆分到多个部位后重命名"},
    "mhwi.operators.overflow_resplit": {
        "EN": "This already-processed armature is split as a whole set: it becomes body",
        "ZH": "这副已处理过的骨架会被当作整套拆分：它自己变成 body"},
    "mhwi.operators.outcome_block": {
        "EN": "Does not fit a range-limited part:", "ZH": "做成有范围限制的部位装不下："},
    "mhwi.operators.block_option_body": {
        "EN": "- make it body instead (it can be split there)", "ZH": "· 改为做成 body（那边可以拆分）"},
    "mhwi.operators.block_option_plugin": {
        "EN": "- or use the \"Remove Physics Limit\" plugin (tick it above)", "ZH": "· 或者使用「解除物理上限」插件（勾选上方选项）"},
    "mhwi.operators.block_option_simplify": {
        "EN": "- or simplify the physics bones yourself", "ZH": "· 或者自行简化物理骨"},
    "mhwi.operators.block_noop": {
        "EN": "OK does nothing in this state -- change the choice above or cancel",
        "ZH": "这种情况下点确定不会执行任何操作，请调整上方选项或取消"},
    "mhwi.operators.renumber_only": {
        "EN": "{name}: renamed by {rule} rules without splitting ({changed} renamed, {kept} kept, {fail} failed)",
        "ZH": "{name}：按{rule}规则重命名，未拆分（改名 {changed} 根，保留 {kept} 根，失败 {fail} 根）"},
    "mhwi.operators.renumber_many_done": {
        "EN": "Renumbered {n} armature(s): {changed} renamed, {kept} kept, {fail} failed",
        "ZH": "重新编号 {n} 副骨架：改名 {changed} 根，保留 {kept} 根，失败 {fail} 根"},
    "mhwi.operators.renumber_need_split": {
        "EN": "Not touched, these need splitting -- select each on its own: {names}",
        "ZH": "以下骨架需要拆分，未处理，请逐个单独选中：{names}"},
    "mhwi.operators.rule_body": {"EN": "no-range-limit", "ZH": "无范围限制"},
    "mhwi.operators.rule_slot": {"EN": "range-limited", "ZH": "有范围限制"},
    "mhwi.operators.state_partial": {"EN": "partly renamed", "ZH": "部分已重命名"},
    "mhwi.operators.state_normalized": {"EN": "fully renamed", "ZH": "已全部重命名"},
    "mhwi.operators.overflow_physics": {"EN": "Physics bones {n}/{cap}", "ZH": "物理骨 {n}/{cap}"},
    "mhwi.operators.overflow_tail": {"EN": "Tail bones {n}/{cap}", "ZH": "末端骨 {n}/{cap}"},
    "mhwi.operators.overflow_total": {"EN": "Total bones {n}/{cap}", "ZH": "总骨数 {n}/{cap}"},
    "mhwi.operators.region_head": {"EN": "Head", "ZH": "头部"},
    "mhwi.operators.region_upper": {"EN": "Upper Body", "ZH": "上半身"},
    "mhwi.operators.region_lower": {"EN": "Lower Body", "ZH": "下半身"},
    "mhwi.operators.col_region": {"EN": "Region", "ZH": "区域"},
    "mhwi.operators.col_bone_count": {"EN": "Physics Bones", "ZH": "物理骨数"},
    "mhwi.operators.col_target_slot": {"EN": "Target Slot", "ZH": "目标部位"},
    "mhwi.operators.cannot_load_world_preset": {
        "EN": "Cannot load the Monster Hunter World preset", "ZH": "无法加载怪猎世界预设"},
    "mhwi.operators.no_physics_bones_found": {
        "EN": "No physics bones found to process", "ZH": "未找到需要处理的物理骨骼"},
    "mhwi.operators.confirm_region_targets": {
        "EN": "Please confirm the target slot for each region:", "ZH": "请确认各区域的目标部位："},
    "mhwi.operators.rename_done": {
        "EN": "Rename complete: {success} succeeded, {fail} failed",
        "ZH": "重命名完成：成功 {success} 根，失败 {fail} 根"},
    "mhwi.operators.split_overflow": {
        "EN": "{n} bone(s) fit in no part (largest: {names}); decimate when grafting, or use the \"Remove Physics Limit\" plugin",
        "ZH": "还有 {n} 根骨放不下（最大的几组：{names}）；移植时勾选抽稀，或使用「解除物理上限」插件"},
    "mhwi.operators.split_spare_note": {
        "EN": "What does not fit its region's part goes to {slot}, then to any part with room",
        "ZH": "放不进本区域部位的先进 {slot}，再进任何还有空的部位"},
    "mhwi.operators.split_auto_pack": {
        "EN": "Without the plugin, groups are packed by size: arm / wst / leg first, the rest into body",
        "ZH": "未装插件：按大小自动装箱，arm / wst / leg 优先，放不下的进 body"},
    "mhwi.operators.split_mesh_summary": {
        "EN": "Meshes: {moved} moved whole, {split} split by face; {verts} vertex(es) had another part's physics weight moved to its anchor bone",
        "ZH": "网格：整块移走 {moved} 个，按面拆开 {split} 个；{verts} 个顶点上别的部位的物理权重改挂到锚点骨"},
    "mhwi.operators.split_no_mod3": {
        "EN": "The armature is not inside a .mod3 collection; each new part was put in a plain collection — move it into its own .mod3 collection before exporting",
        "ZH": "骨架不在 .mod3 集合里，新部位放进了普通集合；导出前请各自放进单独的 .mod3 集合"},
    "mhwi.operators.split_done": {
        "EN": "Split complete: {n} armature(s) generated ({names})",
        "ZH": "拆分完成：已生成 {n} 个骨架（{names}）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_import.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_import.part_arm":  {"EN": "Arms", "ZH": "手臂"},
    "mhwi.batch_import.part_leg":  {"EN": "Legs", "ZH": "腿部"},
    "mhwi.batch_import.part_body": {"EN": "Chest", "ZH": "身体"},
    "mhwi.batch_import.part_helm": {"EN": "Head", "ZH": "头盔"},
    "mhwi.batch_import.part_wst":  {"EN": "Waist", "ZH": "腰部"},
    "mhwi.batch_import.gender_f":  {"EN": "Female", "ZH": "女"},
    "mhwi.batch_import.gender_m":  {"EN": "Male", "ZH": "男"},

    "mhwi.batch_import.scan_desc": {
        "EN": "Scan the current Mod Root folder and list importable equipment files",
        "ZH": "扫描当前 Mod Root 目录，列出可导入的装备文件"},
    "mhwi.batch_import.set_mod_root_first": {
        "EN": "Please set the Mod Root folder first (the parent folder of nativePC)",
        "ZH": "请先设置 Mod Root 目录（nativePC 的上级文件夹）"},
    "mhwi.batch_import.no_files_found": {
        "EN": "No importable equipment files found; please confirm the folder structure is correct",
        "ZH": "未找到任何可导入的装备文件，请确认目录结构正确"},
    "mhwi.batch_import.scan_done": {
        "EN": "Scan complete, found {n} file(s)", "ZH": "解析完成，找到 {n} 个文件"},
    "mhwi.batch_import.toggle_group_desc": {
        "EN": "Expand/collapse one equipment set", "ZH": "展开/折叠一套装备"},
    "mhwi.batch_import.select_group_desc": {
        "EN": "Batch select/deselect all files in one equipment set", "ZH": "批量选中/取消选中一套装备的所有文件"},
    "mhwi.batch_import.select_all_desc": {
        "EN": "Select/deselect all pending import files", "ZH": "全选/全不选所有待导入文件"},
    "mhwi.batch_import.batch_import_desc": {
        "EN": "MHWI equipment batch import", "ZH": "MHWI 装备批量导入"},
    "mhwi.batch_import.model_editor_missing": {
        "EN": "MHW Model Editor is not installed", "ZH": "MHW Model Editor 未安装"},
    "mhwi.batch_import.no_items_selected": {
        "EN": "No items selected", "ZH": "没有选中任何项目"},
    "mhwi.batch_import.import_done_with_fail": {
        "EN": "Done: imported {ok}, failed {fail}", "ZH": "完成: 导入 {ok}, 失败 {fail}"},
    "mhwi.batch_import.import_done": {
        "EN": "Done: imported {ok} file(s)", "ZH": "完成: 导入 {ok} 个文件"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_import_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_import_ui.dialog_desc": {
        "EN": "MHWI equipment batch import dialog", "ZH": "MHWI 装备批量导入对话框"},
    "mhwi.batch_import_ui.not_set": {"EN": "Not set", "ZH": "未设置"},
    "mhwi.batch_import_ui.scan_btn": {"EN": "Scan", "ZH": "解析"},
    "mhwi.batch_import_ui.click_scan_hint": {
        "EN": "Click \"Scan\" to scan for equipment files", "ZH": "点击「解析」扫描装备文件"},
    "mhwi.batch_import_ui.set_mod_root_hint": {
        "EN": "Please set Mod Root first", "ZH": "请先设置 Mod Root"},
    "mhwi.batch_import_ui.deselect_all": {"EN": "Deselect All", "ZH": "全不选"},
    "mhwi.batch_import_ui.selected_count": {
        "EN": "{enabled} / {total} selected", "ZH": "{enabled} / {total} 已选"},
    "mhwi.batch_import_ui.main_model": {"EN": "Main Model", "ZH": "主模型"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/weapon_data.py
    # ══════════════════════════════════════════════════════════════════════
    # (weapon type display names in WEAPON_TYPES are static English fallbacks
    # since that list is a module-level constant evaluated once at import time,
    # before the addon's language preference is loaded; only the secondary-part
    # labels below are re-looked-up dynamically via get_weapon_parts())

    "mhwi.weapon_data.type_two":  {"EN": "Greatsword",     "ZH": "大剑"},
    "mhwi.weapon_data.type_one":  {"EN": "Sword & Shield", "ZH": "片手剑"},
    "mhwi.weapon_data.type_sou":  {"EN": "Dual Blades",    "ZH": "双剑"},
    "mhwi.weapon_data.type_swo":  {"EN": "Long Sword",     "ZH": "太刀"},
    "mhwi.weapon_data.type_ham":  {"EN": "Hammer",         "ZH": "大锤"},
    "mhwi.weapon_data.type_hue":  {"EN": "Hunting Horn",   "ZH": "狩猎笛"},
    "mhwi.weapon_data.type_lan":  {"EN": "Lance",          "ZH": "长枪"},
    "mhwi.weapon_data.type_gun":  {"EN": "Gunlance",       "ZH": "铳枪"},
    "mhwi.weapon_data.type_saxe": {"EN": "Switch Axe",     "ZH": "斩斧"},
    "mhwi.weapon_data.type_caxe": {"EN": "Charge Blade",   "ZH": "盾斧"},
    "mhwi.weapon_data.type_rod":  {"EN": "Insect Glaive",  "ZH": "操虫棍"},
    "mhwi.weapon_data.type_bow":  {"EN": "Bow",            "ZH": "弓"},
    "mhwi.weapon_data.type_hbg":  {"EN": "Heavy Bowgun",   "ZH": "重弩炮"},
    "mhwi.weapon_data.type_lbg":  {"EN": "Light Bowgun",   "ZH": "轻弩炮"},

    "mhwi.weapon_data.part_main":   {"EN": "Main Model", "ZH": "主模型"},
    "mhwi.weapon_data.part_sld":    {"EN": "Shield", "ZH": "盾"},
    "mhwi.weapon_data.part_saya":   {"EN": "Sheath", "ZH": "刀鞘"},
    "mhwi.weapon_data.part_sou_r":  {"EN": "Right Blade", "ZH": "右手剑"},
    "mhwi.weapon_data.part_saya_r": {"EN": "Right Sheath", "ZH": "右手鞘"},
    "mhwi.weapon_data.no_weapon_sets": {"EN": "No weapon preset groups", "ZH": "无武器预设组"},
    "mhwi.weapon_data.no_weapons":     {"EN": "No weapons", "ZH": "无武器"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_export.no_armor_sets": {"EN": "No armor preset packs", "ZH": "无装备包"},
    "mhwi.batch_export.batch_export_desc": {"EN": "MHWI equipment batch export", "ZH": "MHWI 装备批量导出"},
    "mhwi.batch_export.select_weapon_first": {"EN": "Please select a weapon first", "ZH": "请先选择一件武器"},
    "mhwi.batch_export.weapon_not_found": {
        "EN": "Not found in weapon preset group: {id}", "ZH": "武器预设组中未找到: {id}"},
    "mhwi.batch_export.armor_not_found": {
        "EN": "Not found in armor pack: {id}", "ZH": "装备包中未找到: {id}"},
    "mhwi.batch_export.set_natives_root_desc": {
        "EN": "Select the MHWI Mod root folder (the parent folder of nativePC)",
        "ZH": "选择 MHWI Mod 根目录（nativePC 的上级文件夹）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_export_ui.no_matching_collections": {"EN": "No matching collections", "ZH": "无匹配集合"},
    "mhwi.batch_export_ui.toggle_blank_desc": {
        "EN": "Toggle whether this part uses a blank model", "ZH": "切换该部位是否使用空模"},
    "mhwi.batch_export_ui.toggle_ccl_desc": {
        "EN": "Toggle whether this part's CTC also exports CCL", "ZH": "切换该部位 CTC 是否顺带导出 CCL"},
    "mhwi.batch_export_ui.pick_armor_desc": {
        "EN": "Search and select an armor set (avoids overflowing the screen when there are too many)",
        "ZH": "搜索并选择装备（避免装备过多时下拉表溢出屏幕）"},
    "mhwi.batch_export_ui.pick_weapon_desc": {
        "EN": "Search and select a weapon (avoids overflowing the screen when there are too many)",
        "ZH": "搜索并选择武器（避免武器过多时下拉表溢出屏幕）"},
    "mhwi.batch_export_ui.dialog_desc": {
        "EN": "MHWI equipment batch export dialog", "ZH": "MHWI 装备批量导出对话框"},
    "mhwi.batch_export_ui.watermark_toggle_desc": {
        "EN": "Anti-reselling: adds a watermark effect that is almost only visible when changing equipment",
        "ZH": "防倒狗用，添加一个几乎只在换装时可见的水印"},
    "mhwi.batch_export_ui.watermark_dialog_body": {
        "EN": "This feature is intended only for freely distributed mods.\n"
              "When enabled, wearing this outfit will display:\n"
              "\"This is a free mod — refuse resellers, beware scams!\"\n"
              "If your mod has no free distribution channel,\n"
              "it's best not to use this feature!",
        "ZH": "此功能仅为免费公开MOD使用，\n"
              "选中后会在穿着此套服装时显示：\n"
              "「此为免费MOD，拒绝倒狗 谨防受骗！」\n"
              "如果你的mod不设任何免费获取渠道，\n"
              "最好不要使用此功能！"},
    "mhwi.batch_export_ui.preset_group": {"EN": "Preset Group", "ZH": "预设组"},
    "mhwi.batch_export_ui.weapon_type": {"EN": "Weapon Type", "ZH": "武器类型"},
    "mhwi.batch_export_ui.select_armor_hint": {
        "EN": "Please select an armor set to configure bindings", "ZH": "请选择装备以配置绑定"},
    "mhwi.batch_export_ui.armor_not_in_pack": {
        "EN": "This armor was not found in the pack", "ZH": "装备包中未找到该装备"},
    "mhwi.batch_export_ui.pick_weapon_placeholder": {"EN": "Select weapon...", "ZH": "选择武器..."},
    "mhwi.batch_export_ui.select_weapon_hint": {
        "EN": "Please select a weapon to configure bindings", "ZH": "请选择武器以配置绑定"},
    "mhwi.batch_export_ui.patch_model_warning": {
        "EN": "This weapon has a patch model — replacing it is not recommended!",
        "ZH": "该武器拥有贴片模型，不建议替换！"},
    "mhwi.batch_export_ui.blank_model": {"EN": "Blank", "ZH": "空模"},
    "mhwi.batch_export_ui.blank_model_evhl": {"EN": "Blank+evhl", "ZH": "空模+evhl"},
    "mhwi.batch_export_ui.physics_not_supported": {"EN": "Physics Not Supported", "ZH": "不支持物理"},
    "mhwi.batch_export_ui.standalone_face": {"EN": "Standalone Face", "ZH": "独立头部"},
    "mhwi.batch_export_ui.face_label": {"EN": "Face", "ZH": "头部"},
    "mhwi.batch_export_ui.standalone_hair": {"EN": "Standalone Hair", "ZH": "独立头发"},
    "mhwi.batch_export_ui.hair_label": {"EN": "Hair", "ZH": "头发"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_generator.refresh_desc": {"EN": "Refresh the material list", "ZH": "刷新材质列表"},
    "mhwi.mrl3_generator.process_desc": {
        "EN": "Generate MRL3 + textures from Blender materials", "ZH": "从 Blender 材质生成 MRL3 + 贴图"},
    "mhwi.mrl3_generator.set_mod_root_first": {"EN": "Please set the Mod Root folder first", "ZH": "请先设置 Mod Root 目录"},
    "mhwi.mrl3_generator.select_mod3_collection_first": {
        "EN": "Please select a MOD3 collection first", "ZH": "请先选择 MOD3 集合"},
    "mhwi.mrl3_generator.fill_base_path": {
        "EN": "Please fill in the Base Path (texture directory under nativePC/)",
        "ZH": "请填写 Base Path（nativePC/ 下的贴图目录）"},
    "mhwi.mrl3_generator.click_refresh_first": {
        "EN": "Please click Refresh to load materials first", "ZH": "请先点击 Refresh 加载材质"},
    "mhwi.mrl3_generator.cannot_load_tex_convert": {
        "EN": "Cannot load the MHW Model Editor texture conversion function; "
              "please confirm it's installed and enabled",
        "ZH": "无法加载 MHW Model Editor 贴图转换函数，请确认已安装并启用"},
    "mhwi.mrl3_generator.cannot_load_tex_utils": {
        "EN": "Cannot load the RE Mesh Editor texture tools; please confirm it's installed and enabled",
        "ZH": "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用"},
    "mhwi.mrl3_generator.process_done_with_fail": {
        "EN": "Done: {success} succeeded, {fail} failed", "ZH": "完成: 成功 {success}, 失败 {fail}"},
    "mhwi.mrl3_generator.process_done": {
        "EN": "Done: successfully generated MRL3 + textures for {n} material(s)",
        "ZH": "完成: 成功生成 {n} 个材质的 MRL3 + 贴图"},
    "mhwi.mrl3_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the MOD3 collection using the current material (stage 2: smart filter)",
        "ZH": "选中 MOD3 集合中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "mhwi.mrl3_generator.selected_matching_meshes": {
        "EN": "Selected {n} mesh(es) using '{name}' (including self, {total} total)",
        "ZH": "已选中 {n} 个使用 '{name}' 的网格（含自身共 {total} 个）"},

    "mhwi.mrl3_generator.use_toon_name": {"EN": "Toon Shading", "ZH": "使用三渲二"},
    "mhwi.mrl3_generator.skip_textures_name": {"EN": "Materials Only", "ZH": "仅生成材质"},
    "mhwi.mrl3_generator.ao_strength_name": {
        "EN": "AO Strength", "ZH": "AO 强度"},
    "mhwi.mrl3_generator.hide_snow_overlay_name": {
        "EN": "Hide Snow Overlay (fixes black legs in snow)", "ZH": "隐藏覆雪效果（解决雪地腿部发黑）"},
    "mhwi.mrl3_generator.flip_normal_g_name": {"EN": "Normal Map OpenGL -> DirectX", "ZH": "法线 OpenGL → DirectX"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_generator_ui.dialog_desc": {
        "EN": "MRL3 Generator - create MRL3 + textures from Blender mesh materials. "
              "Requires an existing MOD3 collection with a Principled BSDF wired up in the material",
        "ZH": "MRL3 Generator — 从 Blender 网格材质创建 MRL3 + 贴图。需要有现成的 MOD3 集合，并在材质里连好 Principled BSDF"},
    "mhwi.mrl3_generator_ui.auto_prefix": {"EN": "Auto", "ZH": "自动"},
    "mhwi.mrl3_generator_ui.preset_dir_not_found": {
        "EN": "MHW Model Editor MaterialPresets folder not found", "ZH": "未找到 MHW Model Editor MaterialPresets 目录"},
    "mhwi.mrl3_generator_ui.select_mod3_then_refresh": {
        "EN": "Select a MOD3 collection, then click Refresh", "ZH": "选择 MOD3 集合后点击刷新"},
    "mhwi.mrl3_generator_ui.node_tree_analysis": {
        "EN": "Node Tree Analysis (texture source strategy)", "ZH": "节点树分析 (贴图来源策略)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_tex_processor.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_tex_processor.select_mrl3_collection_first": {
        "EN": "Please select an MRL3 collection first", "ZH": "请先选择 MRL3 集合"},
    "mhwi.mrl3_tex_processor.materials_loaded": {
        "EN": "Loaded {n} material(s)", "ZH": "已加载 {n} 个材质"},
    "mhwi.mrl3_tex_processor.process_desc": {
        "EN": "Compose PBR texture channels, convert DDS to TEX, and update MRL3 binding paths",
        "ZH": "合成 PBR 贴图通道、转换 DDS→TEX 并更新 MRL3 绑定路径"},
    "mhwi.mrl3_tex_processor.process_done_with_fail": {
        "EN": "Done: generated {n}, failed {fail}, skipped {skip}",
        "ZH": "完成: 生成 {n}, 失败 {fail}, 跳过 {skip}"},
    "mhwi.mrl3_tex_processor.process_done": {
        "EN": "Done: generated {n}, skipped {skip}", "ZH": "完成: 生成 {n}, 跳过 {skip}"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_tex_processor_ui.dialog_desc": {
        "EN": "MHWI MRL3 + Tex Processor", "ZH": "MHWI MRL3 + Tex 处理器"},
    "mhwi.mrl3_tex_processor_ui.mrl3_collection_label": {"EN": "MRL3 Collection", "ZH": "MRL3 集合"},
    "mhwi.mrl3_tex_processor_ui.base_path_example": {
        "EN": "e.g. pl/f_equip/pl042_0500/helm/tex", "ZH": "例：pl/f_equip/pl042_0500/helm/tex"},
    "mhwi.mrl3_tex_processor_ui.select_mrl3_then_refresh": {
        "EN": "Select an MRL3 collection and click Refresh", "ZH": "选择 MRL3 集合并点击 Refresh"},
    "mhwi.mrl3_tex_processor_ui.use_direct_instead": {"EN": "Use DIRECT instead", "ZH": "请改用 DIRECT"},
    "mhwi.mrl3_tex_processor_ui.no_default": {"EN": "(no default)", "ZH": "(无默认)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), which are baked
    # into the datablock when the group is first built. Switching language
    # therefore does not retranslate an already-built group; it only affects
    # groups created afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.shader_defs.albedo": {
        "EN": "AlbedoMap — RGB base colour, A alpha",
        "ZH": "AlbedoMap — RGB 基础色, A 透明度"},
    "mhwi.shader_defs.normal": {
        "EN": "NormalMap — RG tangent normal (B unused, BC5)",
        "ZH": "NormalMap — RG 切线法线 (B 未使用, BC5)"},
    "mhwi.shader_defs.rmt": {
        "EN": "RMTMap — R roughness, G metallic, B translucency",
        "ZH": "RMTMap — R 粗糙度, G 金属度, B 透光"},
    "mhwi.shader_defs.colormask": {
        "EN": "ColorMaskMap — colour-change mask. Carried for export; not previewed",
        "ZH": "ColorMaskMap — 换色遮罩。仅用于导出, 不参与预览"},
    "mhwi.shader_defs.fx": {
        "EN": "FxMap — carried for export; not previewed",
        "ZH": "FxMap — 仅用于导出, 不参与预览"},
    "mhwi.shader_defs.furvelocity": {
        "EN": "FurVelocityMap — carried for export; not previewed",
        "ZH": "FurVelocityMap — 仅用于导出, 不参与预览"},

    "mhwi.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with AlbedoMap",
        "ZH": "基础色。与 AlbedoMap 相乘"},
    "mhwi.shader_defs.pbr_alpha": {
        "EN": "Alpha. Multiplied with AlbedoMap's alpha",
        "ZH": "透明度。与 AlbedoMap 的 Alpha 相乘"},
    "mhwi.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with RMTMap.R, as MRL3 does with fRoughness",
        "ZH": "粗糙度。与 RMTMap.R 相乘 (与 MRL3 的 fRoughness 一致)"},
    "mhwi.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to RMTMap.G",
        "ZH": "金属度。与 RMTMap.G 相加"},
    "mhwi.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour. MHWI has no AO slot, "
              "so this gets baked into AlbedoMap on export instead of its own texture",
        "ZH": "环境光遮蔽，正片叠底到基础色上。MHWI 没有独立的 AO 槽位，导出时会直接烤进 AlbedoMap，而不是单独出图"},
    "mhwi.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap",
        "ZH": "自发光颜色。与 EmissiveMap 相加"},
    "mhwi.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to NormalMap's",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量与 NormalMap 相加"},

    # ── MHWI_OT_SetMeshDisplayCondition ──────────────────────────────────
    "mhwi.operators.btn_set_display_condition": {"EN": "Set Mesh Display Condition", "ZH": "设置网格显示条件"},
    "mhwi.operators.set_display_condition_desc": {
        "EN": "Set when the selected meshes are visible in game. mod3 encodes this in the Group_<N> part of the object name, so this is a rename. Meshes not already in mod3 naming format are renamed first",
        "ZH": "设置选中网格在游戏里的显示时机。mod3 把它编码在物体名的 Group_<N> 里，所以本质是改名。名字不符合 mod3 格式的网格会先被重命名"},
    "mhwi.operators.disp_field_preset":   {"EN": "Preset",   "ZH": "预设"},
    "mhwi.operators.disp_field_group_id": {"EN": "Group ID", "ZH": "Group ID"},
    "mhwi.operators.disp_cond_0":  {"EN": "0 - Always visible",                      "ZH": "0 - 始终显示"},
    "mhwi.operators.disp_cond_1":  {"EN": "1 - Weapon drawn (weapons only)",         "ZH": "1 - 持刀显示（仅武器）"},
    "mhwi.operators.disp_cond_2":  {"EN": "2 - Weapon sheathed (weapons only)",      "ZH": "2 - 收刀显示（仅武器）"},
    "mhwi.operators.disp_cond_30": {"EN": "30 - Sheathed (needs transform plugin)",  "ZH": "30 - 收刀显示（需要变身插件）"},
    "mhwi.operators.disp_cond_31": {"EN": "31 - Drawn (needs transform plugin)",     "ZH": "31 - 拔刀显示（需要变身插件）"},
    "mhwi.operators.disp_cond_32": {"EN": "32 - Glaive no light / Long Sword no aura (needs transform plugin)",
                                     "ZH": "32 - 虫棍无灯 / 太刀无刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_33": {"EN": "33 - Glaive 1 light / Long Sword white (needs transform plugin)",
                                     "ZH": "33 - 虫棍一灯 / 太刀白刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_34": {"EN": "34 - Glaive 2 lights / Long Sword yellow (needs transform plugin)",
                                     "ZH": "34 - 虫棍二灯 / 太刀黄刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_35": {"EN": "35 - Glaive 3 lights / Long Sword red (needs transform plugin)",
                                     "ZH": "35 - 虫棍三灯 / 太刀红刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_custom": {"EN": "Other - enter an ID manually", "ZH": "其他 - 手动填写 ID"},
    "mhwi.operators.disp_no_mesh": {"EN": "No mesh objects selected", "ZH": "没有选中任何网格物体"},
    "mhwi.operators.disp_done": {"EN": "Set display condition {gid} on {n} mesh(es)",
                                  "ZH": "已将 {n} 个网格的显示条件设为 {gid}"},
    "mhwi.operators.disp_renamed_suffix": {"EN": "; {n} renamed to mod3 format first",
                                            "ZH": "；其中 {n} 个先重命名为 mod3 格式"},
    "mhwi.operators.add_facial_bones_desc": {
        "EN": "Graft the facial bones from the native character skeleton onto the current skeleton",
        "ZH": "将原生角色骨架的表情骨骼移植到当前骨架"},
    "mhwi.operators.facial_bones_warning": {
        "EN": "Using this feature will clear any existing facial bones!", "ZH": "使用该功能将清除原本存在的表情骨！"},
    "mhwi.operators.facial_target_armature": {"EN": "Skeleton", "ZH": "骨架"},
    "mhwi.operators.facial_no_reference": {
        "EN": "Select a reference character (add the file to assets/reference_skeletons/mhwi/)",
        "ZH": "请选择参考角色（添加文件到 assets/reference_skeletons/mhwi/）"},
    "mhwi.operators.facial_no_head_bone": {
        "EN": "Head bone {bone} not found on the target skeleton; facial bones attach to it",
        "ZH": "目标骨架中未找到头骨 {bone}，表情骨需要挂在它下面"},
    "mhwi.operators.facial_ref_import_failed": {
        "EN": "Failed to import reference skeleton: {name}", "ZH": "参考骨架导入失败: {name}"},
    "mhwi.operators.facial_ref_empty": {
        "EN": "No facial bones found under {bone} on the reference skeleton",
        "ZH": "参考骨架中 {bone} 之下没有表情骨"},
    "mhwi.operators.facial_ref_female": {"EN": "Female", "ZH": "女性"},
    "mhwi.operators.facial_ref_male": {"EN": "Male", "ZH": "男性"},
}
