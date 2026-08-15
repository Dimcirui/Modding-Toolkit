"""MHWI -> MHWS rebuild, execution layer.

Crossing engines is a rebuild, not a conversion, and the shape of the rebuild is the
opposite of what the RE-to-RE port does.  ``mesh_port`` converts the source rig in
place: rename its bones, merge what the target lacks, *build* what the target needs.
Building bones by rule is the weak part -- placement comes from a table of anchors
rather than from the target game, and it showed: 89 helper bones inserted, up to
250 mm from where MHWilds actually puts them, six of them parentless because the
insert order is alphabetical rather than hierarchical.

So the skeleton is not converted here, it is **replaced**.  The output rig is
MHWilds' own reference skeleton -- correct names, hierarchy, helper set and
orientations by construction -- snapped onto the MHWI model's joint positions so it
takes the *model's* proportions.  Nothing is placed by rule and nothing can come out
parentless (user's design, 2026-08-15).

The order matters, and the first two steps are the only ones that touch the mesh::

    1. translate    rig + meshes up by SOLE_OFFSET_Z, so the sole planes meet
    2. thumbs       swing MHWI's thumbs onto MHWilds' splay, mesh follows
    3. reference    import MHWilds' reference model, merge its facial bones, T-pose
                    it, discard its body mesh
    4. snap         move the *reference's* bones onto the MHWI rig's joints,
                    position only -- the mesh is not touched
    5. assemble     a .mesh collection holding the snapped rig and the meshes,
                    rebound to it
    6. vertex groups renamed MHWI -> MHWilds
    7. physics      graft the model's own cloth/hair bones onto the new rig
    8. optimise     the two MHWilds skeleton passes

Steps 1 and 2 move the mesh and so go through ``core/pose_bake.py``; step 4 moves the
skeleton to the mesh instead, which is why it can be a plain rest edit and why the
2.6 cm the old direction lost at the ankle simply does not arise -- MHWilds' ankle is
2.6 cm lower than MHWI's above the sole, and here it is the ankle that moves.

Nearly every step is an existing operator; see ``docs/mhwi_mhws_port_notes.md``.
"""

import math

import bpy
from mathutils import Matrix, Vector

from . import bone_utils, mhwi_port, pose_bake, ref_model, ref_model_ops
from .bone_mapper import build_cross_game_map
from .i18n import T

SRC_PRESET = "mhwi_world.json"
DST_PRESET = "mhws.json"
DST_GAME = "MHWS"


# ── detection ───────────────────────────────────────────────────────────────────

def looks_like_mhwi(arm_obj):
    """True when a rig came out of MHW Model Editor.

    Checked on the *majority*, not on any one bone: a user who has renamed a few
    bones by hand should still be recognised, while an RE Engine rig that happens to
    carry one imported MHWI bone should not.
    """
    names = [b.name for b in arm_obj.data.bones]
    if not names:
        return False
    hits = sum(1 for n in names if mhwi_port.bone_id(n) is not None)
    return hits * 2 > len(names)


def is_mod3_collection(col):
    """MHW Model Editor tags and names its collections ``.mod3``, not ``.mesh``."""
    return col.get("~TYPE") == "MHW_MOD3_COLLECTION" or col.name.endswith(".mod3")


def bound_meshes(arm_obj):
    """Everything that travels with the rig, which is not the same set as everything
    it deforms -- see ``pose_bake.attached_meshes``.

    The port carries this set; ``pose_bake.bake_pose_to_rest`` deforms the narrower
    one on its own.  Getting that backwards in either direction is a real bug: the
    wide set for baking moves vertices nothing in the viewport moves, and the narrow
    set for carrying drops meshes out of the output entirely.
    """
    return pose_bake.attached_meshes(arm_obj)


def _activate(context, obj, *, selected=()):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for o in selected:
        o.hide_set(False)
        o.select_set(True)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


# ── 1. translate ────────────────────────────────────────────────────────────────

