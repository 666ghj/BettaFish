# agno_tools/db_query_tools.py
# 迁移自 BettaFish/InsightEngine/tools/search.py
# 6 个本地社交媒体数据库查询工具，供 InsightAgent 使用
#
# 数据库表来源：MediaCrawler 爬虫
# 内容表：bilibili_video, douyin_aweme, kuaishou_video, weibo_note,
#          xhs_note, zhihu_content, tieba_note, daily_news
# 评论表：bilibili_video_comment, douyin_aweme_comment, kuaishou_video_comment,
#          weibo_note_comment, xhs_note_comment, zhihu_comment, tieba_comment

from __future__ import annotations
import asyncio
from urllib.parse import quote_plus
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field

from agno.tools import tool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import settings


# ===== 数据结构 =====

@dataclass
class QueryResult:
    platform: str = ""
    content_type: str = ""
    title_or_content: str = ""
    author_nickname: Optional[str] = None
    url: Optional[str] = None
    publish_time: Optional[datetime] = None
    engagement: Dict[str, int] = field(default_factory=dict)
    source_keyword: Optional[str] = None
    hotness_score: float = 0.0
    source_table: str = ""


# ===== 异步数据库引擎 =====

_engine: Optional[AsyncEngine] = None


def _build_database_url() -> str:
    dialect = (settings.DB_DIALECT or "mysql").lower()
    user = quote_plus(settings.DB_USER or "")
    password = quote_plus(settings.DB_PASSWORD or "")
    host = settings.DB_HOST or ""
    port = str(settings.DB_PORT or "")
    db_name = settings.DB_NAME or ""

    if dialect == "sqlite":
        # SQLite: DB_NAME 应是文件路径，例如 data/mock_yuqing.db
        return f"sqlite+aiosqlite:///{db_name}"
    if dialect in ("postgresql", "postgres"):
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _build_database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine


async def _async_fetch_all(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(query), params or {})
        rows = result.mappings().all()
        return [dict(row) for row in rows]


def _execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """同步包装，自动管理 event loop"""
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_async_fetch_all(query, params))
    except Exception as e:
        return [{"_error": str(e)}]


def _wrap_field(field: str) -> str:
    """根据数据库方言包装字段名"""
    dialect = (settings.DB_DIALECT or "").lower()
    if dialect in ("postgresql", "postgres", "sqlite"):
        return f'"{field}"'
    return f'`{field}`'


def _to_datetime(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, date):
            return datetime.combine(ts, datetime.min.time())
        if isinstance(ts, (int, float)) or str(ts).isdigit():
            val = float(ts)
            return datetime.fromtimestamp(val / 1000 if val > 1_000_000_000_000 else val)
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.split('+')[0].strip())
    except (ValueError, TypeError):
        return None


def _extract_engagement(row: Dict[str, Any]) -> Dict[str, int]:
    """从原始行提取互动数据"""
    engagement = {}
    mapping = {
        'likes': ['liked_count', 'like_count', 'voteup_count', 'comment_like_count'],
        'comments': ['video_comment', 'comments_count', 'comment_count', 'total_replay_num', 'sub_comment_count'],
        'shares': ['video_share_count', 'shared_count', 'share_count', 'total_forwards'],
        'views': ['video_play_count', 'viewd_count'],
        'favorites': ['video_favorite_count', 'collected_count'],
        'coins': ['video_coin_count'],
        'danmaku': ['video_danmaku'],
    }
    for key, cols in mapping.items():
        for col in cols:
            if col in row and row[col] is not None:
                try:
                    engagement[key] = int(row[col])
                except (ValueError, TypeError):
                    engagement[key] = 0
                break
    return engagement


