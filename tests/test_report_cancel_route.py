import importlib
import importlib.util
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


@pytest.fixture
def report_interface(monkeypatch):
    saved_modules = _remove_modules("ReportEngine")

    agent_module = ModuleType("ReportEngine.agent")
    agent_module.ReportAgent = type("ReportAgent", (), {})
    agent_module.create_agent = lambda *args, **kwargs: None

    nodes_module = ModuleType("ReportEngine.nodes")
    nodes_module.ChapterJsonParseError = type("ChapterJsonParseError", (Exception,), {})

    utils_package = ModuleType("ReportEngine.utils")
    utils_package.__path__ = []
    config_module = ModuleType("ReportEngine.utils.config")
    config_module.settings = SimpleNamespace()
    filenames_path = Path(__file__).resolve().parents[1] / "ReportEngine" / "utils" / "filenames.py"
    filenames_spec = importlib.util.spec_from_file_location("ReportEngine.utils.filenames", filenames_path)
    filenames_module = importlib.util.module_from_spec(filenames_spec)
    assert filenames_spec.loader is not None
    filenames_spec.loader.exec_module(filenames_module)

    monkeypatch.setitem(sys.modules, "ReportEngine.agent", agent_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.nodes", nodes_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils", utils_package)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.config", config_module)
    monkeypatch.setitem(sys.modules, "ReportEngine.utils.filenames", filenames_module)

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
