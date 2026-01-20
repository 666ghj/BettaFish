"""
Unified LLM client module supporting multiple providers:
- OpenAI (and compatible: DeepSeek, Kimi, OpenRouter)
- Azure OpenAI
- Anthropic Claude

Usage:
    from utils.llm import create_llm_client, BaseLLMClient

    client = create_llm_client(
        provider="openai",  # or "azure", "anthropic", "auto"
        api_key="...",
        model_name="gpt-4",
        base_url="https://api.openai.com/v1"  # optional
    )

    response = client.invoke("You are helpful.", "Hello!")
"""

from .base import BaseLLMClient
from .factory import create_llm_client, detect_provider

__all__ = [
    "BaseLLMClient",
    "create_llm_client",
    "detect_provider",
]
