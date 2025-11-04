"""
Configuration management module for the Insight Engine.
Handles environment variables and config file parameters.
"""

import os
from dataclasses import dataclass
from typing import Optional


def _get_value(source, key: str, default=None):
    """
    Helper to fetch a configuration value with environment fallback.
    """
    value = None
    if isinstance(source, dict):
        value = source.get(key)
    else:
        value = getattr(source, key, None)

    if value is None:
        value = os.getenv(key, default)
    return value if value not in ("", None) else default


@dataclass
class Config:
    """Insight Engine configuration."""

    # LLM configuration
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_name: Optional[str] = None
    llm_provider: Optional[str] = None  # kept for backward compatibility

    # Database configuration
    db_host: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_name: Optional[str] = None
    db_port: int = 3306
    db_charset: str = "utf8mb4"

    # Sensor data configuration
    sensor_table_name: str = "sensor_data"

    # Model behaviour configuration
    max_reflections: int = 3
    max_paragraphs: int = 6
    search_timeout: int = 240
    max_content_length: int = 500000

    # Search result limits
    default_search_hot_content_limit: int = 100
    default_search_topic_globally_limit_per_table: int = 50
    default_search_topic_by_date_limit_per_table: int = 100
    default_get_comments_for_topic_limit: int = 500
    default_search_topic_on_platform_limit: int = 200
    max_search_results_for_llm: int = 0
    max_high_confidence_sentiment_results: int = 0

    # Output configuration
    output_dir: str = "reports"
    save_intermediate_states: bool = True

    def __post_init__(self):
        if not self.llm_provider and self.llm_model_name:
            # Provider is no longer used, but keep the attribute for compatibility.
            self.llm_provider = self.llm_model_name

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.llm_api_key:
            print("错误: Insight Engine LLM API Key 未设置 (INSIGHT_ENGINE_API_KEY)。")
            return False

        if not self.llm_model_name:
            print("错误: Insight Engine 模型名称未设置 (INSIGHT_ENGINE_MODEL_NAME)。")
            return False

        if not all([self.db_host, self.db_user, self.db_password, self.db_name]):
            print("错误: 数据库连接信息不完整，请检查 config.py 中的 DB_* 配置。")
            return False

        return True

    @classmethod
    def from_file(cls, config_file: str) -> "Config":
        """Create configuration from file."""
        if config_file.endswith(".py"):
            import importlib.util

            spec = importlib.util.spec_from_file_location("config", config_file)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            return cls(
                llm_api_key=_get_value(config_module, "INSIGHT_ENGINE_API_KEY"),
                llm_base_url=_get_value(config_module, "INSIGHT_ENGINE_BASE_URL"),
                llm_model_name=_get_value(config_module, "INSIGHT_ENGINE_MODEL_NAME"),
                db_host=_get_value(config_module, "DB_HOST"),
                db_user=_get_value(config_module, "DB_USER"),
                db_password=_get_value(config_module, "DB_PASSWORD"),
                db_name=_get_value(config_module, "DB_NAME"),
                db_port=int(_get_value(config_module, "DB_PORT", 3306)),
                db_charset=_get_value(config_module, "DB_CHARSET", "utf8mb4"),
                sensor_table_name=_get_value(config_module, "SENSOR_TABLE_NAME", "sensor_data"),
                max_reflections=int(_get_value(config_module, "MAX_REFLECTIONS", 3)),
                max_paragraphs=int(_get_value(config_module, "MAX_PARAGRAPHS", 6)),
                search_timeout=int(_get_value(config_module, "SEARCH_TIMEOUT", 240)),
                max_content_length=int(_get_value(config_module, "SEARCH_CONTENT_MAX_LENGTH", 500000)),
                default_search_hot_content_limit=int(
                    _get_value(config_module, "DEFAULT_SEARCH_HOT_CONTENT_LIMIT", 100)
                ),
                default_search_topic_globally_limit_per_table=int(
                    _get_value(config_module, "DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE", 50)
                ),
                default_search_topic_by_date_limit_per_table=int(
                    _get_value(config_module, "DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE", 100)
                ),
                default_get_comments_for_topic_limit=int(
                    _get_value(config_module, "DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT", 500)
                ),
                default_search_topic_on_platform_limit=int(
                    _get_value(config_module, "DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT", 200)
                ),
                max_search_results_for_llm=int(_get_value(config_module, "MAX_SEARCH_RESULTS_FOR_LLM", 0)),
                max_high_confidence_sentiment_results=int(
                    _get_value(config_module, "MAX_HIGH_CONFIDENCE_SENTIMENT_RESULTS", 0)
                ),
                output_dir=_get_value(config_module, "OUTPUT_DIR", "reports"),
                save_intermediate_states=str(
                    _get_value(config_module, "SAVE_INTERMEDIATE_STATES", "true")
                ).lower()
                in ("true", "1", "yes"),
            )

        # .env style configuration
        config_dict = {}
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config_dict[key.strip()] = value.strip()

        return cls(
            llm_api_key=_get_value(config_dict, "INSIGHT_ENGINE_API_KEY"),
            llm_base_url=_get_value(config_dict, "INSIGHT_ENGINE_BASE_URL"),
            llm_model_name=_get_value(config_dict, "INSIGHT_ENGINE_MODEL_NAME"),
            db_host=_get_value(config_dict, "DB_HOST"),
            db_user=_get_value(config_dict, "DB_USER"),
            db_password=_get_value(config_dict, "DB_PASSWORD"),
            db_name=_get_value(config_dict, "DB_NAME"),
            db_port=int(_get_value(config_dict, "DB_PORT", 3306)),
            db_charset=_get_value(config_dict, "DB_CHARSET", "utf8mb4"),
            sensor_table_name=_get_value(config_dict, "SENSOR_TABLE_NAME", "sensor_data"),
            max_reflections=int(_get_value(config_dict, "MAX_REFLECTIONS", 3)),
            max_paragraphs=int(_get_value(config_dict, "MAX_PARAGRAPHS", 6)),
            search_timeout=int(_get_value(config_dict, "SEARCH_TIMEOUT", 240)),
            max_content_length=int(_get_value(config_dict, "SEARCH_CONTENT_MAX_LENGTH", 500000)),
            default_search_hot_content_limit=int(
                _get_value(config_dict, "DEFAULT_SEARCH_HOT_CONTENT_LIMIT", 100)
            ),
            default_search_topic_globally_limit_per_table=int(
                _get_value(config_dict, "DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE", 50)
            ),
            default_search_topic_by_date_limit_per_table=int(
                _get_value(config_dict, "DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE", 100)
            ),
            default_get_comments_for_topic_limit=int(
                _get_value(config_dict, "DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT", 500)
            ),
            default_search_topic_on_platform_limit=int(
                _get_value(config_dict, "DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT", 200)
            ),
            max_search_results_for_llm=int(_get_value(config_dict, "MAX_SEARCH_RESULTS_FOR_LLM", 0)),
            max_high_confidence_sentiment_results=int(
                _get_value(config_dict, "MAX_HIGH_CONFIDENCE_SENTIMENT_RESULTS", 0)
            ),
            output_dir=_get_value(config_dict, "OUTPUT_DIR", "reports"),
            save_intermediate_states=str(
                _get_value(config_dict, "SAVE_INTERMEDIATE_STATES", "true")
            ).lower()
            in ("true", "1", "yes"),
        )


