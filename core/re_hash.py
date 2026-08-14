"""RE Engine bone-name hashing (murmur3 over UTF-16LE).

Chain files never store bone names — every joint reference is a 32-bit hash of
the name (``jointNameHash``, ``pairJointNameHash``, ``constraintJntNameHash``,
``jointHash``, ``terminateNodeNameHash``).  Cross-game chain conversion has to
recompute those hashes whenever a bone is renamed, so this primitive is a
prerequisite for it.

Deliberately dependency-free (no ``bpy``, no RE-Chain-Editor import) so it can
be unit-tested outside Blender and works even when no companion addon is
enabled.  RE-Chain-Editor ships an equivalent ``modules/pymmh3.py``;
``tests/test_re_hash.py`` asserts bit-exact agreement with it whenever the
checkout is present, which turns this duplication into a machine-checked
contract instead of drift waiting to happen.

Two notes on the upstream implementation, both verified numerically:

* pymmh3 ends with a signed->unsigned wraparound branch,
  ``-((v ^ 0xFFFFFFFF) + 1) & 0xFFFFFFFF``.  That expression is algebraically
  ``v`` again, so the branch is a no-op and is simply omitted here.  (Half of
  all bone names take it; every result is unchanged.)
* pymmh3 fakes UTF-16LE by inserting ``\\x00`` after each character and then
  encoding the result as UTF-8.  That matches real UTF-16LE for ASCII, but
  diverges for anything above U+007F (``髪`` becomes 3+1 bytes instead of 2).
  This module encodes properly as ``utf-16-le``.  Every bone name observed in
  shipped assets is ASCII, so the two agree in practice; the divergence is
  pinned by a test so it cannot change silently.
"""

_C1 = 0xCC9E2D51
_C2 = 0x1B873593
_DEFAULT_SEED = 0xFFFFFFFF

#: ``hash_wide("")``.  RE-Chain-Editor writes this into ``jointHash`` to mean
#: "no joint" (its own comment reads "Hash is of something that means None" --
#: the something is the empty string).  Real MHWilds chain2 files use it for
#: every node whose jointHash is unset.
NONE_HASH = 2180083513


def _fmix(h):
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def murmur3_32(data, seed=_DEFAULT_SEED):
    """murmur3 x86_32 over raw bytes, as RE Engine uses it (seed 0xFFFFFFFF)."""
    if isinstance(data, str):
        raise TypeError("murmur3_32 takes bytes; use hash_wide() for names")

    length = len(data)
    h1 = seed

    for start in range(0, (length // 4) * 4, 4):
        k1 = (data[start + 3] << 24 | data[start + 2] << 16
              | data[start + 1] << 8 | data[start])
        k1 = (k1 * _C1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * _C2) & 0xFFFFFFFF
        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    tail = length & 3
    if tail:
        i = (length // 4) * 4
        k1 = 0
        if tail >= 3:
            k1 ^= data[i + 2] << 16
        if tail >= 2:
            k1 ^= data[i + 1] << 8
        k1 ^= data[i]
        k1 = (k1 * _C1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * _C2) & 0xFFFFFFFF
        h1 ^= k1

    return _fmix(h1 ^ length)


def hash_wide(name, seed=_DEFAULT_SEED):
    """Hash a bone/joint name the way chain files store it.

    Returns an unsigned 32-bit int, matching the ``read_uint`` fields in
    RE-Chain-Editor's chain/chain2 parsers.
    """
    return murmur3_32(name.encode("utf-16-le"), seed)
