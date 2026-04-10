import os
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QUERY_ENGINE_API_KEY", "test-query-key")
os.environ.setdefault("QUERY_ENGINE_MODEL_NAME", "test-model")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")

if "tavily" not in sys.modules:
    tavily_module = types.ModuleType("tavily")

    class DummyTavilyClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, **kwargs):
            return {
                "query": kwargs.get("query", ""),
                "results": [],
                "images": [],
            }

    tavily_module.TavilyClient = DummyTavilyClient
    sys.modules["tavily"] = tavily_module

if "openai" not in sys.modules:
    openai_module = types.ModuleType("openai")

    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_module.OpenAI = DummyOpenAI
    sys.modules["openai"] = openai_module

from QueryEngine.agent import DeepSearchAgent
from QueryEngine.nodes.search_node import FirstSearchNode, ReflectionNode
from QueryEngine.prompts.prompts import build_first_search_prompt, build_reflection_prompt
from QueryEngine.tools.market_sentiment import AdanosSentimentAgency
from QueryEngine.tools.search import TavilyResponse


def test_market_sentiment_prompt_toggle():
    first_prompt = build_first_search_prompt(enable_market_sentiment=False)
    reflection_prompt = build_reflection_prompt(enable_market_sentiment=False)

    assert "search_market_sentiment" not in first_prompt
    assert "search_market_sentiment" not in reflection_prompt

    enabled_first_prompt = build_first_search_prompt(enable_market_sentiment=True)
    enabled_reflection_prompt = build_reflection_prompt(enable_market_sentiment=True)

    assert "search_market_sentiment" in enabled_first_prompt
    assert "search_market_sentiment" in enabled_reflection_prompt


def test_first_search_node_preserves_tool_and_dates():
    node = FirstSearchNode(llm_client=None, enable_market_sentiment=True)
    result = node.process_output(
        """
        {
          "search_query": "AAPL market sentiment",
          "search_tool": "search_market_sentiment",
          "reasoning": "需要结构化情绪数据",
          "start_date": "2026-04-01",
          "end_date": "2026-04-07"
        }
        """
    )

    assert result["search_query"] == "AAPL market sentiment"
    assert result["search_tool"] == "search_market_sentiment"
    assert result["start_date"] == "2026-04-01"
    assert result["end_date"] == "2026-04-07"


def test_reflection_node_preserves_tool_selection():
    node = ReflectionNode(llm_client=None, enable_market_sentiment=True)
    result = node.process_output(
        """
        {
          "search_query": "TSLA bulls vs bears",
          "search_tool": "search_market_sentiment",
          "reasoning": "需要补齐量化情绪证据"
        }
        """
    )

    assert result["search_query"] == "TSLA bulls vs bears"
    assert result["search_tool"] == "search_market_sentiment"
    assert result["start_date"] is None
    assert result["end_date"] is None


def test_adanos_sentiment_agency_formats_stock_results():
    agency = AdanosSentimentAgency(api_key="test-adanos-key")

    def fake_request(path, params):
        if path == "/reddit/stocks/v1/stock/AAPL":
            return {
                "found": True,
                "buzz_score": 74.2,
                "sentiment_score": 0.41,
                "bullish_pct": 68,
                "trend": "rising",
                "mentions": 120,
            }
        if path == "/x/stocks/v1/stock/AAPL":
            return {
                "found": True,
                "buzz_score": 61.8,
                "sentiment_score": 0.22,
                "bullish_pct": 57,
                "trend": "stable",
                "unique_tweets": 84,
            }
        return None

    agency._request_json = fake_request

    response = agency.search_market_sentiment("Evaluate AAPL sentiment", days=14)

    assert response.query == "Evaluate AAPL sentiment"
    assert response.results
    assert response.results[0].title == "AAPL cross-source market sentiment snapshot"
    assert "Average buzz score" in response.results[0].content
    assert any(result.title == "AAPL REDDIT sentiment details" for result in response.results)
    assert any(result.title == "AAPL X sentiment details" for result in response.results)


def test_adanos_sentiment_agency_formats_market_overview():
    agency = AdanosSentimentAgency(api_key="test-adanos-key")

    def fake_request(path, params):
        if path == "/news/stocks/v1/market-sentiment":
            return {
                "buzz_score": 55.0,
                "sentiment_score": 0.18,
                "bullish_pct": 54,
                "trend": "stable",
                "mentions": 540,
                "active_tickers": 31,
                "drivers": [{"ticker": "NVDA", "buzz_score": 82.1, "sentiment_score": 0.44}],
            }
        if path == "/reddit/stocks/v1/market-sentiment":
            return {
                "buzz_score": 63.5,
                "sentiment_score": 0.27,
                "bullish_pct": 61,
                "trend": "rising",
                "mentions": 710,
                "active_tickers": 45,
                "drivers": [{"ticker": "PLTR", "buzz_score": 76.0, "sentiment_score": 0.39}],
            }
        return None

    agency._request_json = fake_request

    response = agency.search_market_sentiment("What is the current stock market mood?", days=7)

    assert response.results
    assert response.results[0].title == "Cross-source US market sentiment overview"
    assert "Covered sources: NEWS, REDDIT" in response.results[0].content
    assert any(result.title == "NEWS market sentiment overview" for result in response.results)


def test_execute_search_tool_market_sentiment_is_fail_open():
    agent = DeepSearchAgent.__new__(DeepSearchAgent)
    agent.market_sentiment_agency = None

    response = agent.execute_search_tool("search_market_sentiment", "AAPL")

    assert isinstance(response, TavilyResponse)
    assert response.results == []
    assert "not configured" in (response.answer or "").lower()
