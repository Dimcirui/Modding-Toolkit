import bpy
import json
import os
import shutil

from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available


def _get_export_schemes_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(addon_dir, "assets", "export_schemes", "re4")
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
    key = f"re4ex_{character_id}_{entry_id}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "")


def _get_binding(scene, character_id, entry_id, suffix):
    return scene.get(_make_key(character_id, entry_id, suffix), "")


def _set_binding(scene, character_id, entry_id, suffix, value):
    scene[_make_key(character_id, entry_id, suffix)] = value


def _make_en_key(character_id, entry_id, suffix):
    key = f"re4en_{character_id}_{entry_id}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "")


def _get_enabled(scene, character_id, entry_id, suffix):
    return scene.get(_make_en_key(character_id, entry_id, suffix), True)


def _set_enabled(scene, character_id, entry_id, suffix, value):
    scene[_make_en_key(character_id, entry_id, suffix)] = value


# Simplified mode keys
def _get_simplified_group_key(character_id, group_name, suffix):
    key = f"re4sg_{character_id}_{group_name}_{suffix}"
    return key.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")


def _get_simplified_group_binding(scene, character_id, group_name, suffix):
    return scene.get(_get_simplified_group_key(character_id, group_name, suffix), "")


def _set_simplified_group_binding(scene, character_id, group_name, suffix, value):
    scene[_get_simplified_group_key(character_id, group_name, suffix)] = value


def _get_simplified_empty_key(character_id, suffix):
    return f"re4se_{character_id}_{suffix}"


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
    call_re_mesh_op('exportfile', filepath=filepath, targetCollection=collection_name, **MESH_SETTINGS)

