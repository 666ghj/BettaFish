import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_deduplication_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "InsightEngine"
        / "utils"
        / "deduplication.py"
    )
    spec = importlib.util.spec_from_file_location("insight_deduplication", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deduplication = load_deduplication_module()


def test_url_less_results_do_not_dedupe_by_truncated_prefix():
    prefix = (
        "Breaking: Major vulnerability found in popular framework "
        "CVE-2026-1234 with remote code execution impact affecting millions "
        "of users worldwide. "
    )
    first = SimpleNamespace(
        url=None,
        platform="weibo",
        content_type="comment",
        source_table="weibo_note_comment",
        author_nickname="alice",
        publish_time=None,
        title_or_content=prefix + "No patch is needed.",
    )
    second = SimpleNamespace(
        url=None,
        platform="weibo",
        content_type="comment",
        source_table="weibo_note_comment",
        author_nickname="alice",
        publish_time=None,
        title_or_content=prefix + "Patch immediately.",
    )

    assert first.title_or_content[:100] == second.title_or_content[:100]
    assert deduplication.build_result_dedup_key(first) != deduplication.build_result_dedup_key(second)


def test_url_results_keep_url_based_deduplication():
    first = SimpleNamespace(
        url="https://example.com/post/1",
        title_or_content="Original content",
    )
    second = SimpleNamespace(
        url="https://example.com/post/1",
        title_or_content="Updated content",
    )

    assert deduplication.build_result_dedup_key(first) == deduplication.build_result_dedup_key(second)
