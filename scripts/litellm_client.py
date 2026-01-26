#!/usr/bin/env python3
"""
LiteLLM Gateway Client for llm.art-ai.me

Connects to the LiteLLM proxy gateway and provides:
- Model listing
- Chat completions
- News analysis
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

# LiteLLM Gateway configuration
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "https://llm.art-ai.me")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")


class LiteLLMClient:
    """Client for LiteLLM Gateway API."""

    def __init__(
        self,
        base_url: str = LITELLM_BASE_URL,
        api_key: str = LITELLM_API_KEY,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def get_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from the gateway.

        Returns:
            List of model dictionaries
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/models",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a chat completion.

        Args:
            messages: List of message dictionaries
            model: Model ID to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            stream: Whether to stream response

        Returns:
            Completion response dictionary
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def analyze_news(
        self,
        news_content: str,
        model: str = "gpt-4o-mini",
    ) -> str:
        """
        Analyze news content for sentiment and key points.

        Args:
            news_content: News text to analyze
            model: Model to use for analysis

        Returns:
            Analysis result
        """
        messages = [
            {
                "role": "system",
                "content": """You are a political news analyst. Analyze the following news content and provide:
1. Key topics and themes
2. Political sentiment (left-leaning, right-leaning, neutral)
3. Main stakeholders mentioned
4. Public opinion indicators
5. Brief summary (2-3 sentences)

Be objective and factual in your analysis."""
            },
            {
                "role": "user",
                "content": f"Analyze this news content:\n\n{news_content}"
            }
        ]

        response = await self.chat_completion(messages, model=model)
        return response["choices"][0]["message"]["content"]


async def test_connection():
    """Test the LiteLLM gateway connection."""
    client = LiteLLMClient()

    print("=" * 60)
    print("Testing LiteLLM Gateway Connection")
    print(f"Base URL: {client.base_url}")
    print("=" * 60)

    # Get available models
    print("\n1. Fetching available models...")
    try:
        models = await client.get_models()
        print(f"   Found {len(models)} models:")
        for model in models[:20]:  # Show first 20
            model_id = model.get("id", "unknown")
            print(f"   - {model_id}")
        if len(models) > 20:
            print(f"   ... and {len(models) - 20} more")
    except Exception as e:
        print(f"   Error getting models: {e}")
        return False

    # Test chat completion
    print("\n2. Testing chat completion with gpt-4o-mini...")
    try:
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Hello! What is 2+2?"}],
            model="gpt-4o-mini",
            max_tokens=100,
        )
        content = response["choices"][0]["message"]["content"]
        print(f"   Response: {content[:200]}")
    except Exception as e:
        print(f"   Error with gpt-4o-mini: {e}")

    # Test with GPT5.2-mini if available
    print("\n3. Testing with GPT5.2-mini...")
    try:
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "What are you? What model are you?"}],
            model="GPT5.2-mini",
            max_tokens=200,
        )
        content = response["choices"][0]["message"]["content"]
        print(f"   Response: {content[:300]}")
    except Exception as e:
        print(f"   Note: GPT5.2-mini test: {e}")
        # Try alternative model names
        for alt_model in ["gpt-5.2-mini", "gpt5.2-mini", "gpt-5-mini"]:
            try:
                response = await client.chat_completion(
                    messages=[{"role": "user", "content": "Hello!"}],
                    model=alt_model,
                    max_tokens=50,
                )
                print(f"   Found working model: {alt_model}")
                break
            except:
                pass

    print("\n" + "=" * 60)
    print("Connection test complete!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    asyncio.run(test_connection())
