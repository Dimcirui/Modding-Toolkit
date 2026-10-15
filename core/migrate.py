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
    # Old physics-transfer presets (removed in earlier version)
    (os.path.join("presets", "import"), "怪猎世界(物理移植用).json"),
    (os.path.join("presets", "import"), "MMD(物理移植用).json"),
    (os.path.join("presets", "import"), "终末地(物理移植用).json"),
    # Chinese-named presets replaced by ASCII filenames (display name now stored inside JSON)
    (os.path.join("presets", "bone"),   "怪猎世界.json"),
    (os.path.join("presets", "bone"),   "怪猎世界(旧插件).json"),
    (os.path.join("presets", "bone"),   "怪猎崛起.json"),
    (os.path.join("presets", "bone"),   "怪猎荒野.json"),
    (os.path.join("presets", "bone"),   "生化危机4.json"),
    (os.path.join("presets", "bone"),   "生化危机9.json"),
    (os.path.join("presets", "bone"),   "鬼泣5.json"),
    (os.path.join("presets", "bone"),   "街霸6.json"),
    (os.path.join("presets", "bone"),   "绝地潜兵2.json"),
    (os.path.join("presets", "import"), "怪猎世界.json"),
    (os.path.join("presets", "import"), "怪猎崛起.json"),
    (os.path.join("presets", "import"), "怪猎荒野.json"),
    (os.path.join("presets", "import"), "生化危机4.json"),
    (os.path.join("presets", "import"), "生化危机9.json"),
    (os.path.join("presets", "import"), "鬼泣5.json"),
    (os.path.join("presets", "import"), "街霸6.json"),
    (os.path.join("presets", "import"), "绝地潜兵2.json"),
    (os.path.join("presets", "import"), "碧蓝幻想.json"),
    (os.path.join("presets", "import"), "终末地.json"),
    (os.path.join("presets", "import"), "赛马娘.json"),
    (os.path.join("presets", "import"), "Valve社.json"),
]

#: Canonical-JSON sha1 (core.preset_guard.canonical_hash) of every version of
#: the files above that git history contains, under any of their old folders.
#: A deprecated name is deleted only when its content is one of these: the
#: preset editor lets users save under any name, Chinese included, and a user's
#: own "怪猎荒野.json" used to be deleted on the next start with only a console line.
#: Generated from git history once; these files are no longer shipped, so the set
#: cannot grow.
_SHIPPED_HASHES = frozenset({
    "069aa57459b2c8fdccfba59b399737a3563a2b60",
    "1009b8fbff291a200c2f8aed50393d85b1808bf9",
    "1c335066c646c04750ad5ff0413f2e68b2c26c0e",
    "1fb8c63cc06319e959a11ae2ab6616a5cb7fc441",
    "22132ff76d41e6e933e8d9ef0666aa95779e1cb4",
    "30e27776499092992cdeca14eac46d00e5681bc1",
    "3b50a3432b540c4ec849d859b4b58007b67b418d",
    "3fea7a740bbe30f4de2d133c8d960dbd0de43116",
    "41b6001d22eac942bf446c6a6a82644ff3761505",
    "43058bf921d09c690fa486547ba8739040746ce4",
    "4d68b095356abf63e2f29a3923bc7b0c34bb02e5",
    "56ec83b7012fc6228fd46e7930420a98c22c3874",
    "59058eb2ff4806f5229e37117f477699d569a49b",
    "5ba75715b0200433cec3db19df5c51c20b694de5",
    "6e1ab25e88c97da6a930bc55456319adb643af5b",
    "714052bec9357f14106a0a84f431f9eb29947519",
    "7632a65a3a0e19c1443d60f21526515da2803e09",
    "782b78bf099e2893ad8a0d85d9a4f7db34155ce5",
    "784f11eb38b39fb8d8b3099c9b7c4d0141dd2e1b",
    "92a9fbdc0b6a1b6b1728ac87542aaa3bd6b27011",
    "930a4fb25ff9fce5c3f26aeb713db3556cda97ec",
    "9526adad2c0acbcb572c94e62b622e290253e92c",
    "9697db1516dc80a00cb115a9be52a99690edccf2",
    "98ad8692c0667cab2deb4d7b9edc768ca08f6ec5",
    "9b21acd9a91cc73bac28e51c4efa3276a1a252ba",
    "a38849dffbea7f733d950669c8aefe6ccc00f2b3",
    "adeb764ada95559931ec50c2e549ed3cfad106b3",
    "b3466ccd9204f95690f363b6d7357090348e6697",
    "bdde5f1e11aabf03af4ce8099ad844749cc2604d",
    "d62bb6e2ff877d81504ce76fb14241844d45e887",
    "dcc36894cbefd4ffcd8113c79fd973d049538f3d",
    "dee1bd4d045a7a846bf7b793b629776bb1ea56fd",
    "e4b8b528bd54844a17132bedfc12f4152e737acc",
    "e641943b87c0b08e1309a0349766ac94a7668a8d",
    "e6d262de051d90b4bffa5a3ee015e4619284fb58",
    "ee5be7953e24d45b0fde0f0cba8eca4f0986b914",
    "f30205ed6741ace10ce232ea3b28a4633854bfb9",
    "f5e309a57ce501c7d7a26cdac8370eb03cb10145",
    "f6dc54604ec0afa384ac71f8f73c7a36c5c1a5aa",
})

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


