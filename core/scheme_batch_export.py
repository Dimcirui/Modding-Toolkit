"""Scheme-driven batch export, shared by the games whose mods are a fixed set of part
files: RE9 and Onimusha (ONI).

A *scheme* (``assets/export_schemes/<game>/<character>.json``) lists a character's
parts -- grouped by what they are (arm, hair, cloak...) -- and for each part the
files the game loads: one mesh, one or more mdf2, and optionally sfur / chain2 /
clsp / gpuc.  The user binds Blender collections to parts; export writes each bound
collection to every path the part lists, and (optionally) a built-in blank file to
the parts left unbound, which is how a mod hides a vanilla part.

This was RE9's exporter, ``games/re9/batch_export(_ui).py``, until ONI needed the same
thing.  A third copy next to RE4's would have been three forks of one dialog, so the
body moved here unchanged and everything game-specific became a field of
:class:`SchemeExportSpec`.  RE9 keeps its operator ids and scene keys byte for byte --
bindings saved in existing .blend files are read back under the same names.

``build_classes(exporter)`` returns the operator / list classes for one game; each game
module registers its own set.  The class *bodies* live here once.
"""

import os
import json
import shutil

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty

from .i18n import T
from .re_mesh_compat import call_re_mesh_op, re_mesh_op_available
from .bone_utils import align_armatures_by_name
from . import console_export
from . import mod_root
from .export_verify import checked
from . import poll_msg

#: Slots a part can carry besides its mesh.  ``gpuc`` (Onimusha's cloth-sim cache)
#: has no Blender-side editor, so it is only ever written as a blank file.
SLOTS = ("mesh", "mdf2", "sfur", "chain2", "clsp")

MESH_SETTINGS = {
    "exportAllLODs": True,
    "autoSolveRepeatedUVs": True,
    "preserveSharpEdges": True,
    "rotate90": True,
    "useBlenderMaterialName": False,
    "preserveBoneMatrices": False,
    "exportBoundingBoxes": False,
}


#: Types with no meaningful empty file, skipped instead of blanked -- the same
#: call MHRS made for .chain (games/mhrs/batch_export.py NO_BLANK_FILE_TYPES).
#: There were never blank chain2/clsp files, so these slots only ever printed
#: "SKIP blank (file not found)".
NO_BLANK_FILE_TYPES = {"chain2", "clsp"}


def _addon_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Exporters (also borrowed by games/mhws/batch_export.py via re9) ──────────

def do_export_mesh(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: call_re_mesh_op('exportfile', filepath=filepath, targetCollection=collection_name, **MESH_SETTINGS))


def do_export_mdf2(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: bpy.ops.re_mdf.exportfile(filepath=filepath, targetCollection=collection_name))


def do_export_sfur(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: bpy.ops.re_sfur.exportfile(filepath=filepath, targetCollection=collection_name))


def do_export_fbxskel(filepath, armature_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: bpy.ops.re_fbxskel.exportfile(filepath=filepath, targetArmature=armature_name))


def do_export_chain2(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: bpy.ops.re_chain2.exportfile(filepath=filepath, targetCollection=collection_name))


