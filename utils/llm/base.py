"""
Abstract base class for all LLM provider adapters.

All adapters must implement these methods to ensure consistent behavior
across different LLM providers (OpenAI, Azure, Anthropic, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional


class BaseLLMClient(ABC):
    """Abstract base class for LLM client adapters."""

    @abstractmethod
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Synchronous non-streaming call to the LLM.

        Args:
            system_prompt: System-level instructions for the model
            user_prompt: User's input/question
            **kwargs: Additional parameters (temperature, top_p, etc.)

        Returns:
            Model's response as a string
        """
        pass

    @abstractmethod
    def stream_invoke(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """
        Streaming call to the LLM, yielding response chunks.

        Args:
            system_prompt: System-level instructions for the model
            user_prompt: User's input/question
            **kwargs: Additional parameters (temperature, top_p, etc.)

        Yields:
            Response text chunks as they arrive
        """
        pass

    @abstractmethod
    def stream_invoke_to_string(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> str:
        """
        Streaming call that returns the complete response as a string.

        Handles UTF-8 multi-byte character safety by collecting bytes
        before decoding.

        Args:
            system_prompt: System-level instructions for the model
            user_prompt: User's input/question
            **kwargs: Additional parameters (temperature, top_p, etc.)

        Returns:
            Complete response as a string
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Return metadata about the provider and model configuration.

        Returns:
            Dictionary containing provider, model name, and API base URL
        """
        pass

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        """
        Validate and clean the response string.

        Args:
            response: Raw response from the model

        Returns:
            Cleaned response string (empty string if None)
        """
        if response is None:
            return ""
        return response.strip()
