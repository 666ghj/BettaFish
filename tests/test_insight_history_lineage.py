"""Search history must retain the lineage emitted by real Insight searches."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from InsightEngine.agent import DeepSearchAgent
from InsightEngine.state.state import Research, Search, State
from InsightEngine.tools.search import DBResponse, QueryResult


LINEAGE = {
    "query_time": "2026-10-18T12:00:00",
    "table": "weibo_note",
    "filters": {"topic": "清华鹅腿阿姨", "platform": "weibo"},
    "time_window": {"start": "2026-10-01", "end": "2026-10-19"},
    "sample_size": 1,
    "aggregation_method": "record_lookup",
    "row_ids": ["42"],
    "primary_key": "42",
}

HISTORY_LINEAGE = {
    "source_table": "weibo_note",
    "record_id": "42",
    "query_time": "2026-10-18T12:00:00",
    "filters": {"topic": "清华鹅腿阿姨", "platform": "weibo"},
    "time_window": {"start": "2026-10-01", "end": "2026-10-19"},
    "sample_size": 1,
    "aggregation_method": "record_lookup",
}


@pytest.mark.parametrize("stage", ["initial", "reflection"])
def test_agent_search_history_preserves_row_lineage_in_saved_state(stage):
    # Catch an ingestion mismatch between nested tool provenance and history's
    # public fields, while leaving search conversion and evidence capture real.
    row = QueryResult(
        platform="weibo", content_type="note", title_or_content="清华鹅腿阿姨受到关注",
        source_table="weibo_note", record_id="42", provenance=deepcopy(LINEAGE),
    )
    response = DBResponse(
        tool_name="search_topic_on_platform_optimized",
        parameters={"original_query": "清华鹅腿阿姨"},
        results=[row], results_count=1,
    )
    agent = DeepSearchAgent.__new__(DeepSearchAgent)
    agent.state = State(query="清华鹅腿阿姨")
    agent.state.add_paragraph("平台讨论", "微博讨论")
    agent.config = SimpleNamespace(
        MAX_REFLECTIONS=1, MAX_SEARCH_RESULTS_FOR_LLM=0,
        DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT=20, MAX_CONTENT_LENGTH=20000,
    )
    planning = SimpleNamespace(run=lambda _input: {
        "search_query": "清华鹅腿阿姨", "search_tool": "search_topic_on_platform",
        "platform": "weibo", "reasoning": "检查平台来源",
    })
    summary = SimpleNamespace(mutate_state=lambda _input, state, _index: state)
    agent.first_search_node = agent.reflection_node = planning
    agent.first_summary_node = agent.reflection_summary_node = summary
    agent.execute_search_tool = lambda *_args, **_kwargs: response

    if stage == "initial":
        agent._initial_search_and_summary(0)
    else:
        agent._reflection_loop(0)

    saved = json.loads(agent.state.to_json())
    history = saved["paragraphs"][0]["research"]["search_history"][0]
    assert {key: history[key] for key in HISTORY_LINEAGE} == HISTORY_LINEAGE
    restored = State.from_json(agent.state.to_json())
    assert restored.paragraphs[0].research.search_history[0].to_dict() == history
    assert row.provenance == LINEAGE
    assert len(restored.provenance_bundle.evidence) == 1
    scope = restored.provenance_bundle.evidence[0].scope
    assert {key: scope[key] for key in LINEAGE} == LINEAGE


def test_history_accepts_existing_top_level_lineage():
    research = Research()
    research.add_search_results("旧格式查询", [{
        "title": "旧格式结果", "content": "旧格式正文", **deepcopy(HISTORY_LINEAGE),
    }])

    saved = research.to_dict()["search_history"][0]
    assert {key: saved[key] for key in HISTORY_LINEAGE} == HISTORY_LINEAGE
    assert Search.from_dict(saved).to_dict() == saved


def test_history_still_restores_legacy_records_without_lineage():
    research = Research()
    research.add_search_results("旧查询", [{"title": "旧标题", "content": "旧正文"}])

    saved = research.to_dict()["search_history"][0]
    assert saved["query"] == "旧查询"
    assert saved["title"] == "旧标题"
    assert saved["content"] == "旧正文"
    assert {key: saved[key] for key in HISTORY_LINEAGE} == {
        "source_table": "", "record_id": "", "query_time": "", "filters": {},
        "time_window": {}, "sample_size": 0, "aggregation_method": "",
    }
    assert Search.from_dict(saved).to_dict() == saved


def test_nested_lineage_is_authoritative_when_top_level_metadata_is_stale():
    research = Research()
    research.add_search_results("查询", [{
        "source_table": "stale_table", "record_id": "old-row",
        "query_time": "stale-time", "sample_size": 999,
        "provenance": deepcopy(LINEAGE),
    }])

    saved = research.to_dict()["search_history"][0]
    assert {key: saved[key] for key in HISTORY_LINEAGE} == HISTORY_LINEAGE
