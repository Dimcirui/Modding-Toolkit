"""
MDF2 Generator base — creates MDF2 + textures from Blender mesh materials.

Analyzes Principled BSDF node trees with three strategies per PBR input:
  DIRECT  — Image Texture (or Normal Map → Image Texture) directly connected
  SOLID   — Constant value / unlinked socket → generates 256×256 solid texture
  BAKE    — Complex node chain → uses Cycles to bake the result

Parallel to mdf_tex_processor_base but starts from Blender materials instead
of existing MDF2 materials.
"""

import bpy
import os
import json
import re
import tempfile
import shutil
import time

from .mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
    SRGB_SLOT_TYPES, PBR_DEFAULTS, PBR_CHANNEL_SELECTABLE, _CH,
    _import_tex_utils, _compose_channels,
    make_mdf_path, make_disk_path,
)

# ── Principled BSDF socket → PBR type mapping ─────────────────────────────────

PRINCIPLED_INPUT_MAP = {
    'color':     'Base Color',
    'metallic':  'Metallic',
    'roughness': 'Roughness',
    'normal':    'Normal',
    'alpha':     'Alpha',
    'emissive':  'Emission Color',
    # 'ao' has no Principled BSDF socket — always defaults to SOLID 1.0
}

BAKE_SIZE_DEFAULT = 1024
SOLID_SIZE        = 256


# ── Node analysis ──────────────────────────────────────────────────────────────

def _find_principled_bsdf(material):
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    return None


def _find_emission_shader(material):
    """Return the first Emission shader node in the material, or None."""
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'EMISSION':
            return node
    return None


_MMD_DEV_NAME_HINTS = ('mmdshaderdev', 'mmd_shader', 'mmd shader')
_MMD_COLOR_SOCKET   = 'Base Tex'
_MMD_ALPHA_SOCKET   = 'Base Alpha'


def _find_mmd_shader_dev(material):
    """Return the MMDShaderDev node group if present, or None."""
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree:
            if any(hint in node.node_tree.name.lower() for hint in _MMD_DEV_NAME_HINTS):
                return node
    return None


SHADER_PRINCIPLED = 'principled'
SHADER_EMISSION   = 'emission'
SHADER_MMD_DEV    = 'mmd_shader_dev'
SHADER_UNKNOWN    = 'unknown'


def detect_shader_type(material):
    """Return SHADER_* constant for the dominant shader in the material."""
    if _find_principled_bsdf(material) is not None:
        return SHADER_PRINCIPLED
    if _find_emission_shader(material) is not None:
        return SHADER_EMISSION
    if _find_mmd_shader_dev(material) is not None:
        return SHADER_MMD_DEV
    return SHADER_UNKNOWN


def _analyze_principled_input(principled_node, input_name, mat_name=None, pbr_type=None):
    """
    Returns ('DIRECT', filepath, source_channel) | ('SOLID', value) | ('BAKE', None).

    DIRECT:  Image Texture directly connected, or via a Normal Map node.
             Third element is 'R' (Color output) or 'A' (Alpha output) to
             indicate which source channel should be read during composition.
    SOLID:   Socket unlinked — use default_value as a constant solid texture.
    BAKE:    Complex node chain — Cycles bake required.
    """
    _tag = f"[MDF Gen]   STRATEGY {mat_name}/{pbr_type}" if mat_name and pbr_type else "[MDF Gen]"

    socket = principled_node.inputs.get(input_name)
    if socket is None:
        # print(f"{_tag}: 输入端 '{input_name}' 不存在 → SOLID(0.0)", flush=True)
        return ('SOLID', 0.0)
    if not socket.is_linked:
        # print(f"{_tag}: '{input_name}' 未连接 → SOLID", flush=True)
        return ('SOLID', socket.default_value)

    src = socket.links[0].from_node

    if src.type == 'TEX_IMAGE':
        if not src.image:
            # print(f"{_tag}: TEX_IMAGE({src.name}) 无图片数据 → BAKE", flush=True)
            return ('BAKE', None)
        path = bpy.path.abspath(src.image.filepath)
        if not path:
            # print(f"{_tag}: TEX_IMAGE({src.name}) 路径为空 → BAKE", flush=True)
            return ('BAKE', None)
        if not os.path.isfile(path):
            # print(f"{_tag}: TEX_IMAGE({src.name}) 文件不存在 → BAKE (路径: {path})", flush=True)
            return ('BAKE', None)
        from_sock = socket.links[0].from_socket
        src_ch = 'A' if from_sock.name == 'Alpha' else 'R'
        # print(f"{_tag}: TEX_IMAGE({src.name}) 文件有效 → DIRECT(ch={src_ch})", flush=True)
        return ('DIRECT', path, src_ch)

    if src.type == 'NORMAL_MAP':
        nm_color = src.inputs.get('Color')
        if not nm_color:
            # print(f"{_tag}: Normal Map({src.name}) 无 Color 输入端 → SOLID (默认法线 0.5,0.5,1.0)", flush=True)
            return ('SOLID', (0.5, 0.5, 1.0, 1.0))
        if not nm_color.is_linked:
            # print(f"{_tag}: Normal Map({src.name}) Color 未连接 → SOLID (默认法线 0.5,0.5,1.0)", flush=True)
            return ('SOLID', (0.5, 0.5, 1.0, 1.0))
        nm_src = nm_color.links[0].from_node
        if nm_src.type == 'TEX_IMAGE':
            if not nm_src.image:
                # print(f"{_tag}: Normal Map({src.name}) → TEX_IMAGE({nm_src.name}) 无图片数据 → BAKE", flush=True)
                return ('BAKE', None)
            path = bpy.path.abspath(nm_src.image.filepath)
            if not path:
                # print(f"{_tag}: Normal Map({src.name}) → TEX_IMAGE({nm_src.name}) 路径为空 → BAKE", flush=True)
                return ('BAKE', None)
            if not os.path.isfile(path):
                # print(f"{_tag}: Normal Map({src.name}) → TEX_IMAGE({nm_src.name}) 文件不存在: {path} → BAKE", flush=True)
                return ('BAKE', None)
            # print(f"{_tag}: Normal Map({src.name}) → TEX_IMAGE({nm_src.name}) → DIRECT(ch=R)", flush=True)
            return ('DIRECT', path, 'R')
        # print(f"{_tag}: Normal Map({src.name}) Color ← {nm_src.type}({nm_src.name}) → BAKE", flush=True)
        return ('BAKE', None)

    # print(f"{_tag}: '{input_name}' ← 未识别节点类型 '{src.type}'({src.name}) → BAKE", flush=True)
    return ('BAKE', None)


