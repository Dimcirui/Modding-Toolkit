import os
import bpy


def _addon_root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_reference_skeleton_dir(game_code):
    """assets/reference_skeletons/<game_code>/ 的绝对路径"""
    return os.path.join(_addon_root_dir(), "assets", "reference_skeletons", game_code)


# 【关键】：每个 game_code 各自持有一个全局缓存列表，防止 Blender C 层持有的字符串指针
# 因 Python GC 变成野指针 —— EnumProperty 动态回调返回的列表必须有持久引用
_ref_skeleton_item_caches = {}


def get_reference_skeleton_items(game_code):
    """扫描 assets/reference_skeletons/<game_code>/ 下的 .fbx 文件，供 EnumProperty 使用。"""
    cache = _ref_skeleton_item_caches.setdefault(game_code, [])
    cache.clear()
    d = get_reference_skeleton_dir(game_code)
    if os.path.isdir(d):
        for fname in sorted(os.listdir(d)):
            if fname.lower().endswith(".fbx"):
                stem = os.path.splitext(fname)[0]
                cache.append((fname, stem, ""))
    if not cache:
        cache.append(("NONE", "无可用参考骨架", ""))
    return cache


def import_reference_armature(game_code, filename):
    """通过 Blender 内置 FBX 导入器导入 assets/reference_skeletons/<game_code>/<filename>。

    只保留导入产生的骨架物体本身（其余网格等物体一并清除，避免残留），骨架会被
    重新挂到场景根集合，所在的导入集合若因此变空也会一并清理。不依赖任何外部插件。
    返回骨架物体；文件不存在或导入结果中没有骨架时返回 None。
    """
    filepath = os.path.join(get_reference_skeleton_dir(game_code), filename)
    if not os.path.isfile(filepath):
        return None

    before_objs = set(bpy.data.objects)
    before_cols = set(bpy.data.collections)

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.fbx(filepath=filepath)

    new_objs = [o for o in bpy.data.objects if o not in before_objs]
    new_cols = [c for c in bpy.data.collections if c not in before_cols]

    arm_obj = next((o for o in new_objs if o.type == 'ARMATURE'), None)
    if arm_obj is None:
        for o in new_objs:
            bpy.data.objects.remove(o, do_unlink=True)
        return None

    extras = [o for o in new_objs if o is not arm_obj]

    # 骨架先挂回场景根集合，确保它不随导入集合一起被清理掉
    scene_col = bpy.context.scene.collection
    if arm_obj.name not in scene_col.objects:
        scene_col.objects.link(arm_obj)
    for col in list(arm_obj.users_collection):
        if col != scene_col:
            col.objects.unlink(arm_obj)

    for o in extras:
        bpy.data.objects.remove(o, do_unlink=True)

    # 清理已变为空的导入集合（跳过场景根集合）
    for col in new_cols:
        if col.name in bpy.data.collections and len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)

    return arm_obj
