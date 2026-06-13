"""Global public/API-backed source providers for localized MindSpider collection.

These adapters keep SNS/community collection explicit and auditable. Public/no-key
sources are preferred first; official API/key-backed sources fail closed when the
required credential is missing. Browser/session crawling is intentionally not part
of this baseline module.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen

from .base import SearchBackedSourceProvider, SourceItem, SourceProviderError
from .rss import RssSourceProvider


USER_AGENT = "BettaFish-localized/1.0 (+https://github.com/YunyueLi/MiroMind)"


def _json_get(url: str, *, timeout: int = 20, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    try:
        req = Request(url, headers=req_headers)
        with urlopen(req, timeout=timeout) as response:  # nosec B310 - fixed public APIs or user query parameters
            payload = response.read().decode("utf-8", errors="replace")
        return json.loads(payload)
    except Exception as exc:
        raise SourceProviderError(f"Global source request failed for {url}: {exc}") from exc


def _json_post_form(url: str, data: Dict[str, str], *, timeout: int = 20, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        req_headers.update(headers)
    try:
        payload = urlencode(data).encode("utf-8")
        req = Request(url, data=payload, headers=req_headers, method="POST")
        with urlopen(req, timeout=timeout) as response:  # nosec B310 - fixed public API endpoint
            body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)
    except Exception as exc:
        raise SourceProviderError(f"Global source POST failed for {url}: {exc}") from exc




def _json_post_json(url: str, data: Dict[str, str], *, timeout: int = 20, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    try:
        payload = json.dumps(data).encode("utf-8")
        req = Request(url, data=payload, headers=req_headers, method="POST")
        with urlopen(req, timeout=timeout) as response:  # nosec B310 - fixed public API endpoint
            body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)
    except Exception as exc:
        raise SourceProviderError(f"Global source JSON POST failed for {url}: {exc}") from exc

def _require(value: Optional[str], name: str) -> str:
    if not value:
        raise SourceProviderError(f"{name} is required for this source")
    return value


class HackerNewsSourceProvider:
    """Collect Hacker News stories via the public Algolia HN API."""

    base_url = "https://hn.algolia.com/api/v1/search"

    def __init__(self, *, timeout: int = 20):
        self.timeout = timeout

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        for query in queries:
            params = urlencode({"query": query, "tags": "story", "hitsPerPage": max_results_per_query})
            data = _json_get(f"{self.base_url}?{params}", timeout=self.timeout)
            for hit in data.get("hits", [])[:max_results_per_query]:
                title = hit.get("title") or hit.get("story_title") or "Untitled HN story"
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                snippet = hit.get("story_text") or hit.get("comment_text") or ""
                items.append(SourceItem(title=title, url=url, snippet=snippet, source_provider="hackernews", source_region="global", source_platform="hackernews", published_date=hit.get("created_at"), raw=hit))
        return items


class GitHubSourceProvider:
    """Collect repositories/issues through GitHub public search APIs."""

    def __init__(self, *, timeout: int = 20, token: Optional[str] = None, mode: str = "repositories"):
        self.timeout = timeout
        self.token = token
        self.mode = mode

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        for query in queries:
            if self.mode == "issues":
                url = "https://api.github.com/search/issues?" + urlencode({"q": query, "sort": "updated", "order": "desc", "per_page": max_results_per_query})
            else:
                url = "https://api.github.com/search/repositories?" + urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": max_results_per_query})
            headers = {"Accept": "application/vnd.github+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            data = _json_get(url, timeout=self.timeout, headers=headers)
            if "message" in data and "items" not in data:
                raise SourceProviderError(f"GitHub source failed: {data.get('message')}")
            for item in data.get("items", [])[:max_results_per_query]:
                if self.mode == "issues":
                    title = item.get("title", "Untitled GitHub issue")
                    snippet = item.get("body") or ""
                    platform = "github_issues"
                else:
                    title = item.get("full_name") or item.get("name") or "Untitled GitHub repository"
                    snippet = item.get("description") or ""
                    platform = "github_repositories"
                items.append(SourceItem(title=title, url=item.get("html_url", ""), snippet=snippet, source_provider="github", source_region="global", source_platform=platform, published_date=item.get("updated_at") or item.get("created_at"), raw=item))
        return items


class RedditSourceProvider:
    """Collect public Reddit search results without login."""

    def __init__(self, *, timeout: int = 20, subreddits: Optional[Iterable[str]] = None):
        self.timeout = timeout
        self.subreddits = [s.strip().strip("/") for s in (subreddits or []) if s and s.strip()]

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        for query in queries:
            targets = self.subreddits or [""]
            for subreddit in targets:
                prefix = f"https://www.reddit.com/r/{subreddit}/search.json" if subreddit else "https://www.reddit.com/search.json"
                params = urlencode({"q": query, "limit": max_results_per_query, "sort": "relevance", "restrict_sr": "on" if subreddit else "off"})
                data = _json_get(f"{prefix}?{params}", timeout=self.timeout)
                children = data.get("data", {}).get("children", [])
                items.extend(_reddit_children_to_items(children[:max_results_per_query], provider="reddit"))
        return items


class RedditApiSourceProvider:
    """Collect Reddit through official OAuth client-credentials API."""

    token_url = "https://www.reddit.com/api/v1/access_token"
    api_base = "https://oauth.reddit.com"

    def __init__(self, *, client_id: Optional[str], client_secret: Optional[str], timeout: int = 20, subreddits: Optional[Iterable[str]] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.subreddits = [s.strip().strip("/") for s in (subreddits or []) if s and s.strip()]
        self._token: Optional[str] = None

    def _access_token(self) -> str:
        if self._token:
            return self._token
        client_id = _require(self.client_id, "REDDIT_CLIENT_ID")
        client_secret = _require(self.client_secret, "REDDIT_CLIENT_SECRET")
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        data = _json_post_form(self.token_url, {"grant_type": "client_credentials"}, timeout=self.timeout, headers={"Authorization": f"Basic {basic}"})
        token = data.get("access_token")
        if not token:
            raise SourceProviderError("Reddit API token response did not include access_token")
        self._token = token
        return token

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        token = self._access_token()
        items: List[SourceItem] = []
        headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
        for query in queries:
            targets = self.subreddits or [""]
            for subreddit in targets:
                path = f"/r/{subreddit}/search" if subreddit else "/search"
                params = urlencode({"q": query, "limit": max_results_per_query, "sort": "relevance", "restrict_sr": "true" if subreddit else "false"})
                data = _json_get(f"{self.api_base}{path}?{params}", timeout=self.timeout, headers=headers)
                children = data.get("data", {}).get("children", [])
                items.extend(_reddit_children_to_items(children[:max_results_per_query], provider="reddit-api"))
        return items


def _reddit_children_to_items(children: Iterable[Dict[str, Any]], *, provider: str) -> List[SourceItem]:
    items: List[SourceItem] = []
    for child in children:
        post = child.get("data", {})
        permalink = post.get("permalink", "")
        items.append(SourceItem(title=post.get("title", "Untitled Reddit post"), url=("https://www.reddit.com" + permalink) if permalink.startswith("/") else post.get("url", ""), snippet=post.get("selftext") or post.get("url_overridden_by_dest") or "", source_provider=provider, source_region="global", source_platform="reddit", published_date=str(post.get("created_utc", "")) or None, raw=post))
    return items


class YouTubeSearchSourceProvider:
    """Collect YouTube results through the configured web-search provider."""

    def __init__(self, provider: str = "searxng", *, timeout: int = 20, settings_obj: Optional[Any] = None, market: str = "global", fail_closed: bool = True):
        self.search = SearchBackedSourceProvider(provider, market=market, fail_closed=fail_closed, settings_obj=settings_obj)

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        site_queries = [f"site:youtube.com/watch {query}" for query in queries]
        items = self.search.collect(site_queries, max_results_per_query=max_results_per_query)
        for item in items:
            item.source_provider = "youtube"
            item.source_platform = "youtube_search"
            item.raw = {**item.raw, "discovery_provider": self.search.provider}
        return items


class YouTubeRssSourceProvider(RssSourceProvider):
    """Collect YouTube channel feeds from explicit channel IDs."""

    def __init__(self, channel_ids: Iterable[str], *, timeout: int = 20):
        feeds = [f"https://www.youtube.com/feeds/videos.xml?channel_id={quote_plus(channel_id.strip())}" for channel_id in channel_ids if channel_id and channel_id.strip()]
        super().__init__(feeds, timeout=timeout)


class YouTubeDataSourceProvider:
    """Collect YouTube video search metadata through the official Data API."""

    base_url = "https://www.googleapis.com/youtube/v3/search"

    def __init__(self, *, api_key: Optional[str], timeout: int = 20):
        self.api_key = api_key
        self.timeout = timeout

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        api_key = _require(self.api_key, "YOUTUBE_DATA_API_KEY")
        items: List[SourceItem] = []
        for query in queries:
            params = urlencode({"part": "snippet", "type": "video", "q": query, "maxResults": max_results_per_query, "key": api_key})
            data = _json_get(f"{self.base_url}?{params}", timeout=self.timeout)
            if "error" in data:
                message = data.get("error", {}).get("message", "unknown YouTube API error")
                raise SourceProviderError(f"YouTube Data API failed: {message}")
            for item in data.get("items", [])[:max_results_per_query]:
                video_id = item.get("id", {}).get("videoId", "")
                snippet = item.get("snippet", {})
                items.append(SourceItem(title=snippet.get("title", "Untitled YouTube video"), url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "", snippet=snippet.get("description", ""), source_provider="youtube-data", source_region="global", source_platform="youtube", published_date=snippet.get("publishedAt"), raw=item))
        return items


class BlueskySourceProvider:
    """Collect Bluesky posts through AT Protocol appview.

    The public appview is tried without credentials. If it is blocked by the
    instance, configure `BLUESKY_IDENTIFIER` + `BLUESKY_APP_PASSWORD` to use an
    official app-password session. This remains API-backed, not browser scraping.
    """

    base_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
    session_url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    authed_base_url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"

    def __init__(self, *, timeout: int = 20, identifier: Optional[str] = None, app_password: Optional[str] = None):
        self.timeout = timeout
        self.identifier = identifier
        self.app_password = app_password
        self._access_jwt: Optional[str] = None

    def _headers(self) -> Optional[Dict[str, str]]:
        if not self.identifier and not self.app_password:
            return None
        identifier = _require(self.identifier, "BLUESKY_IDENTIFIER")
        app_password = _require(self.app_password, "BLUESKY_APP_PASSWORD")
        if not self._access_jwt:
            data = _json_post_json(self.session_url, {"identifier": identifier, "password": app_password}, timeout=self.timeout)
            jwt = data.get("accessJwt")
            if not jwt:
                raise SourceProviderError("Bluesky session response did not include accessJwt")
            self._access_jwt = jwt
        return {"Authorization": f"Bearer {self._access_jwt}"}

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        headers = self._headers()
        endpoint = self.authed_base_url if headers else self.base_url
        for query in queries:
            params = urlencode({"q": query, "limit": max_results_per_query})
            data = _json_get(f"{endpoint}?{params}", timeout=self.timeout, headers=headers)
            for post in data.get("posts", [])[:max_results_per_query]:
                record = post.get("record", {})
                author = post.get("author", {})
                handle = author.get("handle", "unknown")
                uri = post.get("uri", "")
                post_id = uri.rsplit("/", 1)[-1] if uri else ""
                url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else f"https://bsky.app/profile/{handle}"
                text = record.get("text", "")
                title = text.splitlines()[0][:100] if text else f"Bluesky post by @{handle}"
                items.append(SourceItem(title=title, url=url, snippet=text, source_provider="bluesky", source_region="global", source_platform="bluesky", published_date=record.get("createdAt") or post.get("indexedAt"), raw=post))
        return items


class MastodonSourceProvider:
    """Collect Mastodon statuses from an instance search or hashtag timeline."""

    def __init__(self, *, instance: str = "mastodon.social", access_token: Optional[str] = None, timeout: int = 20):
        self.instance = instance.replace("https://", "").strip("/") or "mastodon.social"
        self.access_token = access_token
        self.timeout = timeout

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        items: List[SourceItem] = []
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else None
        for query in queries:
            clean = query.strip().lstrip("#")
            if " " not in clean and clean:
                url = f"https://{self.instance}/api/v1/timelines/tag/{quote_plus(clean)}?" + urlencode({"limit": max_results_per_query})
                data = _json_get(url, timeout=self.timeout, headers=headers)
                statuses = data if isinstance(data, list) else []
            else:
                url = f"https://{self.instance}/api/v2/search?" + urlencode({"q": query, "type": "statuses", "limit": max_results_per_query})
                data = _json_get(url, timeout=self.timeout, headers=headers)
                statuses = data.get("statuses", []) if isinstance(data, dict) else []
            for status in statuses[:max_results_per_query]:
                account = status.get("account", {})
                title = (status.get("content", "") or f"Mastodon post by @{account.get('acct', 'unknown')}").replace("<p>", "").replace("</p>", "")[:100]
                items.append(SourceItem(title=title, url=status.get("url", ""), snippet=status.get("content", ""), source_provider="mastodon", source_region="global", source_platform="mastodon", published_date=status.get("created_at"), raw=status))
        return items


class XApiSourceProvider:
    """Collect X/Twitter recent search via the official API v2 bearer token."""

    base_url = "https://api.twitter.com/2/tweets/search/recent"

    def __init__(self, *, bearer_token: Optional[str], timeout: int = 20):
        self.bearer_token = bearer_token
        self.timeout = timeout

    def collect(self, queries: Iterable[str], max_results_per_query: int = 10) -> List[SourceItem]:
        token = _require(self.bearer_token, "X_BEARER_TOKEN")
        items: List[SourceItem] = []
        headers = {"Authorization": f"Bearer {token}"}
        for query in queries:
            params = urlencode({"query": query, "max_results": max(10, min(max_results_per_query, 100)), "tweet.fields": "created_at,author_id,lang,public_metrics"})
            data = _json_get(f"{self.base_url}?{params}", timeout=self.timeout, headers=headers)
            if "errors" in data and "data" not in data:
                raise SourceProviderError(f"X API failed: {data.get('errors')}")
            for tweet in data.get("data", [])[:max_results_per_query]:
                tweet_id = tweet.get("id", "")
                text = tweet.get("text", "")
                title = text.splitlines()[0][:100] if text else "X post"
                items.append(SourceItem(title=title, url=f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "", snippet=text, source_provider="x-api", source_region="global", source_platform="x", published_date=tweet.get("created_at"), raw=tweet))
        return items