def do_export_clsp(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    checked(filepath, lambda: bpy.ops.re_clsp.exportfile(filepath=filepath, targetCollection=collection_name))


def _as_list(value):
    return value if isinstance(value, list) else [value]


class SchemeExportSpec:
    """What differs between two games using this exporter.

    *op_prefix*        bl_idname namespace and class-name prefix (``re9`` ->
                       ``re9.batch_export``, ``RE9_OT_BatchExport``).
    *key_prefix*       scene custom-property prefix for bindings.  Never change it
                       for a shipped game: it is how saved bindings are found.
    *fbxskel_base*     path under ``natives/`` the scheme's ``fbxskel`` is relative to.
    *native_skeleton_dir*  ``assets/native_skeletons/<dir>``; when it holds a file
                       named like the scheme's fbxskel, the vanilla skeleton is
                       aligned to the user's rig and exported instead of the rig.
    *mdf_active_game*  RE Mesh Editor's ``activeGame`` for the export.  mdf2 version
                       51 is RE9's and Onimusha's both, and REME picks the layout
                       from that scene setting alone -- so it is set for the run and
                       put back, or an RE9 export after an Onimusha import writes
                       Onimusha's layout.
    *check_game* / *autofix_game*  the game key for the pre-export check and the
                       auto-fix, or None where that game is not registered there.
    """

    def __init__(self, code, op_prefix, key_prefix, title, scheme_dir, blank_dir,
                 natives_root_key, scheme_setting, blank_setting, fbxskel_base,
                 native_skeleton_dir=None, mdf_active_game=None,
                 check_game=None, autofix_game=None):
        self.code = code
        self.op_prefix = op_prefix
        self.key_prefix = key_prefix
        self.title = title
        self.scheme_dir = scheme_dir
        self.blank_dir = blank_dir
        self.natives_root_key = natives_root_key
        self.scheme_setting = scheme_setting
        self.blank_setting = blank_setting
        self.fbxskel_base = fbxskel_base
        self.native_skeleton_dir = native_skeleton_dir
        self.mdf_active_game = mdf_active_game
        self.check_game = check_game
        self.autofix_game = autofix_game


class SchemeExporter:
    """Scheme loading, binding storage and the export run for one game."""

    def __init__(self, spec):
        self.spec = spec
        #: EnumProperty items must outlive the callback (Blender keeps the C
        #: strings), so one persistent list per game -- see core/ref_skeleton.py.
        self._scheme_cache = []

        # A plain function, not the bound method: EnumProperty(items=...) accepts
        # only a real function object and rejects a bound method outright
        # ("expected a sequence of tuples ... or a function").
        def schemes_callback(_self, context):
            return self._schemes_items()
        self.schemes_callback = schemes_callback

    # ── paths ───────────────────────────────────────────────────────────────

    def schemes_dir(self):
        d = os.path.join(_addon_dir(), "assets", "export_schemes", self.spec.scheme_dir)
        os.makedirs(d, exist_ok=True)
        return d

    def native_skeletons_dir(self):
        if not self.spec.native_skeleton_dir:
            return ""
        return os.path.join(_addon_dir(), "assets", "native_skeletons", self.spec.native_skeleton_dir)

    def native_skeleton_for(self, fbxskel_path):
        d = self.native_skeletons_dir()
        return os.path.join(d, os.path.basename(fbxskel_path)) if d else ""

    def blank_path(self, filetype, filename=None):
        """``blank_files/<game>/<filename>``, else the game's generic ``blank.<type>``.

        *filename* is an entry's own ``blank_mesh`` -- RE4's convention, and the
        reason it exists: a part whose prefab has components that look up its own
        joints by name needs a blank that still carries them.  Onimusha's cloak is
        the measured case: its PlayerCloakController / MultiChainManager copy the
        mantle joints, the generic blank has none of them, and the game crashed
        loading it (2026-10-14).
        """
        d = os.path.join(_addon_dir(), "assets", "blank_files", self.spec.blank_dir)
        if filename:
            return os.path.join(d, filename)
        plain = os.path.join(d, f"blank.{filetype}")
        if os.path.isfile(plain):
            return plain
        # Some blanks carry their version in the name, as the game files do
        # (re9's is blank.sfur.5); looking for "blank.sfur" alone never found it,
        # so every unbound RE9 sfur slot was skipped instead of blanked.
        try:
            versioned = sorted(f for f in os.listdir(d) if f.startswith(f"blank.{filetype}."))
        except OSError:
            versioned = []
        return os.path.join(d, versioned[0]) if versioned else plain

    # ── schemes ─────────────────────────────────────────────────────────────

    def _schemes_items(self):
        cache = self._scheme_cache
        cache.clear()
        d = self.schemes_dir()
        if os.path.exists(d):
            for f in sorted(os.listdir(d)):
                if f.endswith('.json'):
                    cache.append((f, f.replace('.json', ''), ""))
        if not cache:
            cache.append(('NONE', "No scheme", ""))
        return cache

    def load_scheme(self, filename):
        filepath = os.path.join(self.schemes_dir(), filename)
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ── bindings (scene custom properties) ──────────────────────────────────

    @staticmethod
    def _clean(key):
        return key.replace(" ", "_").replace("(", "").replace(")", "")

    def _key(self, character_id, entry_id, suffix):
        return self._clean(f"{self.spec.key_prefix}ex_{character_id}_{entry_id}_{suffix}")

    def get_binding(self, scene, character_id, entry_id, suffix):
        return scene.get(self._key(character_id, entry_id, suffix), "")

    def set_binding(self, scene, character_id, entry_id, suffix, value):
        scene[self._key(character_id, entry_id, suffix)] = value

    def _en_key(self, character_id, entry_id, suffix):
        return self._clean(f"{self.spec.key_prefix}en_{character_id}_{entry_id}_{suffix}")

    def get_enabled(self, scene, character_id, entry_id, suffix):
        return scene.get(self._en_key(character_id, entry_id, suffix), True)

    def set_enabled(self, scene, character_id, entry_id, suffix, value):
        scene[self._en_key(character_id, entry_id, suffix)] = value

    def _sg_key(self, character_id, group_name, suffix):
        return self._clean(f"{self.spec.key_prefix}sg_{character_id}_{group_name}_{suffix}").replace("-", "_")

    def get_group_binding(self, scene, character_id, group_name, suffix):
        return scene.get(self._sg_key(character_id, group_name, suffix), "")

    def set_group_binding(self, scene, character_id, group_name, suffix, value):
        scene[self._sg_key(character_id, group_name, suffix)] = value

    def _se_key(self, character_id, suffix):
        return f"{self.spec.key_prefix}se_{character_id}_{suffix}"

    def get_empty_binding(self, scene, character_id, suffix):
        return scene.get(self._se_key(character_id, suffix), "")

    def set_empty_binding(self, scene, character_id, suffix, value):
        scene[self._se_key(character_id, suffix)] = value

    @property
    def simplified_key(self):
        return f"{self.spec.key_prefix}_use_simplified"

    def use_simplified(self, scene):
        return scene.get(self.simplified_key, False)

    # ── resolution (shared by export, check and auto-fix) ───────────────────

    def resolve_mesh_mdf2(self, scene, character_id, group, entry, use_simplified):
        """``(mesh_col_name, mdf2_col_name)`` this entry currently resolves to
        under the given mode -- "" for a slot with nothing bound (disabled, or
        simplified mode has nothing picked yet). The single place that decides
        "what collection backs this entry's mesh/mdf2 right now", read by both
        the real export loop and the pre-export check, so a future change to
        the mode-resolution rules can't make them disagree.

        sfur/chain2/clsp and the "empty"-scheme blank-copy path are left to the
        export loop: none of them are part of what pre_export_check inspects, and
        a blank copy has no Blender data behind it for either caller to read.
        """
        if use_simplified:
            group_name = group["name"]
            simp = entry.get("simplified", "user")
            if simp == "user":
                return (self.get_group_binding(scene, character_id, group_name, "mesh"),
                        self.get_group_binding(scene, character_id, group_name, "mdf2"))
            elif simp == "empty":
                return (self.get_empty_binding(scene, character_id, "mesh"),
                        self.get_empty_binding(scene, character_id, "mdf2"))
            return "", ""  # "skip", or any future unknown value

        entry_id = entry["id"]
        mesh_col = (self.get_binding(scene, character_id, entry_id, "mesh")
                    if self.get_enabled(scene, character_id, entry_id, "mesh") else "")
        mdf2_col = (self.get_binding(scene, character_id, entry_id, "mdf2")
                    if self.get_enabled(scene, character_id, entry_id, "mdf2") else "")
        return mesh_col, mdf2_col

    def bound_pairs(self, scene, scheme, use_simplified):
        """``[(group name, mdf_col, mesh_col)]`` for every distinct mesh / mdf2
        pair this batch exports -- what auto-fix runs over.  Wider than the check's
        pairs: an entry with only a mesh bound still gets its weights cleaned."""
        character_id = scheme["character_id"]
        out, seen = [], set()
        for group in scheme.get("groups", []):
            for entry in group["entries"]:
                mesh_name, mdf_name = self.resolve_mesh_mdf2(scene, character_id, group, entry, use_simplified)
                mesh = bpy.data.collections.get(mesh_name) if mesh_name else None
                mdf = bpy.data.collections.get(mdf_name) if mdf_name else None
                key = (mdf.name if mdf else None, mesh.name if mesh else None)
                if (mdf is None and mesh is None) or key in seen:
                    continue
                seen.add(key)
                out.append((group["name"], mdf, mesh))
        return out

    def gather_check_pairs(self, scene, character_id, scheme, use_simplified):
        """``[(label, mdf_col, mesh_col), ...]`` for whatever this batch would
        actually export.  Simplified mode checks once per group (the group-level
        binding covers every "user" entry in it together); normal mode checks
        once per entry."""
        pairs = []
        for group in scheme["groups"]:
            group_name = group["name"]
            if use_simplified:
                user_entries = [e for e in group["entries"] if e.get("simplified") == "user"]
                if not user_entries or not any(e.get("mdf2") for e in user_entries):
                    continue
                mesh_name, mdf_name = self.resolve_mesh_mdf2(
                    scene, character_id, group, {"simplified": "user"}, True)
                mdf_col = bpy.data.collections.get(mdf_name) if mdf_name else None
                if mdf_col is None:
                    continue
                mesh_col = bpy.data.collections.get(mesh_name) if mesh_name else None
                pairs.append((group_name, mdf_col, mesh_col))
            else:
                for entry in group["entries"]:
                    if not entry.get("mdf2"):
                        continue
                    mesh_name, mdf_name = self.resolve_mesh_mdf2(scene, character_id, group, entry, False)
                    mdf_col = bpy.data.collections.get(mdf_name) if mdf_name else None
                    if mdf_col is None:
                        continue
                    mesh_col = bpy.data.collections.get(mesh_name) if mesh_name else None
                    pairs.append((f"{group_name} / {entry['id']}", mdf_col, mesh_col))
        return pairs

    # ── the run ─────────────────────────────────────────────────────────────

    def run(self, op, context):
        """The batch export operator's body; *op* is the operator (for report)."""
        from . import export_autofix
        spec = self.spec
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not re_mesh_op_available('exportfile'):
            op.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        natives_root = mod_root.read(scene, spec.natives_root_key)
        if not natives_root or not os.path.isdir(natives_root):
            op.report({'ERROR'}, "Set natives root directory first")
            return {'CANCELLED'}

        scheme_file = getattr(settings, spec.scheme_setting)
        if not scheme_file or scheme_file == 'NONE':
            op.report({'ERROR'}, "No export scheme selected")
            return {'CANCELLED'}

        scheme = self.load_scheme(scheme_file)
        if not scheme:
            op.report({'ERROR'}, f"Failed to load: {scheme_file}")
            return {'CANCELLED'}

        mdf_panel = getattr(scene, "re_mdf_toolpanel", None)
        prev_game = getattr(mdf_panel, "activeGame", None) if mdf_panel is not None else None
        if spec.mdf_active_game and mdf_panel is not None:
            mdf_panel.activeGame = spec.mdf_active_game
        try:
            if spec.autofix_game is None:
                return self._export(op, context, scene, settings, natives_root, scheme)
            # Auto-fix only after every check above has passed: an export that
            # cancels must not leave its fixes behind. Persistent fixes first (one
            # undo step), then the temporary ones wrap the export itself and come
            # off again even if it raises.
            pairs = self.bound_pairs(scene, scheme, self.use_simplified(scene))
            ids = export_autofix.enabled_items(context, spec.autofix_game)
            done = export_autofix.apply(context, spec.autofix_game, pairs, ids)
            with export_autofix.temporary(context, spec.autofix_game, pairs, ids) as tmp:
                result = self._export(op, context, scene, settings, natives_root, scheme)
            fixed = {k: v for k, v in list(done.items()) + list(tmp.items()) if v}
            if fixed:
                print(f"[{spec.code}] auto-fix: " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
                op.report({'INFO'}, T("core.pre_export_check_ops.autofix_done").format(
                    n=sum(fixed.values())))
            return result
        finally:
            if spec.mdf_active_game and mdf_panel is not None and prev_game is not None:
                mdf_panel.activeGame = prev_game

    def _export(self, op, context, scene, settings, natives_root, scheme):
        spec = self.spec
        tag = f"[{spec.code}]"
        character_id = scheme["character_id"]
        base_path = scheme["base_path"].replace("\\", "/")
        use_simplified = self.use_simplified(scene)
        use_blank = getattr(settings, spec.blank_setting)

        export_count = 0
        fail_count = 0
        skip_count = 0

        # Cache for identical exports: (func_name, target) -> exported_filepath
        export_cache = {}

        def make_full(rel, bp_override=None):
            bp = (bp_override or base_path).replace("/", os.sep)
            return os.path.join(natives_root, "natives", bp, rel.replace("/", os.sep))

        def try_export(func, filepath, target, label):
            nonlocal export_count, fail_count, skip_count
            if not target or target == "NONE":
                skip_count += 1
                return
            # Check target exists
            if func == do_export_fbxskel:
                if target not in bpy.data.objects or bpy.data.objects[target].type != 'ARMATURE':
                    print(f"{tag} SKIP {label}: armature '{target}' not found")
                    skip_count += 1
                    return
            else:
                if target not in bpy.data.collections:
                    print(f"{tag} SKIP {label}: collection '{target}' not found")
                    skip_count += 1
                    return

            cache_key = (func.__name__, target)
            if cache_key in export_cache:
                try:
                    source_filepath = export_cache[cache_key]
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    shutil.copy2(source_filepath, filepath)
                    print(f"{tag} {label}: {target} [CACHED] -> {os.path.basename(filepath)}")
                    export_count += 1
                except Exception as err:
                    print(f"{tag} FAILED {label} [CACHE COPY]: {err}")
                    fail_count += 1
                return

            try:
                print(f"{tag} {label}: {target} -> {os.path.basename(filepath)}")
                func(filepath, target)
                export_cache[cache_key] = filepath
                export_count += 1
            except Exception as err:
                print(f"{tag} FAILED {label}: {err}")
                fail_count += 1

        def try_blank(filetype, filepath, label, filename=None):
            nonlocal export_count, skip_count
            if filetype in NO_BLANK_FILE_TYPES:
                print(f"{tag} {label}: not bound, left as is (no blank for {filetype})")
                skip_count += 1
                return
            blank_src = self.blank_path(filetype, filename)
            if os.path.isfile(blank_src):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                shutil.copy2(blank_src, filepath)
                print(f"{tag} {label}: BLANK -> {os.path.basename(filepath)}")
                export_count += 1
            else:
                print(f"{tag} SKIP blank (file not found): {blank_src}")
                skip_count += 1

        # --- FBXSKEL ---
        fbxskel_path = scheme.get("fbxskel", "")
        if fbxskel_path:
            fbx_enabled = self.get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            fbx_arm = self.get_binding(scene, character_id, "_fbxskel", "fbxskel")
            if fbx_enabled and fbx_arm:
                full = os.path.join(natives_root, "natives", spec.fbxskel_base.replace("/", os.sep),
                                    fbxskel_path.replace("/", os.sep))
                native_path = self.native_skeleton_for(fbxskel_path)
                if native_path and os.path.isfile(native_path):
                    user_arm_obj = bpy.data.objects.get(fbx_arm)
                    if user_arm_obj is None or user_arm_obj.type != 'ARMATURE':
                        print(f"{tag} SKIP FBXSKEL: armature '{fbx_arm}' not found")
                        skip_count += 1
                    else:
                        prev_active = context.view_layer.objects.active
                        prev_sel = [o for o in context.selected_objects]
                        for o in prev_sel:
                            o.select_set(False)
                        native_copy = None
                        try:
                            bpy.ops.re_fbxskel.importfile(filepath=native_path)
                            native_copy = context.view_layer.objects.active
                            if native_copy is None or native_copy.type != 'ARMATURE':
                                raise RuntimeError(f"导入原生骨架失败: {native_path}")
                            native_copy.select_set(False)
                            # 仅对齐位置/朝向，不生成假骨骼——把原生骨架（含仅存在于原生骨架
                            # 中的骨骼）整体对齐到用户绑定的骨架比例上，再导出对齐后的副本
                            align_armatures_by_name(user_arm_obj, native_copy, mode='FULL')
                            print(f"{tag} FBXSKEL (对齐原生骨架): {fbx_arm} -> {os.path.basename(full)}")
                            do_export_fbxskel(full, native_copy.name)
                            export_count += 1
                        except Exception as err:
                            print(f"{tag} FAILED FBXSKEL (对齐原生骨架): {err}")
                            fail_count += 1
                        finally:
                            if native_copy is not None and native_copy.name in bpy.data.objects:
                                bpy.data.objects.remove(native_copy, do_unlink=True)
                            context.view_layer.objects.active = prev_active
                            for o in prev_sel:
                                if o.name in bpy.data.objects:
                                    o.select_set(True)
                else:
                    try_export(do_export_fbxskel, full, fbx_arm, "FBXSKEL")

        # --- Per entry ---
        for group in scheme["groups"]:
            group_name = group["name"]
            grp_bp = group.get("base_path")  # Optional per-group base_path override
            for entry in group["entries"]:
                entry_id = entry["id"]
                simp = entry.get("simplified", "user")
                # A part that must never be replaced by the blank opts out with
                # "no_blank": exported when bound, left untouched otherwise, in both
                # modes.  Onimusha's gauntlet (ch001_00_60) is one -- the user's
                # finding, 2026-10-14: blanking it does not work in game.
                entry_blank = use_blank and not entry.get("no_blank", False)

                # gpuc: a cloth-sim cache with no Blender-side data, so the only
                # thing a mod can put there is the blank -- written whenever the
                # part's mesh is being replaced, since a vanilla cache built for
                # the vanilla mesh's vertices must not drive a different mesh.
                def blank_gpuc():
                    for g in _as_list(entry["gpuc"]):
                        try_blank("gpuc", make_full(g, grp_bp), f"GPUC {entry_id}")

                if use_simplified:
                    # Determine mesh/mdf2 collection based on simplified rule
                    if simp == "skip":
                        continue
                    elif simp == "user":
                        mesh_col, mdf2_col = self.resolve_mesh_mdf2(scene, character_id, group, entry, use_simplified)
                    elif simp == "empty":
                        if entry_blank:
                            # Use built-in blank files directly for empty entries
                            if entry.get("mesh"):
                                try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}",
                                      entry.get("blank_mesh"))
                            if entry.get("mdf2"):
                                for m in entry["mdf2"]:
                                    try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}")
                            if entry.get("sfur"):
                                try_blank("sfur", make_full(entry["sfur"], grp_bp), f"SFUR {entry_id}")
                            if entry.get("chain2"):
                                for c in _as_list(entry["chain2"]):
                                    try_blank("chain2", make_full(c, grp_bp), f"CHAIN2 {entry_id}")
                            if entry.get("gpuc"):
                                blank_gpuc()
                            continue
                        else:
                            mesh_col, mdf2_col = self.resolve_mesh_mdf2(scene, character_id, group, entry, use_simplified)
                    else:
                        continue

                    # sfur
                    sfur_col = ""
                    rule_sfur = entry.get("simplified_sfur", simp)
                    if rule_sfur == "user" and entry.get("sfur"):
                        sfur_col = self.get_group_binding(scene, character_id, group_name, "sfur")
                    elif rule_sfur == "empty" and entry.get("sfur"):
                        if entry_blank:
                            try_blank("sfur", make_full(entry["sfur"], grp_bp), f"SFUR {entry_id}")
                        else:
                            sfur_col = self.get_empty_binding(scene, character_id, "sfur")

                    # chain2
                    rule_chain2 = entry.get("simplified_chain2", simp)
                    if rule_chain2 == "user" and entry.get("chain2"):
                        chain2_col = self.get_group_binding(scene, character_id, group_name, "chain2")
                        if chain2_col:
                            for c in _as_list(entry["chain2"]):
                                try_export(do_export_chain2, make_full(c, grp_bp), chain2_col, f"CHAIN2 {entry_id}")
                    elif rule_chain2 == "empty" and entry.get("chain2"):
                        if entry_blank:
                            for c in _as_list(entry["chain2"]):
                                try_blank("chain2", make_full(c, grp_bp), f"CHAIN2 {entry_id}")
                        else:
                            chain2_col = self.get_empty_binding(scene, character_id, "chain2")
                            if chain2_col:
                                for c in _as_list(entry["chain2"]):
                                    try_export(do_export_chain2, make_full(c, grp_bp), chain2_col, f"CHAIN2 {entry_id}")

                    # clsp
                    rule_clsp = entry.get("simplified_clsp", simp)
                    if rule_clsp == "user" and entry.get("clsp"):
                        clsp_col = self.get_group_binding(scene, character_id, group_name, "clsp")
                        if clsp_col:
                            for c in _as_list(entry["clsp"]):
                                try_export(do_export_clsp, make_full(c, grp_bp), clsp_col, f"CLSP {entry_id}")
                    elif rule_clsp == "empty" and entry.get("clsp"):
                        if entry_blank:
                            for c in _as_list(entry["clsp"]):
                                try_blank("clsp", make_full(c, grp_bp), f"CLSP {entry_id}")
                        else:
                            clsp_col = self.get_empty_binding(scene, character_id, "clsp")
                            if clsp_col:
                                for c in _as_list(entry["clsp"]):
                                    try_export(do_export_clsp, make_full(c, grp_bp), clsp_col, f"CLSP {entry_id}")

                    # Export mesh
                    if entry.get("mesh"):
                        if mesh_col:
                            try_export(do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")
                            if entry.get("gpuc"):
                                blank_gpuc()
                        elif entry_blank:
                            try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}",
                                      entry.get("blank_mesh"))
                            if entry.get("gpuc"):
                                blank_gpuc()

                    # Export mdf2s
                    if entry.get("mdf2"):
                        if mdf2_col:
                            for m in entry["mdf2"]:
                                try_export(do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")
                        elif entry_blank:
                            for m in entry["mdf2"]:
                                try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}")

                    # Export sfur (collection-bound; blank case handled above)
                    if entry.get("sfur") and sfur_col:
                        try_export(do_export_sfur, make_full(entry["sfur"], grp_bp), sfur_col, f"SFUR {entry_id}")

                else:
                    # Normal mode: use per-entry bindings
                    mesh_col, mdf2_col = self.resolve_mesh_mdf2(scene, character_id, group, entry, use_simplified)

                    mesh_en = self.get_enabled(scene, character_id, entry_id, "mesh")
                    if entry.get("mesh"):
                        if mesh_en and mesh_col:
                            try_export(do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")
                            if entry.get("gpuc"):
                                blank_gpuc()
                        elif mesh_en and entry_blank:
                            try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}",
                                      entry.get("blank_mesh"))
                            if entry.get("gpuc"):
                                blank_gpuc()

                    mdf2_en = self.get_enabled(scene, character_id, entry_id, "mdf2")
                    if entry.get("mdf2"):
                        if mdf2_en and mdf2_col:
                            for m in entry["mdf2"]:
                                try_export(do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")
                        elif mdf2_en and entry_blank:
                            for m in entry["mdf2"]:
                                try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}")

                    sfur_en = self.get_enabled(scene, character_id, entry_id, "sfur")
                    sfur_col = self.get_binding(scene, character_id, entry_id, "sfur")
                    if entry.get("sfur"):
                        if sfur_en and sfur_col:
                            try_export(do_export_sfur, make_full(entry["sfur"], grp_bp), sfur_col, f"SFUR {entry_id}")
                        elif sfur_en and entry_blank:
                            try_blank("sfur", make_full(entry["sfur"], grp_bp), f"SFUR {entry_id}")

                    chain2_en = self.get_enabled(scene, character_id, entry_id, "chain2")
                    chain2_col = self.get_binding(scene, character_id, entry_id, "chain2")
                    if entry.get("chain2"):
                        if chain2_en and chain2_col:
                            for c in _as_list(entry["chain2"]):
                                try_export(do_export_chain2, make_full(c, grp_bp), chain2_col, f"CHAIN2 {entry_id}")
                        elif chain2_en and entry_blank:
                            for c in _as_list(entry["chain2"]):
                                try_blank("chain2", make_full(c, grp_bp), f"CHAIN2 {entry_id}")

                    clsp_en = self.get_enabled(scene, character_id, entry_id, "clsp")
                    clsp_col = self.get_binding(scene, character_id, entry_id, "clsp")
                    if entry.get("clsp"):
                        if clsp_en and clsp_col:
                            for c in _as_list(entry["clsp"]):
                                try_export(do_export_clsp, make_full(c, grp_bp), clsp_col, f"CLSP {entry_id}")
                        elif clsp_en and entry_blank:
                            for c in _as_list(entry["clsp"]):
                                try_blank("clsp", make_full(c, grp_bp), f"CLSP {entry_id}")

        if fail_count > 0:
            op.report({'WARNING'}, f"Done: {export_count} exported, {fail_count} failed, {skip_count} skipped")
        else:
            op.report({'INFO'}, f"Done: {export_count} exported, {skip_count} skipped")
        return {'FINISHED'}


