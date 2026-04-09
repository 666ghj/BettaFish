# agno_tools/media_search_tools.py
# 迁移自 BettaFish/MediaEngine/tools/search.py
# 5 个基于 Bocha API 的多模态搜索工具，供 MediaAgent 使用

import json
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from agno.tools import tool
from config import settings


# ===== 数据结构 =====

@dataclass
class WebpageResult:
    name: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    display_url: Optional[str] = None
    date_last_crawled: Optional[str] = None


@dataclass
class ImageResult:
    name: Optional[str] = None
    content_url: Optional[str] = None
    host_page_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ModalCardResult:
    """Bocha 特色：天气/股票/百科等结构化数据卡"""
    card_type: str
    content: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BochaResponse:
    query: str = ""
    answer: Optional[str] = None
    follow_ups: List[str] = field(default_factory=list)
    webpages: List[WebpageResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    modal_cards: List[ModalCardResult] = field(default_factory=list)


# ===== Bocha 客户端 =====

_BOCHA_HEADERS = None


def _get_headers():
    """懒加载 Bocha 请求头"""
    global _BOCHA_HEADERS
    if _BOCHA_HEADERS is None:
        api_key = settings.BOCHA_WEB_SEARCH_API_KEY
        if not api_key:
            raise ValueError("BOCHA_WEB_SEARCH_API_KEY 未在 .env 中配置")
        _BOCHA_HEADERS = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }
    return _BOCHA_HEADERS


def _parse_bocha_response(response_dict: Dict[str, Any], query: str) -> BochaResponse:
    """解析 Bocha API 返回结构"""
    result = BochaResponse(query=query)
    messages = response_dict.get("messages", [])
    for msg in messages:
        if msg.get("role") != "assistant":
            continue

        msg_type = msg.get("type")
        content_type = msg.get("content_type")
        content_str = msg.get("content", "{}")

        try:
            content_data = json.loads(content_str)
        except json.JSONDecodeError:
            content_data = content_str

        if msg_type == "answer" and content_type == "text":
            result.answer = content_data
        elif msg_type == "follow_up" and content_type == "text":
            result.follow_ups.append(content_data)
        elif msg_type == "source":
            if content_type == "webpage":
                for item in content_data.get("value", []):
                    result.webpages.append(WebpageResult(
                        name=item.get("name"),
                        url=item.get("url"),
                        snippet=item.get("snippet"),
                        display_url=item.get("displayUrl"),
                        date_last_crawled=item.get("dateLastCrawled"),
                    ))
            elif content_type == "image":
                result.images.append(ImageResult(
                    name=content_data.get("name"),
                    content_url=content_data.get("contentUrl"),
                    host_page_url=content_data.get("hostPageUrl"),
                    thumbnail_url=content_data.get("thumbnailUrl"),
                    width=content_data.get("width"),
                    height=content_data.get("height"),
                ))
            else:
                # 其他都视为模态卡
                result.modal_cards.append(ModalCardResult(
                    card_type=content_type or "unknown",
                    content=content_data if isinstance(content_data, dict) else {"raw": content_data},
                ))
    return result


