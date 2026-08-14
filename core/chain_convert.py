"""Cross-game chain/chain2 conversion, scene-side: re-attach colliders.

Why this works on bone *names* and not hashes: RE-Chain-Editor computes a
collider's ``jointNameHash`` at export time from the object's bone constraint --
``hash_wide(obj.constraints["BoneName"].subtarget)``
(``re_chain_propertyGroups.py``) -- and on import it *skips* any collider whose
hash resolves to no bone on the armature (``blender_re_chain.py``, which also
raises a warning).  So a collider that exists in the scene is always bound to a
real bone by name, and converting it means rewriting that name.  ``core/re_hash.py``
is not on this path; it is for offline file inspection and tests.

Scope is deliberately narrow.  Chain physics itself never attaches to base
skeleton bones -- only colliders do.  Node-side references (``jointHash``,
``constraintJntNameHash``, ``terminateNodeNameHash``) point at per-asset
hair/cloth bones that travel with the model, so their names, and therefore their
hashes, are already identical in the target game.  Measured on shipped files:
24/24 collider attach points resolve to standard skeleton bones, while 0/196
terminate-node hashes resolve against 5272 pooled bones from 21 armatures.

**Every other collider parameter is inherited verbatim, including the local offset.**
No axis-convention correction is applied even when crossing convention families, and
that is deliberate: a collider is positioned from **joint coordinates only** -- bone
rotation and twist do not enter -- and a capsule's axis comes from the positions of
its two joints (``jointNameHash`` and ``pairJointNameHash``), not from any rotation.
So the only thing that has to be right is that the bone a collider lands on means the
same body part, which is what the mapping above guarantees.  Positions need not match
a hand-made port exactly; colliders are coarse volumes (measured radii 37-144 mm) and
the small residual is the user's to nudge if it ever matters.

``core/bone_correction.py`` exists for the cases that *do* need C -- validating a
reference skeleton's pose, and converting skeletons, where bone orientation drives
skinning and animation.  It is intentionally not wired in here.

Validated against hand-made ground truth (one model shipped as MHWS, RE4R and
RE9 mods, authored independently per game): mapping the 18 MHWS collider attach
points gives, at bone-slot level, **no destination the author did not also use**
in either target -- every difference is a collider they chose to add or drop.
"""

import bpy

#: Collider object markers RE-Chain-Editor puts in ``obj["TYPE"]``.
COLLIDER_TYPES = frozenset({
    "RE_CHAIN_COLLISION_SINGLE",
    "RE_CHAIN_COLLISION_CAPSULE_ROOT",
})

#: Every object that makes up a collision shape, not just the two that carry a bone
#: binding: a capsule is a ROOT plus its two endpoint children, and moving the set
#: between containers has to move all three.  ``RE_CHAIN_LINK_COLLISION`` is
#: deliberately absent -- despite the name it belongs to a chain *link*, lives in
#: ``Chain Links - ...``, and is not a collision shape.
COLLISION_OBJECT_TYPES = frozenset({
    "RE_CHAIN_COLLISION_SINGLE",
    "RE_CHAIN_COLLISION_CAPSULE_ROOT",
    "RE_CHAIN_COLLISION_CAPSULE_START",
    "RE_CHAIN_COLLISION_CAPSULE_END",
})

#: The bone constraint RE-Chain-Editor binds every collider through.
BONE_CONSTRAINT = "BoneName"

#: Which physics file format each game reads.  ``.chain`` and ``.chain2`` are two
#: different container formats, not two spellings of one -- a ``.chain2`` handed to
#: RE4R is simply the wrong file.  Confirmed against docs/chain_chain2_plan.md and
#: against all three reference characters in the project's own scene.
CHAIN_EXT_BY_GAME = {"MHWS": ".chain2", "RE4": ".chain", "RE9": ".chain2"}

#: Extensions a chain-side collection name can carry, longest first so ``.chain2``
#: is never mistaken for ``.chain`` + a stray ``2``.
_CHAIN_EXTS = (".chain2", ".chain", ".clsp")

