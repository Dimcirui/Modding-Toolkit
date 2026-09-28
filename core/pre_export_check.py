"""Pre-export check, rules layer: what counts as broken, and how to name it.

Three separate questions, deliberately kept apart from the operator that runs
them so each can be checked offline (``tests/test_pre_export_check.py``):

1. **Does a texture binding resolve?**  A path is fine if it is a vanilla game
   asset or if the file is actually on disk under the user's mod root.
   Anything else is a dangling reference the game will fail on.
2. **Do the meshes and the materials line up?**  RE Mesh derives a submesh's
   material name from its object name, so a mesh whose derived name matches no
   material -- or a material no mesh asks for -- is a broken export.
3. **Is a material name legal?**  Separate from (2) because an illegal name can
   match perfectly and still export wrong.

**The legality rules are not RE Mesh Editor's.**  Its exporter does
``name.split("__", 1)[1].split(".")[0]``, which truncates at the *first* dot --
so ``Mat.Body`` silently exports as ``Mat``.  Since people do name materials
that way, following the exporter's parse verbatim would make this check declare
a name fine and then have it export as something else.  This module instead
strips only Blender's own ``.NNN`` de-duplication suffix and judges the rest,
which is what the user actually typed.
"""

import os
import re

#: Blender's own de-duplication suffix -- ``.001``, never anything else.
_DEDUP_SUFFIX = re.compile(r'\.\d{3}$')

#: ``[LOD_n_]Group_x_Sub_y__<material name>``.  The material half is captured
#: raw, illegal characters and all: judging it is the next step's job, and a
#: name has to be *found* before it can be judged.  The index half is captured
#: too, so ``rebuild_mesh_name`` can put a corrected material name back behind
#: the same prefix instead of reconstructing it from parsed integers.
_MESH_NAME = re.compile(r'^(?P<prefix>(?:LOD_\d+_)?Group_\d+_Sub_\d+)__(?P<mat>.+)$')

#: The same shape with one underscore where there should be two -- by far the
#: most common way to get the format wrong, and worth its own message rather
#: than a generic "does not match".
_MESH_NAME_SINGLE = re.compile(
    r'^(?P<prefix>(?:LOD_\d+_)?Group_\d+_Sub_\d+)_(?P<mat>[^_].*)$')

# Reason codes. The operator turns these into translated text; keeping them as
# codes means the rules layer has no opinion about wording or language.
SPACE = 'space'
DOT = 'dot'
NON_ASCII = 'non_ascii'     # CJK, kana, fullwidth, accented letters, ...
SYMBOL = 'symbol'           # any other ASCII character outside [A-Za-z0-9_]
EMPTY = 'empty'
SINGLE_UNDERSCORE = 'single_underscore'

#: The only characters a material name may use (docs/pre_export_check_plan.md
#: §6.1).  Chinese material names do work in game -- the user has confirmed it --
#: but the rule is kept conservative on purpose, "以防万一".
_LEGAL = re.compile(r'^[A-Za-z0-9_]+$')

#: Texture binding verdicts.
TEX_OK = 'ok'              # a vanilla asset, or found on disk
TEX_MISSING = 'missing'    # neither vanilla nor present under the mod root
TEX_EMPTY = 'empty'        # the binding has no path at all

#: The two halves of ``TEX_OK``.  The report has to tell them apart even though
#: neither is a problem on its own: "no custom texture resolved anywhere" is the
#: signal that the mod root points somewhere wrong, and a mod that is entirely
#: vanilla-textured must not trip it (see ``texture_verdict``).
TEX_VANILLA = 'vanilla'    # a path in the game's own shipped asset list
TEX_FOUND = 'found'        # the user's own asset, present under the mod root

#: Texture *file* verdicts, for the ones that did resolve. Separate from the
#: binding verdicts above because they answer a different question: not "is the
#: file there" but "is the file itself built right".
TEXF_OK = 'ok'
TEXF_NOT_POW2 = 'not_pow2'      # a side that is not a power of two
TEXF_UNREADABLE = 'unreadable'  # no readable .tex header -- often a renamed .png/.dds

#: What the whole texture scan adds up to.
TEXV_OK = 'ok'
TEXV_ROOT_WRONG = 'root_wrong'   # nothing custom resolved -- wrong root, or no textures built
TEXV_MISSING = 'missing'         # some resolved, some did not -- genuinely absent files


