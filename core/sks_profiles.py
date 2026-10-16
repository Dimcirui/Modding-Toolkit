"""ShapeKeySystem (SKS) expression profiles, read the way SKS reads them.

SKS is a REFramework plugin that drives a mesh's blendshapes in game.  An
expression *profile* (``sks.profile/1``: ARKit, MMD, one per VRChat face...) maps
mesh shape-key names to game signals; it holds no values.  In game a key is an
expression key when the active profile matches it on a part where at least three
distinct profile channels match -- every other key is a sculpt (捏脸) key.  Batch
export needs the same split to filter keys and to write a sculpt preset, so the
matching below is a port of SKS's own, line for line where it matters:

    U.norm / U.fold_width   ShapeKeySystem_Core/Util.lua
    N.keys / build_index / match_part      .../Names.lua
    P.load_all / resolve / match_count     .../Profile.lua
    S.key_of                               .../Sculpt.lua

Profiles come from two places, merged and deduplicated by id: the snapshot
bundled in ``assets/sks/`` (SKS's builtin set) and, when found, the SKS install
in the game folder (its builtin/ plus the user's mods/ and user/ profiles).  The
local one wins on the same id, in SKS's own folder order.  Local alone is not
enough: an install that carries one profile would hide every bundled one.

No bpy here: the module is pure data so it can be tested outside Blender.
"""

import json
import os
import re

PROFILE_SCHEMA = "sks.profile/1"
SCULPT_SCHEMA = "sks.sculpt/1"
BINDING_SCHEMA = "sks.binding/1"

#: A part becomes an expression target only with this many distinct channels
#: matched (SKS API.lua ``min_hits``).
MIN_HITS = 3

_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_DIR = os.path.join(_ADDON_DIR, "assets", "sks")


# ── Names (Util.lua / Names.lua) ─────────────────────────────────────────────

def _half_kana_table():
    half = [0xFF61, 0xFF62, 0xFF63, 0xFF64, 0xFF65]
    full = [0x3002, 0x300C, 0x300D, 0x3001, 0x30FB]
    kana = ("ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノ"
            "ハヒフヘホマミムメモヤユヨラリルレロワン")
    for i, c in enumerate(kana):
        half.append(0xFF66 + i)
        full.append(ord(c))
    return dict(zip(half, full))


_HALF_KANA = _half_kana_table()
_VOICED = {0x30AB, 0x30AD, 0x30AF, 0x30B1, 0x30B3, 0x30B5, 0x30B7, 0x30B9, 0x30BB, 0x30BD,
           0x30BF, 0x30C1, 0x30C4, 0x30C6, 0x30C8, 0x30CF, 0x30D2, 0x30D5, 0x30D8, 0x30DB}
_SEMI = {0x30CF, 0x30D2, 0x30D5, 0x30D8, 0x30DB}


def fold_width(s):
    """Full-width ASCII -> ASCII, half-width katakana -> full-width with the
    voiced marks merged, ideographic space dropped."""
    out = []
    for ch in s:
        c = ord(ch)
        if 0xFF01 <= c <= 0xFF5E:
            c -= 0xFEE0
        elif c in _HALF_KANA:
            c = _HALF_KANA[c]
        elif c == 0x301C:
            c = 0x7E
        prev = out[-1] if out else None
        if c in (0xFF9E, 0x3099, 0x309B) and prev is not None and (prev in _VOICED or prev == 0x30A6):
            out[-1] = 0x30F4 if prev == 0x30A6 else prev + 1
        elif c in (0xFF9F, 0x309A, 0x309C) and prev is not None and prev in _SEMI:
            out[-1] = prev + 2
        elif c != 0x3000:
            out.append(c)
    return "".join(chr(c) for c in out)


_SEPARATORS = re.compile(r"[_\-\t\n\v\f\r ]")


def norm(name):
    """Case / separator / width insensitive key.  Lua's lower() and %s are ASCII
    only, so these are too."""
    if any(ord(ch) > 127 for ch in name):
        name = fold_width(name)
    name = "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in name)
    return _SEPARATORS.sub("", name)


