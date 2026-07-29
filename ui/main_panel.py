import bpy
import os
import re
from ..core.i18n import T, draw_language_toggle, get_lang
from ..core import bone_utils, weight_utils, ui_config
from . import game_sections
from ..core.mdf_generator_base import MHW_OT_SetChannelSize
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..games.re9.batch_export import get_schemes_callback
from ..games.re4.batch_export import get_schemes_callback as get_re4_schemes_callback
from ..games.mhws.batch_export import get_mhws_schemes_callback, get_mhws_armor_callback, get_mhws_variants
from ..games.mhrs.batch_export import get_mhrs_schemes_callback, get_mhrs_armor_callback, get_mhrs_genders
from ..games.mhwi.batch_export import (
    get_mhwi_armor_sets_callback,
    get_mhwi_hr_armor_callback,
    get_mhwi_mr_armor_callback,
    get_mhwi_sp_armor_callback,
)
from ..games.mhwi.weapon_data import get_mhwi_weapon_sets_callback, get_weapon_type_items
from ..core.bone_mapper import BoneMapManager

# Mapping detail preview cache: {(x_preset, y_preset): (mapper_x, mapper_y)}
_mapping_detail_cache = {}


def _align_mode_items(self, context):
    return [
        ('POS_ONLY', T("ui.main_panel.align_mode_pos_only"), T("ui.main_panel.align_mode_pos_only_desc")),
        ('POS_ROLL', T("ui.main_panel.align_mode_pos_roll"), T("ui.main_panel.align_mode_pos_roll_desc")),
        ('FULL',     T("ui.main_panel.align_mode_full"),     T("ui.main_panel.align_mode_full_desc")),
    ]


def _mhwi_export_mode_items(self, context):
    return [
        ('ARMOR',  T("ui.main_panel.mhwi_mode_armor"),  T("ui.main_panel.mhwi_mode_armor_desc")),
        ('WEAPON', T("ui.main_panel.mhwi_mode_weapon"), T("ui.main_panel.mhwi_mode_weapon_desc")),
    ]


def _mhwi_rank_tab_items(self, context):
    return [
        ('HR', T("ui.main_panel.mhwi_rank_hr"), T("ui.main_panel.mhwi_rank_hr_desc")),
        ('MR', T("ui.main_panel.mhwi_rank_mr"), T("ui.main_panel.mhwi_rank_mr_desc")),
        ('SP', T("ui.main_panel.mhwi_rank_sp"), T("ui.main_panel.mhwi_rank_sp_desc")),
    ]


def _mhwi_gender_items(self, context):
    return [
        ('F',    T("ui.main_panel.mhwi_gender_f"),    T("ui.main_panel.mhwi_gender_f_desc")),
        ('M',    T("ui.main_panel.mhwi_gender_m"),    T("ui.main_panel.mhwi_gender_m_desc")),
        ('BOTH', T("ui.main_panel.mhwi_gender_both"), T("ui.main_panel.mhwi_gender_both_desc")),
    ]


def _mhws_bs_bind_part_items(self, context):
    return [
        ("1", T("ui.main_panel.mhws_bind_part_helmet"), ""),
        ("2", T("ui.main_panel.mhws_bind_part_body"), ""),
    ]


