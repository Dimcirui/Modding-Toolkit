import sys
import time
import bpy
from bpy.app.translations import pgettext as _
from dataclasses import dataclass
from ..core.bone_mapper import BoneMapManager, resolve_preset
from ..core.standard_ops import _build_fuzzy_preset_bones


@dataclass
class REChainConfig:
    chain_format: str = '.chain2'
    chain_file_type: str = 'chain2'
    auto_create_collection: bool = False
    collection_name: str = ''
    tuning: dict | None = None
    settings_mode: str = 'SHARED'
    selected_collection: str = ''
    sync_orientation: bool = False


def _patch_chain_cleanup(disable=True):
    """批量替换 alignChains + setChainBoneColor 为 no-op 或恢复。"""
    saved = []
    for mod in sys.modules.values():
        has_align = hasattr(mod, 'alignChains') and callable(mod.alignChains)
        has_color = hasattr(mod, 'setChainBoneColor') and callable(mod.setChainBoneColor)
        if has_align and has_color:
            saved.append((mod, mod.alignChains, mod.setChainBoneColor))
            if disable:
                mod.alignChains = lambda: None
                mod.setChainBoneColor = lambda x: None
    return saved


def _decompose_chains(head_pb, armature, physics_bones):
    """将以 head_pb 为根的物理链递归分解为多条线性路径。"""
    paths = []

    def walk(pb, current_path):
        current_path = current_path + [pb.name]

        bone_data = armature.data.bones.get(pb.name)
        if not bone_data:
            paths.append(current_path)
            return

        physics_children = [
            armature.pose.bones[c.name]
            for c in bone_data.children
            if c.name in physics_bones
            and armature.pose.bones.get(c.name)
            and not c.name.endswith('_End')
        ]

        if not physics_children:
            end_pb = armature.pose.bones.get(f"{pb.name}_End")
            if end_pb and end_pb.name in physics_bones:
                current_path = current_path + [end_pb.name]
            paths.append(current_path)
            return

        if len(physics_children) == 1:
            walk(physics_children[0], current_path)
            return

        main_child = next(
            (c for c in physics_children if c.get("chain_role") == "main_continue"),
            None
        )

        if main_child:
            walk(main_child, current_path)
            for branch in physics_children:
                if branch != main_child:
                    walk(branch, [])
        else:
            end_pb = armature.pose.bones.get(f"{pb.name}_End")
            if end_pb and end_pb.name in physics_bones:
                current_path = current_path + [end_pb.name]
            paths.append(current_path)
            for child in physics_children:
                walk(child, [])

    walk(head_pb, [])
    return paths


def _is_valid_chain_collection(col):
    """与 RE Chain Editor 的 filterChainCollection 逻辑一致"""
    t = col.get("~TYPE", "")
    return (t in ("RE_CHAIN_COLLECTION", "RE_CLSP_COLLECTION")
            and (".chain" in col.name or ".clsp" in col.name))


def _build_physics_bones_set(context, armature):
    """构建物理骨骼名称集合（排除预设骨）。"""
    settings = context.scene.mhw_suite_settings
    mapper = BoneMapManager()
    _x, _ = resolve_preset(settings.import_preset_enum, armature, True)
    if _x and mapper.load_preset(_x, is_import_x=True):
        preset_bones = _build_fuzzy_preset_bones(mapper, armature)
    else:
        preset_bones = set()
    return {b.name for b in armature.data.bones if b.name not in preset_bones}


def _auto_create_chain_collection(config: REChainConfig):
    """创建集合 + Chain Header 并应用游戏特调。

    调用 RE Chain Editor 的 create_chain_header 操作符，
    post-hoc 覆盖调优字段。

    返回 (collection, header_obj, error_message | None)。
    """
    toolpanel = getattr(bpy.context.scene, 're_chain_toolpanel', None)
    if toolpanel is None:
        return None, None, "RE Chain Editor toolpanel not found"

    old_file_type = toolpanel.chainFileType
    old_active = bpy.context.view_layer.objects.active

    try:
        toolpanel.chainFileType = config.chain_file_type

        result = bpy.ops.re_chain.create_chain_header(
            collectionName=config.collection_name,
            chainFormat=config.chain_format,
        )
        if result != {'FINISHED'}:
            return None, None, "create_chain_header failed"

        full_name = config.collection_name + config.chain_format
        col = bpy.data.collections.get(full_name)
        if col is None:
            return None, None, f"Collection not found: {full_name}"

        header = next(
            (o for o in col.all_objects if o.get("TYPE") == "RE_CHAIN_HEADER"),
            None
        )

        if config.tuning:
            h = header.re_chain_header
            for attr, val in config.tuning.items():
                try:
                    setattr(h, attr, val)
                except (AttributeError, TypeError, ValueError):
                    pass

        return col, header, None

    finally:
        toolpanel.chainFileType = old_file_type
        if old_active and old_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = old_active


