# agno_team/_agno_setup.py
"""
agno 环境初始化（必须最先导入！）

作用：
1. 清除环境变量代理（http_proxy / https_proxy / all_proxy）
2. Patch agno.models.openai.chat 的全局 httpx client 获取函数，
   强制使用 proxy=None 的客户端，避免在用 SOCKS 代理的环境下 agno 调用失败

使用方式：
    from agno_team import _agno_setup  # noqa: F401（必须最先导入）
    from agno.agent import Agent  # 之后才能正常使用 agno
"""

import os
import httpx

# ============== 第一步：清除代理环境变量 ==============
_PROXY_KEYS = [
    "http_proxy", "https_proxy", "all_proxy",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
]
for _k in _PROXY_KEYS:
    os.environ.pop(_k, None)


# ============== 第二步：Patch agno 的全局 httpx client 获取函数 ==============

def _create_no_proxy_sync_client() -> httpx.Client:
    """创建一个绕过代理的 sync httpx client（保持 agno 默认配置）"""
    return httpx.Client(
        limits=httpx.Limits(max_connections=1000, max_keepalive_connections=200),
        timeout=httpx.Timeout(300.0),
        http2=False,
        follow_redirects=True,
        proxy=None,  # 关键
    )


def _create_no_proxy_async_client() -> httpx.AsyncClient:
    """创建一个绕过代理的 async httpx client"""
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=1000, max_keepalive_connections=200),
        timeout=httpx.Timeout(300.0),
        http2=True,
        follow_redirects=True,
        proxy=None,
    )


def _patch_agno_clients():
    """覆盖 agno 的全局 client 函数，让它们返回无代理的客户端"""
    try:
        import agno.models.openai.chat as _agno_chat
    except ImportError:
        return False

    # 单例缓存
    _cached_sync = None
    _cached_async = None

    def patched_get_sync():
        nonlocal _cached_sync
        if _cached_sync is None or _cached_sync.is_closed:
            _cached_sync = _create_no_proxy_sync_client()
        return _cached_sync

    def patched_get_async():
        nonlocal _cached_async
        if _cached_async is None or _cached_async.is_closed:
            _cached_async = _create_no_proxy_async_client()
        return _cached_async

    _agno_chat.get_default_sync_client = patched_get_sync
    _agno_chat.get_default_async_client = patched_get_async

    # 同时清空模块级单例（如果已经创建过）
    if hasattr(_agno_chat, "_global_sync_client"):
        _agno_chat._global_sync_client = None
    if hasattr(_agno_chat, "_global_async_client"):
        _agno_chat._global_async_client = None

    return True


_PATCHED = _patch_agno_clients()