#: What RE-Chain-Editor's own createChainCollection stamps on a chain collection
#: (blender_re_chain.py:88-89); blender_re_clsp.py:361-362 uses the same colour with
#: ``RE_CLSP_COLLECTION``.  Both matter: re_chain_propertyGroups.py's collection poll
#: requires the ``~TYPE`` *and* a ``.chain``/``.clsp`` in the name, so a copy missing
#: either is invisible to every RE-Chain-Editor tool.
CHAIN_COLOR_TAG = "COLOR_02"
CHAIN_COLLECTION_TYPE = "RE_CHAIN_COLLECTION"
CLSP_COLLECTION_TYPE = "RE_CLSP_COLLECTION"

#: What the two sub-collections carry (blender_re_chain.py:813 and :943).  Note the
#: key is plain ``TYPE``, *not* the ``~TYPE`` the chain/clsp collections themselves
#: use -- checking only ``~TYPE`` makes these look like untagged plain collections.
CHAIN_COLLISION_COLLECTION_TYPE = "RE_CHAIN_COLLISION_COLLECTION"
CHAIN_LINK_COLLECTION_TYPE = "RE_CHAIN_LINK_COLLECTION"

#: Deliberately not carried onto a port.  RE-Chain-Editor uses ``~ASSETPATH`` to
#: decide where a collection exports to *automatically* (blender_re_chain.py:495,
#: blender_re_clsp.py:367).  A port's real destination is another game's directory
#: convention and is not knowable here -- and for a same-format port (MHWS -> RE9,
#: both ``.chain2``) an inherited path points at the *source file itself*, where an
#: automatic export would overwrite the original.  Better absent than plausibly wrong.
PORT_DROPPED_COLLECTION_PROPS = ("~ASSETPATH",)


def _copy_collection_props(src, dst):
    """Carry a collection's own custom properties onto its copy, minus the ones a
    port must not inherit.  Copies by key rather than a fixed list so a property
    RE-Chain-Editor adds later still survives a port."""
    for key in src.keys():
        if key in PORT_DROPPED_COLLECTION_PROPS:
            continue
        dst[key] = src[key]


def chain_stem(name):
    """``'char'`` from ``'char.chain'`` / ``'char.chain2'`` / ``'char.clsp'``."""
    for ext in _CHAIN_EXTS:
        if name.endswith(ext):
            return name[:-len(ext)]
    return name


def ported_chain_collection_name(source_name, target_game):
    """Name for *source_name*'s port to *target_game*.

    ``<stem>_<GAME><target's own extension>`` -- the extension comes from the
    **target** game, never from the source, so an MHWilds ``.chain2`` ported to
    RE4R comes out as ``.chain``.  Stem-then-suffix matches what
    mesh_port_ops.duplicate_mesh_collection does for ``.mesh``.
    """
    ext = CHAIN_EXT_BY_GAME.get(target_game, ".chain2")
    return f"{chain_stem(source_name)}_{target_game}{ext}"


class RemapReport:
    """What a re-attach pass did, or would do in a dry run.

    remapped        : [(obj_name, old_bone, new_bone)] -- bone actually changed
    unchanged       : count of bindings whose bone name is the same in both games
    unmapped        : [(obj_name, bone)] -- no cross-game mapping for this bone.
                      **This is the case to surface to the user**: exporting it
                      would hash a name the target skeleton does not have, and
                      the game would get a collider bound to nothing.  Node-side
                      pass-through is fine, collider-side is not.
    missing_in_target: [(obj_name, new_bone)] -- mapped, but the target armature
                      has no such bone (stale preset, or wrong armature passed)
    collapsed       : {new_bone: [old_bone, ...]} -- several distinct attach
                      points merged onto one target bone.  Their local offsets
                      may need compensating; measured ~28 mm for MHWilds
                      L_Knee/L_Shin, about 40 % of a typical capsule radius.
                      Must be measured per asset -- the sign flips between rigs.
    """

    def __init__(self):
        self.remapped = []
        self.unchanged = 0
        self.unmapped = []
        self.missing_in_target = []
        self.collapsed = {}

    @property
    def ok(self):
        """True when every collider binding landed on a bone the target has."""
        return not self.unmapped and not self.missing_in_target

    def summary(self):
        parts = [f"{len(self.remapped)} re-attached", f"{self.unchanged} unchanged"]
        if self.unmapped:
            parts.append(f"{len(self.unmapped)} UNMAPPED")
        if self.missing_in_target:
            parts.append(f"{len(self.missing_in_target)} MISSING IN TARGET")
        if self.collapsed:
            parts.append(f"{len(self.collapsed)} merged target bone(s)")
        return ", ".join(parts)