#: Object-transform verdicts.  RE Mesh's exporter bakes ``obj.matrix_world``
#: into the mesh it writes (``blender_re_mesh.py``, ``evaluatedSubMeshData
#: .transform(subMeshWorldMatrix)``), unconditionally and without touching the
#: custom split normals.  ``Mesh.transform`` does not handle a negative
#: determinant for those: a custom normal is stored relative to a basis derived
#: from the surrounding geometry, and mirroring the geometry flips that basis,
#: so the same stored bytes decode to a different direction.  Measured on one
#: face mesh, only the matrix's sign changing: determinant +1 left the normals
#: 0 degrees out, determinant -1 left 76% of corners more than 90 degrees out.
#: The winding is *not* reordered, so this is not a corner-order problem and
#: triangulating first does not help -- that guards a different mechanism.
XFORM_OK = 'ok'
XFORM_MIRRORED = 'mirrored'      # negative determinant: normals die on export
XFORM_DEGENERATE = 'degenerate'  # a collapsed axis: nothing to export from


#: 判定"权重总和等于 1"的容差。量化到 255 / 1023 的导出器本身有 1/255 ≈ 0.004 的
#: 粒度，所以再严格没有意义；反过来 1e-4 足以把真正的作图偏差全捞出来（实测八具
#: VRChat 头像：偏差最大的一具均值 0.7247，最小非零总和 0.1034）。
WEIGHT_SUM_EPS = 1e-4


#: 上游 RE Mesh 导出时丢弃低于这个值的权重（``blender_re_mesh.py:1587/1597``，
#: 注释说再低引擎就会把顶点甩到原点）。所以「有没有有效权重」要在滤掉它们之后判：
#: 一个顶点的权重全都小于它，导出后照样是全零行——而全零行在 ``file_re_mesh.py:1810``
#: 被把差额 255 整个加到第 0 格，顶点 100% 跟着骨骼索引 0 走。
EXPORT_MIN_WEIGHT = 0.002


def classify_weight_sum(total, eps=WEIGHT_SUM_EPS):
    """``"ok"`` / ``"unweighted"`` / ``"under"`` / ``"over"``。

    ``unweighted`` 与 ``under`` 必须分开，因为处置完全不同：``under`` 归一化就能修，
    ``unweighted`` 是 0/0，归一化救不了——两个导出器都会为它写出全零权重行
    （RE Mesh Editor 与 mod3 都有 ``boneWeightsArray[weightSums == 0] = 0``），
    进游戏后那些顶点留在骨架原点。合成一条报，用户就分不出"顺手修掉"和"必须补权重"。
    """
    if total <= eps:
        return "unweighted"
    if total < 1.0 - eps:
        return "under"
    if total > 1.0 + eps:
        return "over"
    return "ok"


def classify_transform(determinant, eps=1e-9):
    """Verdict for an object's world matrix, from its determinant alone.

    The determinant is the whole question: what breaks is the *sign*, and a
    mirror, a single negative scale axis and three negative axes all reach it
    the same way, so there is nothing else to inspect.
    """
    if determinant is None or abs(determinant) <= eps:
        return XFORM_DEGENERATE
    return XFORM_MIRRORED if determinant < 0 else XFORM_OK


def strip_dedup_suffix(name):
    """``Foo.001`` -> ``Foo``.  Only the trailing three-digit suffix Blender
    adds itself; a dot anywhere else is the user's own and is a finding, not
    something to quietly remove."""
    return _DEDUP_SUFFIX.sub('', name or '')


def parse_mesh_name(obj_name):
    """``(material_name, how)`` for a mesh object name.

    *how* is ``'format'`` when the name is the proper
    ``Group_x_Sub_y__Name``, ``'single_underscore'`` when it is that shape with
    one underscore instead of two, and ``'no_format'`` when it is neither -- in
    which case *material_name* is None and the caller falls back to the object's
    Blender material, the same fallback RE Mesh's exporter uses.
    """
    stripped = strip_dedup_suffix(obj_name)
    m = _MESH_NAME.match(stripped)
    if m:
        return m.group('mat'), 'format'
    m = _MESH_NAME_SINGLE.match(stripped)
    if m:
        return m.group('mat'), 'single_underscore'
    return None, 'no_format'


def name_problems(name):
    """Reason codes for a material name, empty list when it is fine.

    Order is stable so a report reads the same way twice.
    """
    if not name:
        return [EMPTY]
    if _LEGAL.match(name):
        return []
    out = []
    if ' ' in name:
        out.append(SPACE)
    if '.' in name:
        out.append(DOT)
    if any(ord(ch) > 127 for ch in name):
        out.append(NON_ASCII)
    if any(ord(ch) <= 127 and ch not in ' .' and not (ch.isalnum() or ch == '_') for ch in name):
        out.append(SYMBOL)
    return out


