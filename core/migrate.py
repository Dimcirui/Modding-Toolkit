import os
import shutil

# Old subdirectory → new subdirectory (relative to assets/)
_RENAMES = [
    ("bone_presets",         os.path.join("presets", "bone")),
    ("import_presets",       os.path.join("presets", "import")),
    ("pose_presets",         os.path.join("presets", "pose")),
    ("re4_export_schemes",   os.path.join("export_schemes", "re4")),
    ("re4_native_skeletons", os.path.join("native_skeletons", "re4")),
    ("mhws_armor_sets",      os.path.join("mhws", "armor_sets")),
    ("mhws_bonesystem",      os.path.join("mhws", "bonesystem")),
]

# Deprecated files to remove on update (hardcoded names only, never patterns)
_DEPRECATED = [
    (os.path.join("presets", "import"), "怪猎世界(物理移植用).json"),
    (os.path.join("presets", "import"), "MMD(物理移植用).json"),
    (os.path.join("presets", "import"), "终末地(物理移植用).json"),
]

# Top-level .json files in the old export_schemes/ root → export_schemes/re9/
_EXPORT_SCHEMES_ROOT = "export_schemes"
_EXPORT_SCHEMES_RE9  = os.path.join("export_schemes", "re9")


def _assets_dir():
    # core/ → addon root → assets/
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def _migrate_dir(old_dir, new_dir):
    """Copy files from old_dir to new_dir, skipping files that already exist at the destination."""
    migrated = []
    if not os.path.isdir(old_dir):
        return migrated
    os.makedirs(new_dir, exist_ok=True)
    for filename in os.listdir(old_dir):
        src = os.path.join(old_dir, filename)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(new_dir, filename)
        if os.path.exists(dst):
            continue
        try:
            shutil.copy2(src, dst)
            migrated.append((src, dst))
        except Exception as e:
            print(f"[Modding Toolkit] migrate: failed to copy {src} → {dst}: {e}")
    return migrated


def run():
    """
    Check for pre-restructure asset directories and migrate any files that are
    not yet present at the new locations. Called once on addon register.
    """
    assets = _assets_dir()
    all_migrated = []

    # Simple directory renames
    for old_sub, new_sub in _RENAMES:
        old_dir = os.path.join(assets, old_sub)
        new_dir = os.path.join(assets, new_sub)
        all_migrated.extend(_migrate_dir(old_dir, new_dir))

    # Special case: top-level .json files in old export_schemes/ → export_schemes/re9/
    old_es = os.path.join(assets, _EXPORT_SCHEMES_ROOT)
    new_es = os.path.join(assets, _EXPORT_SCHEMES_RE9)
    if os.path.isdir(old_es):
        os.makedirs(new_es, exist_ok=True)
        for filename in os.listdir(old_es):
            src = os.path.join(old_es, filename)
            if not os.path.isfile(src) or not filename.endswith(".json"):
                continue
            dst = os.path.join(new_es, filename)
            if os.path.exists(dst):
                continue
            try:
                shutil.copy2(src, dst)
                all_migrated.append((src, dst))
            except Exception as e:
                print(f"[Modding Toolkit] migrate: failed to copy {src} → {dst}: {e}")

    # Remove deprecated files (hardcoded list, safe against user custom presets)
    for subdir, filename in _DEPRECATED:
        path = os.path.join(assets, subdir, filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
                print(f"[Modding Toolkit] Removed deprecated file: {os.path.join(subdir, filename)}")
            except Exception as e:
                print(f"[Modding Toolkit] migrate: failed to remove {path}: {e}")

    if all_migrated:
        print(f"[Modding Toolkit] Migrated {len(all_migrated)} file(s) from old asset paths:")
        for src, dst in all_migrated:
            rel_src = os.path.relpath(src, assets)
            rel_dst = os.path.relpath(dst, assets)
            print(f"  {rel_src}  →  {rel_dst}")
        print("[Modding Toolkit] Old directories are kept as-is and can be safely deleted.")
