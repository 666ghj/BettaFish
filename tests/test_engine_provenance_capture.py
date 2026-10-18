from types import SimpleNamespace

from InsightEngine.agent import DeepSearchAgent as InsightAgent
from InsightEngine.state import State as InsightState
from InsightEngine.tools.search import DBResponse, MediaCrawlerDB
from MediaEngine.agent import DeepSearchAgent as MediaAgent
from common.provenance.models import ProvenanceBundle
from tests.insight_search_test_support import unbounded_weibo_rows


def test_media_ocr_capture_replaces_web_raw_content():
    agent = MediaAgent.__new__(MediaAgent)
    agent.state = SimpleNamespace(
        provenance_bundle=ProvenanceBundle(agent="media_engine")
    )

    agent._capture_provenance(
        [{
            "title": "带 OCR 的搜索结果",
            "url": "https://example.com/item",
            "raw_content": "网页摘要中的数值是 99",
            "content": "网页摘要中的数值是 99",
            "ocr_text": "图片 OCR 中的数值是 42",
        }],
        "测试查询",
        "测试章节",
        "bocha",
    )

    evidence = agent.state.provenance_bundle.evidence
    assert len(evidence) == 1
    assert evidence[0].evidence_type == "ocr"
    assert evidence[0].snippet == "图片 OCR 中的数值是 42"
    assert "99" not in evidence[0].snippet


def test_insight_capture_uses_row_lineage_not_merged_response_metadata():
    agent = InsightAgent.__new__(InsightAgent)
    agent.state = SimpleNamespace(
        provenance_bundle=ProvenanceBundle(agent="insight_engine")
    )
    response = DBResponse(
        tool_name="search_topic_by_date_optimized",
        parameters={"original_query": "合并查询"},
        results=[],
        results_count=2,
        query_time="2026-02-01T00:00:00",
        time_window={"kind": "unbounded"},
    )
    row_lineage = {
        "query_time": "2026-01-15T12:00:00",
        "table": "daily_news",
        "filters": {"topic": "原始关键词", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        "time_window": {"start": "2026-01-01", "end": "2026-02-01"},
        "sample_size": 1,
        "aggregation_method": "record_lookup",
        "row_ids": ["7"],
        "primary_key": "7",
    }

    captured = agent._capture_internal_provenance(
        response,
        [{
            "title": "一条新闻",
            "content": "一月份记录值为 42",
            "raw_content": "一月份记录值为 42",
            "source_table": "daily_news",
            "record_id": "7",
            "provenance": row_lineage,
        }],
        "原始查询",
        "时间窗口章节",
    )

    assert captured == 1
    scope = agent.state.provenance_bundle.evidence[0].scope
    assert scope["query_time"] == "2026-01-15T12:00:00"
    assert scope["filters"]["topic"] == "原始关键词"
    assert scope["time_window"]["start"] == "2026-01-01"
    assert scope["sample_size"] == 1
    assert scope["row_ids"] == ["7"]


def test_insight_initial_summary_accepts_unbounded_platform_lineage():
    database = MediaCrawlerDB()
    database._execute_query = unbounded_weibo_rows
    response = database.search_topic_on_platform("weibo", "某热点事件")

    agent = InsightAgent.__new__(InsightAgent)
    agent.state = InsightState(query="某热点事件")
    agent.state.add_paragraph("平台讨论", "分析微博讨论")
    agent.config = SimpleNamespace(
        MAX_SEARCH_RESULTS_FOR_LLM=0,
        DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT=20,
        MAX_CONTENT_LENGTH=20000,
    )
    agent.first_search_node = SimpleNamespace(
        run=lambda _input: {
            "search_query": "某热点事件",
            "search_tool": "search_topic_on_platform",
            "platform": "weibo",
            "reasoning": "定向查看微博讨论",
        }
    )
    agent.execute_search_tool = lambda *_args, **_kwargs: response

    def summarize(_input, state, paragraph_index):
        state.paragraphs[paragraph_index].research.latest_summary = "已生成有证据总结"
        return state

    agent.first_summary_node = SimpleNamespace(mutate_state=summarize)

    agent._initial_search_and_summary(0)

    assert response.results[0].provenance["time_window"] == {"kind": "unbounded"}
    assert len(agent.state.provenance_bundle.evidence) > 0
    assert agent.state.paragraphs[0].research.latest_summary == "已生成有证据总结"
