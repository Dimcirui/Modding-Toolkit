# Blender regression checks

Run from the repository root on Windows with Pillow available in Blender's
Python environment. NumPy is bundled with Blender; texconv uses the add-on's
bundled DLL.

```text
blender --background --factory-startup --python-exit-code 1 --python tests/blender_regressions.py -- --work-dir <temporary-output-directory>
```

The checks generate their own PNG/TGA fixtures, compare encoded DDS pixels using
Pillow, and verify both tagged and untagged inputs, sRGB and linear formats,
alpha and mip counts. They also exercise temporary Onimusha face triangulation
for normal and simplified bindings, including cleanup after an export failure
and preservation of existing modifiers and unbound meshes.

The weapon check runs the shared export loop with placeholder binary writers.
It verifies the four blade/sheath paths and that weapon schemes bypass the
character SKS path. It does not validate real mesh/MDF serialization or in-game
behavior. Generated files and a JSON report go only into `--work-dir`.
