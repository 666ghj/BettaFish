#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Western News Collection Module
Collects news from USA and Western media sources via RSS feeds
Supports: Google News, major news outlets (left/right/center political spectrum)
"""

import sys
import asyncio
import hashlib
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from time import mktime
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    feedparser = None

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False
    UserAgent = None


# Western news sources configuration
# Format: source_id -> (name, rss_url, political_lean, category)
WESTERN_NEWS_SOURCES = {
    # Left-leaning sources
    "cnn": {
        "name": "CNN",
        "rss": "http://rss.cnn.com/rss/cnn_topstories.rss",
        "political_lean": "left",
        "category": "general"
    },
    "cnn_politics": {
        "name": "CNN Politics",
        "rss": "http://rss.cnn.com/rss/cnn_allpolitics.rss",
        "political_lean": "left",
        "category": "politics"
    },
    "nytimes": {
        "name": "New York Times",
        "rss": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "political_lean": "left",
        "category": "general"
    },
    "washpost": {
        "name": "Washington Post",
        "rss": "https://feeds.washingtonpost.com/rss/politics",
        "political_lean": "left",
        "category": "politics"
    },
    "npr": {
        "name": "NPR",
        "rss": "https://feeds.npr.org/1001/rss.xml",
        "political_lean": "left",
        "category": "general"
    },

    # Right-leaning sources
    "foxnews": {
        "name": "Fox News",
        "rss": "https://moxie.foxnews.com/google-publisher/latest.xml",
        "political_lean": "right",
        "category": "general"
    },
    "foxnews_politics": {
        "name": "Fox News Politics",
        "rss": "https://moxie.foxnews.com/google-publisher/politics.xml",
        "political_lean": "right",
        "category": "politics"
    },
    "nypost": {
        "name": "New York Post",
        "rss": "https://nypost.com/feed/",
        "political_lean": "right",
        "category": "general"
    },

    # Center/balanced sources
    "reuters": {
        "name": "Reuters",
        "rss": "https://www.reutersagency.com/feed/",
        "political_lean": "center",
        "category": "general"
    },
    "bbc": {
        "name": "BBC News",
        "rss": "http://feeds.bbci.co.uk/news/rss.xml",
        "political_lean": "center",
        "category": "general"
    },
    "wsj": {
        "name": "Wall Street Journal",
        "rss": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "political_lean": "center",
        "category": "business"
    },

    # Tech sources
    "techcrunch": {
        "name": "TechCrunch",
        "rss": "https://techcrunch.com/feed/",
        "political_lean": "center",
        "category": "tech"
    },
    "theverge": {
        "name": "The Verge",
        "rss": "https://www.theverge.com/rss/index.xml",
        "political_lean": "center",
        "category": "tech"
    },
    "wired": {
        "name": "Wired",
        "rss": "https://www.wired.com/feed/rss",
        "political_lean": "center",
        "category": "tech"
    },

    # Google News - Various topics
    "google_news_us": {
        "name": "Google News USA",
        "rss": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "political_lean": "center",
        "category": "general"
    },
    "google_news_politics": {
        "name": "Google News Politics",
        "rss": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNRFZxYUdjU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US:en",
        "political_lean": "center",
        "category": "politics"
    },
    "google_news_tech": {
        "name": "Google News Technology",
        "rss": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "political_lean": "center",
        "category": "tech"
    }
}


class WesternNewsCollector:
    """Western news collector - RSS feed based collection"""

    def __init__(self, rate_limit_delay: float = 2.0):
        """
        Initialize Western news collector

        Args:
            rate_limit_delay: Delay between requests in seconds (default: 2.0)
        """
        if not FEEDPARSER_AVAILABLE:
            raise ImportError("feedparser not installed. Install with: pip install feedparser")
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx not installed. Install with: pip install httpx")

        self.rate_limit_delay = rate_limit_delay
        self.ua = UserAgent() if FAKE_UA_AVAILABLE else None
        self.supported_sources = list(WESTERN_NEWS_SOURCES.keys())

    def close(self):
        """Close resources"""
        pass  # No resources to close currently

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _generate_article_id(self, url: str) -> str:
        """Generate unique article ID from URL"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:32]

    def _get_user_agent(self) -> str:
        """Get a user agent string"""
        if self.ua:
            return self.ua.random
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    async def fetch_rss_feed(self, source_id: str) -> Dict[str, Any]:
        """
        Fetch RSS feed from a news source

        Args:
            source_id: Source identifier from WESTERN_NEWS_SOURCES

        Returns:
            Dictionary with feed data or error info
        """
        if source_id not in WESTERN_NEWS_SOURCES:
            return {
                "source": source_id,
                "status": "error",
                "error": f"Unknown source: {source_id}"
            }

        source_info = WESTERN_NEWS_SOURCES[source_id]
        rss_url = source_info["rss"]

        try:
            # Use custom headers to avoid blocking
            headers = {
                "User-Agent": self._get_user_agent(),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }

            # Fetch RSS feed
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(rss_url, headers=headers)
                response.raise_for_status()

                # Parse RSS feed
                feed = feedparser.parse(response.text)

                if feed.bozo:  # Feed parsing error
                    logger.warning(f"Feed parsing warning for {source_id}: {feed.bozo_exception}")

                articles = []
                for entry in feed.entries[:20]:  # Limit to 20 most recent articles
                    article = self._parse_rss_entry(entry, source_id, source_info)
                    if article:
                        articles.append(article)

                return {
                    "source": source_id,
                    "status": "success",
                    "articles": articles,
                    "count": len(articles),
                    "timestamp": datetime.now().isoformat()
                }

        except httpx.TimeoutException:
            return {
                "source": source_id,
                "status": "timeout",
                "error": f"Request timeout: {source_id}",
                "timestamp": datetime.now().isoformat()
            }
        except httpx.HTTPStatusError as e:
            return {
                "source": source_id,
                "status": "http_error",
                "error": f"HTTP error: {e.response.status_code}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "source": source_id,
                "status": "error",
                "error": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _parse_rss_entry(self, entry, source_id: str, source_info: Dict) -> Optional[Dict]:
        """Parse a single RSS entry"""
        try:
            # Get article URL
            url = entry.get('link', '')
            if not url:
                return None

            # Parse published date
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = int(mktime(entry.published_parsed))

            # Extract title and description
            title = entry.get('title', 'No title').strip()
            description = entry.get('summary', '') or entry.get('description', '')

            # Clean HTML tags from description
            description = unescape(description)
            description = re.sub('<[^<]+?>', '', description)  # Remove HTML tags
            description = description.strip()

            # Get author
            author = entry.get('author', '') or entry.get('dc:creator', '')

            return {
                'article_id': self._generate_article_id(url),
                'platform': 'western_news',
                'source': source_id,
                'source_name': source_info['name'],
                'political_lean': source_info['political_lean'],
                'category': source_info['category'],
                'title': title[:500],  # Limit title length
                'url': url[:512],
                'author': author[:200] if author else None,
                'description': description[:2000] if description else None,
                'published_at': published_at,
                'add_ts': int(datetime.now().timestamp()),
                'last_modify_ts': int(datetime.now().timestamp()),
                'collected_at': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to parse RSS entry: {e}")
            return None

    async def collect_all_western_news(
        self,
        sources: Optional[List[str]] = None,
        political_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Collect news from all or selected Western sources

        Args:
            sources: List of source IDs to collect from (None = all sources)
            political_filter: Filter by political leaning ('left', 'right', 'center')

        Returns:
            Collection results dictionary
        """
        # Determine which sources to collect from
        if sources is None:
            sources = list(WESTERN_NEWS_SOURCES.keys())

        # Apply political filter if specified
        if political_filter:
            sources = [
                s for s in sources
                if WESTERN_NEWS_SOURCES[s]['political_lean'] == political_filter
            ]

        logger.info(f"Collecting Western news from {len(sources)} sources...")

        all_articles = []
        successful_sources = 0
        failed_sources = 0

        for source_id in sources:
            source_name = WESTERN_NEWS_SOURCES.get(source_id, {}).get('name', source_id)
            logger.info(f"Fetching {source_name}...")

            result = await self.fetch_rss_feed(source_id)

            if result['status'] == 'success':
                successful_sources += 1
                articles = result.get('articles', [])
                all_articles.extend(articles)
                logger.info(f"  {source_name}: {len(articles)} articles")
            else:
                failed_sources += 1
                logger.warning(f"  {source_name}: {result.get('error', 'Failed')}")

            # Rate limiting - be respectful to avoid IP bans
            await asyncio.sleep(self.rate_limit_delay)

        logger.info(f"Collection complete: {successful_sources}/{len(sources)} sources, {len(all_articles)} articles")

        return {
            'success': True,
            'total_sources': len(sources),
            'successful_sources': successful_sources,
            'failed_sources': failed_sources,
            'total_articles': len(all_articles),
            'articles': all_articles
        }

    async def collect_by_political_spectrum(self) -> Dict[str, Any]:
        """Collect news from all political perspectives (left, right, center)"""
        logger.info("Collecting news from across political spectrum...")

        results = {
            'left': await self.collect_all_western_news(political_filter='left'),
            'right': await self.collect_all_western_news(political_filter='right'),
            'center': await self.collect_all_western_news(political_filter='center')
        }

        total_articles = sum(r['total_articles'] for r in results.values())
        logger.info(f"Total articles across all spectrums: {total_articles}")

        return results

    def get_sources_by_category(self, category: str) -> List[str]:
        """Get source IDs by category (general, politics, tech, business)"""
        return [
            source_id for source_id, info in WESTERN_NEWS_SOURCES.items()
            if info['category'] == category
        ]

    def get_sources_by_political_lean(self, lean: str) -> List[str]:
        """Get source IDs by political leaning (left, right, center)"""
        return [
            source_id for source_id, info in WESTERN_NEWS_SOURCES.items()
            if info['political_lean'] == lean
        ]


async def main():
    """Test Western news collector"""
    logger.info("Testing Western News Collector...")

    async with WesternNewsCollector(rate_limit_delay=1.0) as collector:
        # Test with a few sources from each political leaning
        test_sources = ['bbc', 'techcrunch', 'google_news_tech']

        result = await collector.collect_all_western_news(sources=test_sources)

        if result['success']:
            logger.info(f"Collection successful! Articles collected: {result['total_articles']}")
            for article in result['articles'][:3]:
                logger.info(f"  - {article['title'][:60]}... ({article['source_name']})")
        else:
            logger.error("Collection failed")


if __name__ == "__main__":
    asyncio.run(main())
