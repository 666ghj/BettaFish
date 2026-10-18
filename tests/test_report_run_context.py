"""A report task belongs to one provenance run; occupancy stays global."""

from flask import Flask
import pytest
from types import SimpleNamespace

from common.provenance.runtime import RuntimeProvenanceStore


@pytest.fixture
def report_api(monkeypatch):
    from ReportEngine import flask_interface as interface

    monkeypatch.setattr(interface, "current_task", None)
    monkeypatch.setattr(interface, "tasks_registry", {})
    monkeypatch.setattr(interface, "runtime_store", RuntimeProvenanceStore())
    monkeypatch.setattr(interface, "report_agent", SimpleNamespace(
        check_input_files=lambda *args: {"ready": True, "files_found": []},
    ))
    monkeypatch.setattr(interface, "clear_report_log", lambda: None)
    app = Flask(__name__)
    app.register_blueprint(interface.report_bp, url_prefix="/api/report")
    return interface, app.test_client()


def test_run_status_hides_other_run_task_but_retains_global_worker_occupancy(report_api):
    interface, web = report_api
    run_a = interface.runtime_store.begin("same topic", ["query"])
    run_b = interface.runtime_store.begin("same topic", ["query"])
    task = interface.ReportTask("same topic", "task-A")
    task.run_id = run_a
    task.status = "running"
    task.worker_running = True
    interface.current_task = task
    interface.tasks_registry[task.task_id] = task

    result = web.get(f"/api/report/status?run_id={run_b}").get_json()

    assert result["current_task"] is None
    assert result["worker_busy"] is True
    assert web.post("/api/report/generate", json={"query": "same topic", "run_id": run_b}).status_code == 409
    own = web.get(f"/api/report/status?run_id={run_a}").get_json()
    assert own["current_task"]["task_id"] == "task-A"
    assert own["current_task"]["run_id"] == run_a


def test_run_status_selects_own_history_without_changing_global_task(report_api):
    interface, web = report_api
    task_a = interface.ReportTask("same topic", "task-A")
    task_a.run_id = "run-A"
    task_a.status = "completed"
    task_b = interface.ReportTask("same topic", "task-B")
    task_b.run_id = "run-B"
    task_b.status = "running"
    task_b.worker_running = True
    interface.current_task = task_b
    interface.tasks_registry.update({task_a.task_id: task_a, task_b.task_id: task_b})

    result = web.get("/api/report/status?run_id=run-A").get_json()

    assert result["current_task"]["task_id"] == "task-A"
    assert result["current_task"]["run_id"] == "run-A"
    assert result["worker_busy"] is True
    assert interface.current_task is task_b


def test_generate_binds_run_id_before_worker_starts(report_api, monkeypatch):
    interface, web = report_api
    run_id = interface.runtime_store.begin("topic", ["query"])
    monkeypatch.setattr(interface, "check_engines_ready", lambda _run: {"ready": True})

    class ReservedThread:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            pass

    monkeypatch.setattr(interface.threading, "Thread", ReservedThread)
    response = web.post("/api/report/generate", json={"query": "topic", "run_id": run_id})

    assert response.status_code == 200
    assert response.get_json()["task"]["run_id"] == run_id
    task = interface.tasks_registry[response.get_json()["task_id"]]
    assert task.run_id == run_id
    assert task.event_history[0]["payload"]["task"]["run_id"] == run_id


def test_legacy_status_and_historical_result_remain_accessible(report_api):
    interface, web = report_api
    task = interface.ReportTask("legacy topic", "legacy-report")
    task.status = "completed"
    task.html_content = "<html>legacy report</html>"
    interface.current_task = task
    interface.tasks_registry[task.task_id] = task

    assert web.get("/api/report/status").get_json()["current_task"]["task_id"] == "legacy-report"
    assert web.get("/api/report/status?run_id=other-run").get_json()["current_task"] is None
    assert web.get("/api/report/result/legacy-report").get_data(as_text=True) == "<html>legacy report</html>"
