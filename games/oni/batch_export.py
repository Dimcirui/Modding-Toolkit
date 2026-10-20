"""Onimusha scheme batch export -- the shared exporter in core/scheme_batch_export.py,
configured for ONI.

Schemes live in assets/export_schemes/oni/.  Their parts and file lists were read off
the game's own part prefabs (natives/stm/gamedesign/action/player/_prefab/partslist/
<semantic folder>/<part id>.pfb, plus OniBody/OniHead.pfb for the Oni form): each
prefab names the mesh / mdf2 / chain2 / clsp / gpuc it loads, and its ``_HQ`` twin
the ``_event_00.mdf2`` used in cutscenes -- which is why every part writes both mdf2.

Not registered with the pre-export check or the auto-fix: neither knows ONI yet, so
both are switched off here rather than run against another game's rules.
"""

from ...core.scheme_batch_export import SchemeExportSpec, SchemeExporter, build_classes

SPEC = SchemeExportSpec(
    code="ONI", op_prefix="oni", key_prefix="oni", title="Onimusha Batch Exporter",
    scheme_dir="oni", blank_dir="oni",
    natives_root_key="oni_natives_root",
    scheme_setting="oni_export_scheme", blank_setting="oni_use_blank_export",
    fbxskel_base="stm/art/model/character/ch0", native_skeleton_dir="oni",
    # mdf2 .51 is RE9's version too; RE Mesh Editor writes Onimusha's layout only
    # when its activeGame says so.
    mdf_active_game="ONIWOTS",
    check_game=None, autofix_game=None,
    # SKS's Onimusha parts are the player root's slot children (Adapter.lua
    # PARTS); Hair hangs under Head and is not one.  The sculpt preset's target
    # is metadata on ONI (its adapter has no additional_faces, so no actor
    # instances).  Should it get them, the cutscene copy's parts are named after
    # their mesh (ch001_.._event) and won't match "Head": drop the target then.
    sks_parts=("Head", "Body", "Cloak", "Gauntlet", "Amulet"),
)


class OnimushaExporter(SchemeExporter):
    """Share character export with optional face preparation and weapon schemes."""

    def draw_scheme_options(self, layout, scene, scheme):
        if scheme.get("resource_type") != "weapon":
            layout.prop(scene.mhw_suite_settings, "oni_triangulate_face")

    def _export_with_shapekeys(self, op, context, scene, settings, natives_root, scheme, scheme_file):
        if scheme.get("resource_type") == "weapon":
            # Weapon schemes do not use Musashi's character sculpt presets.
            return self._export(op, context, scene, settings, natives_root, scheme)
        if settings.oni_triangulate_face:
            from ...core.export_prep import triangulated_for_export
            collections = [mesh for _label, _mdf, mesh in
                           self.bound_pairs(scene, scheme, self.use_simplified(scene)) if mesh is not None]
            objects = {obj for collection in collections for obj in collection.all_objects}
            with triangulated_for_export(objects, 'oni'):
                return super()._export_with_shapekeys(
                    op, context, scene, settings, natives_root, scheme, scheme_file)
        return super()._export_with_shapekeys(
            op, context, scene, settings, natives_root, scheme, scheme_file)


EXPORTER = OnimushaExporter(SPEC)

get_schemes_callback = EXPORTER.schemes_callback

classes = build_classes(EXPORTER)


def register():
    import bpy
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    import bpy
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