def _sync_chain_orientations(armature, chain_head_names, physics_bones):
    """在 Edit 模式下将所有物理链首（及其物理子孙）对齐到各自的身体父级朝向。

    chain_head_names: 链首骨骼名称列表（pose bone 名，在 edit 模式下同样有效）
    physics_bones:    物理骨骼名称集合，用于在递归时跳过身体骨子树
    """
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    def align_to_parent(eb):
        parent = eb.parent
        if parent is None:
            return
        parent_dir = (parent.tail - parent.head).normalized()
        eb.tail = eb.head + parent_dir * eb.length
        eb.roll = parent.roll

    def recurse(eb):
        align_to_parent(eb)
        for child in eb.children:
            if child.name in physics_bones:
                recurse(child)
            # body-bone children and their subtrees are silently skipped

    synced = 0
    for name in chain_head_names:
        eb = edit_bones.get(name)
        if eb is None:
            continue
        recurse(eb)
        synced += 1

    bpy.ops.object.mode_set(mode='POSE')
    return synced


def auto_create_re_chains(context, armature, config: REChainConfig):
    """核心 RE Chain 创建逻辑，按游戏参数化配置。"""
    col = None

    if config.auto_create_collection:
        col, header, error = _auto_create_chain_collection(config)
        if error or col is None:
            return {'CANCELLED'}
    else:
        col = bpy.data.collections.get(config.selected_collection)
        if col is None:
            toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
            if toolpanel and toolpanel.chainCollection:
                col = toolpanel.chainCollection
        if col is None:
            return {'CANCELLED'}
        header = next(
            (o for o in col.all_objects if o.get("TYPE") == "RE_CHAIN_HEADER"),
            None
        )
        if header is None:
            return {'CANCELLED'}

    toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
    if toolpanel is None:
        return {'CANCELLED'}
    toolpanel.chainCollection = col

    chain_heads = [pb for pb in armature.pose.bones if pb.get("chain_role") in ("head", "branch_head")]
    if not chain_heads:
        return {'CANCELLED'}

    physics_bones = _build_physics_bones_set(context, armature)

    if config.sync_orientation:
        chain_head_names = [pb.name for pb in chain_heads]
        n = _sync_chain_orientations(armature, chain_head_names, physics_bones)
        print(f"[ChainGen] sync_orientation: aligned {n} chain heads", file=sys.stderr)
        # _sync_chain_orientations leaves us in POSE mode; re-fetch chain_heads
        # so any pose-bone references remain valid after the mode round-trip.
        chain_heads = [pb for pb in armature.pose.bones if pb.get("chain_role") in ("head", "branch_head")]

    t_decompose = time.perf_counter()
    all_entries = []
    for head_pb in chain_heads:
        paths = _decompose_chains(head_pb, armature, physics_bones)
        for path in paths:
            all_entries.append((head_pb, paths, path))
    t_decompose = time.perf_counter() - t_decompose
    print(f"[ChainGen] _decompose_chains: {t_decompose:.4f}s  "
          f"({len(chain_heads)} heads -> {len(all_entries)} paths)", file=sys.stderr)

    created = 0
    skipped = 0

    if config.settings_mode == 'SHARED':
        if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
            return {'CANCELLED'}

    saved_experimental = getattr(toolpanel, 'experimentalPoseModeOptions', False)
    _patches = _patch_chain_cleanup(disable=True)

    t_loop = time.perf_counter()
    try:
        for idx, (_head_pb, _head_paths, path) in enumerate(all_entries, 1):
            t_settings = 0.0
            if config.settings_mode == 'SEPARATE':
                t0 = time.perf_counter()
                if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                    skipped += 1
                    continue
                t_settings = time.perf_counter() - t0

            bpy.ops.pose.select_all(action='DESELECT')
            for bone_name in path:
                pb2 = armature.pose.bones.get(bone_name)
                if pb2:
                    pb2.bone.select = True
            first_pb = armature.pose.bones.get(path[0]) if path else None
            if first_pb:
                armature.data.bones.active = first_pb.bone
            toolpanel.experimentalPoseModeOptions = True

            t0 = time.perf_counter()
            if bpy.ops.re_chain.chain_from_bone() == {'FINISHED'}:
                created += 1
            else:
                skipped += 1
            t_chain = time.perf_counter() - t0

            print(f"[ChainGen] Chain {idx:3d}/{len(all_entries)}  "
                  f"settings={t_settings:.4f}s  create={t_chain:.4f}s  "
                  f"bones={len(path):2d}", file=sys.stderr)
    finally:
        _patch_chain_cleanup(disable=False)
        if _patches and created > 0:
            mod, _align, _color = _patches[0]
            _align()
            _color(armature)
        toolpanel.experimentalPoseModeOptions = saved_experimental

    t_loop = time.perf_counter() - t_loop
    print(f"[ChainGen] --- loop: {t_loop:.4f}s  created={created}  skipped={skipped} ---",
          file=sys.stderr)

    return {'FINISHED'}
