"""
统一 LLM 客户端提供模块

支持 OpenAI SDK 和 Anthropic SDK（含 Claude Code OAuth token 认证）。
各引擎通过此模块创建 LLM 客户端，对上层暴露完全一致的接口。

Token 类型自动检测逻辑:
  - sk-ant-oat* → Anthropic SDK + OAuth 认证模式（注入特殊 headers）
  - sk-ant-*    → Anthropic SDK + 标准 API key 模式
  - 其他        → OpenAI SDK（向后兼容）

用法:
    from utils.llm_provider import LLMClient

    client = LLMClient(api_key="sk-ant-oat-xxx", model_name="claude-sonnet-4-20250514")
    response = client.invoke("你是助手", "你好")
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional, Generator
from loguru import logger

# ------------------------------------------------------------------
#  重试机制导入（与 retry_helper.py 同目录）
# ------------------------------------------------------------------
try:
    from utils.retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    try:
        from retry_helper import with_retry, LLM_RETRY_CONFIG
    except ImportError:
        def with_retry(config=None):
            def decorator(func):
                return func
            return decorator

        LLM_RETRY_CONFIG = None

# ------------------------------------------------------------------
#  Token 前缀常量
# ------------------------------------------------------------------
OAUTH_TOKEN_PREFIX = "sk-ant-oat"
ANTHROPIC_TOKEN_PREFIX = "sk-ant-"

# Anthropic messages API 必须显式指定 max_tokens
DEFAULT_ANTHROPIC_MAX_TOKENS = 8192


# ------------------------------------------------------------------
#  Token 类型判断
# ------------------------------------------------------------------
def is_oauth_token(api_key: str) -> bool:
    """判断是否为 Claude Code OAuth token（sk-ant-oat 开头）"""
    return bool(api_key and api_key.startswith(OAUTH_TOKEN_PREFIX))


def is_anthropic_token(api_key: str) -> bool:
    """判断是否为 Anthropic 系列 token（含 OAuth 和普通 API key）"""
    return bool(api_key and api_key.startswith(ANTHROPIC_TOKEN_PREFIX))


# ------------------------------------------------------------------
#  客户端工厂函数
# ------------------------------------------------------------------
def _create_openai_client(api_key: str, base_url: Optional[str] = None):
    """创建 OpenAI 兼容客户端"""
    from openai import OpenAI

    kwargs: Dict[str, Any] = {"api_key": api_key, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _create_anthropic_client(api_key: str, base_url: Optional[str] = None):
    """
    创建 Anthropic 客户端，自动检测 OAuth token 并注入相应 headers。

    Args:
        api_key: Anthropic API key 或 OAuth token
        base_url: 可选的自定义 base_url（通常不需要设置）
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError(
            "使用 Anthropic/Claude 需要安装 anthropic 包: pip install anthropic"
        )

    client_kwargs: Dict[str, Any] = {}
    if base_url:
        client_kwargs["base_url"] = base_url

    if is_oauth_token(api_key):
        # OAuth token 模式：使用 auth_token 参数 + 特殊 headers
        logger.info("检测到 Claude Code OAuth token (sk-ant-oat*)，使用 OAuth 认证模式")
        client_kwargs["auth_token"] = api_key
        client_kwargs["default_headers"] = {
            "anthropic-dangerous-direct-browser-access": "true",
            "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
            "user-agent": "claude-cli/1.0.0 (external, cli)",
            "x-app": "cli",
        }
    else:
        # 标准 Anthropic API key 模式
        logger.info("检测到 Anthropic API key (sk-ant-*)，使用标准 API key 认证模式")
        client_kwargs["api_key"] = api_key

    return Anthropic(**client_kwargs)


