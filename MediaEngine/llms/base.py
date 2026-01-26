"""
Unified OpenAI-compatible LLM client for the Media Engine, with retry support.

This module now uses the unified LLM client from utils/llm/ while preserving
engine-specific behavior (time prefix, retry logic).
"""

import os
import sys
from datetime import datetime
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
        def decorator(func):
            return func
        return decorator

    LLM_RETRY_CONFIG = None

# Import unified LLM client factory
from utils.llm import create_llm_client, BaseLLMClient


class LLMClient:
    """
    Wrapper around the unified LLM client with Media Engine-specific behavior.

    Preserves backward compatibility while using utils/llm/ unified client.
    Supports OpenAI, Azure, Anthropic Claude, and OpenRouter.
    """

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        if not api_key:
            raise ValueError("Media Engine LLM API key is required.")
        if not model_name:
            raise ValueError("Media Engine model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("MEDIA_ENGINE_REQUEST_TIMEOUT") or "1800"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 1800.0

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

    def _add_time_prefix(self, user_prompt: str) -> str:
        """Add current time prefix to user prompt (Media Engine specific)."""
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        if user_prompt:
            return f"{time_prefix}\n{user_prompt}"
        return time_prefix

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Invoke LLM with time prefix prepended to user prompt.

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.
        """
        # Add time prefix (Media Engine specific behavior)
        user_prompt_with_time = self._add_time_prefix(user_prompt)

        # Delegate to unified client
        return self._unified_client.invoke(system_prompt, user_prompt_with_time, **kwargs)

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式调用LLM，逐步返回响应内容

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）

        Yields:
            响应文本块（str）
        """
        # Add time prefix (Media Engine specific behavior)
        user_prompt_with_time = self._add_time_prefix(user_prompt)

        # Delegate to unified client
        yield from self._unified_client.stream_invoke(system_prompt, user_prompt_with_time, **kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        流式调用LLM并安全地拼接为完整字符串（避免UTF-8多字节字符截断）

        Uses unified client internally, supports OpenAI/Azure/Anthropic/OpenRouter.

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）

        Returns:
            完整的响应字符串
        """
        # Add time prefix (Media Engine specific behavior)
        user_prompt_with_time = self._add_time_prefix(user_prompt)

        # Delegate to unified client
        return self._unified_client.stream_invoke_to_string(system_prompt, user_prompt_with_time, **kwargs)

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information from the unified client."""
        return self._unified_client.get_model_info()
