import bpy
import os
import re
from ..core.i18n import T, draw_language_toggle, get_lang
from ..core import bone_utils, ui_config, export_autofix
from ..core.shapekey_export import MT_ShapeKeyExportSettings
from . import game_sections
from ..core.mdf_generator_base import (
    MHW_OT_SetChannelSize, MHW_OT_SetShaderSource,
    MHW_OT_GenCopyMaterial, MHW_OT_GenPasteMaterial,
)
from ..core.mdf_generator_ui_base import MDFGEN_UL_materials
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..games.re9.batch_export import get_schemes_callback
from ..games.re4.batch_export import get_schemes_callback as get_re4_schemes_callback
from ..games.oni.batch_export import get_schemes_callback as get_oni_schemes_callback
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
from ..core.stable_enum import stable_enum

# Mapping detail preview cache: {(x_preset, y_preset): (mapper_x, mapper_y)}
_mapping_detail_cache = {}


def _mhws_bonesystem_exclusive(own, other):
    """Update callback: MHWS's Bonesystem and the Wilds lua bone system are two
    alternative ways to reshape the body and must not both be on (user's call),
    so switching one on switches the other off. Switching off touches nothing."""
    def update(self, context):
        if getattr(self, own) and getattr(self, other):
            setattr(self, other, False)
    return update


def _align_mode_items(self, context):
    return [
        ('POS_ONLY', T("ui.main_panel.align_mode_pos_only"), T("ui.main_panel.align_mode_pos_only_desc")),
        ('POS_ROLL', T("ui.main_panel.align_mode_pos_roll"), T("ui.main_panel.align_mode_pos_roll_desc")),
        ('FULL',     T("ui.main_panel.align_mode_full"),     T("ui.main_panel.align_mode_full_desc")),
    ]


#: Persistent backing for the enum below -- the trap every dynamic enum in this
#: addon documents: Blender's C side keeps the pointers, so a list built fresh
#: inside the callback is freed the moment Python drops it.
_skeleton_mode_item_cache = []


def _mhrs_skeleton_mode_items(self, context):
    # Four-tuples: an ENUM_FLAG enum needs an explicit power-of-two value per item.
    _skeleton_mode_item_cache.clear()
    _skeleton_mode_item_cache.extend([
        ('SHADOW', T("ui.main_panel.mhrs_skel_shadow"), T("ui.main_panel.mhrs_skel_shadow_desc"), 1),
        ('LUA',    T("ui.main_panel.mhrs_skel_lua"),    T("ui.main_panel.mhrs_skel_lua_desc"),    2),
    ])
    return _skeleton_mode_item_cache


#: Where the previous selection is remembered, so the update below can tell which
#: of two lit buttons was the one just clicked.
_SKEL_PREV_KEY = "_mhrs_skeleton_mode_prev"


def _mhrs_skeleton_mode_exclusive(self, context):
    """Keep at most one scheme lit.

    A plain EnumProperty cannot express "neither" -- it always holds a value --
    so this is an ENUM_FLAG (a set, which may be empty) narrowed back down to a
    radio button by hand.  That buys the two things a plain enum could not have
    together: nothing selected by default, and clicking the lit button again to
    turn it back off.

    Re-assigning inside an update callback re-enters this function once; the
    second pass sees a single item and only records it, so it terminates.
    """
    current = set(self.mhrs_skeleton_mode)
    if len(current) > 1:
        just_clicked = current - set(self.get(_SKEL_PREV_KEY, []))
        self.mhrs_skeleton_mode = just_clicked or {next(iter(current))}
        return
    self[_SKEL_PREV_KEY] = list(current)


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


# align_mode_override reused as the mode picker for same-kind (name-matched)
# alignment, which routes to MHW_OT_GeneralTools instead of the preset pipeline
_SAME_KIND_ALIGN_ACTION = {
    'POS_ONLY': 'ALIGN_POS',
    'POS_ROLL': 'ALIGN_POS_ROLL',
    'FULL':     'ALIGN_FULL',
}