def _do_bocha_search(**kwargs) -> BochaResponse:
    """统一的 Bocha 搜索执行器"""
    query = kwargs.get("query", "Unknown")
    payload = {"stream": False}
    payload.update(kwargs)
    try:
        base_url = settings.BOCHA_BASE_URL or "https://api.bocha.cn/v1/ai-search"
        resp = requests.post(base_url, headers=_get_headers(), json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            return BochaResponse(query=query, answer=f"Bocha API 错误: {data.get('msg', '未知')}")
        return _parse_bocha_response(data, query)
    except Exception as e:
        return BochaResponse(query=query, answer=f"搜索失败: {e}")


def _format_bocha(resp: BochaResponse) -> str:
    """将 BochaResponse 格式化为 LLM 可消费的字符串"""
    lines = [f"搜索查询: {resp.query}"]
    if resp.answer:
        lines.append(f"\nAI 摘要: {resp.answer}")
    if resp.modal_cards:
        lines.append(f"\n结构化数据卡（{len(resp.modal_cards)} 个）：")
        for i, card in enumerate(resp.modal_cards, 1):
            lines.append(f"{i}. [{card.card_type}] {json.dumps(card.content, ensure_ascii=False)[:300]}")
    if resp.webpages:
        lines.append(f"\n网页结果（{len(resp.webpages)} 条）：")
        for i, w in enumerate(resp.webpages, 1):
            date = f" [{w.date_last_crawled}]" if w.date_last_crawled else ""
            lines.append(f"\n{i}. {w.name}{date}")
            lines.append(f"   URL: {w.url}")
            if w.snippet:
                lines.append(f"   摘要: {w.snippet[:500]}")
    if resp.images:
        lines.append(f"\n相关图片（{len(resp.images)} 张）：")
        for i, img in enumerate(resp.images, 1):
            lines.append(f"{i}. {img.name or '无标题'} - {img.content_url}")
    if resp.follow_ups:
        # follow_ups 可能是 str 或 list，统一展平为 str
        flat = []
        for fu in resp.follow_ups:
            if isinstance(fu, list):
                flat.extend(str(x) for x in fu)
            else:
                flat.append(str(fu))
        if flat:
            lines.append(f"\n追问建议: {' | '.join(flat)}")
    return "\n".join(lines)


# ===== 5 个 Agent 工具 =====

@tool(description="全面综合搜索：标准的多模态搜索，返回网页、图片、AI总结、追问建议和可能的模态卡")
def comprehensive_search(query: str, max_results: int = 10) -> str:
    """
    Args:
        query: 搜索查询词
        max_results: 最大结果数，默认 10
    """
    resp = _do_bocha_search(query=query, count=max_results, answer=True)
    return _format_bocha(resp)


@tool(description="纯网页搜索：只获取网页链接和摘要，不请求 AI 总结，速度更快成本更低")
def web_search_only(query: str, max_results: int = 15) -> str:
    """
    Args:
        query: 搜索查询词
        max_results: 最大结果数，默认 15
    """
    resp = _do_bocha_search(query=query, count=max_results, answer=False)
    return _format_bocha(resp)


@tool(description="结构化数据查询：专门用于查询天气/股票/汇率/百科/医疗等可触发模态卡的结构化信息")
def search_for_structured_data(query: str) -> str:
    """
    Args:
        query: 搜索查询词，应针对结构化数据，如「北京天气」「茅台股价」「阿司匹林副作用」
    """
    resp = _do_bocha_search(query=query, count=5, answer=True)
    return _format_bocha(resp)


@tool(description="搜索过去24小时内发布的最新信息，适用于追踪突发事件")
def search_last_24_hours(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_bocha_search(query=query, freshness="oneDay", answer=True)
    return _format_bocha(resp)


@tool(description="搜索过去一周内发布的主要报道，适用于近期趋势分析")
def search_last_week(query: str) -> str:
    """
    Args:
        query: 搜索查询词
    """
    resp = _do_bocha_search(query=query, freshness="oneWeek", answer=True)
    return _format_bocha(resp)


# ===== 给 run_single_agent.py 用的 dispatch =====

MEDIA_TOOL_DISPATCH = {
    "comprehensive_search": lambda **kw: _format_bocha(_do_bocha_search(
        query=kw["query"], count=kw.get("max_results", 10), answer=True)),
    "web_search_only": lambda **kw: _format_bocha(_do_bocha_search(
        query=kw["query"], count=kw.get("max_results", 15), answer=False)),
    "search_for_structured_data": lambda **kw: _format_bocha(_do_bocha_search(
        query=kw["query"], count=5, answer=True)),
    "search_last_24_hours": lambda **kw: _format_bocha(_do_bocha_search(
        query=kw["query"], freshness="oneDay", answer=True)),
    "search_last_week": lambda **kw: _format_bocha(_do_bocha_search(
        query=kw["query"], freshness="oneWeek", answer=True)),
}


def call_media_tool(tool_name: str, **kwargs) -> str:
    """根据工具名调度调用，供 run_single_agent.py 在多步流程中使用"""
    if tool_name not in MEDIA_TOOL_DISPATCH:
        return f"未知工具: {tool_name}"
    try:
        return MEDIA_TOOL_DISPATCH[tool_name](**kwargs)
    except Exception as e:
        return f"工具 {tool_name} 调用失败: {e}"
