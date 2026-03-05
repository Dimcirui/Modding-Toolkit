import bpy
import json
import os


def _get_export_schemes_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(addon_dir, "assets", "export_schemes")
    os.makedirs(d, exist_ok=True)
    return d


_scheme_cache = []

def get_schemes_callback(self, context):
    global _scheme_cache
    _scheme_cache = []
    d = _get_export_schemes_dir()
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                name = f.replace('.json', '')
                _scheme_cache.append((f, name, ""))
    if not _scheme_cache:
        _scheme_cache.append(('NONE', "No scheme", ""))
    return _scheme_cache


def _load_scheme(filename):
    filepath = os.path.join(_get_export_schemes_dir(), filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _make_key(character_id, entry_id, suffix):
    key = f"re9ex_{character_id}_{entry_id}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "")


def _get_binding(scene, character_id, entry_id, suffix):
    return scene.get(_make_key(character_id, entry_id, suffix), "")


def _set_binding(scene, character_id, entry_id, suffix, value):
    scene[_make_key(character_id, entry_id, suffix)] = value


def _make_en_key(character_id, entry_id, suffix):
    key = f"re9en_{character_id}_{entry_id}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "")


def _get_enabled(scene, character_id, entry_id, suffix):
    return scene.get(_make_en_key(character_id, entry_id, suffix), True)


def _set_enabled(scene, character_id, entry_id, suffix, value):
    scene[_make_en_key(character_id, entry_id, suffix)] = value


# Simplified mode keys
def _get_simplified_group_key(character_id, group_name, suffix):
    key = f"re9sg_{character_id}_{group_name}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")


def _get_simplified_group_binding(scene, character_id, group_name, suffix):
    return scene.get(_get_simplified_group_key(character_id, group_name, suffix), "")


def _set_simplified_group_binding(scene, character_id, group_name, suffix, value):
    scene[_get_simplified_group_key(character_id, group_name, suffix)] = value


def _get_simplified_empty_key(character_id, suffix):
    return f"re9se_{character_id}_{suffix}"


def _get_simplified_empty_binding(scene, character_id, suffix):
    return scene.get(_get_simplified_empty_key(character_id, suffix), "")


def _set_simplified_empty_binding(scene, character_id, suffix, value):
    scene[_get_simplified_empty_key(character_id, suffix)] = value


MESH_SETTINGS = {
    "exportAllLODs": True,
    "autoSolveRepeatedUVs": True,
    "preserveSharpEdges": True,
    "rotate90": True,
    "useBlenderMaterialName": False,
    "preserveBoneMatrices": False,
    "exportBoundingBoxes": False,
}