class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # Top toggle row
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=False)
    show_mhws: bpy.props.BoolProperty(name="MHWS", default=False)
    show_mhrs: bpy.props.BoolProperty(name="MHRS", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    show_re9: bpy.props.BoolProperty(name="RE9", default=False)

    # Basic tools toggle
    show_basic_tools: bpy.props.BoolProperty(name="Basic Tools", default=True)

    # Universal converter toggle
    show_std_converter: bpy.props.BoolProperty(name="Universal Skeleton Conversion", default=True)
    show_experimental: bpy.props.BoolProperty(name="Experimental Features", default=False)

    # Preset selection (X/Y) - used by the standard converter
    import_preset_enum: bpy.props.EnumProperty(
        name="Source Preset (X)",
        description="Select the skeleton structure of the imported model",
        items=get_import_presets_callback,
    )

    target_preset_enum: bpy.props.EnumProperty(
        name="Target Game (Y)",
        description="Select the target game to export to",
        items=get_target_presets_callback,
        update=lambda self, context: setattr(
            self, "align_mode_override", bone_utils.get_default_align_mode(self.target_preset_enum)
        ),
    )

    align_mode_override: bpy.props.EnumProperty(
        name="Align Mode",
        description="Bone alignment (Snap) mode; automatically syncs to the preset's default when the target game (Y) changes",
        items=_align_mode_items,
        default=0,
    )

    show_mapping_details: bpy.props.BoolProperty(name="Show Mapping Details", default=False)

    bone_view_mode: bpy.props.EnumProperty(
        items=[
            ('ALL',     '全显',    '显示所有骨骼'),
            ('BASE',    '仅基础骨', '隐藏物理骨，只显示预设基础骨'),
            ('PHYSICS', '仅物理骨', '隐藏基础骨，只显示物理骨'),
        ],
        default='ALL'
    )

    # Pose convert section
    show_pose_convert: bpy.props.BoolProperty(name="Pose Convert", default=False)

    # Pose-convert-only preset (independent of the standard converter's X/Y presets)
    pose_import_preset_enum: bpy.props.EnumProperty(
        name="Skeleton Preset",
        description="Preset used to recognize bone names",
        items=get_import_presets_callback,
    )

    # Saved pose record selection
    pose_preset_enum: bpy.props.EnumProperty(
        name="Pose Record",
        description="Select a saved pose matrix record",
        items=get_pose_presets_callback
    )

    # RE9 batch export scheme
    re9_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE9",
        items=get_schemes_callback
    )

    # MHWI batch export
    mhwi_export_mode: bpy.props.EnumProperty(
        name="Export Mode",
        items=_mhwi_export_mode_items,
        default=0,
    )
    mhwi_armor_sets_file: bpy.props.EnumProperty(
        name="Preset Group",
        description="Select an MHWI armor preset group JSON",
        items=get_mhwi_armor_sets_callback,
    )
    mhwi_weapon_sets_file: bpy.props.EnumProperty(
        name="Preset Group",
        description="Select an MHWI weapon preset group JSON",
        items=get_mhwi_weapon_sets_callback,
    )
    mhwi_weapon_type_tab: bpy.props.EnumProperty(
        name="Weapon Type",
        items=get_weapon_type_items,
    )
    mhwi_rank_tab: bpy.props.EnumProperty(
        name="Rank",
        items=_mhwi_rank_tab_items,
        default=0,
    )
    mhwi_gender: bpy.props.EnumProperty(
        name="Gender",
        items=_mhwi_gender_items,
        default=0,
    )
    mhwi_selected_hr_armor: bpy.props.EnumProperty(
        name="LR/HR Armor",
        description="Select the LR/HR armor to export",
        items=get_mhwi_hr_armor_callback,
    )
    mhwi_selected_mr_armor: bpy.props.EnumProperty(
        name="MR Armor",
        description="Select the MR armor to export",
        items=get_mhwi_mr_armor_callback,
    )
    mhwi_selected_sp_armor: bpy.props.EnumProperty(
        name="Full Transmog Set",
        description="Select the full transmog set to export",
        items=get_mhwi_sp_armor_callback,
    )
    mhwi_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mod3 collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights "
                     "(requires RE Mesh Editor; silently skipped if not installed)",
        default=True,
    )
    mhwi_confuse_before_export: bpy.props.BoolProperty(
        name="Anti-Plagiarism",
        description="Adds confusion content to mod3/mrl3 that doesn't affect normal use, but helps deter people "
                     "who repackage others' mods as their own",
        default=False,
    )

    # MHWs batch export
    mhws_armor_scheme: bpy.props.EnumProperty(
        name="Armor Pack",
        description="Select an MHWs armor pack JSON",
        items=get_mhws_schemes_callback
    )
    mhws_armor_variant: bpy.props.EnumProperty(
        name="Set Variant",
        description="Select the set variant (male/female hunter x male/female set)",
        items=get_mhws_variants,
    )
    mhws_selected_armor: bpy.props.EnumProperty(
        name="Armor",
        description="Select the armor to export",
        items=get_mhws_armor_callback
    )

    # MHWs Bonesystem
    mhws_use_bonesystem: bpy.props.BoolProperty(
        name="Use Bonesystem",
        description="Also generate fbxskel.7 and BoneSystem JSON on export (requires the Bonesystem framework)",
        default=False,
    )
    mhws_fbxskel_name: bpy.props.StringProperty(
        name="FBXSkel Definition Name",
        description="Written to the JSON's FbxPath field, also used as the .fbxskel.7 filename (e.g. ch03_000_9000)",
    )
    mhws_bs_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="Armature",
        description="MHWs character armature used to generate the fbxskel",
    )
    mhws_bs_hide_face: bpy.props.BoolProperty(
        name="Hide Face",    default=True)
    mhws_bs_hide_hair: bpy.props.BoolProperty(
        name="Hide Hair",    default=True)
    mhws_bs_hide_slinger: bpy.props.BoolProperty(
        name="Hide Slinger",  default=True)
    mhws_bs_bind_face: bpy.props.BoolProperty(
        name="Bind Face",    default=True)
    mhws_bs_bind_part: bpy.props.EnumProperty(
        name="Bind Part",
        items=_mhws_bs_bind_part_items,
        default=0,
    )
    mhws_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=False,
    )
    mhws_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mesh collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights (requires RE Mesh Editor)",
        default=True,
    )
    re9_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )

    # MHRS batch export
    mhrs_armor_scheme: bpy.props.EnumProperty(
        name="Armor Pack",
        description="Select an MHRS armor pack JSON",
        items=get_mhrs_schemes_callback
    )
    mhrs_gender: bpy.props.EnumProperty(
        name="Gender",
        description="Select hunter gender",
        items=get_mhrs_genders,
    )
    mhrs_selected_armor: bpy.props.EnumProperty(
        name="Armor",
        description="Select the armor to export",
        items=get_mhrs_armor_callback
    )
    mhrs_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=False,
    )
    mhrs_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mesh collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights (requires RE Mesh Editor)",
        default=True,
    )
    mhrs_use_shadow_export: bpy.props.BoolProperty(
        name="Use Shadow Mesh",
        description="On export, align the built-in Shadow reference model's skeleton to the selected armature and "
                     "export it to the fixed mod/{gender}/bone/ path",
        default=False,
    )
    mhrs_shadow_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="Align Armature",
        description="Target armature to align the Shadow reference model's skeleton to; if left empty and only "
                     "one Mesh collection is bound this run, that collection's armature is used automatically",
    )

    # RE4 batch export
    re4_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE4",
        items=get_re4_schemes_callback
    )
    re4_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )
    re4_use_fakebone: bpy.props.BoolProperty(
        name="Use Fake Head Method",
        description="Before exporting fbxskel, auto-generate body+finger End bones "
                     "(the native skeleton is specified by the preset's native_skeleton field)",
        default=False,
    )
    re4_use_body_arm: bpy.props.BoolProperty(
        name="Use Body Armature",
        description="Automatically get the armature from the body Mesh collection and align it to the native "
                     "skeleton, skipping manual fbxskel armature binding",
        default=False,
    )


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


