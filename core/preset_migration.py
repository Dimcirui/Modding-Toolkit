"""
预设迁移模块 - v2.2 → v2.3 (英文预设名 → 中文预设名)

在 register() 时自动执行一次。逻辑：
1. 检查是否已迁移（通过标记文件 _migration_done.json）
2. 将旧英文内置预设重命名为中文名
3. 用户自建的预设完全不动
4. 写入标记文件，后续启动不再重复执行
"""

import os
import json

# ============================================================
# 旧文件名 → 新文件名 对照表（不含 .json 后缀）
# ============================================================
IMPORT_RENAME_MAP = {
    "mhwi_in":            "怪猎世界",
    "mhwi_in_graft":      "怪猎世界(物理移植用)",
    "mmd_in":             "MMD",
    "mmd_in_graft":       "MMD(物理移植用)",
    "Valve":              "Valve社",
    "vrc_in":             "VRChat",
    "vrc_in_graft":       "VRChat(物理移植用)",
    "mhrs_in":            "怪猎崛起",
    "mhws_in":            "怪猎荒野",
    "re4_in":             "生化危机4",
    "gbfr_in":            "碧蓝幻想",
    "endfield_in":        "终末地",
    "endfield_in_graft":  "终末地(物理移植用)",
    "uma_in":             "赛马娘",
    "dmc5_in":            "鬼泣5",
}

TARGET_RENAME_MAP = {
    "mhwi_bonfunction_out":  "怪猎世界(旧插件)",
    "mhwi_MhBone_out":      "怪猎世界",
    "mhrs_out":             "怪猎崛起",
    "mhws_out":             "怪猎荒野",
    "re4_out":              "生化危机4",
    "dmc5_out":             "鬼泣5",
    "sf6_out":              "街霸6",
}

MIGRATION_MARKER = "_migration_v2.3_done.json"


def _get_addon_root():
    """获取插件根目录（core/ 的上一级）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _migrate_folder(folder_path, rename_map):
    """
    对指定文件夹执行迁移。
    
    规则：
    - 旧英文名存在 且 新中文名不存在 → 重命名（迁移）
    - 旧英文名存在 且 新中文名也存在 → 删除旧英文名（新版已提供中文版）
    - 旧英文名不存在 → 跳过（用户可能已经手动删了）
    - 不在 rename_map 中的文件 → 完全不动（这些是用户自建预设）
    
    返回：(renamed_count, skipped_count, removed_count)
    """
    if not os.path.exists(folder_path):
        return 0, 0, 0

    renamed = 0
    skipped = 0
    removed = 0

    for old_stem, new_stem in rename_map.items():
        old_path = os.path.join(folder_path, old_stem + ".json")
        new_path = os.path.join(folder_path, new_stem + ".json")

        if not os.path.exists(old_path):
            skipped += 1
            continue

        if os.path.exists(new_path):
            # 新版中文预设已存在（可能是更新包带来的），删掉旧的英文名副本
            try:
                os.remove(old_path)
                removed += 1
                print(f"[Migration] 已删除旧预设: {old_stem}.json (新版 {new_stem}.json 已存在)")
            except Exception as e:
                print(f"[Migration] 删除失败: {old_path} - {e}")
        else:
            # 新中文名不存在，直接重命名旧文件
            try:
                os.rename(old_path, new_path)
                renamed += 1
                print(f"[Migration] 重命名: {old_stem}.json → {new_stem}.json")
            except Exception as e:
                print(f"[Migration] 重命名失败: {old_path} - {e}")

    return renamed, skipped, removed


def run_migration():
    """
    执行一次性迁移。在 register() 中调用。
    如果已经迁移过（标记文件存在），立即返回。
    """
    addon_root = _get_addon_root()
    assets_dir = os.path.join(addon_root, "assets")
    marker_path = os.path.join(assets_dir, MIGRATION_MARKER)

    # 检查标记文件 — 已迁移则跳过
    if os.path.exists(marker_path):
        return

    print("[Migration] 开始预设迁移 (v2.2 → v2.3)...")

    # 迁移 import_presets
    import_dir = os.path.join(assets_dir, "import_presets")
    r1, s1, d1 = _migrate_folder(import_dir, IMPORT_RENAME_MAP)
    print(f"[Migration] import_presets: 重命名 {r1}, 跳过 {s1}, 清理 {d1}")

    # 迁移 bone_presets
    target_dir = os.path.join(assets_dir, "bone_presets")
    r2, s2, d2 = _migrate_folder(target_dir, TARGET_RENAME_MAP)
    print(f"[Migration] bone_presets: 重命名 {r2}, 跳过 {s2}, 清理 {d2}")

    # 写入标记文件，防止重复迁移
    try:
        from datetime import datetime
        marker_data = {
            "migrated_at": str(datetime.now()),
            "from_version": "2.2",
            "to_version": "2.3",
            "import_presets": {"renamed": r1, "skipped": s1, "removed": d1},
            "bone_presets": {"renamed": r2, "skipped": s2, "removed": d2},
        }
        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(marker_data, f, indent=2, ensure_ascii=False)
        print("[Migration] 迁移完成，已写入标记文件。")
    except Exception as e:
        print(f"[Migration] 写入标记文件失败: {e}")

    print("[Migration] 预设迁移结束。")
