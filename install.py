#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# 虚拟环境目录常量
VENV_DIR = ".venv"

try:
    from install_deps.modules.utils import validate_python_version, get_system_info, format_size, get_free_space
    from install_deps.modules.interactive_installer import InteractiveInstaller
except ImportError as e:
    print(f"❌ 无法导入必需的模块: {e}")
    sys.exit(1)


class BettaFishInstaller:
    def __init__(self):
        self.interactive_installer = InteractiveInstaller()
        self.install_plan = {}
        self.virtual_env_path = None
        self.python_executable = sys.executable

    def check_system_requirements(self) -> bool:
        print("🔍 检查系统要求...")
        print()

        # 检查Python版本
        python_ok, python_msg = validate_python_version("3.9")
        if python_ok:
            print(f"✅ {python_msg}")
        else:
            print(f"❌ {python_msg}")
            return False

        # 检查系统信息
        sys_info = get_system_info()
        print(f"✅ 操作系统: {sys_info['platform']} {sys_info['release']}")
        print(f"✅ 系统架构: {sys_info['architecture']}")
        print(f"✅ Python版本: {sys_info['python_version']}")

        # 检查可用磁盘空间
        free_space = get_free_space(".")
        print(f"✅ 可用磁盘空间: {format_size(free_space)}")

        if free_space < 2 * 1024 * 1024 * 1024:  # 2GB
            print("⚠️  警告: 可用磁盘空间少于2GB，可能不足以完成安装")
            if not input("是否继续？(y/N): ").lower().startswith('y'):
                return False

        # 检查Linux系统依赖
        if sys_info['platform'] == 'Linux':
            self._check_linux_system_deps()

        print()
        return True

    def _check_linux_system_deps(self):
        """检查Linux系统所需的依赖"""
        missing_deps = []

        # 检查libxml2和libxslt（lxml需要）
        try:
            import subprocess
            result = subprocess.run(["dpkg", "-l", "libxml2-dev"], capture_output=True)
            if result.returncode != 0:
                missing_deps.append("libxml2-dev")
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            missing_deps.append("libxml2-dev")

        try:
            import subprocess
            result = subprocess.run(["dpkg", "-l", "libxslt1-dev"], capture_output=True)
            if result.returncode != 0:
                missing_deps.append("libxslt1-dev")
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            missing_deps.append("libxslt1-dev")

        if missing_deps:
            print("⚠️  检测到缺少系统依赖:")
            print(f"   缺失: {', '.join(missing_deps)}")
            print("   安装命令: sudo apt install " + " ".join(missing_deps))
            print("💡 这些依赖是安装 lxml 所需的系统库")
            choice = input("是否现在安装？(y/N): ").lower().strip()
            if choice.startswith('y'):
                try:
                    import subprocess
                    install_cmd = ["sudo", "apt", "install"] + missing_deps
                    print(f"🔄 正在安装: {' '.join(missing_deps)}")
                    subprocess.run(install_cmd, check=True)
                    print("✅ 系统依赖安装完成")
                except Exception as e:
                    print(f"❌ 系统依赖安装失败: {e}")
                    print("💡 请手动运行: sudo apt install " + " ".join(missing_deps))
        else:
            print("✅ Linux系统依赖检查通过")

    def create_virtual_environment(self, plan: dict) -> bool:
        if not plan['virtual_env']['use']:
            print("🐍 跳过虚拟环境创建")
            return True

        env_manager = plan['virtual_env']['manager']
        print(f"🐍 使用 {env_manager} 创建虚拟环境...")

        try:
            if env_manager == "conda":
                import subprocess
                subprocess.run(["conda", "create", "-n", "bettafish", "python=3.11", "-y"], check=True)
                print("✅ Conda环境创建成功")
                print("💡 虚拟环境已配置，将使用conda命令安装依赖")
            elif env_manager == "uv":
                import subprocess
                subprocess.run(["uv", "venv"], check=True)
                print("✅ UV虚拟环境创建成功")
                self.virtual_env_path = VENV_DIR
                if os.name == 'nt':  # Windows
                    self.python_executable = f"{VENV_DIR}\\Scripts\\python.exe"
                else:
                    self.python_executable = f"{VENV_DIR}/bin/python"
                print("💡 虚拟环境已自动激活")
            elif env_manager == "venv":
                import subprocess
                subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
                print("✅ Python虚拟环境创建成功")
                self.virtual_env_path = VENV_DIR
                if os.name == 'nt':  # Windows
                    self.python_executable = f"{VENV_DIR}\\Scripts\\python.exe"
                else:
                    self.python_executable = f"{VENV_DIR}/bin/python"
                print("💡 虚拟环境已自动激活")

            return True
        except Exception as e:
            print(f"❌ 虚拟环境创建失败: {e}")
            return False

    def _check_requirements_file(self) -> Path:
        """检查requirements.txt文件是否存在"""
        requirements_path = Path("requirements.txt")
        if not requirements_path.exists():
            print("❌ 未找到 requirements.txt 文件")
            raise FileNotFoundError("未找到 requirements.txt 文件")

        print(f"📦 使用依赖文件: {requirements_path}")
        return requirements_path

    def _install_with_venv_manager(self, manager: str, requirements_path: Path) -> None:
        """使用虚拟环境管理器安装依赖"""
        import subprocess

        if manager == "conda":
            print("🔄 使用 Conda 安装依赖...")
            subprocess.run(["conda", "run", "-n", "bettafish", "pip", "install", "-r", str(requirements_path)], check=True)
        elif manager == "uv":
            print("🔄 使用 UV 安装依赖...")
            subprocess.run(["uv", "pip", "install", "-r", str(requirements_path)], check=True)
        else:  # venv
            print("🔄 使用虚拟环境的 Pip 安装依赖...")
            subprocess.run([self.python_executable, "-m", "pip", "install", "-r", str(requirements_path)], check=True)

    def _install_without_venv(self, requirements_path: Path) -> None:
        """不使用虚拟环境安装依赖"""
        import subprocess

        try:
            subprocess.run([self.python_executable, "-m", "pip", "install", "-r", str(requirements_path)], check=True)
        except subprocess.CalledProcessError as e:
            if "externally-managed-environment" in str(e):
                print("⚠️  系统Python环境受保护")
                from install_deps.modules.utils import confirm
                if confirm("是否使用 --break-system-packages 强制安装？", default=False):
                    subprocess.run([self.python_executable, "-m", "pip", "install", "--break-system-packages", "-r", str(requirements_path)], check=True)
                else:
                    print("❌ 安装被取消")
                    raise Exception("安装被用户取消")
            else:
                raise e

    def install_dependencies(self, plan: dict) -> bool:
        print("📦 安装依赖包...")

        try:
            requirements_path = self._check_requirements_file()
            import subprocess

            if plan['virtual_env']['use']:
                self._install_with_venv_manager(plan['virtual_env']['manager'], requirements_path)
            else:
                self._install_without_venv(requirements_path)

            print("✅ 依赖包安装完成")
            return True
        except Exception as e:
            print(f"❌ 依赖包安装失败: {e}")
            return False

    def install_playwright(self) -> bool:
        print("🌐 安装 Playwright 浏览器驱动...")

        try:
            import subprocess
            subprocess.run([self.python_executable, "-m", "playwright", "install", "chromium"], check=True)
            print("✅ Playwright 浏览器驱动安装完成")
            return True
        except Exception as e:
            print(f"❌ Playwright 安装失败: {e}")
            return False

    def generate_config_file(self, plan: dict) -> bool:
        print("⚙️  生成配置文件...")

        try:
            env_example_path = Path(".env.example")
            env_path = Path(".env")

            if not env_example_path.exists():
                print("⚠️  未找到 .env.example 文件，将创建基础配置文件")
                self._create_basic_env_file(env_path, plan)
            else:
                # 复制.env.example到.env
                import shutil
                shutil.copy(env_example_path, env_path)
                print("✅ 已创建 .env 配置文件")

            # 根据用户选择更新配置
            self._update_env_config(env_path, plan)

            print("✅ 配置文件生成完成")
            print("💡 请编辑 .env 文件，填入您的API密钥")
            return True
        except Exception as e:
            print(f"❌ 配置文件生成失败: {e}")
            return False

    def _create_basic_env_file(self, env_path: Path, plan: dict):
        content = f"""# BettaFish 配置文件
# 由安装脚本自动生成

# 服务器配置
HOST=0.0.0.0
PORT=5000

# 数据库配置
DB_DIALECT={plan['database']['db_type']}
"""

        content += f"""DB_HOST={plan['database']['host']}
DB_PORT={plan['database']['port']}
DB_USER={plan['database']['username']}
DB_PASSWORD={plan['database']['password']}
DB_NAME={plan['database']['database']}
DB_CHARSET=utf8mb4
"""

        if plan['llm_config'].get('use_recommended'):
            content += """
# LLM配置 - 推荐方案 (请填入您的API密钥)
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2-0711-preview
INSIGHT_ENGINE_API_KEY=

MEDIA_ENGINE_BASE_URL=https://aihubmix.com/v1
MEDIA_ENGINE_MODEL_NAME=gemini-2.5-pro
MEDIA_ENGINE_API_KEY=

QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat
QUERY_ENGINE_API_KEY=

REPORT_ENGINE_BASE_URL=https://aihubmix.com/v1
REPORT_ENGINE_MODEL_NAME=gemini-2.5-pro
REPORT_ENGINE_API_KEY=
"""

        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _update_env_config(self, env_path: Path, plan: dict):
        # 这里可以添加根据用户选择更新配置的逻辑
        pass

    def run_installation(self, plan: dict) -> bool:
        print("🚀 开始安装过程...")
        print()

        steps = [
            ("创建虚拟环境", lambda: self.create_virtual_environment(plan)),
            ("安装依赖包", lambda: self.install_dependencies(plan)),
            ("安装浏览器驱动", lambda: self.install_playwright()),
            ("生成配置文件", lambda: self.generate_config_file(plan)),
        ]

        for step_name, step_func in steps:
            print(f"🔄 {step_name}...")
            if not step_func():
                print(f"❌ {step_name}失败，安装终止")
                return False
            print()

        print("🎉 安装完成！")
        return True

    def show_completion_message(self, plan: dict):
        print("🎊 BettaFish 安装完成！")
        print("=" * 50)

        if plan['virtual_env']['use']:
            env_manager = plan['virtual_env']['manager']
            print("📋 下一步操作:")
            if env_manager == "conda":
                print("  1. 激活虚拟环境: conda activate bettafish")
            elif env_manager == "uv":
                print("  1. 激活虚拟环境: source {VENV_DIR}/bin/activate")
            else:  # venv
                if os.name == 'nt':  # Windows
                    print("  1. 激活虚拟环境: {VENV_DIR}\\Scripts\\activate")
                else:
                    print("  1. 激活虚拟环境: source {VENV_DIR}/bin/activate")
            print("  2. 编辑 .env 文件，填入API密钥")
            print("  3. 启动应用: python app.py")
        else:
            print("📋 下一步操作:")
            print("  1. 编辑 .env 文件，填入API密钥")
            print("  2. 启动应用: python app.py")

        print()
        print("🌐 启动后访问: http://localhost:5000")
        print()
        print("📚 文档和帮助:")
        print("  • GitHub仓库: https://github.com/666ghj/BettaFish")
        print("  • 问题反馈: https://github.com/666ghj/BettaFish/issues")
        print("  • 官方文档: README.md")
        print()
        print("💡 提示:")
        print("  • 首次启动可能需要下载模型文件")
        print("  • 如果遇到问题，请检查 .env 配置")
        print("  • 建议使用推荐配置的LLM服务")

    def main(self):
        try:
            # 检查系统要求
            if not self.check_system_requirements():
                print("❌ 系统要求检查失败")
                return 1

            # 获取安装计划
            self.install_plan = self.interactive_installer.get_installation_plan()

            # 显示安装计划摘要
            if not self.interactive_installer.show_installation_summary(self.install_plan):
                print("❌ 用户取消安装")
                return 0

            # 执行安装
            if not self.run_installation(self.install_plan):
                print("❌ 安装失败")
                return 1

            # 显示完成信息
            self.show_completion_message(self.install_plan)
            return 0

        except KeyboardInterrupt:
            print("\n❌ 安装被用户中断")
            return 1
        except Exception as e:
            print(f"❌ 安装过程中发生错误: {e}")
            return 1


def main():
    installer = BettaFishInstaller()
    return installer.main()


if __name__ == "__main__":
    sys.exit(main())
