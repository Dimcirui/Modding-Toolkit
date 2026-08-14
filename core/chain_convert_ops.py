"""Operator for the cross-game chain port, one entry per REE game section.

The section supplies ``source_game``, so the direction is fixed by where the user
clicked and only the target has to be chosen.  That introduces one failure mode the
panel-less version did not have -- clicking it in the MHWS section while a RE4R chain
collection is selected -- so the source game is verified against the collection's own
armature and a mismatch is refused rather than silently converted the wrong way.

All the work lives in ``core.chain_convert`` and ``core.bone_mapper``; this file is
only the dialog.
"""

import json
import os

import bpy

from .bone_mapper import BoneMapManager, auto_detect_preset, build_cross_game_map
from .chain_convert import (duplicate_chain_collection, iter_collider_bindings,
                            remap_collider_attachments)
from .i18n import T

#: Games this is offered for, keyed by the ``game_code`` in the bone preset -- which
#: is **not** always the section key: MH Rise's section is ``mhrs`` but its preset
#: says ``MHR``.  Keying off the preset is what makes ``_preset_by_game()`` resolve.
#:
#: Deliberately three, not five:
#: * **MHWI** is not RE Engine at all -- its physics goes through mhw_ctc, and its
#:   chain code is off-limits per the refactor backlog.
#: * **MHRS** is RE Engine, but its rig is positioned from the character centre like
#:   MHWI rather than from the sole of the foot, so a port needs work nobody has done
#:   or measured yet.  Shelved rather than offered untested.
#: * **SF6 / DMC5** have no reference skeleton to validate against.
#:
#: The mapping layer already handles all of them (`build_cross_game_map` composes any
#: pair); this list is only about which ones have been *validated end to end*.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9")

#: EnumProperty item callbacks must keep a persistent reference to what they return.
#: Blender's C side holds the strings, and a list built inside the callback is freed
#: the moment Python drops it, leaving dangling pointers -- the same trap documented
#: in core/ref_skeleton.py.
_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _preset_by_game():
    """``{game_code: (filename, display_name)}`` from assets/presets/bone/*.json."""
    out = {}
    mgr = BoneMapManager()
    root = os.path.dirname(mgr.get_preset_path("x.json"))
    if not os.path.isdir(root):
        return out
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(root, fname), "r", encoding="utf-8") as f:
                info = json.load(f).get("preset_info", {})
        except Exception:
            continue
        code = info.get("game_code")
        # first preset wins: several files can share a game_code (mhwi_world and
        # mhwi_world_legacy), and the alternates are not what we want here
        if code and code not in out:
            out[code] = (fname, info.get("name") or code)
    return out


def _chain_collections():
    """Collections holding an imported chain -- identified by their header object."""
    return [c for c in bpy.data.collections
            if any(o.get("TYPE") == "RE_CHAIN_HEADER" for o in c.all_objects)]


def _collection_items(self, context):
    items = [(c.name, c.name, "", 'OUTLINER_COLLECTION', i)
             for i, c in enumerate(_chain_collections())]
    if not items:
        items = [("NONE", T("core.chain_convert_ops.no_chain_collection"), "", 'ERROR', 0)]
    return _cached("collection", items)


def _target_game_items(self, context):
    presets = _preset_by_game()
    items = []
    for code in PORTABLE_GAMES:
        if code == self.source_game or code not in presets:
            continue
        items.append((code, presets[code][1], "", len(items)))
    if not items:
        items = [("NONE", "-", "", 0)]
    return _cached("target_game", items)


def _armature_items(self, context):
    items = [(o.name, f"{o.name}  ({len(o.data.bones)})", "", 'ARMATURE_DATA', i)
             for i, o in enumerate(o for o in bpy.data.objects if o.type == 'ARMATURE')]
    if not items:
        items = [("NONE", "-", "", 'ERROR', 0)]
    return _cached("armature", items)


def _collection_armature(collection):
    """The armature a collection's colliders are bound to, or None.

    Read from the constraints rather than guessed, since a scene can hold several
    rigs and the collection itself records no owner.
    """
    for _obj, con in iter_collider_bindings(collection):
        if getattr(con, "target", None) is not None and con.target.type == 'ARMATURE':
            return con.target
    return None