# ============================================================
# UI
# ============================================================

EXPORTER_WINDOW_WIDTH = 600


def _get_filtered_collections(suffix):
    result = []
    type_map = {"mesh": "RE_MESH_COLLECTION", "mdf2": "RE_MDF_COLLECTION", "sfur": "RE_SFUR_COLLECTION", "chain2": "RE_CHAIN_COLLECTION"}
    name_sfx_map = {"mesh": ".mesh", "mdf2": ".mdf2", "sfur": ".sfur", "chain2": ".chain", "clsp": ".clsp"}
    target_type = type_map.get(suffix, "")
    name_sfx = name_sfx_map.get(suffix, "")
    for c in bpy.data.collections:
        col_type = c.get("~TYPE", "")
        # Match by type
        if target_type and col_type == target_type:
            icon = f"COLLECTION_{c.color_tag}" if c.color_tag != "NONE" else "OUTLINER_COLLECTION"
            result.append((c.name, c.name, "", icon, len(result)))
            continue
        # Match by extension
        if name_sfx and (c.name.endswith(name_sfx) or f"{name_sfx}." in c.name):
            result.append((c.name, c.name, "", "OUTLINER_COLLECTION", len(result)))
    if not result:
        result.append(("NONE", "No matching collections", "", "ERROR", 0))
    return result


