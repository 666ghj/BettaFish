import pytest

from MindSpider.source_providers import SearchBackedSourceProvider, LegacyChinaSourceProvider, SourceProviderError


class _FakeResponse:
    def __init__(self, data):
        self._data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self._data


class _Settings:
    SEARXNG_BASE_URL = 'http://searxng:8080'


def test_search_backed_source_provider_preserves_source_metadata(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kwargs):
        return _FakeResponse({'results': [{'title': 'Topic', 'url': 'https://example.com/topic', 'content': 'Evidence'}]})
    monkeypatch.setattr('localized_search.providers.requests.get', fake_get)
    provider = SearchBackedSourceProvider('searxng', market='global', settings_obj=_Settings())
    items = provider.collect(['topic'], max_results_per_query=1)
    assert len(items) == 1
    assert items[0].source_provider == 'searxng'
    assert items[0].source_region == 'global'
    record = items[0].to_daily_news_record()
    assert record['source_provider'] == 'searxng'
    assert record['source_platform'] == 'web_search'


def test_legacy_china_source_provider_is_explicit_opt_in_marker():
    provider = LegacyChinaSourceProvider()
    with pytest.raises(SourceProviderError):
        provider.collect(['topic'])
