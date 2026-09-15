import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from flask import Flask


def _remove_modules(prefix):
    saved = {
        name: module
        for name, module in list(sys.modules.items())
        if name == prefix or name.startswith(f"{prefix}.")
    }
    for name in saved:
        sys.modules.pop(name, None)
    return saved


def _load_filenames_module():
    path = Path(__file__).resolve().parents[1] / "ReportEngine" / "utils" / "filenames.py"
    spec = importlib.util.spec_from_file_location("ReportEngine.utils.filenames", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def report_interface(monkeypatch, tmp_path):
    saved_modules = _remove_modules("ReportEngine")

    agent_module = ModuleType("ReportEngine.agent")
    agent_module.ReportAgent = type("ReportAgent", (), {})
    agent_module.create_agent = lambda *args, **kwargs: None

    nodes_module = ModuleType("ReportEngine.nodes")
    nodes_module.ChapterJsonParseError = type("ChapterJsonParseError", (Exception,), {})

    utils_package = ModuleType("ReportEngine.utils")
    utils_package.__path__ = []
    config_module = ModuleType("ReportEngine.utils.config")
    config_module.settings = SimpleNamespace(OUTPUT_DIR=str(tmp_path / "output"))

    filenames_module = _load_filenames_module()
    dep_module = ModuleType("ReportEngine.utils.dependency_check")
    dep_module.check_pango_available = lambda: (True, "ok")
    dep_module.log_dependency_status = lambda: None

    class FakePDFRenderer:
        def render_to_bytes(self, document_ir, optimize_layout=True):
            return b"%PDF-fake"

    renderers_module = ModuleType("ReportEngine.renderers")
    renderers_module.PDFRenderer = FakePDFRenderer
    renderers_module.MarkdownRenderer = type("MarkdownRenderer", (), {})

    monkeypatch.setitem(sys.modules, "ReportEngine.agent", agent_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.nodes", nodes_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils", utils_package)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.config", config_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.filenames", filenames_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.dependency_check", dep_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.renderers", renderers_module)

    module = importlib.import_module("ReportEngine.flask_interface")
    flask_app = Flask(__name__)
    flask_app.register_blueprint(module.report_bp, url_prefix="/api/report")

    try:
        yield module, flask_app.test_client(), tmp_path
    finally:
        _remove_modules("ReportEngine")
        sys.modules.update(saved_modules)


def _completed_task(module, tmp_path, document_ir, task_id="task-pdf"):
    ir_path = tmp_path / f"{task_id}.json"
    ir_path.write_text(json.dumps(document_ir), encoding="utf-8")
    task = module.ReportTask(query="fallback-query", task_id=task_id)
    task.status = "completed"
    task.ir_file_path = str(ir_path)
    module.current_task = task
    module.tasks_registry.clear()
    module.tasks_registry[task.task_id] = task
    return task


def _assert_safe_pdf_disposition(response, expected_topic_segment):
    assert response.status_code == 200
    assert response.data == b"%PDF-fake"
    disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert expected_topic_segment in disposition
    assert ".." not in disposition
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert 'filename="' in disposition
    filename = disposition.split("filename=", 1)[1].strip().strip('"')
    assert "/" not in filename
    assert "\\" not in filename
    assert '"' not in filename
    assert filename.startswith(f"report_{expected_topic_segment}_")
    assert filename.endswith(".pdf")


def test_export_pdf_sanitizes_content_disposition_topic(report_interface):
    module, client, tmp_path = report_interface
    _completed_task(
        module,
        tmp_path,
        {"metadata": {"topic": '../../tmp/pwned\r\nSet-Cookie: a=1"; filename="evil'}},
    )

    response = client.get("/api/report/export/pdf/task-pdf")
    _assert_safe_pdf_disposition(response, "tmppwnedSet-Cookie_a1_filenameevil")


def test_export_pdf_from_ir_sanitizes_content_disposition_topic(report_interface):
    module, client, tmp_path = report_interface
    response = client.post(
        "/api/report/export/pdf-from-ir",
        json={
            "document_ir": {
                "metadata": {"topic": '..\\..\\tmp\\pwned"; filename="evil'}
            },
            "optimize": False,
        },
    )
    _assert_safe_pdf_disposition(response, "tmppwned_filenameevil")

def test_export_pdf_from_ir_uses_report_fallback_when_metadata_missing(report_interface):
    _module, client, _tmp_path = report_interface
    response = client.post(
        "/api/report/export/pdf-from-ir",
        json={"document_ir": {"metadata": None}},
    )
    _assert_safe_pdf_disposition(response, "report")


def test_export_pdf_uses_task_query_when_topic_missing(report_interface):
    module, client, tmp_path = report_interface
    _completed_task(module, tmp_path, {"metadata": {}}, task_id="task-pdf")
    response = client.get("/api/report/export/pdf/task-pdf")
    _assert_safe_pdf_disposition(response, "fallback-query")
