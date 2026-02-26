# Modding Toolkit (Blender Addon)

[中文说明见下方](#中文说明)

A comprehensive Blender toolkit for game modding. Supports Monster Hunter World: Iceborne (MHWI), Monster Hunter Wilds (MHWs), Resident Evil 4 Remake (RE4), and more through a universal preset system.

**Supported Blender Versions**: 4.x (recommended 4.3+)

---

## Core Features

### 1. Universal Skeleton Converter
Convert any source model to any target game format using customizable JSON presets.

* **X → Y Architecture**: Define your source (X) and target (Y) freely.
    * **Source (X)**: VRChat, MMD, Endfield, or any custom ripped model.
    * **Target (Y)**: MHWI, MHW: Wilds, RE4 Remake, Street Fighter 6, etc.
* **Bone Snap** [X+Y, dual armature]: Align your model's skeleton to the target game's skeleton.
* **Direct Convert** [X+Y]: Rename vertex groups directly on the mesh.
* **Experimental - Physics Bone Graft** [X+Y, dual armature]: Transplant physics bones from source to target skeleton with auto-generated end bones.

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

### 4. Game-Specific Modules

* **MHWI (Iceborne)**: Non-physics bone alignment tool.
* **MHWilds (Wilds)**:
    * Endfield face vertex group rename (Endfield → MHWilds format).
    * Face weight simplification (merge detailed facial bones to main control bones).
* **RE4 (Remake)**: FakeBone (end bone) generation, alignment, and merging toolset.

### 5. General Utilities
* Roll Zero, Add Tail Bone, Mirror X, Chain Simplification.

---

## Installation

1. Download the **ZIP** file from the Releases page.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click **Install**, select the ZIP, and enable **Modding Toolkit**.

---

<a id="中文说明"></a>
# 中文说明

一款综合性的 Blender 游戏 Mod 制作工具包。支持怪物猎人世界：冰原 (MHWI)、怪物猎人：荒野 (MHWs)、生化危机4重制版 (RE4) 等游戏，并通过通用预设系统支持更多游戏。

**支持的 Blender 版本**: 4.x（推荐 4.3+）

---

## 核心功能

### 1. 通用骨架转换器
通过可自定义的 JSON 预设，将任意来源模型转换为任意目标游戏格式。

* **X → Y 架构**: 自由定义来源 (X) 和目标 (Y)。
    * **来源 (X)**: VRChat、MMD、明日方舟：终末地、或任何自定义模型。
    * **目标 (Y)**: 怪猎世界冰原、怪猎荒野、生化4重制版、街霸6 等。
* **骨骼对齐** [X+Y, 双骨架]: 将模型骨架对齐到目标游戏骨架。
* **重命名顶点组** [X+Y]: 直接在网格上重命名顶点组。
* **实验性功能 - 物理骨移植** [X+Y, 双骨架]: 将物理骨骼从来源骨架移植到目标骨架，自动生成末端骨。

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

### 4. 游戏专用模块

* **怪猎世界冰原 (MHWI)**: 非物理骨对齐工具。
* **怪猎荒野 (MHWilds)**:
    * Endfield 面部顶点组改名（Endfield → MHWilds 格式）。
    * 面部权重简化（将细分面部骨骼权重合并到主控制骨骼）。
* **生化4重制版 (RE4)**: FakeBone（末端骨）生成、对齐和合并工具集。

### 5. 通用工具
* 扭转归零、添加尾骨、镜像对齐 X、骨链简化。

---

## 安装方法

1. 从 Releases 页面下载 **ZIP** 文件。
2. 在 Blender 中，进入 `编辑 > 首选项 > 插件`。
3. 点击 **安装**，选择 ZIP 文件，启用 **Modding Toolkit**。