def _sibling_clsp_collection(collection):
    """The .clsp collection sharing *collection*'s own parent, if any.

    RE-Chain-Editor's own chain and CLSP importers each derive their collection
    name from their own source file's stem and independently look up the same
    parent collection (the armature's own mesh collection's parent) -- so two
    files sharing a stem land as siblings under it purely by naming coincidence,
    with no explicit link between them (confirmed against
    RE-Chain-Editor/blender_re_chain.py and blender_re_clsp.py's own import
    code). Some characters keep their actual collision shapes
    (RE_CHAIN_COLLISION_CAPSULE_*) in this separate .clsp collection instead of
    embedding them directly in the chain collection -- confirmed 2026-08-14
    against a real character whose .chain2 collection has zero collider objects
    of its own. Identified by ``~TYPE == "RE_CLSP_COLLECTION"``, the same tag
    RE-Chain-Editor itself stamps on import.
    """
    name = getattr(collection, "name", None)
    collections = getattr(getattr(bpy, "data", None), "collections", None)
    if name is None or collections is None:
        return None
    # A scene's own root ("Scene Collection" in the outliner) is a real
    # candidate parent too, but is not itself a member of bpy.data.collections
    # -- confirmed the hard way: duplicate_chain_collection links a fresh pair
    # of chain/.clsp copies there whenever its own caller passes no explicit
    # link_into, and without this, the lookup would find the sibling for an
    # *original* character (parented under a regular named collection) but
    # silently miss it for every *port* of one -- exactly the case this exists
    # to serve.
    scene_root = getattr(getattr(getattr(bpy, "context", None), "scene", None), "collection", None)
    candidates = list(collections) + ([scene_root] if scene_root is not None else [])
    parents = [c for c in candidates if name in {ch.name for ch in c.children}]
    # Stem must match, not merely "is a .clsp under the same parent": porting
    # links the copy in beside the original, so a parent can hold both
    # ``char.clsp`` and ``char_RE4.clsp`` -- taking whichever came first would
    # hand the port the *original's* colliders and silently remap those.
    stem = chain_stem(name)
    for parent in parents:
        for sib in parent.children:
            if sib.get("~TYPE") == CLSP_COLLECTION_TYPE and chain_stem(sib.name) == stem:
                return sib
    return None


def _collision_objects(collection):
    """Every collision-shape object anywhere under *collection* (ROOT plus the
    capsule endpoints), in a stable order."""
    return [o for o in collection.all_objects
            if o.get("TYPE") in COLLISION_OBJECT_TYPES]


def iter_collider_bindings(collection):
    """Yield ``(obj, constraint)`` for every collider bone binding in a collection.

    Capsule colliders keep their two endpoints as child objects, each with its own
    ``BoneName`` constraint, so children are walked too -- a capsule spans two
    bones and both ends need converting.

    Also checks a sibling .clsp collection (see _sibling_clsp_collection) --
    without it, a character whose collision shapes live there instead of in
    *collection* itself would silently report zero bindings, not an error.
    """
    collections = [collection]
    clsp = _sibling_clsp_collection(collection)
    if clsp is not None:
        collections.append(clsp)
    for col in collections:
        for obj in col.all_objects:
            if obj.get("TYPE") not in COLLIDER_TYPES:
                continue
            for candidate in (obj, *obj.children):
                con = candidate.constraints.get(BONE_CONSTRAINT)
                if con is not None and getattr(con, "subtarget", ""):
                    yield candidate, con


