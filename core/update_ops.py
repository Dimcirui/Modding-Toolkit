import bpy
import json
import urllib.request
import ssl

# 替换为你的 GitHub 仓库 raw 地址
# 例如: https://raw.githubusercontent.com/YourName/RepoName/main/version.json
# 注意：一定要用 raw.githubusercontent.com
VERSION_URL = "https://raw.githubusercontent.com/dimcirui/modding-toolkit/main/version.json"

class MODDER_OT_CheckForUpdates(bpy.types.Operator):
    """检查插件更新"""
    bl_idname = "modder.check_updates"
    bl_label = "检查更新"
    
    def execute(self, context):
        try:
            # 忽略 SSL 证书验证 (防止部分网络环境下报错)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(VERSION_URL)
            with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                remote_ver = tuple(data.get("version", [0, 0, 0]))
                # 获取本地插件版本 (从 __init__ 读取)
                # 注意：这里假设插件包名是 "MHW-Modding-Toolkit" 或类似，需根据实际情况调整
                # 更稳妥的方法是直接从 bl_info 传进来，或者硬编码
                # 这里我们假设 bl_info 在运行时已注册，我们对比 context.preferences
                
                # 简单起见，我们直接获取当前 module 的 bl_info
                # 但由于这是在 operator 里，我们直接从 sys.modules 获取或者手动维护
                # 为了演示，我们假设本地版本是 context.scene 里的属性，或者直接对比
                
                # 更好的方式：从 add-on preferences 获取
                addon_name = __name__.split('.')[0]
                local_ver = context.preferences.addons[addon_name].bl_info.get('version', (0, 0, 0))
                
                if remote_ver > local_ver:
                    self.report({'WARNING'}, f"发现新版本: v{'.'.join(map(str, remote_ver))} (当前: v{'.'.join(map(str, local_ver))})")
                    # 这里可以弹窗提示下载
                    bpy.ops.wm.url_open(url=data.get("download_url", ""))
                else:
                    self.report({'INFO'}, "当前已是最新版本")
                    
        except Exception as e:
            self.report({'ERROR'}, f"检查更新失败: {str(e)}")
            
        return {'FINISHED'}

classes = [MODDER_OT_CheckForUpdates]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)