def _do_export_mesh(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_mesh.exportfile(filepath=filepath, targetCollection=collection_name, **MESH_SETTINGS)

def _do_export_mdf2(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_mdf.exportfile(filepath=filepath, targetCollection=collection_name)

def _do_export_sfur(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_sfur.exportfile(filepath=filepath, targetCollection=collection_name)

def _do_export_fbxskel(filepath, armature_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_fbxskel.exportfile(filepath=filepath, targetArmature=armature_name)


class RE9_OT_BatchExport(bpy.types.Operator):
    """RE9 batch exporter"""
    bl_idname = "re9.batch_export"
    bl_label = "RE9 Batch Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not hasattr(bpy.ops, 're_mesh') or not hasattr(bpy.ops.re_mesh, 'exportfile'):
            self.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        natives_root = scene.get("re9_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "Set natives root directory first")
            return {'CANCELLED'}

        scheme_file = settings.re9_export_scheme
        if not scheme_file or scheme_file == 'NONE':
            self.report({'ERROR'}, "No export scheme selected")
            return {'CANCELLED'}

        scheme = _load_scheme(scheme_file)
        if not scheme:
            self.report({'ERROR'}, f"Failed to load: {scheme_file}")
            return {'CANCELLED'}

        character_id = scheme["character_id"]
        base_path = scheme["base_path"].replace("\\", "/")
        use_simplified = scene.get("re9_use_simplified", False)

        export_count = 0
        fail_count = 0
        skip_count = 0

        def make_full(rel, bp_override=None):
            bp = (bp_override or base_path).replace("/", os.sep)
            return os.path.join(natives_root, bp, rel.replace("/", os.sep))

        def try_export(func, filepath, target, label):
            nonlocal export_count, fail_count, skip_count
            if not target or target == "NONE":
                skip_count += 1
                return
            # Check target exists
            if func == _do_export_fbxskel:
                if target not in bpy.data.objects or bpy.data.objects[target].type != 'ARMATURE':
                    print(f"[RE9] SKIP {label}: armature '{target}' not found")
                    skip_count += 1
                    return
            else:
                if target not in bpy.data.collections:
                    print(f"[RE9] SKIP {label}: collection '{target}' not found")
                    skip_count += 1
                    return
            try:
                print(f"[RE9] {label}: {target} -> {os.path.basename(filepath)}")
                func(filepath, target)
                export_count += 1
            except Exception as err:
                print(f"[RE9] FAILED {label}: {err}")
                fail_count += 1

        # --- FBXSKEL ---
        fbxskel_path = scheme.get("fbxskel", "")
        if fbxskel_path:
            fbx_enabled = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            fbx_arm = _get_binding(scene, character_id, "_fbxskel", "fbxskel")
            if fbx_enabled and fbx_arm:
                full = os.path.join(natives_root, "stm", "character", fbxskel_path.replace("/", os.sep))
                try_export(_do_export_fbxskel, full, fbx_arm, "FBXSKEL")

        # --- Per entry ---
        for group in scheme["groups"]:
            group_name = group["name"]
            grp_bp = group.get("base_path")  # Optional per-group base_path override
            for entry in group["entries"]:
                entry_id = entry["id"]
                simp = entry.get("simplified", "user")
                simp_sfur = entry.get("simplified_sfur", "")

                if use_simplified:
                    # Determine mesh/mdf2 collection based on simplified rule
                    if simp == "skip":
                        continue
                    elif simp == "user":
                        mesh_col = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
                        mdf2_col = _get_simplified_group_binding(scene, character_id, group_name, "mdf2")
                    elif simp == "empty":
                        mesh_col = _get_simplified_empty_binding(scene, character_id, "mesh")
                        mdf2_col = _get_simplified_empty_binding(scene, character_id, "mdf2")
                    else:
                        continue

                    # sfur
                    sfur_col = ""
                    if simp_sfur == "empty" and entry.get("sfur"):
                        sfur_col = _get_simplified_empty_binding(scene, character_id, "sfur")

                    # Export mesh
                    if entry.get("mesh") and mesh_col:
                        try_export(_do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")

                    # Export mdf2s
                    if entry.get("mdf2") and mdf2_col:
                        for m in entry["mdf2"]:
                            try_export(_do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")

                    # Export sfur
                    if entry.get("sfur") and sfur_col:
                        try_export(_do_export_sfur, make_full(entry["sfur"], grp_bp), sfur_col, f"SFUR {entry_id}")

                else:
                    # Normal mode: use per-entry bindings
                    mesh_en = _get_enabled(scene, character_id, entry_id, "mesh")
                    mesh_col = _get_binding(scene, character_id, entry_id, "mesh")
                    if mesh_en and mesh_col and entry.get("mesh"):
                        try_export(_do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")

                    mdf2_en = _get_enabled(scene, character_id, entry_id, "mdf2")
                    mdf2_col = _get_binding(scene, character_id, entry_id, "mdf2")
                    if mdf2_en and mdf2_col and entry.get("mdf2"):
                        for m in entry["mdf2"]:
                            try_export(_do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")

                    sfur_en = _get_enabled(scene, character_id, entry_id, "sfur")
                    sfur_col = _get_binding(scene, character_id, entry_id, "sfur")
                    if sfur_en and sfur_col and entry.get("sfur"):
                        try_export(_do_export_sfur, make_full(entry["sfur"], grp_bp), sfur_col, f"SFUR {entry_id}")

        if fail_count > 0:
            self.report({'WARNING'}, f"Done: {export_count} exported, {fail_count} failed, {skip_count} skipped")
        else:
            self.report({'INFO'}, f"Done: {export_count} exported, {skip_count} skipped")
        return {'FINISHED'}


class RE9_OT_SetNativesRoot(bpy.types.Operator):
    """Select the natives root directory"""
    bl_idname = "re9.set_natives_root"
    bl_label = "Set Natives Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        context.scene["re9_natives_root"] = self.directory
        self.report({'INFO'}, f"Natives root: {self.directory}")
        return {'FINISHED'}


classes = [
    RE9_OT_BatchExport,
    RE9_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)