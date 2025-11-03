"""
配置检查脚本
快速诊断 BettaFish 项目配置是否正确
"""

import os
import sys
from pathlib import Path

def check_config():
    """检查配置文件"""
    print("=" * 60)
    print("BettaFish 配置检查工具")
    print("=" * 60)
    print()
    
    # 检查当前目录
    current_dir = Path.cwd()
    print(f"当前目录: {current_dir}")
    
    # 检查是否在 NextJSAdapter 目录
    if current_dir.name == "NextJSAdapter":
        print("✓ 在 NextJSAdapter 目录")
        project_root = current_dir.parent
    else:
        project_root = current_dir
    
    print(f"项目根目录: {project_root}")
    print()
    
    # 检查配置文件
    print("检查配置文件:")
    config_files = ["config.py", "config.env", ".env"]
    found_config = None
    
    for config_file in config_files:
        config_path = project_root / config_file
        if config_path.exists():
            print(f"  ✓ {config_file} 存在")
            found_config = config_path
            
            # 检查文件内容
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 检查关键配置项
                required_keys = [
                    'QUERY_ENGINE_API_KEY',
                    'QUERY_ENGINE_MODEL_NAME',
                    'TAVILY_API_KEY'
                ]
                
                print(f"\n  检查 {config_file} 中的必需配置:")
                for key in required_keys:
                    if key in content:
                        # 检查是否有值
                        lines = [line for line in content.split('\n') if key in line and not line.strip().startswith('#')]
                        if lines:
                            # 简单检查是否赋值
                            has_value = any('=' in line and line.split('=')[1].strip() not in ['', '""', "''"] for line in lines)
                            if has_value:
                                print(f"    ✓ {key}: 已配置")
                            else:
                                print(f"    ⚠ {key}: 已定义但可能为空")
                        else:
                            print(f"    ✗ {key}: 未找到")
                    else:
                        print(f"    ✗ {key}: 未找到")
                        
            except Exception as e:
                print(f"  ⚠ 无法读取配置文件: {e}")
        else:
            print(f"  ✗ {config_file} 不存在")
    
    print()
    
    if not found_config:
        print("=" * 60)
        print("错误: 未找到配置文件!")
        print("=" * 60)
        print()
        print("请在 BettaFish 根目录创建 config.py，参考以下模板:")
        print()
        print("-" * 60)
        print("""# BettaFish 配置文件

# QueryEngine LLM 配置
QUERY_ENGINE_API_KEY = "your-api-key-here"
QUERY_ENGINE_BASE_URL = "https://api.openai.com/v1"
QUERY_ENGINE_MODEL_NAME = "gpt-4"

# Tavily 搜索 API
TAVILY_API_KEY = "your-tavily-api-key-here"

# ReportEngine LLM 配置
REPORT_ENGINE_API_KEY = "your-api-key-here"
REPORT_ENGINE_BASE_URL = "https://api.openai.com/v1"
REPORT_ENGINE_MODEL_NAME = "gpt-4"

# 可选配置
SEARCH_TIMEOUT = 240
MAX_SEARCH_RESULTS = 20
""")
        print("-" * 60)
        print()
        print("提示:")
        print("1. 复制上面的模板到 config.py")
        print("2. 替换 API Key 为您的实际密钥")
        print("3. 保存文件")
        print("4. 重新运行服务")
        return False
    
    print("=" * 60)
    print("配置检查完成")
    print("=" * 60)
    print()
    
    if found_config:
        print(f"✓ 找到配置文件: {found_config.name}")
        print("提示: 请确保所有必需的 API Key 都已正确配置")
        return True
    
    return False


if __name__ == '__main__':
    try:
        success = check_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
