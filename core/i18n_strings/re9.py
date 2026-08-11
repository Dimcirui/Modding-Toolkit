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

    # ══════════════════════════════════════════════════════════════════════
    # games/re9/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), baked into the
    # datablock when the group is first built. Switching language does not
    # retranslate an already-built group; it only affects groups created
    # afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "re9.shader_defs.panel_pbr": {"EN": "PBR Inputs", "ZH": "PBR 输入"},
    "re9.shader_defs.panel_slots_standard": {
        "EN": "Game Slots (packed) — Standard", "ZH": "游戏槽位 (打包) — 标准"},
    "re9.shader_defs.panel_slots_skin": {
        "EN": "Game Slots (packed) — Skin", "ZH": "游戏槽位 (打包) — 皮肤"},
    "re9.shader_defs.panel_slots_hair": {
        "EN": "Game Slots (packed) — Hair", "ZH": "游戏槽位 (打包) — 毛发"},
    "re9.shader_defs.panel_slots_emissive": {
        "EN": "Game Slots (packed) — Emissive", "ZH": "游戏槽位 (打包) — 自发光"},

    "re9.shader_defs.albd": {
        "EN": "BaseDielectricMap — RGB base colour, A inverted metallic (not opacity)",
        "ZH": "BaseDielectricMap — RGB 基础色, A 反转金属度 (不是透明度)"},
    "re9.shader_defs.nrm": {
        "EN": "NormalRoughnessMap — R/G plain tangent-space normal, B unused, A roughness",
        "ZH": "NormalRoughnessMap — R/G 普通切线空间法线, B 未使用, A 粗糙度"},
    "re9.shader_defs.baseshift": {
        "EN": "BaseShiftMap — RGB base colour. Hair's equivalent of "
              "BaseDielectricMap (hair has no metallic-alpha convention)",
        "ZH": "BaseShiftMap — RGB 基础色。是毛发用来代替 BaseDielectricMap 的槽位"
              "（毛发没有反转 Alpha 表示金属度的约定）"},
    "re9.shader_defs.acot": {
        "EN": "AlphaCavityOcclusionTranslucentMap — R alpha (real opacity), B AO",
        "ZH": "AlphaCavityOcclusionTranslucentMap — R 透明度 (真正的不透明度), B 环境光遮蔽"},
    "re9.shader_defs.ssscot": {
        "EN": "SSSCavityOcclusionTranslucentMap — R is a fixed constant (no "
              "opacity data), B AO",
        "ZH": "SSSCavityOcclusionTranslucentMap — R 为固定常量 (无不透明度数据), "
              "B 环境光遮蔽"},
    "re9.shader_defs.nrcm": {
        "EN": "NormalRoughnessCavityMap — R roughness, G/A hemi-octahedral normal, "
              "B a constant (RE9 writes no Cavity data)",
        "ZH": "NormalRoughnessCavityMap — R 粗糙度, G/A 半八面体编码法线, "
              "B 为常量 (RE9 不写入 Cavity 数据)"},
    "re9.shader_defs.atosss": {
        "EN": "AlphaTranslucentOcclusionSSSMap — R alpha (real opacity), B AO",
        "ZH": "AlphaTranslucentOcclusionSSSMap — R 透明度 (真正的不透明度), B 环境光遮蔽"},
    "re9.shader_defs.occ": {
        "EN": "OcclusionMap — a second, plain-greyscale AO source (R=G=B)",
        "ZH": "OcclusionMap — 第二个环境光遮蔽来源 (纯灰度, R=G=B)"},
    "re9.shader_defs.emissive": {
        "EN": "EmissiveMap — emissive colour",
        "ZH": "EmissiveMap — 自发光颜色"},

    # ── Secondary slots: no composition recipe, carried through untouched.
    "re9.shader_defs.wetmap": {
        "EN": "WetMap — rain/sweat wetness mask; carried for export, not used "
              "by the preview",
        "ZH": "WetMap — 雨水/汗水湿润遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.recordsys_fixmask": {
        "EN": "RecordSys_FixMask — damage-record system fixed-area mask; "
              "carried for export, not used by the preview",
        "ZH": "RecordSys_FixMask — 损伤记录系统固定区域遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.recordsys_protectmask": {
        "EN": "RecordSys_ProtectMask — damage-record system protected-area "
              "mask; carried for export, not used by the preview",
        "ZH": "RecordSys_ProtectMask — 损伤记录系统保护区域遮罩；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.recordsys_addmask": {
        "EN": "RecordSys_AddMask — damage-record system additive-area mask; "
              "carried for export, not used by the preview",
        "ZH": "RecordSys_AddMask — 损伤记录系统叠加区域遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.fixbloodmask": {
        "EN": "FixBloodMask — fixed blood decal mask; carried for export, not "
              "used by the preview",
        "ZH": "FixBloodMask — 固定血渍贴花遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.bloodshed_rtt": {
        "EN": "BloodShed_rtt — blood-shedding simulation render target; "
              "carried for export, not used by the preview",
        "ZH": "BloodShed_rtt — 流血模拟渲染目标；仅为导出保留，预览不使用"},
    "re9.shader_defs.lightdamage_albd": {
        "EN": "LightDamage_ALBD — light-damage decal colour texture; carried "
              "for export, not used by the preview",
        "ZH": "LightDamage_ALBD — 轻度损伤贴花颜色贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.burntmap_albm": {
        "EN": "BurntMap_ALBM — burn decal colour texture; carried for export, "
              "not used by the preview",
        "ZH": "BurntMap_ALBM — 烧伤贴花颜色贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.lightdamage_nrra": {
        "EN": "LightDamage_NRRA — light-damage decal normal/roughness texture; "
              "carried for export, not used by the preview",
        "ZH": "LightDamage_NRRA — 轻度损伤贴花法线/粗糙度贴图；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.burntmap_nrmr": {
        "EN": "BurntMap_NRMR — burn decal normal/roughness texture; carried "
              "for export, not used by the preview",
        "ZH": "BurntMap_NRMR — 烧伤贴花法线/粗糙度贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.heavydamage_albd": {
        "EN": "HeavyDamage_ALBD — heavy-damage decal colour texture; carried "
              "for export, not used by the preview",
        "ZH": "HeavyDamage_ALBD — 重度损伤贴花颜色贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.heavydamage_nrra": {
        "EN": "HeavyDamage_NRRA — heavy-damage decal normal/roughness texture; "
              "carried for export, not used by the preview",
        "ZH": "HeavyDamage_NRRA — 重度损伤贴花法线/粗糙度贴图；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.blood_nrra": {
        "EN": "Blood_NRRA — blood decal normal/roughness texture; carried for "
              "export, not used by the preview",
        "ZH": "Blood_NRRA — 血渍贴花法线/粗糙度贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.recordsys_rtt": {
        "EN": "RecordSys_rtt — damage-record system render target; carried "
              "for export, not used by the preview",
        "ZH": "RecordSys_rtt — 损伤记录系统渲染目标；仅为导出保留，预览不使用"},
    "re9.shader_defs.raindrop_stopdrops": {
        "EN": "RainDrop_StopDrops — rain droplet stop-motion normal texture; "
              "carried for export, not used by the preview",
        "ZH": "RainDrop_StopDrops — 雨滴静止法线贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.raindrop_flickdrops": {
        "EN": "RainDrop_FlickDrops — rain droplet flick-motion normal texture; "
              "carried for export, not used by the preview",
        "ZH": "RainDrop_FlickDrops — 雨滴滑落法线贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.raindrop_dropmask": {
        "EN": "RainDrop_DropMask — rain droplet placement mask; carried for "
              "export, not used by the preview",
        "ZH": "RainDrop_DropMask — 雨滴分布遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.detailmask": {
        "EN": "DetailMask — masks in the detail layer; carried for export, "
              "not used by the preview",
        "ZH": "DetailMask — 用来遮罩混合细节层；仅为导出保留，预览不使用"},
    "re9.shader_defs.detailalbedomap": {
        "EN": "DetailAlbedoMap — a detail-layer colour texture; carried for "
              "export, not used by the preview",
        "ZH": "DetailAlbedoMap — 细节层颜色贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.detailmap": {
        "EN": "DetailMap — a detail-layer normal/roughness texture; carried "
              "for export, not used by the preview",
        "ZH": "DetailMap — 细节层法线/粗糙度贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.imperfectdetail_map": {
        "EN": "ImperfectDetail_Map — skin/surface imperfection detail "
              "texture; carried for export, not used by the preview",
        "ZH": "ImperfectDetail_Map — 表面瑕疵细节贴图；仅为导出保留，预览不使用"},
    "re9.shader_defs.wrinklemap": {
        "EN": "WrinkleMap — cloth wrinkle normal detail; carried for export, "
              "not used by the preview",
        "ZH": "WrinkleMap — 布料皱纹法线细节；仅为导出保留，预览不使用"},
    "re9.shader_defs.sweatmap": {
        "EN": "SweatMap — skin sweat mask; carried for export, not used by "
              "the preview",
        "ZH": "SweatMap — 皮肤汗水遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.secondarybasecolormap_maskmap": {
        "EN": "SecondaryBaseColorMap_MaskMap — masks in the secondary hair "
              "colour; carried for export, not used by the preview",
        "ZH": "SecondaryBaseColorMap_MaskMap — 用来遮罩混合第二毛发颜色；"
              "仅为导出保留，预览不使用"},
    "re9.shader_defs.secondarybasecolormap": {
        "EN": "SecondaryBaseColorMap — hair's secondary colour blend texture; "
              "carried for export, not used by the preview",
        "ZH": "SecondaryBaseColorMap — 毛发的第二颜色混合贴图；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.specular_flowmap": {
        "EN": "Specular_FlowMap — hair anisotropic specular flow map; carried "
              "for export, not used by the preview",
        "ZH": "Specular_FlowMap — 毛发各向异性高光流向贴图；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.rimlight_fakenormalmap": {
        "EN": "RimLight_FakeNormalMap — a substitute normal for rim-light "
              "calculation; carried for export, not used by the preview",
        "ZH": "RimLight_FakeNormalMap — 用于边缘光计算的替代法线；仅为导出保留，"
              "预览不使用"},
    "re9.shader_defs.dirtmaskmap": {
        "EN": "DirtMaskMap — dirt accumulation mask; carried for export, not "
              "used by the preview",
        "ZH": "DirtMaskMap — 污垢积累遮罩；仅为导出保留，预览不使用"},
    "re9.shader_defs.dirtwearmap": {
        "EN": "DirtWearMap — dirt wear-pattern texture; carried for export, "
              "not used by the preview",
        "ZH": "DirtWearMap — 污垢磨损纹理；仅为导出保留，预览不使用"},

    "re9.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with BaseDielectricMap/BaseShiftMap",
        "ZH": "基础色。与 BaseDielectricMap/BaseShiftMap 相乘"},
    "re9.shader_defs.pbr_alpha": {
        "EN": "Alpha. Multiplied with the spec's own opacity slot -- "
              "AlphaCavityOcclusionTranslucentMap.R (Standard/Hair) or "
              "AlphaTranslucentOcclusionSSSMap.R (Emissive). Skin has no "
              "opacity slot at all, so this panel value is its only source",
        "ZH": "透明度。与本 spec 自己的不透明度槽位相乘——标准/毛发是 "
              "AlphaCavityOcclusionTranslucentMap.R，自发光是 "
              "AlphaTranslucentOcclusionSSSMap.R。皮肤没有不透明度槽位，"
              "此项是唯一来源"},
    "re9.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with NormalRoughnessMap.A (Standard/"
              "Skin/Hair) or NormalRoughnessCavityMap.R (Emissive)",
        "ZH": "粗糙度。与 NormalRoughnessMap.A (标准/皮肤/毛发) 或 "
              "NormalRoughnessCavityMap.R (自发光) 相乘"},
    "re9.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to BaseDielectricMap's inverted alpha (1 - alpha). "
              "No effect on the Hair spec, which has no metallic slot at all",
        "ZH": "金属度。与 BaseDielectricMap 反转后的 Alpha (1 - alpha) 相加。"
              "对毛发 spec 无效——毛发没有金属度槽位"},
    "re9.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour. Genuinely "
              "exports: AlphaCavityOcclusionTranslucentMap.B/"
              "SSSCavityOcclusionTranslucentMap.B carries it, or both "
              "OcclusionMap and AlphaTranslucentOcclusionSSSMap.B on Emissive",
        "ZH": "环境光遮蔽，正片叠底到基础色上。可以真正导出——由 "
              "AlphaCavityOcclusionTranslucentMap.B/"
              "SSSCavityOcclusionTranslucentMap.B 携带，自发光则由 "
              "OcclusionMap 和 AlphaTranslucentOcclusionSSSMap.B 共同携带"},
    "re9.shader_defs.pbr_ao_strength": {
        "EN": "AO strength: 0 = off, 1 = the full map",
        "ZH": "AO 强度：0 为关闭，1 为完整应用"},
    "re9.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap on the Emissive spec; "
              "Standard/Skin/Hair have no emissive slot, so this panel value "
              "is the only source there",
        "ZH": "自发光颜色。在自发光 spec 上会与 EmissiveMap 相加；标准/皮肤/"
              "毛发没有自发光槽位，此项是唯一来源"},
    "re9.shader_defs.pbr_emission_strength": {
        "EN": "Emission strength",
        "ZH": "自发光强度"},
    "re9.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to the decoded "
              "slot normal (NormalRoughnessMap or NormalRoughnessCavityMap, "
              "depending on the spec)",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量会和槽位解码出的法线相加 (NormalRoughnessMap 或 "
              "NormalRoughnessCavityMap，取决于所用的 spec)"},
}
