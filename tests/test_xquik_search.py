import datetime
from types import SimpleNamespace

import pytest
import requests

from config import Settings as RootSettings
from MediaEngine import agent as agent_module
from MediaEngine.tools import search as search_module
from MediaEngine.tools.search import XquikSearch
from MediaEngine.utils.config import Settings


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.url = "https://api.example.test/x/tweets/search"

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.url = self.url
            raise requests.HTTPError(response=response)

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_media_engine_settings_allow_unselected_credentials_to_be_blank():
    settings = Settings(_env_file=None)

    assert settings.INSIGHT_ENGINE_API_KEY is None
    assert settings.MEDIA_ENGINE_API_KEY is None
    assert settings.QUERY_ENGINE_API_KEY is None
    assert settings.REPORT_ENGINE_API_KEY is None
    assert settings.FORUM_HOST_API_KEY is None
    assert settings.KEYWORD_OPTIMIZER_API_KEY is None
    assert settings.TAVILY_API_KEY is None


def test_root_settings_accept_xquik_provider():
    settings = RootSettings(_env_file=None, SEARCH_TOOL_TYPE="XquikAPI")

    assert settings.SEARCH_TOOL_TYPE == "XquikAPI"
    assert settings.XQUIK_BASE_URL == "https://xquik.com/api/v1/x/tweets/search"


def test_xquik_search_maps_posts_and_request_contract():
    calls = []
    payload = {
        "has_next_page": True,
        "next_cursor": "cursor-2",
        "tweets": [
            {
                "id": "1840001",
                "text": "BettaFish release discussion",
                "createdAt": "2026-08-26T10:30:00.000Z",
                "url": "https://x.com/bettafish/status/1840001",
                "likeCount": 12,
                "retweetCount": 4,
                "replyCount": 3,
                "quoteCount": 1,
                "viewCount": 900,
                "author": {"name": "BettaFish", "username": "bettafish"},
            },
            {
                "id": "1840002",
                "text": "A second post",
                "author": {"username": "researcher"},
            },
            "invalid-row",
        ],
    }

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload)

    search = XquikSearch(
        api_key="test-key",
        base_url="https://api.example.test/x/tweets/search",
        request_get=request_get,
    )

    result = search.comprehensive_search("BettaFish", max_results=20000)

    assert calls == [
        (
            "https://api.example.test/x/tweets/search",
            {
                "headers": {"x-api-key": "test-key", "Accept": "application/json"},
                "params": {
                    "q": "BettaFish",
                    "limit": 10000,
                    "queryType": "Latest",
                },
                "timeout": search_module.settings.SEARCH_TIMEOUT,
            },
        )
    ]
    assert result.query == "BettaFish"
    assert result.has_next_page is True
    assert result.next_cursor == "cursor-2"
    assert len(result.webpages) == 2
    assert result.webpages[0].name == "BettaFish (@bettafish)"
    assert result.webpages[0].url == "https://x.com/bettafish/status/1840001"
    assert result.webpages[0].date_last_crawled == "2026-08-26T10:30:00.000Z"
    assert result.webpages[0].snippet == (
        "BettaFish release discussion\n"
        "Engagement: likes=12, reposts=4, replies=3, quotes=1, views=900"
    )
    assert result.webpages[1].name == "researcher (@researcher)"
    assert result.webpages[1].url == "https://x.com/researcher/status/1840002"


def test_xquik_search_applies_utc_time_windows():
    calls = []
    now = datetime.datetime(2026, 8, 26, 12, 30, tzinfo=datetime.timezone.utc)

    def request_get(_url, **kwargs):
        calls.append(kwargs["params"])
        return FakeResponse({"tweets": []})

    search = XquikSearch(
        api_key="test-key",
        request_get=request_get,
        now=lambda: now,
    )

    search.search_last_24_hours("release")
    search.search_last_week("release")

    assert calls[0]["sinceTime"] == "2026-08-25T12:30:00Z"
    assert calls[0]["untilTime"] == "2026-08-26T12:30:00Z"
    assert calls[1]["sinceTime"] == "2026-08-19T12:30:00Z"
    assert calls[1]["untilTime"] == "2026-08-26T12:30:00Z"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"tweets": "not-a-list"},
        ValueError("invalid JSON"),
    ],
)
def test_xquik_search_returns_empty_results_for_invalid_responses(payload):
    calls = 0

    def request_get(_url, **_kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(payload)

    result = XquikSearch(api_key="test-key", request_get=request_get).web_search_only(
        "BettaFish"
    )

    assert calls == 1
    assert result.query == "BettaFish"
    assert result.webpages == []


def test_xquik_search_rejects_empty_queries_before_request():
    def request_get(_url, **_kwargs):
        raise AssertionError("empty queries must not make a request")

    search = XquikSearch(api_key="test-key", request_get=request_get)

    with pytest.raises(ValueError, match="搜索关键词不能为空"):
        search.comprehensive_search("   ")


def test_xquik_search_handles_permanent_http_errors_without_retry():
    calls = 0

    def request_get(_url, **_kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse({}, status_code=401)

    result = XquikSearch(
        api_key="test-key", request_get=request_get
    ).comprehensive_search("BettaFish")

    assert calls == 1
    assert result.query == "BettaFish"
    assert result.webpages == []


def test_create_agent_selects_xquik_provider(monkeypatch):
    config = SimpleNamespace(SEARCH_TOOL_TYPE="XquikAPI")
    selected = object()

    monkeypatch.setattr(
        agent_module,
        "XquikSearchAgent",
        lambda received_config: selected if received_config is config else None,
    )

    assert agent_module.create_agent(config) is selected


def test_create_agent_loads_xquik_provider_from_env_file(monkeypatch, tmp_path):
    config_file = tmp_path / "provider.env"
    config_file.write_text(
        "SEARCH_TOOL_TYPE=XquikAPI\nXQUIK_API_KEY=test-key\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        agent_module,
        "XquikSearchAgent",
        lambda config: config,
    )

    selected = agent_module.create_agent(str(config_file))

    assert selected.SEARCH_TOOL_TYPE == "XquikAPI"
    assert selected.XQUIK_API_KEY == "test-key"


def test_search_loader_selects_xquik_provider(monkeypatch):
    monkeypatch.setattr(search_module.settings, "SEARCH_TOOL_TYPE", "XquikAPI")
    monkeypatch.setattr(search_module.settings, "XQUIK_API_KEY", "test-key")

    selected = search_module.load_agent_from_config()

    assert isinstance(selected, XquikSearch)
