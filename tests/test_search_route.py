import atexit
import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Blueprint
from common.provenance.runtime import RuntimeProvenanceStore


class DummyThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


class DummySocketIO:
    def __init__(self, *args, **kwargs):
        pass

    def emit(self, *args, **kwargs):
        pass

    def on(self, _event):
        return lambda function: function

    def run(self, *args, **kwargs):
        pass

    def stop(self):
        pass


def _remove_modules(prefixes):
    saved = {
        name: module
        for name, module in list(sys.modules.items())
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
    }
    for name in saved:
        sys.modules.pop(name, None)
    return saved


@pytest.fixture
def root_app(monkeypatch, tmp_path):
    prefixes = ("bettafish_app_under_test", "MindSpider", "ReportEngine", "flask_socketio")
    saved_modules = _remove_modules(prefixes)

    mindspider_package = ModuleType("MindSpider")
    mindspider_package.__path__ = []
    mindspider_main = ModuleType("MindSpider.main")
    mindspider_main.MindSpider = type("MindSpider", (), {})

    report_package = ModuleType("ReportEngine")
    report_package.__path__ = []
    report_interface = ModuleType("ReportEngine.flask_interface")
    report_interface.report_bp = Blueprint("stub_report", __name__)
    report_interface.initialize_report_engine = lambda: True

    socketio_module = ModuleType("flask_socketio")
    socketio_module.SocketIO = DummySocketIO
    socketio_module.emit = lambda *args, **kwargs: None

    # This fixture owns module restoration in its finally block. A later
    # monkeypatch undo would delete the real modules restored there.
    sys.modules.update({
        "MindSpider": mindspider_package,
        "MindSpider.main": mindspider_main,
        "ReportEngine": report_package,
        "ReportEngine.flask_interface": report_interface,
        "flask_socketio": socketio_module,
    })
    monkeypatch.chdir(tmp_path)

    source_path = Path(__file__).resolve().parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("bettafish_app_under_test", source_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    with patch.object(threading, "Thread", DummyThread), patch.object(
        atexit, "register", lambda *args, **kwargs: None
    ):
        spec.loader.exec_module(module)

    try:
        yield module, module.app.test_client()
    finally:
        _remove_modules(prefixes)
        sys.modules.update(saved_modules)


def test_search_skips_forum_and_calls_searchable_engine(root_app, monkeypatch):
    module, client = root_app
    module.processes = {
        "insight": {"status": "running", "port": 8501},
        "forum": {"status": "running"},
    }
    monkeypatch.setattr(module, "check_app_status", lambda: None)
    engine_response = Mock(status_code=200)
    engine_response.json.return_value = {"success": True, "items": ["result"]}
    post = Mock(return_value=engine_response)
    monkeypatch.setattr(module.requests, "post", post)

    response = client.post("/api/search", json={"query": "BettaFish"})

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "query": "BettaFish",
        "results": {"insight": {"success": True, "items": ["result"]}},
    }
    post.assert_called_once_with(
        "http://localhost:8501/api/search",
        json={"query": "BettaFish"},
        timeout=10,
    )


def test_search_with_only_forum_returns_empty_engine_results(root_app, monkeypatch):
    module, client = root_app
    module.processes = {"forum": {"status": "running"}}
    monkeypatch.setattr(module, "check_app_status", lambda: None)
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)

    response = client.post("/api/search", json={"query": "BettaFish"})

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "query": "BettaFish",
        "results": {},
    }
    post.assert_not_called()


def test_search_uses_configured_engine_port(root_app, monkeypatch):
    module, client = root_app
    module.processes = {
        "insight": {"status": "running", "port": 8551},
        "forum": {"status": "stopped", "port": None},
    }
    monkeypatch.setattr(module, "check_app_status", lambda: None)
    engine_response = Mock(status_code=200)
    engine_response.json.return_value = {"success": True}
    post = Mock(return_value=engine_response)
    monkeypatch.setattr(module.requests, "post", post)

    response = client.post("/api/search", json={"query": "BettaFish"})

    assert response.status_code == 200
    post.assert_called_once_with(
        "http://localhost:8551/api/search",
        json={"query": "BettaFish"},
        timeout=10,
    )


def test_index_injects_configured_engine_ports(root_app):
    module, client = root_app
    module.processes["insight"]["port"] = 8551
    module.processes["media"]["port"] = 8552
    module.processes["query"]["port"] = 8553

    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'const APP_PORTS = {"insight": 8551, "media": 8552, "query": 8553};' in page


def test_runtime_provenance_routes_complete_one_engine_run(root_app):
    module, client = root_app
    begin = client.post(
        "/api/provenance/runs",
        json={"query": "BettaFish", "engines": ["query"]},
    )
    assert begin.status_code == 200
    run_id = begin.get_json()["run_id"]

    publish = client.post(
        "/api/provenance/result",
        json={
            "run_id": run_id,
            "engine": "query",
            "query": "BettaFish",
            "report": "done",
            "bundle": {
                "agent": "query_engine",
                "meta": {"query": "BettaFish", "run_id": run_id},
            },
            "status": "complete",
        },
        headers={"X-Provenance-Token": module.PROVENANCE_TOKEN},
    )

    assert publish.status_code == 200
    assert module.runtime_store.status(run_id)["ready"] is True


def test_runtime_provenance_run_route_returns_429_at_active_capacity(root_app):
    module, client = root_app
    module.runtime_store = RuntimeProvenanceStore(max_runs=1)
    first = client.post(
        "/api/provenance/runs",
        json={"query": "first", "engines": ["query"]},
    )

    second = client.post(
        "/api/provenance/runs",
        json={"query": "second", "engines": ["query"]},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.get_json()["success"] is False
    assert "容量已满" in second.get_json()["error"]


def test_runtime_provenance_run_route_defaults_to_all_engines_when_omitted(root_app):
    module, client = root_app

    response = client.post("/api/provenance/runs", json={"query": "BettaFish"})

    assert response.status_code == 200
    run_id = response.get_json()["run_id"]
    assert module.runtime_store.context(run_id)["expected"] == [
        "query",
        "media",
        "insight",
    ]


@pytest.mark.parametrize(
    "engines, expected_error",
    [
        ([], "不能为空"),
        (["query", "other"], "不支持"),
        ("query", "列表"),
    ],
)
def test_runtime_provenance_run_route_rejects_invalid_engine_selection(
    root_app, engines, expected_error
):
    _module, client = root_app

    response = client.post(
        "/api/provenance/runs",
        json={"query": "BettaFish", "engines": engines},
    )

    assert response.status_code == 400
    assert expected_error in response.get_json()["error"]


def test_runtime_provenance_route_records_failure(root_app):
    module, client = root_app
    begin = client.post(
        "/api/provenance/runs",
        json={"query": "BettaFish", "engines": ["insight"]},
    )
    run_id = begin.get_json()["run_id"]

    publish = client.post(
        "/api/provenance/result",
        json={
            "run_id": run_id,
            "engine": "insight",
            "query": "BettaFish",
            "status": "failed",
            "error": "model unavailable",
        },
        headers={"X-Provenance-Token": module.PROVENANCE_TOKEN},
    )

    assert publish.status_code == 200
    assert module.runtime_store.status(run_id)["failed"] == {
        "insight": "model unavailable"
    }


def test_runtime_provenance_route_rejects_bad_token(root_app):
    _module, client = root_app

    response = client.post(
        "/api/provenance/result",
        json={},
        headers={"X-Provenance-Token": "wrong"},
    )

    assert response.status_code == 403
