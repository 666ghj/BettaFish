#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BroadTopicExtraction module - source/news collection.

Localized default: collect from provider-backed public sources (SearXNG/Naver/
Brave/Tavily/Serper/Jina) plus optional RSS feeds. The original China hot-list
API remains available only when MINDSPIDER_SOURCE_MODE=legacy_china or when
legacy source IDs are explicitly requested.
"""

import sys
import asyncio
import httpx
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from loguru import logger

# Add both MindSpider root and repository root to import path.
mindspider_root = Path(__file__).resolve().parents[1]
repo_root = Path(__file__).resolve().parents[2]
sys.path.extend([str(mindspider_root), str(repo_root)])

try:
    from BroadTopicExtraction.database_manager import DatabaseManager
    import config
    from source_providers import (
        BlueskySourceProvider,
        SearchBackedSourceProvider,
        RssSourceProvider,
        SourceProviderError,
        GitHubSourceProvider,
        HackerNewsSourceProvider,
        MastodonSourceProvider,
        RedditApiSourceProvider,
        RedditSourceProvider,
        XApiSourceProvider,
        YouTubeDataSourceProvider,
        YouTubeRssSourceProvider,
        YouTubeSearchSourceProvider,
    )
except ImportError as e:
    raise ImportError(f"导入模块失败: {e}")

# Legacy China-oriented hot-list API. Kept for explicit opt-in only.
BASE_URL = "https://newsnow.busiyi.world"

LEGACY_CHINA_SOURCE_NAMES = {
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "bilibili-hot-search": "B站热搜",
    "toutiao": "今日头条",
    "douyin": "抖音热榜",
    "github-trending-today": "GitHub趋势",
    "coolapk": "酷安热榜",
    "tieba": "百度贴吧",
    "wallstreetcn": "华尔街见闻",
    "thepaper": "澎湃新闻",
    "cls-hot": "财联社",
    "xueqiu": "雪球热榜",
}

LOCALIZED_SOURCE_NAMES = {
    "localized": "Localized provider search",
    "searxng": "SearXNG local search",
    "naver": "Naver Search",
    "brave": "Brave Search",
    "tavily": "Tavily Search",
    "serper": "Serper Search",
    "jina": "Jina Search",
    "rss": "RSS feeds",
    "hackernews": "Hacker News public API",
    "github": "GitHub repository search",
    "github-issues": "GitHub issue search",
    "reddit": "Reddit public search",
    "reddit-api": "Reddit official API search",
    "youtube": "YouTube search via configured web provider",
    "youtube-data": "YouTube Data API search",
    "youtube-rss": "YouTube channel RSS feeds",
    "bluesky": "Bluesky public post search",
    "mastodon": "Mastodon public/API status search",
    "x-api": "X/Twitter official API recent search",
}

# Backward-compatible exported name used by BroadTopicExtraction.main.
SOURCE_NAMES = {**LOCALIZED_SOURCE_NAMES, **LEGACY_CHINA_SOURCE_NAMES}


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class NewsCollector:
    """News/source collector feeding the existing DB/topic-analysis workflow."""

    def __init__(self, source_mode: Optional[str] = None, provider: Optional[str] = None, queries: Optional[Iterable[str]] = None, rss_feeds: Optional[Iterable[str]] = None, db_manager: Optional[Any] = None):
        self.settings = config.settings
        self.source_mode = (source_mode or getattr(self.settings, "MINDSPIDER_SOURCE_MODE", "localized")).lower()
        self.provider = (provider or getattr(self.settings, "MINDSPIDER_SOURCE_PROVIDER", "searxng")).lower()
        self.queries = list(queries) if queries is not None else _split_csv(getattr(self.settings, "MINDSPIDER_SOURCE_QUERIES", ""))
        if not self.queries:
            self.queries = ["AI", "technology", "market", "public opinion"]
        self.rss_feeds = list(rss_feeds) if rss_feeds is not None else _split_csv(getattr(self.settings, "MINDSPIDER_RSS_FEEDS", None))
        self.reddit_subreddits = _split_csv(getattr(self.settings, "MINDSPIDER_REDDIT_SUBREDDITS", None))
        self.youtube_channel_ids = _split_csv(getattr(self.settings, "MINDSPIDER_YOUTUBE_CHANNEL_IDS", None))
        self.mastodon_instance = getattr(self.settings, "MASTODON_INSTANCE", "mastodon.social")
        self.db_manager = db_manager or DatabaseManager()
        self.supported_sources = list(SOURCE_NAMES.keys())

    def close(self):
        if self.db_manager:
            self.db_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ==================== Localized source collection ====================

    async def collect_localized_sources(self, sources: Optional[List[str]] = None) -> List[dict]:
        """Collect source items from localized providers and optional RSS feeds."""
        selected = sources or [self.provider]
        results: List[dict] = []

        # `localized` means use the configured default provider.
        normalized_sources = [self.provider if source == "localized" else source for source in selected]

        for source in normalized_sources:
            if source == "rss":
                if not self.rss_feeds:
                    results.append({"source": "rss", "status": "skipped", "data": {"items": []}, "error": "MINDSPIDER_RSS_FEEDS is empty", "timestamp": datetime.now().isoformat()})
                    continue
                try:
                    provider = RssSourceProvider(self.rss_feeds, timeout=getattr(self.settings, "SEARCH_TIMEOUT", 30))
                    items = provider.collect(max_items_per_feed=getattr(self.settings, "SEARCH_MAX_RESULTS", 10))
                    results.append(self._source_items_to_result("rss", items))
                except SourceProviderError as exc:
                    if getattr(self.settings, "SEARCH_FAIL_CLOSED", True):
                        raise
                    results.append({"source": "rss", "status": "error", "data": {"items": []}, "error": str(exc), "timestamp": datetime.now().isoformat()})
                continue

            if source in {"hackernews", "github", "github-issues", "reddit", "reddit-api", "youtube", "youtube-data", "youtube-rss", "bluesky", "mastodon", "x-api"}:
                try:
                    items = self._collect_global_source(source)
                    results.append(self._source_items_to_result(source, items))
                except SourceProviderError as exc:
                    if getattr(self.settings, "SEARCH_FAIL_CLOSED", True):
                        raise
                    results.append({"source": source, "status": "error", "data": {"items": []}, "error": str(exc), "timestamp": datetime.now().isoformat()})
                continue

            try:
                provider = SearchBackedSourceProvider(
                    source,
                    market=getattr(self.settings, "SEARCH_MARKET", "global"),
                    fail_closed=getattr(self.settings, "SEARCH_FAIL_CLOSED", True),
                    settings_obj=self.settings,
                )
                items = provider.collect(self.queries, max_results_per_query=getattr(self.settings, "SEARCH_MAX_RESULTS", 10))
                results.append(self._source_items_to_result(source, items))
            except SourceProviderError as exc:
                if getattr(self.settings, "SEARCH_FAIL_CLOSED", True):
                    raise
                results.append({"source": source, "status": "error", "data": {"items": []}, "error": str(exc), "timestamp": datetime.now().isoformat()})

        return results

    def _collect_global_source(self, source: str):
        max_results = getattr(self.settings, "SEARCH_MAX_RESULTS", 10)
        timeout = getattr(self.settings, "SEARCH_TIMEOUT", 30)
        if source == "hackernews":
            return HackerNewsSourceProvider(timeout=timeout).collect(self.queries, max_results_per_query=max_results)
        if source == "github":
            return GitHubSourceProvider(timeout=timeout, token=getattr(self.settings, "GITHUB_TOKEN", None), mode="repositories").collect(self.queries, max_results_per_query=max_results)
        if source == "github-issues":
            return GitHubSourceProvider(timeout=timeout, token=getattr(self.settings, "GITHUB_TOKEN", None), mode="issues").collect(self.queries, max_results_per_query=max_results)
        if source == "reddit":
            return RedditSourceProvider(timeout=timeout, subreddits=self.reddit_subreddits).collect(self.queries, max_results_per_query=max_results)
        if source == "reddit-api":
            return RedditApiSourceProvider(
                timeout=timeout,
                subreddits=self.reddit_subreddits,
                client_id=getattr(self.settings, "REDDIT_CLIENT_ID", None),
                client_secret=getattr(self.settings, "REDDIT_CLIENT_SECRET", None),
            ).collect(self.queries, max_results_per_query=max_results)
        if source == "youtube":
            return YouTubeSearchSourceProvider(
                self.provider,
                timeout=timeout,
                settings_obj=self.settings,
                market=getattr(self.settings, "SEARCH_MARKET", "global"),
                fail_closed=getattr(self.settings, "SEARCH_FAIL_CLOSED", True),
            ).collect(self.queries, max_results_per_query=max_results)
        if source == "youtube-data":
            return YouTubeDataSourceProvider(timeout=timeout, api_key=getattr(self.settings, "YOUTUBE_DATA_API_KEY", None)).collect(self.queries, max_results_per_query=max_results)
        if source == "youtube-rss":
            if not self.youtube_channel_ids:
                raise SourceProviderError("MINDSPIDER_YOUTUBE_CHANNEL_IDS is empty")
            return YouTubeRssSourceProvider(self.youtube_channel_ids, timeout=timeout).collect(max_items_per_feed=max_results)
        if source == "bluesky":
            return BlueskySourceProvider(timeout=timeout, identifier=getattr(self.settings, "BLUESKY_IDENTIFIER", None), app_password=getattr(self.settings, "BLUESKY_APP_PASSWORD", None)).collect(self.queries, max_results_per_query=max_results)
        if source == "mastodon":
            return MastodonSourceProvider(timeout=timeout, instance=self.mastodon_instance, access_token=getattr(self.settings, "MASTODON_ACCESS_TOKEN", None)).collect(self.queries, max_results_per_query=max_results)
        if source == "x-api":
            return XApiSourceProvider(timeout=timeout, bearer_token=getattr(self.settings, "X_BEARER_TOKEN", None)).collect(self.queries, max_results_per_query=max_results)
        raise SourceProviderError(f"Unsupported global source: {source}")

    def _source_items_to_result(self, source: str, items) -> dict:
        return {
            "source": source,
            "status": "success",
            "data": {"items": [item.to_daily_news_record() for item in items]},
            "timestamp": datetime.now().isoformat(),
        }

    # ==================== Legacy China hot-list API ====================

    async def fetch_news(self, source: str) -> dict:
        """Fetch from the legacy China-oriented hot-list API."""
        url = f"{BASE_URL}/api/s?id={source}&latest"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": BASE_URL,
            "Connection": "keep-alive",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return {"source": source, "status": "success", "data": response.json(), "timestamp": datetime.now().isoformat()}
        except httpx.TimeoutException:
            return {"source": source, "status": "timeout", "error": f"请求超时: {source}({url})", "timestamp": datetime.now().isoformat()}
        except httpx.HTTPStatusError as e:
            return {"source": source, "status": "http_error", "error": f"HTTP错误: {source}({url}) - {e.response.status_code}", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"source": source, "status": "error", "error": f"未知错误: {source}({url}) - {str(e)}", "timestamp": datetime.now().isoformat()}

    async def get_popular_news(self, sources: Optional[List[str]] = None) -> List[dict]:
        """Get source/news data according to localized-vs-legacy mode."""
        if self.source_mode != "legacy_china":
            # If caller explicitly names legacy IDs, require explicit legacy mode.
            if sources and any(source in LEGACY_CHINA_SOURCE_NAMES for source in sources):
                raise SourceProviderError("Legacy China sources require MINDSPIDER_SOURCE_MODE=legacy_china")
            return await self.collect_localized_sources(sources)

        if sources is None:
            sources = list(LEGACY_CHINA_SOURCE_NAMES.keys())
        logger.info(f"正在获取 {len(sources)} 个 legacy China 新闻源的最新内容...")
        results = []
        for source in sources:
            source_name = LEGACY_CHINA_SOURCE_NAMES.get(source, source)
            logger.info(f"正在获取 {source_name} 的新闻...")
            result = await self.fetch_news(source)
            results.append(result)
            if result["status"] == "success":
                data = result["data"]
                count = len(data.get("items", [])) if isinstance(data, dict) and isinstance(data.get("items"), list) else 0
                logger.info(f"✓ {source_name}: 获取成功，共 {count} 条新闻")
            else:
                logger.error(f"✗ {source_name}: {result.get('error', '获取失败')}")
            await asyncio.sleep(0.5)
        return results

    # ==================== Processing and storage ====================

    async def collect_and_save_news(self, sources: Optional[List[str]] = None) -> Dict:
        collection_summary_message = ""
        collection_summary_message += "\n开始收集每日热点/来源数据...\n"
        collection_summary_message += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        collection_summary_message += f"Source mode: {self.source_mode}\n"
        if self.source_mode == "localized":
            collection_summary_message += f"Provider: {self.provider}\n"
            collection_summary_message += f"Queries: {', '.join(self.queries)}\n"
            if self.rss_feeds:
                collection_summary_message += f"RSS feeds: {len(self.rss_feeds)}\n"
        if sources:
            collection_summary_message += f"指定 source: {', '.join(sources)}\n"
        logger.info(collection_summary_message)

        try:
            results = await self.get_popular_news(sources)
            processed_data = self._process_news_results(results)
            if processed_data['news_list']:
                saved_count = self.db_manager.save_daily_news(processed_data['news_list'], date.today())
                processed_data['saved_count'] = saved_count
            self._print_collection_summary(processed_data)
            return processed_data
        except Exception as e:
            logger.exception(f"收集新闻/来源失败: {e}")
            return {'success': False, 'error': str(e), 'news_list': [], 'total_news': 0, 'successful_sources': 0, 'total_sources': 0}

    def _process_news_results(self, results: List[Dict]) -> Dict:
        news_list = []
        successful_sources = 0
        total_news = 0
        for result in results:
            source = result['source']
            status = result['status']
            if status == 'success':
                successful_sources += 1
                data = result['data']
                if 'items' in data and isinstance(data['items'], list):
                    source_news_count = len(data['items'])
                    total_news += source_news_count
                    for i, item in enumerate(data['items'], 1):
                        processed_news = self._process_news_item(item, source, i)
                        if processed_news:
                            news_list.append(processed_news)
            elif status == "skipped":
                logger.info(f"跳过 source {source}: {result.get('error', '')}")
        return {'success': True, 'news_list': news_list, 'successful_sources': successful_sources, 'total_sources': len(results), 'total_news': total_news, 'collection_time': datetime.now().isoformat()}

    def _process_news_item(self, item: Dict, source: str, rank: int) -> Optional[Dict]:
        try:
            if isinstance(item, dict):
                title = (item.get('title') or '无标题').strip()
                url = item.get('url', '')
                source_provider = item.get('source_provider') or item.get('source') or source
                source_platform = item.get('source_platform') or source_provider
                news_id = item.get('id') or f"{source_provider}_{source_platform}_{rank}"
                return {'id': news_id, 'title': title, 'url': url, 'source': source_platform, 'source_provider': source_provider, 'source_region': item.get('source_region', ''), 'rank': rank}
            title = str(item)[:100] if len(str(item)) > 100 else str(item)
            return {'id': f"{source}_rank_{rank}", 'title': title, 'url': '', 'source': source, 'rank': rank}
        except Exception as e:
            logger.exception(f"处理新闻项失败: {e}")
            return None

    def _print_collection_summary(self, data: Dict):
        collection_summary_message = ""
        collection_summary_message += f"\n总 source: {data['total_sources']}\n"
        collection_summary_message += f"成功 source 数: {data['successful_sources']}\n"
        collection_summary_message += f"总 item 数: {data['total_news']}\n"
        if 'saved_count' in data:
            collection_summary_message += f"已保存数: {data['saved_count']}\n"
        logger.info(collection_summary_message)

    def get_today_news(self) -> List[Dict]:
        try:
            return self.db_manager.get_daily_news(date.today())
        except Exception as e:
            logger.exception(f"获取今日新闻失败: {e}")
            return []


async def main():
    logger.info("测试新闻/source 收集器...")
    async with NewsCollector() as collector:
        result = await collector.collect_and_save_news()
        if result['success']:
            logger.info(f"收集成功！共获取 {result['total_news']} 条 item")
        else:
            logger.error(f"收集失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    asyncio.run(main())