def _format_results(results: List[QueryResult], tool_name: str, params: Dict[str, Any]) -> str:
    """将查询结果格式化为 LLM 可消费的字符串"""
    lines = [f"工具: {tool_name}"]
    lines.append(f"参数: {params}")
    lines.append(f"找到 {len(results)} 条记录")

    if not results:
        lines.append("\n暂无相关内容。")
        return "\n".join(lines)

    lines.append("\n查询结果（最多前30条）：\n")
    for i, r in enumerate(results[:30], 1):
        content = (r.title_or_content or "").replace("\n", " ")[:200]
        author = r.author_nickname or "未知"
        time_str = r.publish_time.strftime("%Y-%m-%d %H:%M") if r.publish_time else "未知时间"
        engagement = ", ".join(f"{k}={v}" for k, v in r.engagement.items() if v) or "无数据"
        lines.append(f"{i}. [{r.platform.upper()}/{r.content_type}] {content}")
        lines.append(f"   作者: {author} | 时间: {time_str}")
        lines.append(f"   互动: {{{engagement}}}")
        if r.url:
            lines.append(f"   链接: {r.url}")
        if r.hotness_score > 0:
            lines.append(f"   热度: {r.hotness_score:.2f}")
        if r.source_keyword:
            lines.append(f"   源关键词: {r.source_keyword}")
        lines.append("")
    return "\n".join(lines)


# ===== 6 个 Agent 工具 =====

