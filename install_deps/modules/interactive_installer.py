from typing import Dict, List, Tuple, Optional
from .utils import get_user_input, confirm, format_size, get_free_space, check_command_exists


class InteractiveInstaller:
    def __init__(self):
        self.install_options = {}

    def show_welcome(self) -> None:
        print("=" * 60)
        print("🐟 欢迎使用 BettaFish 微舆系统 安装向导")
        print("=" * 60)
        print("BettaFish 是一个多智能体舆情分析系统")
        print("本向导将帮助您完成系统的安装和配置")
        print("=" * 60)
        print()

    def decide_install_mode(self) -> str:
        print("📋 请选择安装模式:")
        print()
        print("1. 快速模式 - 使用默认配置，快速开始体验")
        print("   • 安装常用组件")
        print("   • 使用推荐配置")
        print("   • 适合初次使用")
        print()
        print("2. 自定义模式 - 手动选择组件和配置")
        print("   • 灵活选择所需组件")
        print("   • 自定义配置参数")
        print("   • 适合有特定需求")
        print()
        print("3. 开发模式 - 包含开发工具和调试功能")
        print("   • 安装开发依赖")
        print("   • 启用调试功能")
        print("   • 适合开发者")
        print()

        choices = ["1", "2", "3"]
        mode_map = {
            "1": "quick",
            "2": "custom",
            "3": "development"
        }

        choice = get_user_input("请选择安装模式", default="1", choices=choices)
        return mode_map[choice]

    def _show_virtual_env_explanation(self):
        """显示虚拟环境的说明"""
        print("🔧 要不要创建虚拟环境？")
        print()
        print("虚拟环境就像是给这个项目单独建一个\"房间\"，")
        print("里面的东西不会和你电脑上的其他项目搞混。")
        print()
        print("✅ 用虚拟环境的好处：")
        print("  • 不会弄乱你电脑上的其他Python项目")
        print("  • 可以用不同版本的软件包")
        print("  • 以后想删掉这个项目时，一键就能删干净")
        print("  • 安装软件包不需要管理员权限")
        print()
        print("❌ 不用虚拟环境的坏处：")
        print("  • 可能会影响其他Python项目")
        print("  • 有时候需要管理员权限才能装包")
        print("  • 以后删除项目时可能留下垃圾文件")
        print()

    def _confirm_skip_virtual_env(self) -> bool:
        """确认是否跳过虚拟环境"""
        print()
        print("⚠️  你确定不用虚拟环境吗？")
        print("不用的话就直接装在你电脑的Python环境里了。")
        return confirm("确定不用虚拟环境，继续安装？", default=True)

    def _get_available_managers(self) -> List[str]:
        """获取可用的环境管理器列表"""
        print()
        print("🐛 选择一个环境管理工具：")
        print()

        available_managers = []

        print("1. venv (Python自带的)")
        print("   • 简单可靠，不需要额外安装任何东西")
        print("   • Python自带的功能，肯定能用")
        available_managers.append("venv")

        if check_command_exists("uv"):
            print("2. uv (超级快的)")
            print("   • 比Python自带的pip快很多倍")
            print("   • 又快又好用，强烈推荐")
            available_managers.append("uv")
        else:
            print("2. uv (超级快的) - 需要安装")
            print("   • 比Python自带的pip快很多倍")
            print("   • 又快又好用，安装也很简单")
            available_managers.append("uv")

        if check_command_exists("conda"):
            print("3. conda (功能最多的)")
            print("   • 既能管Python包，也能管其他软件")
            print("   • 特别适合做数据科学和机器学习")
            available_managers.append("conda")

        print()
        return available_managers

    def _select_environment_manager(self, available_managers: List[str]) -> str:
        """选择环境管理器"""
        choices = ["1", "2"]
        if len(available_managers) > 2:
            choices.append("3")

        default_choice = "2" if "uv" in available_managers else "1"
        choice = get_user_input("选哪个？", default=default_choice, choices=choices)

        manager_map = {"1": "venv", "2": "uv", "3": "conda"}
        return manager_map[choice]

    def _handle_uv_installation(self) -> str:
        """处理uv的安装"""
        print()
        print("🔧 uv还没安装，安装很简单：")
        print("只需要运行: pip install uv")
        print()
        if confirm("现在就安装uv？", default=True):
            try:
                import subprocess
                import sys
                print("🔄 正在安装uv...")
                subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
                print("✅ uv安装成功！")
                return "uv"
            except Exception as e:
                print(f"❌ uv安装失败了: {e}")
                print("没关系，我们可以用Python自带的venv")
                return "venv"
        return "uv"

    def _handle_conda_check(self, selected_manager: str) -> str:
        """处理conda检查"""
        if selected_manager != "conda":
            return selected_manager

        print()
        print("⚠️  没检测到conda")
        print("你需要先安装Miniconda或Anaconda")
        print("可以访问: https://docs.conda.io/en/latest/miniconda.html")
        print()
        if not confirm("还是想用conda？(需要你自己先安装)", default=False):
            # 重新选择
            return self.decide_virtual_environment()[1]
        return selected_manager

    def decide_virtual_environment(self) -> Tuple[bool, str]:
        self._show_virtual_env_explanation()

        use_venv = confirm("要不要用虚拟环境？(推荐用)", default=True)

        if not use_venv:
            if self._confirm_skip_virtual_env():
                print()
                print("✅ 直接安装在系统Python环境中")
                return False, "none"

        available_managers = self._get_available_managers()
        selected_manager = self._select_environment_manager(available_managers)

        # 如果用户选了uv但没安装
        if selected_manager == "uv" and not check_command_exists("uv"):
            selected_manager = self._handle_uv_installation()

        # 如果用户选了conda但没安装
        if selected_manager == "conda" and not check_command_exists("conda"):
            selected_manager = self._handle_conda_check(selected_manager)

        print()
        print(f"✅ 已经选择了: {selected_manager}")
        return True, selected_manager

    def decide_database(self) -> Dict[str, str]:
        print("🗄️  数据库配置:")
        print()
        print("📖 什么是数据库？")
        print("   数据库是用来存储舆情分析数据的仓库，包括抓取的社交媒体内容、")
        print("   分析结果、用户历史记录等。")
        print()
        print("BettaFish 支持以下数据库:")
        print("1. PostgreSQL (推荐) - 性能更好，功能更强大")
        print("   ✅ 优点: 性能优秀，支持复杂查询，数据稳定可靠")
        print("   ✅ 适合: 生产环境，大量数据处理")
        print("   💡 端口: 5432")
        print()
        print("2. MySQL - 兼容性好，使用广泛")
        print("   ✅ 优点: 使用广泛，文档丰富，易于维护")
        print("   ✅ 适合: 已有MySQL环境，对兼容性要求高")
        print("   💡 端口: 3306")
        print()

        choices = ["1", "2"]
        db_map = {
            "1": "postgresql",
            "2": "mysql"
        }

        choice = get_user_input("选择数据库类型", default="1", choices=choices)
        db_type = db_map[choice]

        config = {"db_type": db_type}

        print(f"\n请输入 {db_type.upper()} 数据库连接信息:")
        config["host"] = get_user_input("数据库主机地址", default="localhost")
        config["port"] = get_user_input("数据库端口", default="5432" if db_type == "postgresql" else "3306")
        config["username"] = get_user_input("数据库用户名", default="bettafish")
        config["password"] = get_user_input("数据库密码", default="bettafish")
        config["database"] = get_user_input("数据库名称", default="bettafish")

        # 询问是否自动创建数据库
        if db_type == "postgresql":
            auto_create = confirm("是否自动创建数据库和用户？", default=True)
            config["auto_create"] = auto_create

        return config

    def decide_llm_config(self) -> Dict[str, str]:
        print("🤖 大语言模型配置:")
        print()
        print("BettaFish 使用多个AI Agent，需要配置相应的LLM API:")
        print()

        llm_providers = [
            {
                "name": "推荐方案",
                "description": "按官方推荐配置各服务",
                "providers": [
                    {"agent": "Insight", "llm": "Kimi-k2", "url": "https://platform.moonshot.cn/"},
                    {"agent": "Media", "llm": "Gemini-2.5-pro", "url": "https://aihubmix.com/?aff=8Ds9"},
                    {"agent": "Query", "llm": "DeepSeek", "url": "https://platform.deepseek.com/"},
                    {"agent": "Report", "llm": "Gemini-2.5-pro", "url": "https://aihubmix.com/?aff=8Ds9"}
                ]
            },
            {
                "name": "自定义方案",
                "description": "手动配置每个Agent的LLM",
                "providers": []
            }
        ]

        print("1. 推荐方案 - 按照项目推荐的最佳配置")
        print("   • Insight Agent: Kimi-k2 (推理能力强)")
        print("   • Media Agent: Gemini-2.5-pro (多模态能力强)")
        print("   • Query Agent: DeepSeek (搜索能力强)")
        print("   • Report Agent: Gemini-2.5-pro (生成能力强)")
        print()
        print("2. 自定义方案 - 根据您的需求自定义配置")
        print("   • 支持任何OpenAI兼容的API")
        print("   • 可以为不同Agent选择不同模型")
        print()
        print("🌐 网络API服务:")
        print("   • API地址格式: https://api.provider.com/v1 (注意要以/v1结尾)")
        print("   • 需要申请API密钥")
        print("   • 例: https://api.openai.com/v1")
        print()
        print("🏠 本地模型部署:")
        print("   • API地址格式: http://localhost:端口/v1")
        print("   • API密钥: 可填写任意字符串如'local'")
        print("   • 支持Ollama、LM Studio等本地部署方案")
        print()

        use_recommended = get_user_input("选择配置方案", default="1", choices=["1", "2"]) == "1"

        if use_recommended:
            print("\n📝 推荐方案配置说明:")
            print("请访问相应官网申请API密钥:")
            for provider in llm_providers[0]["providers"]:
                print(f"  • {provider['agent']} Agent: {provider['llm']} - {provider['url']}")

            proceed = confirm("是否使用推荐配置？您可以稍后在.env文件中修改", default=True)
            if not proceed:
                return self._custom_llm_config()

            return {"use_recommended": True}
        else:
            return self._custom_llm_config()

    def _custom_llm_config(self) -> Dict[str, str]:
        """自定义LLM配置"""
        print("\n⚙️  自定义LLM配置:")
        print("请为所有必需组件配置API信息 (直接回车跳过该组件):")
        print("⚠️  注意: 所有组件都是系统正常运行所必需的")
        print()

        # 所有必需的LLM组件
        components = [
            ("insight", "深度分析Agent"),
            ("media", "多模态Agent"),
            ("query", "搜索Agent"),
            ("report", "报告生成Agent"),
            ("mindspider", "爬虫系统"),
            ("forum_host", "论坛主持人"),
            ("keyword_optimizer", "关键词优化器")
        ]

        config = {"use_recommended": False}

        for agent_key, agent_desc in components:
            print(f"🔧 {agent_desc} 配置:")
            api_key = get_user_input("  API 密钥 (本地模型可填'local')", default="")
            if api_key:
                config[f"{agent_key}_api_key"] = api_key
                config[f"{agent_key}_base_url"] = get_user_input("  API 地址", default="")
                config[f"{agent_key}_model_name"] = get_user_input("  模型名称", default="")
            else:
                print(f"  ⏭️  跳过 {agent_desc}")
            print()

        # 检查配置完成度
        configured_count = len([k for k in config.keys() if 'api_key' in k])
        total_count = len(components)

        if configured_count < total_count:
            print(f"⚠️  警告: 只配置了 {configured_count}/{total_count} 个组件，系统功能可能不完整")
            print("💡 建议: 使用推荐配置确保所有组件正常工作")
        else:
            print(f"✅ 已配置所有 {configured_count} 个组件")

        return config

    def decide_optional_components(self, install_mode: str) -> Dict[str, bool]:
        print("🎯 可选组件:")
        print()

        components = {
            "crawler": {
                "name": "爬虫系统 (MindSpider)",
                "description": "用于抓取社交媒体数据，需要较多资源",
                "default": install_mode != "quick"
            },
            "ml_models": {
                "name": "机器学习情感分析模型",
                "description": "本地情感分析模型，需要下载模型文件 (约1-2GB)",
                "default": install_mode != "quick"
            },
            "dev_tools": {
                "name": "开发工具",
                "description": "代码格式化、测试等开发工具",
                "default": install_mode == "development"
            }
        }

        selected = {}
        for key, comp in components.items():
            print(f"📦 {comp['name']}")
            print(f"   {comp['description']}")
            install_comp = confirm(f"是否安装 {comp['name']}?", default=comp["default"])
            selected[key] = install_comp
            print()

        return selected

    def get_installation_plan(self) -> Dict:
        self.show_welcome()

        plan = {
            "install_mode": self.decide_install_mode(),
            "virtual_env": {},
            "database": {},
            "llm_config": {},
            "components": {}
        }

        # 虚拟环境配置
        use_venv, env_manager = self.decide_virtual_environment()
        plan["virtual_env"] = {
            "use": use_venv,
            "manager": env_manager
        }

        # 数据库配置
        plan["database"] = self.decide_database()

        # LLM配置
        plan["llm_config"] = self.decide_llm_config()

        # 可选组件
        plan["components"] = self.decide_optional_components(plan["install_mode"])

        return plan

    def show_installation_summary(self, plan: Dict) -> bool:
        print("📋 安装计划摘要:")
        print("=" * 50)

        print(f"🚀 安装模式: {plan['install_mode']}")

        venv_info = plan['virtual_env']
        if venv_info['use']:
            print(f"🐍 虚拟环境: 使用 {venv_info['manager']}")
        else:
            print("🐍 虚拟环境: 不使用")

        db_info = plan['database']
        print(f"🗄️  数据库: {db_info['db_type'].upper()}")

        if plan['llm_config'].get('use_recommended'):
            print("🤖 LLM配置: 使用推荐配置")
        else:
            configured_agents = [k.replace('_api_key', '') for k in plan['llm_config'].keys() if 'api_key' in k]
            agents_str = ', '.join(configured_agents)
            print(f"🤖 LLM配置: 自定义 ({agents_str})")

        components = plan['components']
        installed_comps = [k for k, v in components.items() if v]
        print(f"📦 组件: {', '.join(installed_comps) if installed_comps else '基础组件'}")

        print("=" * 50)

        return confirm("确认开始安装？", default=True)