_LOD_SUFFIX = re.compile(r"_[Ll][Oo][Dd]\d+$")


def keys(channel_name):
    """Normalised lookup keys for one mesh channel, most specific first: the full
    name, after the first dot, after the last dot, each also without _LODn."""
    out = []

    def add(s):
        if not s:
            return
        out.append(norm(s))
        base = _LOD_SUFFIX.sub("", s)
        if base != s:
            out.append(norm(base))

    add(channel_name)
    m = re.match(r"^[^.]+\.(.+)$", channel_name, re.S)
    first = m.group(1) if m else None
    add(first)
    m = re.match(r"^.+\.([^.]+)$", channel_name, re.S)
    last = m.group(1) if m else None
    if last != first:
        add(last)
    return out


def key_of(channel_name):
    """The sculpt key a channel belongs to: after the last dot, minus _LODn.
    Same-named channels of different parts / LODs share one sculpt key."""
    short = channel_name.rsplit(".", 1)[-1] or channel_name
    return _LOD_SUFFIX.sub("", short)


class _Index:
    __slots__ = ("slot", "rank", "ranked", "unless")

    def __init__(self):
        self.slot = {}      # norm(name) -> slot
        self.rank = {}      # norm(any name) -> rank, 1-based (the channel name is 0)
        self.ranked = set()
        self.unless = {}    # slot -> [slots]


def build_index(channels, alias_set_names, alias_sets):
    idx = _Index()
    for slot, ch in enumerate(channels):
        idx.slot[norm(ch["name"])] = slot
    for slot, ch in enumerate(channels):
        if isinstance(ch.get("any"), list):
            idx.ranked.add(slot)
            for r, a in enumerate(ch["any"], 1):
                k = norm(a) if isinstance(a, str) else ""
                if k and k not in idx.slot:
                    idx.slot[k] = slot
                    idx.rank[k] = r
    slot_of = {ch["name"]: slot for slot, ch in enumerate(channels)}
    for slot, ch in enumerate(channels):
        if isinstance(ch.get("unless"), list):
            lst = [slot_of[o] for o in ch["unless"] if o in slot_of]
            if lst:
                idx.unless[slot] = lst
    for set_name in alias_set_names or ():
        for a, canonical in (alias_sets.get(set_name) or {}).items():
            s = idx.slot.get(norm(canonical))
            if s is not None and a not in idx.slot:
                idx.slot[a] = s
    return idx


def match(idx, channel_name):
    for k in keys(channel_name):
        s = idx.slot.get(k)
        if s is not None:
            return s, k
    return None, None


def match_part(idx, names):
    """Slot (or None) for each name of one part, with "any" ranking and
    "unless" applied."""
    sel, rank, best = [], {}, {}
    for i, cn in enumerate(names):
        s, k = match(idx, cn) if cn else (None, None)
        sel.append(s)
        if s is not None and s in idx.ranked:
            r = idx.rank.get(k, 0)
            rank[i] = r
            if s not in best or r < best[s]:
                best[s] = r
    present = set()
    for i, s in enumerate(sel):
        if s is not None and i in rank and rank[i] > best[s]:
            sel[i] = None
        if sel[i] is not None:
            present.add(sel[i])
    drop = {s for s, lst in idx.unless.items()
            if s in present and any(o in present for o in lst)}
    return [None if s in drop else s for s in sel]


# ── Profiles (Profile.lua) ───────────────────────────────────────────────────

def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _json_files(folder):
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".json"))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names]


def sks_data_dir(root):
    """``<root>/reframework/data/ShapeKeySystem`` for a game or mod root."""
    return os.path.join(root, "reframework", "data", "ShapeKeySystem")


