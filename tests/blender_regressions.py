"""Run with Blender --background --factory-startup --python-exit-code 1 --python
tests/blender_regressions.py -- --work-dir <temporary-output-directory>.

Uses generated images and placeholder resource writers; no game assets required.
The Windows texture checks use the add-on's bundled texconv DLL and require
Pillow in Blender's Python environment to inspect stored DDS values independently.
"""
import argparse
import importlib
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch
import zlib

import bpy
import numpy as np
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("--work-dir", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
output = args.work_dir.resolve()
output.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo.parent))
addon = importlib.import_module(repo.name)
assert Path(addon.__file__).resolve().parent == repo
assert bpy.ops.preferences.addon_enable(module=repo.name) == {'FINISHED'}
native = importlib.import_module(repo.name + ".core.texconv_native")
core = importlib.import_module(repo.name + ".core.scheme_batch_export")
batch = importlib.import_module(repo.name + ".games.oni.batch_export")
prep = importlib.import_module(repo.name + ".core.export_prep")


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_png(path, rgba, tagged):
    height, width = rgba.shape[:2]
    data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
    if tagged:
        data += png_chunk(b"sRGB", b"\x00") + png_chunk(b"gAMA", struct.pack(">I", 45455))
    rows = b"".join(b"\x00" + row.tobytes() for row in rgba)
    path.write_bytes(data + png_chunk(b"IDAT", zlib.compress(rows)) + png_chunk(b"IEND", b""))


x, y = np.meshgrid(np.arange(64), np.arange(64))
reference = np.stack((32 + x * 3, 24 + y * 3, 48 + (x + y), 32 + x * 3), axis=2).astype(np.uint8)
errors = {}
sources = []
for tagged in (False, True):
    source = output / ("tagged.png" if tagged else "untagged.png")
    write_png(source, reference, tagged)
    sources.append(source)
tga = importlib.import_module(repo.name + ".core.tga_file")
source = output / "staging.tga"
tga.write_tga_rgba8(str(source), reference[::-1].astype(np.float32) / 255)
sources.append(source)
for source in sources:
    for fmt in ("BC7_UNORM_SRGB", "R8G8B8A8_UNORM_SRGB", "R8G8B8A8_UNORM"):
        folder = output / source.stem / fmt
        folder.mkdir(parents=True, exist_ok=True)
        target = native.convert_to_dds(str(source), fmt, str(folder), generate_mips=True)
        raw = Path(target).read_bytes()
        assert struct.unpack_from("<I", raw, 28)[0] == 7
        expected_format = {"BC7_UNORM_SRGB": 99, "R8G8B8A8_UNORM_SRGB": 29, "R8G8B8A8_UNORM": 28}[fmt]
        if raw[84:88] == b'DX10':
            assert struct.unpack_from("<I", raw, 128)[0] == expected_format
        else:
            assert fmt == "R8G8B8A8_UNORM" and struct.unpack_from("<I", raw, 88)[0] == 32
        decoded = np.asarray(Image.open(target).convert("RGBA"))
        error = np.abs(decoded.astype(float) - reference).mean(axis=(0, 1))
        assert max(error) < (3 if fmt.startswith("BC7") else 1), (source, fmt, error)
        errors[source.stem + "/" + fmt] = error.tolist()

scene = bpy.context.scene
settings = scene.mhw_suite_settings
exp = batch.EXPORTER
assert not settings.oni_triangulate_face
assert prep.head_bone_names("oni")
scheme = exp.load_scheme("Musashi.json")
head_group = next(group for group in scheme["groups"] if group["name"].split()[-1] == "Head")
head_entry = head_group["entries"][0]
collection = bpy.data.collections.new("BoundFace")
scene.collection.children.link(collection)


def make_head(name, target_collection):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(name, mesh)
    target_collection.objects.link(obj)
    obj.vertex_groups.new(name=sorted(prep.head_bone_names("oni"))[0])
    return obj


face = make_head("Face", collection)
existing = make_head("ExistingTriangulate", collection)
existing.modifiers.new("UserTriangulate", 'TRIANGULATE')
unrelated = make_head("UnboundHead", scene.collection)
exp.set_binding(scene, scheme["character_id"], head_entry["id"], "mesh", collection.name)
settings.oni_triangulate_face = True


def inspect_preparation(*unused):
    assert len(face.modifiers) == 1 and face.modifiers[0].type == 'TRIANGULATE'
    assert len(existing.modifiers) == 1
    assert len(unrelated.modifiers) == 0
    raise RuntimeError("Expected export failure")


for simplified in (False, True):
    scene["oni_use_simplified"] = simplified
    exp.set_group_binding(scene, scheme["character_id"], head_group["name"], "mesh", collection.name)
    with patch.object(core.SchemeExporter, "_export_with_shapekeys", inspect_preparation):
        try:
            exp._export_with_shapekeys(None, bpy.context, scene, settings, str(output), scheme, "Musashi.json")
        except RuntimeError as error:
            assert str(error) == "Expected export failure"
        else:
            raise AssertionError("Expected export failure")
    assert len(face.modifiers) == 0
    assert len(existing.modifiers) == 1

scene["oni_use_simplified"] = False
weapon = exp.load_scheme("it000_0170_Weapon.json")
for group in weapon["groups"]:
    for entry in group["entries"]:
        for suffix in ("mesh", "mdf2"):
            exp.set_binding(scene, weapon["character_id"], entry["id"], suffix, collection.name)


def placeholder(kind):
    def write(filepath, _target):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(kind.encode())
    write.__name__ = "placeholder_" + kind
    return write


class Reporter:
    def report(self, _level, message):
        print(message)


weapon_output = output / "weapon"
with patch.object(core.SchemeExporter, "_export_with_shapekeys", side_effect=AssertionError("Weapon entered character SKS")), \
        patch.object(core, "do_export_mesh", placeholder("mesh")), \
        patch.object(core, "do_export_mdf2", placeholder("mdf2")):
    result = exp._export_with_shapekeys(Reporter(), bpy.context, scene, settings, str(weapon_output), weapon, "it000_0170_Weapon.json")
assert result == {'FINISHED'}
files = sorted(path for path in weapon_output.rglob("*") if path.is_file())
assert len(files) == 4
assert {path.name for path in files} == {
    "it000_0170_00.mesh.260209350", "it000_0170_10.mesh.260209350",
    "it000_0170_00_A.mdf2.51", "it000_0170_10_A.mdf2.51"}
assert all("item/it0/it000_0170" in path.as_posix() for path in files)
report = {"texture_mae_rgba": errors, "temporary_triangulation_cleanup": "passed",
          "normal_and_simplified_bindings": "passed", "unbound_mesh_untouched": "passed",
          "weapon_routing_with_placeholder_writers": "passed", "game_validation": "not_performed"}
(output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("UPSTREAM_REGRESSIONS_PASSED")