class MODDER_OT_ConvertChainCrossGame(bpy.types.Operator):
    bl_idname = "modder.convert_chain_cross_game"
    bl_label = "Port Chain to Another Game"
    bl_options = {'REGISTER', 'UNDO'}

    source_game: bpy.props.StringProperty(options={'HIDDEN'})
    source_collection: bpy.props.EnumProperty(
        name="Chain Collection", items=_collection_items)
    target_game: bpy.props.EnumProperty(name="Target Game", items=_target_game_items)
    target_armature: bpy.props.EnumProperty(
        name="Target Armature", items=_armature_items)
    replace_original: bpy.props.BoolProperty(
        name="Replace the Original", default=False,
        description="Convert the original in place instead of converting a copy")

    @classmethod
    def description(cls, context, properties):
        return T("core.chain_convert_ops.desc")

    @classmethod
    def poll(cls, context):
        return bool(_chain_collections())

    def invoke(self, context, event):
        self._lines = []
        self._blocked = True
        return context.window_manager.invoke_props_dialog(self, width=460)

    def check(self, context):
        """Re-run the preflight whenever a field changes, and redraw.

        A dry run over a few dozen colliders is cheap, so the report can just track
        the fields instead of hiding behind a separate button.
        """
        self._preflight()
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.chain_convert_ops.source_collection"))
        layout.prop(self, "target_game", text=T("core.chain_convert_ops.target_game"))
        layout.prop(self, "target_armature",
                    text=T("core.chain_convert_ops.target_armature"))
        layout.prop(self, "replace_original",
                    text=T("core.port.replace_original"))

        if not getattr(self, "_lines", None):
            self._preflight()

        box = layout.box()
        for icon, text in self._lines:
            box.label(text=text, icon=icon)

    # ── preflight ────────────────────────────────────────────────────────────

    def _resolve(self):
        """``(collection, armature, cross_map, error_line)``; any may be None."""
        presets = _preset_by_game()
        col = bpy.data.collections.get(self.source_collection)
        arm = bpy.data.objects.get(self.target_armature)
        if col is None or arm is None or arm.type != 'ARMATURE':
            return None, None, None, ('INFO', T("core.chain_convert_ops.pick_target"))

        # The section fixed the source game, so make sure the collection agrees --
        # otherwise clicking this in the wrong section converts the wrong direction.
        src_arm = _collection_armature(col)
        if src_arm is not None:
            detected = auto_detect_preset(src_arm, False)
            code = None
            if detected:
                mgr = BoneMapManager()
                if mgr.load_preset(detected):
                    code = mgr.preset_info.get("game_code")
            if code and self.source_game and code != self.source_game:
                return None, None, None, ('ERROR', T(
                    "core.chain_convert_ops.wrong_source_game").format(
                        found=code, expected=self.source_game))

        src = presets.get(self.source_game)
        dst = presets.get(self.target_game)
        if not src or not dst:
            return None, None, None, ('ERROR', T("core.chain_convert_ops.pick_target"))
        return col, arm, build_cross_game_map(src[0], dst[0]), None

    def _preflight(self):
        self._lines = []
        self._blocked = True
        col, arm, cross_map, err = self._resolve()
        if err is not None:
            self._lines = [err]
            return
        if cross_map is None:
            self._lines = [('ERROR', T("core.chain_convert_ops.pick_target"))]
            return

        rep = remap_collider_attachments(col, cross_map, target_armature=arm,
                                         dry_run=True)
        self._report = rep
        total = len(rep.remapped) + rep.unchanged
        self._lines.append(('INFO', T("core.chain_convert_ops.stat_bindings").format(
            total=total, remapped=len(rep.remapped), kept=rep.unchanged)))

        if rep.unmapped:
            names = sorted({b for _o, b in rep.unmapped})
            self._lines.append(('ERROR', T("core.chain_convert_ops.unmapped").format(
                n=len(names), names=", ".join(names[:4]))))
        if rep.missing_in_target:
            names = sorted({b for _o, b in rep.missing_in_target})
            self._lines.append(('ERROR', T("core.chain_convert_ops.missing").format(
                n=len(names), names=", ".join(names[:4]))))
        if rep.ok:
            self._lines.append(('CHECKMARK', T("core.chain_convert_ops.all_resolved")))
        if rep.collapsed:
            tgt, srcs = sorted(rep.collapsed.items())[0]
            self._lines.append(('ERROR', T("core.chain_convert_ops.merged").format(
                n=len(rep.collapsed), example=f"{tgt} <- {', '.join(srcs)}")))
        self._blocked = not rep.ok

    # ── execute ──────────────────────────────────────────────────────────────

    def execute(self, context):
        self._preflight()
        if self._blocked:
            self.report({'ERROR'}, T("core.chain_convert_ops.blocked"))
            return {'CANCELLED'}

        col, arm, cross_map, err = self._resolve()
        if err is not None or cross_map is None:
            self.report({'ERROR'}, err[1] if err else T("core.chain_convert_ops.blocked"))
            return {'CANCELLED'}

        if not self.replace_original:
            col, _mapping = duplicate_chain_collection(
                col, f"{col.name}_{self.target_game}")

        rep = remap_collider_attachments(col, cross_map, target_armature=arm)
        self.report({'INFO'}, T("core.chain_convert_ops.done").format(
            game=self.target_game, remapped=len(rep.remapped), kept=rep.unchanged))
        return {'FINISHED'}


classes = [MODDER_OT_ConvertChainCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
