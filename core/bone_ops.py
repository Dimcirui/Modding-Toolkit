"""Bone and skeleton operators.

Moved out of ui/main_panel.py unchanged -- same bl_idnames, same properties,
same code. They were only defined there because that is the panel that draws
them; the algorithms they call have always lived in core/bone_utils.py and
core/bone_mapper.py, so the operators belong on this side of the ui/core line
too. Nothing about their behaviour changed in the move.

MHW_OT_GeneralTools is still one operator dispatching nine actions through an
`action` enum. That is worth splitting -- it costs per-action poll(), a
distinct Redo-panel label, and a tooltip that has to be routed through
description() -- but splitting changes operator idnames, so it is a separate
decision from this move.
"""

import bpy
import os
import re

from .i18n import T
from . import bone_utils, weight_utils


# (action_id, label_key, description_key) — single source of truth for the
# "action" EnumProperty items= callback below AND MHW_OT_GeneralTools's
# per-action dynamic classmethod description() (they describe the same
# thing: what a given action does).
_GENERAL_TOOLS_ACTIONS = [
    ('ROLL_ZERO',        "ui.main_panel.gt_action_roll_zero",        "ui.main_panel.gt_desc_roll_zero"),
    ('ADD_TAIL',         "ui.main_panel.gt_action_add_tail",         "ui.main_panel.gt_desc_add_tail"),
    ('MIRROR_X',         "ui.main_panel.gt_action_mirror_x",         "ui.main_panel.gt_desc_mirror_x"),
    ('SIMPLIFY_CHAIN',   "ui.main_panel.gt_action_simplify_chain",   "ui.main_panel.gt_desc_simplify_chain"),
    ('MERGE_TO_ACTIVE',  "ui.main_panel.gt_action_merge_to_active",  "ui.main_panel.gt_desc_merge_to_active"),
    ('ALIGN_POS',        "ui.main_panel.gt_action_align_pos",        "ui.main_panel.gt_desc_align_pos"),
    ('ALIGN_POS_ROLL',   "ui.main_panel.gt_action_align_pos_roll",   "ui.main_panel.gt_desc_align_pos_roll"),
    ('ALIGN_FULL',       "ui.main_panel.gt_action_align_full",       "ui.main_panel.gt_desc_align_full"),
    ('MERGE_CHAINS',     "ui.main_panel.gt_action_merge_chains",     "ui.main_panel.gt_desc_merge_chains"),
]
def _general_tools_action_items(self, context):
    return [(action_id, T(label_key), T(desc_key)) for action_id, label_key, desc_key in _GENERAL_TOOLS_ACTIONS]