def analyze_material_strategies(material):
    """
    Returns dict {pbr_type: (strategy, value_or_path)} for all PBR types.
    'ao' always returns ('SOLID', 1.0).

    Handles three shader types:
      Principled BSDF — full PBR analysis per socket
      Emission        — color/emissive from Color socket; others SOLID defaults
      MMDShaderDev    — color from Base Tex, alpha from Base Alpha; others SOLID defaults
    Both non-Principled types are treated as toon-style emissive shaders.
    """
    principled = _find_principled_bsdf(material)
    result = {}

    if principled is not None:
        for pbr_type, input_name in PRINCIPLED_INPUT_MAP.items():
            result[pbr_type] = _analyze_principled_input(principled, input_name, material.name, pbr_type)
        result['ao'] = ('SOLID', 1.0)
        return result

    # Non-Principled defaults (neutral values for unused channels)
    _NON_PBR_DEFAULTS = {
        'metallic':  0.0,
        'roughness': 1.0,
        'normal':    (0.5, 0.5, 1.0, 1.0),
        'alpha':     1.0,
        'emissive':  (0.0, 0.0, 0.0, 1.0),
        'color':     (0.0, 0.0, 0.0, 1.0),
    }
    for pbr_type in PRINCIPLED_INPUT_MAP:
        result[pbr_type] = ('SOLID', _NON_PBR_DEFAULTS.get(pbr_type, 0.0))

    emission = _find_emission_shader(material)
    if emission is not None:
        color_strat        = _analyze_principled_input(emission, 'Color', material.name, 'emissive')
        result['color']    = color_strat
        result['emissive'] = color_strat
    else:
        mmd = _find_mmd_shader_dev(material)
        if mmd is not None:
            result['color']    = _analyze_principled_input(mmd, _MMD_COLOR_SOCKET, material.name, 'color')
            result['alpha']    = _analyze_principled_input(mmd, _MMD_ALPHA_SOCKET, material.name, 'alpha')
            result['emissive'] = result['color']

    result['ao'] = ('SOLID', 1.0)
    return result


def strategy_label(strategy):
    return {'DIRECT': 'Direct', 'SOLID': 'Solid', 'BAKE': 'Bake'}.get(strategy, '?')


def _emissive_strength_is_zero(material):
    """True if Principled BSDF's Emission Strength is unlinked and equals 0."""
    principled = _find_principled_bsdf(material)
    if principled is None:
        return True
    sock = principled.inputs.get('Emission Strength')
    if sock is None:
        return True
    return not sock.is_linked and float(sock.default_value) == 0.0


def _is_emissive_slot(slot_type):
    return 'missive' in slot_type.lower()


def _is_albedo_slot(slot_type, channel_maps):
    """True if any channel of this slot maps from the 'color' PBR type."""
    return any(
        isinstance(v, tuple) and v[0] == 'color'
        for v in channel_maps.get(slot_type, {}).values()
    )


_PRESET_EMISSIVE_CACHE: dict = {}


def preset_has_emissive_slots(preset_path, is_mrl3=False):
    """True if the preset JSON includes any emissive texture slot."""
    if not preset_path or preset_path == 'NONE' or not os.path.isfile(preset_path):
        return False
    if preset_path in _PRESET_EMISSIVE_CACHE:
        return _PRESET_EMISSIVE_CACHE[preset_path]
    try:
        with open(preset_path, encoding='utf-8') as f:
            data = json.load(f)
        if is_mrl3:
            result = any(_is_emissive_slot(e.get('name', ''))
                         for e in data.get('Map List', []))
        else:
            result = any(_is_emissive_slot(b.get('Texture Type', ''))
                         for b in data.get('Texture Bindings', []))
    except Exception:
        result = False
    _PRESET_EMISSIVE_CACHE[preset_path] = result
    return result


# ── Preset loading ─────────────────────────────────────────────────────────────

def _get_re_mesh_editor_addon_dir():
    import addon_utils
    for mod in addon_utils.modules():
        pkg  = getattr(mod, '__package__', '') or getattr(mod, '__name__', '')
        name = mod.bl_info.get('name', '')
        if 'RE Mesh' in name or 'REMeshEditor' in pkg or 're_mesh_editor' in pkg.lower():
            return os.path.dirname(mod.__file__)
    return None


def get_preset_dir_for_game(game_name):
    """Return path to RE Mesh Editor's Presets/{game_name}/ directory, or None."""
    addon_dir = _get_re_mesh_editor_addon_dir()
    if not addon_dir:
        return None
    d = os.path.join(addon_dir, 'Presets', game_name)
    return d if os.path.isdir(d) else None


def load_preset_enum_items(game_name):
    """Return EnumProperty-compatible list for presets of the given game."""
    preset_dir = get_preset_dir_for_game(game_name)
    if not preset_dir:
        return [('NONE', 'RE Mesh Editor presets not found', '')]
    items = []
    try:
        for entry in sorted(os.scandir(preset_dir), key=lambda e: e.name):
            if entry.is_file() and entry.name.endswith('.json'):
                items.append((entry.path, entry.name[:-5], entry.path))
    except Exception:
        pass
    return items if items else [('NONE', f'No presets found for {game_name}', '')]


