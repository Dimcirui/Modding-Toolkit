"""Keep an update from overwriting a built-in preset the user has edited.

Built-in presets live in the addon folder (``assets/presets/``), and users do edit
them in place -- typically to add bones a preset is missing.  ``addon_updater``
overwrites every ``*.json`` the new version ships, so without this an update silently
throws those edits away.

The question "has the user edited this file?" is answered without any install-time
state: ``scripts/build_release.py`` writes ``PRESET_HASHES.json`` into the zip, holding
for every preset path the hash of **every version of it that git history contains**.
An installed file whose hash is in that set is one of ours, from whichever release,
and is safe to replace; anything else was edited (or created under a name we later
started shipping), and is left where it is.

Hashes are taken over *canonical* JSON, not bytes: the preset editor re-dumps the whole
file on save, and ``git archive`` may or may not rewrite line endings, so a byte hash
would call an untouched file "edited" for reasons that have nothing to do with the user.
Key order is canonicalised; list order is not, because ``main[0]`` is the preferred
candidate and reordering it is a real edit.

Scope is deliberately "don't overwrite".  What to do with the new official version
of a file that was kept is a separate decision.

Free of ``bpy``: it runs inside the updater, and is unit-testable offline.
"""

import hashlib
import json
import os

HASHES_NAME = "PRESET_HASHES.json"

#: Only files under here are guarded.  Everything else keeps the updater's plain
#: overwrite behaviour.
GUARDED_PREFIX = "assets/presets/"


def is_guarded(rel):
    return rel.startswith(GUARDED_PREFIX) and rel.endswith(".json")


def canonical_hash(data):
    """sha1 of the canonical form of JSON *data* (bytes), or None if it is not JSON."""
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def file_hash(path):
    try:
        with open(path, "rb") as f:
            return canonical_hash(f.read())
    except OSError:
        return None


def load_hashes(*roots):
    """``{rel: set(hashes)}`` from the first root that has a hash table, else None.

    The updater passes the staged new version first: its table covers history up to
    the release being installed, which is a superset of the installed one's.
    """
    for root in roots:
        if not root:
            continue
        try:
            with open(os.path.join(root, HASHES_NAME), "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue
        return {rel: set(hs) for rel, hs in raw.get("presets", {}).items()}
    return None


def is_user_modified(rel, installed_path, hashes):
    """True if the installed file at *rel* must **not** be overwritten.

    * not a guarded path, or no hash table at all -> False (old behaviour: overwrite).
      No table means the release predates this mechanism; refusing every overwrite
      then would freeze every preset forever.
    * hash matches a version we shipped -> False.
    * otherwise -> True.  That includes a file that is not valid JSON (the user broke
      it mid-edit -- still theirs) and a path the table has no entry for (a preset the
      user created under a name a later release started shipping).
    """
    if hashes is None or not is_guarded(rel):
        return False
    return file_hash(installed_path) not in hashes.get(rel, ())
