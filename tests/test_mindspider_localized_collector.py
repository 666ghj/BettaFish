import asyncio

import pytest

from MindSpider.BroadTopicExtraction.get_today_news import NewsCollector
from MindSpider.source_providers import RssSourceProvider, SourceProviderError


class _FakeDb:
    def __init__(self):
        self.saved = []
    def close(self):
        pass
    def save_daily_news(self, news_data, crawl_date=None):
        self.saved.extend(news_data)
        return len(news_data)
    def get_daily_news(self, crawl_date=None):
        return self.saved


class _FakeResponse:
    def __init__(self, data):
        self._data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self._data


def test_news_collector_default_localized_searxng_collects_and_saves(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kwargs):
        return _FakeResponse({'results': [{'title': 'Local topic', 'url': 'https://example.com/a', 'content': 'Snippet'}]})
    monkeypatch.setattr('localized_search.providers.requests.get', fake_get)
    collector = NewsCollector(source_mode='localized', provider='searxng', queries=['korean ai'], db_manager=_FakeDb())
    result = asyncio.run(collector.collect_and_save_news())
    assert result['success']
    assert result['total_news'] == 1
    assert result['saved_count'] == 1
    assert result['news_list'][0]['source_provider'] == 'searxng'


def test_news_collector_blocks_legacy_sources_without_legacy_mode():
    collector = NewsCollector(source_mode='localized', provider='searxng', db_manager=_FakeDb())
    result = asyncio.run(collector.collect_and_save_news(sources=['weibo']))
    assert not result['success']
    assert 'legacy_china' in result['error']


def test_rss_source_provider_parses_rss(monkeypatch):
    payload = b'''<?xml version="1.0"?><rss><channel><item><title>RSS Topic</title><link>https://example.com/rss</link><description>RSS body</description><pubDate>Sat, 13 Jun 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    class _UrlResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return payload
    monkeypatch.setattr('MindSpider.source_providers.rss.urlopen', lambda *args, **kwargs: _UrlResponse())
    provider = RssSourceProvider(['https://example.com/feed.xml'])
    items = provider.collect()
    assert items[0].title == 'RSS Topic'
    assert items[0].source_provider == 'rss'
    assert items[0].source_platform == 'rss'
