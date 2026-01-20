"""
Anthropic Claude adapter.

Handles Anthropic's different API format:
- Response format: content[0].text (not choices[0].message.content)
- System prompt in separate parameter (not in messages)
- Different streaming format
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from loguru import logger

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

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


class AnthropicAdapter(BaseLLMClient):
    """
    Adapter for Anthropic Claude API.

    Key differences from OpenAI:
    - System prompt is a separate parameter
    - Response format: response.content[0].text
    - Streaming uses different event types
    - Model names: claude-3-5-sonnet-20241022, claude-3-opus-20240229, etc.
    """

    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key
            model_name: Model identifier (e.g., "claude-3-5-sonnet-20241022")
            base_url: Optional custom endpoint (for proxies)
            timeout: Request timeout in seconds (default: 1800)
        """
        if Anthropic is None:
            raise ImportError(
                "Anthropic not available. Install with: pip install anthropic>=0.28.0"
            )

        if not api_key:
            raise ValueError("API key is required for Anthropic adapter")
        if not model_name:
            raise ValueError("Model name is required for Anthropic adapter")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = "anthropic"

        # Determine timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            timeout_env = os.getenv("LLM_REQUEST_TIMEOUT", "1800")
            try:
                self.timeout = float(timeout_env)
            except ValueError:
                self.timeout = 1800.0

        # Initialize Anthropic client
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = Anthropic(**client_kwargs)

    def _prepare_user_prompt(self, user_prompt: str) -> str:
        """Add time prefix to user prompt."""
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"

        if user_prompt:
            return f"{time_prefix}\n{user_prompt}"
        return time_prefix

    def _get_max_tokens(self, kwargs: Dict[str, Any]) -> int:
        """Get max_tokens from kwargs or default."""
        return kwargs.pop("max_tokens", self.DEFAULT_MAX_TOKENS)

    def _filter_params(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter allowed parameters for the API call."""
        allowed_keys = {
            "temperature",
            "top_p",
            "top_k",  # Anthropic-specific
        }
        return {
            key: value
            for key, value in kwargs.items()
            if key in allowed_keys and value is not None
        }

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Non-streaming call to Anthropic Claude.

        Args:
            system_prompt: System instructions
            user_prompt: User input
            **kwargs: Additional parameters

        Returns:
            Model response as string
        """
        prepared_prompt = self._prepare_user_prompt(user_prompt)
        max_tokens = self._get_max_tokens(kwargs)
        extra_params = self._filter_params(kwargs)

        # Anthropic format: system is separate, messages only contain user/assistant
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prepared_prompt}],
            **extra_params,
        )

        # CRITICAL: Anthropic uses content[0].text, not choices[0].message.content
        if response.content and len(response.content) > 0:
            return self.validate_response(response.content[0].text)
        return ""

    def stream_invoke(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """
        Streaming call to Anthropic Claude.

        Args:
            system_prompt: System instructions
            user_prompt: User input
            **kwargs: Additional parameters

        Yields:
            Response text chunks
        """
        prepared_prompt = self._prepare_user_prompt(user_prompt)
        max_tokens = self._get_max_tokens(kwargs)
        extra_params = self._filter_params(kwargs)

        try:
            with self.client.messages.stream(
                model=self.model_name,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prepared_prompt}],
                **extra_params,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming request failed: {str(e)}")
            raise

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> str:
        """
        Streaming call that returns complete response as string.

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
            "api_base": self.base_url or "https://api.anthropic.com",
        }