def _do_export_mdf2(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_mdf.exportfile(filepath=filepath, targetCollection=collection_name)

def _do_export_chain(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_chain.exportfile(filepath=filepath, targetCollection=collection_name)

def _do_export_fbxskel(filepath, armature_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_fbxskel.exportfile(filepath=filepath, targetArmature=armature_name)


def _get_armature_from_collection(col_name):
    if not col_name or col_name not in bpy.data.collections:
        return None
    arms = [o for o in bpy.data.collections[col_name].objects if o.type == 'ARMATURE']
    return arms[0] if len(arms) == 1 else None


def _find_body_arm_for_fbxskel(scene, scheme, use_simplified):
    character_id = scheme["character_id"]
    body_groups = scheme.get("body_groups_for_fbxskel", [])
    groups_by_name = {g["name"]: g for g in scheme.get("groups", [])}
    for group_name in body_groups:
        col_name = None
        if use_simplified:
            col_name = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
        else:
            group = groups_by_name.get(group_name)
            if group:
                for entry in group["entries"]:
                    if entry.get("mesh"):
                        binding = _get_binding(scene, character_id, entry["id"], "mesh")
                        if binding:
                            col_name = binding
                            break
        if col_name:
            arm = _get_armature_from_collection(col_name)
            if arm is not None:
                return arm
    return None

def _get_blank_path(filetype, filename=None):
    """Return the path to a blank file in blank_files/re4/.
    If filename is given, use that directly; otherwise fall back to blank.<filetype>."""
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    name = filename if filename else f"blank.{filetype}"
    return os.path.join(addon_dir, "assets", "blank_files", "re4", name)


class RE4_OT_BatchExport(bpy.types.Operator):
    """RE4 batch exporter"""
    bl_idname = "re4.batch_export"
    bl_label = "RE4 Batch Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not re_mesh_op_available('exportfile'):
            self.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        natives_root = scene.get("re4_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "Set natives root directory first")
            return {'CANCELLED'}

        scheme_file = settings.re4_export_scheme
        if not scheme_file or scheme_file == 'NONE':
            self.report({'ERROR'}, "No export scheme selected")
            return {'CANCELLED'}

        scheme = _load_scheme(scheme_file)
        if not scheme:
            self.report({'ERROR'}, f"Failed to load: {scheme_file}")
            return {'CANCELLED'}

        character_id = scheme["character_id"]
        base_path = scheme["base_path"].replace("\\", "/")
        use_simplified = scene.get("re4_use_simplified", True)
        use_blank = settings.re4_use_blank_export
        use_body_arm = settings.re4_use_body_arm

        export_count = 0
        fail_count = 0
        skip_count = 0

        export_cache = {}

        def make_full(rel, bp_override=None):
            bp = (bp_override or base_path).replace("/", os.sep)
            return os.path.join(natives_root, "natives", bp, rel.replace("/", os.sep))

        def try_export(func, filepath, target, label):
            nonlocal export_count, fail_count, skip_count
            if not target or target == "NONE":
                skip_count += 1
                return
            if func == _do_export_fbxskel:
                if target not in bpy.data.objects or bpy.data.objects[target].type != 'ARMATURE':
                    print(f"[RE4] SKIP {label}: armature '{target}' not found")
                    skip_count += 1
                    return
            else:
                if target not in bpy.data.collections:
                    print(f"[RE4] SKIP {label}: collection '{target}' not found")
                    skip_count += 1
                    return

            cache_key = (func.__name__, target)
            if cache_key in export_cache:
                try:
                    source_filepath = export_cache[cache_key]
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    shutil.copy2(source_filepath, filepath)
                    print(f"[RE4] {label}: {target} [CACHED] -> {os.path.basename(filepath)}")
                    export_count += 1
                except Exception as err:
                    print(f"[RE4] FAILED {label} [CACHE COPY]: {err}")
                    fail_count += 1
                return

            try:
                print(f"[RE4] {label}: {target} -> {os.path.basename(filepath)}")
                func(filepath, target)
                export_cache[cache_key] = filepath
                export_count += 1
            except Exception as err:
                print(f"[RE4] FAILED {label}: {err}")
                fail_count += 1

        def try_blank(filetype, filepath, label, filename=None):
            nonlocal export_count, skip_count
            blank_src = _get_blank_path(filetype, filename)
            if os.path.isfile(blank_src):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                shutil.copy2(blank_src, filepath)
                print(f"[RE4] {label}: BLANK -> {os.path.basename(filepath)}")
                export_count += 1
            else:
                print(f"[RE4] SKIP blank (file not found): {blank_src}")
                skip_count += 1

        # 收集 fbxskel 配置（延迟到 mesh 之后执行）
        fbxskel_raw = scheme.get("fbxskel", "")
        fbxskel_paths = ([fbxskel_raw] if isinstance(fbxskel_raw, str) else list(fbxskel_raw))
        fbxskel_paths = [p for p in fbxskel_paths if p]
        fbx_enabled = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
        fbx_arm = _get_binding(scene, character_id, "_fbxskel", "fbxskel")

        # --- Per entry ---
        for group in scheme["groups"]:
            group_name = group["name"]
            grp_bp = group.get("base_path")
            for entry in group["entries"]:
                entry_id = entry["id"]
                simp = entry.get("simplified", "user")

                if use_simplified:
                    if simp == "skip":
                        continue
                    elif simp == "user":
                        mesh_col  = _get_simplified_group_binding(scene, character_id, group_name, "mesh")
                        mdf2_col  = _get_simplified_group_binding(scene, character_id, group_name, "mdf2")
                        chain_col = _get_simplified_group_binding(scene, character_id, group_name, "chain")
                    elif simp == "empty":
                        if use_blank:
                            if entry.get("mesh"):
                                try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}",
                                          entry.get("blank_mesh"))
                            if entry.get("mdf2"):
                                for m in entry["mdf2"]:
                                    try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}",
                                              entry.get("blank_mdf2"))
                            if entry.get("chain"):
                                try_blank("chain", make_full(entry["chain"], grp_bp), f"CHAIN {entry_id}",
                                          entry.get("blank_chain"))
                            continue
                        else:
                            mesh_col  = _get_simplified_empty_binding(scene, character_id, "mesh")
                            mdf2_col  = _get_simplified_empty_binding(scene, character_id, "mdf2")
                            chain_col = _get_simplified_empty_binding(scene, character_id, "chain")
                    else:
                        continue

                    if entry.get("mesh"):
                        if mesh_col:
                            try_export(_do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")
                        elif use_blank:
                            try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}")

                    if entry.get("mdf2"):
                        if mdf2_col:
                            for m in entry["mdf2"]:
                                try_export(_do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")
                        elif use_blank:
                            for m in entry["mdf2"]:
                                try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}")

                    if entry.get("chain"):
                        if chain_col:
                            try_export(_do_export_chain, make_full(entry["chain"], grp_bp), chain_col, f"CHAIN {entry_id}")
                        elif use_blank:
                            try_blank("chain", make_full(entry["chain"], grp_bp), f"CHAIN {entry_id}")

                else:
                    # Normal mode: per-entry bindings
                    mesh_en  = _get_enabled(scene, character_id, entry_id, "mesh")
                    mesh_col = _get_binding(scene, character_id, entry_id, "mesh")
                    if entry.get("mesh"):
                        if mesh_en and mesh_col:
                            try_export(_do_export_mesh, make_full(entry["mesh"], grp_bp), mesh_col, f"MESH {entry_id}")
                        elif mesh_en and use_blank:
                            try_blank("mesh", make_full(entry["mesh"], grp_bp), f"MESH {entry_id}")

                    mdf2_en  = _get_enabled(scene, character_id, entry_id, "mdf2")
                    mdf2_col = _get_binding(scene, character_id, entry_id, "mdf2")
                    if entry.get("mdf2"):
                        if mdf2_en and mdf2_col:
                            for m in entry["mdf2"]:
                                try_export(_do_export_mdf2, make_full(m, grp_bp), mdf2_col, f"MDF2 {entry_id}")
                        elif mdf2_en and use_blank:
                            for m in entry["mdf2"]:
                                try_blank("mdf2", make_full(m, grp_bp), f"MDF2 {entry_id}")

                    chain_en  = _get_enabled(scene, character_id, entry_id, "chain")
                    chain_col = _get_binding(scene, character_id, entry_id, "chain")
                    if entry.get("chain"):
                        if chain_en and chain_col:
                            try_export(_do_export_chain, make_full(entry["chain"], grp_bp), chain_col, f"CHAIN {entry_id}")
                        elif chain_en and use_blank:
                            try_blank("chain", make_full(entry["chain"], grp_bp), f"CHAIN {entry_id}")

        # --- FBXSKEL（在 mesh 之后执行，借助 mesh 导出对骨架唯一性的校验）---
        if fbxskel_paths and fbx_enabled:
            if use_body_arm:
                from .operators import do_fakebone, _get_native_skeletons_dir
                from ...core.bone_utils import align_armatures_by_name
                native_file = scheme.get("native_skeleton", "")
                if not native_file:
                    self.report({'WARNING'}, "使用身体骨架: 预设未配置 native_skeleton，跳过 FBXSKEL")
                    fail_count += 1
                else:
                    native_path = os.path.join(_get_native_skeletons_dir(), native_file)
                    if not os.path.isfile(native_path):
                        self.report({'WARNING'}, f"使用身体骨架: 找不到原生骨架文件 {native_file}")
                        fail_count += 1
                    else:
                        body_arm_obj = _find_body_arm_for_fbxskel(scene, scheme, use_simplified)
                        if body_arm_obj is not None:
                            prev_active = context.view_layer.objects.active
                            prev_sel = [o for o in context.selected_objects]
                            for o in prev_sel:
                                o.select_set(False)
                            native_copy = None
                            try:
                                bpy.ops.re_fbxskel.importfile(filepath=native_path)
                                native_copy = context.active_object
                                if native_copy is None or native_copy.type != 'ARMATURE':
                                    raise RuntimeError(f"导入原生骨架失败: {native_path}")
                                native_copy.select_set(False)
                                align_armatures_by_name(body_arm_obj, native_copy, mode='FULL')
                                if settings.re4_use_fakebone:
                                    do_fakebone(context, native_copy, native_path)
                                label_prefix = "FBXSKEL (身体骨架+假头法)" if settings.re4_use_fakebone else "FBXSKEL (身体骨架)"
                                for fbxskel_path in fbxskel_paths:
                                    full = os.path.join(natives_root, "natives", "STM", fbxskel_path.replace("/", os.sep))
                                    try_export(_do_export_fbxskel, full, native_copy.name, f"{label_prefix} {os.path.basename(fbxskel_path)}")
                            except Exception as err:
                                print(f"[RE4] FAILED FBXSKEL (身体骨架): {err}")
                                fail_count += 1
                            finally:
                                if native_copy is not None and native_copy.name in bpy.data.objects:
                                    bpy.data.objects.remove(native_copy, do_unlink=True)
                                context.view_layer.objects.active = prev_active
                                for o in prev_sel:
                                    if o.name in bpy.data.objects:
                                        o.select_set(True)
            elif fbx_arm:
                if settings.re4_use_fakebone:
                    from .operators import do_fakebone, _get_native_skeletons_dir
                    native_file = scheme.get("native_skeleton", "")
                    if not native_file:
                        self.report({'WARNING'}, "假头法: 未选择原生骨架，跳过 FBXSKEL")
                        fail_count += 1
                    else:
                        native_path = os.path.join(_get_native_skeletons_dir(), native_file)
                        if not os.path.isfile(native_path):
                            self.report({'WARNING'}, f"假头法: 找不到原生骨架文件 {native_file}")
                            fail_count += 1
                        else:
                            user_arm_obj = bpy.data.objects.get(fbx_arm)
                            if user_arm_obj is None:
                                self.report({'WARNING'}, f"假头法: 骨架对象 '{fbx_arm}' 不存在")
                                fail_count += 1
                            else:
                                prev_active = context.view_layer.objects.active
                                prev_sel = [o for o in context.selected_objects]
                                prev_hidden = user_arm_obj.hide_viewport
                                for o in prev_sel:
                                    o.select_set(False)
                                user_arm_obj.hide_viewport = False
                                context.view_layer.objects.active = user_arm_obj
                                user_arm_obj.select_set(True)
                                bpy.ops.object.duplicate()
                                arm_copy = context.active_object
                                user_arm_obj.hide_viewport = prev_hidden
                                user_arm_obj.select_set(False)
                                if arm_copy is None:
                                    self.report({'WARNING'}, "假头法: duplicate 失败，无法获取副本对象")
                                    fail_count += 1
                                else:
                                    try:
                                        do_fakebone(context, arm_copy, native_path)
                                        for fbxskel_path in fbxskel_paths:
                                            full = os.path.join(natives_root, "natives", "STM", fbxskel_path.replace("/", os.sep))
                                            try_export(_do_export_fbxskel, full, arm_copy.name, f"FBXSKEL (假头法) {os.path.basename(fbxskel_path)}")
                                    except Exception as err:
                                        print(f"[RE4] FAILED FBXSKEL (假头法): {err}")
                                        fail_count += 1
                                    finally:
                                        if arm_copy is not None and arm_copy.name in bpy.data.objects:
                                            bpy.data.objects.remove(arm_copy, do_unlink=True)
                                        context.view_layer.objects.active = prev_active
                                        for o in prev_sel:
                                            if o.name in bpy.data.objects:
                                                o.select_set(True)
                else:
                    for fbxskel_path in fbxskel_paths:
                        full = os.path.join(natives_root, "natives", "STM", fbxskel_path.replace("/", os.sep))
                        try_export(_do_export_fbxskel, full, fbx_arm, f"FBXSKEL {os.path.basename(fbxskel_path)}")

        if fail_count > 0:
            self.report({'WARNING'}, f"Done: {export_count} exported, {fail_count} failed, {skip_count} skipped")
        else:
            self.report({'INFO'}, f"Done: {export_count} exported, {skip_count} skipped")
        return {'FINISHED'}


class RE4_OT_SetNativesRoot(bpy.types.Operator):
    """选择 RE4 Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"""
    bl_idname = "re4.set_natives_root"
    bl_label = "Set Natives Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        path = self.directory.rstrip("/\\")
        if os.path.basename(path).lower() == "natives":
            path = os.path.dirname(path)
        context.scene["re4_natives_root"] = path
        self.report({'INFO'}, f"RE4 Mod root: {path}")
        return {'FINISHED'}


classes = [
    RE4_OT_BatchExport,
    RE4_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
