#!/usr/bin/env python3
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_imports():
    print("🔍 检查Python包导入...")

    required_packages = [
        'flask', 'streamlit', 'openai', 'pandas', 'numpy',
        'requests', 'sqlalchemy', 'pydantic', 'loguru'
    ]

    failed_imports = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            failed_imports.append(package)

    if failed_imports:
        print(f"\n❌ 以下包导入失败: {', '.join(failed_imports)}")
        return False

    print("✅ 所有必需包导入成功")
    return True


def check_project_structure():
    print("\n🔍 检查项目结构...")

    project_root = Path("../")
    required_dirs = [
        "QueryEngine", "MediaEngine", "InsightEngine",
        "ReportEngine", "ForumEngine", "MindSpider"
    ]

    missing_dirs = []

    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            print(f"  ✅ {dir_name}")
        else:
            print(f"  ❌ {dir_name}")
            missing_dirs.append(dir_name)

    if missing_dirs:
        print(f"\n❌ 以下目录缺失: {', '.join(missing_dirs)}")
        return False

    print("✅ 项目结构完整")
    return True


def check_config_file():
    print("\n🔍 检查配置文件...")

    env_path = Path("../.env")
    if env_path.exists():
        print("  ✅ .env 文件存在")

        # 检查关键配置项
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()

        key_configs = ['DB_DIALECT', 'HOST', 'PORT']
        missing_configs = []

        for config in key_configs:
            if config not in content:
                missing_configs.append(config)

        if missing_configs:
            print(f"  ⚠️  以下配置项缺失: {', '.join(missing_configs)}")
        else:
            print("  ✅ 基础配置项完整")

        return True
    else:
        print("  ❌ .env 文件不存在")
        return False


def check_playwright():
    print("\n🔍 检查Playwright...")

    try:
        from playwright.sync_api import sync_playwright

        # 尝试启动浏览器（但不实际打开）
        with sync_playwright():
            print("  ✅ Playwright 可用")
            return True
    except ImportError:
        print("  ❌ Playwright 未安装")
        return False
    except Exception as e:
        print(f"  ⚠️  Playwright 安装可能有问题: {e}")
        return False


def test_basic_imports():
    print("\n🔍 测试项目模块导入...")

    project_root = Path("../")
    sys.path.insert(0, str(project_root))

    test_modules = ['config']
    failed_modules = []

    for module in test_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            failed_modules.append(module)
        except Exception as e:
            print(f"  ⚠️  {module}: {e}")

    return len(failed_modules) == 0


def main():
    print("🐟 BettaFish 安装验证")
    print("=" * 40)

    checks = [
        ("Python包导入", check_python_imports),
        ("项目结构", check_project_structure),
        ("配置文件", check_config_file),
        ("Playwright", check_playwright),
        ("项目模块", test_basic_imports)
    ]

    results = []

    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} 检查失败: {e}")
            results.append((name, False))

    print("\n" + "=" * 40)
    print("📊 验证结果摘要:")

    passed = 0
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1

    print(f"\n总计: {passed}/{total} 项检查通过")

    if passed == total:
        print("🎉 安装验证完全通过！BettaFish 已准备就绪。")
        print("\n🚀 下一步:")
        print("  1. 编辑 .env 文件，填入您的API密钥")
        print("  2. 运行: python app.py")
        print("  3. 访问: http://localhost:5000")
        return 0
    else:
        print("⚠️  部分检查未通过，请检查上述问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())