"""
Factory for creating LLM clients based on provider detection.

Supports automatic detection of provider from model name or base URL,
or explicit provider specification.
"""

from typing import Optional

from .base import BaseLLMClient
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.azure_adapter import AzureOpenAIAdapter
from .adapters.anthropic_adapter import AnthropicAdapter


def detect_provider(
    model_name: str, base_url: Optional[str] = None
) -> str:
    """
    Auto-detect LLM provider from model name and base URL.

    Priority: base_url > model_name
    - OpenRouter/other proxies use OpenAI-compatible API even for Claude models
    - Azure uses its own API format
    - Direct Anthropic API uses Anthropic format

    Args:
        model_name: Model identifier
        base_url: Optional API endpoint

    Returns:
        Provider string: "anthropic", "azure", or "openai"
    """
    model_lower = model_name.lower() if model_name else ""
    base_lower = (base_url or "").lower()

    # Check base URL first (takes priority over model name)
    # OpenRouter and other proxies use OpenAI-compatible API
    if "openrouter.ai" in base_lower:
        return "openai"

    # Azure OpenAI detection
    if "azure" in base_lower or "openai.azure.com" in base_lower:
        return "azure"

    # If no special base URL and model name contains "claude", use Anthropic
    if "claude" in model_lower and not base_url:
        return "anthropic"

    # Also check for explicit anthropic.com
    if "anthropic.com" in base_lower:
        return "anthropic"

    # Anthropic Claude detection from model name
    if "claude" in model_lower:
        return "anthropic"

    # Default to OpenAI-compatible (covers OpenAI, DeepSeek, Kimi, OpenRouter)
    return "openai"


def create_llm_client(
    provider: str = "auto",
    api_key: str = "",
    model_name: str = "",
    base_url: Optional[str] = None,
    api_version: Optional[str] = None,
    timeout: Optional[float] = None,
    **kwargs,
) -> BaseLLMClient:
    """
    Factory function to create the appropriate LLM client.

    Args:
        provider: Provider type ("openai", "azure", "anthropic", or "auto")
        api_key: API key for authentication
        model_name: Model identifier or deployment name
        base_url: Optional custom API endpoint
        api_version: API version (Azure only)
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured LLM client instance

    Examples:
        # Auto-detect provider from model name
        client = create_llm_client(
            provider="auto",
            api_key="sk-...",
            model_name="claude-3-5-sonnet-20241022"
        )

        # Explicit Azure configuration
        client = create_llm_client(
            provider="azure",
            api_key="...",
            model_name="gpt-4-deployment",
            base_url="https://myresource.openai.azure.com",
            api_version="2024-02-01"
        )

        # OpenRouter (OpenAI-compatible)
        client = create_llm_client(
            provider="openai",
            api_key="sk-or-...",
            model_name="anthropic/claude-3.5-sonnet",
            base_url="https://openrouter.ai/api/v1"
        )
    """
    # Auto-detect provider if not specified
    if provider == "auto" or not provider:
        provider = detect_provider(model_name, base_url)

    provider_lower = provider.lower()

    if provider_lower == "anthropic":
        return AnthropicAdapter(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            timeout=timeout,
        )

    if provider_lower == "azure":
        return AzureOpenAIAdapter(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            api_version=api_version,
            timeout=timeout,
        )

    # Default: OpenAI-compatible (OpenAI, DeepSeek, Kimi, OpenRouter)
    return OpenAIAdapter(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        timeout=timeout,
    )


# Backward compatibility alias
def LLMClient(
    api_key: str, model_name: str, base_url: Optional[str] = None
) -> BaseLLMClient:
    """
    Backward-compatible factory function.

    This provides drop-in replacement for existing LLMClient usage
    in engine code.
    """
    return create_llm_client(
        provider="auto",
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )
