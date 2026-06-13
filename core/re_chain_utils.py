import sys
import time
import bpy
from .i18n import _
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
    straighten_orientation: bool = False
    # 统一覆写 colliderFilterInfoPath：None=不动；""=留空(RE4/RE9，否则崩溃)；路径=MHWs 标准
    collider_filter_path: str | None = None
    # 创建完所有链之后自动对每个 ChainSettings 组应用角度限制坡度
    apply_angle_ramp: bool = False
    apply_angle_ramp_max: float = 1.047198   # ≈ 60°
    apply_angle_ramp_iter: int = 4


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


def _straighten_chain_orientations(armature, physics_bones):
    """在 Edit 模式下将所有物理骨骼调整为竖直向上（+Z）、扭转归零。"""
    from mathutils import Vector
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones
    up = Vector((0.0, 0.0, 1.0))
    count = 0
    for eb in edit_bones:
        if eb.name in physics_bones:
            length = max(eb.length, 1e-6)
            eb.tail = eb.head + up * length
            eb.roll = 0.0
            count += 1
    bpy.ops.object.mode_set(mode='POSE')
    return count


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
            old_active.select_set(True)
            if old_active.type == 'ARMATURE' and bpy.context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')


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


# 物理参数写入：跳过的元数据键 / 向量键 / 枚举键
_PARAM_SKIP_KEYS = {"presetVersion", "presetType", "subDataValues", "id",
                    "unknQuaternion", "unknPos"}
_PARAM_VECTOR_KEYS = {"gravity"}
_PARAM_ENUM_KEYS = {"windDelayType", "springCalcType", "motionForceCalcType"}


def _apply_params_to_cs(cs_obj, params):
    """把物理参数写入 ChainSettings 对象的 PropertyGroup，返回未能写入的字段名列表。"""
    pg = getattr(cs_obj, "re_chain_chainsettings", None)
    if pg is None:
        return ["<no re_chain_chainsettings>"]
    skipped = []
    for key, val in params.items():
        if key in _PARAM_SKIP_KEYS:
            continue
        if key in _PARAM_VECTOR_KEYS and isinstance(val, list):
            val = tuple(val)
        try:
            setattr(pg, key, val)
            continue
        except (AttributeError, TypeError, ValueError):
            pass
        # 枚举字段可能要求字符串整数（如 windDelayType）
        if key in _PARAM_ENUM_KEYS:
            try:
                setattr(pg, key, str(int(val)))
                continue
            except (AttributeError, TypeError, ValueError):
                pass
        skipped.append(key)
    return skipped


def _is_settings_obj(o):
    return ("SETTING" in str(o.get("TYPE", "")).upper()
            or "SETTING" in o.name.upper())


def _find_new_settings(col, before_names):
    """create_chain_settings 后，从集合里找出新建的 ChainSettings 对象。"""
    new_objs = [o for o in col.all_objects if o.name not in before_names]
    if not new_objs:
        return None
    typed = [o for o in new_objs if _is_settings_obj(o)]
    return typed[0] if typed else new_objs[0]


def _apply_collider_filter(col, before_names, path):
    """对本次新建的所有 ChainSettings 统一设定 colliderFilterInfoPath，返回设定数量。"""
    n = 0
    for o in col.all_objects:
        if o.name in before_names or not _is_settings_obj(o):
            continue
        pg = getattr(o, "re_chain_chainsettings", None)
        if pg is None:
            continue
        try:
            pg.colliderFilterInfoPath = path
            n += 1
        except (AttributeError, TypeError, ValueError):
            pass
    return n