def load_config(config_file: Optional[str] = None) -> Config:
    """
    Load configuration.
    """
    if config_file:
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        file_to_load = config_file
    else:
        for candidate in ("config.py", "config.env", ".env"):
            if os.path.exists(candidate):
                file_to_load = candidate
                print(f"已找到配置文件: {candidate}")
                break
        else:
            raise FileNotFoundError("未找到配置文件，请创建 config.py。")

    config = Config.from_file(file_to_load)

    if not config.validate():
        raise ValueError("配置校验失败，请检查 config.py 中的相关配置。")

    return config


def print_config(config: Config):
    """Print configuration (sensitive values masked)."""
    print("\n=== Insight Engine 配置 ===")
    print(f"LLM 模型: {config.llm_model_name}")
    print(f"LLM Base URL: {config.llm_base_url or '(默认)'}")
    print(f"搜索超时: {config.search_timeout} 秒")
    print(f"最长内容长度: {config.max_content_length}")
    print(f"最大反思次数: {config.max_reflections}")
    print(f"最大段落数: {config.max_paragraphs}")
    print(f"输出目录: {config.output_dir}")
    print(f"保存中间状态: {config.save_intermediate_states}")
    print(f"LLM API Key: {'已配置' if config.llm_api_key else '未配置'}")
    print(f"数据库连接: {'已配置' if all([config.db_host, config.db_user, config.db_password, config.db_name]) else '未配置'}")
    print("========================\n")
