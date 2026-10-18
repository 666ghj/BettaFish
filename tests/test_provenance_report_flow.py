"""Exercise public run/callback/report routes and final artifacts together."""

import json
from copy import deepcopy
from pathlib import Path
from threading import Event

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.runtime import RuntimeProvenanceStore
from ReportEngine import flask_interface as interface
from ReportEngine.renderers import MarkdownRenderer
from ReportEngine.utils.chart_review_service import get_chart_review_service
from tests.report_network_test_support import LocalCompletionServer, ResponseStep
from tests.test_report_network_cancellation import _agent, _client, LAYOUT
from tests.test_search_route import root_app


def test_callbacks_to_real_report_worker_preserve_run_and_exported_sources(root_app, tmp_path, monkeypatch):
    module, web = root_app
    store = RuntimeProvenanceStore()
    monkeypatch.setattr(module, "runtime_store", store)
    monkeypatch.setattr(module, "PROVENANCE_TOKEN", "offline-callback-token")
    monkeypatch.setattr(interface, "runtime_store", store)
    monkeypatch.setattr(interface, "current_task", None)
    monkeypatch.setattr(interface, "tasks_registry", {})
    monkeypatch.setattr(interface, "clear_report_log", lambda: None)
    # root_app substitutes only the process-launching integrations at import.
    # Register the real Report blueprint for this isolated Flask application.
    module.app.register_blueprint(interface.report_bp, url_prefix="/api/report")
    query, fact = "今天热度", "今天热度为 42。"
    source_url = "https://example.com/heat"
    claim = {"text": fact, "claim_type": "metric", "evidence_ids": ["e1"]}
    chart = {
        "type": "widget", "widgetType": "chart.js/bar", "widgetId": "valid-chart",
        "props": {"type": "bar", "options": {"responsive": True}},
        "data": {"labels": ["今天"], "datasets": [{"label": "热度", "data": [42]}]},
        "claims": [claim],
    }
    incomplete = deepcopy(chart)
    incomplete["widgetId"] = "no-unverified-fallback"
    incomplete["data"].pop("datasets")
    table = {"type": "table", "rows": [{"cells": [
        {"blocks": [{"type": "paragraph", "inlines": [{"text": fact}], "claims": [claim]}]},
        {"blocks": [{"type": "paragraph", "inlines": [{"text": fact}],
                     "claims": [{**claim, "claim_type": "prediction"}]}]},
    ]}]}
    chapter = {"chapterId": "S1", "title": "Overview", "anchor": "overview", "order": 1,
               "blocks": [chart, incomplete, table],
               "data": {"labels": ["今天"], "datasets": [{"label": "热度", "data": [99]}]}}
    with LocalCompletionServer(ResponseStep("stream", json.dumps(LAYOUT)),
                               ResponseStep("stream", json.dumps(chapter))) as server:
        client = _client(server)
        agent, _ = _agent(tmp_path, client)
        # Repair failures must not escape to a paid provider in an offline test.
        service = get_chart_review_service()
        monkeypatch.setattr(service.repairer, "llm_repair_fns", [])
        monkeypatch.setattr(agent.renderer.chart_repairer, "llm_repair_fns", [])
        monkeypatch.setattr(interface, "report_agent", agent)
        worker_done = Event()
        actual_worker = interface.run_report_generation

        def run_worker(*args):
            try:
                actual_worker(*args)
            finally:
                worker_done.set()

        monkeypatch.setattr(interface, "run_report_generation", run_worker)
        try:
            started = web.post("/api/provenance/runs", json={"query": query})
            assert started.status_code == 200
            run_id = started.get_json()["run_id"]
            assert not web.get(f"/api/report/status?run_id={run_id}").get_json()["engines_ready"]
            for engine in ("query", "media", "insight"):
                bundle = ProvenanceBundle(agent=f"{engine}_engine", meta={"query": query, "run_id": run_id})
                if engine == "query":
                    bundle.sources = [SourceRecord(source_id="s1", agent=bundle.agent, source_type="web", url=source_url)]
                    bundle.evidence = [EvidenceRecord(evidence_id="e1", source_id="s1", agent=bundle.agent, evidence_type="web", snippet=fact)]
                response = web.post("/api/provenance/result", headers={"X-Provenance-Token": "offline-callback-token"},
                                    json={"run_id": run_id, "engine": engine, "query": query,
                                          "report": fact, "bundle": bundle.to_dict()})
                assert response.status_code == 200, response.get_json()
            assert web.get(f"/api/report/status?run_id={run_id}").get_json()["engines_ready"]
            response = web.post("/api/report/generate", json={"query": query, "run_id": run_id})
            assert response.status_code == 200, response.get_json()
            task_id = response.get_json()["task_id"]
            assert worker_done.wait(15), "The local report worker did not finish"
            task = interface.tasks_registry[task_id]
            assert task.status == "completed", task.error_message
            assert not task.worker_running
            own = web.get(f"/api/report/status?run_id={run_id}").get_json()
            assert own["current_task"]["run_id"] == run_id
            assert own["current_task"]["task_id"] == task_id
            html = web.get(f"/api/report/result/{task_id}").get_data(as_text=True)
            ir = json.loads(Path(task.ir_file_path).read_text(encoding="utf-8"))
            state = json.loads(Path(task.state_file_path).read_text(encoding="utf-8"))
            sidecar = json.loads(Path(task.report_file_path).with_suffix(".provenance.json").read_text(encoding="utf-8"))
            markdown = MarkdownRenderer().render(ir)
            assert state["provenance_bundle"] == sidecar == ir["provenanceBundle"]
            assert sidecar["meta"]["run_id"] == run_id
            assert f'href="{source_url}"' in html
            assert f"[[1]]({source_url}" in markdown and "**[预测]**" in markdown
            assert '"data": [99]' not in html and "| 今天 | 99 |" not in markdown
            charts = [block for block in ir["chapters"][0]["blocks"] if block["type"] == "widget"]
            assert charts[0]["data"]["datasets"][0]["data"] == [42]
            assert "datasets" not in charts[1]["data"]
            newer = web.post("/api/provenance/runs", json={"query": query}).get_json()["run_id"]
            assert web.get(f"/api/report/status?run_id={newer}").get_json()["current_task"] is None
            assert web.get(f"/api/report/result/{task_id}").status_code == 200
            assert server.request_count == 2 and not server.errors
        finally:
            for task in interface.tasks_registry.values():
                task.cancellation_token.cancel()
            server.close()
            if interface.tasks_registry:
                worker_done.wait(5)
            client.client.close()