def guess_best_preset(material_name, preset_items):
    """Keyword-scoring heuristic — returns the best matching preset path."""
    if not preset_items or preset_items[0][0] == 'NONE':
        return 'NONE'

    mat_lower = material_name.lower()
    SCORES = {
        3: ['body', 'skin', 'eye', 'hair', 'face', 'decal', 'emissive', 'cloth'],
        2: ['_emi', 'emit', 'weapon', 'armor'],
        1: ['wp', 'ch', 'pl', 'em', 'sm', 'st', 'gm'],
    }

    best_score, best_len, best_path = -1, 9999, preset_items[0][0]
    for preset_path, preset_name, _ in preset_items:
        if preset_path == 'NONE':
            continue
        score = 0
        pl = preset_name.lower()
        for pts, kws in SCORES.items():
            for kw in kws:
                if kw in mat_lower and kw in pl:
                    score += pts
        if score > best_score or (score == best_score and len(preset_name) < best_len):
            best_score, best_len, best_path = score, len(preset_name), preset_path

    return best_path


# ── Solid texture generation ───────────────────────────────────────────────────

def _generate_solid_texture_path(value, tmp_dir, name_hint, size=SOLID_SIZE):
    """
    Write a solid-colour PNG to tmp_dir and return its path.
    value: float scalar (greyscale) or colour sequence (r,g,b[,a]).
    """
    img_name = f"__gen_solid_{name_hint}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])

    img = bpy.data.images.new(img_name, width=size, height=size, alpha=False)

    if isinstance(value, (int, float)):
        v = float(max(0.0, min(1.0, value)))
        pixel = [v, v, v, 1.0]
    else:
        vals = [float(max(0.0, min(1.0, c))) for c in list(value)[:4]]
        while len(vals) < 4:
            vals.append(1.0)
        pixel = vals

    img.pixels[:] = pixel * (size * size)
    out_path = os.path.join(tmp_dir, f"_solid_{name_hint}.png")
    img.filepath_raw = out_path
    img.file_format  = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return out_path


# ── Composition cache helpers ───────────────────────────────────────────────────

def _make_source_id(strat_val):
    """Return a hashable identifier for a PBR source, or None if uncacheable (BAKE).

    DIRECT → ('DIRECT', normalised_path)
    SOLID  → ('SOLID', (r, g, b, a))
    BAKE   → None
    """
    if not strat_val:
        return None
    strategy = strat_val[0]
    value    = strat_val[1]
    if strategy == 'DIRECT':
        return ('DIRECT', os.path.normpath(value))
    if strategy == 'SOLID':
        if isinstance(value, (int, float)):
            v = round(float(value), 6)
            return ('SOLID', (v, v, v, 1.0))
        else:
            vals = [round(float(max(0.0, min(1.0, c))), 6) for c in list(value)[:4]]
            while len(vals) < 4:
                vals.append(1.0)
            return ('SOLID', tuple(vals))
    return None


def _resolve_solid_rgba(strat_val):
    """Return the 4-channel pixel value from a SOLID strategy, or None."""
    if not strat_val or strat_val[0] != 'SOLID':
        return None
    value = strat_val[1]
    if isinstance(value, (int, float)):
        v = float(max(0.0, min(1.0, value)))
        return (v, v, v, 1.0)
    else:
        vals = [float(max(0.0, min(1.0, c))) for c in list(value)[:4]]
        while len(vals) < 4:
            vals.append(1.0)
        return tuple(vals)


def _try_downgrade_slot(slot_type, strategies, pbr_channels, channel_maps):
    """If every PBR source used by *slot_type* is a constant, return the
    resulting RGBA pixel value as a 4-tuple; otherwise return None."""
    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        return None

    rgba = [0.0, 0.0, 0.0, 0.0]
    for out_ch_name, src in ch_map.items():
        out_i = _CH.get(out_ch_name)
        if out_i is None:
            return None

        if src is None:
            rgba[out_i] = 0.0
        elif isinstance(src, (int, float)):
            rgba[out_i] = float(src)
        elif isinstance(src, tuple):
            pbr_type = src[0]
            in_ch_i  = src[1]
            invert   = len(src) > 2 and src[2] is True

            strat_val = strategies.get(pbr_type)
            if strat_val is None or strat_val[0] != 'SOLID':
                return None

            solid_rgba = _resolve_solid_rgba(strat_val)
            if solid_rgba is None:
                return None

            if pbr_type in PBR_CHANNEL_SELECTABLE:
                override = pbr_channels.get(pbr_type)
                if override:
                    in_ch_i = _CH.get(override, in_ch_i)

            val = solid_rgba[in_ch_i]
            if invert:
                val = 1.0 - val
            rgba[out_i] = val
        else:
            return None

    return tuple(rgba)


# ── Cycles baking ──────────────────────────────────────────────────────────────

def _bake_pbr_channel(material, pbr_type, mesh_obj, size, tmp_dir, context):
    """
    Bake one PBR channel from a Blender material via Cycles.
    Returns path to the saved PNG, or None on failure.

    Special handling:
      metallic    — temporarily routes Metallic link → Roughness, bakes as ROUGHNESS
      alpha       — temporarily routes Alpha link → Emission Color, bakes as EMIT
      emission/MMDShaderDev color/emissive — bakes as EMIT directly (no Principled needed)
    """
    tree = material.node_tree
    principled = _find_principled_bsdf(material)

    if principled is None:
        # Emission shader: can bake color/emissive channels as EMIT pass
        if pbr_type not in ('color', 'emissive'):
            return None
        if _find_emission_shader(material) is None and _find_mmd_shader_dev(material) is None:
            return None

    img_name = f"__gen_bake_{pbr_type}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])
    bake_img = bpy.data.images.new(img_name, width=size, height=size,
                                   alpha=False, float_buffer=True)

    bake_node = tree.nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_img
    tree.nodes.active = bake_node

    tmp_remove  = []   # new links to remove afterward
    tmp_restore = []   # (kind, ...) tuples describing what to undo

    orig_engine = context.scene.render.engine
    # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 原始引擎={orig_engine}", flush=True)

    # ── Save Cycles GPU / device state ──────────────────────────────────────
    cycles_scene = context.scene.cycles
    orig_device  = cycles_scene.device
    orig_samples = cycles_scene.samples
    orig_compute_device_type = None
    orig_dev_use = {}
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
        orig_compute_device_type = cprefs.compute_device_type
        for d in cprefs.devices:
            orig_dev_use[d.name] = d.use