def _apply_angle_ramp_all(context, armature, col, max_angle, iterations):
    """创建完成后，对集合中所有 chain group 应用角度限制坡度。

    re_chain.apply_angle_limit_ramp 算子会遍历 bpy.context.selected_objects 中
    所有 RE_CHAIN_CHAINGROUP / RE_CHAIN_SUBGROUP 一次性处理，并要求 OBJECT 模式、
    active_object 为 chain group。它读取的是 bpy.context.selected_objects——在外层
    算子 execute() 深处直接 bpy.ops 调用时，仅靠 select_set 设置的选择状态不一定被
    算子上下文采纳，一旦为空算子就静默 CANCELLED。因此这里用 temp_override 显式传入
    selected_objects + active_object，并同时真实 select_set 作双保险，单次调用处理全部组。
    """
    group_objs = [o for o in col.all_objects
                  if o.get("TYPE") in ("RE_CHAIN_CHAINGROUP", "RE_CHAIN_SUBGROUP")]
    if not group_objs:
        print("[ChainGen] apply_angle_ramp: no chain group objects found in collection",
              file=sys.stderr)
        return

    if not hasattr(bpy.ops.re_chain, 'apply_angle_limit_ramp'):
        print("[ChainGen] apply_angle_ramp: operator re_chain.apply_angle_limit_ramp unavailable",
              file=sys.stderr)
        return

    prev_active = context.view_layer.objects.active
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # 真实选择（双保险：覆盖那些读取实际选择标志而非上下文的算子内部逻辑）
    try:
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:
        pass
    for o in group_objs:
        try:
            o.select_set(True)
        except Exception:
            pass
    context.view_layer.objects.active = group_objs[0]

    try:
        with context.temp_override(active_object=group_objs[0],
                                   object=group_objs[0],
                                   selected_objects=group_objs,
                                   selected_editable_objects=group_objs):
            res = bpy.ops.re_chain.apply_angle_limit_ramp(
                maxAngleLimit=max_angle, maxIteration=iterations)
        print(f"[ChainGen] apply_angle_ramp: {res} on {len(group_objs)} group(s)",
              file=sys.stderr)
    except Exception as e:
        print(f"[ChainGen] apply_angle_ramp failed: {e}", file=sys.stderr)

    # 恢复活动对象（mode 由调用方保持 OBJECT 即可）
    try:
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:
        pass
    context.view_layer.objects.active = prev_active
    if prev_active:
        try:
            prev_active.select_set(True)
        except Exception:
            pass


def _make_one_chain(armature, toolpanel, path):
    """选中 path 上的骨骼并调用 chain_from_bone，返回是否成功。"""
    bpy.ops.pose.select_all(action='DESELECT')
    for bone_name in path:
        pb2 = armature.pose.bones.get(bone_name)
        if pb2:
            # Blender 4.x: selection lives on Bone data; 5.x: moved to PoseBone
            if hasattr(pb2, 'select'):
                pb2.select = True
            else:
                pb2.bone.select = True
    first_pb = armature.pose.bones.get(path[0]) if path else None
    if first_pb:
        armature.data.bones.active = first_pb.bone
    toolpanel.experimentalPoseModeOptions = True
    return bpy.ops.re_chain.chain_from_bone() == {'FINISHED'}


def _create_chains_guess(armature, toolpanel, col, all_entries, chain_heads, physics_bones):
    """猜测分组模式：按推测类型分组，每组一个 ChainSettings（含参数），
    第 0 组（None）收纳无匹配的链，不写参数。返回 (created, skipped)。"""
    from collections import OrderedDict
    from .chain_classifier import classify_heads, get_physics_params

    heads = {pb.name: pb.bone for pb in chain_heads}
    types_by_head = classify_heads(heads, physics_bones)

    groups = OrderedDict()
    groups[None] = []  # 无匹配组排在最前
    for entry in all_entries:
        head_pb = entry[0]
        t = types_by_head.get(head_pb.name)
        groups.setdefault(t, []).append(entry)

    created = 0
    skipped = 0
    for type_key, entries in groups.items():
        if not entries:
            continue
        label = type_key or "unmatched"
        before = {o.name for o in col.all_objects}
        if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
            skipped += len(entries)
            continue
        if type_key is not None:
            cs = _find_new_settings(col, before)
            params = get_physics_params(type_key)
            if cs is not None and params:
                miss = _apply_params_to_cs(cs, params)
                if miss:
                    print(f"[ChainGen GUESS] {label}: skipped params {miss}", file=sys.stderr)
            elif cs is None:
                print(f"[ChainGen GUESS] {label}: settings object not found", file=sys.stderr)
        grp_created = 0
        for entry in entries:
            if _make_one_chain(armature, toolpanel, entry[2]):
                created += 1
                grp_created += 1
            else:
                skipped += 1
        print(f"[ChainGen GUESS] group={label:24s} chains={grp_created}/{len(entries)}",
              file=sys.stderr)

    return created, skipped


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
        chain_heads = [pb for pb in armature.pose.bones if pb.get("chain_role") in ("head", "branch_head")]

    if config.straighten_orientation:
        n = _straighten_chain_orientations(armature, physics_bones)
        print(f"[ChainGen] straighten_orientation: straightened {n} physics bones", file=sys.stderr)
        chain_heads = [pb for pb in armature.pose.bones if pb.get("chain_role") in ("head", "branch_head")]

    t_decompose = time.perf_counter()
    all_entries = []
    for head_pb in chain_heads:
        paths = _decompose_chains(head_pb, armature, physics_bones)
        for path in paths:
            if len(path) < 2:
                print(f"[ChainGen] skip single-bone path: {path[0] if path else '?'} "
                      f"(RE Chain requires at least head + tail)", file=sys.stderr)
                continue
            all_entries.append((head_pb, paths, path))
    t_decompose = time.perf_counter() - t_decompose
    print(f"[ChainGen] _decompose_chains: {t_decompose:.4f}s  "
          f"({len(chain_heads)} heads -> {len(all_entries)} paths)", file=sys.stderr)

    created = 0
    skipped = 0

    # 记录创建前已有的对象，用于事后定位本次新建的 ChainSettings（统一覆写 collider filter）
    cs_before = {o.name for o in col.all_objects}

    # SHARED：循环外创建唯一 Chain Settings；GUESS 在 _create_chains_guess 内分组创建
    if config.settings_mode == 'SHARED':
        if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
            return {'CANCELLED'}

    saved_experimental = getattr(toolpanel, 'experimentalPoseModeOptions', False)
    _patches = _patch_chain_cleanup(disable=True)

    t_loop = time.perf_counter()
    try:
        if config.settings_mode == 'GUESS':
            created, skipped = _create_chains_guess(
                armature, toolpanel, col, all_entries, chain_heads, physics_bones)
        else:
            for idx, (_head_pb, _head_paths, path) in enumerate(all_entries, 1):
                if config.settings_mode == 'SEPARATE':
                    if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                        skipped += 1
                        continue
                if _make_one_chain(armature, toolpanel, path):
                    created += 1
                else:
                    skipped += 1
    finally:
        _patch_chain_cleanup(disable=False)
        if _patches and created > 0:
            mod, _align, _color = _patches[0]
            _align()
            _color(armature)
        toolpanel.experimentalPoseModeOptions = saved_experimental

    # 统一覆写 collider filter：MHWs 用标准路径；RE4/RE9 留空（否则游戏崩溃）
    if config.collider_filter_path is not None:
        n = _apply_collider_filter(col, cs_before, config.collider_filter_path)
        print(f"[ChainGen] collider filter set on {n} settings -> "
              f"'{config.collider_filter_path}'", file=sys.stderr)

    t_loop = time.perf_counter() - t_loop
    print(f"[ChainGen] --- loop: {t_loop:.4f}s  created={created}  skipped={skipped} ---",
          file=sys.stderr)

    # 所有链及 collider filter 设定完成后，对每个 ChainSettings 组应用角度限制坡度
    if config.apply_angle_ramp and created > 0:
        toolpanel.chainCollection = col  # alignChains() 可能改变了集合指针，重新断言
        _apply_angle_ramp_all(context, armature, col,
                              config.apply_angle_ramp_max, config.apply_angle_ramp_iter)

    return {'FINISHED'}
