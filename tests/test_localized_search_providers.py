import os
import pytest

from localized_search.providers import LocalizedSearchClient, SearchProviderError, _clean_html


def test_clean_html_for_naver_titles():
    assert _clean_html('<b>한국</b> &amp; AI &quot;검색&quot;') == '한국 & AI "검색"'


def test_fail_closed_requires_key(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    client = LocalizedSearchClient(provider='brave', fail_closed=True)
    with pytest.raises(SearchProviderError):
        client.search('ai search', max_results=1)


def test_non_fail_closed_reports_error(monkeypatch):
    monkeypatch.delenv('NAVER_CLIENT_ID', raising=False)
    monkeypatch.delenv('NAVER_CLIENT_SECRET', raising=False)
    client = LocalizedSearchClient(provider='naver', fail_closed=False)
    response = client.search('한국 AI 검색', max_results=1)
    assert not response.ok
    assert response.provider == 'naver'
    assert 'NAVER_CLIENT_ID' in response.error


class _FakeResponse:
    def __init__(self, data):
        self._data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self._data


def test_default_provider_is_searxng(monkeypatch):
    monkeypatch.delenv('SEARCH_PROVIDER', raising=False)
    client = LocalizedSearchClient()
    assert client.provider == 'searxng'


def test_searxng_normalizes_results_from_settings_object(monkeypatch):
    class Settings:
        SEARXNG_BASE_URL = 'http://searxng:8080'
    calls = {}
    def fake_get(url, params=None, timeout=None, **kwargs):
        calls['url'] = url
        calls['params'] = params
        return _FakeResponse({'results': [{'title': 'Result', 'url': 'https://example.com', 'content': 'Snippet'}]})
    monkeypatch.setattr('localized_search.providers.requests.get', fake_get)
    client = LocalizedSearchClient(provider='searxng', settings_obj=Settings())
    response = client.search('query', max_results=1)
    assert response.ok
    assert calls['url'] == 'http://searxng:8080/search'
    assert calls['params']['format'] == 'json'
    assert response.results[0].source == 'searxng'
    assert response.results[0].content == 'Snippet'


def test_tavily_requires_key(monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    client = LocalizedSearchClient(provider='tavily', fail_closed=True)
    with pytest.raises(SearchProviderError):
        client.search('ai search', max_results=1)