# ------------------------------------------------------------------
#  统一 LLM 客户端
# ------------------------------------------------------------------
class LLMClient:
    """
    统一的 LLM 客户端封装。

    根据 api_key 前缀自动选择 OpenAI SDK 或 Anthropic SDK，
    对上层暴露完全一致的 invoke / stream_invoke / stream_invoke_to_string 接口。
    """

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        *,
        engine_name: str = "LLM",
        timeout_env_prefix: Optional[str] = None,
        default_timeout: float = 1800.0,
        prepend_time: bool = True,
        max_tokens: int = DEFAULT_ANTHROPIC_MAX_TOKENS,
    ):
        """
        初始化 LLM 客户端。

        Args:
            api_key: API 密钥或 OAuth token
            model_name: 模型名称
            base_url: 自定义 API 地址（仅 OpenAI 模式生效，Anthropic 模式默认忽略）
            engine_name: 引擎名称，用于日志和错误提示
            timeout_env_prefix: 超时环境变量前缀，如 "INSIGHT_ENGINE"
            default_timeout: 默认超时秒数
            prepend_time: 是否在 user_prompt 前自动添加当前时间
            max_tokens: Anthropic API 的 max_tokens 参数（OpenAI 模式忽略）
        """
        if not api_key:
            raise ValueError(f"{engine_name} API key is required.")
        if not model_name:
            raise ValueError(f"{engine_name} model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        self.engine_name = engine_name
        self.prepend_time = prepend_time
        self.max_tokens = max_tokens

        # 从环境变量读取超时
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT")
        if not timeout_fallback and timeout_env_prefix:
            timeout_fallback = os.getenv(f"{timeout_env_prefix}_REQUEST_TIMEOUT")
        if not timeout_fallback:
            timeout_fallback = str(default_timeout)
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = default_timeout

        # 根据 token 类型选择后端
        self._use_anthropic = is_anthropic_token(api_key)

        if self._use_anthropic:
            # Anthropic 模式：OAuth token 不需要 base_url（直连 Anthropic 官方 API）
            anthropic_base_url = None if is_oauth_token(api_key) else base_url
            self.client = _create_anthropic_client(api_key, anthropic_base_url)
            logger.info(f"{engine_name}: 使用 Anthropic SDK (model={model_name})")
        else:
            self.client = _create_openai_client(api_key, base_url)
            logger.info(f"{engine_name}: 使用 OpenAI SDK (model={model_name})")

    # ================================================================ #
    #  消息预处理
    # ================================================================ #

    def _prepare_user_prompt(self, user_prompt: str) -> str:
        """可选地在 user_prompt 前添加当前时间"""
        if not self.prepend_time:
            return user_prompt
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        return f"{time_prefix}\n{user_prompt}" if user_prompt else time_prefix

    # ================================================================ #
    #  Anthropic 后端
    # ================================================================ #

    def _build_anthropic_kwargs(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Dict[str, Any]:
        """构建 Anthropic messages.create / messages.stream 参数"""
        messages = [{"role": "user", "content": user_prompt}]

        create_kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
        }

        # timeout 需要单独传递
        timeout = kwargs.pop("timeout", self.timeout)
        create_kwargs["timeout"] = timeout

        if system_prompt:
            create_kwargs["system"] = system_prompt

        # 映射支持的采样参数（Anthropic 不支持 presence_penalty / frequency_penalty）
        for key in ("temperature", "top_p"):
            val = kwargs.get(key)
            if val is not None:
                create_kwargs[key] = val

        return create_kwargs

    def _anthropic_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """通过 Anthropic SDK 进行非流式调用"""
        create_kwargs = self._build_anthropic_kwargs(system_prompt, user_prompt, **kwargs)
        response = self.client.messages.create(**create_kwargs)
        if response.content:
            return self.validate_response(response.content[0].text)
        return ""

    def _anthropic_stream(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """通过 Anthropic SDK 进行流式调用"""
        create_kwargs = self._build_anthropic_kwargs(system_prompt, user_prompt, **kwargs)
        # messages.stream 返回上下文管理器
        with self.client.messages.stream(**create_kwargs) as stream:
            for text in stream.text_stream:
                yield text

    # ================================================================ #
    #  OpenAI 后端
    # ================================================================ #

    def _openai_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """通过 OpenAI SDK 进行非流式调用"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {
            "temperature", "top_p", "presence_penalty",
            "frequency_penalty", "stream",
        }
        extra_params = {
            k: v for k, v in kwargs.items() if k in allowed_keys and v is not None
        }

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

    def _openai_stream(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """通过 OpenAI SDK 进行流式调用"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty"}
        extra_params = {
            k: v for k, v in kwargs.items() if k in allowed_keys and v is not None
        }
        extra_params["stream"] = True

        timeout = kwargs.pop("timeout", self.timeout)

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

    # ================================================================ #
    #  公共接口
    # ================================================================ #

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        非流式调用 LLM，自动选择后端。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 采样参数（temperature, top_p 等）

        Returns:
            LLM 响应文本
        """
        user_prompt = self._prepare_user_prompt(user_prompt)
        if self._use_anthropic:
            return self._anthropic_invoke(system_prompt, user_prompt, **kwargs)
        return self._openai_invoke(system_prompt, user_prompt, **kwargs)

    def stream_invoke(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> Generator[str, None, None]:
        """
        流式调用 LLM，逐步返回响应内容。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 采样参数（temperature, top_p 等）

        Yields:
            响应文本块（str）
        """
        user_prompt = self._prepare_user_prompt(user_prompt)
        try:
            if self._use_anthropic:
                yield from self._anthropic_stream(system_prompt, user_prompt, **kwargs)
            else:
                yield from self._openai_stream(system_prompt, user_prompt, **kwargs)
        except Exception as e:
            logger.error(f"流式请求失败: {str(e)}")
            raise

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> str:
        """
        流式调用 LLM 并安全地拼接为完整字符串（避免 UTF-8 多字节字符截断）。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 采样参数

        Returns:
            完整的响应字符串
        """
        byte_chunks = []
        for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
            byte_chunks.append(chunk.encode("utf-8"))

        if byte_chunks:
            return b"".join(byte_chunks).decode("utf-8", errors="replace")
        return ""

    # ================================================================ #
    #  工具方法
    # ================================================================ #

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        """兜底处理 None / 空白字符串"""
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        """返回当前客户端的模型 / 提供方 / 后端信息"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
            "backend": "anthropic" if self._use_anthropic else "openai",
        }
