"""Strings for games/re4/. Filled in incrementally as the module is migrated."""

STRINGS = {
    # ── operators.py ────────────────────────────────────────────────────────
    "re4.operators.no_native_skeleton": {
        "EN": "No skeleton available (add one to assets/native_skeletons/re4/)",
        "ZH": "无可用骨架 (添加至 assets/native_skeletons/re4/)",
    },
    "re4.operators.fakebone_oneclick_desc": {
        "EN": "(Fakehead Method) One-click generate a full set of End bones for the selected skeleton",
        "ZH": "(假头法) 一键为选中骨架生成全套 End 骨骼",
    },
    "re4.operators.native_skeleton_prop_label": {
        "EN": "Character Native Skeleton",
        "ZH": "角色原生骨架",
    },
    "re4.operators.select_target_armature_error": {
        "EN": "Select a target armature first",
        "ZH": "请先选中目标骨架",
    },
    "re4.operators.need_re_mesh_editor": {
        "EN": "RE Mesh Editor addon is required",
        "ZH": "需要 RE Mesh Editor 插件",
    },
    "re4.operators.select_native_skeleton_error": {
        "EN": "Select a native skeleton (add the file to assets/native_skeletons/re4/)",
        "ZH": "请选择原生骨架（添加文件到 assets/native_skeletons/re4/）",
    },
    "re4.operators.native_skeleton_not_found": {
        "EN": "Native skeleton not found: {path}",
        "ZH": "找不到原生骨架: {path}",
    },
    "re4.operators.fakebone_done": {
        "EN": "Fake bone generation complete",
        "ZH": "假骨骼生成完成",
    },
    "re4.operators.fakebone_failed": {
        "EN": "Fake bone generation failed: {error}",
        "ZH": "假骨骼生成失败: {error}",
    },
    "re4.operators.autocreate_chains_desc": {
        "EN": "One-click create RE Chain (RE4 default .chain format)",
        "ZH": "一键创建 RE Chain（RE4 默认 .chain 格式）。",
    },
    "re4.operators.settings_mode_separate_desc": {
        "EN": "Each chain gets its own independent Chain Settings",
        "ZH": "每条链拥有独立的 Chain Settings",
    },
    "re4.operators.settings_mode_guess_label": {
        "EN": "Guess Groups",
        "ZH": "猜测分组",
    },
    "re4.operators.settings_mode_guess_desc": {
        "EN": "Auto-classify by bone name; chains of the same type share one Chain Settings group "
              "with inferred physics parameters written in; unrecognized bones go into the first group",
        "ZH": "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组",
    },
    "re4.operators.auto_create_collection_label": {
        "EN": "Auto-Create Collection",
        "ZH": "自动创建集合",
    },
    "re4.operators.chain_format_v1_desc": {
        "EN": "Legacy format, used by RE4 and other earlier games",
        "ZH": "旧格式，用于 RE4 等早期游戏",
    },
    "re4.operators.chain_format_v2_desc": {
        "EN": "New format, used by MHWilds / RE9",
        "ZH": "新格式，用于 MHWilds / RE9",
    },
    "re4.operators.straighten_orientation_label": {
        "EN": "Straighten Bone Orientation",
        "ZH": "骨骼方向预处理",
    },
    "re4.operators.auto_refresh_label": {
        "EN": "Create Directly (auto-refresh bone colors)",
        "ZH": "直接创建（自动刷新骨骼颜色）",
    },
    "re4.operators.apply_angle_ramp_label": {
        "EN": "Auto-Apply Angle Ramp",
        "ZH": "自动应用角度坡度",
    },
    "re4.operators.no_markers_warning1": {
        "EN": "The current skeleton has no markers!",
        "ZH": "当前骨架没有任何标记！",
    },
    "re4.operators.no_markers_warning2": {
        "EN": "It's recommended to mark bones manually with the Physics Chain tool before using this.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。",
    },
    "re4.operators.create_chain_done": {
        "EN": "RE Chain creation complete",
        "ZH": "RE Chain 创建完成",
    },
    "re4.operators.add_facial_bones_desc": {
        "EN": "Graft facial bones from the native character skeleton onto the current skeleton; "
              "optionally use the Fakehead Method to adjust blink amplitude",
        "ZH": "将原生角色骨架的表情骨骼移植到当前骨架，可选择使用假头法调整眨眼幅度",
    },
    "re4.operators.target_armature_label": {
        "EN": "Skeleton",
        "ZH": "骨架",
    },
    "re4.operators.increase_blink_amplitude_label": {
        "EN": "Increase Blink Amplitude (for anime-style models)",
        "ZH": "增加眨眼幅度（二次元模型用）",
    },
    "re4.operators.facial_bones_warning": {
        "EN": "Using this will clear any existing facial bones!",
        "ZH": "使用该功能将清除原本存在的表情骨！",
    },
    "re4.operators.invalid_armature_warning": {
        "EN": "Select a valid armature",
        "ZH": "请选择一个有效的骨架",
    },
    "re4.operators.select_reference_character_error": {
        "EN": "Select a reference character (add the file to assets/reference_skeletons/re4/)",
        "ZH": "请选择参考角色（添加文件到 assets/reference_skeletons/re4/）",
    },
    "re4.operators.reference_import_failed": {
        "EN": "Failed to import reference skeleton: {name}",
        "ZH": "参考骨架导入失败: {name}",
    },
    "re4.operators.facial_root_not_found": {
        "EN": "Facial bone root not found on reference skeleton ({bone})",
        "ZH": "参考骨架中未找到表情骨根骨骼 ({bone})",
    },
    "re4.operators.blink_amplitude_added": {
        "EN": "; increased blink amplitude on {n} side(s)",
        "ZH": "，{n} 侧已增加眨眼幅度",
    },
    "re4.operators.need_re_fbxskel_importer": {
        "EN": "RE Mesh Editor's fbxskel importer is required (re_fbxskel.importfile)",
        "ZH": "需要 RE Mesh Editor 的 fbxskel 导入器 (re_fbxskel.importfile)",
    },
    "re4.operators.native_import_failed": {
        "EN": "Failed to import native skeleton: {path}",
        "ZH": "导入原生骨架失败: {path}",
    },

    # ── batch_export_ui.py ──────────────────────────────────────────────────
    "re4.batch_export_ui.preset_missing_native_skeleton": {
        "EN": "Preset has no native_skeleton configured",
        "ZH": "预设未配置 native_skeleton",
    },
    "re4.batch_export_ui.preset_missing_body_groups": {
        "EN": "Preset has no body_groups_for_fbxskel configured",
        "ZH": "预设未配置 body_groups_for_fbxskel",
    },

    # ── mdf_generator.py ────────────────────────────────────────────────────
    "re4.mdf_generator.use_toon_label": {
        "EN": "Toon Shading",
        "ZH": "使用三渲二",
    },
    "re4.mdf_generator.skip_textures_label": {
        "EN": "Materials Only",
        "ZH": "仅生成材质",
    },
    "re4.mdf_generator.flip_normal_g_label": {
        "EN": "Normal Map: OpenGL -> DirectX",
        "ZH": "法线 OpenGL → DirectX",
    },
    "re4.mdf_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the Mesh Collection using the current material "
              "(stage 2: smart filtering)",
        "ZH": "选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）",
    },
    "re4.mdf_generator.select_mesh_collection_first": {
        "EN": "Select a Mesh Collection first",
        "ZH": "请先选择 Mesh Collection",
    },
    "re4.mdf_generator.active_object_no_material": {
        "EN": "Active object has no material",
        "ZH": "激活物体没有材质",
    },
    "re4.mdf_generator.select_same_material_log": {
        "EN": "Smart filter: material '{mat}' -> {n} mesh(es): {names}",
        "ZH": "智能筛选: 材质 '{mat}' → {n} 个网格: {names}",
    },
    "re4.mdf_generator.select_same_material_done": {
        "EN": "Selected {n} mesh(es) using '{mat}' (including itself, {total} total)",
        "ZH": "已选中 {n} 个使用 '{mat}' 的网格（含自身共 {total} 个）",
    },

    # ── mdf_generator_ui.py ─────────────────────────────────────────────────
    "re4.mdf_generator_ui.dialog_desc": {
        "EN": "RE4 MDF2 Generator - create MDF2 + textures from Blender mesh materials. "
              "Requires an existing mesh collection with a Principled BSDF wired up in each material",
        "ZH": "RE4 MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，"
              "并在材质里连好 Principled BSDF",
    },
    "re4.mdf_generator_ui.auto_mdf_name": {
        "EN": "    Auto: {name}",
        "ZH": "    自动: {name}",
    },
    "re4.mdf_generator_ui.preset_dir_not_found": {
        "EN": "RE Mesh Editor RE4 preset folder not found",
        "ZH": "未找到 RE Mesh Editor RE4 预设目录",
    },
    "re4.mdf_generator_ui.select_mesh_collection_hint": {
        "EN": "Select a mesh collection then click Refresh",
        "ZH": "选择网格集合后点击刷新",
    },
    "re4.mdf_generator_ui.node_tree_analysis": {
        "EN": "Node Tree Analysis (texture source strategy)",
        "ZH": "节点树分析 (贴图来源策略)",
    },

    # ── batch_export.py ─────────────────────────────────────────────────────
    "re4.batch_export.body_arm_no_native_preset": {
        "EN": "Body Armature: preset has no native_skeleton configured, skipping FBXSKEL",
        "ZH": "使用身体骨架: 预设未配置 native_skeleton，跳过 FBXSKEL",
    },
    "re4.batch_export.body_arm_native_missing": {
        "EN": "Body Armature: native skeleton file not found: {file}",
        "ZH": "使用身体骨架: 找不到原生骨架文件 {file}",
    },
    "re4.batch_export.native_import_failed": {
        "EN": "Failed to import native skeleton: {path}",
        "ZH": "导入原生骨架失败: {path}",
    },
    "re4.batch_export.label_body_arm_fakebone": {
        "EN": "FBXSKEL (Body Armature + Fakehead Method)",
        "ZH": "FBXSKEL (身体骨架+假头法)",
    },
    "re4.batch_export.label_body_arm": {
        "EN": "FBXSKEL (Body Armature)",
        "ZH": "FBXSKEL (身体骨架)",
    },
    "re4.batch_export.fakebone_no_native_selected": {
        "EN": "Fakehead Method: no native skeleton selected, skipping FBXSKEL",
        "ZH": "假头法: 未选择原生骨架，跳过 FBXSKEL",
    },
    "re4.batch_export.fakebone_native_missing": {
        "EN": "Fakehead Method: native skeleton file not found: {file}",
        "ZH": "假头法: 找不到原生骨架文件 {file}",
    },
    "re4.batch_export.fakebone_arm_not_found": {
        "EN": "Fakehead Method: armature object '{arm}' does not exist",
        "ZH": "假头法: 骨架对象 '{arm}' 不存在",
    },
    "re4.batch_export.fakebone_duplicate_failed": {
        "EN": "Fakehead Method: duplicate failed, could not get the copied object",
        "ZH": "假头法: duplicate 失败，无法获取副本对象",
    },
    "re4.batch_export.label_fakebone": {
        "EN": "FBXSKEL (Fakehead Method)",
        "ZH": "FBXSKEL (假头法)",
    },
    "re4.batch_export.set_natives_root_desc": {
        "EN": "Select the RE4 mod root directory (the parent of natives). If the selected folder "
              "is itself named natives, its parent is used automatically",
        "ZH": "选择 RE4 Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级",
    },

    # ── mdf_tex_processor_ui.py ─────────────────────────────────────────────
    "re4.mdf_tex_processor_ui.dialog_desc": {
        "EN": "MDF2 Processor - process textures on top of an existing MDF2 material. "
              "Requires an existing, properly named MDF2 collection",
        "ZH": "MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合",
    },

    # ══════════════════════════════════════════════════════════════════════
    # games/re4/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), which are baked
    # into the datablock when the group is first built. Switching language
    # therefore does not retranslate an already-built group; it only affects
    # groups created afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "re4.shader_defs.atocm": {
        "EN": "AlphaTranslucentOcclusionCavityMap — R alpha (real opacity), B AO",
        "ZH": "AlphaTranslucentOcclusionCavityMap — R 透明度 (真正的不透明度), B 环境光遮蔽"},
    "re4.shader_defs.nrcm": {
        "EN": "NormalRoughnessCavityMap — R roughness, G/A hemi-octahedral normal, "
              "B a constant (RE4 writes no Cavity data)",
        "ZH": "NormalRoughnessCavityMap — R 粗糙度, G/A 半八面体编码法线, "
              "B 为常量 (RE4 不写入 Cavity 数据)"},

    # ── Secondary slots: no composition recipe, carried through untouched.
    "re4.shader_defs.detailmap": {
        "EN": "DetailMap — a detail-layer texture; carried for export, not used by "
              "the preview",
        "ZH": "DetailMap — 细节层贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.maskmap": {
        "EN": "MaskMap — masks in the detail layer; carried for export, not used "
              "by the preview",
        "ZH": "MaskMap — 用来遮罩混合细节层；仅为导出保留，预览不使用"},
    "re4.shader_defs.imperfectdetail_map": {
        "EN": "ImperfectDetail_Map — skin/surface imperfection detail texture; "
              "carried for export, not used by the preview",
        "ZH": "ImperfectDetail_Map — 皮肤/表面瑕疵细节贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.wrinklenormalmap": {
        "EN": "WrinkleNormalMap — skin wrinkle normal detail; carried for export, "
              "not used by the preview",
        "ZH": "WrinkleNormalMap — 皮肤皱纹法线细节；仅为导出保留，预览不使用"},
    "re4.shader_defs.wind_maskmap": {
        "EN": "Wind_MaskMap — wind/cloth simulation mask; carried for export, not "
              "used by the preview",
        "ZH": "Wind_MaskMap — 风力/布料模拟遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.noise3d": {
        "EN": "Noise3D — generic 3D noise texture used by several effects; "
              "carried for export, not used by the preview",
        "ZH": "Noise3D — 多个效果共用的通用 3D 噪声贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.recordsys_fix": {
        "EN": "RecordSys_Fix — damage-record system fixed layer; carried for "
              "export, not used by the preview",
        "ZH": "RecordSys_Fix — 损伤记录系统固定层；仅为导出保留，预览不使用"},
    "re4.shader_defs.recordsys_protect": {
        "EN": "RecordSys_Protect — damage-record system protected-area mask; "
              "carried for export, not used by the preview",
        "ZH": "RecordSys_Protect — 损伤记录系统保护区域遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.bloodmask": {
        "EN": "BloodMask — blood decal mask; carried for export, not used by "
              "the preview",
        "ZH": "BloodMask — 血渍贴花遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.bloodflow_rtt": {
        "EN": "BloodFlow_rtt — blood-flow simulation render target; carried for "
              "export, not used by the preview",
        "ZH": "BloodFlow_rtt — 血流模拟渲染目标；仅为导出保留，预览不使用"},
    "re4.shader_defs.bloodflow_uv": {
        "EN": "BloodFlow_uv — blood-flow simulation UV map; carried for export, "
              "not used by the preview",
        "ZH": "BloodFlow_uv — 血流模拟 UV 贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.injury_map_alba": {
        "EN": "Injury_Map_ALBA — wound decal colour texture; carried for export, "
              "not used by the preview",
        "ZH": "Injury_Map_ALBA — 伤口贴花颜色贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.injury_map_nrm": {
        "EN": "Injury_Map_NRM — wound decal normal texture; carried for export, "
              "not used by the preview",
        "ZH": "Injury_Map_NRM — 伤口贴花法线贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.stain_cloth_map_msk4": {
        "EN": "Stain_Cloth_Map_MSK4 — cloth stain mask; carried for export, not "
              "used by the preview",
        "ZH": "Stain_Cloth_Map_MSK4 — 布料污渍遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.clothdamagemaskmap": {
        "EN": "clothDamagemaskMap — cloth damage mask; carried for export, not "
              "used by the preview",
        "ZH": "clothDamagemaskMap — 布料损伤遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.dirtmask_atex": {
        "EN": "DirtMask_Atex — dirt accumulation mask; carried for export, not "
              "used by the preview",
        "ZH": "DirtMask_Atex — 污垢积累遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.rec_rain_waterriple": {
        "EN": "Rec_Rain_WaterRiple — rain ripple normal texture; carried for "
              "export, not used by the preview",
        "ZH": "Rec_Rain_WaterRiple — 雨水波纹法线贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.rec_rain_wetmask": {
        "EN": "Rec_Rain_WetMask — rain wetness mask; carried for export, not "
              "used by the preview",
        "ZH": "Rec_Rain_WetMask — 雨水湿润遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.secondaryalbedomap": {
        "EN": "SecondaryAlbedoMap — hair's secondary colour blend texture; "
              "carried for export, not used by the preview",
        "ZH": "SecondaryAlbedoMap — 毛发的第二颜色混合贴图；仅为导出保留，预览不使用"},
    "re4.shader_defs.fakespheremap": {
        "EN": "FakeSphereMap — a fake specular-highlight sphere map (used by "
              "the Emissive family's eye-highlight trick); carried for export, "
              "not used by the preview",
        "ZH": "FakeSphereMap — 假高光球面贴图 (自发光材质做眼睛假高光用)；"
              "仅为导出保留，预览不使用"},
    "re4.shader_defs.rainstreakmaskmap": {
        "EN": "RainStreakMaskMap — rain streak mask; carried for export, not "
              "used by the preview",
        "ZH": "RainStreakMaskMap — 雨痕遮罩；仅为导出保留，预览不使用"},
    "re4.shader_defs.raindropsmaskmap": {
        "EN": "RainDropsMaskMap — rain droplet mask; carried for export, not "
              "used by the preview",
        "ZH": "RainDropsMaskMap — 雨滴遮罩；仅为导出保留，预览不使用"},

    "re4.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with BaseDielectricMap/BaseShiftMap",
        "ZH": "基础色。与 BaseDielectricMap/BaseShiftMap 相乘"},
    "re4.shader_defs.pbr_alpha": {
        "EN": "Alpha. Multiplied with the spec's own opacity slot -- "
              "AlphaTranslucentOcclusionCavityMap.R (Standard/Hair) or "
              "AlphaTranslucentOcclusionSSSMap.R (Emissive), both real opacity",
        "ZH": "透明度。与本 spec 自己的不透明度槽位相乘——标准/毛发是 "
              "AlphaTranslucentOcclusionCavityMap.R，自发光是 "
              "AlphaTranslucentOcclusionSSSMap.R，两者都是真正的不透明度"},
    "re4.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with NormalRoughnessMap.A (Standard/Hair) "
              "or NormalRoughnessCavityMap.R (Emissive)",
        "ZH": "粗糙度。与 NormalRoughnessMap.A (标准/毛发) 或 "
              "NormalRoughnessCavityMap.R (自发光) 相乘"},
    "re4.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to BaseDielectricMap's inverted alpha (1 - alpha). "
              "No effect on the Hair spec, which has no metallic slot at all",
        "ZH": "金属度。与 BaseDielectricMap 反转后的 Alpha (1 - alpha) 相加。"
              "对毛发 spec 无效——毛发没有金属度槽位"},
    "re4.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour. Genuinely exports: "
              "AlphaTranslucentOcclusionCavityMap.B (Standard/Hair) or both "
              "OcclusionMap and AlphaTranslucentOcclusionSSSMap.B (Emissive) carry it",
        "ZH": "环境光遮蔽，正片叠底到基础色上。可以真正导出——标准/毛发由 "
              "AlphaTranslucentOcclusionCavityMap.B 携带，自发光则由 OcclusionMap 和 "
              "AlphaTranslucentOcclusionSSSMap.B 共同携带"},
    "re4.shader_defs.pbr_cavity": {
        "EN": "Cavity, multiplied into the same AO chain. Genuinely exports: "
              "AlphaTranslucentOcclusionCavityMap.A (Standard/Hair) or "
              "NormalRoughnessCavityMap.B (Emissive) carry it",
        "ZH": "腔体遮蔽 (Cavity)，并入同一条 AO 正片叠底链。可以真正导出——标准/毛发由 "
              "AlphaTranslucentOcclusionCavityMap.A 携带，自发光由 "
              "NormalRoughnessCavityMap.B 携带"},
    "re4.shader_defs.pbr_translucency": {
        "EN": "Translucency. Genuinely carried by "
              "AlphaTranslucentOcclusionCavityMap.G (Standard/Hair) or "
              "AlphaTranslucentOcclusionSSSMap.G (Emissive), but Principled has "
              "no matching input (not the same thing as Subsurface Scattering) "
              "-- this value round-trips to the exporter, the preview does not "
              "show it",
        "ZH": "半透 (Translucency)。标准/毛发由 "
              "AlphaTranslucentOcclusionCavityMap.G 真实携带，自发光由 "
              "AlphaTranslucentOcclusionSSSMap.G 真实携带，但 Principled 没有对应"
              "输入 (不等同于次表面散射)——此值仅在导出时生效，预览不会显示"},
    "re4.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap on the Emissive spec; "
              "Standard/Hair have no emissive slot, so this panel value is the "
              "only source there",
        "ZH": "自发光颜色。在自发光 spec 上会与 EmissiveMap 相加；标准/毛发没有"
              "自发光槽位，此项是唯一来源"},
    "re4.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to the decoded "
              "slot normal (NormalRoughnessMap or NormalRoughnessCavityMap, "
              "depending on the spec)",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量会和槽位解码出的法线相加 (NormalRoughnessMap 或 "
              "NormalRoughnessCavityMap，取决于所用的 spec)"},
    "re4.shader_defs.recordsys_rtt": {
        "EN": "RecordSys_rtt — damage-record system render target; carried for "
              "export, not used by the preview",
        "ZH": "RecordSys_rtt — 损伤记录系统渲染目标；仅为导出保留，预览不使用"},
    "re4.shader_defs.rimlight_fakenormalmap": {
        "EN": "RimLight_FakeNormalMap — a substitute normal for rim-light "
              "calculation; carried for export, not used by the preview",
        "ZH": "RimLight_FakeNormalMap — 用于边缘光计算的替代法线；仅为导出保留，预览不使用"},

    # ══════════════════════════════════════════════════════════════════════
    # games/re4/mdf_material_convert.py
    # ══════════════════════════════════════════════════════════════════════

    "re4.mdf_material_convert.dialog_desc": {
        "EN": "Convert the selected MDF material object(s) to a different RE Mesh Editor preset material, "
              "migrating custom texture paths (and optionally params)",
        "ZH": "将选中的 MDF 材质物体转换为另一个 RE Mesh Editor 预设材质，迁移自定义贴图路径 (可选连带参数)"},
}