def translate_rig(arm_obj, dz):
    """Lift the armature and everything it deforms by *dz* in world Z.

    Applied to object transforms rather than to bone and vertex data: it is a rigid
    move of the whole assembly, so there is nothing to bake.  Meshes parented to the
    armature come along on their own; ones merely bound by modifier do not.
    """
    arm_obj.location.z += dz
    for obj in bound_meshes(arm_obj):
        if obj.parent is not arm_obj:
            obj.location.z += dz
    bpy.context.view_layer.update()


# ── 2. thumbs ───────────────────────────────────────────────────────────────────

def _pose_world_rotate(arm_obj, bone_name, axis, degrees):
    """Rotate a pose bone **about its own head** -- orientation only, no translation."""
    pb = arm_obj.pose.bones.get(bone_name)
    if pb is None:
        return False
    head = (arm_obj.matrix_world @ pb.bone.matrix_local).translation
    R = Matrix.Rotation(math.radians(degrees), 4, Vector(axis).normalized())
    world = Matrix.Translation(head) @ R @ Matrix.Translation(-head)
    pb.matrix = arm_obj.matrix_world.inverted() @ world @ arm_obj.matrix_world @ pb.matrix
    bpy.context.view_layer.update()
    return True


def rotate_thumbs(arm_obj, context=None):
    """Swing MHWI's thumbs onto MHWilds' splay, mesh included.

    MHWI's thumb phalanges run along the hand axis exactly like its other fingers
    (``Thumb2 -> Thumb3`` measures ``(1, 0, 0)``); MHWilds' are splayed.  Every other
    finger matches to 0.00 degrees, so this is the single place the two hands
    disagree, and it is why step 4 cannot be left to sort the thumb out on its own:
    the snap moves MHWilds' thumb bone onto whatever MHWI's thumb is doing, so
    without this the ported thumb would point along the hand and MHWilds' thumb
    animation -- authored against the splay, and deliberately exempt from T-pose
    zeroing for that reason -- would drive it wrong.

    Two rotations rather than one (user's decision, 2026-08-15): rotating only at the
    first joint would swing the whole thumb rigidly and keep MHWI's internal shape,
    while these two land each phalanx near its MHWilds direction.  Exact coincidence
    is not the goal and is not checked -- the snap in step 4 sets final positions.

    Rotation only, never translation: each bone turns about its own head, so a joint
    never leaves the place the model put it.
    """
    posed = 0
    for side in ("L", "R"):
        for bone_name, axis, degrees in mhwi_port.THUMB_ROTATIONS[side]:
            if _pose_world_rotate(arm_obj, bone_name, axis, degrees):
                posed += 1
    if posed:
        pose_bake.bake_pose_to_rest(arm_obj, context)
    return posed


# ── 3. the reference rig ────────────────────────────────────────────────────────

def import_reference_rig(context):
    """MHWilds' reference skeleton, facial bones merged and T-posed, mesh discarded.

    This is the state the "Import Reference Model" button produces with its first two
    options on, and it is the output rig -- so it is imported through the same code
    path rather than through ``ref_skeleton.import_reference_armature``, which keeps
    only the armature and would therefore have no vertex groups for the facial merge
    to act on.  The body mesh is dropped once the merges are done.

    Auxiliary bones are deliberately *not* merged: they are MHWilds' own helper
    system and the ported rig is supposed to have them.
    """
    ident = ref_model.MODELS.get(DST_GAME, ())
    if not ident:
        return None
    arm = ref_model_ops.import_model(DST_GAME, ident[0][0])
    if arm is None:
        return None
    ref_model_ops.apply_merges(arm, DST_GAME, True, False)
    _activate(context, arm)
    bpy.ops.modder.ree_to_tpose()

    for obj in list(bound_meshes(arm)):
        bpy.data.objects.remove(obj, do_unlink=True)
    return arm


# ── 4. snap the reference onto the model ────────────────────────────────────────