def _marker_path():
    try:
        import bpy
        cfg = bpy.utils.user_resource("CONFIG")
    except Exception:
        cfg = os.path.expanduser("~")
    return os.path.join(cfg, "modding_toolkit_migrated.txt")


def _already_migrated(root):
    try:
        with open(_marker_path(), encoding="utf-8") as f:
            return root in {line.strip() for line in f}
    except OSError:
        return False


def _mark_migrated(root):
    try:
        with open(_marker_path(), "a", encoding="utf-8") as f:
            f.write(root + "\n")
    except OSError:
        pass


def run():
    """Migrate the pre-restructure asset folders once, then drop deprecated presets.

    Never raises: it runs first in register(), and an OSError here used to abort
    registration before the preferences and every module were loaded.
    """
    try:
        _run()
    except Exception as e:
        print(f"[Modding Toolkit] migrate skipped: {e}")


def _run():
    assets = _assets_dir()
    all_migrated = []

    # The copy is done once per install.  Installs updated by the updater from
    # <= 2.4.4 keep their old folders (the updater never deletes), so running it
    # on every start copied ~24 deprecated files back into presets/ only to delete
    # them again, and brought back any preset the user had deleted on purpose.
    if _already_migrated(assets):
        _remove_deprecated(assets)
        return

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

    _remove_deprecated(assets)
    _mark_migrated(assets)

    if all_migrated:
        print(f"[Modding Toolkit] Migrated {len(all_migrated)} file(s) from old asset paths:")
        for src, dst in all_migrated:
            rel_src = os.path.relpath(src, assets)
            rel_dst = os.path.relpath(dst, assets)
            print(f"  {rel_src}  →  {rel_dst}")
        print("[Modding Toolkit] Old directories are kept as-is and can be safely deleted.")


def _remove_deprecated(assets):
    """Delete the deprecated presets -- but only the ones that are ours."""
    from .preset_guard import file_hash
    for subdir, filename in _DEPRECATED:
        path = os.path.join(assets, subdir, filename)
        if not os.path.isfile(path):
            continue
        if file_hash(path) not in _SHIPPED_HASHES:
            # Same name as a preset we used to ship, different content: the
            # user's own.  Leave it.
            continue
        try:
            os.remove(path)
            print(f"[Modding Toolkit] Removed deprecated file: {os.path.join(subdir, filename)}")
        except Exception as e:
            print(f"[Modding Toolkit] migrate: failed to remove {path}: {e}")
