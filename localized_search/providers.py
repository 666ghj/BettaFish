"""Localized search provider adapters for BettaFish-localized.

This module is intentionally dependency-light (requests only) so it can be used by
QueryEngine/MediaEngine/MindSpider before deeper agent refactors. It normalizes
Korean/global search providers into one shape and fails closed by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os
import requests


@dataclass
class LocalizedSearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_date: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    # Compatibility aliases for upstream QueryEngine/MediaEngine result shapes.
    @property
    def content(self) -> str:
        return self.snippet

    @property
    def raw_content(self) -> str:
        return self.snippet

    @property
    def score(self) -> Optional[float]:
        return None

    @property
    def name(self) -> str:
        return self.title

    @property
    def date_last_crawled(self) -> Optional[str]:
        return self.published_date


@dataclass
class LocalizedSearchResponse:
    query: str
    provider: str
    results: List[LocalizedSearchResult] = field(default_factory=list)
    answer: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    # Compatibility alias for upstream MediaEngine BochaResponse shape.
    @property
    def webpages(self) -> List[LocalizedSearchResult]:
        return self.results


class SearchProviderError(RuntimeError):
    pass


def _clean_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return (
        text.replace("<b>", "")
        .replace("</b>", "")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .strip()
    )


class LocalizedSearchClient:
    """Provider router for global/Korean-friendly search APIs.

    Supported provider names:
    - searxng: bundled self-hosted/free metasearch; default for Docker Compose.
    - brave: global independent web index; opt in when user can issue a key.
    - naver: Korean news/web/blog/local coverage; use for Korea-first workflows.
    - serper: Google-style global results; useful when broad recall matters.
    - jina: lightweight search/reader style retrieval; useful for research snippets.
    - searxng: self-hosted/free metasearch; best for no commercial API key setups.
    """

    def __init__(self, provider: Optional[str] = None, fail_closed: bool = True, timeout: int = 30, settings_obj: Optional[Any] = None):
        self.settings_obj = settings_obj
        self.provider = (provider or self._config("SEARCH_PROVIDER") or "searxng").lower()
        self.fail_closed = fail_closed
        self.timeout = timeout

    def _config(self, name: str, default: Optional[str] = None) -> Optional[str]:
        if self.settings_obj is not None:
            value = getattr(self.settings_obj, name, None)
            if value not in (None, ""):
                return str(value)
        value = os.getenv(name)
        return value if value not in (None, "") else default


    # Upstream tool-name compatibility methods.
    def basic_search_news(self, query: str, max_results: int = 7) -> LocalizedSearchResponse:
        return self.search(query, max_results=max_results)

    def deep_search_news(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=20)

    def search_news_last_24_hours(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=10)

    def search_news_last_week(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=10)

    def search_images_for_news(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=5)

    def search_news_by_date(self, query: str, start_date: str, end_date: str) -> LocalizedSearchResponse:
        return self.search(f"{query} after:{start_date} before:{end_date}", max_results=15)

    def comprehensive_search(self, query: str, max_results: int = 10) -> LocalizedSearchResponse:
        return self.search(query, max_results=max_results)

    def web_search_only(self, query: str, max_results: int = 15) -> LocalizedSearchResponse:
        return self.search(query, max_results=max_results)

    def search_for_structured_data(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=10)

    def search_last_24_hours(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=10)

    def search_last_week(self, query: str) -> LocalizedSearchResponse:
        return self.search(query, max_results=10)

    def search(self, query: str, max_results: int = 10, market: str = "global") -> LocalizedSearchResponse:
        try:
            if self.provider == "brave":
                return self._brave(query, max_results, market)
            if self.provider == "naver":
                return self._naver(query, max_results)
            if self.provider == "tavily":
                return self._tavily(query, max_results)
            if self.provider == "serper":
                return self._serper(query, max_results)
            if self.provider == "jina":
                return self._jina(query, max_results)
            if self.provider == "searxng":
                return self._searxng(query, max_results)
            raise SearchProviderError(f"Unsupported localized search provider: {self.provider}")
        except Exception as exc:
            if self.fail_closed:
                raise SearchProviderError(f"{self.provider} search failed: {exc}") from exc
            return LocalizedSearchResponse(query=query, provider=self.provider, error=str(exc))

    def _brave(self, query: str, max_results: int, market: str) -> LocalizedSearchResponse:
        key = self._config("BRAVE_SEARCH_API_KEY")
        if not key:
            raise SearchProviderError("BRAVE_SEARCH_API_KEY is required")
        base = self._config("BRAVE_SEARCH_BASE_URL", "https://api.search.brave.com/res/v1/web/search")
        country = "KR" if market == "korea" else None
        headers = {"X-Subscription-Token": key, "Accept": "application/json"}
        params = {"q": query, "count": max_results}
        if country:
            params["country"] = country
        resp = requests.get(base, headers=headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("web", {}).get("results", [])
        return LocalizedSearchResponse(
            query=query,
            provider="brave",
            results=[LocalizedSearchResult(title=i.get("title", ""), url=i.get("url", ""), snippet=i.get("description", ""), source="brave", raw=i) for i in items[:max_results]],
        )

    def _naver(self, query: str, max_results: int) -> LocalizedSearchResponse:
        client_id = self._config("NAVER_CLIENT_ID")
        client_secret = self._config("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise SearchProviderError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")
        base = self._config("NAVER_SEARCH_BASE_URL", "https://openapi.naver.com/v1/search/news.json")
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
        resp = requests.get(base, headers=headers, params={"query": query, "display": min(max_results, 100)}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LocalizedSearchResponse(
            query=query,
            provider="naver",
            results=[LocalizedSearchResult(title=_clean_html(i.get("title")), url=i.get("originallink") or i.get("link", ""), snippet=_clean_html(i.get("description")), source="naver", published_date=i.get("pubDate"), raw=i) for i in data.get("items", [])[:max_results]],
        )

    def _tavily(self, query: str, max_results: int) -> LocalizedSearchResponse:
        key = self._config("TAVILY_API_KEY")
        if not key:
            raise SearchProviderError("TAVILY_API_KEY is required")
        base = self._config("TAVILY_BASE_URL", "https://api.tavily.com/search")
        payload = {"api_key": key, "query": query, "max_results": max_results, "include_answer": True}
        resp = requests.post(base, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LocalizedSearchResponse(
            query=query,
            provider="tavily",
            results=[LocalizedSearchResult(title=i.get("title", ""), url=i.get("url", ""), snippet=i.get("content", ""), source="tavily", raw=i) for i in data.get("results", [])[:max_results]],
            answer=data.get("answer"),
        )

    def _serper(self, query: str, max_results: int) -> LocalizedSearchResponse:
        key = self._config("SERPER_API_KEY")
        if not key:
            raise SearchProviderError("SERPER_API_KEY is required")
        base = self._config("SERPER_BASE_URL", "https://google.serper.dev/search")
        headers = {"X-API-KEY": key, "Content-Type": "application/json"}
        resp = requests.post(base, headers=headers, json={"q": query, "num": max_results}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LocalizedSearchResponse(
            query=query,
            provider="serper",
            results=[LocalizedSearchResult(title=i.get("title", ""), url=i.get("link", ""), snippet=i.get("snippet", ""), source="serper", raw=i) for i in data.get("organic", [])[:max_results]],
            answer=(data.get("answerBox") or {}).get("answer"),
        )

    def _jina(self, query: str, max_results: int) -> LocalizedSearchResponse:
        base = self._config("JINA_SEARCH_BASE_URL", "https://s.jina.ai/")
        headers = {}
        if self._config("JINA_API_KEY"):
            headers["Authorization"] = f"Bearer {self._config('JINA_API_KEY')}"
        resp = requests.get(base, headers=headers, params={"q": query}, timeout=self.timeout)
        resp.raise_for_status()
        lines = [line.strip() for line in resp.text.splitlines() if line.strip()]
        results: List[LocalizedSearchResult] = []
        current: Dict[str, str] = {}
        for line in lines:
            if line.startswith("Title:"):
                if current.get("title") or current.get("url"):
                    results.append(LocalizedSearchResult(title=current.get("title", ""), url=current.get("url", ""), snippet=current.get("snippet", ""), source="jina", raw=dict(current)))
                    current = {}
                current["title"] = line.replace("Title:", "", 1).strip()
            elif line.startswith("URL Source:") or line.startswith("URL:"):
                current["url"] = line.split(":", 1)[1].strip()
            elif "snippet" not in current and not line.startswith(("[", "Markdown Content")):
                current["snippet"] = line[:500]
        if current.get("title") or current.get("url"):
            results.append(LocalizedSearchResult(title=current.get("title", ""), url=current.get("url", ""), snippet=current.get("snippet", ""), source="jina", raw=dict(current)))
        return LocalizedSearchResponse(query=query, provider="jina", results=results[:max_results])

    def _searxng(self, query: str, max_results: int) -> LocalizedSearchResponse:
        base = self._config("SEARXNG_BASE_URL")
        if not base:
            raise SearchProviderError("SEARXNG_BASE_URL is required")
        url = base.rstrip("/") + "/search"
        resp = requests.get(url, params={"q": query, "format": "json"}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LocalizedSearchResponse(
            query=query,
            provider="searxng",
            results=[LocalizedSearchResult(title=i.get("title", ""), url=i.get("url", ""), snippet=i.get("content", ""), source="searxng", raw=i) for i in data.get("results", [])[:max_results]],
        )
