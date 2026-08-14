"""RE Mdf port, operator: run mdf_port.plan_material on real selected materials.

Mirrors two existing patterns rather than inventing a third:

- ``core/mesh_port_ops.py``'s ``modder.port_mesh_cross_game`` -- one game-agnostic
  operator, ``source_game`` fixed by which per-game UI section calls it,
  ``target_game`` picked in the dialog, and the result lands in a *new* collection
  next to the original rather than mutating it in place.
- ``core/mdf_material_convert_base.py``'s same-game convert -- read the old
  material's bindings, build the new one from a preset, copy the custom textures
  across.  The cross-game difference is everything downstream of "which bindings
  copy": the target's slot vocabulary and channel packing can differ (see
  ``core/mdf_port_tex.py``), so a straight ``old_path`` copy is not enough here.

Params are not migrated, unlike the same-game convert's ``ALL_TEX_PARAMS`` mode --
the shader's Property List is itself game-specific, not just a same-shape table
with different defaults.
"""

import os
import tempfile
import shutil

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .i18n import T
from . import mdf_port
from . import mdf_port_tex
from .mdf_material_convert_base import _load_vanilla_art_paths, is_custom_tex_path
from .mdf_tex_processor_base import mdf_collection_poll, _import_tex_utils
from .mdf_generator_base import (
    import_read_preset_json, PLACEHOLDER_SLOT_TYPES, _resolve_placeholder_slot)

_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _target_game_items(self, context):
    items = [(g, g, "") for g in mdf_port.PORTABLE_GAMES if g != self.source_game]
    if not items:
        items = [("NONE", "-", "")]
    return _cached("mdf_port_target_game", items)


def _new_port_collection(src_col, suffix):
    """A fresh, empty .mdf2 collection beside *src_col* -- same naming/linking
    convention as mesh_port_ops.duplicate_mesh_collection, minus the armature
    duplication that has no equivalent here."""
    stem = src_col.name[:-5] if src_col.name.endswith(".mdf2") else src_col.name
    new_col = bpy.data.collections.new(f"{stem}_{suffix}.mdf2")
    if src_col.get("~TYPE") is not None:
        new_col["~TYPE"] = src_col["~TYPE"]
    new_col.color_tag = src_col.color_tag

    parents = [c for c in bpy.data.collections if src_col.name in c.children]
    if not parents:
        parents = [bpy.context.scene.collection]
    for parent in parents:
        parent.children.link(new_col)
    return new_col


