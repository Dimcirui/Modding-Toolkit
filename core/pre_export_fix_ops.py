"""Pre-export check, the fix buttons: one operator per repair the report offers.

Design: ``docs/pre_export_check_plan.md`` §5.  Every button here is a fallback
for something auto-fix cannot decide on its own, so none of them carries
options beyond what the repair strictly needs, and every one re-runs the check
in place afterwards (the report dialog stays open across an operator button,
measured in 5.1.2) so the user sees the problem dissolve -- or turn into the
next, smaller one.

The inputs come from ``pre_export_check_ops._LAST_RUN``, the same record the
report was built from, and each operator recomputes what it touches from the
scene rather than trusting report text.
"""

import re

import bpy
from bpy.props import CollectionProperty, EnumProperty, IntProperty, StringProperty

from .i18n import T
from . import pre_export_check as pc
from . import pre_export_check_ops as pec
from . import export_autofix
from . import mdf_layouts

_K = "core.pre_export_fix_ops."

_PREFIX = re.compile(r'^(LOD_\d+_)?Group_(\d+)_Sub_(\d+)')


def _pairs():
    return pec._pairs_from_last_run()


def _finish(op, context, key, n, **fmt):
    """Common tail: undo step, re-check in place, one line of feedback."""
    if n:
        bpy.ops.ed.undo_push(message=op.bl_label)
    pec._rerun_and_store(context)
    op.report({'INFO'}, T(_K + key).format(n=n, **fmt))
    return {'FINISHED'}


def _object_mode(context):
    if context.view_layer.objects.active is not None and context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


# ── Material names ───────────────────────────────────────────────────────────

class MODDER_OT_PecAlignNames(bpy.types.Operator):
    """「按 mdf 材质名对齐」: each "mesh wants X, mdf has Y" pair is resolved in
    favour of the mdf, whose Material Name is a fixed string slot and the more
    stable side (user's call): the mesh's name behind ``__`` becomes Y.  A mesh
    with no ``Group_x_Sub_y__`` name gets its fallback Blender material renamed
    instead, as the exporter reads that one."""
    bl_idname = "modder.pec_align_names"
    bl_label = "Align to mdf Names"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "align_desc")

    def execute(self, context):
        n = 0
        for _label, mdf, mesh in _pairs():
            if mesh is None:
                continue
            m = pec.material_matching(pec._mdf_materials(mdf), pec._mesh_objects(mesh))
            for obj_name, _want, have in m['paired']:
                obj = bpy.data.objects.get(obj_name)
                if obj is None:
                    continue
                new = pc.rebuild_mesh_name(obj_name, have)
                if new:
                    obj.name = new
                    n += 1
                    continue
                slots = [s for s in obj.data.materials if s is not None]
                if slots:
                    slots[0].name = have
                    n += 1
        return _finish(self, context, "align_done", n)


def _next_sub(mesh_col, lod, group):
    used = []
    for o in mesh_col.all_objects:
        m = _PREFIX.match(pc.strip_dedup_suffix(o.name))
        if m and (m.group(1) or '') == lod and int(m.group(2)) == group:
            used.append(int(m.group(3)))
    return max(used) + 1 if used else 0


def separate_and_rename(context, obj, mesh_col):
    """Split *obj* per material and name the new fragments
    ``[LOD_n_]Group_<g>_Sub_<n>__<Blender material>``.

    Same scheme as RE Mesh Editor's ``re_mesh.rename_meshes``, written here to
    avoid its four problems (§5.2.3): Sub numbering continues after the
    group's highest instead of restarting at 0, a ``LOD_n_`` prefix is kept,
    only Blender's .NNN is dropped from the material name (a real dot stays
    for the legality check to report), and only these fragments are touched.
    The original name goes to whichever piece carries the material that name
    referred to -- *not* necessarily the source object: Blender's separate
    leaves an arbitrary material on the source (measured in 5.1.2: the second
    one), and keeping the name on the source then named two pieces after the
    same material and lost the other.  Every other piece is named after its own.
    """
    from .mesh_utils import separate_by_materials
    orig_name = obj.name
    wanted, _how = pec._derived_material(obj)
    before = set(bpy.data.objects)
    separate_by_materials(context, [obj], rename=False, prune_keys=True,
                          prune_groups=True, clean_suffix=False)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    pieces = [obj] + new

    def mat_of(piece):
        mats = pec.used_materials(piece)
        return pc.strip_dedup_suffix(mats[0].name) if mats else "NO_MATERIAL"

    holder = next((p for p in pieces if mat_of(p) == wanted), None) or obj
    m = _PREFIX.match(pc.strip_dedup_suffix(orig_name))
    lod, group = ((m.group(1) or ''), int(m.group(2))) if m else ('', 0)
    nxt = _next_sub(mesh_col, lod, group)
    renamed = []
    if holder is not obj:
        obj.name = orig_name + "__MTK_TMP"
        holder.name = orig_name
        holder.data.name = orig_name
    for piece in pieces:
        if piece is holder:
            continue
        piece.name = f"{lod}Group_{group}_Sub_{nxt}__{mat_of(piece)}"
        piece.data.name = piece.name
        renamed.append(piece)
        nxt += 1
    return renamed