def snap_reference_to_model(context, model_arm, ref_arm):
    """Move *ref_arm*'s bones onto *model_arm*'s joints, position only.

    ``modder.universal_snap`` reads the two rigs through the bone presets, so it
    matches MHWI's ``MhBone_NNN`` against MHWilds' names by standard slot -- a plain
    name match would find nothing.  Its convention is that the **active** armature is
    the one that moves, which is the reference; the model rig is only read.

    Position only: taking direction and roll from MHWI would throw away the very
    thing the reference is here to supply, since MHWI stores no bone orientation at
    all (all 86 of its bones share one rest frame).
    """
    settings = context.scene.mhw_suite_settings
    saved = (settings.import_preset_enum, settings.target_preset_enum,
             settings.align_mode_override)
    try:
        settings.import_preset_enum = SRC_PRESET
        settings.target_preset_enum = DST_PRESET
        settings.align_mode_override = 'POS_ONLY'
        _activate(context, ref_arm, selected=(model_arm,))
        bpy.ops.modder.universal_snap()
    finally:
        (settings.import_preset_enum, settings.target_preset_enum,
         settings.align_mode_override) = saved


# ── 5. assemble the output collection ───────────────────────────────────────────

def assemble_collection(src_col, ref_arm, meshes):
    """A ``.mesh`` collection holding the new rig and the meshes, rebound to it.

    Tagged ``RE_MESH_COLLECTION`` because the output is a MHWilds model: every
    downstream check -- the RE exporter, the MDF tools, the pre-export check -- looks
    for that tag or the ``.mesh`` suffix, and a collection still carrying MHWI's
    ``MHW_MOD3_COLLECTION`` reads as the wrong engine to all of them.

    The colour is part of that: RE Mesh Editor stamps ``COLOR_01`` on every mesh
    collection it makes (``blender_re_mesh.py:694``, ``re_mesh_operators.py:158``), so
    a port without it is the one red-less collection in an outliner full of red ones
    -- it reads as "not really a mesh collection" even though every check passes.
    """
    stem = src_col.name
    for suffix in (".mod3", ".mesh"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    col = bpy.data.collections.new(f"{stem}_{DST_GAME}.mesh")
    col["~TYPE"] = "RE_MESH_COLLECTION"
    col.color_tag = "COLOR_01"

    parents = [c for c in bpy.data.collections if src_col.name in c.children]
    for parent in (parents or [bpy.context.scene.collection]):
        parent.children.link(col)

    for obj in [ref_arm] + list(meshes):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)

    for mesh in meshes:
        # Re-parenting must not move the mesh.  Step 1's lift lives in the *object*
        # transform of the rig the meshes were parented to, so they inherit it --
        # hand them to a different armature without preserving world space and the
        # 1.05 m silently comes back off, leaving the body at MHWI's height while the
        # skeleton stands at MHWilds'.  Setting matrix_parent_inverse is not enough:
        # it cancels the new parent, not the old one.
        world = mesh.matrix_world.copy()
        mesh.parent = ref_arm
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_world = world
        # Binds rather than merely retargets: a mesh that arrived with an empty-target
        # modifier, or with none at all, is one the port has just rescued from being
        # dropped -- leaving it unbound would put it in the output looking correct and
        # deforming with nothing.
        pose_bake.rebind(mesh, ref_arm)
    return col


# ── 6. vertex groups ────────────────────────────────────────────────────────────

def rename_vertex_groups(context, meshes):
    """Rename the meshes' vertex groups from MHWI names to MHWilds names.

    ``modder.direct_convert`` is the same button a user would press ("Rename Vertex
    Groups [X+Y]"), driven by the same two presets as the snap, so the groups end up
    named for exactly the bones the snap moved.  Physics groups are not in either
    preset and are left alone, which is what step 7 relies on.
    """
    settings = context.scene.mhw_suite_settings
    saved = (settings.import_preset_enum, settings.target_preset_enum)
    try:
        settings.import_preset_enum = SRC_PRESET
        settings.target_preset_enum = DST_PRESET
        if not meshes:
            return
        _activate(context, meshes[0], selected=meshes[1:])
        bpy.ops.modder.direct_convert()
    finally:
        settings.import_preset_enum, settings.target_preset_enum = saved

    # A group named for an MHWI base bone that the preset never mapped survives the
    # rename -- ``MhBone_000``, the origin, is the one this hits.  It names no bone on
    # the new rig, so it can only confuse the exporter's bone/group matching.
    # Physics groups are left alone: they are the ones step 7 grafts bones for.
    for mesh in meshes:
        for vg in list(mesh.vertex_groups):
            if mhwi_port.is_base_bone(vg.name):
                mesh.vertex_groups.remove(vg)


