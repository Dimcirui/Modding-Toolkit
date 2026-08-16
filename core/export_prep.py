"""Pre-export mesh preparation shared by the RE-series batch exporters.

Face triangulation
------------------
RE Mesh Editor's exporter mangles face-mesh shading; triangulating the mesh
first (Ctrl+T) avoids it.  The exporter reads evaluated geometry —

    cloneObj.data = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))

— so a Triangulate *modifier* is enough: the export sees triangles while the
mesh data itself is never touched, and there is no second layer of temporary
objects on top of the clone the exporter already makes.

Two modifier defaults are wrong for this and must be overridden.  Measured
against `bpy.ops.mesh.quads_convert_to_tris` (Ctrl+T) on a 7280-quad face mesh:

    default (SHORTEST_DIAGONAL)          different triangulation
    BEAUTY, keep_custom_normals=False    same triangles, normals p99 120 deg off
    BEAUTY, keep_custom_normals=True     same triangles, normals p99 0.04 deg

`keep_custom_normals` matters because these meshes carry authored split
normals — see core/normal_utils.py.
"""

import json
import os
from contextlib import contextmanager

#: Triangulation only helps the face; everything else is left alone.  Which
#: meshes count as "the face" is decided by the presence of a vertex group
#: named after the game's head bone, because the head geometry can live in any
#: object with any name.
#: Keyed by the lowercase *section* key, not by ``game_code``.  MH Rise's preset
#: file is still called ``mhwr.json`` for compatibility with existing user presets
#: even though its ``game_code`` is ``MHRS`` -- the filename is not a game code and
#: nothing derives one from it.
_GAME_BONE_PRESET = {
    'mhws': 'mhws.json',
    'mhrs': 'mhwr.json',
    're4':  're4.json',
    're9':  're9.json',
}

_MODIFIER_NAME = "MTK_ExportTriangulate"


def head_bone_names(game):
    """Head bone names for *game*, read from its bone preset rather than
    hard-coded, so editing the preset keeps this in step."""
    filename = _GAME_BONE_PRESET.get(game)
    if not filename:
        return set()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "assets", "presets", "bone", filename)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    entry = (data.get("mappings") or {}).get("head") or {}
    return set(entry.get("main") or []) | set(entry.get("aux") or [])


def find_head_meshes(objects, game):
    """Mesh objects among *objects* that are weighted to the game's head bone."""
    names = head_bone_names(game)
    if not names:
        return []
    return [o for o in objects
            if o.type == 'MESH' and any(vg.name in names for vg in o.vertex_groups)]


@contextmanager
def triangulated_for_export(objects, game):
    """Temporarily triangulate the head meshes among *objects*.

    Yields the list of objects that got a modifier.  The modifiers are removed
    on the way out even if the export raises, and objects that already carry a
    Triangulate modifier are left alone.
    """
    touched = []
    try:
        for obj in find_head_meshes(objects, game):
            if any(m.type == 'TRIANGULATE' for m in obj.modifiers):
                continue
            mod = obj.modifiers.new(_MODIFIER_NAME, 'TRIANGULATE')
            # Matches Ctrl+T; see the module docstring for the measurements
            mod.quad_method = 'BEAUTY'
            mod.ngon_method = 'BEAUTY'
            mod.keep_custom_normals = True
            mod.min_vertices = 4
            touched.append(obj)
        yield touched
    finally:
        for obj in touched:
            mod = obj.modifiers.get(_MODIFIER_NAME)
            if mod:
                obj.modifiers.remove(mod)