@tool(description="查找热点内容：获取最近一段时间内综合热度最高的内容（基于点赞/评论/分享/观看的加权算法）")
def search_hot_content(time_period: str = "week", limit: int = 50) -> str:
    """
    Args:
        time_period: 时间范围，'24h' / 'week' / 'year'，默认 'week'
        limit: 返回结果数量上限，默认 50
    """
    params_log = {"time_period": time_period, "limit": limit}
    now = datetime.now()
    days = {"24h": 1, "week": 7}.get(time_period, 365)
    start_time = now - timedelta(days=days)

    # 简化版：直接全局搜热门内容（按 id DESC 取最新作为热度近似）
    # 完整版的 hotness_formulas 需要 MySQL 特定函数，PostgreSQL 移植复杂
    # 这里用「最近内容 + 互动数据排序」的简化策略
    tables = {
        "weibo_note": {"type": "note", "title": "content", "time_col": "create_date_time"},
        "xhs_note": {"type": "note", "title": "title", "time_col": "time"},
        "zhihu_content": {"type": "content", "title": "title", "time_col": "created_time"},
        "bilibili_video": {"type": "video", "title": "title", "time_col": "create_time"},
        "douyin_aweme": {"type": "video", "title": "title", "time_col": "create_time"},
        "kuaishou_video": {"type": "video", "title": "title", "time_col": "create_time"},
        "tieba_note": {"type": "note", "title": "title", "time_col": "publish_time"},
    }

    all_results = []
    for table, cfg in tables.items():
        try:
            query = f'SELECT * FROM {_wrap_field(table)} ORDER BY id DESC LIMIT :limit'
            rows = _execute_query(query, {"limit": limit // len(tables) + 1})
            if rows and "_error" in rows[0]:
                continue
            for row in rows:
                content = row.get("title") or row.get("content") or row.get("desc", "")
                time_key = row.get(cfg["time_col"])
                pub_time = _to_datetime(time_key)
                # 时间过滤
                if pub_time and pub_time < start_time:
                    continue
                eng = _extract_engagement(row)
                hot = (
                    eng.get("likes", 0) * 1.0
                    + eng.get("comments", 0) * 5.0
                    + eng.get("shares", 0) * 10.0
                    + eng.get("views", 0) * 0.1
                    + eng.get("favorites", 0) * 10.0
                )
                all_results.append(QueryResult(
                    platform=table.split("_")[0],
                    content_type=cfg["type"],
                    title_or_content=content,
                    author_nickname=row.get("nickname") or row.get("user_nickname"),
                    url=row.get("video_url") or row.get("note_url") or row.get("content_url") or row.get("aweme_url"),
                    publish_time=pub_time,
                    engagement=eng,
                    hotness_score=hot,
                    source_keyword=row.get("source_keyword"),
                    source_table=table,
                ))
        except Exception:
            continue

    all_results.sort(key=lambda r: r.hotness_score, reverse=True)
    return _format_results(all_results[:limit], "search_hot_content", params_log)


# 各平台搜索配置
_SEARCH_CONFIGS = {
    "bilibili_video": {"fields": ["title", "desc", "source_keyword"], "type": "video"},
    "bilibili_video_comment": {"fields": ["content"], "type": "comment"},
    "douyin_aweme": {"fields": ["title", "desc", "source_keyword"], "type": "video"},
    "douyin_aweme_comment": {"fields": ["content"], "type": "comment"},
    "kuaishou_video": {"fields": ["title", "desc", "source_keyword"], "type": "video"},
    "kuaishou_video_comment": {"fields": ["content"], "type": "comment"},
    "weibo_note": {"fields": ["content", "source_keyword"], "type": "note"},
    "weibo_note_comment": {"fields": ["content"], "type": "comment"},
    "xhs_note": {"fields": ["title", "desc", "tag_list", "source_keyword"], "type": "note"},
    "xhs_note_comment": {"fields": ["content"], "type": "comment"},
    "zhihu_content": {"fields": ["title", "desc", "content_text", "source_keyword"], "type": "content"},
    "zhihu_comment": {"fields": ["content"], "type": "comment"},
    "tieba_note": {"fields": ["title", "desc", "source_keyword"], "type": "note"},
    "tieba_comment": {"fields": ["content"], "type": "comment"},
}


def _search_topic_tables(topic: str, limit_per_table: int, configs: Dict[str, Any]) -> List[QueryResult]:
    """统一的话题搜索辅助函数"""
    search_term = f"%{topic}%"
    all_results = []

    for table, cfg in configs.items():
        try:
            param_dict = {"limit": limit_per_table}
            where_clauses = []
            for idx, fld in enumerate(cfg["fields"]):
                pname = f"term_{idx}"
                where_clauses.append(f'{_wrap_field(fld)} LIKE :{pname}')
                param_dict[pname] = search_term
            where_clause = " OR ".join(where_clauses)
            query = f'SELECT * FROM {_wrap_field(table)} WHERE {where_clause} ORDER BY id DESC LIMIT :limit'

            rows = _execute_query(query, param_dict)
            if rows and "_error" in rows[0]:
                continue

            for row in rows:
                content = (
                    row.get("title") or row.get("content")
                    or row.get("desc") or row.get("content_text", "")
                )
                time_key = (
                    row.get("create_time") or row.get("time") or row.get("created_time")
                    or row.get("publish_time") or row.get("create_date_time")
                )
                all_results.append(QueryResult(
                    platform=table.split("_")[0],
                    content_type=cfg["type"],
                    title_or_content=content,
                    author_nickname=row.get("nickname") or row.get("user_nickname") or row.get("user_name"),
                    url=row.get("video_url") or row.get("note_url") or row.get("content_url") or row.get("url") or row.get("aweme_url"),
                    publish_time=_to_datetime(time_key),
                    engagement=_extract_engagement(row),
                    source_keyword=row.get("source_keyword"),
                    source_table=table,
                ))
        except Exception:
            continue

    return all_results


@tool(description="全局话题搜索：在数据库所有平台（微博/B站/抖音/快手/小红书/知乎/贴吧）的内容和评论中搜索指定话题")
def search_topic_globally(topic: str, limit_per_table: int = 100) -> str:
    """
    Args:
        topic: 搜索话题关键词
        limit_per_table: 每个表的结果数上限，默认 100
    """
    params_log = {"topic": topic, "limit_per_table": limit_per_table}
    results = _search_topic_tables(topic, limit_per_table, _SEARCH_CONFIGS)
    return _format_results(results, "search_topic_globally", params_log)


@tool(description="按日期范围搜索话题：在指定的历史日期范围内搜索特定话题的所有内容（追踪舆情演变）")
def search_topic_by_date(topic: str, start_date: str, end_date: str, limit_per_table: int = 100) -> str:
    """
    Args:
        topic: 搜索话题关键词
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        limit_per_table: 每个表的结果数上限，默认 100
    """
    params_log = {"topic": topic, "start_date": start_date, "end_date": end_date}
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return f"日期格式错误，请使用 YYYY-MM-DD 格式。当前: start_date={start_date}, end_date={end_date}"

    # 先全局搜，再按 publish_time 过滤
    all_results = _search_topic_tables(topic, limit_per_table, _SEARCH_CONFIGS)
    filtered = [
        r for r in all_results
        if r.publish_time and start_dt <= r.publish_time < end_dt
    ]
    return _format_results(filtered, "search_topic_by_date", params_log)


@tool(description="获取话题评论：搜索所有平台中与话题相关的公众评论数据，深度挖掘网民真实态度")
def get_comments_for_topic(topic: str, limit: int = 500) -> str:
    """
    Args:
        topic: 搜索话题关键词
        limit: 评论总数量上限，默认 500
    """
    params_log = {"topic": topic, "limit": limit}
    comment_configs = {
        k: v for k, v in _SEARCH_CONFIGS.items() if k.endswith("_comment")
    }
    results = _search_topic_tables(topic, limit // max(len(comment_configs), 1) + 1, comment_configs)
    return _format_results(results[:limit], "get_comments_for_topic", params_log)


@tool(description="平台定向搜索：在指定的单个社交媒体平台上精确搜索话题（适合分析特定平台用户群体的观点）")
def search_topic_on_platform(
    platform: str,
    topic: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Args:
        platform: 平台名称，必须是 bilibili / weibo / douyin / kuaishou / xhs / zhihu / tieba 之一
        topic: 搜索话题关键词
        start_date: 可选开始日期，格式 YYYY-MM-DD
        end_date: 可选结束日期，格式 YYYY-MM-DD
        limit: 返回结果数量上限，默认 20
    """
    params_log = {"platform": platform, "topic": topic, "start_date": start_date, "end_date": end_date}

    platform_table_map = {
        "bilibili": ["bilibili_video", "bilibili_video_comment"],
        "douyin": ["douyin_aweme", "douyin_aweme_comment"],
        "kuaishou": ["kuaishou_video", "kuaishou_video_comment"],
        "weibo": ["weibo_note", "weibo_note_comment"],
        "xhs": ["xhs_note", "xhs_note_comment"],
        "zhihu": ["zhihu_content", "zhihu_comment"],
        "tieba": ["tieba_note", "tieba_comment"],
    }

    if platform not in platform_table_map:
        return f"不支持的平台: {platform}。支持: {list(platform_table_map.keys())}"

    tables = platform_table_map[platform]
    configs = {t: _SEARCH_CONFIGS[t] for t in tables if t in _SEARCH_CONFIGS}
    results = _search_topic_tables(topic, limit, configs)

    # 时间过滤
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            results = [r for r in results if r.publish_time and start_dt <= r.publish_time < end_dt]
        except ValueError:
            pass

    return _format_results(results[:limit], "search_topic_on_platform", params_log)


@tool(description="多语言情感分析：对文本列表进行情感倾向分析，输出5级情感分类（非常负面/负面/中性/正面/非常正面），支持22种语言")
def analyze_sentiment(texts: List[str]) -> str:
    """
    Args:
        texts: 待分析的文本列表
    """
    try:
        from .sentiment_tools import analyze_texts
        return analyze_texts(texts)
    except ImportError:
        return "情感分析工具未实现：请确保 agno_tools/sentiment_tools.py 已就绪"
    except Exception as e:
        return f"情感分析失败: {e}"


# ===== run_single_agent.py 用的 dispatch =====

INSIGHT_TOOL_DISPATCH = {
    "search_hot_content": lambda **kw: _format_results(
        [], "search_hot_content", kw  # 通过下面的 wrapper 实现
    ),
}


def call_insight_tool(tool_name: str, **kwargs) -> str:
    """根据工具名调度调用，供 run_single_agent.py 在多步流程中使用"""
    # 直接调用 @tool 装饰的函数 (它们 .entrypoint 会暴露原始函数)
    tool_funcs = {
        "search_hot_content": search_hot_content,
        "search_topic_globally": search_topic_globally,
        "search_topic_by_date": search_topic_by_date,
        "get_comments_for_topic": get_comments_for_topic,
        "search_topic_on_platform": search_topic_on_platform,
        "analyze_sentiment": analyze_sentiment,
    }
    if tool_name not in tool_funcs:
        return f"未知工具: {tool_name}"
    try:
        fn = tool_funcs[tool_name]
        # 取出原函数（agno @tool 装饰后会变成 Function 对象）
        actual = getattr(fn, "entrypoint", None) or getattr(fn, "fn", None) or fn
        return actual(**kwargs)
    except Exception as e:
        return f"工具 {tool_name} 调用失败: {e}"
