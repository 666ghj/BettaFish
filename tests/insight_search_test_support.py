"""Shared deterministic rows for Insight platform-search regression tests."""


def unbounded_weibo_rows(query, _params=None):
    if "weibo_note_comment" in query:
        return []
    return [{
        "id": 42,
        "content": "某热点事件获得平台关注",
        "nickname": "测试用户",
        "create_date_time": "2026-09-10 10:00:00",
    }]