class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # The show_* fold flags of the old single panel are gone: the panels are
    # native now and Blender keeps their open state.  Values left in older
    # .blend files are ignored.

    # Collapses the converter down to a plain name-matched armature align
    same_kind_align: bpy.props.BoolProperty(
        name="Same-Kind Bone Align",
        description="Both armatures are already the same kind, so bones are matched by name and no preset is needed",
        default=False,
    )

    # 辅助骨槽位。默认**开着忽略**，因为它决定的是老用户按同一个按钮会得到什么：
    # 关掉时扭转骨/掌骨这些各占一个标准键，会被改名保留；勾上时它们折回父段的 aux，
    # 也就是并进主骨然后删掉 —— 与加槽位之前完全一致。改默认值等于替所有人改结果。
    ignore_aux_bones: bpy.props.BoolProperty(
        name="Ignore Auxiliary Bones",
        description="Merge twist / palm / elbow / knee / instep bones into their parent bone instead of giving them their own standard slots",
        default=True,
    )

    # 标准化前先把形变权重归一化。默认开，理由是它**不改变外观**（Blender 的骨架形变
    # 与 RE/mod3 的导出器都先除以权重总和），只把隐患拆掉；而忘记做的代价很高——
    # 在总和跑偏的顶点上刷过一笔之后，Auto Normalize 会把幽灵残留放大成可见的错误影响。
    normalize_weights_first: bpy.props.BoolProperty(
        name="Normalize Weights First",
        description="Normalize bone-deform vertex weights to 1 before standardising",
        default=True,
    )

    # Preset selection (X/Y) - used by the standard converter.  stable_enum: these
    # list a folder, and a plain dynamic enum's selection shifts when a file is
    # added -- see core/stable_enum.py.
    import_preset_enum: stable_enum(
        "import_preset_enum",
        name="Source Preset (X)",
        description="Select the skeleton structure of the imported model",
        items=get_import_presets_callback,
    )

    target_preset_enum: stable_enum(
        "target_preset_enum",
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


    bone_view_mode: bpy.props.EnumProperty(
        items=[
            ('ALL',     '全显',    '显示所有骨骼'),
            ('BASE',    '仅基础骨', '隐藏物理骨，只显示预设基础骨'),
            ('PHYSICS', '仅物理骨', '隐藏基础骨，只显示物理骨'),
        ],
        default='ALL'
    )


    # Pose-convert-only preset (independent of the standard converter's X/Y presets)
    pose_import_preset_enum: stable_enum(
        "pose_import_preset_enum",
        name="Skeleton Preset",
        description="Preset used to recognize bone names",
        items=get_import_presets_callback,
    )

    # Saved pose record selection
    pose_preset_enum: stable_enum(
        "pose_preset_enum",
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

    # Onimusha batch export scheme
    oni_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for Onimusha",
        items=get_oni_schemes_callback
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
    mhwi_watermark_before_export: bpy.props.BoolProperty(
        name="Add Watermark Effect",
        description="Anti-reselling: adds a watermark effect that is almost only visible when changing equipment",
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
        update=_mhws_bonesystem_exclusive("mhws_use_bonesystem", "mhws_use_lua_bone_system"),
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
    mhws_use_lua_bone_system: bpy.props.BoolProperty(
        name="Use Lua Bone System",
        description="Also write the Wilds \"lua bone system\" custom joint json on export "
                    "(a community REFramework script, distinct from the Bonesystem above; "
                    "uses the same armature picked for Bonesystem)",
        default=False,
        update=_mhws_bonesystem_exclusive("mhws_use_lua_bone_system", "mhws_use_bonesystem"),
    )
    mhws_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=False,
    )
    # 「导出前自动修正」 replaces the separate Clean Mesh / Triangulate Face toggles
    # (docs/pre_export_check_plan.md §3.1). Old .blend values for those two are
    # simply ignored; the only visible change is triangulation now defaulting on.
    mhws_autofix: bpy.props.BoolProperty(
        name="Auto-fix Before Export",
        description="Fix the problems that need no decision before exporting; the gear chooses which",
        default=True,
    )
    mhws_autofix_items: bpy.props.EnumProperty(
        name="Auto-fix Items",
        items=export_autofix.enum_items_for('MHWS'),
        options={'ENUM_FLAG'},
        **export_autofix.default_kwargs('MHWS'),
    )
    # 「导出前自动修正」, same as MHWS's (replaces the old triangulate toggle).
    re9_autofix: bpy.props.BoolProperty(
        name="Auto-fix Before Export",
        description="Fix the problems that need no decision before exporting; the gear chooses which",
        default=True,
    )
    re9_autofix_items: bpy.props.EnumProperty(
        name="Auto-fix Items",
        items=export_autofix.enum_items_for('RE9'),
        options={'ENUM_FLAG'},
        **export_autofix.default_kwargs('RE9'),
    )
    re9_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )
    oni_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )
    # Shape keys in each batch export (core/shapekey_export.py).
    mhws_shapekeys: bpy.props.PointerProperty(type=MT_ShapeKeyExportSettings)
    re4_shapekeys: bpy.props.PointerProperty(type=MT_ShapeKeyExportSettings)
    re9_shapekeys: bpy.props.PointerProperty(type=MT_ShapeKeyExportSettings)
    mhrs_shapekeys: bpy.props.PointerProperty(type=MT_ShapeKeyExportSettings)
    oni_shapekeys: bpy.props.PointerProperty(type=MT_ShapeKeyExportSettings)

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
    # 「导出前自动修正」, same as MHWS's (replaces the old triangulate toggle).
    mhrs_autofix: bpy.props.BoolProperty(
        name="Auto-fix Before Export",
        description="Fix the problems that need no decision before exporting; the gear chooses which",
        default=True,
    )
    mhrs_autofix_items: bpy.props.EnumProperty(
        name="Auto-fix Items",
        items=export_autofix.enum_items_for('MHRS'),
        options={'ENUM_FLAG'},
        **export_autofix.default_kwargs('MHRS'),
    )
    #: How the armour's proportions reach the game.  One enum rather than two
    #: checkboxes because the two are mutually exclusive in the game, not merely
    #: by convention: both move the same joints, so enabling both applies the
    #: same offset twice.
    mhrs_skeleton_mode: bpy.props.EnumProperty(
        name="Skeleton Scheme",
        description="How this armor set's skeleton reaches the game",
        items=_mhrs_skeleton_mode_items,
        options={'ENUM_FLAG'},
        # No default=.  Blender rejects a set default when items is a callback
        # ("'default' can only be an integer when 'items' is a function"), and an
        # ENUM_FLAG with no default already starts as the empty set, which is
        # exactly "neither scheme chosen".
        update=_mhrs_skeleton_mode_exclusive,
    )
    mhrs_shadow_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="Source Armature",
        description="Armature this set's skeleton is read from; if left empty and only "
                     "one Mesh collection is bound this run, that collection's armature is used automatically",
    )

    # RE4 batch export
    re4_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE4",
        items=get_re4_schemes_callback
    )
    # 「导出前自动修正」, same as MHWS's (replaces the old triangulate toggle).
    re4_autofix: bpy.props.BoolProperty(
        name="Auto-fix Before Export",
        description="Fix the problems that need no decision before exporting; the gear chooses which",
        default=True,
    )
    re4_autofix_items: bpy.props.EnumProperty(
        name="Auto-fix Items",
        items=export_autofix.enum_items_for('RE4'),
        options={'ENUM_FLAG'},
        **export_autofix.default_kwargs('RE4'),
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


# =========================================
# Panels
# =========================================
# Everything is a native panel or sub-panel rather than one panel with
# hand-rolled fold boxes: folding a native panel is not an undo step, does not
# mark the .blend as modified, and gets Blender's own panel features
# (drag to reorder, Ctrl+click to collapse the others, pinning).
#
# Top to bottom: the root panel (language, game picker, and the active game's
# tool groups as sub-panels -- see ui/game_sections.py), then the tools that do
# not depend on the game.  The idnames are new on purpose: Blender caches the
# panel order per idname, and a fresh idname is what gets the new order.
#
# A panel whose header goes through T() has an empty bl_label: Blender draws
# bl_label after whatever draw_header() adds, so a real one shows up twice.

ROOT_IDNAME = "MTK_PT_root"
BASIC_IDNAME = "MTK_PT_basic_tools"
CONVERT_IDNAME = "MTK_PT_skeleton_convert"


class _SidebarPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'


class MTK_PT_Root(_SidebarPanel, bpy.types.Panel):
    bl_label = "MOD Toolkit"
    bl_idname = ROOT_IDNAME
    bl_order = 0

    def draw_header_preset(self, context):
        # In the header so it stays reachable with the panel folded, and so it
        # costs no row in the body.
        draw_language_toggle(self.layout, compact=True)

    def draw(self, context):
        game_sections.draw_game_picker(self.layout, context)


# ── Basic tools ───────────────────────────────────────────────────────────────

class MTK_PT_BasicTools(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = BASIC_IDNAME
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.basic_tools_header"), icon='TOOL_SETTINGS')

    def draw(self, context):
        pass


class MTK_PT_BasicBones(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_basic_bones"
    bl_parent_id = BASIC_IDNAME
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.bone_weight_header"), icon='BONE_DATA')

    def draw(self, context):
        layout = self.layout
        # One per row: side by side, the English labels do not fit at the
        # default sidebar width.  Merging into the parent is the same kind of
        # operation as merging into the active bone and needs no preset.
        col = layout.column(align=True)
        col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_to_active")).action = 'MERGE_TO_ACTIVE'
        col.operator("modder.merge_into_parent", text=T("ui.main_panel.btn_merge_into_parent"), icon='SNAP_MIDPOINT')
        col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_simplify_chain")).action = 'SIMPLIFY_CHAIN'
        col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_chains")).action = 'MERGE_CHAINS'

        # NOTE: the armature-align group used to live here. It overlapped with
        # the standard converter's align action, so it now sits behind that
        # panel's "Same-Kind Bone Align" toggle.
        row = layout.row(align=True)
        row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_roll_zero")).action = 'ROLL_ZERO'
        row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_mirror_x")).action = 'MIRROR_X'


class MTK_PT_BasicMesh(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_basic_mesh"
    bl_parent_id = BASIC_IDNAME
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.mesh_header"), icon='GROUP_VERTEX')

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("mhw.clear_empty_vgroups", text=T("ui.main_panel.btn_clear_empty_vgroups"), icon='GROUP_VERTEX')
        col.operator("mhw.merge_renamed_vgroups", text=T("ui.main_panel.btn_merge_renamed_vgroups"), icon='AUTOMERGE_ON')
        col.separator()
        col.operator("mhw.cylindrical_face_normals", text=T("ui.main_panel.btn_cylindrical_face_normals"), icon='NORMALS_FACE')
        col.operator("mhw.reset_face_normals", text=T("ui.main_panel.btn_reset_face_normals"), icon='FILE_REFRESH')
        col.separator()
        # Transfer Normals and Safe Apply Base Transform are off the panel: the
        # first is only for references whose corner order differs, so it sits
        # inside the Fix Shape Key Normals dialog; the second is done by the
        # export fixes.
        col.operator("mhw.sk_to_weights", text=T("ui.main_panel.btn_sk_to_weights"), icon='SHAPEKEY_DATA')
        col.operator("mhw.fix_shape_key_normals",
                     text=T("ui.main_panel.btn_fix_shape_key_normals"), icon='MOD_NORMALEDIT')
        col.operator("mhw.apply_modifiers_keep_shape_keys",
                     text=T("ui.main_panel.btn_apply_mods_keep_sk"), icon='MODIFIER')
        col.separator()
        col.operator("mhw.separate_by_materials",
                     text=T("ui.main_panel.btn_separate_by_materials"), icon='MOD_EXPLODE')
        col.operator("mhw.create_outline",
                     text=T("ui.main_panel.btn_create_outline"), icon='MOD_SOLIDIFY')


class MTK_PT_BasicTexture(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_basic_texture"
    bl_parent_id = BASIC_IDNAME
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.texture_header"), icon='TEXTURE')

    def draw(self, context):
        self.layout.operator("mt.tex_convert_dialog",
                             text=T("ui.main_panel.btn_tex_process"), icon='TEXTURE')


# ── Universal skeleton conversion ─────────────────────────────────────────────

def _split_row(layout):
    """A row whose props draw label-left / widget-right.  Used for the dropdowns
    that carry a label: drawn inline, the label got squeezed to two characters."""
    row = layout.row(align=True)
    row.use_property_split = True
    row.use_property_decorate = False
    return row


class MTK_PT_SkeletonConvert(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = CONVERT_IDNAME
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.std_converter_header"), icon='ARMATURE_DATA')

    def draw(self, context):
        settings = context.scene.mhw_suite_settings
        col = self.layout.column(align=True)
        col.prop(settings, "same_kind_align", text=T("ui.main_panel.same_kind_align_label"))
        if not settings.same_kind_align:
            # 同种类对齐按骨名逐一匹配，辅助骨本来就跟着走，这个开关对它无意义。
            col.prop(settings, "ignore_aux_bones",
                     text=T("ui.main_panel.ignore_aux_bones"))
        col.separator()

        # Same-kind armatures match by bone name, so the preset pipeline and
        # everything hanging off it is irrelevant here: show only the align rows.
        if settings.same_kind_align:
            _split_row(col).prop(settings, "align_mode_override",
                                 text=T("ui.main_panel.align_mode_label"))
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("mhw.general_tools",
                         text=T("ui.main_panel.btn_same_kind_snap"),
                         icon='SNAP_ON').action = _SAME_KIND_ALIGN_ACTION[settings.align_mode_override]
            return

        row = _split_row(col)
        row.prop(settings, "import_preset_enum", text=T("ui.main_panel.import_preset_label"), icon='IMPORT')
        op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
        op.attr_name = 'import_preset_enum'
        op.is_import_x = True
        row = _split_row(col)
        row.prop(settings, "target_preset_enum", text=T("ui.main_panel.target_preset_label"), icon='EXPORT')
        op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
        op.attr_name = 'target_preset_enum'
        op.is_import_x = False

        col.separator()
        row = col.row(align=True)
        row.prop(settings, "normalize_weights_first",
                 text=T("ui.main_panel.normalize_weights_first"))
        row.operator("modder.normalize_deform_weights", text="",
                     icon='MOD_VERTEX_WEIGHT')
        col.separator()

        # Core actions (with preset-dependency hints).  The mode picker has its
        # own row: sharing one, the button text was cut after "[X".
        _split_row(col).prop(settings, "align_mode_override",
                             text=T("ui.main_panel.align_mode_label"))
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("modder.universal_snap", text=T("ui.main_panel.btn_universal_snap"), icon='SNAP_ON')
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("modder.direct_convert", text=T("ui.main_panel.btn_direct_convert"), icon='MOD_VERTEX_WEIGHT')


class _PresetPipelinePanel(_SidebarPanel):
    """Sub-panels that only mean something with the X/Y presets in play."""
    bl_parent_id = CONVERT_IDNAME
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, "mhw_suite_settings", None)
        return settings is not None and not settings.same_kind_align


class MTK_PT_ConvertNonPhysics(_PresetPipelinePanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_convert_non_physics"
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.label_skeleton_cleanup"), icon='TOOL_SETTINGS')

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("modder.merge_physics_weights", text=T("ui.main_panel.btn_merge_physics_weights"), icon='TRASH')
        col.operator("modder.remove_non_base_bones", text=T("ui.main_panel.btn_remove_non_base_bones"), icon='X')
        col.operator("modder.rename_bones_to_target", text=T("ui.main_panel.btn_rename_bones_to_target"), icon='SORTALPHA')


class MTK_PT_ConvertPhysics(_PresetPipelinePanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_convert_physics"
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.label_physics_chain_tools"), icon='BONE_DATA')

    def draw(self, context):
        settings = context.scene.mhw_suite_settings
        layout = self.layout
        col = layout.column(align=True)
        col.operator("modder.smart_graft", text=T("ui.main_panel.btn_smart_graft"), icon='BONE_DATA')
        col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_add_tail"), icon='RIGID_BODY').action = 'ADD_TAIL'
        col.operator("modder.mark_as_main_continue", text=T("ui.main_panel.btn_mark_main_continue"), icon='HANDLE_ALIGNED')
        col.operator("modder.clear_chain_role", text=T("ui.main_panel.btn_clear_chain_role"), icon='X')
        col.operator("modder.refresh_physics_bone_colors", text=T("ui.main_panel.btn_refresh_bone_colors"), icon='COLOR')
        # Bone visibility lives here because the three modes filter by physics
        # vs base bones.
        layout.label(text=T("ui.main_panel.label_bone_visibility"), icon='HIDE_OFF')
        row = layout.row(align=True)
        row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_all"),
                     depress=(settings.bone_view_mode == 'ALL')).mode = 'ALL'
        row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_base"),
                     depress=(settings.bone_view_mode == 'BASE')).mode = 'BASE'
        row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_physics"),
                     depress=(settings.bone_view_mode == 'PHYSICS')).mode = 'PHYSICS'


class MTK_PT_ConvertMapping(_PresetPipelinePanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_convert_mapping"
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.mapping_details_header"))

    def draw(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        col = self.layout.column(align=True)
        if not (arm_obj and arm_obj.type == 'ARMATURE'):
            col.label(text=T("ui.main_panel.label_select_armature_preview"), icon='INFO')
            return
        if 'AUTO' in (settings.import_preset_enum, settings.target_preset_enum):
            col.label(text=T("ui.main_panel.label_mapping_preview_need_preset"), icon='INFO')
            return

        cache_key = (settings.import_preset_enum, settings.target_preset_enum)
        if cache_key not in _mapping_detail_cache:
            m_x = BoneMapManager()
            m_y = BoneMapManager()
            m_x.load_preset(settings.import_preset_enum, is_import_x=True)
            m_y.load_preset(settings.target_preset_enum, is_import_x=False)
            _mapping_detail_cache.clear()
            _mapping_detail_cache[cache_key] = (m_x, m_y)
        mapper, mapper_y = _mapping_detail_cache[cache_key]

        for group_name, group_data in ui_config.UI_HIERARCHY.items():
            g_box = col.box()
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


# ── Pose convert ──────────────────────────────────────────────────────────────

class MTK_PT_PoseConvert(_SidebarPanel, bpy.types.Panel):
    bl_label = ""
    bl_idname = "MTK_PT_pose_convert"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3

    def draw_header(self, context):
        self.layout.label(text=T("ui.main_panel.pose_convert_header"), icon='OUTLINER_OB_ARMATURE')

    def draw(self, context):
        settings = context.scene.mhw_suite_settings
        col = self.layout.column(align=True)

        # Both fixed-purpose tools below are self-contained: MMD A->T always matches
        # against the MMD preset internally, REE->T auto-detects the game from its own
        # private bone list. Neither needs the generic preset selector any more; that
        # selector now only feeds the Pose Recorder's optional name bridge below
        # (same-name matching is still the fallback there).
        col.label(text=T("ui.main_panel.label_simple_tools"))
        col.operator("modder.mmd_a_to_tpose", text=T("ui.main_panel.btn_mmd_a_to_tpose"), icon='EMPTY_SINGLE_ARROW')
        col.operator("modder.ree_to_tpose", text=T("ui.main_panel.btn_ree_to_tpose"), icon='MESH_GRID')

        col.separator()
        col.label(text=T("ui.main_panel.label_pose_recorder"))

        row = _split_row(col)
        row.prop(settings, "pose_import_preset_enum", text=T("ui.main_panel.pose_preset_field_label"), icon='IMPORT')
        op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
        op.attr_name = 'pose_import_preset_enum'
        op.is_import_x = True

        row = col.row(align=True)
        row.prop(settings, "pose_preset_enum", text="")
        row.operator("modder.delete_pose_preset", text="", icon='TRASH')

        col.operator("modder.record_transform", text=T("ui.main_panel.btn_record_transform"), icon='REC')

        # No icons: the labels already start with the arrows, and with icons
        # the English pair no longer fits side by side.
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator("modder.apply_transform_forward", text=T("ui.main_panel.btn_apply_forward"))
        row.operator("modder.apply_transform_inverse", text=T("ui.main_panel.btn_apply_inverse"))


# Known Blender dynamic-enum limitation: if the list returned by an items=
# callback is a local variable, Python's GC can free the strings while the C
# side still holds a pointer to them, corrupting non-ASCII (CJK, etc.) text.
# Fix: stash the list in a module-level variable so GC can't collect it.
_sk_enum_cache: list = []


# ==========================================
# register / unregister
# ==========================================
classes = [
    MT_ShapeKeyExportSettings,     # before the settings that point at it
    MHW_PT_SuiteSettings,
    MHW_OT_SetChannelSize,
    MHW_OT_SetShaderSource,
    MHW_OT_GenCopyMaterial,
    MHW_OT_GenPasteMaterial,
    MDFGEN_UL_materials,
    MTK_PT_Root,
    *game_sections.make_group_panels(ROOT_IDNAME),
    MTK_PT_BasicTools,
    MTK_PT_BasicBones,
    MTK_PT_BasicMesh,
    MTK_PT_BasicTexture,
    MTK_PT_SkeletonConvert,
    MTK_PT_ConvertNonPhysics,
    MTK_PT_ConvertPhysics,
    MTK_PT_ConvertMapping,
    MTK_PT_PoseConvert,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)