class MODDER_OT_PecSeparateRecheck(bpy.types.Operator):
    """「分离并重新检查」 for meshes behind one material name that show several
    base colours: split per material, name the pieces, re-check.  The one vague
    problem turns into specific ones (illegal names, missing materials) that
    each have a fix of their own."""
    bl_idname = "modder.pec_separate_recheck"
    bl_label = "Separate and Re-check"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "separate_desc")

    def execute(self, context):
        _object_mode(context)
        n = 0
        for _label, _mdf, mesh in _pairs():
            if mesh is None:
                continue
            for obj in pec._mesh_objects(mesh):
                mats = pec.used_materials(obj)
                if len(mats) > 1 and pec.distinct_base_colors(mats) > 1:
                    n += len(separate_and_rename(context, obj, mesh))
        return _finish(self, context, "separate_done", n)


class MODDER_OT_PecFixUnusedByBlender(bpy.types.Operator):
    """「按 Blender 材质修复」: an unused mdf material whose name a mesh's
    Blender material carries.  A mesh using several materials is separated (the
    fragment named after this one then matches); a single-material mesh has its
    name behind ``__`` set to it."""
    bl_idname = "modder.pec_fix_unused_blender"
    bl_label = "Fix by Blender Material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "unused_blender_desc")

    def execute(self, context):
        _object_mode(context)
        n = 0
        for _label, mdf, mesh in _pairs():
            if mesh is None:
                continue
            meshes = pec._mesh_objects(mesh)
            m = pec.material_matching(pec._mdf_materials(mdf), meshes)
            done = set()
            for name in m['open_mats']:
                for obj in pec.unused_by_blender_material(name, meshes, m['mat_names']):
                    if obj.name in done:
                        continue
                    done.add(obj.name)
                    if len(pec.used_materials(obj)) > 1:
                        separate_and_rename(context, obj, mesh)
                    else:
                        new = pc.rebuild_mesh_name(obj.name, name)
                        obj.name = new or f"Group_0_Sub_{_next_sub(mesh, '', 0)}__{name}"
                    n += 1
        return _finish(self, context, "unused_blender_done", n)


class MODDER_OT_PecDeleteUnused(bpy.types.Operator):
    """「删除多余材质」: drop the mdf materials no mesh asks for, then let RE
    Mesh Editor renumber the rest."""
    bl_idname = "modder.pec_delete_unused"
    bl_label = "Delete Unused Materials"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "delete_unused_desc")

    def execute(self, context):
        n = 0
        for _label, mdf, mesh in _pairs():
            if mesh is None:
                continue
            m = pec.material_matching(pec._mdf_materials(mdf), pec._mesh_objects(mesh))
            doomed = [o for name in m['open_mats'] for o in m['mat_by_name'].get(name, [])]
            for obj in doomed:
                for child in list(obj.children_recursive):
                    bpy.data.objects.remove(child, do_unlink=True)
                bpy.data.objects.remove(obj, do_unlink=True)
                n += 1
            if doomed:
                _reindex(context, mdf)
        return _finish(self, context, "delete_unused_done", n)