# ── 7. physics bones ────────────────────────────────────────────────────────────

def _physics_order(arm_obj):
    """Physics bone names, parents before children."""
    out = []

    def walk(bone):
        if mhwi_port.is_physics_bone(bone.name):
            out.append(bone.name)
        for c in bone.children:
            walk(c)

    for root in [b for b in arm_obj.data.bones if b.parent is None]:
        walk(root)
    return out


def transplant_physics(model_arm, ref_arm, name_map):
    """Copy the model's own cloth and hair bones onto the new rig.

    Safe to take world coordinates verbatim: step 4 has already moved the reference's
    joints onto the model's, so the two rigs coincide wherever they share a bone, and
    a physics bone's position relative to the body is the same in either.  That is
    also what "transplant as-is, relative to the parent" reduces to once the parent
    is in the right place.

    Which bones these are is decided by id window, not by name or by weights: MHWI
    restricts physics to ``mhwi_port.PHYSICS_ID_RANGES``, and a bone outside them has
    no physical effect in the game at all.  Their names are kept, because the chain
    file being rebuilt alongside will refer to them by the same name.

    Returns ``(made, orphans)``; an orphan is a physics bone whose parent resolved to
    nothing on the new rig, which is reported rather than guessed at.
    """
    names = _physics_order(model_arm)
    if not names:
        return 0, []

    src_bones = model_arm.data.bones
    to_ref = ref_arm.matrix_world.inverted() @ model_arm.matrix_world

    _activate(bpy.context, ref_arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ref_arm.data.edit_bones
    made, orphans = 0, []
    try:
        for name in names:
            if name in eb:
                continue
            src = src_bones[name]
            parent_name = src.parent.name if src.parent else None
            # A physics bone hangs off either another physics bone, which keeps its
            # name, or a base bone, which the snap renamed -- so the base case has to
            # go through the same mapping the snap used.
            if parent_name is not None and not mhwi_port.is_physics_bone(parent_name):
                parent_name = name_map.get(parent_name)
            parent = eb.get(parent_name) if parent_name else None
            if parent is None:
                orphans.append(name)
                continue
            new = eb.new(name)
            new.head = to_ref @ src.head_local
            new.tail = to_ref @ src.tail_local
            new.align_roll((to_ref @ src.matrix_local).to_3x3() @ Vector((0.0, 0.0, 1.0)))
            new.parent = parent
            new.use_connect = False
            made += 1
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return made, orphans


# ── 8. optimise ─────────────────────────────────────────────────────────────────

def optimize(context, arm_obj, meshes):
    """The two MHWilds skeleton passes, run as the user would run them by hand."""
    _activate(context, arm_obj, selected=meshes)
    bpy.ops.mhws.optimize_skeleton()
    _activate(context, arm_obj, selected=meshes)
    bpy.ops.mhws.optimize_aux_bones()


# ── operator ────────────────────────────────────────────────────────────────────

_collection_item_cache = []


def _collection_items(self, context):
    """EnumProperty items must outlive the call: Blender's C side keeps the pointers."""
    _collection_item_cache.clear()
    _collection_item_cache.extend(
        (c.name, c.name, "") for c in bpy.data.collections if is_mod3_collection(c))
    if not _collection_item_cache:
        _collection_item_cache.append(
            ("NONE", T("core.mhwi_port_ops.no_mod3_collection"), ""))
    return _collection_item_cache


class MHWI_OT_PortToMHWS(bpy.types.Operator):
    bl_idname = "mhwi.port_to_mhws"
    bl_label = "MHWI -> MHWilds"
    #: No 'UNDO', for the same reason as the mesh port and the reference importer:
    #: this creates and deletes objects through ``bpy.data``, so a redo-panel re-run
    #: would build a second model rather than revise the first.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mhwi_port_ops.desc")

    source_collection: bpy.props.EnumProperty(
        name="Source", items=_collection_items)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=430)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.mhwi_port_ops.source_collection"))
        box = layout.box()
        box.label(text=T("core.mhwi_port_ops.rebuild_note"), icon='INFO')

    def execute(self, context):
        col = bpy.data.collections.get(self.source_collection)
        arms = [o for o in col.objects if o.type == 'ARMATURE'] if col else []
        if len(arms) != 1:
            self.report({'ERROR'}, T("core.mhwi_port_ops.pick_collection"))
            return {'CANCELLED'}
        if not looks_like_mhwi(arms[0]):
            self.report({'ERROR'}, T("core.mhwi_port_ops.not_mhwi"))
            return {'CANCELLED'}

        cross = build_cross_game_map(SRC_PRESET, DST_PRESET)
        if cross is None:
            self.report({'ERROR'}, T("core.mhwi_port_ops.preset_load_failed"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Work on a copy: steps 1 and 2 rewrite mesh data, and the source model must
        # survive them intact.
        work_arm = bone_utils.duplicate_armature_with_meshes(
            arms[0], arms[0].name + "_port_tmp")
        work_meshes = bound_meshes(work_arm)

        # Bind the copies *before* anything moves, not at assembly time.  A mesh that
        # arrived with an empty modifier target is deformed by nothing, so the thumb
        # bake in step 2 would skip it -- and it would then be bound, at the end, to a
        # rig whose rest pose already carries the rotated thumb, leaving its own thumb
        # geometry where MHWI had it.  Binding here puts every mesh through every step.
        #
        # Only the copy is touched; the user's own model keeps whatever binding state
        # it had.  Harmless for the meshes that were already bound -- rebind retargets
        # in place rather than stacking a second modifier.
        for mesh in work_meshes:
            pose_bake.rebind(mesh, work_arm)

        translate_rig(work_arm, mhwi_port.SOLE_OFFSET_Z)
        thumbs = rotate_thumbs(work_arm, context)

        ref_arm = import_reference_rig(context)
        if ref_arm is None:
            # The mesh copies have to go too.  ``duplicate_armature_with_meshes``
            # links them into the *source's* collections, so leaving them behind
            # puts a second, unbound body in the user's own .mod3 collection --
            # which then reads as a two-mesh model on the next run.
            for obj in work_meshes:
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.objects.remove(work_arm, do_unlink=True)
            self.report({'ERROR'}, T("core.mhwi_port_ops.need_reference"))
            return {'CANCELLED'}

        snap_reference_to_model(context, work_arm, ref_arm)
        out_col = assemble_collection(col, ref_arm, work_meshes)
        rename_vertex_groups(context, work_meshes)
        grafted, orphans = transplant_physics(work_arm, ref_arm, dict(cross.mapping))

        bpy.data.objects.remove(work_arm, do_unlink=True)
        optimize(context, ref_arm, work_meshes)

        parts = [T("core.mhwi_port_ops.stat").format(
            name=out_col.name, thumbs=thumbs, bones=len(ref_arm.data.bones),
            grafted=grafted, meshes=len(work_meshes))]
        if orphans:
            parts.append(T("core.mhwi_port_ops.physics_orphans").format(
                n=len(orphans), names=", ".join(orphans[:8])))
        unknown = mhwi_port.partition(
            [b.name for b in arms[0].data.bones])["unknown"]
        if unknown:
            parts.append(T("core.mhwi_port_ops.unknown_ids").format(
                n=len(unknown), names=", ".join(unknown[:8])))
        self.report({'WARNING'} if (orphans or unknown) else {'INFO'},
                    "  ".join(parts))
        return {'FINISHED'}


classes = [MHWI_OT_PortToMHWS]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
