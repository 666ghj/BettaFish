import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from common.provenance.models import ProvenanceBundle
from common.provenance.normalizer import new_provenance_bundle
from common.provenance.runtime import RuntimeProvenanceStore


def _remove_modules(prefix):
    saved = {
        name: module
        for name, module in list(sys.modules.items())
        if name == prefix or name.startswith(f"{prefix}.")
    }
    for name in saved:
        sys.modules.pop(name, None)
    return saved


@pytest.fixture
def report_interface(monkeypatch):
    saved_modules = _remove_modules("ReportEngine")

    agent_module = ModuleType("ReportEngine.agent")
    agent_module.ReportAgent = type("ReportAgent", (), {})
    agent_module.InsufficientInputError = type("InsufficientInputError", (ValueError,), {})
    agent_module.create_agent = lambda *args, **kwargs: None

    nodes_module = ModuleType("ReportEngine.nodes")
    nodes_module.ChapterJsonParseError = type("ChapterJsonParseError", (Exception,), {})

    utils_package = ModuleType("ReportEngine.utils")
    utils_package.__path__ = []
    config_module = ModuleType("ReportEngine.utils.config")
    config_module.settings = SimpleNamespace()

    monkeypatch.setitem(sys.modules, "ReportEngine.agent", agent_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.nodes", nodes_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils", utils_package)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.config", config_module)

    module = importlib.import_module("ReportEngine.flask_interface")
    flask_app = Flask(__name__)
    flask_app.register_blueprint(module.report_bp, url_prefix="/api/report")

    try:
        yield module, flask_app.test_client()
    finally:
        _remove_modules("ReportEngine")
        sys.modules.update(saved_modules)


def _task(module, task_id, status):
    task = module.ReportTask(query="test", task_id=task_id)
    task.status = status
    return task


def test_cancel_current_running_task_returns_success(report_interface):
    module, client = report_interface
    task = _task(module, "current-running", "running")
    module.current_task = task
    module.tasks_registry.clear()

    response = client.post("/api/report/cancel/current-running")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert task.status == "cancelled"
    assert module.current_task is None


def test_cancel_registry_running_task_returns_success(report_interface):
    module, client = report_interface
    task = _task(module, "registry-running", "running")
    module.current_task = None
    module.tasks_registry.clear()
    module.tasks_registry[task.task_id] = task

    response = client.post("/api/report/cancel/registry-running")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert task.status == "cancelled"


def test_cancel_already_cancelled_task_is_idempotent(report_interface):
    module, client = report_interface
    task = _task(module, "already-cancelled", "cancelled")
    module.current_task = None
    module.tasks_registry.clear()
    module.tasks_registry[task.task_id] = task

    response = client.post("/api/report/cancel/already-cancelled")

    assert response.status_code == 200
    assert response.get_json()["success"] is True


@pytest.mark.parametrize("status", ["completed", "error"])
def test_cancel_terminal_task_returns_not_found(report_interface, status):
    module, client = report_interface
    task = _task(module, f"terminal-{status}", status)
    module.current_task = None
    module.tasks_registry.clear()
    module.tasks_registry[task.task_id] = task

    response = client.post(f"/api/report/cancel/{task.task_id}")

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_cancel_missing_task_returns_not_found(report_interface):
    module, client = report_interface
    module.current_task = None
    module.tasks_registry.clear()

    response = client.post("/api/report/cancel/missing")

    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_status_exposes_failed_upstream_engine(report_interface, monkeypatch):
    module, client = report_interface
    monkeypatch.setattr(
        module,
        "check_engines_ready",
        lambda _run_id="": {
            "ready": False,
            "missing_files": [],
            "failed": {"insight": "model unavailable"},
        },
    )

    response = client.get("/api/report/status?run_id=run-1")

    assert response.status_code == 200
    assert response.get_json()["failed_engines"] == {
        "insight": "model unavailable"
    }


def test_generate_rejects_failed_upstream_engine(report_interface, monkeypatch):
    module, client = report_interface
    module.report_agent = object()
    monkeypatch.setattr(
        module,
        "check_engines_ready",
        lambda _run_id="": {
            "ready": False,
            "missing_files": [],
            "failed": {"insight": "model unavailable"},
        },
    )

    response = client.post(
        "/api/report/generate", json={"query": "topic", "run_id": "run-1"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "上游 Agent 运行失败"
    assert response.get_json()["failed_engines"] == {
        "insight": "model unavailable"
    }


def test_three_runtime_engine_results_flow_into_report_generation(
    report_interface, monkeypatch
):
    module, _client = report_interface
    store = RuntimeProvenanceStore(max_runs=2)
    run_id = store.begin("topic", ["query", "media", "insight"])
    for engine, report in (
        ("query", "query report"),
        ("media", "media report"),
        ("insight", "insight report"),
    ):
        store.publish(
            run_id,
            engine,
            "topic",
            report,
            new_provenance_bundle(f"{engine}_engine", "topic", run_id=run_id),
        )

    captured = {}

    class Agent:
        def generate_report(self, **kwargs):
            captured.update(kwargs)
            return {"html_content": "<html>done</html>"}

    module.runtime_store = store
    module.report_agent = Agent()
    forum_reader = Mock(return_value="forum context")
    monkeypatch.setattr(module, "read_runtime_forum_context", forum_reader)
    task = module.ReportTask(query="topic", task_id="report-runtime")
    module.current_task = task

    module.run_report_generation(task, "topic", run_id=run_id)

    assert task.status == "completed"
    assert task.html_content == "<html>done</html>"
    assert captured["reports"] == [
        "query report",
        "media report",
        "insight report",
    ]
    assert captured["forum_logs"] == "forum context"
    forum_reader.assert_called_once_with(run_id, set())
    assert captured["provenance_bundle"].agent == "report_engine"
    assert captured["provenance_bundle"].meta["agents"] == [
        "query_engine",
        "media_engine",
        "insight_engine",
    ]
