import importlib.util
from pathlib import Path

_FILENAMES_PATH = Path(__file__).resolve().parents[1] / "ReportEngine" / "utils" / "filenames.py"
_SPEC = importlib.util.spec_from_file_location("report_filenames_under_test", _FILENAMES_PATH)
filenames = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(filenames)

safe_filename_segment = filenames.safe_filename_segment
topic_from_document_ir = filenames.topic_from_document_ir
report_export_filename = filenames.report_export_filename


def test_safe_filename_segment_keeps_simple_names():
    assert safe_filename_segment("market-outlook") == "market-outlook"
    assert safe_filename_segment("武汉 大学") == "武汉_大学"


def test_safe_filename_segment_strips_path_and_header_metacharacters():
    assert ".." not in safe_filename_segment("../../tmp/pwned")
    assert "/" not in safe_filename_segment("../../tmp/pwned")
    assert "\\" not in safe_filename_segment("..\\tmp\\pwned")
    assert "\r" not in safe_filename_segment("ok\r\nSet-Cookie: a=1")
    assert "\n" not in safe_filename_segment("ok\r\nSet-Cookie: a=1")
    assert '"' not in safe_filename_segment('say "hello"')
    assert safe_filename_segment("///") == "report"
    assert safe_filename_segment("", fallback="export") == "export"


def test_topic_from_document_ir_uses_title_and_fallback():
    assert topic_from_document_ir({"metadata": {"title": "Q3 复盘"}}) == "Q3 复盘"
    assert topic_from_document_ir({"metadata": None}, fallback="task-query") == "task-query"
    assert topic_from_document_ir("not-a-dict") == "report"


def test_report_export_filename_is_single_path_segment():
    filename = report_export_filename(
        {"metadata": {"topic": '../../tmp/pwned"; filename="evil'}},
        "pdf",
        timestamp="20260101_000000",
    )
    assert filename == "report_tmppwned_filenameevil_20260101_000000.pdf"
    assert "/" not in filename
    assert "\\" not in filename
    assert ".." not in filename
    assert '"' not in filename
    assert "\n" not in filename