def _get_armatures():
    result = []
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            result.append((obj.name, obj.name, "", 'ARMATURE_DATA', len(result)))
    if not result:
        result.append(("NONE", "No armatures", "", "ERROR", 0))
    return result


def group_supported_slots(scheme, group_name):
    """Which of the 5 slots a group actually shows a picker for, mirroring
    _draw_group_detail_simplified's own gating -- needed again by paste, so it
    can skip a slot the target group has no picker for at all."""
    group = next((g for g in scheme["groups"] if g["name"] == group_name), None) if scheme else None
    if group is None:
        return {}
    entries = group["entries"]
    if not any(e.get("simplified") == "user" for e in entries):
        return {}
    return {
        "mesh": True,
        "mdf2": True,
        "sfur": any(e.get("sfur") and e.get("simplified_sfur", e.get("simplified", "user")) != "skip"
                   for e in entries),
        "chain2": any(e.get("chain2") and e.get("simplified_chain2", e.get("simplified", "user")) != "skip"
                     for e in entries),
        "clsp": any(e.get("clsp") and e.get("simplified_clsp", e.get("simplified", "user")) != "skip"
                   for e in entries),
    }


def _mark_group_issues(groups, report):
    """Set ``has_issues`` on each group list item whose pair label carries an
    error in the report -- either the bare group name (simplified) or
    ``"<group> / <entry>"`` (normal)."""
    from . import pre_export_check_ops as pec
    parts = pec.pr.parts_with_errors(report)
    for item in groups:
        prefix_entry = item.group_name + " / "
        item.has_issues = any(p == item.group_name or p.startswith(prefix_entry)
                              for p in parts)


