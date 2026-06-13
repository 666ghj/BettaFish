"""RSS source provider for localized MindSpider collection."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Any, Iterable, List, Optional
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .base import SourceItem, SourceProviderError


def _text(element: Optional[ET.Element], default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text.strip()


class RssSourceProvider:
    """Collect public RSS/Atom feeds without extra dependencies.

    RSS is a safe default extension for Korea/global public-opinion collection
    because it avoids platform login scraping while still adding source diversity.
    """

    def __init__(self, feeds: Iterable[str], *, timeout: int = 20):
        self.feeds = [feed.strip() for feed in feeds if feed and feed.strip()]
        self.timeout = timeout
        if not self.feeds:
            raise SourceProviderError("At least one RSS feed URL is required")

    def collect(self, max_items_per_feed: int = 20) -> List[SourceItem]:
        items: List[SourceItem] = []
        for feed_url in self.feeds:
            try:
                req = Request(feed_url, headers={"User-Agent": "BettaFish-localized/1.0"})
                with urlopen(req, timeout=self.timeout) as response:  # nosec B310 - user-configured public feeds
                    payload = response.read()
                root = ET.fromstring(payload)
            except Exception as exc:
                raise SourceProviderError(f"RSS feed collection failed for {feed_url}: {exc}") from exc

            feed_items = self._parse_feed(root, feed_url)[:max_items_per_feed]
            items.extend(feed_items)
        return items

    def _parse_feed(self, root: ET.Element, feed_url: str) -> List[SourceItem]:
        # RSS 2.0: channel/item. Atom: {namespace}entry.
        rss_items = root.findall(".//item")
        if rss_items:
            return [self._from_rss_item(item, feed_url) for item in rss_items]
        atom_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        return [self._from_atom_entry(entry, feed_url) for entry in atom_items]

    def _from_rss_item(self, item: ET.Element, feed_url: str) -> SourceItem:
        title = _text(item.find("title"), "Untitled")
        link = _text(item.find("link"))
        description = _text(item.find("description"))
        pub_date = _text(item.find("pubDate"))
        return SourceItem(
            title=title,
            url=link,
            snippet=description,
            source_provider="rss",
            source_region="global",
            source_platform="rss",
            published_date=pub_date,
            raw={"feed_url": feed_url},
        )

    def _from_atom_entry(self, entry: ET.Element, feed_url: str) -> SourceItem:
        ns = "{http://www.w3.org/2005/Atom}"
        title = _text(entry.find(f"{ns}title"), "Untitled")
        link_el = entry.find(f"{ns}link")
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        summary = _text(entry.find(f"{ns}summary")) or _text(entry.find(f"{ns}content"))
        updated = _text(entry.find(f"{ns}updated")) or _text(entry.find(f"{ns}published"))
        return SourceItem(
            title=title,
            url=link,
            snippet=summary,
            source_provider="rss",
            source_region="global",
            source_platform="rss",
            published_date=updated,
            raw={"feed_url": feed_url},
        )
