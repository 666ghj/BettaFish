"""
Report Engine 默认的OpenAI兼容LLM客户端封装。

This module now uses the unified LLM client from utils/llm/ while preserving
engine-specific behavior (retry logic, no time prefix).

提供统一的非流式/流式调用、可选重试、字节安全拼接与模型元信息查询。
"""

import os
import sys
from typing import Any, Dict, Optional, Generator
from loguru import logger

# Add project root to path for unified LLM imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

utils_dir = os.path.join(project_root, "utils")
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

try:
    from retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    def with_retry(config=None):
        """简化版with_retry占位，实现与真实装饰器一致的调用签名"""
        def decorator(func):
            """直接返回原函数，确保无retry依赖时代码仍可运行"""
            return func
        return decorator

    LLM_RETRY_CONFIG = None

# Import unified LLM client factory
from utils.llm import create_llm_client, BaseLLMClient


class LLMClient:
    """
    针对OpenAI Chat Completion API的轻量封装，统一Report Engine调用入口。

    Preserves backward compatibility while using utils/llm/ unified client.
    Supports OpenAI, Azure, Anthropic Claude, and OpenRouter.
    """

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        """
        初始化LLM客户端并保存基础连接信息。

        Args:
            api_key: 用于鉴权的API Token
            model_name: 具体模型ID，用于定位供应商能力
            base_url: 自定义兼容接口地址，默认为OpenAI官方
        """
        if not api_key:
            raise ValueError("Report Engine LLM API key is required.")
        if not model_name:
            raise ValueError("Report Engine model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("REPORT_ENGINE_REQUEST_TIMEOUT") or "3000"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 3000.0

        # Use unified LLM client factory with auto-detection
        self._unified_client = create_llm_client(
            provider="auto",
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            timeout=self.timeout,
        )

        # Keep reference to underlying client for backward compatibility
        self.client = getattr(self._unified_client, 'client', None)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        以非流式方式调用LLM，并返回一次性完成的完整响应。

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.

        Args:
            system_prompt: 系统角色提示
            user_prompt: 用户高优先级指令
            **kwargs: 允许透传temperature/top_p等采样参数

        Returns:
            去除首尾空白后的LLM响应文本
        """
        # Delegate to unified client (no time prefix for ReportEngine)
        return self._unified_client.invoke(system_prompt, user_prompt, **kwargs)

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式调用LLM，逐步返回响应内容。

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.

        参数:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。
            **kwargs: 采样参数（temperature、top_p等）。

        产出:
            str: 每次yield一段delta文本，方便上层实时渲染。
        """
        # Delegate to unified client (no time prefix for ReportEngine)
        yield from self._unified_client.stream_invoke(system_prompt, user_prompt, **kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        流式调用LLM并安全地拼接为完整字符串（避免UTF-8多字节字符截断）。

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.

        参数:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。
            **kwargs: 采样或超时配置。

        返回:
            str: 将所有delta拼接后的完整响应。
        """
        # Delegate to unified client (no time prefix for ReportEngine)
        return self._unified_client.stream_invoke_to_string(system_prompt, user_prompt, **kwargs)

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        """兜底处理None/空白字符串，防止上层逻辑崩溃"""
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        """以字典形式返回当前客户端的模型/提供方/基础URL信息"""
        return self._unified_client.get_model_info()