#: Per-session clipboard for copy/paste of a group's bindings.  Module-level, not
#: Scene data -- it is per-session clipboard state, not part of the .blend.  Shared
#: across games on purpose: nothing can paste across games anyway, since a paste
#: only applies slots the target group has and both sides name the same collections.
_group_clipboard = {}


class _Ops:
    """bl_idnames for one game, so draw code reads ``OPS.pick_binding``."""

    def __init__(self, prefix):
        for name in ("batch_export", "batch_export_dialog", "toggle_entry", "toggle_simplified",
                     "pick_binding", "pick_armature", "clear_sg", "clear_se",
                     "copy_group_bindings", "paste_group_bindings", "clear_normal_binding",
                     "clear_all_bindings", "set_natives_root"):
            setattr(self, name, f"{prefix}.{name}")


def build_classes(exp):
    """The operator, property-group and UI-list classes for *exp*'s game."""
    spec = exp.spec
    P = spec.op_prefix.upper()
    OPS = _Ops(spec.op_prefix)

    class BatchExport(bpy.types.Operator):
        bl_idname = OPS.batch_export
        bl_label = f"{spec.code} Batch Export"
        bl_options = {'REGISTER'}

        def execute(self, context):
            show_console = console_export.get_preferences(context).show_console_on_batch_export
            with console_export.kept_open_for_export(show_console):
                return exp.run(self, context)

    class ToggleEntry(bpy.types.Operator):
        bl_idname = OPS.toggle_entry
        bl_label = "Toggle"
        bl_options = {'INTERNAL'}
        character_id: StringProperty()
        entry_id: StringProperty()
        suffix: StringProperty()

        def execute(self, context):
            current = exp.get_enabled(context.scene, self.character_id, self.entry_id, self.suffix)
            exp.set_enabled(context.scene, self.character_id, self.entry_id, self.suffix, not current)
            return {'FINISHED'}

    class ToggleSimplified(bpy.types.Operator):
        bl_idname = OPS.toggle_simplified
        bl_label = "Toggle Simplified"
        bl_options = {'INTERNAL'}

        def execute(self, context):
            context.scene[exp.simplified_key] = not exp.use_simplified(context.scene)
            return {'FINISHED'}

    # One operator for 5 slots x 3 scopes; the scope/slot pair arrives as
    # operator properties.  'EMPTY' has no call site -- the per-entry "empty"
    # bindings are only ever cleared, never picked -- but the capability exists.
    class PickBinding(bpy.types.Operator):
        bl_idname = OPS.pick_binding
        bl_label = "Pick Collection"
        bl_options = {'INTERNAL'}
        bl_property = "collection_name"

        #: 'ENTRY' | 'GROUP' | 'EMPTY'. A plain string, not an enum, because
        #: bl_property already designates collection_name as the searched enum.
        scope: StringProperty(default="ENTRY")
        slot: StringProperty()
        character_id: StringProperty()
        entry_id: StringProperty()
        group_name: StringProperty()
        collection_name: bpy.props.EnumProperty(
            name="Collection",
            items=lambda self, ctx: _get_filtered_collections(self.slot)
        )

        def invoke(self, context, event):
            context.window_manager.invoke_search_popup(self)
            return {'RUNNING_MODAL'}

        def execute(self, context):
            if self.collection_name != "NONE":
                scene = context.scene
                if self.scope == "GROUP":
                    exp.set_group_binding(scene, self.character_id, self.group_name, self.slot,
                                          self.collection_name)
                elif self.scope == "EMPTY":
                    exp.set_empty_binding(scene, self.character_id, self.slot, self.collection_name)
                elif self.scope == "ENTRY":
                    exp.set_binding(scene, self.character_id, self.entry_id, self.slot,
                                    self.collection_name)
                else:
                    # Silently doing nothing is how a typo'd scope would hide.
                    self.report({'ERROR'}, f"unknown pick scope {self.scope!r}")
                    return {'CANCELLED'}
            return {'FINISHED'}

    class PickArmature(bpy.types.Operator):
        bl_idname = OPS.pick_armature
        bl_label = "Pick Armature"
        bl_options = {'INTERNAL'}
        bl_property = "armature_name"
        character_id: StringProperty()
        armature_name: bpy.props.EnumProperty(name="Armature",
                                              items=lambda self, ctx: _get_armatures())

        def invoke(self, context, event):
            context.window_manager.invoke_search_popup(self)
            return {'RUNNING_MODAL'}

        def execute(self, context):
            if self.armature_name != "NONE":
                exp.set_binding(context.scene, self.character_id, "_fbxskel", "fbxskel", self.armature_name)
            return {'FINISHED'}

    class ClearSimplifiedGroup(bpy.types.Operator):
        bl_idname = OPS.clear_sg
        bl_label = "Clear Group Binding"
        bl_options = {'INTERNAL'}
        character_id: StringProperty()
        group_name: StringProperty()
        suffix: StringProperty()

        def execute(self, context):
            exp.set_group_binding(context.scene, self.character_id, self.group_name, self.suffix, "")
            return {'FINISHED'}

    class ClearSimplifiedEmpty(bpy.types.Operator):
        bl_idname = OPS.clear_se
        bl_label = "Clear Empty Binding"
        bl_options = {'INTERNAL'}
        character_id: StringProperty()
        suffix: StringProperty()

        def execute(self, context):
            exp.set_empty_binding(context.scene, self.character_id, self.suffix, "")
            return {'FINISHED'}

    class CopyGroupBindings(bpy.types.Operator):
        bl_idname = OPS.copy_group_bindings
        bl_label = "Copy Group Bindings"
        bl_options = {'INTERNAL'}
        character_id: StringProperty()
        group_name: StringProperty()

        @classmethod
        def description(cls, context, properties):
            return T("core.scheme_batch_export.copy_bindings_desc")

        def execute(self, context):
            global _group_clipboard
            scene = context.scene
            clip = {}
            for slot in SLOTS:
                cur = exp.get_group_binding(scene, self.character_id, self.group_name, slot)
                if cur:
                    clip[slot] = cur
            _group_clipboard = clip
            if clip:
                self.report({'INFO'}, T("core.scheme_batch_export.copy_done").format(
                    n=len(clip), group=self.group_name))
            else:
                self.report({'WARNING'}, T("core.scheme_batch_export.copy_nothing").format(
                    group=self.group_name))
            return {'FINISHED'}

    class PasteGroupBindings(bpy.types.Operator):
        bl_idname = OPS.paste_group_bindings
        bl_label = "Paste Group Bindings"
        bl_options = {'INTERNAL', 'UNDO'}
        character_id: StringProperty()
        group_name: StringProperty()

        @classmethod
        def description(cls, context, properties):
            return T("core.scheme_batch_export.paste_bindings_desc")

        @classmethod
        def poll(cls, context):
            return poll_msg.require(cls, _group_clipboard, "core.poll.need_copied_bindings")

        def execute(self, context):
            scene = context.scene
            settings = scene.mhw_suite_settings
            scheme = exp.load_scheme(getattr(settings, spec.scheme_setting))
            supported = group_supported_slots(scheme, self.group_name)

            applied = 0
            for slot, value in _group_clipboard.items():
                if not supported.get(slot):
                    continue
                exp.set_group_binding(scene, self.character_id, self.group_name, slot, value)
                applied += 1

            if applied:
                self.report({'INFO'}, T("core.scheme_batch_export.paste_done").format(
                    n=applied, group=self.group_name))
            else:
                self.report({'WARNING'}, T("core.scheme_batch_export.paste_nothing").format(
                    group=self.group_name))
            return {'FINISHED'}

    class ClearNormalBinding(bpy.types.Operator):
        bl_idname = OPS.clear_normal_binding
        bl_label = "Clear"
        bl_options = {'INTERNAL'}
        character_id: StringProperty()
        entry_id: StringProperty()
        suffix: StringProperty()

        def execute(self, context):
            exp.set_binding(context.scene, self.character_id, self.entry_id, self.suffix, "")
            return {'FINISHED'}

    class ClearAllBindings(bpy.types.Operator):
        bl_idname = OPS.clear_all_bindings
        bl_label = "Clear All Currently Selected"
        bl_description = "Clear all mesh/mdf/sfur/chain2 bindings for this scheme"
        bl_options = {'REGISTER', 'UNDO'}
        scheme_file: StringProperty()

        def execute(self, context):
            scheme = exp.load_scheme(self.scheme_file)
            if not scheme:
                return {'CANCELLED'}
            char_id = scheme["character_id"]
            scene = context.scene
            exp.set_binding(scene, char_id, "_fbxskel", "fbxskel", "")
            for group in scheme["groups"]:
                for sfx in SLOTS:
                    exp.set_group_binding(scene, char_id, group["name"], sfx, "")
                for entry in group["entries"]:
                    for sfx in SLOTS:
                        exp.set_binding(scene, char_id, entry["id"], sfx, "")
            for sfx in SLOTS:
                exp.set_empty_binding(scene, char_id, sfx, "")
            self.report({'INFO'}, "All bindings for this scheme cleared")
            return {'FINISHED'}

    # ── Group list -- left column of the master-detail layout ──────────────
    # Only the selected group's detail is drawn, so the popup's height is
    # bounded by its biggest single group instead of the whole scheme.

    class GroupListItem(bpy.types.PropertyGroup):
        group_name: StringProperty()
        entry_count: IntProperty()
        #: Set from the aggregated pre-export check right before this list draws,
        #: so a group with a problem is visible without opening the report.
        has_issues: BoolProperty()

    class UL_Groups(bpy.types.UIList):
        bl_idname = f"{P}_UL_Groups"

        def draw_item(self, context, layout, data, item, icon,
                      active_data, active_propname, index):
            layout.label(text=f"{item.group_name} ({item.entry_count})",
                         icon='ERROR' if item.has_issues else 'FILE_FOLDER')

    class BatchExportDialog(bpy.types.Operator):
        bl_idname = OPS.batch_export_dialog
        bl_label = spec.title
        bl_options = {'REGISTER'}

        groups: CollectionProperty(type=GroupListItem)
        group_index: IntProperty()

        def invoke(self, context, event):
            return context.window_manager.invoke_props_dialog(self, width=EXPORTER_WINDOW_WIDTH)

        def _sync_groups(self, scheme, scheme_file):
            """Repopulate the group list only when the selected character scheme
            actually changed since the last draw -- rebuilding it every redraw
            would reset ``group_index`` on every unrelated property change."""
            if getattr(self, '_groups_scheme_file', None) == scheme_file:
                return
            self._groups_scheme_file = scheme_file
            self.groups.clear()
            for group in scheme["groups"]:
                item = self.groups.add()
                item.group_name = group["name"]
                item.entry_count = len(group["entries"])
            self.group_index = 0

        def draw(self, context):
            from . import export_autofix
            from . import pre_export_check_ops as pec
            layout = self.layout
            scene = context.scene
            settings = scene.mhw_suite_settings

            layout.prop(settings, spec.scheme_setting, text="Character")

            # Natives root
            natives_root = mod_root.read(scene, spec.natives_root_key)
            row = layout.row(align=True)
            row.operator(OPS.set_natives_root, text="Natives Root", icon='FILE_FOLDER')
            if natives_root:
                parts = natives_root.replace("\\", "/").rstrip("/").split("/")
                short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
                row.label(text=f".../{short}")
            else:
                row.label(text="Not set", icon='ERROR')

            scheme_file = getattr(settings, spec.scheme_setting)
            if not scheme_file or scheme_file == 'NONE':
                layout.label(text="Select a character scheme", icon='INFO')
                return
            scheme = exp.load_scheme(scheme_file)
            if not scheme:
                layout.label(text="Failed to load scheme", icon='ERROR')
                return

            character_id = scheme["character_id"]
            use_simplified = exp.use_simplified(scene)
            self._sync_groups(scheme, scheme_file)

            # Simplified toggle
            layout.separator()
            row = layout.row()
            simp_icon = 'CHECKBOX_HLT' if use_simplified else 'CHECKBOX_DEHLT'
            row.operator(OPS.toggle_simplified, text="", icon=simp_icon, emboss=False)
            row.label(text="Use Simplified Export", icon='SORTBYEXT')

            # --- FBXSKEL (always shown) ---
            fbxskel_path = scheme.get("fbxskel", "")
            if fbxskel_path:
                layout.separator()
                box = layout.box()
                row = box.row(align=True)
                fbx_en = exp.get_enabled(scene, character_id, "_fbxskel", "fbxskel")
                op = row.operator(OPS.toggle_entry, text="",
                                  icon='CHECKBOX_HLT' if fbx_en else 'CHECKBOX_DEHLT', emboss=False)
                op.character_id = character_id; op.entry_id = "_fbxskel"; op.suffix = "fbxskel"
                row.label(text="FBXSKEL", icon='ARMATURE_DATA')
                cur_arm = exp.get_binding(scene, character_id, "_fbxskel", "fbxskel")
                op_p = row.operator(OPS.pick_armature, text=cur_arm if cur_arm else "Select armature...",
                                    icon='DOWNARROW_HLT')
                op_p.character_id = character_id

                native_path = exp.native_skeleton_for(fbxskel_path)
                row2 = box.row(align=True)
                if native_path and os.path.isfile(native_path):
                    row2.label(text=T("core.scheme_batch_export.will_align_native_skeleton").format(
                        name=os.path.basename(native_path)), icon='ARMATURE_DATA')
                else:
                    row2.label(text=T("core.scheme_batch_export.native_skeleton_not_found"), icon='ERROR')

            layout.separator()
            row = layout.row()
            op_c = row.operator(OPS.clear_all_bindings, text="Clear All Selected", icon='TRASH')
            op_c.scheme_file = scheme_file

            layout.prop(settings, spec.blank_setting, text=T("ui.prop.use_blank_export"), icon='FILE_BLANK')
            if spec.autofix_game is not None:
                export_autofix.draw_toggle(layout, settings, spec.autofix_game)

            # Run the check before the list draws, so each row can carry its own
            # issue icon; the summary line at the bottom reuses the same result.
            if spec.check_game is not None:
                pairs = exp.gather_check_pairs(scene, character_id, scheme, use_simplified)
                entries = pec.ensure_checked(self, context, spec.check_game, pairs, natives_root,
                                             autofix_pairs=exp.bound_pairs(scene, scheme, use_simplified))
                _mark_group_issues(self.groups, entries)

            layout.separator()
            split = layout.split(factor=0.35)
            col1, col2 = split.column(), split.column()
            col1.template_list(UL_Groups.bl_idname, "", self, "groups", self, "group_index",
                               rows=max(4, min(len(self.groups), 10)))

            selected_group = None
            if self.groups and 0 <= self.group_index < len(self.groups):
                item = self.groups[self.group_index]
                selected_group = next((g for g in scheme["groups"] if g["name"] == item.group_name), None)

            # Below the list rather than inside the detail box, so it does not
            # read as one more slot. Simplified-mode only -- normal mode's
            # bindings are per-entry, there is nothing group-level to copy.
            if use_simplified and selected_group is not None:
                user_entries = [e for e in selected_group["entries"] if e.get("simplified") == "user"]
                if user_entries:
                    row = col1.row(align=True)
                    op_copy = row.operator(OPS.copy_group_bindings,
                                           text=T("core.scheme_batch_export.copy_bindings"), icon='COPYDOWN')
                    op_copy.character_id = character_id; op_copy.group_name = selected_group["name"]
                    op_paste = row.operator(OPS.paste_group_bindings,
                                            text=T("core.scheme_batch_export.paste_bindings"), icon='PASTEDOWN')
                    op_paste.character_id = character_id; op_paste.group_name = selected_group["name"]

            if selected_group is not None:
                box = col2.box()
                if use_simplified:
                    self._draw_group_detail_simplified(box, scene, character_id, selected_group)
                else:
                    self._draw_group_detail_normal(box, scene, character_id, selected_group)

            if spec.check_game is not None:
                pec.draw_summary_row(self, layout)

        def _draw_group_detail_simplified(self, layout, scene, character_id, group):
            group_name = group["name"]
            user_entries = [e for e in group["entries"] if e.get("simplified") == "user"]
            empty_count = sum(1 for e in group["entries"] if e.get("simplified") == "empty")
            skip_count = sum(1 for e in group["entries"] if e.get("simplified") == "skip")

            layout.label(text=group_name, icon='FILE_FOLDER')

            if not user_entries:
                info = []
                if empty_count: info.append(f"{empty_count} empty")
                if skip_count: info.append(f"{skip_count} skip")
                layout.label(text=f"({', '.join(info)})" if info else "—")
                return

            # Label above the picker, not beside it: this box is only 35% of the
            # dialog's width, and a long collection name in a sibling row gets
            # silently ellipsis-clipped by the button widget.
            def slot_row(slot, label, icon):
                layout.label(text=label, icon=icon)
                row = layout.row(align=True)
                cur = exp.get_group_binding(scene, character_id, group_name, slot)
                op = row.operator(OPS.pick_binding, text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                op.scope = "GROUP"
                op.slot = slot
                op.character_id = character_id; op.group_name = group_name
                if cur:
                    op_c = row.operator(OPS.clear_sg, text="", icon='X')
                    op_c.character_id = character_id; op_c.group_name = group_name; op_c.suffix = slot

            supported = group_supported_slots({"groups": [group]}, group_name)
            slot_row("mesh", "MESH:", 'OUTLINER_OB_MESH')
            slot_row("mdf2", "MDF2:", 'MATERIAL')
            if supported.get("sfur"):
                slot_row("sfur", "SFUR:", 'OUTLINER_OB_CURVES')
            if supported.get("chain2"):
                slot_row("chain2", "CHAIN2:", 'PHYSICS')
            if supported.get("clsp"):
                slot_row("clsp", "CLSP:", 'PHYSICS')

            info = [f"{len(user_entries)} user"]
            if empty_count: info.append(f"{empty_count} empty")
            if skip_count: info.append(f"{skip_count} skip")
            layout.separator()
            layout.label(text=f"Entries: {', '.join(info)}")

        def _draw_group_detail_normal(self, layout, scene, character_id, group):
            layout.label(text=group["name"], icon='FILE_FOLDER')
            for entry in group["entries"]:
                entry_id = entry["id"]
                header = entry_id
                note = entry.get("note", "")
                if note:
                    header += f"  [{note}]"
                entry_box = layout.box()
                entry_box.label(text=header)

                # Label on its own row, picker+clear on the next: a long
                # collection name sharing a row with the label gets clipped.
                for slot, label, base_icon in (
                        ("mesh", "MESH", 'OUTLINER_OB_MESH'),
                        ("mdf2", f"MDF2 x{len(entry.get('mdf2') or [])}", 'MATERIAL'),
                        ("sfur", "SFUR", 'OUTLINER_OB_CURVES'),
                        ("chain2", "CHAIN2", 'PHYSICS'),
                        ("clsp", "CLSP", 'PHYSICS')):
                    if not entry.get(slot):
                        continue
                    cur = exp.get_binding(scene, character_id, entry_id, slot)
                    ic = base_icon
                    if cur and cur in bpy.data.collections:
                        ct = bpy.data.collections[cur].color_tag
                        if ct != "NONE":
                            ic = f"COLLECTION_{ct}"
                    entry_box.label(text=label, icon=ic)
                    row = entry_box.row(align=True)
                    op_p = row.operator(OPS.pick_binding,
                                        text=cur if cur else "Select...", icon='DOWNARROW_HLT')
                    op_p.scope = "ENTRY"
                    op_p.slot = slot
                    op_p.character_id = character_id; op_p.entry_id = entry_id
                    if cur:
                        op_c = row.operator(OPS.clear_normal_binding, text="", icon='X')
                        op_c.character_id = character_id; op_c.entry_id = entry_id; op_c.suffix = slot
                if entry.get("gpuc"):
                    entry_box.label(text="GPUC: " + T("core.scheme_batch_export.gpuc_blank"),
                                    icon='FILE_BLANK')

        def execute(self, context):
            getattr(getattr(bpy.ops, spec.op_prefix), "batch_export")()
            return {'FINISHED'}

    classes = [GroupListItem, UL_Groups, PickBinding, ToggleEntry, ToggleSimplified,
               PickArmature, BatchExportDialog, ClearSimplifiedGroup, ClearSimplifiedEmpty,
               CopyGroupBindings, PasteGroupBindings, ClearNormalBinding, ClearAllBindings,
               BatchExport]
    # Distinct Python names per game: Blender keys PropertyGroups and UILists by
    # class name, and two games' identically named classes would collide.
    for cls in classes:
        kind = ("_UL_" if issubclass(cls, bpy.types.UIList)
                else "_PG_" if issubclass(cls, bpy.types.PropertyGroup) else "_OT_")
        cls.__name__ = cls.__qualname__ = P + kind + cls.__name__.replace("UL_", "")
    return classes
