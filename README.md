# Modding Toolkit (Blender Addon)

[中文说明见下方](#中文说明)

A comprehensive Blender toolkit for game modding. Supports Capcom's games and more.

**Supported Blender Versions**: 4.x (recommended 4.3+)

---

## Supported Games
* Monster Hunter World: Iceborne
* Monster Hunter Rise: Sunbreak
* Monster Hunter Wilds
* Resident Evil 4: Remake
* Resident Evil: Requiem
* Street Fighter 6
* Devil May Cry 5
* Helldivers 2

## Core Features

### 1. Universal Skeleton Converter
Convert any source model to any target game format using customizable JSON presets.

* **X → Y Architecture**: Define your source (X) and target (Y) freely.
    * **Source (X)**: VRChat, MMD, Endfield, or any custom ripped model.
    * **Target (Y)**: MHWI, MHW: Wilds, RE4 Remake, Street Fighter 6, etc.
* **Bone Snap** [X+Y, dual armature]: Align your model's skeleton to the target game's skeleton.
* **Direct Convert** [X+Y]: Rename vertex groups directly on the mesh.
* **Fuzzy Bone Matching**: Normalizes separator characters (`_`, `.`, space) when matching bone names, so preset-driven operations work regardless of naming style variations in the source.
* **Experimental - Physics Bone Graft** [X+Y, dual armature]: Transplants physical bones from the source skeleton to the target skeleton, handles directional twists, automatically generates end bones, and colors chain-head bones for easy identification.
* **Experimental Feature - Physics Weight Downgrade** [X]: Merges physics weights onto the nearest body bone for scenarios where physics are unnecessary or unavailable.

### 2. Pose Convert
A standalone pose transformation system, independent of the skeleton converter.

* **Direction Calc**: Simple tool to rotate upper arms to horizontal (A-pose → T-pose for basic cases).
* **RE Engine Matrix Zero**: Reset limb bone rotation matrices for all RE Engine games (MH Wilds, SF6, RE4, etc.).
* **Pose Transform Recorder**: Record the relative rotation transform between two poses of the same skeleton type, then apply forward (A→B) or inverse (B→A) to any skeleton of that type.
    * Record once, use forever — no need to keep reference armatures in the scene.
    * JSON-based storage in `assets/pose_presets/`, preserved across addon updates.

### 3. Visual Preset Editor
A built-in GUI editor to create custom bone mappings without writing code.
* Pick & click bone assignment from the 3D viewport.
* Batch auxiliary bone adding.
* Smart mirror: auto-generate Right-side mappings from the Left side.
* Grouped category dropdown for large preset libraries.

### 4. General Utilities
* Roll Zero, Add Tail Bone, Mirror X.
* **Bone Chain Simplification**: Reduce chain density with configurable keep-ratio; includes a Merge To Active action that merges selected bones into the active bone.
* **General Align Tools**: Align any armature's bones to a reference armature by name.
    * **Full mode** copies head, tail, and roll; **Position-only mode** moves the head while preserving the original bone direction.
* **Three-state Bone Visibility Toggle**: Cycle bones between visible / hidden / hidden+unselectable.

### 5. Game-Specific Modules

#### MHWI (Iceborne)
* Non-physics bone alignment tool.

#### MHWilds (Monster Hunter Wilds)
* Endfield face vertex group rename (Endfield → MHWilds format).
* Face weight simplification (merge detailed facial bones to main control bones).
* **Armor Batch Exporter**: Export mesh / MDF2 / Chain2 / CLSP files for all 5 armor parts (arm, body, helmet, leg, waist) in one click.
    * Armor sets defined in JSON packs under `assets/mhws_armor_sets/`.
    * 4 armor variants (male-male, male-female, female-male, female-female) with independent armor IDs and base paths.
    * `parts_mask` support in JSON to skip non-existent parts without manual binding.
    * Collection bindings shared across variants — configure once, export all.
* **MDF2 + Tex Semi-Auto Processor**: Batch-update texture binding paths in an MDF2 collection and convert source images to game-ready `.tex` files in a single operation.
    * Per-material PBR inputs (Albedo / Alpha / Normal / Roughness / Metallic / AO / Emissive).
    * Per-slot modes: **COMPOSE** (channel-pack from PBR inputs), **DIRECT** (pick any image / DDS / TEX), **DEFAULT** (write game null-tex path), **SKIP** (leave unchanged).
    * Channel selector (R/G/B/A) + invert toggle for single-channel inputs (e.g. smoothness→roughness, dielectric→metallic).
    * **GL→DX normal flip**: toggle per-material; G-channel inversion is applied at process time together with other channel compositing, not as a separate step.
    * Auto-detects existing null-texture paths on refresh and sets DEFAULT.
    * Copy / paste material configuration between materials.
    * Per-collection state persistence — switching between MDF2 collections preserves each collection's configuration independently.
    * Output: BC7_UNORM_SRGB for color/emissive slots, BC7_UNORM for linear slots.
* **Blank File Export**: when exporting, any slot with no collection bound can automatically copy a built-in blank file (mesh / MDF2 / Chain2 / CLSP) to the target path instead of being skipped.
* **One-Click RE Chain Creation**: Detects chain-head bones by color, shows a collection picker, then auto-creates Chain Settings + Chain Group for each chain via RE Chain Editor. Supports per-chain independent Settings or a single shared Settings for all chains.
* **BoneSystem Export**: Generates the `.fbxskel.7` file and `reframework/data/BoneSystem/{id}.json` configuration used by the BoneSystem REFramework script. Integrated into the batch exporter panel.

#### RE4 Remake / RE: Requiem (RE9)
* Synchronize child bone orientations.
* **Batch Exporter** (requires RE Mesh Editor plugin): Export mesh / MDF2 / SFUR / Chain2 / CLSP in bulk from JSON-defined schemes. Supports both RE9 and RE4 scheme formats.
    * Simplified mode available: bind one collection per group instead of per entry, with "empty" entries handled automatically.
    * Blank file export option: unset slots copy built-in blank files instead of being skipped. In simplified mode, "empty" entries use blank files directly without requiring a manual collection binding.
* **MDF2 + Tex Processor**: same feature set as the MHWilds version, adapted for RE9 texture paths and version numbers.

---

## Installation

1. Download the **ZIP** file from the Releases page.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click **Install**, select the ZIP, and enable **Modding Toolkit**.

---

<a id="中文说明"></a>
# 中文说明

一款综合性的 Blender 游戏 Mod 制作工具包。支持部分卡普空游戏以及其他游戏。

**支持的 Blender 版本**: 4.x（推荐 4.3+）

---

## 支持游戏
* 怪物猎人世界：冰原 (MHWI)
* 怪物猎人崛起：曙光 (MHRS)
* 怪物猎人：荒野 (MHWs)
* 生化危机4重制版 (RE4R)
* 生化危机：镇魂曲（RE9）
* 街霸6 (SF6)
* 鬼泣5 (DMC5)
* 绝地潜兵2 (HD2)

## 核心功能

### 1. 通用骨架转换器
通过可自定义的 JSON 预设，将任意来源模型转换为任意目标游戏格式。

* **X → Y 架构**: 自由定义来源 (X) 和目标 (Y)。
    * **来源 (X)**: VRChat、MMD、明日方舟：终末地、或任何自定义模型。
    * **目标 (Y)**: 怪猎世界冰原、怪猎荒野、生化4重制版、街霸6 等。
* **骨骼对齐** [X+Y, 双骨架]: 将模型骨架对齐到目标游戏骨架。
* **重命名顶点组** [X+Y]: 直接在网格上重命名顶点组。
* **模糊骨骼名匹配**: 在匹配骨骼名时自动归一化分隔符（`_`、`.`、空格），使预设驱动的操作不受来源骨骼命名风格差异影响。
* **实验性功能 - 物理骨移植** [X+Y, 双骨架]: 将物理骨骼从来源骨架移植到目标骨架，处理方向扭转，自动生成末端骨，并对链首骨骼进行颜色标记以便识别。
* **实验性功能 - 物理权重降级** [X]: 将物理权重合并到最近的身体骨骼上，以用于不需要或不能使用物理的场景。

### 2. 姿态转换
独立于骨架转换器的姿态变换系统。

* **方向计算**: 简易工具，仅将上臂旋转到水平方向。
* **RE Engine 矩阵归零**: 重置 RE Engine 游戏骨架的肢体旋转矩阵（适用于荒野/街霸6/生化4等）。
* **姿态变换记录器**: 录制同类型骨架两个姿态之间的相对旋转变换，之后可正向 (A→B) 或逆向 (B→A) 应用到任何同类型骨架。
    * 录制一次，永久使用——不需要每次都在场景中准备参考骨架。
    * 基于 JSON 文件存储在 `assets/pose_presets/`，插件更新不会删除已有记录。

### 3. 可视化预设编辑器
内置的图形界面编辑器，无需编写代码即可创建自定义骨骼映射。
* 在 3D 视口中点选骨骼进行分配。
* 批量添加辅助骨骼。
* 智能镜像：自动从左侧生成右侧映射。
* 分类分组的预设下拉菜单，便于管理大型预设库。

### 4. 通用工具
* 扭转归零、添加尾骨、镜像对齐 X。
* **骨链简化**: 按保留比例缩减骨链密度；包含合并到活动骨骼功能。
* **通用骨架对齐**: 按骨骼名将任意骨架对齐到参考骨架。
    * **完全对齐模式**同时复制头部、尾部和 Roll；**仅位置模式**只移动头部，保留原有方向。
* **三态骨骼可见性切换**: 在可见 / 隐藏 / 隐藏且不可选 三种状态间循环切换。

### 5. 游戏专用模块

#### 怪猎世界冰原 (MHWI)
* 非物理骨对齐工具。

#### 怪猎荒野 (MHWilds)
* Endfield 面部顶点组改名（Endfield → MHWilds 格式）。
* 面部权重简化（将细分面部骨骼权重合并到主控制骨骼）。
* **装备批量导出器**: 一键导出全部5个部位（手臂/身体/头盔/腿/腰）的 Mesh / MDF2 / Chain2 / CLSP 文件。
    * 装备集由 `assets/mhws_armor_sets/` 下的 JSON 文件定义。
    * 支持4种装备变体（男猎男套/男猎女套/女猎男套/女猎女套），各自独立的 armor_id 和 base_path。
    * JSON 中 `parts_mask` 支持跳过不存在的部位，无需手动留空绑定。
    * 集合绑定在所有变体间共享——配置一次，所有变体通用。
* **MDF2 + Tex 半自动贴图处理器**: 批量更新 MDF2 集合中的贴图绑定路径，并将来源图像一步转换为游戏可用的 `.tex` 文件。
    * 每个材质独立配置 PBR 输入（固有色/Alpha/法线/粗糙度/金属度/AO/自发光）。
    * 每个贴图槽位独立模式：**PBR转换**（从 PBR 输入合成通道）、**直接选择**（选择任意图片/DDS/TEX）、**默认空贴图**（写入游戏内空贴图路径）、**不修改**（保持现有路径）。
    * 单通道输入支持通道选择（R/G/B/A）和反相（例如平滑度→粗糙度、绝缘度→金属度）。
    * **GL→DX 法线翻转**：按材质独立开关，G 通道翻转在处理阶段与通道合成一并执行，不需要单独操作。
    * 刷新时自动检测现有空贴图路径并设为"默认空贴图"模式。
    * 支持材质配置的复制/粘贴。
    * 按集合持久化状态——在不同 MDF2 集合间切换时各自独立保留配置。
    * 输出格式：颜色/自发光槽位用 BC7_UNORM_SRGB，线性槽位用 BC7_UNORM。
* **空模型导出**: 导出时，未绑定集合的槽位可自动将内置空文件（mesh / MDF2 / Chain2 / CLSP）复制到目标路径，不再直接跳过。
* **一键创建 RE Chain**: 自动检测链首骨骼（按颜色），弹出集合选择器，随后调用 RE Chain Editor 为每条链自动创建 Chain Settings 和 Chain Group。支持每条链独立 Settings 或全部链共用同一 Settings 两种模式。
* **BoneSystem 导出**: 生成 `.fbxskel.7` 文件及 `reframework/data/BoneSystem/{id}.json` 配置文件，供 BoneSystem REFramework 脚本使用。已集成到批量导出面板中。

#### 生化危机4重制版 / 生化危机：镇魂曲 (RE4R / RE9)
* 同步子级骨骼朝向。
* **批量导出工具**（需要 RE Mesh Editor 插件）: 通过 JSON 方案批量导出 Mesh / MDF2 / SFUR / Chain2 / CLSP。同时支持 RE9 和 RE4 方案格式。
    * 支持简化模式：按组绑定集合，无需逐条目配置。
    * 支持空模型导出选项：未绑定槽位自动复制内置空文件。简化模式下 "empty" 类型条目无需手动绑定，直接使用内置空文件。
* **MDF2 + Tex 贴图处理器**：与荒野版功能相同，适配 RE9 的贴图路径和版本号。

---

## 安装方法

1. 从 Releases 页面下载 **ZIP** 文件。
2. 在 Blender 中，进入 `编辑 > 首选项 > 插件`。
3. 点击 **安装**，选择 ZIP 文件，启用 **Modding Toolkit**。