def _reindex(context, mdf_col):
    """RE Mesh Editor's own renumbering (``Material NN (name)``), pointed at
    *mdf_col* for the call and pointed back afterwards."""
    tp = getattr(context.scene, "re_mdf_toolpanel", None)
    if tp is None or 'reindex_materials' not in dir(bpy.ops.re_mdf):
        return
    prev = tp.mdfCollection
    try:
        tp.mdfCollection = mdf_col
        bpy.ops.re_mdf.reindex_materials()
    except Exception as e:
        print(f"[PreExportCheck] reindex failed: {e}")
    finally:
        tp.mdfCollection = prev


class MODDER_OT_PecUpdateOutdated(bpy.types.Operator):
    """「更新过时材质」: bring each material to its shader's vanilla layout from
    the bundled snapshot (core/mdf_layouts.py).  A button, never an auto-fix: a
    snapshot older than the game would move current materials backwards."""
    bl_idname = "modder.pec_update_outdated"
    bl_label = "Update Outdated Materials"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "outdated_desc")

    def execute(self, context):
        game = pec._LAST_RUN.get('game', "")
        n = 0
        mmtrs = []
        for _label, mdf, _mesh in _pairs():
            for obj in pec._mdf_materials(mdf):
                md = obj.re_mdf_material
                sample = mdf_layouts.sample_for(game, md.mmtrPath)
                if sample is None:
                    continue
                changed, warnings = mdf_layouts.update(md, sample)
                n += bool(changed)
                if "mmtrs" in warnings:
                    mmtrs.append(md.materialName)
        if mmtrs:
            self.report({'WARNING'}, T(_K + "outdated_mmtrs").format(names=", ".join(mmtrs)))
        return _finish(self, context, "outdated_done", n,
                       snap=mdf_layouts.snapshot_label(game))


# ── Bones and weights ────────────────────────────────────────────────────────

def _scope_armatures():
    arms, meshes = [], []
    for _label, _mdf, mesh in _pairs():
        if mesh is None:
            continue
        ms = pec._mesh_objects(mesh)
        meshes += ms
        arm = pec.export_armature(mesh, ms)
        if arm is not None and arm not in arms:
            arms.append(arm)
    return arms, meshes


class MODDER_OT_PecAsciiBones(bpy.types.Operator):
    """「转成英文名并同步引用」 (docs/pre_export_check_plan.md §6.2).

    ``bone.name = new`` on every armature involved: Blender itself carries the
    rename to vertex groups of meshes linked to that armature and to constraint
    subtargets, RE Chain Editor's ``BoneName`` included (measured in 5.1.2).
    What it does not carry is patched here: the plain-string chain fields
    ``constraintJntName`` / ``jointHash``, and same-named vertex groups on
    meshes with no link to the armature.  One old name maps to one new name in
    every armature, so parts that share a bone stay in step."""
    bl_idname = "modder.pec_ascii_bones"
    bl_label = "Rename Bones to English"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "ascii_desc")

    def execute(self, context):
        _object_mode(context)
        arms, meshes = _scope_armatures()
        names = [b.name for a in arms for b in a.data.bones]
        plan = pc.allocate_ascii_names(names, names)
        if not plan:
            return _finish(self, context, "ascii_done", 0)
        for arm in arms:
            for old, new in plan.items():
                bone = arm.data.bones.get(old)
                if bone is not None:
                    bone.name = new
        patched = 0
        for obj in bpy.data.objects:
            node = getattr(obj, "re_chain_chainnode", None)
            if node is None or not obj.get("TYPE"):
                continue
            for field in ("constraintJntName", "jointHash"):
                v = getattr(node, field, "")
                if v in plan:
                    setattr(node, field, plan[v])
                    patched += 1
        for obj in meshes:
            for vg in obj.vertex_groups:
                if vg.name in plan and plan[vg.name] not in obj.vertex_groups:
                    vg.name = plan[vg.name]
        self.report({'WARNING'}, T(_K + "ascii_reexport"))
        return _finish(self, context, "ascii_done", len(plan))