#         print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 原始GPU后端={orig_compute_device_type}, "
#               f"活跃设备={[d.name for d in cprefs.devices if d.use]}", flush=True)
    except Exception:
        pass

    try:
        context.scene.render.engine = 'CYCLES'
        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 切换后引擎={context.scene.render.engine}", flush=True)

        # ── Force GPU compute ───────────────────────────────────────────────
        try:
            cycles_scene.device = 'GPU'
            cycles_scene.samples = 1
            cprefs = bpy.context.preferences.addons['cycles'].preferences
            # Pick the first available GPU backend
            for dt in ('OPTIX', 'CUDA', 'HIP', 'METAL'):
                try:
                    cprefs.compute_device_type = dt
                    cprefs.get_devices()
                    if any(d.type == dt for d in cprefs.devices):
                        break
                except Exception:
                    continue
            for d in cprefs.devices:
                d.use = (d.type == cprefs.compute_device_type)
#             print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: "
#                   f"GPU后端={cprefs.compute_device_type}, "
#                   f"已启用={[d.name for d in cprefs.devices if d.use]}", flush=True)
        except Exception:
            pass

        bake_type   = 'EMIT' if principled is None else 'DIFFUSE'
        bake_kwargs = {}

        if principled is not None:
            if pbr_type == 'color':
                bake_type   = 'DIFFUSE'
                bake_kwargs = {'pass_filter': {'COLOR'}}
                # Zero metallic temporarily so it doesn't darken the diffuse bake
                m_sock = principled.inputs.get('Metallic')
                if m_sock and not m_sock.is_linked:
                    orig_val = m_sock.default_value
                    m_sock.default_value = 0.0
                    tmp_restore.append(('default', m_sock, orig_val))

            elif pbr_type == 'normal':
                bake_type = 'NORMAL'

            elif pbr_type == 'roughness':
                bake_type = 'ROUGHNESS'

            elif pbr_type == 'metallic':
                # Route Metallic source → Roughness socket, bake as ROUGHNESS
                bake_type   = 'ROUGHNESS'
                m_sock = principled.inputs.get('Metallic')
                r_sock = principled.inputs.get('Roughness')
                if m_sock and r_sock and m_sock.is_linked:
                    metal_from = m_sock.links[0].from_socket
                    if r_sock.is_linked:
                        rough_from = r_sock.links[0].from_socket
                        tmp_restore.append(('link', rough_from, r_sock))
                        tree.links.remove(r_sock.links[0])
                    lnk = tree.links.new(metal_from, r_sock)
                    tmp_remove.append(lnk)

            elif pbr_type == 'alpha':
                # Route Alpha source → Emission Color socket, bake as EMIT
                bake_type = 'EMIT'
                a_sock  = principled.inputs.get('Alpha')
                e_sock  = principled.inputs.get('Emission Color')
                if a_sock and e_sock and a_sock.is_linked:
                    alpha_from = a_sock.links[0].from_socket
                    if e_sock.is_linked:
                        emit_from = e_sock.links[0].from_socket
                        tmp_restore.append(('link', emit_from, e_sock))
                        tree.links.remove(e_sock.links[0])
                    lnk = tree.links.new(alpha_from, e_sock)
                    tmp_remove.append(lnk)

            elif pbr_type == 'emissive':
                bake_type = 'EMIT'

        # Activate the target mesh
        prev_active   = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)
        for o in prev_selected:
            o.select_set(False)
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 开始 (type={bake_type}, size={size}, samples={cycles_scene.samples})", flush=True)
        bpy.ops.object.bake(type=bake_type, **bake_kwargs)

        out_path = os.path.join(tmp_dir, f"_baked_{_slugify(material.name)}_{pbr_type}.png")
        bake_img.filepath_raw = out_path
        bake_img.file_format  = 'PNG'
        bake_img.save()

        # Restore selection
        for o in prev_selected:
            o.select_set(True)
        context.view_layer.objects.active = prev_active

        return out_path

    except Exception as e:
        print(f"[MDF Gen] Bake failed {material.name}/{pbr_type}: {e}")
        return None

    finally:
        for lnk in tmp_remove:
            try:
                tree.links.remove(lnk)
            except Exception:
                pass
        for item in tmp_restore:
            if item[0] == 'link':
                _, from_sock, to_sock = item
                tree.links.new(from_sock, to_sock)
            elif item[0] == 'default':
                _, sock, val = item
                sock.default_value = val
        tree.nodes.remove(bake_node)
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])
        context.scene.render.engine = orig_engine
        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 已恢复引擎={context.scene.render.engine}", flush=True)
        # Restore Cycles GPU / device state
        try:
            cycles_scene.device = orig_device
            cycles_scene.samples = orig_samples
        except Exception:
            pass
        if orig_compute_device_type is not None:
            try:
                cprefs = bpy.context.preferences.addons['cycles'].preferences
                cprefs.compute_device_type = orig_compute_device_type
                cprefs.get_devices()
                for d in cprefs.devices:
                    if d.name in orig_dev_use:
                        d.use = orig_dev_use[d.name]
#                 print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: "
#                       f"已恢复GPU后端={orig_compute_device_type}", flush=True)
            except Exception:
                pass


