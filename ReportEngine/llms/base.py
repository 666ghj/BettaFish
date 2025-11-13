"""
Report Engine 默认的OpenAI兼容LLM客户端封装。

提供统一的非流式/流式调用、可选重试、字节安全拼接与模型元信息查询。
"""

import os
import sys
from typing import Any, Dict, Optional, Generator
from loguru import logger

from openai import OpenAI

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(project_root, "utils")
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

try:
    from retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    def with_retry(config=None):
        """简化版with_retry占位，实现与真实装饰器一致的调用签名"""
        def decorator(func):
            """直接返回原函数，确保无retry依赖时代码仍可运行"""
            return func
        return decorator

    LLM_RETRY_CONFIG = None


class LLMClient:
    """针对OpenAI Chat Completion API的轻量封装，统一Report Engine调用入口。"""

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        """
        初始化LLM客户端并保存基础连接信息。

        Args:
            api_key: 用于鉴权的API Token
            model_name: 具体模型ID，用于定位供应商能力
            base_url: 自定义兼容接口地址，默认为OpenAI官方
        """
        if not api_key:
            raise ValueError("Report Engine LLM API key is required.")
        if not model_name:
            raise ValueError("Report Engine model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("REPORT_ENGINE_REQUEST_TIMEOUT") or "3000"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 3000.0

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "max_retries": 0,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        以非流式方式调用LLM，并返回一次性完成的完整响应。

        Args:
            system_prompt: 系统角色提示
            user_prompt: 用户高优先级指令
            **kwargs: 允许透传temperature/top_p等采样参数

        Returns:
            去除首尾空白后的LLM响应文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "stream"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}

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

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        流式调用LLM，逐步返回响应内容
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）
            
        Yields:
            响应文本块（str），调用方可边读边写入磁盘或透传到UI
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}
        # 强制使用流式
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
            logger.error(f"流式请求失败: {str(e)}")
            raise e
    
    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        流式调用LLM并安全地拼接为完整字符串（避免UTF-8多字节字符截断）
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 额外参数（temperature, top_p等）
            
        Returns:
            完整的响应字符串
        """
        # 以字节形式收集所有块
        byte_chunks = []
        for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
            byte_chunks.append(chunk.encode('utf-8'))
        
        # 拼接所有字节，然后一次性解码
        if byte_chunks:
            return b''.join(byte_chunks).decode('utf-8', errors='replace')
        return ""

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        """兜底处理None/空白字符串，防止上层逻辑崩溃"""
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        """以字典形式返回当前客户端的模型/提供方/基础URL信息"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
        }
