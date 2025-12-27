# MHW Modding Toolkit (Blender Addon)

A comprehensive Blender toolkit designed specifically for modding Monster Hunter World: Iceborne (MHWI), Monster Hunter Wilds (MHWs), and Resident Evil 4 Remake (RE4).

**Supported Versions**: Blender 3.0+ / 4.0+ (Universal Compatibility)

## Key Features

### General Tools
Quick operations for any humanoid skeleton:
* **Roll Zero**: Recursively resets the Roll values of selected bones and their children to 0.
* **Add Tail**: Adds a vertically upward-pointing child bone to the selected terminal bone (for physics chain construction).
* **Mirror X**: Perfectly mirrors the corresponding X-axis bone relative to the X+ axis bone.
* **Bone Chain Simplification**: Deletes every other bone and automatically merges weights (optimizes physical bone count).

### MHWI (Monster Hunter World: Iceborne)
* **Non-Physical Bone Alignment**: Aligns mod skeletons to the base game skeleton, intelligently skipping physical bones like skirts to prevent clipping.
* **MMD Snap**: One-click snaps Japanese/English MMD skeletons to MHWI standard positions (includes toe/elbow corrections).
* **Endfield to MHWI**: One-stop conversion including bone renaming, weight merging, and hierarchy repair.

### MHWs (Monster Hunter: World)
* **T-Pose Conversion**: Forcibly converts MHWs skeleton poses to MHWI standard T-Pose and automatically bakes mesh modifiers.
* **Endfield -> MHWs**: Precisely snaps Endfield skeleton positions to MHWs standards.

### RE4 (Resident Evil 4 Remake)
* **MHWI -> RE4**: Renames MHWI skeletons to RE4 standards.
* **Endfield -> RE4**: Intelligent weight conversion, automatically processing and merging duplicate vertex groups (e.g., split lip weights).

## Installation Method

1. Download the ZIP archive from this repository (do not unzip).
2. Open Blender.
3. From the menu bar, select `Edit` -> `Preferences` -> `Add-ons`.
4. Click `Install...` and select the downloaded ZIP file.
5. Check `Object: MHW Modding Toolkit` to enable the add-on.
6. Press **N** in the 3D viewport to open the **MOD Toolkit** panel in the right sidebar.