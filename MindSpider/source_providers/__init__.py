"""Localized MindSpider source provider layer.

This package separates source discovery from downstream DB/analysis/report flows.
The original China platform crawlers remain available as explicit legacy opt-in
modules; localized defaults should use SearXNG/Naver/Brave/RSS-style providers.
"""

from .base import SourceItem, SourceProviderError, SearchBackedSourceProvider, LegacyChinaSourceProvider
from .rss import RssSourceProvider
from .global_sources import (
    BlueskySourceProvider,
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

__all__ = [
    "SourceItem",
    "SourceProviderError",
    "SearchBackedSourceProvider",
    "LegacyChinaSourceProvider",
    "RssSourceProvider",
    "BlueskySourceProvider",
    "GitHubSourceProvider",
    "HackerNewsSourceProvider",
    "MastodonSourceProvider",
    "RedditApiSourceProvider",
    "RedditSourceProvider",
    "XApiSourceProvider",
    "YouTubeDataSourceProvider",
    "YouTubeRssSourceProvider",
    "YouTubeSearchSourceProvider",
]