# ── Transliteration to a legal name ──────────────────────────────────────────

#: Hepburn romaji for kana, hiragana and katakana alike (katakana are folded to
#: hiragana first).  Two-character entries are the ゃゅょ digraphs.
_KANA = {
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    'わ': 'wa', 'ゐ': 'i', 'ゑ': 'e', 'を': 'o', 'ん': 'n', 'ゔ': 'vu',
    'ぁ': 'a', 'ぃ': 'i', 'ぅ': 'u', 'ぇ': 'e', 'ぉ': 'o', 'ゎ': 'wa',
    'ゃ': 'ya', 'ゅ': 'yu', 'ょ': 'yo',
}
_KANA_DIGRAPH = {'ゃ': 'a', 'ゅ': 'u', 'ょ': 'o'}
_SOKUON = 'っ'
_CHOON = 'ー'


def _is_kana(ch):
    return 'ぁ' <= ch <= 'ヿ' and ch not in '・'


def _romaji(run):
    """A run of kana as one romaji word: ``スカート`` -> ``sukaato``."""
    hira = ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in run)
    out = []
    i = 0
    double = False
    while i < len(hira):
        c = hira[i]
        if c == _SOKUON:
            double = True
            i += 1
            continue
        if c == _CHOON:
            if out and out[-1]:
                out.append(out[-1][-1])
            i += 1
            continue
        syl = _KANA.get(c, '')
        nxt = hira[i + 1] if i + 1 < len(hira) else ''
        if nxt in _KANA_DIGRAPH and syl.endswith('i') and len(syl) > 1:
            # きゃ kya, しゃ sha, ちゃ cha, じゃ ja
            base = syl[:-1]
            syl = (base if base in ('sh', 'ch', 'j') else base + 'y') + _KANA_DIGRAPH[nxt]
            i += 1
        if double and syl:
            syl = ('t' if syl.startswith('ch') else syl[0]) + syl
        double = False
        out.append(syl)
        i += 1
    return ''.join(out)


_pinyin = {}


def _pinyin_table():
    """{ideograph: syllable}, baked from Unicode Unihan's kMandarin field
    (``assets/pinyin_kmandarin.txt``, see ``scripts/bake_pinyin.py``).
    Japanese-only forms (髪, 顔) are in it too; they read as Mandarin, which is
    legal and distinguishable, if not what a Japanese reader would say."""
    if not _pinyin:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "assets", "pinyin_kmandarin.txt")
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith('#') or '\t' not in line:
                        continue
                    syl, chars = line.rstrip('\n').split('\t', 1)
                    for ch in chars:
                        _pinyin[ch] = syl
        except OSError:
            _pinyin[''] = ''    # remember the miss; CJK then falls through to '_'
    return _pinyin


def _translit(name):
    """Steps 2-6 of §6.1: fullwidth folded, accents dropped, kana to romaji,
    ideographs to capitalised pinyin, anything else to ``_``."""
    import unicodedata
    s = unicodedata.normalize('NFKC', name)
    table = _pinyin_table()
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isascii():
            out.append(ch if (ch.isalnum() or ch == '_') else '_')
            i += 1
            continue
        if _is_kana(ch) or (ch == _CHOON and out):
            j = i
            while j < len(s) and (_is_kana(s[j]) or s[j] == _CHOON):
                j += 1
            word = _romaji(s[i:j])
            out.append(word[:1].upper() + word[1:])
            i = j
            continue
        syl = table.get(ch)
        if syl:
            out.append(syl[:1].upper() + syl[1:])
            i += 1
            continue
        plain = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
        out.append(plain if plain.isascii() and plain.isalnum() else '_')
        i += 1
    return ''.join(out)


def is_ascii_name(name):
    """Bone and vertex-group rule (docs/pre_export_check_plan.md §6.2): ASCII
    only.  Looser than the material rule on purpose -- spaces and ASCII
    punctuation hash the same in RE Chain Editor and the engine, so they are
    left alone; only characters above U+007F break the chain hash."""
    return all(ord(ch) < 128 for ch in (name or ''))


