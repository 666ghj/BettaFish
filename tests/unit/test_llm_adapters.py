"""
Unit tests for LLM adapter implementations.

Tests:
- OpenAI adapter
- Azure OpenAI adapter
- Anthropic Claude adapter
- Factory function and auto-detection
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestProviderDetection:
    """Tests for automatic provider detection."""

    def test_detect_anthropic_from_model_name(self):
        """Anthropic detected from model name containing 'claude'."""
        from utils.llm.factory import detect_provider

        assert detect_provider("claude-3-5-sonnet-20241022") == "anthropic"
        assert detect_provider("claude-3-opus-20240229") == "anthropic"
        assert detect_provider("Claude-Instant") == "anthropic"

    def test_detect_azure_from_base_url(self):
        """Azure detected from base URL containing 'azure'."""
        from utils.llm.factory import detect_provider

        assert detect_provider("gpt-4", "https://myresource.openai.azure.com") == "azure"
        assert detect_provider("gpt-35-turbo", "https://example.azure.com/v1") == "azure"

    def test_detect_openai_default(self):
        """OpenAI is default for non-matching cases."""
        from utils.llm.factory import detect_provider

        assert detect_provider("gpt-4") == "openai"
        assert detect_provider("deepseek-chat") == "openai"
        assert detect_provider("kimi-k2") == "openai"
        assert detect_provider("gpt-4", "https://openrouter.ai/api/v1") == "openai"


class TestFactoryFunction:
    """Tests for create_llm_client factory."""

    def test_create_openai_client(self):
        """Factory creates OpenAI adapter correctly."""
        from utils.llm import create_llm_client
        from utils.llm.adapters import OpenAIAdapter

        with patch.object(OpenAIAdapter, '__init__', return_value=None):
            client = create_llm_client(
                provider="openai",
                api_key="test-key",
                model_name="gpt-4"
            )
            assert isinstance(client, OpenAIAdapter)

    def test_create_azure_client(self):
        """Factory creates Azure adapter correctly."""
        from utils.llm import create_llm_client
        from utils.llm.adapters import AzureOpenAIAdapter

        with patch.object(AzureOpenAIAdapter, '__init__', return_value=None):
            client = create_llm_client(
                provider="azure",
                api_key="test-key",
                model_name="gpt-4-deployment",
                base_url="https://myresource.openai.azure.com",
                api_version="2024-02-01"
            )
            assert isinstance(client, AzureOpenAIAdapter)

    def test_create_anthropic_client(self):
        """Factory creates Anthropic adapter correctly."""
        from utils.llm import create_llm_client
        from utils.llm.adapters import AnthropicAdapter

        with patch.object(AnthropicAdapter, '__init__', return_value=None):
            client = create_llm_client(
                provider="anthropic",
                api_key="test-key",
                model_name="claude-3-5-sonnet-20241022"
            )
            assert isinstance(client, AnthropicAdapter)

    def test_auto_detection(self):
        """Factory auto-detects provider from model name."""
        from utils.llm import create_llm_client
        from utils.llm.adapters import AnthropicAdapter

        with patch.object(AnthropicAdapter, '__init__', return_value=None):
            client = create_llm_client(
                provider="auto",
                api_key="test-key",
                model_name="claude-3-opus-20240229"
            )
            assert isinstance(client, AnthropicAdapter)

    def test_backward_compatible_llmclient(self):
        """LLMClient alias works for backward compatibility."""
        from utils.llm.factory import LLMClient
        from utils.llm.adapters import OpenAIAdapter

        with patch.object(OpenAIAdapter, '__init__', return_value=None):
            client = LLMClient(
                api_key="test-key",
                model_name="gpt-4",
                base_url="https://api.openai.com/v1"
            )
            assert isinstance(client, OpenAIAdapter)


class TestOpenAIAdapter:
    """Tests for OpenAI adapter."""

    def test_validation_requires_api_key(self):
        """OpenAI adapter requires API key."""
        from utils.llm.adapters import OpenAIAdapter

        with pytest.raises(ValueError, match="API key is required"):
            OpenAIAdapter(api_key="", model_name="gpt-4")

    def test_validation_requires_model_name(self):
        """OpenAI adapter requires model name."""
        from utils.llm.adapters import OpenAIAdapter

        with pytest.raises(ValueError, match="Model name is required"):
            OpenAIAdapter(api_key="test-key", model_name="")

    def test_get_model_info(self):
        """OpenAI adapter returns correct model info."""
        from utils.llm.adapters import OpenAIAdapter

        with patch('utils.llm.adapters.openai_adapter.OpenAI'):
            adapter = OpenAIAdapter(
                api_key="test-key",
                model_name="gpt-4",
                base_url="https://api.openai.com/v1"
            )
            info = adapter.get_model_info()

            assert info["provider"] == "openai"
            assert info["model"] == "gpt-4"
            assert "api.openai.com" in info["api_base"]


class TestAzureAdapter:
    """Tests for Azure OpenAI adapter."""

    def test_validation_requires_base_url(self):
        """Azure adapter requires base URL (endpoint)."""
        from utils.llm.adapters import AzureOpenAIAdapter

        with pytest.raises(ValueError, match="endpoint.*required"):
            AzureOpenAIAdapter(
                api_key="test-key",
                model_name="gpt-4-deployment",
                base_url=""
            )

    def test_default_api_version(self):
        """Azure adapter uses default API version."""
        from utils.llm.adapters import AzureOpenAIAdapter

        with patch('utils.llm.adapters.azure_adapter.AzureOpenAI'):
            adapter = AzureOpenAIAdapter(
                api_key="test-key",
                model_name="gpt-4-deployment",
                base_url="https://myresource.openai.azure.com"
            )
            assert adapter.api_version == "2024-02-01"

    def test_custom_api_version(self):
        """Azure adapter accepts custom API version."""
        from utils.llm.adapters import AzureOpenAIAdapter

        with patch('utils.llm.adapters.azure_adapter.AzureOpenAI'):
            adapter = AzureOpenAIAdapter(
                api_key="test-key",
                model_name="gpt-4-deployment",
                base_url="https://myresource.openai.azure.com",
                api_version="2023-12-01"
            )
            assert adapter.api_version == "2023-12-01"

    def test_get_model_info_includes_version(self):
        """Azure adapter model info includes API version."""
        from utils.llm.adapters import AzureOpenAIAdapter

        with patch('utils.llm.adapters.azure_adapter.AzureOpenAI'):
            adapter = AzureOpenAIAdapter(
                api_key="test-key",
                model_name="gpt-4-deployment",
                base_url="https://myresource.openai.azure.com"
            )
            info = adapter.get_model_info()

            assert info["provider"] == "azure"
            assert "api_version" in info


class TestAnthropicAdapter:
    """Tests for Anthropic Claude adapter."""

    @pytest.mark.skipif(
        not pytest.importorskip("anthropic", reason="anthropic not installed"),
        reason="anthropic package not available"
    )
    def test_validation_requires_api_key(self):
        """Anthropic adapter requires API key."""
        from utils.llm.adapters import AnthropicAdapter

        with pytest.raises(ValueError, match="API key is required"):
            AnthropicAdapter(api_key="", model_name="claude-3-5-sonnet-20241022")

    @pytest.mark.skipif(
        not pytest.importorskip("anthropic", reason="anthropic not installed"),
        reason="anthropic package not available"
    )
    def test_get_model_info(self):
        """Anthropic adapter returns correct model info."""
        from utils.llm.adapters import AnthropicAdapter

        with patch('utils.llm.adapters.anthropic_adapter.Anthropic'):
            adapter = AnthropicAdapter(
                api_key="test-key",
                model_name="claude-3-5-sonnet-20241022"
            )
            info = adapter.get_model_info()

            assert info["provider"] == "anthropic"
            assert info["model"] == "claude-3-5-sonnet-20241022"
            assert "anthropic.com" in info["api_base"]


class TestBaseClientInterface:
    """Tests that all adapters implement BaseLLMClient interface."""

    def test_openai_implements_interface(self):
        """OpenAI adapter implements all required methods."""
        from utils.llm.base import BaseLLMClient
        from utils.llm.adapters import OpenAIAdapter

        assert issubclass(OpenAIAdapter, BaseLLMClient)

        # Check required methods exist
        assert hasattr(OpenAIAdapter, 'invoke')
        assert hasattr(OpenAIAdapter, 'stream_invoke')
        assert hasattr(OpenAIAdapter, 'stream_invoke_to_string')
        assert hasattr(OpenAIAdapter, 'get_model_info')

    def test_azure_implements_interface(self):
        """Azure adapter implements all required methods."""
        from utils.llm.base import BaseLLMClient
        from utils.llm.adapters import AzureOpenAIAdapter

        assert issubclass(AzureOpenAIAdapter, BaseLLMClient)

    def test_anthropic_implements_interface(self):
        """Anthropic adapter implements all required methods."""
        from utils.llm.base import BaseLLMClient
        from utils.llm.adapters import AnthropicAdapter

        assert issubclass(AnthropicAdapter, BaseLLMClient)