def _detect_max_tex_size(material):
    """扫描节点树，返回所有已加载图像中的最大边长；无贴图时返回 BAKE_SIZE_DEFAULT。"""
    max_size = 0
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                w, h = node.image.size
                max_size = max(max_size, w, h)
    return max_size if max_size > 0 else BAKE_SIZE_DEFAULT


def _get_pbr_paths(material, strategies, tmp_dir, bake_size, context, mesh_obj):
    """
    Resolve each PBR strategy to a file path.
    Returns dict {pbr_type: path_or_None}.
    """
    paths = {}
    for pbr_type, strat_val in strategies.items():
        strategy = strat_val[0]
        value    = strat_val[1]
        if strategy == 'DIRECT':
            paths[pbr_type] = value

        elif strategy == 'SOLID':
            hint = f"{_slugify(material.name)}_{pbr_type}"
            paths[pbr_type] = _generate_solid_texture_path(
                value, tmp_dir, hint, size=SOLID_SIZE)

        elif strategy == 'BAKE':
            if mesh_obj:
                _t_bake = time.time()
                paths[pbr_type] = _bake_pbr_channel(
                    material, pbr_type, mesh_obj, bake_size, tmp_dir, context)
                # print(f"[MDF Gen]   烘培 {pbr_type}: {time.time() - _t_bake:.2f}s", flush=True)
            else:
                print(f"[MDF Gen] No mesh found for baking {material.name}/{pbr_type}, skipping")
                paths[pbr_type] = None
    return paths


# ── Mesh helpers ───────────────────────────────────────────────────────────────

def _slugify(name):
    """Convert to filesystem-safe slug (ASCII, no spaces)."""
    slug = re.sub(r'[^\w\-]', '_', name)
    return slug.strip('_') or 'material'


def _strip_blender_suffix(name):
    """
    Strip Blender's auto-generated duplicate suffix (.001, .002, …) from a
    material name so that 'MyMat.001' resolves to the same tex_name as 'MyMat'.
    Only strips when the suffix is purely numeric (Blender's pattern).
    """
    return re.sub(r'\.\d+$', '', name)