def profile_dirs(game_id, local_roots=()):
    """(folder, source) in load order, later folders win: SKS's own order
    (shared builtin, the game's builtin, mods, user), bundled before local at
    each builtin step."""
    dirs = [(os.path.join(BUNDLED_DIR, "profiles"), "bundled")]
    locals_ = [sks_data_dir(r) for r in local_roots if r]
    for d in locals_:
        dirs.append((os.path.join(d, "builtin", "profiles"), "builtin"))
    if game_id:
        dirs.append((os.path.join(BUNDLED_DIR, game_id, "profiles"), "bundled"))
        for d in locals_:
            dirs.append((os.path.join(d, "builtin", game_id, "profiles"), "builtin"))
    for src in ("mods", "user"):
        for d in locals_:
            dirs.append((os.path.join(d, src, "profiles"), src))
    return dirs


class Library:
    """Every usable profile for one game, with "extends" resolved on demand."""

    def __init__(self, registry, alias_sets):
        self.registry = registry        # id -> {"id", "name", "source", "path", "data"}
        self.alias_sets = alias_sets    # set name -> {norm(alias): canonical}
        self._resolved = {}
        self._index = {}

    def resolve(self, pid, seen=None):
        if pid in self._resolved:
            return self._resolved[pid]
        seen = seen or set()
        e = self.registry.get(pid)
        if e is None or pid in seen:
            return None
        seen.add(pid)
        channels, pos, aliases = [], {}, []
        parent_id = e["data"].get("extends")
        if isinstance(parent_id, str):
            parent = self.resolve(parent_id, seen)
            if parent is None:
                return None
            for ch in parent["channels"]:
                pos[ch["name"]] = len(channels)
                channels.append(ch)
            aliases.extend(parent["aliases"])
        for ch in e["data"].get("channels") or []:
            if isinstance(ch, dict) and isinstance(ch.get("name"), str):
                if ch["name"] in pos:
                    channels[pos[ch["name"]]] = ch
                else:
                    pos[ch["name"]] = len(channels)
                    channels.append(ch)
        aliases.extend(a for a in (e["data"].get("aliases") or []) if isinstance(a, str))
        r = {"id": pid, "name": e["name"], "source": e["source"],
             "aliases": aliases, "channels": channels}
        self._resolved[pid] = r
        return r

    def index(self, pid):
        if pid not in self._index:
            r = self.resolve(pid)
            self._index[pid] = (build_index(r["channels"], r["aliases"], self.alias_sets)
                                if r else None)
        return self._index[pid]

    def match_count(self, pid, names):
        idx = self.index(pid)
        if idx is None:
            return 0
        return len({s for s in match_part(idx, names) if s is not None})

    def rank(self, names):
        """``[(id, name, hits, channels, source)]``, best match first."""
        out = []
        for pid in self.registry:
            r = self.resolve(pid)
            if r is None:
                continue
            out.append((pid, r["name"], self.match_count(pid, names), len(r["channels"]), r["source"]))
        out.sort(key=lambda t: (-t[2], t[1].lower(), t[0]))
        return out

    def expression_names(self, pid, part_names, min_hits=MIN_HITS):
        """The names SKS would drive from profile *pid* on one part: every matched
        channel, or none when fewer than *min_hits* distinct channels match."""
        idx = self.index(pid) if pid else None
        if idx is None:
            return set()
        sel = match_part(idx, part_names)
        if len({s for s in sel if s is not None}) < min_hits:
            return set()
        return {n for n, s in zip(part_names, sel) if s is not None}


def _load_aliases(local_roots):
    sets = {}
    paths = [os.path.join(BUNDLED_DIR, "aliases.json")]
    paths += [os.path.join(sks_data_dir(r), "builtin", "aliases.json") for r in local_roots if r]
    for p in paths:
        data = _load_json(p)
        if isinstance(data, dict) and isinstance(data.get("sets"), dict):
            for set_name, mapping in data["sets"].items():
                if isinstance(mapping, dict):
                    t = sets.setdefault(set_name, {})
                    for a, c in mapping.items():
                        if isinstance(a, str) and isinstance(c, str):
                            t[norm(a)] = c
    return sets


