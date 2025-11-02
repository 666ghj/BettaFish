"""
Configuration management module for the Query Engine.
"""

import os
from dataclasses import dataclass
from typing import Optional


def _get_value(source, key: str, default=None, *fallback_keys: str):
    candidates = (key,) + fallback_keys
    value = None
    for candidate in candidates:
        if isinstance(source, dict):
            value = source.get(candidate)
        else:
            value = getattr(source, candidate, None)
        if value not in (None, ""):
            break
    if value in (None, ""):
        for candidate in candidates:
            env_val = os.getenv(candidate)
            if env_val not in (None, ""):
                value = env_val
                break
    return value if value not in (None, "") else default


@dataclass
class Config:
    """Query Engine configuration."""

    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_name: Optional[str] = None
    llm_provider: Optional[str] = None  # compatibility

    tavily_api_key: Optional[str] = None

    search_timeout: int = 240
    max_content_length: int = 20000
    max_reflections: int = 2
    max_paragraphs: int = 5
    max_search_results: int = 20

    output_dir: str = "reports"
    save_intermediate_states: bool = True

    def __post_init__(self):
        if not self.llm_provider and self.llm_model_name:
            self.llm_provider = self.llm_model_name

    def validate(self) -> bool:
        if not self.llm_model_name:
            print("错误: Query Engine 模型名称未设置 (QUERY_ENGINE_MODEL_NAME)。")
            return False
        # Tavily API Key 现在可选（如果使用本地搜索）
        if not self.tavily_api_key:
            print("提示: Tavily API Key 未设置，将使用本地搜索服务")
        return True

    @classmethod
    def from_file(cls, config_file: str) -> "Config":
        if config_file.endswith(".py"):
            import importlib.util

            spec = importlib.util.spec_from_file_location("config", config_file)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            return cls(
                llm_api_key=_get_value(config_module, "QUERY_ENGINE_API_KEY"),
                llm_base_url=_get_value(config_module, "QUERY_ENGINE_BASE_URL"),
                llm_model_name=_get_value(config_module, "QUERY_ENGINE_MODEL_NAME"),
                tavily_api_key=_get_value(config_module, "TAVILY_API_KEY"),
                search_timeout=int(_get_value(config_module, "SEARCH_TIMEOUT", 240)),
                max_content_length=int(_get_value(config_module, "SEARCH_CONTENT_MAX_LENGTH", 20000)),
                max_reflections=int(_get_value(config_module, "MAX_REFLECTIONS", 2)),
                max_paragraphs=int(_get_value(config_module, "MAX_PARAGRAPHS", 5)),
                max_search_results=int(_get_value(config_module, "MAX_SEARCH_RESULTS", 20)),
                output_dir=_get_value(config_module, "OUTPUT_DIR", "reports"),
                save_intermediate_states=str(
                    _get_value(config_module, "SAVE_INTERMEDIATE_STATES", "true")
                ).lower()
                in ("true", "1", "yes"),
            )

        config_dict = {}
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config_dict[key.strip()] = value.strip()

        return cls(
            llm_api_key=_get_value(config_dict, "QUERY_ENGINE_API_KEY"),
            llm_base_url=_get_value(config_dict, "QUERY_ENGINE_BASE_URL"),
            llm_model_name=_get_value(config_dict, "QUERY_ENGINE_MODEL_NAME"),
            tavily_api_key=_get_value(config_dict, "TAVILY_API_KEY"),
            search_timeout=int(_get_value(config_dict, "SEARCH_TIMEOUT", 240)),
            max_content_length=int(_get_value(config_dict, "SEARCH_CONTENT_MAX_LENGTH", 20000)),
            max_reflections=int(_get_value(config_dict, "MAX_REFLECTIONS", 2)),
            max_paragraphs=int(_get_value(config_dict, "MAX_PARAGRAPHS", 5)),
            max_search_results=int(_get_value(config_dict, "MAX_SEARCH_RESULTS", 20)),
            output_dir=_get_value(config_dict, "OUTPUT_DIR", "reports"),
            save_intermediate_states=str(
                _get_value(config_dict, "SAVE_INTERMEDIATE_STATES", "true")
            ).lower()
            in ("true", "1", "yes"),
        )


def load_config(config_file: Optional[str] = None) -> Config:
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
    print("\n=== Query Engine 配置 ===")
    print(f"LLM 模型: {config.llm_model_name}")
    print(f"LLM Base URL: {config.llm_base_url or '(默认)'}")
    print(f"Tavily API Key: {'已配置' if config.tavily_api_key else '未配置'}")
    print(f"搜索超时: {config.search_timeout} 秒")
    print(f"最长内容长度: {config.max_content_length}")
    print(f"最大反思次数: {config.max_reflections}")
    print(f"最大段落数: {config.max_paragraphs}")
    print(f"最大搜索结果数: {config.max_search_results}")
    print(f"输出目录: {config.output_dir}")
    print(f"保存中间状态: {config.save_intermediate_states}")
    print(f"LLM API Key: {'已配置' if config.llm_api_key else '未配置'}")
    print("========================\n")
