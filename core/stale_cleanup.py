"""Find files an older version of this addon left behind, using the release manifest.

``addon_updater`` updates by *merging* the new files over the installed ones
(``deep_merge_directory``) and never deleting.  Its ``clean_install`` option, which
would clear the folder first, is ``options={'HIDDEN'}`` and defaults to False, so no
user can reach it.  The consequence is that **every file a version drops stays on the
user's disk forever** -- measured on this developer's own 4.3 install: 206 MB of
leftovers across 13855 files, including reference models removed two versions ago and
a whole unrelated tool that had been copied in.

The judgement of what is a leftover is mechanical rather than a hand-kept list of
obsolete paths: ``scripts/build_release.py`` writes ``MANIFEST.txt`` into the zip
listing every file that version ships, so "what a clean install would contain" is
already recorded, and **anything else in the folder is a leftover by definition**.  A
maintained list of "files we deleted in 2.6.x" would be a second copy of the same fact,
free to go stale, and stale in the one direction that deletes a live file.

Two things are exempt from deletion, for the same reason: the addon does not own them.

* ``assets/presets/`` -- the bone-preset editor writes here, so a user's own preset is
  a leftover by the rule above and must not be treated as one.  These are *reported*
  separately instead.
* anything under a top-level ``*updater*`` directory -- the updater's own state and its
  backup of the previous version.  Deleting the backup would remove the only way back.

``__pycache__`` is deleted rather than exempted: it is regenerated on demand, and after
a module is dropped its stale ``.pyc`` is exactly the kind of thing that makes an
install look like it still has code it does not.

Free of ``bpy`` so the planning is unit-testable offline; the operator and its
confirmation dialog live in ``core/stale_cleanup_ops.py``.
"""

import os
import shutil

MANIFEST_NAME = "MANIFEST.txt"

#: Reported, never deleted -- see the module docstring.
KEEP_PREFIXES = ("assets/presets/",)


def addon_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_manifest(root=None):
    """``set`` of addon-relative paths this version ships, or None when there is no
    manifest.

    None is a real answer, not a failure: an install from a pre-manifest release, or a
    git checkout used in place, has nothing to compare against -- and in that case the
    cleanup must do **nothing**, because every file would look like a leftover.
    """
    path = os.path.join(root or addon_root(), MANIFEST_NAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    return {l.strip() for l in lines if l.strip() and not l.startswith("#")}


def _is_updater(rel):
    return "updater" in rel.split("/")[0].lower()


def find_stale(root=None, manifest=None):
    """``(stale, kept, pycache_dirs, total_bytes)`` -- all paths addon-relative.

    *stale* is what the operator would delete, *kept* is the ``KEEP_PREFIXES`` matches
    it refuses to, *pycache_dirs* are deleted wholesale.  Returns empty lists when
    there is no manifest, so a caller cannot accidentally delete an unmanifested
    install by forgetting to check.
    """
    root = root or addon_root()
    if manifest is None:
        manifest = read_manifest(root)
    if manifest is None:
        return [], [], [], 0

    stale, kept, pycache, total = [], [], [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        for d in list(dirnames):
            if d == "__pycache__":
                pycache.append(rel_dir + d)
                dirnames.remove(d)
            elif not rel_dir and _is_updater(d):
                dirnames.remove(d)
        for name in filenames:
            rel = rel_dir + name
            if rel == MANIFEST_NAME or rel in manifest or _is_updater(rel):
                continue
            if rel.startswith(KEEP_PREFIXES):
                kept.append(rel)
                continue
            stale.append(rel)
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return sorted(stale), sorted(kept), sorted(pycache), total


def delete(stale, pycache_dirs, root=None):
    """``(files_removed, dirs_removed, [error strings])``.

    Errors are collected rather than raised: on Windows a single file held open by
    another process must not abort the other 13000.
    """
    root = root or addon_root()
    errors = []
    files = dirs = 0
    for rel in stale:
        try:
            os.remove(os.path.join(root, *rel.split("/")))
            files += 1
        except OSError as e:
            errors.append(f"{rel}: {e}")
    for rel in pycache_dirs:
        try:
            shutil.rmtree(os.path.join(root, *rel.split("/")))
            dirs += 1
        except OSError as e:
            errors.append(f"{rel}: {e}")

    # Directories the deletions emptied out.  Bottom-up so a nest collapses in one
    # pass; the addon root itself is never a candidate.
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        if dirpath == root:
            continue
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
                dirs += 1
        except OSError:
            pass
    return files, dirs, errors
