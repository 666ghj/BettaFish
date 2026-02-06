"""
Insight Engine LLM 客户端

委托 utils/llm_provider.py 统一模块，自动支持 OpenAI / Anthropic（含 OAuth）双后端。
保持与原有 ``LLMClient(api_key, model_name, base_url)`` 构造签名完全兼容。
"""

import os
import sys

# 确保项目根目录在 sys.path 中，以便 ``from utils.llm_provider`` 可用
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.llm_provider import LLMClient as _BaseLLMClient  # noqa: E402


class LLMClient(_BaseLLMClient):
    """Insight Engine 专用 LLM 客户端，继承统一客户端并预置引擎级默认值。"""

    def __init__(self, api_key: str, model_name: str, base_url=None, **kwargs):
        kwargs.setdefault("engine_name", "Insight Engine")
        kwargs.setdefault("timeout_env_prefix", "INSIGHT_ENGINE")
        kwargs.setdefault("default_timeout", 1800.0)
        kwargs.setdefault("prepend_time", True)
        super().__init__(api_key, model_name, base_url, **kwargs)
