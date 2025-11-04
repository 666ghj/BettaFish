"""
环境变量加载工具
用于加载 .env 文件中的配置
"""

import os
from pathlib import Path


def load_env_file(env_file: str = ".env"):
    """
    从 .env 文件加载环境变量

    Args:
        env_file: .env 文件路径，默认为项目根目录的 .env

    Returns:
        bool: 是否成功加载
    """
    # 获取项目根目录
    project_root = Path(__file__).parent
    env_path = project_root / env_file

    if not env_path.exists():
        print(f"⚠️  警告: 未找到 {env_file} 文件")
        print(f"   请复制 .env.example 为 .env 并填入配置信息")
        print(f"   命令: cp .env.example .env")
        return False

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        loaded_count = 0
        for line in lines:
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue

            # 解析 KEY=VALUE 格式
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # 只有当环境变量不存在时才设置（优先使用系统环境变量）
                if key not in os.environ:
                    os.environ[key] = value
                    loaded_count += 1

        print(f"✅ 成功从 {env_file} 加载了 {loaded_count} 个环境变量")
        return True

    except Exception as e:
        print(f"❌ 加载 {env_file} 时出错: {e}")
        return False


def get_env(key: str, default: str = None, required: bool = False) -> str:
    """
    获取环境变量

    Args:
        key: 环境变量名称
        default: 默认值
        required: 是否必需，如果为True且变量不存在则抛出异常

    Returns:
        str: 环境变量值

    Raises:
        ValueError: 当 required=True 且变量不存在时
    """
    value = os.getenv(key, default)

    if required and value is None:
        raise ValueError(f"必需的环境变量 {key} 未设置！请检查 .env 文件")

    return value


def validate_env_config():
    """
    验证必需的环境变量是否已设置

    Returns:
        bool: 是否所有必需的环境变量都已设置
    """
    required_vars = [
        'DB_HOST',
        'DB_USER',
        'DB_PASSWORD',
        'DB_NAME',
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing_vars)}")
        print(f"   请在 .env 文件中设置这些变量")
        return False

    print("✅ 所有必需的环境变量已设置")
    return True


def print_env_config(show_sensitive: bool = False):
    """
    打印当前环境变量配置（用于调试）

    Args:
        show_sensitive: 是否显示敏感信息（如密码、API密钥）
    """
    print("\n" + "="*50)
    print("当前环境变量配置")
    print("="*50)

    # 数据库配置
    print("\n[数据库配置]")
    print(f"  DB_HOST: {os.getenv('DB_HOST', '未设置')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', '3306')}")
    print(f"  DB_USER: {os.getenv('DB_USER', '未设置')}")
    print(f"  DB_PASSWORD: {'***' if not show_sensitive else os.getenv('DB_PASSWORD', '未设置')}")
    print(f"  DB_NAME: {os.getenv('DB_NAME', '未设置')}")
    print(f"  DB_CHARSET: {os.getenv('DB_CHARSET', 'utf8mb4')}")
    print(f"  SENSOR_TABLE_NAME: {os.getenv('SENSOR_TABLE_NAME', 'sensor_data')}")

    # LLM配置
    print("\n[LLM配置]")
    print(f"  INSIGHT_ENGINE_API_KEY: {'***' if not show_sensitive else os.getenv('INSIGHT_ENGINE_API_KEY', '未设置')}")
    print(f"  INSIGHT_ENGINE_BASE_URL: {os.getenv('INSIGHT_ENGINE_BASE_URL', '未设置')}")
    print(f"  INSIGHT_ENGINE_MODEL_NAME: {os.getenv('INSIGHT_ENGINE_MODEL_NAME', '未设置')}")

    # 传感器配置
    print("\n[传感器配置]")
    print(f"  DEFAULT_QUERY_LIMIT: {os.getenv('DEFAULT_QUERY_LIMIT', '1000')}")
    print(f"  DEFAULT_STATISTICAL_HOURS: {os.getenv('DEFAULT_STATISTICAL_HOURS', '24')}")
    print(f"  ANOMALY_THRESHOLD_STD_DEV: {os.getenv('ANOMALY_THRESHOLD_STD_DEV', '2.0')}")

    # 系统配置
    print("\n[系统配置]")
    print(f"  OUTPUT_DIR: {os.getenv('OUTPUT_DIR', './reports')}")
    print(f"  LOG_DIR: {os.getenv('LOG_DIR', './logs')}")
    print(f"  FLASK_HOST: {os.getenv('FLASK_HOST', '0.0.0.0')}")
    print(f"  FLASK_PORT: {os.getenv('FLASK_PORT', '5000')}")

    print("\n" + "="*50 + "\n")


# 自动加载 .env 文件（当模块被导入时）
if __name__ != "__main__":
    load_env_file()