class MHW_PT_MainPanel(bpy.types.Panel):
    bl_label = "MOD Toolkit"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        draw_language_toggle(layout)
        layout.separator()

        # =========================================
        # 1. Top toggle row
        # =========================================
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="MHWS")
        row.prop(settings, "show_mhrs", toggle=True, text="MHRS")
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        row.prop(settings, "show_re9", toggle=True, text="RE9")
        
        layout.separator()

        # =========================================
        # 2. Basic tools
        # =========================================
        basic_box = layout.box()
        row = basic_box.row()
        row.prop(settings, "show_basic_tools",
                 icon="TRIA_DOWN" if settings.show_basic_tools else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.basic_tools_header"), icon='TOOL_SETTINGS')

        if settings.show_basic_tools:
            col = basic_box.column(align=True)

            col.label(text=T("ui.main_panel.label_bone_merge"), icon='AUTOMERGE_ON')
            col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_simplify_chain")).action = 'SIMPLIFY_CHAIN'
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_to_active")).action = 'MERGE_TO_ACTIVE'
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_chains")).action = 'MERGE_CHAINS'

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_bone_processing"), icon='BONE_DATA')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_roll_zero")).action = 'ROLL_ZERO'
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_mirror_x")).action = 'MIRROR_X'

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_armature_align"), icon='ORIENTATION_GIMBAL')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_btn_align_pos")).action = 'ALIGN_POS'
            row.operator("mhw.general_tools", text=T("ui.main_panel.align_mode_pos_roll")).action = 'ALIGN_POS_ROLL'
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_btn_align_full")).action = 'ALIGN_FULL'

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_weight_processing"), icon='GROUP_VERTEX')
            row = col.row(align=True)
            row.operator("mhw.sk_to_weights", text=T("ui.main_panel.btn_sk_to_weights"), icon='SHAPEKEY_DATA')
            row.operator("mhw.merge_renamed_vgroups", text=T("ui.main_panel.btn_merge_renamed_vgroups"), icon='AUTOMERGE_ON')

        layout.separator()

        # =========================================
        # 3. Universal skeleton conversion system
        # =========================================
        main_box = layout.box()
        row = main_box.row()
        row.prop(settings, "show_std_converter",
                 icon="TRIA_DOWN" if settings.show_std_converter else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.std_converter_header"), icon='ARMATURE_DATA')

        if settings.show_std_converter:
            col = main_box.column(align=True)
            row = col.row(align=True)
            row.prop(settings, "import_preset_enum", text=T("ui.main_panel.import_preset_label"), icon='IMPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'import_preset_enum'
            op.is_import_x = True
            row = col.row(align=True)
            row.prop(settings, "target_preset_enum", text=T("ui.main_panel.target_preset_label"), icon='EXPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'target_preset_enum'
            op.is_import_x = False

            col.separator()

            # Core actions (with preset-dependency hints)
            row = col.row(align=True)
            row.scale_y = 1.2
            row.prop(settings, "align_mode_override", text="")
            row.operator("modder.universal_snap", text=T("ui.main_panel.btn_universal_snap"), icon='SNAP_ON')

            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("modder.direct_convert", text=T("ui.main_panel.btn_direct_convert"), icon='MOD_VERTEX_WEIGHT')

            # Experimental features (collapsible)
            col.separator()
            row = col.row()
            row.prop(settings, "show_experimental",
                     icon="TRIA_DOWN" if settings.show_experimental else "TRIA_RIGHT",
                     icon_only=True, emboss=False)
            row.label(text=T("ui.main_panel.experimental_header"), icon='ERROR')

            if settings.show_experimental:
                exp_col = col.column(align=True)

                exp_col.label(text=T("ui.main_panel.label_skeleton_cleanup"), icon='TOOL_SETTINGS')
                exp_col.operator("modder.merge_physics_weights", text=T("ui.main_panel.btn_merge_physics_weights"), icon='TRASH')
                exp_col.operator("modder.remove_non_base_bones", text=T("ui.main_panel.btn_remove_non_base_bones"), icon='X')
                exp_col.operator("modder.rename_bones_to_target", text=T("ui.main_panel.btn_rename_bones_to_target"), icon='SORTALPHA')

                exp_col.separator()
                exp_col.label(text=T("ui.main_panel.label_physics_chain_tools"), icon='BONE_DATA')
                exp_col.operator("modder.smart_graft", text=T("ui.main_panel.btn_smart_graft"), icon='BONE_DATA')
                row = exp_col.row(align=True)
                row.operator("modder.merge_into_parent", text=T("ui.main_panel.btn_merge_into_parent"), icon='SNAP_MIDPOINT')
                row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_add_tail"), icon='RIGID_BODY').action = 'ADD_TAIL'
                row = exp_col.row(align=True)
                row.operator("modder.mark_as_main_continue", text=T("ui.main_panel.btn_mark_main_continue"), icon='HANDLE_ALIGNED')
                row.operator("modder.clear_chain_role", text=T("ui.main_panel.btn_clear_chain_role"), icon='X')
                exp_col.operator("modder.refresh_physics_bone_colors", text=T("ui.main_panel.btn_refresh_bone_colors"), icon='COLOR')
                exp_col.separator()
                row = exp_col.row(align=True)
                row.label(text=T("ui.main_panel.label_bone_visibility"), icon='HIDE_OFF')
                row = exp_col.row(align=True)
                row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_all"),
                             depress=(settings.bone_view_mode == 'ALL')).mode = 'ALL'
                row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_base"),
                             depress=(settings.bone_view_mode == 'BASE')).mode = 'BASE'
                row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_physics"),
                             depress=(settings.bone_view_mode == 'PHYSICS')).mode = 'PHYSICS'

            # Mapping detail preview
            col.separator()
            row = col.row()
            row.prop(settings, "show_mapping_details", text=T("ui.main_panel.show_mapping_details_label"),
                     icon='TRIA_DOWN' if settings.show_mapping_details else 'TRIA_RIGHT',
                     emboss=False)

            if settings.show_mapping_details:
                if arm_obj and arm_obj.type == 'ARMATURE':
                    if 'AUTO' in (settings.import_preset_enum, settings.target_preset_enum):
                        col.label(text=T("ui.main_panel.label_mapping_preview_need_preset"), icon='INFO')
                    else:
                        cache_key = (settings.import_preset_enum, settings.target_preset_enum)
                        if cache_key not in _mapping_detail_cache:
                            m_x = BoneMapManager()
                            m_y = BoneMapManager()
                            m_x.load_preset(settings.import_preset_enum, is_import_x=True)
                            m_y.load_preset(settings.target_preset_enum, is_import_x=False)
                            _mapping_detail_cache.clear()
                            _mapping_detail_cache[cache_key] = (m_x, m_y)
                        mapper, mapper_y = _mapping_detail_cache[cache_key]

                        preview_box = col.box()
                        for group_name, group_data in ui_config.UI_HIERARCHY.items():
                            g_box = preview_box.box()
                            g_box.label(text=group_name, icon=group_data['icon'])

                            for sub_name, bones in group_data['subsections'].items():
                                sub_col = g_box.column(align=True)
                                sub_col.label(text=sub_name)

                                for std_key in bones:
                                    if std_key in ui_config.OPTIONAL_BONES:
                                        if std_key not in mapper_y.mapping_data:
                                            continue

                                    main_bone, aux_list = mapper.get_matches_for_standard(arm_obj, std_key)
                                    m_row = sub_col.row(align=True)
                                    m_row.label(text=f"  {ui_config.get_display_name(std_key)}")

                                    if main_bone:
                                        status = f"{main_bone}"
                                        if aux_list: status += f" (+{len(aux_list)})"
                                        m_row.label(text=status, icon='CHECKMARK')
                                    else:
                                        m_row.label(text=T("ui.main_panel.label_missing"), icon='CANCEL')
                else:
                    col.label(text=T("ui.main_panel.label_select_armature_preview"), icon='INFO')

        layout.separator()

        # =========================================
        # 4. Pose convert (standalone section)
        # =========================================
        pose_box = layout.box()
        row = pose_box.row()
        row.prop(settings, "show_pose_convert",
                 icon="TRIA_DOWN" if settings.show_pose_convert else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.pose_convert_header"), icon='OUTLINER_OB_ARMATURE')

        if settings.show_pose_convert:
            col = pose_box.column(align=True)

            row = col.row(align=True)
            row.prop(settings, "pose_import_preset_enum", text=T("ui.main_panel.pose_preset_field_label"), icon='IMPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'pose_import_preset_enum'
            op.is_import_x = True

            col.separator()
            col.label(text=T("ui.main_panel.label_simple_tools"))
            col.operator("modder.tpose_direction", icon='EMPTY_SINGLE_ARROW')
            col.operator("modder.tpose_matrix_zero", text=T("ui.main_panel.btn_tpose_matrix_zero"), icon='MESH_GRID')

            col.separator()
            col.label(text=T("ui.main_panel.label_pose_recorder"))

            row = col.row(align=True)
            row.prop(settings, "pose_preset_enum", text="")
            row.operator("modder.delete_pose_preset", text="", icon='TRASH')

            col.operator("modder.record_transform", text=T("ui.main_panel.btn_record_transform"), icon='REC')

            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("modder.apply_transform_forward", text=T("ui.main_panel.btn_apply_forward"), icon='PLAY')
            row.operator("modder.apply_transform_inverse", text=T("ui.main_panel.btn_apply_inverse"), icon='LOOP_BACK')

        layout.separator()

        # =========================================
        # 5. Game-specific toolbars
        # =========================================
        
        # One data-driven pass per game -- see ui/game_sections.py. These five
        # sections used to be five hand-written blocks that had drifted apart.
        for _key, _shown in (("mhwi", settings.show_mhwi),
                             ("mhws", settings.show_mhws),
                             ("re4",  settings.show_re4),
                             ("mhrs", settings.show_mhrs),
                             ("re9",  settings.show_re9)):
            if _shown:
                game_sections.draw_section(layout, _key)
# Known Blender dynamic-enum limitation: if the list returned by an items=
# callback is a local variable, Python's GC can free the strings while the C
# side still holds a pointer to them, corrupting non-ASCII (CJK, etc.) text.
# Fix: stash the list in a module-level variable so GC can't collect it.
_sk_enum_cache: list = []


def _sk_enum_items(self, context):
    global _sk_enum_cache
    obj = context.active_object
    if not obj or not obj.data.shape_keys:
        _sk_enum_cache = [('1', 'No shape keys', '', 1)]
        return _sk_enum_cache
    items = []
    for i, kb in enumerate(obj.data.shape_keys.key_blocks):
        if i == 0:
            continue
        items.append((str(i), kb.name, '', i))
    _sk_enum_cache = items or [('1', 'No shape keys', '', 1)]
    return _sk_enum_cache


def _sk_filter_sign_items(self, context):
    return [
        ('+', T("ui.main_panel.sk_sign_pos"), ""),
        ('-', T("ui.main_panel.sk_sign_neg"), ""),
    ]


class MHW_OT_ShapeKeyToWeights(bpy.types.Operator):
    # Method inspired by: 光之影V, 幽玲乃昕
    """Convert a shape key to a vertex group (normalized weights + Laplacian smoothing + seam sync)"""
    bl_idname = "mhw.sk_to_weights"
    bl_label = "Shape Key to Weights"
    bl_options = {'REGISTER', 'UNDO'}

    shape_key_enum: bpy.props.EnumProperty(
        name="Shape Key",
        items=_sk_enum_items,
        description="Shape key to convert (Basis is excluded)",
    )
    ignore_threshold: bpy.props.FloatProperty(
        name="Ignore Threshold",
        default=0.001, min=0.0,
        description="Vertices with displacement smaller than this are ignored",
    )
    weight_strength: bpy.props.FloatProperty(
        name="Weight Strength",
        default=1.0, min=0.1, max=5.0,
        description="Multiplier applied after normalization",
    )
    smooth_factor: bpy.props.FloatProperty(
        name="Smooth Factor",
        default=0.5, min=0.0, max=1.0,
        description="How much weight diffuses to neighbors each Laplacian pass",
    )
    smooth_iters: bpy.props.IntProperty(
        name="Smooth Iterations",
        default=10, min=0, max=100,
        description="Number of Laplacian smoothing passes",
    )
    sync_seams: bpy.props.BoolProperty(
        name="Sync Seam Vertices",
        default=True,
        description="Force identical weights on spatially coincident vertices to prevent UV seam tearing",
    )
    use_direction_filter: bpy.props.BoolProperty(
        name="Direction Filter",
        default=False,
        description="Only include vertices whose displacement projects positively onto the chosen axis",
    )
    filter_axis: bpy.props.EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    filter_sign: bpy.props.EnumProperty(
        name="Direction",
        items=_sk_filter_sign_items,
        default=0,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        obj = context.active_object
        idx = obj.active_shape_key_index
        if idx > 0:
            self.shape_key_enum = str(idx)
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "shape_key_enum", text=T("ui.main_panel.sk_field_shape_key"))
        col.separator()
        col.prop(self, "ignore_threshold", text=T("ui.main_panel.sk_field_ignore_threshold"))
        col.prop(self, "weight_strength", text=T("ui.main_panel.sk_field_weight_strength"), slider=True)
        col.prop(self, "smooth_factor", text=T("ui.main_panel.sk_field_smooth_factor"), slider=True)
        col.prop(self, "smooth_iters", text=T("ui.main_panel.sk_field_smooth_iters"))
        col.prop(self, "sync_seams", text=T("ui.main_panel.sk_field_sync_seams"))
        col.separator()
        col.prop(self, "use_direction_filter", text=T("ui.main_panel.sk_field_direction_filter"))
        if self.use_direction_filter:
            row = col.row(align=True)
            row.prop(self, "filter_axis", expand=True)
            row = col.row(align=True)
            row.prop(self, "filter_sign", expand=True)

    def execute(self, context):
        obj = context.active_object
        key_blocks = obj.data.shape_keys.key_blocks
        idx = int(self.shape_key_enum)

        if idx <= 0 or idx >= len(key_blocks):
            self.report({'ERROR'}, T("ui.main_panel.sk_err_select_non_basis"))
            return {'CANCELLED'}

        active_kb = key_blocks[idx]
        basis_kb = obj.data.shape_keys.reference_key

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        direction = None
        if self.use_direction_filter:
            sign = 1.0 if self.filter_sign == '+' else -1.0
            direction = {'X': (sign, 0, 0), 'Y': (0, sign, 0), 'Z': (0, 0, sign)}[self.filter_axis]

        result = weight_utils.shape_key_to_weights(
            obj, active_kb, basis_kb,
            ignore_threshold=self.ignore_threshold,
            weight_strength=self.weight_strength,
            smooth_factor=self.smooth_factor,
            smooth_iters=self.smooth_iters,
            sync_seams=self.sync_seams,
            direction=direction,
        )

        if result is None:
            self.report({'WARNING'}, T("ui.main_panel.sk_warn_no_deformation").format(name=active_kb.name))
            return {'CANCELLED'}

        self.report({'INFO'}, T("ui.main_panel.sk_info_generated").format(name=active_kb.name, n=result))
        return {'FINISHED'}


# (shape_key_name, direction_xyz, part_id, mhwi_vg, mhws_vg, re4_vg, re9_vg)
# part_id is an internal English identifier (translated for display via
# _MMD_FACE_PART_KEYS below); it used to be the raw Chinese label itself.
_MMD_FACE_ENTRIES = [
    ("ウィンク２",  ( 0,  0, -1), "l_upper_eyelid", "MhBone_321", "L_UpEyeLid_LOD01",    "L_U_Eyelid03",  "L_UprLdEdge_02"),
    ("ウィンク２",  ( 0,  0,  1), "l_lower_eyelid", "MhBone_325", "L_LoEyeLid_LOD01",    "L_D_Eyelid03",  "L_LwrLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0, -1), "r_upper_eyelid", "MhBone_334", "R_UpEyeLid_LOD01",    "R_U_Eyelid03",  "R_UprLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0,  1), "r_lower_eyelid", "MhBone_338", "R_LoEyeLid_LOD01",    "R_D_Eyelid03",  "R_LwrLdEdge_02"),
    ("あ",          ( 0,  0,  1), "upper_lip",      "MhBone_381", "C_upLip_T_LOD01",     "C_UpperLip",    "C_UprLp_02"),
    ("あ",          ( 0,  0, -1), "lower_lip",      "MhBone_388", "C_loLip_T_LOD01",     "C_LowerLip",    "C_LwrLp_02"),
    ("あ",          ( 1,  0,  0), "l_mouth_corner", "MhBone_384", "L_cornerLip_B_LOD01", "L_MouthCorner", "L_LipCorner_02"),
    ("あ",          (-1,  0,  0), "r_mouth_corner", "MhBone_385", "R_cornerLip_B_LOD01", "R_MouthCorner", "R_LipCorner_02"),
]
_MMD_FACE_GAME_COL = {'MHWI': 3, 'MHWS': 4, 'RE4': 5, 'RE9': 6}

# T() keys for each part_id's display label (used in the done/skipped report message)
_MMD_FACE_PART_KEYS = {
    "l_upper_eyelid": "ui.main_panel.mmd_part_l_upper_eyelid",
    "l_lower_eyelid": "ui.main_panel.mmd_part_l_lower_eyelid",
    "r_upper_eyelid": "ui.main_panel.mmd_part_r_upper_eyelid",
    "r_lower_eyelid": "ui.main_panel.mmd_part_r_lower_eyelid",
    "upper_lip":      "ui.main_panel.mmd_part_upper_lip",
    "lower_lip":      "ui.main_panel.mmd_part_lower_lip",
    "l_mouth_corner": "ui.main_panel.mmd_part_l_mouth_corner",
    "r_mouth_corner": "ui.main_panel.mmd_part_r_mouth_corner",
}

# Custom ignore-threshold/weight-strength/smooth-factor/smooth-iterations are
# not user-configurable here; fixed per-part values are used instead.
# Upper eyelids get a higher deformation-capture precision (threshold 0,
# smooth factor 0) to avoid blink weights being over-smoothed.
_MMD_FACE_UPPER_EYELID_LABELS = {"l_upper_eyelid", "r_upper_eyelid"}
_MMD_FACE_FIXED_PARAMS = {
    True:  dict(ignore_threshold=0.0,   weight_strength=1.0, smooth_factor=0.0, smooth_iters=10),
    False: dict(ignore_threshold=0.001, weight_strength=1.0, smooth_factor=0.5, smooth_iters=10),
}


class MHW_OT_MMDFaceWeights(bpy.types.Operator):
    """Split MMD eyelid/mouth shape keys by direction into target-game facial vertex groups"""
    bl_idname = "mhw.mmd_face_weights"
    bl_label = "MMD Face Weights"
    bl_options = {'REGISTER', 'UNDO'}

    target_game: bpy.props.EnumProperty(
        name="Target Game",
        items=[
            ('MHWI', "MHWI", ""),
            ('MHWS', "MHWS", ""),
            ('RE4',  "RE4",  ""),
            ('RE9',  "RE9",  ""),
        ],
    )
    sync_seams: bpy.props.BoolProperty(
        name="Sync Seam Vertices",
        default=True,
    )

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.mmd_face_weights_tip")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "target_game", text=T("ui.main_panel.mmd_target_game_label"))
        col.separator()
        col.prop(self, "sync_seams", text=T("ui.main_panel.mmd_sync_seams_label"))

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        key_blocks = obj.data.shape_keys.key_blocks
        basis_kb = obj.data.shape_keys.reference_key
        vg_col = _MMD_FACE_GAME_COL[self.target_game]

        done, skipped = [], []
        for sk_name, direction, part_id, *vg_names in _MMD_FACE_ENTRIES:
            kb = key_blocks.get(sk_name)
            if kb is None:
                skipped.append(part_id)
                continue
            target_vg = vg_names[vg_col - 3]
            params = _MMD_FACE_FIXED_PARAMS[part_id in _MMD_FACE_UPPER_EYELID_LABELS]

            result = weight_utils.shape_key_to_weights(
                obj, kb, basis_kb,
                sync_seams=self.sync_seams,
                direction=direction,
                vg_name=target_vg,
                **params,
            )
            if result is None:
                skipped.append(part_id)
            else:
                done.append(part_id)

        if not done:
            self.report({'WARNING'}, T("ui.main_panel.mmd_warn_no_valid_shapekeys"))
            return {'CANCELLED'}

        join_sep = "、" if get_lang() == 'ZH' else ", "
        done_labels = [T(_MMD_FACE_PART_KEYS[p]) for p in done]
        msg = T("ui.main_panel.mmd_info_generated").format(n=len(done), parts=join_sep.join(done_labels))
        if skipped:
            skipped_labels = [T(_MMD_FACE_PART_KEYS[p]) for p in skipped]
            msg += T("ui.main_panel.mmd_info_skipped_suffix").format(parts=join_sep.join(skipped_labels))
        self.report({'INFO'}, msg)
        return {'FINISHED'}


_RENAMED_VG_PATTERN = re.compile(r'^(.+)\.\d{3}$')


class MHW_OT_MergeRenamedVGroups(bpy.types.Operator):
    """Merge vertex groups named 'a.001', 'a.002', etc. into 'a' for all selected meshes.
Groups whose suffixed name matches a real bone in the bound armature are skipped."""
    bl_idname = "mhw.merge_renamed_vgroups"
    bl_label = "Merge Renamed Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        total_merged = 0
        total_skipped = 0

        for obj in mesh_objects:
            bound_arm = next(
                (mod.object for mod in obj.modifiers
                 if mod.type == 'ARMATURE' and mod.object),
                None
            )
            arm_bone_names = {b.name for b in bound_arm.data.bones} if bound_arm else set()

            to_merge = {}
            for vg in obj.vertex_groups:
                m = _RENAMED_VG_PATTERN.match(vg.name)
                if not m:
                    continue
                if vg.name in arm_bone_names:
                    total_skipped += 1
                    continue
                base = m.group(1)
                to_merge.setdefault(base, []).append(vg.name)

            for base_name, suffix_names in to_merge.items():
                weight_utils.merge_vgroups_multi(obj, suffix_names, base_name)
                total_merged += len(suffix_names)

        self.report(
            {'INFO'},
            T("ui.main_panel.merge_vg_done").format(merged=total_merged, skipped=total_skipped)
        )
        return {'FINISHED'}


# ==========================================
# register / unregister
# ==========================================
classes = [
    MHW_PT_SuiteSettings,
    MHW_OT_GeneralTools,
    MHW_OT_ShapeKeyToWeights,
    MHW_OT_MMDFaceWeights,
    MHW_OT_SetChannelSize,
    MHW_OT_MergeRenamedVGroups,
    MHW_PT_MainPanel,
]


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

        from ..core.bone_mapper import auto_detect_preset
        result = auto_detect_preset(arm, self.is_import_x)
        if result:
            settings = context.scene.mhw_suite_settings
            setattr(settings, self.attr_name, result)
            display = os.path.splitext(result)[0]
            self.report({'INFO'}, T("ui.main_panel.info_detected").format(name=display))
        else:
            self.report({'WARNING'}, T("ui.main_panel.warn_no_preset_found"))
        return {'FINISHED'}


classes.append(MODDER_OT_AutoDetectPreset)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)