class MODDER_OT_PecSelectUnweighted(bpy.types.Operator):
    """「选中这些顶点」: the vertices the exporter would pin to bone 0, selected
    in Edit Mode on every mesh that has them, ready for weight painting."""
    bl_idname = "modder.pec_select_unweighted"
    bl_label = "Select These Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T(_K + "select_unweighted_desc")

    def execute(self, context):
        _object_mode(context)
        targets = []
        for _label, _mdf, mesh in _pairs():
            if mesh is None:
                continue
            ms = pec._mesh_objects(mesh)
            arm = pec.export_armature(mesh, ms)
            for obj in ms:
                if not len(obj.data.polygons):
                    continue    # an empty submesh belongs to the structure group
                bad = set(pec.unweighted_vertices(obj, arm)) if arm else set()
                if not bad:
                    continue
                sel = [i in bad for i in range(len(obj.data.vertices))]
                obj.data.vertices.foreach_set("select", sel)
                for e in obj.data.edges:
                    e.select = False
                for f in obj.data.polygons:
                    f.select = False
                targets.append((obj, len(bad)))
        if not targets:
            self.report({'INFO'}, T(_K + "select_unweighted_none"))
            return {'FINISHED'}
        for o in context.view_layer.objects:
            o.select_set(False)
        for obj, _n in targets:
            try:
                obj.select_set(True)
            except RuntimeError:
                pass
        context.view_layer.objects.active = targets[0][0]
        try:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
        except RuntimeError:
            pass
        self.report({'INFO'}, T(_K + "select_unweighted_done").format(
            n=sum(n for _o, n in targets), objs=len(targets)))
        return {'FINISHED'}


# ── 「使用生成器快捷生成」 ─────────────────────────────────────────────────────

#: Game the open quick-generate dialog is for; read by the row preset callback.
_QUICK = {'game_name': ""}


def _quick_presets(self, context):
    from .mdf_generator_base import load_preset_enum_items
    return load_preset_enum_items(_QUICK['game_name'])


class PEC_QuickGenRow(bpy.types.PropertyGroup):
    mdf_name: StringProperty(name="")
    blender_material: StringProperty(name="")
    pair_index: IntProperty(name="")
    preset: EnumProperty(name="", items=_quick_presets)


def _art_base(path):
    """The generator's base path (under Art/) of a binding path."""
    p = pc.normalize_tex_path(path)
    d = p.rsplit('/', 1)[0] if '/' in p else ""
    return d[4:] if d.lower().startswith("art/") else d


def default_base_path(game, mdf_col, settings):
    """§5.2.1's three sources, first hit wins: where the mdf's own custom
    textures already live (most common folder), the generator panel's own
    field, then the batch export scheme's folder for this armor."""
    from collections import Counter
    cfg = pec._tex_config(game)
    vanilla = set()
    if cfg is not None:
        from .mdf_material_convert_base import _load_vanilla_art_paths
        vanilla = _load_vanilla_art_paths(cfg["vanilla_asset_rel"])
    counts = Counter()
    for obj in pec._mdf_materials(mdf_col):
        for b in obj.re_mdf_material.textureBindingList_items:
            p = pc.normalize_tex_path(b.path)
            if p and p.lower() not in vanilla and "null" not in p.lower():
                base = _art_base(p)
                if base:
                    counts[base] += 1
    if counts:
        return counts.most_common(1)[0][0]
    if settings is not None and getattr(settings, "texture_base_path", "").strip():
        return settings.texture_base_path.strip()
    return pec._LAST_RUN.get('tex_base_hint', "")


def missing_materials(pairs):
    """``[(pair index, mdf name, Blender material or None)]`` for every mesh
    whose material the mdf lacks -- the rows of the quick-generate dialog."""
    out = []
    for i, (_label, mdf, mesh) in enumerate(pairs):
        if mesh is None:
            continue
        meshes = pec._mesh_objects(mesh)
        m = pec.material_matching(pec._mdf_materials(mdf), meshes)
        seen = set()
        for obj_name, want in m['open_meshes']:
            if not want or want in seen:
                continue
            seen.add(want)
            obj = bpy.data.objects.get(obj_name)
            mats = pec.used_materials(obj) if obj else []
            out.append((i, want, mats[0] if mats else None))
    return out


