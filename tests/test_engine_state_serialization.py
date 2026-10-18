import importlib

import pytest

from common.provenance.models import ProvenanceBundle


@pytest.mark.parametrize(
    ("module_name", "agent_name"),
    [
        ("InsightEngine.state.state", "insight_engine"),
        ("MediaEngine.state.state", "media_engine"),
        ("QueryEngine.state.state", "query_engine"),
    ],
)
def test_engine_state_from_dict_restores_shared_fields(module_name, agent_name):
    state_type = importlib.import_module(module_name).State
    payload = {
        "query": "清华鹅腿阿姨",
        "report_title": "测试报告",
        "paragraphs": [
            {
                "title": "背景",
                "content": "章节说明",
                "research": {
                    "search_history": [],
                    "latest_summary": "有证据的摘要",
                    "reflection_iteration": 2,
                    "is_completed": True,
                },
                "order": 0,
            }
        ],
        "final_report": "最终报告",
        "provenance_bundle": ProvenanceBundle(agent=agent_name).to_dict(),
        "is_completed": True,
        "created_at": "2026-09-10T10:00:00",
        "updated_at": "2026-09-10T11:00:00",
    }

    state = state_type.from_dict(payload)

    assert state.to_dict() == payload
