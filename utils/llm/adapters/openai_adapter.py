"""
OpenAI-compatible LLM adapter.

Supports:
- OpenAI (api.openai.com)
- DeepSeek (api.deepseek.com)
- Kimi/Moonshot (api.moonshot.cn)
- OpenRouter (openrouter.ai)
- Any OpenAI-compatible API
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from loguru import logger
from openai import OpenAI

# Import retry helper from project utils
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
utils_dir = os.path.join(project_root, "utils")
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

try:
    from retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    def with_retry(config=None):
        def decorator(func):
            return func
        return decorator
    LLM_RETRY_CONFIG = None

from ..base import BaseLLMClient


class OpenAIAdapter(BaseLLMClient):
    """
    Adapter for OpenAI and OpenAI-compatible APIs.

    Works with: OpenAI, DeepSeek, Kimi, OpenRouter, and any API that
    follows the OpenAI chat completion format.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the OpenAI adapter.

        Args:
            api_key: API key for authentication
            model_name: Model identifier (e.g., "gpt-4", "deepseek-chat")
            base_url: Optional custom API endpoint
            timeout: Request timeout in seconds (default: 1800)
        """
        if not api_key:
            raise ValueError("API key is required for OpenAI adapter")
        if not model_name:
            raise ValueError("Model name is required for OpenAI adapter")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = "openai"

        # Determine timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            timeout_env = os.getenv("LLM_REQUEST_TIMEOUT", "1800")
            try:
                self.timeout = float(timeout_env)
            except ValueError:
                self.timeout = 1800.0

        # Initialize OpenAI client
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "max_retries": 0,
        }
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)

    def _prepare_messages(
        self, system_prompt: str, user_prompt: str
    ) -> list:
        """Prepare messages with time prefix."""
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"

        if user_prompt:
            user_prompt = f"{time_prefix}\n{user_prompt}"
        else:
            user_prompt = time_prefix

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _filter_params(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter allowed parameters for the API call."""
        allowed_keys = {
            "temperature",
            "top_p",
            "presence_penalty",
            "frequency_penalty",
            "max_tokens",
        }
        return {
            key: value
            for key, value in kwargs.items()
            if key in allowed_keys and value is not None
        }

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Non-streaming call to the OpenAI API.

        Args:
            system_prompt: System instructions
            user_prompt: User input
            **kwargs: Additional parameters

        Returns:
            Model response as string
        """
        messages = self._prepare_messages(system_prompt, user_prompt)
        extra_params = self._filter_params(kwargs)
        timeout = kwargs.pop("timeout", self.timeout)

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            timeout=timeout,
            **extra_params,
        )

        if response.choices and response.choices[0].message:
            return self.validate_response(response.choices[0].message.content)
        return ""

    def stream_invoke(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """
        Streaming call to the OpenAI API.

        Args:
            system_prompt: System instructions
            user_prompt: User input
            **kwargs: Additional parameters

        Yields:
            Response text chunks
        """
        messages = self._prepare_messages(system_prompt, user_prompt)
        extra_params = self._filter_params(kwargs)
        extra_params["stream"] = True
        timeout = kwargs.pop("timeout", self.timeout)

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                timeout=timeout,
                **extra_params,
            )

            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
        except Exception as e:
            logger.error(f"Streaming request failed: {str(e)}")
            raise

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> str:
        """
        Streaming call that returns complete response as string.

        Handles UTF-8 multi-byte character safety.

        Args:
            system_prompt: System instructions
            user_prompt: User input
            **kwargs: Additional parameters

        Returns:
            Complete response string
        """
        byte_chunks = []
        for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
            byte_chunks.append(chunk.encode("utf-8"))

        if byte_chunks:
            return b"".join(byte_chunks).decode("utf-8", errors="replace")
        return ""

    def get_model_info(self) -> Dict[str, Any]:
        """Return provider and model metadata."""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
        }