class MODDER_OT_PecQuickGenerate(bpy.types.Operator):
    """「使用生成器快捷生成」: fill in the materials the mdf lacks straight from
    the meshes' Blender materials, choosing only a preset per material; every
    other generator option stays at its default."""
    bl_idname = "modder.pec_quick_generate"
    bl_label = "Quick Generate"
    bl_options = {'REGISTER', 'UNDO'}

    rows: CollectionProperty(type=PEC_QuickGenRow)
    base_path: StringProperty(name="")

    @classmethod
    def description(cls, context, properties):
        return T(_K + "quick_desc")

    def invoke(self, context, event):
        from .mdf_generator_base import generator_for, load_preset_enum_items, guess_best_preset
        game = pec._LAST_RUN.get('game', "")
        cls = generator_for(game)
        if cls is None:
            self.report({'ERROR'}, T(_K + "quick_no_generator"))
            return {'CANCELLED'}
        _QUICK['game_name'] = cls._game_name
        items = load_preset_enum_items(cls._game_name)
        pairs = _pairs()
        self.rows.clear()
        for i, name, mat in missing_materials(pairs):
            row = self.rows.add()
            row.mdf_name = name
            row.pair_index = i
            row.blender_material = mat.name if mat else ""
            best = guess_best_preset(name, items)
            if best and best != 'NONE':
                row.preset = best
        settings = getattr(context.scene, cls._settings_attr, None)
        first_mdf = pairs[self.rows[0].pair_index][1] if len(self.rows) else None
        self.base_path = default_base_path(game, first_mdf, settings) if first_mdf else ""
        return context.window_manager.invoke_props_dialog(
            self, width=560, **pec._dialog_kwargs(_K + "quick_title", _K + "quick_confirm"))

    def draw(self, context):
        col = self.layout.column()
        for row in self.rows:
            r = col.row(align=True)
            split = r.split(factor=0.55)
            if row.blender_material:
                split.label(text=T(_K + "quick_row").format(mdf=row.mdf_name, mat=row.blender_material),
                            icon='MATERIAL')
                split.prop(row, "preset", text="")
            else:
                split.label(text=row.mdf_name, icon='ERROR')
                split.label(text=T(_K + "quick_no_material"))
        col.separator()
        col.prop(self, "base_path", text=T(_K + "quick_base_path"))

    def execute(self, context):
        from .mdf_generator_base import generator_for, generate_materials, QuickEntry
        game = pec._LAST_RUN.get('game', "")
        cls = generator_for(game)
        base = self.base_path.strip().strip('/\\')
        if cls is None or not base:
            self.report({'ERROR'}, T(_K + "quick_need_base"))
            return {'CANCELLED'}
        if cls._path_fixed_prefix:
            base = cls._path_fixed_prefix.strip('/') + '/' + base
        natives_root = pec._LAST_RUN.get('root', "")
        settings = getattr(context.scene, cls._settings_attr, None)
        pairs = _pairs()
        _object_mode(context)
        ok = failed = 0
        by_pair = {}
        for row in self.rows:
            mat = bpy.data.materials.get(row.blender_material)
            if mat is None or not row.preset or row.preset == 'NONE':
                continue
            by_pair.setdefault(row.pair_index, []).append((row.mdf_name, QuickEntry(mat, row.preset)))
        for i, items in by_pair.items():
            _label, mdf, mesh = pairs[i]
            before = {o.name for o in mdf.all_objects}
            a, b, _unresolved = generate_materials(
                context, cls, [e for _n, e in items], settings, mesh, mdf, natives_root, base)
            ok += a
            failed += b
            # The generator names a material after the first mesh using its
            # Blender material; make sure each lands on the name that was asked for.
            created = [o for o in mdf.all_objects
                       if o.name not in before and o.get("~TYPE") == "RE_MDF_MATERIAL"]
            for (want, entry), obj in zip(items, created):
                if obj.re_mdf_material.materialName != want:
                    obj.re_mdf_material.materialName = want
        if failed:
            self.report({'WARNING'}, T(_K + "quick_failed").format(n=failed))
        _finish(self, context, "quick_done", ok)
        bpy.ops.modder.pre_export_check_report('INVOKE_DEFAULT')
        return {'FINISHED'}


classes = [MODDER_OT_PecAlignNames, MODDER_OT_PecSeparateRecheck,
           MODDER_OT_PecFixUnusedByBlender, MODDER_OT_PecDeleteUnused,
           MODDER_OT_PecUpdateOutdated, PEC_QuickGenRow, MODDER_OT_PecQuickGenerate,
           MODDER_OT_PecAsciiBones, MODDER_OT_PecSelectUnweighted]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
