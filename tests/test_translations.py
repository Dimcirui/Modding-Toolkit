# tests/test_translations.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Stub out bpy so we can import without Blender
import types
bpy_stub = types.ModuleType("bpy")
bpy_stub.app = types.SimpleNamespace(translations=None)
sys.modules["bpy"] = bpy_stub
sys.modules["bpy.props"] = types.ModuleType("bpy.props")
sys.modules["bpy.types"] = types.ModuleType("bpy.types")

from translations import TRANSLATIONS

def test_has_en_US():
    assert "en_US" in TRANSLATIONS

def test_no_empty_keys():
    for (ctx, key), val in TRANSLATIONS["en_US"].items():
        assert key, f"Empty key found in context '{ctx}'"

def test_no_empty_values():
    for (ctx, key), val in TRANSLATIONS["en_US"].items():
        assert val, f"Empty translation for key '{key}'"

def test_no_duplicate_keys():
    keys = list(TRANSLATIONS["en_US"].keys())
    assert len(keys) == len(set(keys)), "Duplicate keys in translation dict"

if __name__ == "__main__":
    test_has_en_US()
    test_no_empty_keys()
    test_no_empty_values()
    test_no_duplicate_keys()
    print("All translation dict tests passed.")