def ascii_name(name):
    """*name* with only its non-ASCII runs transliterated, ASCII kept verbatim
    (``头发_00`` -> ``TouFa_00``, ``Hair.L 左`` -> ``Hair.L Zuo``)."""
    out = []
    run = []
    for ch in name or '':
        if ord(ch) < 128:
            if run:
                out.append(_translit(''.join(run)))
                run = []
            out.append(ch)
        else:
            run.append(ch)
    if run:
        out.append(_translit(''.join(run)))
    s = ''.join(out)
    return s if s.strip('_ ') else 'Bone'


def allocate_ascii_names(names, taken):
    """``{non-ASCII name: ASCII name}``, each new name unique against *taken*
    (every bone name in every armature involved) and against each other, so
    the same old name maps to the same new one in every armature."""
    taken = set(taken)
    out = {}
    for old in names:
        if old in out or is_ascii_name(old):
            continue
        base = ascii_name(old)
        new, k = base, 2
        while new in taken:
            new, k = f"{base}_{k}", k + 1
        taken.add(new)
        out[old] = new
    return out


def fix_name(name):
    """A legal name for *name* (``docs/pre_export_check_plan.md`` §6.1, steps
    1-7; step 8, collisions, needs the other names and lives in
    ``plan_name_fixes``).  Readability is aimed for, not guaranteed:
    ``头发_00`` -> ``TouFa_00``, ``スカート`` -> ``Sukaato``, ``Mat.Body 2`` ->
    ``Mat_Body_2``.  The result always passes ``name_problems``.
    """
    s = _translit(strip_dedup_suffix(name or ''))
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'Mat'


def rebuild_mesh_name(obj_name, new_mat):
    """*obj_name* with its material half replaced by *new_mat*, or None when the
    name has no ``Group_x_Sub_y`` prefix to keep.

    Also the one place the single-underscore slip is repaired: the rebuilt name
    always uses ``__``, so fixing a name and fixing the separator are the same
    operation rather than two passes that could disagree.

    Blender's own ``.NNN`` suffix is dropped rather than carried across -- it is
    a de-duplication artifact, and if the new name still collides Blender adds a
    fresh one on assignment.
    """
    stripped = strip_dedup_suffix(obj_name)
    m = _MESH_NAME.match(stripped) or _MESH_NAME_SINGLE.match(stripped)
    if not m:
        return None
    return f"{m.group('prefix')}__{new_mat}"


def _allocate(names):
    """``{illegal name: legal name}`` over one collection's names -- step 8 of
    §6.1.  One new name per old name (so mdf, meshes and datablocks agree), and
    none equal to a legal name already present or to another old name's new
    one: ``头发`` and ``頭髪`` both transliterate to ``TouFa``, so the second
    becomes ``TouFa_2``.  Resolving it here rather than leaving it to the
    re-check keeps a fix from manufacturing a duplicate-material error.
    """
    taken = {n for n in names if not name_problems(n)}
    out = {}
    for old in names:
        if not name_problems(old):
            continue
        base = fix_name(old)
        new, k = base, 2
        while new in taken:
            new, k = f"{base}_{k}", k + 1
        taken.add(new)
        out[old] = new
    return out


def plan_name_fixes(material_names, mesh_entries):
    """Every rename one "fix the names" pass should make, in three buckets.

    *mesh_entries* is ``[(object_name, derived_material_name, how)]`` as
    ``parse_mesh_name`` classifies them.  Returns::

        {'materials':  {old_material_name: new},   # mdf Material Name fields
         'objects':    {old_object_name: new},     # mesh object renames
         'datablocks': {old_material_name: new}}   # Blender material datablocks

    **The three have to move together.**  Renaming only the mdf material breaks
    the very match the check exists to protect: the meshes still carry the old
    name in their own object names, so a material that matched before the fix
    dangles after it.  So a corrected name is computed once, per *name*, and
    then applied everywhere that name occurs on either side.

    ``datablocks`` is separate because it is the one bucket with reach beyond
    the collections being checked -- those are meshes whose object name carries
    no ``Group_x_Sub_y__`` at all, so their material comes from the Blender
    material datablock, which other objects anywhere in the file may share. The
    caller is expected to say so in the report rather than rename silently.

    Two bad names can correct to the same good one (``My Mat`` and ``My.Mat``
    both become ``My_Mat``). That is not special-cased: the re-check that runs
    right after a fix reports the result as a duplicate material, which is both
    true and more useful than refusing to fix either.
    """
    # Every name either side uses, in first-seen order so the plan is stable.
    all_names = list(dict.fromkeys(
        list(material_names) + [m for _o, m, _h in mesh_entries if m]))
    renames = _allocate(all_names)

    known_materials = set(material_names)
    materials = {old: new for old, new in renames.items() if old in known_materials}

    objects = {}
    datablocks = {}
    for obj_name, mat_name, how in mesh_entries:
        if how == 'no_format':
            # Nothing to rebuild -- there is no prefix to keep and no indices to
            # invent. Only the datablock the name fell back to can be corrected.
            if mat_name in renames:
                datablocks[mat_name] = renames[mat_name]
            continue
        rebuilt = rebuild_mesh_name(obj_name, renames.get(mat_name, mat_name))
        # Compared against the *stripped* name so a rename is proposed only for
        # a real change, not for dropping a .001 that Blender will re-add.
        if rebuilt and rebuilt != strip_dedup_suffix(obj_name):
            objects[obj_name] = rebuilt

    return {'materials': materials, 'objects': objects, 'datablocks': datablocks}