class MODDER_OT_PortMdfMaterialCrossGame(bpy.types.Operator):
    bl_idname = "modder.port_mdf_material_cross_game"
    bl_label = "Port MDF Material to Another Game"
    #: Same reasoning as modder.port_mesh_cross_game: not idempotent (a second
    #: click ports the new collection's own materials) and writes .tex files to
    #: disk, which undo cannot take back either.
    bl_options = {'REGISTER'}

    source_game: StringProperty(options={'HIDDEN'})
    target_game: EnumProperty(name="Target Game", items=_target_game_items)
    dest_base_path: StringProperty(
        name="Destination Base Path",
        description="Path under the target game's own natives/STM convention, e.g. Author/Name",
        default="",
    )
    delete_original: BoolProperty(name="Delete Original Material", default=False)

    @classmethod
    def description(cls, context, properties):
        return T("core.mdf_port_ops.desc")

    @classmethod
    def poll(cls, context):
        return any(o.get("~TYPE") == "RE_MDF_MATERIAL" for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "target_game", text=T("core.mdf_port_ops.target_game_label"))
        col.prop(self, "dest_base_path", text=T("core.mdf_port_ops.dest_base_path_label"))
        col.prop(self, "delete_original", text=T("core.mdf_port_ops.delete_original_label"))

    def execute(self, context):
        src_game = self.source_game
        dst_game = self.target_game
        if not dst_game or dst_game == 'NONE':
            self.report({'ERROR'}, T("core.mdf_port_ops.no_target_selected"))
            return {'CANCELLED'}

        src_cfg = mdf_port_tex.get_game_tex_config(src_game)
        dst_cfg = mdf_port_tex.get_game_tex_config(dst_game)
        if src_cfg is None or dst_cfg is None:
            self.report({'ERROR'}, T("core.mdf_port_ops.missing_tex_config"))
            return {'CANCELLED'}

        targets = [o for o in list(context.selected_objects)
                   if o.get("~TYPE") == "RE_MDF_MATERIAL" and getattr(o, 're_mdf_material', None)]
        if not targets:
            self.report({'WARNING'}, T("core.mdf_port_ops.no_targets"))
            return {'CANCELLED'}

        readPresetJSON = import_read_preset_json()
        if readPresetJSON is None:
            self.report({'ERROR'}, T("core.mdf_port_ops.cannot_load_preset_tool"))
            return {'CANCELLED'}

        vanilla_set = _load_vanilla_art_paths(src_cfg.get("vanilla_asset_rel", ""))
        src_natives_root = context.scene.get(src_cfg["natives_root_key"], "")
        dst_natives_root = context.scene.get(dst_cfg["natives_root_key"], "")
        dst_base_path = self.dest_base_path.strip()

        temp_dir = tempfile.mkdtemp(prefix="mdf_port_")
        new_cols = {}  # source .mdf2 collection name -> its new counterpart
        placeholder_cache = {}  # shared across the whole batch, see _resolve_placeholder_slot

        converted = failed = unsupported = 0
        tex_ported = tex_skipped_vanilla = tex_skipped_no_slot = tex_skipped_no_source = 0
        tex_pending_write = tex_placeholder = 0

        try:
            for obj in targets:
                try:
                    old_data = obj.re_mdf_material
                    old_name = old_data.materialName
                    old_mmtr = old_data.mmtrPath
                    old_bindings = {b.textureType: b.path for b in old_data.textureBindingList_items}

                    mdf_col = next((c for c in obj.users_collection if mdf_collection_poll(None, c)), None)
                    if mdf_col is None:
                        print(f"[MDF Port] {old_name}: no parent .mdf2 collection found, skipped")
                        failed += 1
                        continue

                    new_col = new_cols.get(mdf_col.name)
                    if new_col is None:
                        new_col = _new_port_collection(mdf_col, dst_game)
                        new_cols[mdf_col.name] = new_col

                    plan = mdf_port.plan_material(src_game, dst_game, old_mmtr)
                    if plan["unsupported"]:
                        unsupported += 1
                        print(f"[MDF Port] {old_name}: unsupported material shader "
                              f"'{old_mmtr}', falling back to {plan['target']}")
                    elif not plan["exact"]:
                        print(f"[MDF Port] {old_name}: no exact {dst_game} counterpart "
                              f"for archetype '{plan['archetype']}', using '{plan['target']}'")

                    new_obj = readPresetJSON(plan["path"], new_col)
                    if not new_obj:
                        print(f"[MDF Port] {old_name}: readPresetJSON failed for '{plan['path']}'")
                        failed += 1
                        continue

                    new_data = new_obj.re_mdf_material
                    new_data.materialName = old_name
                    dst_binding_types = {b.textureType: b for b in new_data.textureBindingList_items}
                    tex_name = old_name.removesuffix('_UseSC')
                    handled_dst_slots = set()

                    for tex_type, old_path in old_bindings.items():
                        if not is_custom_tex_path(old_path, vanilla_set):
                            if old_path:
                                tex_skipped_vanilla += 1
                            continue

                        dst_slot_type = mdf_port_tex.find_dst_slot_type(tex_type, dst_binding_types)
                        if dst_slot_type is None:
                            tex_skipped_no_slot += 1
                            continue
                        dst_binding = dst_binding_types[dst_slot_type]

                        if not src_natives_root:
                            tex_skipped_no_source += 1
                            continue
                        src_disk_path = mdf_port_tex.resolve_source_disk_path(
                            src_natives_root, old_path, src_cfg["tex_version"])
                        if not os.path.isfile(src_disk_path):
                            print(f"[MDF Port] {old_name}: source texture not found on disk: "
                                  f"{src_disk_path}")
                            tex_skipped_no_source += 1
                            continue

                        if not dst_base_path:
                            tex_pending_write += 1
                            continue

                        png_path = mdf_port_tex.repack_slot(
                            src_disk_path, tex_type, dst_slot_type, temp_dir, tex_name,
                            src_channel_maps=src_cfg["channel_maps"],
                            dst_channel_maps=dst_cfg["channel_maps"])
                        mdf_path, written = mdf_port_tex.write_ported_tex(
                            png_path, dst_slot_type, dst_cfg, tex_name,
                            dst_natives_root, dst_base_path, temp_dir)
                        dst_binding.path = mdf_path
                        handled_dst_slots.add(dst_slot_type)
                        if written:
                            tex_ported += 1
                        else:
                            tex_pending_write += 1

                    # PLACEHOLDER_SLOT_TYPES (SkinMap/BlendNormalMap so far) have no PBR
                    # recipe and no vanilla default at all (see mdf_generator_base.py's own
                    # comment on that set) -- for any such slot the port left untouched,
                    # write the bundled placeholder rather than shipping the prefab's own
                    # borrowed literal path (some other mod's asset it happened to be
                    # authored against).
                    if dst_base_path and dst_natives_root:
                        for slot_type in PLACEHOLDER_SLOT_TYPES:
                            if slot_type in handled_dst_slots or slot_type not in dst_binding_types:
                                continue
                            image_to_dds, dds_to_tex = _import_tex_utils()
                            mdf_path = _resolve_placeholder_slot(
                                slot_type, tex_name, dst_natives_root, dst_base_path, temp_dir,
                                dst_cfg["abbrev_map"], dst_cfg["tex_version"], dst_cfg["use_art_prefix"],
                                image_to_dds, dds_to_tex, placeholder_cache)
                            if mdf_path:
                                dst_binding_types[slot_type].path = mdf_path
                                tex_placeholder += 1

                    if self.delete_original:
                        bpy.data.objects.remove(obj, do_unlink=True)

                    converted += 1

                except Exception as e:
                    failed += 1
                    print(f"[MDF Port] convert failed for '{obj.name}': {e}")
                    import traceback
                    traceback.print_exc()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if failed:
            self.report({'WARNING'}, T("core.mdf_port_ops.done_with_fail").format(
                done=converted, failed=failed))
        else:
            self.report({'INFO'}, T("core.mdf_port_ops.done").format(
                done=converted, unsupported=unsupported, tex=tex_ported,
                placeholder=tex_placeholder, pending=tex_pending_write, vskip=tex_skipped_vanilla,
                noslot=tex_skipped_no_slot, nosrc=tex_skipped_no_source))
        return {'FINISHED'}


classes = [MODDER_OT_PortMdfMaterialCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
