"""
Report Engine LLM子模块。

目前主要暴露 OpenAI 兼容的 `LLMClient` 封装。
"""

from .base import LLMClient

__all__ = ["LLMClient"]
