bl_info = {
    "name": "Modding Toolkit",
    "author": "Dimcirui",
    "version": (2, 6, 20),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MOD Toolkit",
    "description": "Modding Toolkit for Capcom's games",
    "category": "Object",
}

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, EnumProperty
from bpy.types import AddonPreferences

from . import addon_updater_ops 

from .core import migrate
from .core import i18n
from .core import standard_ops
from .core import pose_ops
from .core import bone_ops
from .core import mesh_ops
from .core import editor_props
from .core import editor_ops
from .core import mdf_tex_processor_base
from .core import tex_convert_base
from .core import shader_ops
from .core import chain_convert_ops
from . import ui, games

class MT_Preferences(AddonPreferences):
    bl_idname = __name__
    
    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )
    updater_interval_months: IntProperty(
        name='Months', description="Number of months between checking for updates",
        default=0, min=0
    )
    updater_interval_days: IntProperty(
        name='Days', description="Number of days between checking for updates",
        default=7, min=0,
    )
    updater_interval_hours: IntProperty(
        name='Hours', description="Number of hours between checking for updates",
        default=0, min=0, max=23
    )
    updater_interval_minutes: IntProperty(
        name='Minutes', description="Number of minutes between checking for updates",
        default=0, min=0, max=59
    )

    show_console_on_batch_export: BoolProperty(
        name="Show Console During Batch Export",
        description=(
            "Opens the system console before a batch export and leaves it open "
            "afterward, so progress and per-file errors can be watched live.\n"
            "Windows only. If RE Mesh Editor's or MHW Model Editor's own 'Show "
            "Console' option is also enabled, it is temporarily disabled during "
            "the batch so it doesn't re-toggle (and hide) the console mid-export.\n"
            "Like those addons, this uses Blender's console_toggle(), which can't "
            "detect whether the console is already open -- if it's already open "
            "when the batch starts, this will close it instead"
        ),
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "show_console_on_batch_export")
        addon_updater_ops.update_settings_ui(self, context)


modules = [
    i18n,
    editor_props,
    editor_ops,
    standard_ops,
    pose_ops,
    # Registered here rather than by ui.main_panel, which is where these
    # operators used to live. They own no PropertyGroup and no scene property,
    # so their position relative to ui/ does not matter.
    bone_ops,
    mesh_ops,
    mdf_tex_processor_base,
    tex_convert_base,
    shader_ops,
    chain_convert_ops,
    games,
    ui,
]

def register():
    addon_updater_ops.register(bl_info)
    migrate.run()

    bpy.utils.register_class(MT_Preferences)

    for mod in modules:
        mod.register()

    _patch_chain_import()

def _patch_chain_import():
    """给 RE-Chain-Editor 的 chain/chain2 导入打上快速补丁。

    上游把 alignChains() 放在链组循环内部，而它扫全场景 + 每节点做一次全量依赖图求值，
    导入代价是 O(G²·m)。实测导入 196 组需约 78 分钟（因此容易被误当成卡死而中断，
    留下静态看不出异常的残缺数据）；补丁后约 32 秒。细节见 core/re_chain_utils.py。

    RE-Chain-Editor 未安装时静默跳过；任何异常都不能影响本插件注册。
    """
    try:
        from .core.re_chain_utils import install_fast_chain_import
        n = install_fast_chain_import()
        if n:
            print(f"[Modding-Toolkit] fast chain import patch applied to {n} binding(s)")
    except Exception as e:
        print(f"[Modding-Toolkit] fast chain import patch skipped: {e}")

def unregister():
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(MT_Preferences)

    try:
        from .core.re_chain_utils import uninstall_fast_chain_import
        uninstall_fast_chain_import()
    except Exception:
        pass

    for mod in reversed(modules):
        mod.unregister()

if __name__ == "__main__":
    register()
