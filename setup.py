#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动环境配置脚本 - 增强版 (彻底解决 CentOS 7 + urllib3 冲突)
"""
import subprocess
import sys
import os
import platform
import json
import time

class EnvironmentSetup:
    def __init__(self):
        self.required_packages = {
            'flask': 'flask>=2.0.0',
            'flask_cors': 'flask-cors>=4.0.0',
            'dashscope': 'dashscope>=1.14.0',
            'requests': 'requests>=2.31.0',
            'PIL': 'Pillow>=10.0.0',
        }
        self.missing_packages = []
        self.is_centos7 = False
        self.is_windows = platform.system() == 'Windows'

    def _run_pip_cmd(self, cmd_args):
        """跨平台执行 pip 命令（列表形式，推荐）"""
        try:
            # 基础命令: [sys.executable, '-m', 'pip']
            base_cmd = [sys.executable, '-m', 'pip']
            full_cmd = base_cmd + cmd_args
            print(f"执行命令: {' '.join(full_cmd)}")
            subprocess.check_call(full_cmd)
            return True
        except subprocess.CalledProcessError as e:
            print(f"命令执行失败: {e}")
            return False

    def check_centos7(self):
        """检测是否为 CentOS 7"""
        if self.is_windows:
            return
        try:
            if os.path.exists('/etc/centos-release'):
                with open('/etc/centos-release', 'r') as f:
                    content = f.read()
                    if 'CentOS Linux release 7' in content or 'CentOS release 7' in content:
                        self.is_centos7 = True
                        print("⚠️  检测到 CentOS 7 系统")
                        print("   将自动处理 urllib3 + OpenSSL 兼容性问题")
        except:
            pass

    def fix_urllib3_centos7(self):
        """专门解决 CentOS 7 的 urllib3 版本锁定"""
        if not self.is_centos7:
            return True

        print("\n🔧 正在为 CentOS 7 修复 urllib3 版本...")
        # 1. 彻底卸载 urllib3 及相关包
        print("   → 卸载旧版本 urllib3, requests, dashscope...")
        self._run_pip_cmd(['uninstall', '-y', 'urllib3', 'requests', 'dashscope'])

        # 2. 安装兼容的 urllib3 1.26.x (强制)
        print("   → 安装 urllib3 1.26.x 兼容版本...")
        if not self._run_pip_cmd(['install', 'urllib3<2.0', '--no-cache-dir']):
            print("   ❌ urllib3 降级失败")
            return False

        # 3. 重新安装其他依赖
        print("   → 重新安装 requests 和 dashscope...")
        self._run_pip_cmd(['install', 'requests', 'dashscope'])

        # 4. 验证版本
        try:
            import urllib3
            if urllib3.__version__.startswith('2.'):
                print(f"   ❌ 修复失败，仍为 urllib3 {urllib3.__version__}")
                return False
            else:
                print(f"   ✅ 修复成功，urllib3 版本: {urllib3.__version__}")
                return True
        except ImportError:
            print("   ❌ 无法导入 urllib3，修复失败")
            return False

    def check_python_version(self):
        """检查Python版本（需要3.7+）"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 7):
            print(f"❌ Python版本过低: {version.major}.{version.minor}")
            return False
        print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True

    def check_and_install_packages(self):
        """检查并安装基础依赖包"""
        print("\n📦 检查Python依赖包...")
        # 先升级pip
        self._run_pip_cmd(['install', '--upgrade', 'pip'])

        for package_name, package_spec in self.required_packages.items():
            try:
                if package_name == 'PIL':
                    import PIL
                elif package_name == 'flask_cors':
                    import flask_cors
                else:
                    __import__(package_name)
                print(f"   ✅ {package_name} 已安装")
            except ImportError:
                print(f"   ⚠️  {package_name} 未安装")
                self.missing_packages.append((package_name, package_spec))

        if self.missing_packages:
            print(f"\n📥 需要安装 {len(self.missing_packages)} 个依赖包...")
            for pkg_name, pkg_spec in self.missing_packages:
                print(f"   正在安装 {pkg_name}...")
                # 简单安装，不重复处理urllib3（后面专项修复）
                self._run_pip_cmd(['install', pkg_spec])
            return True
        return True

    def create_config_template(self):
        """创建配置文件模板"""
        if not os.path.exists("config.json"):
            template_config = {
                "dashscope_key": "",
                "style": "高级感",
                "camera": "环绕旋转",
                "duration": 10,
            }
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(template_config, f, indent=2)
            print("\n📝 已创建 config.json，请填入你的API Key")
            return False
        return True

    def run_web_app(self):
        """启动应用前做最终环境验证"""
        print("\n🚀 启动前最终环境验证...")
        # 再次确认 urllib3 版本（针对 CentOS 7）
        if self.is_centos7:
            try:
                import urllib3
                if urllib3.__version__.startswith('2.'):
                    print("❌ urllib3 版本仍过高，无法启动。请手动执行：")
                    print("   pip3 uninstall urllib3 -y")
                    print("   pip3 install 'urllib3<2.0'")
                    return False
                else:
                    print(f"✅ urllib3 版本兼容: {urllib3.__version__}")
            except ImportError:
                print("❌ urllib3 未正确安装，请检查")
                return False

        print("\n✅ 环境验证通过，启动 Flask 服务...")
        # 直接执行 web_app.py 的导入和运行
        try:
            # 设置环境变量，防止 SSL 警告
            os.environ['CURL_CA_BUNDLE'] = '/etc/pki/tls/certs/ca-bundle.crt'
            from web_app import app
            app.run(host='0.0.0.0', port=5000, debug=False)
            return True
        except ImportError as e:
            print(f"❌ 导入 web_app 失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            return False

    def setup(self):
        print("=" * 50)
        print("🎬 AI视频场景生成器 - 智能配置")
        print("=" * 50)

        if not self.check_python_version():
            return False

        self.check_centos7()

        # 1. 安装基础依赖（可能包含urllib3高版本）
        self.check_and_install_packages()

        # 2. 如果是CentOS7，强制修复urllib3
        if self.is_centos7:
            if not self.fix_urllib3_centos7():
                print("\n❌ CentOS 7 兼容性修复失败")
                print("请手动执行以下命令后重新运行 setup.py：")
                print("  pip3 uninstall urllib3 requests dashscope -y")
                print("  pip3 install 'urllib3<2.0' requests dashscope")
                return False

        # 3. 创建配置
        self.create_config_template()

        # 4. 创建必要文件夹
        for folder in ['uploads', 'videos', 'logs', 'static', 'templates']:
            os.makedirs(folder, exist_ok=True)

        # 5. 启动
        return self.run_web_app()


if __name__ == "__main__":
    setup = EnvironmentSetup()
    success = setup.setup()
    if not success:
        print("\n❌ 配置失败，请根据提示手动操作")
        sys.exit(1)
