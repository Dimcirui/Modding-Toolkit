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


class RE9_OT_BatchExport(bpy.types.Operator):
    """RE9 batch exporter: export mesh, mdf2, sfur and fbxskel files.\nRequires RE Mesh Editor"""
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
            self.report({'ERROR'}, f"Failed to load scheme: {scheme_file}")
            return {'CANCELLED'}

        character_id = scheme["character_id"]
        base_path = scheme["base_path"].replace("\\", "/")

        MESH_SETTINGS = {
            "exportAllLODs": True,
            "autoSolveRepeatedUVs": True,
            "preserveSharpEdges": True,
            "rotate90": True,
            "useBlenderMaterialName": False,
            "preserveBoneMatrices": False,
            "exportBoundingBoxes": False,
        }

        export_count = 0
        fail_count = 0
        skip_count = 0

        # --- FBXSKEL ---
        fbxskel_path = scheme.get("fbxskel", "")
        if fbxskel_path:
            fbxskel_enabled = _get_enabled(scene, character_id, "_fbxskel", "fbxskel")
            fbxskel_armature = _get_binding(scene, character_id, "_fbxskel", "fbxskel")

            if fbxskel_enabled and fbxskel_armature:
                # fbxskel base_path is different: it goes to ch/ch02/ not ch02/0200/
                # The path in JSON is relative to stm/character/ 
                full_path = os.path.join(natives_root, "stm", "character",
                                         fbxskel_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                if fbxskel_armature in bpy.data.objects and bpy.data.objects[fbxskel_armature].type == 'ARMATURE':
                    try:
                        print(f"[RE9 Export] FBXSKEL: {fbxskel_armature} -> {fbxskel_path}")
                        bpy.ops.re_fbxskel.exportfile(
                            filepath=full_path,
                            targetArmature=fbxskel_armature,
                        )
                        export_count += 1
                    except Exception as err:
                        print(f"[RE9 Export] FBXSKEL FAILED: {err}")
                        fail_count += 1
                else:
                    print(f"[RE9 Export] SKIP FBXSKEL: armature '{fbxskel_armature}' not found")
                    skip_count += 1

        # --- MESH / MDF2 / SFUR per entry ---
        for group in scheme["groups"]:
            for entry in group["entries"]:
                entry_id = entry["id"]

                # MESH
                mesh_enabled = _get_enabled(scene, character_id, entry_id, "mesh")
                mesh_collection = _get_binding(scene, character_id, entry_id, "mesh")

                if mesh_enabled and mesh_collection and entry.get("mesh"):
                    rel_path = entry["mesh"].replace("\\", "/")
                    full_path = os.path.join(natives_root, base_path.replace("/", os.sep),
                                             rel_path.replace("/", os.sep))
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)

                    if mesh_collection in bpy.data.collections:
                        try:
                            print(f"[RE9 Export] MESH: {mesh_collection} -> {rel_path}")
                            bpy.ops.re_mesh.exportfile(
                                filepath=full_path,
                                targetCollection=mesh_collection,
                                **MESH_SETTINGS
                            )
                            export_count += 1
                        except Exception as err:
                            print(f"[RE9 Export] MESH FAILED: {err}")
                            fail_count += 1
                    else:
                        print(f"[RE9 Export] SKIP MESH: collection '{mesh_collection}' not found")
                        skip_count += 1

                # MDF2
                mdf2_enabled = _get_enabled(scene, character_id, entry_id, "mdf2")
                mdf2_collection = _get_binding(scene, character_id, entry_id, "mdf2")

                if mdf2_enabled and mdf2_collection and entry.get("mdf2"):
                    if mdf2_collection in bpy.data.collections:
                        for mdf2_rel in entry["mdf2"]:
                            mdf2_rel = mdf2_rel.replace("\\", "/")
                            full_path = os.path.join(natives_root, base_path.replace("/", os.sep),
                                                     mdf2_rel.replace("/", os.sep))
                            os.makedirs(os.path.dirname(full_path), exist_ok=True)
                            try:
                                print(f"[RE9 Export] MDF2: {mdf2_collection} -> {mdf2_rel}")
                                bpy.ops.re_mdf.exportfile(
                                    filepath=full_path,
                                    targetCollection=mdf2_collection,
                                )
                                export_count += 1
                            except Exception as err:
                                print(f"[RE9 Export] MDF2 FAILED: {err}")
                                fail_count += 1
                    else:
                        print(f"[RE9 Export] SKIP MDF2: collection '{mdf2_collection}' not found")
                        skip_count += len(entry["mdf2"])

                # SFUR
                sfur_enabled = _get_enabled(scene, character_id, entry_id, "sfur")
                sfur_collection = _get_binding(scene, character_id, entry_id, "sfur")

                if sfur_enabled and sfur_collection and entry.get("sfur"):
                    sfur_rel = entry["sfur"].replace("\\", "/")
                    full_path = os.path.join(natives_root, base_path.replace("/", os.sep),
                                             sfur_rel.replace("/", os.sep))
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)

                    if sfur_collection in bpy.data.collections:
                        try:
                            print(f"[RE9 Export] SFUR: {sfur_collection} -> {sfur_rel}")
                            bpy.ops.re_sfur.exportfile(
                                filepath=full_path,
                                targetCollection=sfur_collection,
                            )
                            export_count += 1
                        except Exception as err:
                            print(f"[RE9 Export] SFUR FAILED: {err}")
                            fail_count += 1
                    else:
                        print(f"[RE9 Export] SKIP SFUR: collection '{sfur_collection}' not found")
                        skip_count += 1

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