def normalize_tex_path(path):
    """What the path becomes once the exporter has written it.

    Upstream RE Mesh's ``fixTexPath`` (``modules/mdf/blender_re_mdf.py:405``) runs
    on every binding at mdf export, so judging the raw string would report paths
    the exporter fixes on its own.  Mirrored rule for rule -- including the parts
    that look odd, because they are what actually gets written:

    - backslashes become ``/``
    - everything from the first ``.tex`` on is cut and ``.tex`` re-appended --
      case-sensitive, and *unconditionally*, so ``foo.png`` is written as
      ``foo.png.tex`` (which then, correctly, resolves to nothing)
    - if some path segment is exactly ``natives`` (any case), it and the segment
      after it go, along with everything before; a ``natives`` substring inside
      another segment leaves the path alone (upstream's lookup finds no index and
      its ``except`` returns the path unchanged)
    - ``.rtex`` is left untouched

    Two deliberate differences, both about *classifying* rather than exporting:
    an empty path stays empty (upstream would write ``.tex``; the check reports
    empties as their own group), and a leading ``/`` is dropped, as
    ``resolve_disk_path`` does anyway.  ``tests/test_pre_export_report.py`` runs
    upstream's own source against this over a set of paths.
    """
    p = (path or '').strip()
    if not p or p.endswith('.rtex'):
        return p
    p = p.replace('\\', '/')
    p = p.split('.tex')[0] + '.tex'
    if 'natives' in p.lower():
        parts = [s for s in p.split('/') if s]
        idx = next((i for i, s in enumerate(parts) if s.lower() == 'natives'), None)
        if idx is not None:
            p = '/'.join(parts[idx + 2:])
    return p.lstrip('/')