def remap_collider_attachments(collection, cross_map, target_armature=None,
                               dry_run=False):
    """Re-attach every collider in *collection* from the source game's bones to
    the target game's, using a ``CrossGameBoneMap`` from
    ``core.bone_mapper.build_cross_game_map``.

    *target_armature* is optional but strongly recommended: without it a mapping
    onto a bone the target rig lacks cannot be detected here, and the failure
    surfaces only in-game -- where, per the MHWmodfixer findings, broken chain
    physics fails *at boot only* and no static check catches it.

    Only the bone binding is rewritten.  Offsets, radii and every other parameter stay
    as authored -- see the module docstring for why an axis correction is neither
    applied nor needed here.

    With ``dry_run=True`` nothing is written; the report says what would happen.
    Use that to inspect a conversion before touching the scene.
    """
    report = RemapReport()
    target_bones = None
    if target_armature is not None and target_armature.type == 'ARMATURE':
        target_bones = set(target_armature.data.bones.keys())

    for obj, con in iter_collider_bindings(collection):
        old = con.subtarget
        new = cross_map.get(old)

        if new is None:
            report.unmapped.append((obj.name, old))
            continue

        if target_bones is not None and new not in target_bones:
            report.missing_in_target.append((obj.name, new))
            continue

        if new == old:
            report.unchanged += 1
        else:
            report.remapped.append((obj.name, old, new))
            if not dry_run:
                con.subtarget = new
                if target_armature is not None:
                    con.target = target_armature

        report.collapsed.setdefault(new, [])
        if old not in report.collapsed[new]:
            report.collapsed[new].append(old)

    report.collapsed = {new: sorted(olds)
                        for new, olds in report.collapsed.items() if len(olds) > 1}
    return report


#: Chain properties that hold an *object name* and therefore need remapping when a
#: chain collection is duplicated.  Audited against RE-Chain-Editor's property groups:
#: these two are the only object references in the whole chain data model.  Everything
#: else that is a string there is a bone name (``constraintJntName``, ``jointHash``),
#: a file path (``colliderFilterInfoPath``), a UI label or a type marker -- bone names
#: must follow the new armature, so they are deliberately left alone.
LINK_GROUP_REFS = ("chainGroupAObject", "chainGroupBObject")