def load_library(game_id, local_roots=()):
    registry = {}
    for folder, source in profile_dirs(game_id, local_roots):
        for path in _json_files(folder):
            data = _load_json(path)
            if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA:
                continue
            if data.get("game") is not None and data.get("game") != game_id:
                continue
            channels = data.get("channels")
            if channels is not None and not isinstance(channels, list):
                continue
            data["channels"] = channels or []
            base = os.path.splitext(os.path.basename(path))[0]
            pid = data["id"] if isinstance(data.get("id"), str) else base
            name = data["name"] if isinstance(data.get("name"), str) else pid
            registry[pid] = {"id": pid, "name": name, "source": source, "path": path, "data": data}
    return Library(registry, _load_aliases(local_roots))


_cache = {}


def _signature(game_id, local_roots):
    sig = []
    for folder, _src in profile_dirs(game_id, local_roots):
        for p in _json_files(folder):
            try:
                sig.append((p, os.path.getmtime(p)))
            except OSError:
                pass
    for r in local_roots:
        p = os.path.join(sks_data_dir(r), "builtin", "aliases.json") if r else ""
        if p and os.path.isfile(p):
            sig.append((p, os.path.getmtime(p)))
    return tuple(sig)


def library(game_id, local_roots=()):
    """Cached :func:`load_library`; reloads when any profile file changes."""
    local_roots = tuple(r for r in local_roots if r)
    key = (game_id, local_roots)
    sig = _signature(game_id, local_roots)
    hit = _cache.get(key)
    if hit is None or hit[0] != sig:
        hit = (sig, load_library(game_id, local_roots))
        _cache[key] = hit
    return hit[1]


# ── Finding the game ─────────────────────────────────────────────────────────

def _steam_libraries():
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            roots.append(winreg.QueryValueEx(k, "SteamPath")[0])
    except (ImportError, OSError):
        pass
    libs = []
    for root in roots:
        libs.append(root)
        try:
            with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as fh:
                for m in re.finditer(r'"path"\s+"([^"]+)"', fh.read()):
                    libs.append(m.group(1).replace("\\\\", "\\"))
        except OSError:
            pass
    seen, out = set(), []
    for lib in libs:
        k = os.path.normcase(os.path.normpath(lib))
        if k not in seen:
            seen.add(k)
            out.append(lib)
    return out


_game_dirs = {}


def find_game_dir(steam_folder):
    """The game's install folder from the Steam libraries, or None.  Looked up
    once per session."""
    if steam_folder not in _game_dirs:
        found = None
        for lib in _steam_libraries():
            d = os.path.join(lib, "steamapps", "common", steam_folder)
            if os.path.isdir(d):
                found = d
                break
        _game_dirs[steam_folder] = found
    return _game_dirs[steam_folder]


# ── Writing presets (Presets.lua layout) ─────────────────────────────────────

def safe_id(name):
    return re.sub(r'[\\/:*?"<>|]', "_", str(name or "")).strip()


def write_presets(mod_root, folder, rep_part, profile_id, sculpt_name, values):
    """Write ``mods/<folder>/sculpt/<name>.json`` (when *values*) and the model's
    binding ``mods/<folder>/<rep_part>.json`` under *mod_root*.

    The binding is not "global", so a part's own binding -- the player's in
    user/, or another mod's -- still wins over it (Presets.lua lookup order).
    Returns the paths written."""
    base = os.path.join(sks_data_dir(mod_root), "mods", safe_id(folder))
    written = []
    sculpt_id = safe_id(sculpt_name)
    if values and sculpt_id:
        path = os.path.join(base, "sculpt", sculpt_id + ".json")
        _dump(path, {"schema": SCULPT_SCHEMA, "name": sculpt_name,
                     "target": {"part": rep_part}, "values": values})
        written.append(path)
    binding = {"schema": BINDING_SCHEMA, "part": rep_part}
    if profile_id:
        binding["profile"] = profile_id
    if values and sculpt_id:
        binding["sculpt"] = sculpt_name
    if len(binding) > 2:
        path = os.path.join(base, safe_id(rep_part) + ".json")
        _dump(path, binding)
        written.append(path)
    return written


def _dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