#: Source-image extensions: a binding ending in one of these points at a texture
#: that was never converted, which is a finding, not a spelling to tidy.
_IMAGE_EXTS = ('.dds', '.png', '.tga', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')


def fix_tex_path(path):
    """The path the auto-fix writes back (``docs/pre_export_check_plan.md`` §3.6).

    Same as ``normalize_tex_path`` except that a path ending in a source-image
    extension is left alone -- upstream would write ``foo.png.tex``, which only
    hides that the texture was never built.  Empty paths are left alone too;
    filling them is a separate fix.
    """
    p = (path or '').strip()
    if not p or p.lower().endswith(_IMAGE_EXTS):
        return path
    return normalize_tex_path(p)


def pair_unmatched(unmatched, unused):
    """Split dangling names into likely pairs and genuine leftovers.

    *unmatched* is ``[(object_name, derived_material_name)]`` for meshes whose
    material is missing, *unused* the mdf material names no mesh asks for.  A
    half-done rename leaves one of each, and reporting them as two separate
    problems hides that they are the same one.  Pairs are taken in order of
    confidence: names equal ignoring case, then names equal once both are
    legalised, then -- only when exactly one is left on each side -- the two
    leftovers.  Returns ``(pairs, rest_meshes, rest_materials)`` with
    ``pairs = [(object_name, derived_name, mdf_name)]``.
    """
    meshes = list(unmatched)
    mats = list(unused)
    pairs = []
    for key in (lambda n: (n or '').lower(), lambda n: fix_name(n or '').lower()):
        for entry in list(meshes):
            want = key(entry[1])
            hit = next((m for m in mats if key(m) == want), None)
            if hit is not None:
                pairs.append((entry[0], entry[1], hit))
                meshes.remove(entry)
                mats.remove(hit)
    if len(meshes) == 1 and len(mats) == 1:
        pairs.append((meshes[0][0], meshes[0][1], mats[0]))
        meshes, mats = [], []
    return pairs, meshes, mats


def classify_tex_binding(path, vanilla_set, exists_fn):
    """``TEX_VANILLA`` / ``TEX_FOUND`` / ``TEX_MISSING`` / ``TEX_EMPTY``.

    *exists_fn* takes the mdf-relative path and answers whether the file is
    present under the mod root -- injected rather than doing the disk walk here
    so the rules stay testable without a mod on disk.
    """
    if not (path or '').strip():
        return TEX_EMPTY
    norm = path.replace('\\', '/').lower()
    if norm in vanilla_set:
        return TEX_VANILLA
    return TEX_FOUND if exists_fn(path) else TEX_MISSING


def is_power_of_two(v):
    return v > 0 and (v & (v - 1)) == 0


def classify_tex_size(size):
    """``TEXF_OK`` / ``TEXF_NOT_POW2`` / ``TEXF_UNREADABLE`` for one resolved
    texture, given ``(width, height)`` or ``None``.

    Both sides have to be a power of two.  The looser rule the block formats
    actually enforce is "a multiple of four", but every non-power-of-two size is
    worth flagging anyway -- mip chains stop halving cleanly -- and one rule
    means one message instead of two tiers the user then has to rank.

    ``None`` (the header would not parse) is a finding rather than a silent
    skip: a file under the mod root that is not a .tex is usually one that was
    renamed instead of converted, and the export will happily point at it.
    """
    if size is None:
        return TEXF_UNREADABLE
    w, h = size
    return TEXF_OK if (is_power_of_two(w) and is_power_of_two(h)) else TEXF_NOT_POW2


def classify_tex_path(path, vanilla_set, exists_fn):
    """``TEX_OK`` / ``TEX_MISSING`` / ``TEX_EMPTY`` for one binding -- the
    coarse view, for callers that only care whether the path resolves."""
    verdict = classify_tex_binding(path, vanilla_set, exists_fn)
    return TEX_OK if verdict in (TEX_VANILLA, TEX_FOUND) else verdict


def texture_verdict(n_found, n_missing):
    """What to *say* about a texture scan, given how many of the user's own
    textures resolved and how many did not.

    The distinction the user asked for: when nothing custom resolved at all, the
    likely cause is a mod root pointing at the wrong directory (or textures that
    were never built), and listing forty paths that are all wrong for the same
    single reason buries that. When some resolved and some did not, the ones
    that did not are genuinely missing files and every one is worth naming.

    Known limit, accepted deliberately: a mod that is almost entirely vanilla
    textures and is missing only its own one or two files lands in
    ``TEXV_ROOT_WRONG`` and gets told to check its mod root. *n_found* counts
    only custom textures, so there is no vanilla count that could separate the
    two cases -- the mod really does have zero resolving custom textures.
    """
    if n_missing == 0:
        return TEXV_OK
    return TEXV_ROOT_WRONG if n_found == 0 else TEXV_MISSING


def match_meshes_to_materials(mesh_entries, material_names):
    """``(unmatched_meshes, unused_materials)``.

    *mesh_entries* is ``[(object_name, derived_material_name)]`` and
    *material_names* the mdf collection's material names.  A mesh may share a
    material with others and a material may serve several meshes, but neither
    side may dangle: a mesh with no material does not export, and a material no
    mesh asks for is dead weight that usually means a rename went half-done.
    """
    available = set(material_names)
    used = set()
    unmatched = []
    for obj_name, mat_name in mesh_entries:
        if mat_name in available:
            used.add(mat_name)
        else:
            unmatched.append((obj_name, mat_name))
    unused = [m for m in material_names if m not in used]
    return unmatched, unused


def duplicate_material_names(material_names):
    """Names appearing more than once in one .mdf2 collection."""
    seen, dupes = set(), []
    for n in material_names:
        if n in seen and n not in dupes:
            dupes.append(n)
        seen.add(n)
    return dupes


def resolve_disk_path(natives_root, mdf_path, tex_version):
    """Where a binding's ``.tex`` should sit under the user's mod root.

    Mirrors ``core/mdf_port_tex.resolve_source_disk_path``; kept as its own
    small function so this module does not pull the port in.
    """
    rel = (mdf_path or '').replace('\\', '/').lstrip('/')
    return os.path.join(natives_root, 'natives', 'STM', *rel.split('/')) + f'.{tex_version}'