class MHW_OT_GeneralTools(bpy.types.Operator):
    """General bone tools; see the Redo panel / button tooltip for the selected action's description"""
    bl_idname = "mhw.general_tools"
    bl_label = "General Tools"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=_general_tools_action_items,
    )

    _ACTION_DESCRIPTIONS = {action_id: desc_key for action_id, _label_key, desc_key in _GENERAL_TOOLS_ACTIONS}

    @classmethod
    def description(cls, context, properties):
        key = cls._ACTION_DESCRIPTIONS.get(properties.action)
        return T(key) if key else (cls.__doc__ or "")

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("ui.main_panel.gt_err_select_armature"))
            return {'CANCELLED'}

        if self.action == 'ROLL_ZERO':
            bpy.ops.object.mode_set(mode='EDIT')
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, T("ui.main_panel.gt_warn_select_bone_edit"))
                return {'CANCELLED'}
            count = bone_utils.set_roll_to_zero_recursive(selected_bones)
            self.report({'INFO'}, T("ui.main_panel.gt_info_roll_reset").format(n=count))

        elif self.action == 'ADD_TAIL':
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, T("ui.main_panel.gt_warn_select_tail_bone"))
                return {'CANCELLED'}
            count = bone_utils.add_vertical_tail_bone(edit_bones, selected_bones)
            self.report({'INFO'}, T("ui.main_panel.gt_info_tail_added").format(n=count))

        elif self.action == 'MIRROR_X':
            selected_names = []
            if context.mode == 'POSE':
                selected_names = [b.name for b in context.selected_pose_bones]
            elif context.mode == 'EDIT':
                selected_names = [b.name for b in context.selected_editable_bones]
            else:
                selected_names = [b.name for b in arm_obj.data.bones if b.select]

            if len(selected_names) != 2:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_mirror_need_two"))
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            result = bone_utils.mirror_bone_transform(edit_bones, selected_names)
            success = result[0]
            msg_template = result[1]
            msg_args = result[2:] if len(result) > 2 else ()
            # NOTE: bone_utils.mirror_bone_transform() (out of this migration's
            # scope) returns fixed Chinese message templates; they're bridged
            # into T() via literal-text keys in core/i18n_strings/ui.py.
            translated = T(msg_template) % msg_args if msg_args else T(msg_template)
            if success:
                self.report({'INFO'}, translated)
            else:
                self.report({'ERROR'}, translated)

        elif self.action == 'SIMPLIFY_CHAIN':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            selected_bones = list(context.selected_editable_bones)
            if len(selected_bones) < 2:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_need_two_bones"))
                return {'CANCELLED'}

            selected_names = [b.name for b in selected_bones]

            # Gather bound meshes (used for tail-bone detection)
            mesh_objects = [o for o in bpy.data.objects
                            if o.type == 'MESH' and
                            any(m.type == 'ARMATURE' and m.object == arm_obj
                                for m in o.modifiers)]

            # Group into chains
            chains = weight_utils.build_bone_chains(selected_names, arm_obj)

            # Pair up bones per chain; a weightless tail bone at the chain end is skipped
            pairs = []
            for chain in chains:
                if len(chain) < 2:
                    continue
                effective = list(chain)
                # Detect tail bone: exclude it from pairing (kept but not deleted) if it has no vertex weights
                if not weight_utils.bone_has_weights(effective[-1], mesh_objects):
                    effective = effective[:-1]
                for i in range(0, len(effective) - 1, 2):
                    pairs.append((effective[i], effective[i + 1]))

            if not pairs:
                self.report({'WARNING'}, T("ui.main_panel.gt_warn_no_pairs"))
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, T("ui.main_panel.gt_info_chain_simplified").format(n=len(pairs)))

        elif self.action == 'MERGE_TO_ACTIVE':
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            active = context.active_bone
            if not active:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_need_active_bone"))
                return {'CANCELLED'}

            others = [b for b in context.selected_editable_bones if b.name != active.name]
            if not others:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_need_two_for_merge"))
                return {'CANCELLED'}

            active_name = active.name
            pairs = [(active_name, b.name) for b in others]
            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, T("ui.main_panel.gt_info_merged_into").format(n=len(pairs), name=active_name))

        elif self.action == 'MERGE_CHAINS':
            # Get the active bone name and selected bone names (EDIT and POSE mode both supported)
            if context.mode == 'EDIT':
                active = context.active_bone
                selected_names = [b.name for b in context.selected_editable_bones]
            elif context.mode == 'POSE':
                active = context.active_pose_bone
                selected_names = [b.name for b in context.selected_pose_bones]
            else:
                bpy.ops.object.mode_set(mode='EDIT')
                active = context.active_bone
                selected_names = [b.name for b in context.selected_editable_bones]

            if not active:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_need_active_bone"))
                return {'CANCELLED'}

            active_name = active.name
            selected_set = set(selected_names)

            # Filter out non-active candidate chain heads: skip bones whose ancestor is also selected
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

            edit_bones = arm_obj.data.edit_bones
            candidate_heads = []
            for name in selected_names:
                if name == active_name:
                    continue
                bone = edit_bones.get(name)
                if bone is None:
                    continue
                # Walk up the parent chain; skip if a parent is in the selected set (not a chain head)
                is_descendant = False
                parent = bone.parent
                while parent:
                    if parent.name in selected_set:
                        is_descendant = True
                        break
                    parent = parent.parent
                if not is_descendant:
                    candidate_heads.append(name)

            if not candidate_heads:
                self.report({'WARNING'}, T("ui.main_panel.gt_warn_no_valid_chain_heads"))
                return {'CANCELLED'}

            # Build the active chain and each source chain, generating the pair list
            active_chain = weight_utils.build_chain_from_head(active_name, arm_obj)
            pairs = []
            chain_count = 0
            for head in candidate_heads:
                src_chain = weight_utils.build_chain_from_head(head, arm_obj)
                chain_count += 1
                for i, src_bone in enumerate(src_chain):
                    if i < len(active_chain):
                        keep = active_chain[i]
                    else:
                        keep = active_chain[-1]
                    pairs.append((keep, src_bone))

            bpy.ops.object.mode_set(mode='OBJECT')
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            self.report({'INFO'}, T("ui.main_panel.gt_info_chains_merged").format(
                chains=chain_count, name=active_name, pairs=len(pairs)))

        elif self.action in ('ALIGN_FULL', 'ALIGN_POS', 'ALIGN_POS_ROLL'):
            selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
            if len(selected_arms) != 2:
                self.report({'ERROR'}, T("ui.main_panel.gt_err_need_two_armatures"))
                return {'CANCELLED'}
            target = arm_obj
            source = [o for o in selected_arms if o != target][0]
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            if self.action == 'ALIGN_FULL':
                mode = 'FULL'
            elif self.action == 'ALIGN_POS_ROLL':
                mode = 'POS_ROLL'
            else:
                mode = 'POS_ONLY'

            count = bone_utils.align_armatures_by_name(source, target, mode=mode)

            label_map = {
                'ALIGN_FULL': T("ui.main_panel.align_mode_full"),
                'ALIGN_POS': T("ui.main_panel.gt_label_align_pos"),
                'ALIGN_POS_ROLL': T("ui.main_panel.align_mode_pos_roll"),
            }
            self.report({'INFO'}, T("ui.main_panel.gt_info_align_result").format(label=label_map[self.action], n=count))

        return {'FINISHED'}
class MODDER_OT_AutoDetectPreset(bpy.types.Operator):
    """Detect the selected armature's bone coverage and auto-match the best-fitting preset"""
    bl_idname = "modder.auto_detect_preset"
    bl_label = "Detect Preset"
    bl_options = {'REGISTER', 'UNDO'}

    attr_name: bpy.props.StringProperty()
    is_import_x: bpy.props.BoolProperty(default=True)

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.auto_detect_preset_tip")

    def execute(self, context):
        arm = context.active_object
        if not arm or arm.type != 'ARMATURE':
            self.report({'WARNING'}, T("ui.main_panel.err_select_armature_first"))
            return {'CANCELLED'}

        from .bone_mapper import auto_detect_preset
        result = auto_detect_preset(arm, self.is_import_x)
        if result:
            settings = context.scene.mhw_suite_settings
            setattr(settings, self.attr_name, result)
            display = os.path.splitext(result)[0]
            self.report({'INFO'}, T("ui.main_panel.info_detected").format(name=display))
        else:
            self.report({'WARNING'}, T("ui.main_panel.warn_no_preset_found"))
        return {'FINISHED'}


# ── register / unregister ─────────────────────────────────────────────────────

classes = [
    MHW_OT_GeneralTools,
    MODDER_OT_AutoDetectPreset,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
