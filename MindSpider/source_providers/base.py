"""Provider interfaces for localized MindSpider source discovery.

This is the first safe slice of the MindSpider transformation: keep the existing
DB/sentiment/report workflow, but make source collection explicit and swappable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from localized_search import LocalizedSearchClient, SearchProviderError


@dataclass
class SourceItem:
    title: str
    url: str
    snippet: str = ""
    source_provider: str = ""
    source_region: str = "global"
    source_platform: str = "web"
    published_date: Optional[str] = None
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_daily_news_record(self) -> Dict[str, Any]:
        """Compatibility shape for BroadTopicExtraction daily-news flows."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.snippet,
            "summary": self.snippet,
            "source": self.source_provider,
            "source_platform": self.source_platform,
            "source_provider": self.source_provider,
            "source_region": self.source_region,
            "published_date": self.published_date,
            "collected_at": self.collected_at,
            "raw": self.raw,
        }


class SourceProviderError(RuntimeError):
    pass


class SearchBackedSourceProvider:
    """MindSpider source provider backed by localized_search adapters.

    Use for SearXNG(default), Brave, Naver, Tavily, Serper, or Jina discovery.
    Provider/key failures are intentionally fail-closed by default.
    """

    def __init__(self, provider: str = "searxng", *, market: str = "global", fail_closed: bool = True, settings_obj: Optional[Any] = None):
        self.provider = provider
        self.market = market
        self.client = LocalizedSearchClient(provider=provider, fail_closed=fail_closed, settings_obj=settings_obj)

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        for query in queries:
            try:
                response = self.client.search(query, max_results=max_results_per_query, market=self.market)
            except SearchProviderError as exc:
                raise SourceProviderError(f"{self.provider} source discovery failed for {query!r}: {exc}") from exc
            for result in response.results:
                items.append(
                    SourceItem(
                        title=result.title,
                        url=result.url,
                        snippet=result.snippet,
                        source_provider=response.provider,
                        source_region=self.market,
                        source_platform="web_search",
                        published_date=result.published_date,
                        raw=result.raw,
                    )
                )
        return items


class LegacyChinaSourceProvider:
    """Explicit marker for original China platform crawler opt-in.

    This class does not run MediaCrawler directly; it documents/enforces that
    China-focused platforms are not the localized default path.
    """

    platforms = ("xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu")

    def collect(self, *_args: Any, **_kwargs: Any) -> List[SourceItem]:
        raise SourceProviderError(
            "Legacy China crawlers are opt-in only. Use PlatformCrawler explicitly "
            "after selecting legacy_china mode and confirming platform/legal/login requirements."
        )