def _import_read_preset_json():
    """Locate and return readPresetJSON from RE Mesh Editor."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mdf.re_mdf_presets'):
            fn = getattr(mod, 'readPresetJSON', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mdf.re_mdf_presets")
            fn = getattr(m, 'readPresetJSON', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _import_create_mdf_collection():
    """Locate createMDFCollection from RE Mesh Editor's blender_re_mdf module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mdf.blender_re_mdf'):
            fn = getattr(mod, 'createMDFCollection', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mdf.blender_re_mdf")
            fn = getattr(m, 'createMDFCollection', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


# ── MHWI (MHW Model Editor) utilities ─────────────────────────────────────────

def _get_mhwi_module_file():
    """Return the __file__ of MHW Model Editor's mrl3_presets module, or None."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mrl3.mrl3_presets'):
            return mod.__file__
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mrl3.mrl3_presets")
            return m.__file__
        except Exception:
            continue
    return None


def get_mhwi_preset_dir():
    """Return path to MHW Model Editor's MaterialPresets/ directory, or None."""
    f = _get_mhwi_module_file()
    if not f:
        return None
    d = os.path.join(os.path.dirname(f), 'MaterialPresets')
    return d if os.path.isdir(d) else None


def load_mhwi_preset_enum_items():
    """Return EnumProperty items from MHW Model Editor MaterialPresets."""
    preset_dir = get_mhwi_preset_dir()
    if not preset_dir:
        return [('NONE', 'MHW Model Editor presets not found', '')]
    items = []
    try:
        for entry in sorted(os.scandir(preset_dir), key=lambda e: e.name):
            if entry.is_file() and entry.name.endswith('.json'):
                items.append((entry.path, entry.name[:-5], entry.path))
    except Exception:
        pass
    return items if items else [('NONE', 'No MHWI presets found', '')]


def _import_mhwi_create_collection():
    """Locate createCollection from MHW Model Editor's blender_functions module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.common.blender_functions'):
            fn = getattr(mod, 'createCollection', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.common.blender_functions")
            fn = getattr(m, 'createCollection', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _import_mhwi_tex_convert():
    """Locate convertDDSFileToTex from MHW Model Editor."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.tex_function'):
            fn = getattr(mod, 'convertDDSFileToTex', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            tm = importlib.import_module(f"{pkg}.modules.tex.tex_function")
            fn = getattr(tm, 'convertDDSFileToTex', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _import_mhwi_read_preset():
    """Locate readPresetJSON from MHW Model Editor's mrl3_presets module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mrl3.mrl3_presets'):
            fn = getattr(mod, 'readPresetJSON', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mrl3.mrl3_presets")
            fn = getattr(m, 'readPresetJSON', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _call_mhwi_read_preset(filepath, target_col):
    """
    Call MHW Model Editor's readPresetJSON with a specific target collection.

    readPresetJSON() reads from bpy.context.scene.mhw_mrl3_toolpanel.mrl3Collection
    and returns True/False instead of the new object.  We temporarily override the
    collection pointer, diff collection contents before/after, and return the new obj.
    """
    readPresetJSON = _import_mhwi_read_preset()
    if readPresetJSON is None:
        raise RuntimeError("Cannot find readPresetJSON from MHW Model Editor")

    before = {obj.name for obj in target_col.all_objects}

    toolpanel = bpy.context.scene.mhw_mrl3_toolpanel
    original_col = toolpanel.mrl3Collection
    toolpanel.mrl3Collection = target_col
    try:
        result = readPresetJSON(filepath)
    finally:
        toolpanel.mrl3Collection = original_col

    if not result:
        raise RuntimeError(f"readPresetJSON returned False for '{filepath}'")

    after = {obj.name for obj in target_col.all_objects}
    new_names = after - before
    if not new_names:
        raise RuntimeError("readPresetJSON succeeded but no new object in collection")

    return target_col.all_objects[next(iter(new_names))]


# ── Mesh helpers ───────────────────────────────────────────────────────────────

def _separate_mesh_by_material(context, mesh_col):
    """
    Separate every multi-material mesh in the collection by material, then
    rename all resulting objects to RE Engine format: Group_0_Sub_N__MatName.
    """
    # Snapshot — the list grows during separation
    initial = [o for o in mesh_col.all_objects if o.type == 'MESH']

    for obj in context.scene.objects:
        obj.select_set(False)

    for obj in initial:
        if not obj.data or len(obj.data.materials) <= 1:
            continue
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)

    for obj in context.scene.objects:
        obj.select_set(False)

    sub_index = 0
    for obj in sorted(list(mesh_col.all_objects), key=lambda o: o.name):
        if obj.type != 'MESH':
            continue
        mat  = obj.data.materials[0] if obj.data.materials else None
        slug = _slugify(_strip_blender_suffix(mat.name)) if mat else f"unnamed_{sub_index}"
        new_name      = f"Group_0_Sub_{sub_index}__{slug}"
        obj.name      = new_name
        obj.data.name = new_name
        sub_index    += 1


# ── Base operator: Refresh ─────────────────────────────────────────────────────

class MdfGenRefreshBase(bpy.types.Operator):
    bl_label   = "Refresh"
    bl_options = {'INTERNAL'}
    _settings_attr = ""
    _game_name     = ""

    @classmethod
    def _load_preset_items(cls):
        """Override in subclasses that use a different preset system (e.g. MHWI)."""
        return load_preset_enum_items(cls._game_name)

    def execute(self, context):
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)

        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, "请先选择网格集合")
            return {'CANCELLED'}

        mat_names = set()
        for obj in mesh_col.all_objects:
            if obj.type == 'MESH':
                for mat in obj.data.materials:
                    if mat:
                        mat_names.add(mat.name)

        if not mat_names:
            self.report({'ERROR'}, "集合中没有找到材质")
            return {'CANCELLED'}

        preset_items = cls._load_preset_items()
        settings.material_list.clear()

        for mat_name in sorted(mat_names):
            mat = bpy.data.materials.get(mat_name)
            if not mat:
                continue

            strategies   = analyze_material_strategies(mat)
            shader_type  = detect_shader_type(mat)
            item = settings.material_list.add()
            item.blender_material = mat_name

            best = guess_best_preset(mat_name, preset_items)
            try:
                item.material_preset = best
            except Exception:
                pass

            # Auto-enable toon for emissive-style shaders
            if shader_type in (SHADER_EMISSION, SHADER_MMD_DEV):
                try:
                    item.use_toon = True
                except Exception:
                    pass

            # Strategy summary shown in collapsed view
            parts = []
            for pt in ('color', 'normal', 'roughness', 'metallic', 'alpha', 'emissive'):
                sv = strategies.get(pt, ('?', None))
                parts.append(f"{pt[0].upper()}:{strategy_label(sv[0])}")
            item.strategy_display = '  '.join(parts)

            # Per-channel strategy labels (for expanded view)
            for pt in ('color', 'metallic', 'roughness', 'normal', 'alpha', 'emissive'):
                sv = strategies.get(pt, ('?', None))
                setattr(item, f"strat_{pt}", strategy_label(sv[0]))

        self.report({'INFO'}, f"已扫描 {len(settings.material_list)} 个材质")
        return {'FINISHED'}


# ── Base operator: Process ─────────────────────────────────────────────────────

class MdfGenProcessBase(bpy.types.Operator):
    bl_label   = "Generate MDF2 + Textures"
    bl_options = {'REGISTER'}

    _settings_attr     = ""
    _game_name         = ""
    _natives_root_key  = ""
    _tex_version       = 0
    _use_art_prefix    = True
    _path_fixed_prefix = ""   # Optional path segment prepended to texture_base_path (e.g. RE4)
    _abbrev_map        = {}
    _channel_maps      = {}
    _null_tex_by_type  = {}
    _log_tag           = "MDF Gen"
    _bake_size         = BAKE_SIZE_DEFAULT

    def execute(self, context):
        _t_total = time.time()
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)

        natives_root = context.scene.get(cls._natives_root_key, "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, "请先设置 Natives Root 目录（natives 的上级文件夹）")
            return {'CANCELLED'}

        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, "请先选择网格集合")
            return {'CANCELLED'}

        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, "请填写 Base Path")
            return {'CANCELLED'}

        if cls._path_fixed_prefix:
            base_path = cls._path_fixed_prefix.strip('/') + '/' + base_path.strip('/')

        if not settings.material_list:
            self.report({'ERROR'}, "请先点击 Refresh 加载材质")
            return {'CANCELLED'}

        _t_import = time.time()
        ImageListToDDS, DDSToTex = _import_tex_utils()
        # print(f"[{cls._log_tag}] 加载 RE Mesh Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ImageListToDDS is None:
            self.report({'ERROR'}, "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用")
            return {'CANCELLED'}

        _t_import = time.time()
        readPresetJSON = _import_read_preset_json()
        # print(f"[{cls._log_tag}] 加载 Preset 模块: {time.time() - _t_import:.2f}s", flush=True)
        if readPresetJSON is None:
            self.report({'ERROR'}, "无法加载 RE Mesh Editor Preset 工具")
            return {'CANCELLED'}

        mdf_col = self._get_or_create_mdf_collection(context, mesh_col, settings)

        temp_dir = tempfile.mkdtemp(prefix="mdf_gen_")
        comp_cache = {}  # (slot_type, source_ids, pbr_channels) → (composed, disk, mdf)
        export_count = fail_count = 0

        try:
            for mat_entry in settings.material_list:
                try:
                    _t_mat = time.time()
                    self._process_one_material(
                        context, mat_entry, settings, mdf_col,
                        natives_root, base_path, temp_dir,
                        ImageListToDDS, DDSToTex, readPresetJSON, cls, mesh_col,
                        comp_cache,
                    )
                    export_count += 1
                    print(f"[{cls._log_tag}] OK: {mat_entry.blender_material} ({time.time() - _t_mat:.2f}s)")
                except Exception as e:
                    import traceback
                    print(f"[{cls._log_tag}] FAIL {mat_entry.blender_material}: {e}")
                    traceback.print_exc()
                    fail_count += 1
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        _t_sep = time.time()
        try:
            _separate_mesh_by_material(context, mesh_col)
            # print(f"[{cls._log_tag}] 分离网格: {time.time() - _t_sep:.2f}s", flush=True)
        except Exception as e:
            print(f"[{cls._log_tag}] Mesh separate/rename warning: {e}")

        # print(f"[{cls._log_tag}] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)
        if fail_count:
            self.report({'WARNING'}, f"完成: 成功 {export_count}, 失败 {fail_count}")
        else:
            self.report({'INFO'}, f"完成: 成功生成 {export_count} 个材质的 MDF2 + 贴图")
        return {'FINISHED'}  # MdfGenProcessBase

    # ── helpers ────────────────────────────────────────────────────────────────

    def _get_or_create_mdf_collection(self, context, mesh_col, settings):
        mdf_name = settings.mdf_collection_name.strip()
        if not mdf_name:
            mdf_name = (mesh_col.name.replace('.mesh', '.mdf2')
                        if '.mesh' in mesh_col.name
                        else mesh_col.name + ".mdf2")

        if mdf_name in bpy.data.collections:
            return bpy.data.collections[mdf_name]

        parent = next(
            (c for c in bpy.data.collections
             if mesh_col.name in [ch.name for ch in c.children]),
            None,
        )

        createMDFCollection = _import_create_mdf_collection()
        if createMDFCollection:
            return createMDFCollection(mdf_name, parent)

        # Fallback if RE Mesh Editor function is unavailable
        col = bpy.data.collections.new(mdf_name)
        col["~TYPE"] = "RE_MDF_COLLECTION"
        col.color_tag = "COLOR_05"
        if parent:
            parent.children.link(col)
        else:
            context.scene.collection.children.link(col)
        return col

    def _process_one_material(self, context, mat_entry, settings, mdf_col,
                               natives_root, base_path, temp_dir,
                               ImageListToDDS, DDSToTex, readPresetJSON, cls, mesh_col,
                               comp_cache):
        mat_name = mat_entry.blender_material
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            raise ValueError(f"Material '{mat_name}' not found")

        preset_path = mat_entry.material_preset
        if not preset_path or preset_path == 'NONE':
            raise ValueError(f"No preset selected for '{mat_name}'")
        if not os.path.isfile(preset_path):
            raise FileNotFoundError(f"Preset not found: {preset_path}")

        # Find a representative mesh object (needed for baking)
        mesh_obj = next(
            (obj for obj in mesh_col.all_objects
             if obj.type == 'MESH'
             and any(m and m.name == mat_name for m in obj.data.materials)),
            None,
        )

        _t = time.time()
        strategies = analyze_material_strategies(mat)
        # print(f"[{cls._log_tag}]   分析材质节点: {time.time() - _t:.2f}s", flush=True)
        bake_size  = max(_detect_max_tex_size(mat), cls._bake_size)
        _t = time.time()
        pbr_paths  = _get_pbr_paths(
            mat, strategies, temp_dir, bake_size, context, mesh_obj)
        # print(f"[{cls._log_tag}]   解析PBR路径 (含烘培): {time.time() - _t:.2f}s", flush=True)

        # User-provided AO override (Blender has no built-in AO node)
        if getattr(mat_entry, 'use_ao', False):
            ao_path_raw = getattr(mat_entry, 'ao_image', '')
            if ao_path_raw:
                ao_path = bpy.path.abspath(ao_path_raw)
                if ao_path and os.path.isfile(ao_path):
                    strategies['ao'] = ('DIRECT', ao_path, 'R')
                    pbr_paths['ao'] = ao_path

        # Build source-channel overrides from DIRECT strategies where the
        # Image Texture's Alpha output (not Color) was connected — this
        # ensures alpha data is read from the A channel instead of R.
        pbr_channels = {}
        for pbr_type, strat_val in strategies.items():
            if strat_val[0] == 'DIRECT' and len(strat_val) > 2 and strat_val[2] != 'R':
                pbr_channels[pbr_type] = strat_val[2]

        tex_name = _slugify(_strip_blender_suffix(mat_name))

        # Determine which slot types the preset expects
        _t = time.time()
        with open(preset_path, encoding='utf-8') as f:
            preset_data = json.load(f)
        # print(f"[{cls._log_tag}]   加载Preset JSON: {time.time() - _t:.2f}s", flush=True)
        slot_types = [b["Texture Type"] for b in preset_data.get("Texture Bindings", [])]

        use_toon         = getattr(mat_entry, 'use_toon', False)
        emi_zero         = _emissive_strength_is_zero(mat)
        emissive_slots   = {st for st in slot_types if _is_emissive_slot(st)}
        albedo_slots     = {st for st in slot_types if _is_albedo_slot(st, cls._channel_maps)}

        slot_mdf_paths = {}

        for slot_type in slot_types:
            # Emissive: skip composition if toon mode or strength is zero
            if slot_type in emissive_slots:
                if use_toon:
                    continue  # filled from albedo path after loop
                if emi_zero:
                    null = cls._null_tex_by_type.get(slot_type)
                    if null:
                        slot_mdf_paths[slot_type] = null
                    continue

            if slot_type not in cls._channel_maps:
                null = cls._null_tex_by_type.get(slot_type)
                if null:
                    slot_mdf_paths[slot_type] = null
                continue

            # --- skip_textures: just compute the binding path ---
            if getattr(mat_entry, 'skip_textures', False):
                slot_mdf_paths[slot_type] = make_mdf_path(
                    base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._use_art_prefix,
                )
                continue

            # --- cache key construction ---
            ch_map = cls._channel_maps[slot_type]
            needed_pt = {src[0] for src in ch_map.values()
                         if src is not None and isinstance(src, tuple)}
            key_parts = []
            cache_ok = True
            for pt in sorted(needed_pt):
                sv = strategies.get(pt)
                if sv:
                    sid = _make_source_id(sv)
                    if sid is not None:
                        key_parts.append((pt, sid))
                    else:
                        cache_ok = False
                        break
                else:
                    cache_ok = False
                    break

            cache_key = None
            if cache_ok:
                ch_ov = frozenset((k, v) for k, v in pbr_channels.items() if k in needed_pt)
                cache_key = (slot_type, tuple(key_parts), ch_ov)
                cached = comp_cache.get(cache_key)
                if cached is not None:
                    slot_mdf_paths[slot_type] = cached[2]
                    continue

                # Only attempt downgrade for cacheable slots (no BAKE involved)
                rgba = _try_downgrade_slot(slot_type, strategies, pbr_channels, cls._channel_maps)
                if rgba is not None:
                    hint = f"{tex_name}_{slot_type.lower()}_dg"
                    composed = _generate_solid_texture_path(rgba, temp_dir, hint, size=256)
                    if composed:
                        dds_fmt = ('BC7_UNORM_SRGB' if slot_type in SRGB_SLOT_TYPES
                                   else 'BC7_UNORM')
                        disk_path = make_disk_path(
                            natives_root, base_path, tex_name, slot_type,
                            cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                        )
                        os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                        dds_stem = os.path.splitext(os.path.basename(composed))[0]
                        dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                        _t_dds = time.time()
                        ImageListToDDS([(composed, dds_fmt)], temp_dir,
                                       mat_entry.generate_mipmaps)
                        # print(f"[{cls._log_tag}]   PNG→DDS {slot_type} (优化): {time.time() - _t_dds:.2f}s", flush=True)
                        if not os.path.isfile(dds_path):
                            raise FileNotFoundError(
                                f"texconv output not found: {dds_path}")
                        _t_tex = time.time()
                        DDSToTex([dds_path], cls._tex_version, disk_path)
                        # print(f"[{cls._log_tag}]   DDS→TEX {slot_type} (优化): {time.time() - _t_tex:.2f}s", flush=True)

                        mdf_path = make_mdf_path(
                            base_path, tex_name, slot_type,
                            cls._abbrev_map, cls._use_art_prefix,
                        )
                        slot_mdf_paths[slot_type] = mdf_path
                        comp_cache[cache_key] = (composed, disk_path, mdf_path)
                        continue

            # --- full composition path ---
            _t_comp = time.time()
            normal_flip_g = getattr(settings, 'flip_normal_g', False)
            composed = _compose_channels(
                slot_type, pbr_paths, pbr_channels, temp_dir, tex_name,
                channel_maps=cls._channel_maps,
                normal_flip_g=normal_flip_g,
            )
            # print(f"[{cls._log_tag}]   合成通道 {slot_type}: {time.time() - _t_comp:.2f}s", flush=True)
            if composed:
                dds_fmt   = ('BC7_UNORM_SRGB' if slot_type in SRGB_SLOT_TYPES
                             else 'BC7_UNORM')
                disk_path = make_disk_path(
                    natives_root, base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                )
                os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                dds_stem = os.path.splitext(os.path.basename(composed))[0]
                dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                _t_dds = time.time()
                ImageListToDDS([(composed, dds_fmt)], temp_dir,
                               mat_entry.generate_mipmaps)
                # print(f"[{cls._log_tag}]   PNG→DDS {slot_type}: {time.time() - _t_dds:.2f}s", flush=True)
                if not os.path.isfile(dds_path):
                    raise FileNotFoundError(
                        f"texconv output not found: {dds_path}")
                _t_tex = time.time()
                DDSToTex([dds_path], cls._tex_version, disk_path)
                # print(f"[{cls._log_tag}]   DDS→TEX {slot_type}: {time.time() - _t_tex:.2f}s", flush=True)

                mdf_path = make_mdf_path(
                    base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._use_art_prefix,
                )
                slot_mdf_paths[slot_type] = mdf_path

                if cache_key is not None:
                    comp_cache[cache_key] = (composed, disk_path, mdf_path)
                print(f"[{cls._log_tag}]   {slot_type} -> {os.path.basename(disk_path)}")
            else:
                null = cls._null_tex_by_type.get(slot_type)
                if null:
                    slot_mdf_paths[slot_type] = null

        # Toon shading: copy albedo binding path to all emissive slots
        if use_toon and emissive_slots:
            albedo_path = next(
                (slot_mdf_paths[st] for st in albedo_slots if st in slot_mdf_paths),
                None,
            )
            for st in emissive_slots:
                if albedo_path:
                    slot_mdf_paths[st] = albedo_path
                else:
                    null = cls._null_tex_by_type.get(st)
                    if null:
                        slot_mdf_paths[st] = null

        # Create MDF2 material from preset and update texture binding paths
        _t = time.time()
        mat_obj = readPresetJSON(preset_path, mdf_col)
        # print(f"[{cls._log_tag}]   创建MDF2材质: {time.time() - _t:.2f}s", flush=True)
        if mat_obj is None:
            raise RuntimeError(f"readPresetJSON returned None for '{mat_name}'")

        mat_obj.re_mdf_material.materialName = tex_name
        for binding in mat_obj.re_mdf_material.textureBindingList_items:
            if binding.textureType in slot_mdf_paths:
                binding.path = slot_mdf_paths[binding.textureType]
