"""
LLM provider adapters for different API formats.

- OpenAIAdapter: OpenAI, DeepSeek, Kimi, OpenRouter (OpenAI-compatible)
- AzureOpenAIAdapter: Azure OpenAI (requires api_version)
- AnthropicAdapter: Anthropic Claude (different response format)
"""

from .openai_adapter import OpenAIAdapter
from .azure_adapter import AzureOpenAIAdapter
from .anthropic_adapter import AnthropicAdapter

__all__ = [
    "OpenAIAdapter",
    "AzureOpenAIAdapter",
    "AnthropicAdapter",
]