def duplicate_chain_collection(collection, name, link_into=None):
    """Deep-copy a chain collection and return ``(new_collection, {old: new})``.

    Blender's own duplicate is not enough on its own: it remaps *pointer* references
    (constraint targets, parents) but cannot touch ``chainGroupAObject`` /
    ``chainGroupBObject``, which are object **names** in a StringProperty. It has no
    way to know those strings denote objects, so a naive duplicate silently leaves the
    copy's links bound to the *original* collection's groups.

    Objects are copied by hand rather than through ``bpy.ops.object.duplicate()`` so
    the old->new mapping is exact; the operator version only leaves ``.001`` suffixes
    to guess from.

    The copy is a *real* chain collection, not a bag of objects: it carries
    RE-Chain-Editor's own ``~TYPE``/colour tags (without both, its collection poll
    in re_chain_propertyGroups.py rejects it and every chain tool goes blind to it),
    and the ``Chain Links - ...`` / ``Chain Collisions - ...`` sub-collections are
    recreated as sub-collections rather than flattened into one level.

    The collision shapes are treated as **one** set that gets re-homed to wherever
    the *target* format actually uses them, rather than copied structure-for-structure:

    * Taken from the source's sibling .clsp when it has one, else from inside the
      chain collection itself.  Never both -- a .chain2 may carry its own internal
      collisions *and* have a .clsp, but the two are unrelated (the user authors
      shapes inside the .chain2 and exports them as a .clsp, which is why they look
      alike), and copying both would double every capsule.
    * ``.chain`` is chain2+clsp in one format and has no companion .clsp at all, so
      they go inline, into this copy's own ``Chain Collisions - ...``.
    * ``.chain2`` gets a sibling .clsp instead, stem-matched to this copy so
      re-porting cannot confuse it with the original's (see
      _sibling_clsp_collection).  Not its internal collisions: RE-Chain-Editor's
      .chain2 export drops their parameters, so shapes left there are close to
      useless, while a .clsp works directly in most cases.
    """
    parent = link_into
    if parent is None:
        parents = [c for c in bpy.data.collections
                   if collection.name in {ch.name for ch in c.children}]
        parent = parents[0] if parents else bpy.context.scene.collection

    new_col = bpy.data.collections.new(name)
    _copy_collection_props(collection, new_col)
    new_col.color_tag = CHAIN_COLOR_TAG
    new_col["~TYPE"] = CHAIN_COLLECTION_TYPE
    parent.children.link(new_col)

    mapping = {}
    originals = []

    def copy_objects(src_objs, dst_col):
        for obj in src_objs:
            copy = obj.copy()
            if obj.data is not None:
                copy.data = obj.data.copy()
            mapping[obj.name] = copy
            dst_col.objects.link(copy)
            originals.append(obj)

    def rename_child(child_name):
        # RE-Chain-Editor names these "Chain Links - <chain collection>", so the
        # copy's children have to follow the copy, not keep pointing at the original.
        return child_name.replace(collection.name, name) if collection.name in child_name \
            else f"{child_name} - {name}"

    def copy_tree(src_col, dst_col):
        # Collision shapes are placed by format below, not copied in place.
        copy_objects([o for o in src_col.objects
                      if o.get("TYPE") not in COLLISION_OBJECT_TYPES], dst_col)
        for child in src_col.children:
            if _collision_objects(child):
                continue
            new_child = bpy.data.collections.new(rename_child(child.name))
            new_child.color_tag = child.color_tag
            _copy_collection_props(child, new_child)
            dst_col.children.link(new_child)
            copy_tree(child, new_child)

    copy_tree(collection, new_col)

    clsp = _sibling_clsp_collection(collection)
    colliders = _collision_objects(clsp if clsp is not None else collection)
    if colliders:
        if name.endswith(".chain"):
            container = bpy.data.collections.new(f"Chain Collisions - {name}")
            container["TYPE"] = CHAIN_COLLISION_COLLECTION_TYPE
            new_col.children.link(container)
        else:
            container = bpy.data.collections.new(f"{chain_stem(name)}.clsp")
            container.color_tag = CHAIN_COLOR_TAG
            container["~TYPE"] = CLSP_COLLECTION_TYPE
            parent.children.link(container)
        copy_objects(colliders, container)

    # parents second: the whole set has to exist before it can be rewired, and a
    # parent outside the collection (the armature) is left pointing where it was
    for obj in originals:
        copy = mapping[obj.name]
        if obj.parent is not None:
            copy.parent = mapping.get(obj.parent.name, obj.parent)
            copy.matrix_parent_inverse = obj.matrix_parent_inverse.copy()

    remap_link_group_refs(new_col, {k: v.name for k, v in mapping.items()})
    return new_col, mapping


def remap_link_group_refs(collection, name_map):
    """Point every chain link in *collection* at the copied groups, not the originals.

    Returns the number of properties rewritten.  Values that are not object names are
    left alone: RE-Chain-Editor falls back to storing a raw hash as a digit string
    when it cannot find the group object, and that must survive untouched.
    """
    fixed = 0
    for obj in collection.all_objects:
        if obj.get("TYPE") != "RE_CHAIN_LINK":
            continue
        pg = getattr(obj, "re_chain_chainlink", None)
        if pg is None:
            continue
        for attr in LINK_GROUP_REFS:
            old = getattr(pg, attr, "")
            if old and old in name_map:
                setattr(pg, attr, name_map[old])
                fixed += 1
    return fixed


def collider_attach_bones(collection):
    """The distinct bone names every collider in *collection* is bound to.

    Handy for auditing an asset before conversion, and for comparing a converted
    result against a hand-made one.
    """
    return sorted({con.subtarget for _obj, con in iter_collider_bindings(collection)})
