"""Offline faults exercise real chapter streaming, storage and citation gates."""

import json
from concurrent.futures import CancelledError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import AuthenticationError, NotFoundError, RateLimitError

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from ReportEngine.agent import ReportAgent
from ReportEngine.core import ChapterStorage, DocumentComposer, TemplateSection
from ReportEngine.ir import IRValidator
from ReportEngine.llms.base import LLMClient
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode
from ReportEngine.renderers import HTMLRenderer, MarkdownRenderer
from ReportEngine.state import ReportState
from ReportEngine.utils.config import Settings


TEXT = "Auntie sells food at Tsinghua."


class FaultStream:
    def __init__(self, chunks, error=None, on_first=None):
        self.chunks = iter(chunks)
        self.error = error
        self.on_first = on_first
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.on_first:
            self.on_first()
            self.on_first = None
        try:
            return next(self.chunks)
        except StopIteration:
            if self.error:
                raise self.error
            raise

    def close(self):
        self.closed = True


def _chapter(title):
    return json.dumps({"chapterId": "ignored", "title": title, "anchor": "ignored", "order": 1,
                       "blocks": [{"type": "paragraph", "inlines": [{"text": TEXT}],
                                   "claims": [{"text": TEXT, "claim_type": "fact", "evidence_ids": ["e1"]}]}]})


def _agent(tmp_path, streams):
    agent = ReportAgent.__new__(ReportAgent)
    agent.config = Settings(_env_file=None, CHAPTER_JSON_MAX_ATTEMPTS=2)
    agent.state = ReportState()
    agent.chapter_storage = ChapterStorage(str(tmp_path / "chapters"))
    agent.validator = IRValidator()
    client = Mock()
    client.stream_invoke.side_effect = streams
    agent.chapter_generation_node = ChapterGenerationNode(
        client, agent.validator, agent.chapter_storage, error_log_dir=tmp_path / "errors"
    )
    agent.document_composer = DocumentComposer()
    agent.renderer = Mock()
    agent.renderer.render.side_effect = MarkdownRenderer().render
    agent._select_template = Mock(return_value={"template_name": "offline", "template_content": "## Overview\n## Details"})
    agent._slice_template = Mock(return_value=[
        TemplateSection("Overview", "overview", 10, 2, "Overview", chapter_id="S1"),
        TemplateSection("Details", "details", 20, 2, "Details", chapter_id="S2"),
    ])
    agent.document_layout_node = Mock()
    agent.document_layout_node.run.return_value = {"title": "offline", "hero": {}, "tocPlan": [], "tocTitle": "Contents"}
    agent.word_budget_node = Mock()
    agent.word_budget_node.run.return_value = {
        "chapters": [{"chapterId": "S1", "targetWords": 1000}, {"chapterId": "S2", "targetWords": 1000}],
        "totalWords": 2000, "globalGuidelines": [],
    }
    agent._save_report = Mock(return_value={})
    bundle = ProvenanceBundle(agent="report_engine", meta={"query": "Auntie"},
                              sources=[SourceRecord(source_id="s1", source_type="web", url="https://example.com/auntie")],
                              evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", evidence_type="web", snippet=TEXT)])
    return agent, client, bundle


def test_disconnect_retries_current_chapter_without_regenerating_previous(tmp_path):
    streams = [FaultStream([_chapter("Overview")]),
               FaultStream(['{"broken":'], httpx.RemoteProtocolError("incomplete chunked read")),
               FaultStream([_chapter("Details")])]
    agent, client, bundle = _agent(tmp_path, streams)
    agent.config.OUTPUT_DIR = str(tmp_path / "output")
    agent.config.DOCUMENT_IR_OUTPUT_DIR = str(tmp_path / "ir")
    agent.renderer = HTMLRenderer()
    agent._save_report = ReportAgent._save_report.__get__(agent)
    events = []

    result = agent.generate_report("Auntie", [TEXT], provenance_bundle=bundle,
                                   stream_handler=lambda event, data: events.append((event, data)))

    assert client.stream_invoke.call_count == 3
    assert all(stream.closed for stream in streams)
    assert agent.document_layout_node.run.call_count == 1
    assert agent.word_budget_node.run.call_count == 1
    manifest = json.loads(next((tmp_path / "chapters").glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert [item["status"] for item in manifest["chapters"]] == ["ready", "ready"]
    chapter_files = sorted((tmp_path / "chapters").glob("*/*/stream.raw"))
    assert [path.read_text(encoding="utf-8") for path in chapter_files] == [_chapter("Overview"), _chapter("Details")]
    assert '<!DOCTYPE html>' in result["html_content"]
    assert 'href="https://example.com/auntie"' in result["html_content"]
    compiled = json.loads(Path(result["ir_filepath"]).read_text(encoding="utf-8"))
    markdown = MarkdownRenderer().render(compiled)
    assert "[[1]](https://example.com/auntie" in markdown
    state = json.loads(Path(result["state_filepath"]).read_text(encoding="utf-8"))
    sidecar = json.loads(Path(result["provenance_filepath"]).read_text(encoding="utf-8"))
    assert Path(result["report_filepath"]).read_text(encoding="utf-8") == result["html_content"]
    assert state["status"] == "completed"
    assert state["provenance_bundle"] == sidecar == compiled["provenanceBundle"]
    assert len(compiled["claimIndex"]) == 2
    assert all(claim["evidence_ids"] == ["e1"] for claim in compiled["claimIndex"].values())
    details_chunks = [data for event, data in events if event == "chapter_chunk" and data["chapterId"] == "S2"]
    resets = [index for index, data in enumerate(details_chunks) if data.get("reset")]
    assert resets and resets[-1] < len(details_chunks) - 1
    assert details_chunks[-1]["delta"] == _chapter("Details")
    assert any(event == "chapter_status" and data.get("reason") == "transient_stream" for event, data in events)
    progress = [data["progress"] for event, data in events if event == "progress"]
    assert progress == sorted(progress)


@pytest.mark.parametrize("error", [
    AuthenticationError("unauthorized", response=httpx.Response(401, request=httpx.Request("POST", "https://example.com")), body={}),
    NotFoundError("model missing", response=httpx.Response(404, request=httpx.Request("POST", "https://example.com")), body={}),
    RateLimitError("quota exhausted", response=httpx.Response(429, request=httpx.Request("POST", "https://example.com")), body={"error": {"code": "insufficient_quota"}}),
    RuntimeError("programming failure"),
])
def test_non_transient_error_does_not_retry_chapter(tmp_path, error):
    stream = FaultStream(['{"partial":'], error)
    agent, client, bundle = _agent(tmp_path, [stream])

    with pytest.raises(type(error)):
        agent.generate_report("Auntie", [TEXT], provenance_bundle=bundle)

    assert client.stream_invoke.call_count == 1
    assert stream.closed
    assert next((tmp_path / "chapters").glob("*/*/stream.raw")).read_text(encoding="utf-8") == ""
    agent._save_report.assert_not_called()


def test_transient_retry_budget_is_bounded(tmp_path):
    streams = [FaultStream(['{"partial":'], httpx.RemoteProtocolError("closed")) for _ in range(4)]
    agent, client, bundle = _agent(tmp_path, streams)

    with pytest.raises(httpx.RemoteProtocolError):
        agent.generate_report("Auntie", [TEXT], provenance_bundle=bundle)

    assert client.stream_invoke.call_count == 2
    assert next((tmp_path / "chapters").glob("*/*/stream.raw")).read_text(encoding="utf-8") == ""
    agent._save_report.assert_not_called()


def test_cancellation_closes_stream_discards_partial_and_does_not_retry(tmp_path):
    cancelled = {"value": False}
    stream = FaultStream(['{"partial":', '"extra":'], on_first=lambda: cancelled.update(value=True))
    agent, client, bundle = _agent(tmp_path, [stream])

    with pytest.raises(CancelledError):
        agent.generate_report("Auntie", [TEXT], provenance_bundle=bundle,
                              cancel_check=lambda: cancelled["value"])

    assert client.stream_invoke.call_count == 1
    assert stream.closed
    assert agent.state.status == "cancelled"
    assert next((tmp_path / "chapters").glob("*/*/stream.raw")).read_text(encoding="utf-8") == ""
    agent._save_report.assert_not_called()


@pytest.mark.parametrize("cancelled", [False, True])
def test_flask_never_restarts_whole_report_after_agent_failure(tmp_path, monkeypatch, cancelled):
    from ReportEngine import flask_interface as interface
    task = interface.ReportTask("Auntie", "offline-failure")
    error = CancelledError("cancelled") if cancelled else httpx.RemoteProtocolError("closed")
    fake = Mock()
    fake.load_input_files.return_value = {"reports": [TEXT], "forum_logs": "", "provenance_bundle": ProvenanceBundle()}

    def fail(**kwargs):
        if cancelled:
            task.update_status("cancelled", task.progress)
        raise error

    fake.generate_report.side_effect = fail
    monkeypatch.setattr(interface, "report_agent", fake)
    monkeypatch.setattr(interface, "current_task", task)
    monkeypatch.setattr(interface, "check_engines_ready", lambda _run_id: {"ready": True, "latest_files": {}})
    monkeypatch.setattr(interface.time, "sleep", lambda _seconds: None)

    interface.run_report_generation(task, "Auntie")

    assert fake.generate_report.call_count == 1
    assert task.status == ("cancelled" if cancelled else "error")
    assert not any(event["type"] == "completed" for event in task.event_history)


@pytest.mark.parametrize("failure", [False, True])
def test_real_llm_wrapper_closes_underlying_sdk_stream(failure):
    error = httpx.RemoteProtocolError("closed") if failure else None
    chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="delta"))])
    stream = FaultStream([chunk], error)
    client = LLMClient.__new__(LLMClient)
    client.client = Mock()
    client.client.chat.completions.create.return_value = stream
    client.model_name = "offline"
    client.timeout = 10
    iterator = client.stream_invoke("system", "user")

    assert next(iterator) == "delta"
    if failure:
        with pytest.raises(httpx.RemoteProtocolError):
            next(iterator)
    else:
        iterator.close()

    assert stream.closed


@pytest.mark.parametrize("cancel_stage", ["persist", "html_ready", "error", "progress"])
def test_flask_cancellation_cannot_be_overwritten_by_terminal_results(monkeypatch, cancel_stage):
    from ReportEngine import flask_interface as interface
    task = interface.ReportTask("Auntie", "offline-terminal-cancel")
    fake = Mock()
    fake.load_input_files.return_value = {"reports": [TEXT], "forum_logs": ""}

    def generate(**kwargs):
        if cancel_stage == "error":
            task.update_status("cancelled", task.progress)
            raise httpx.RemoteProtocolError("closed after cancellation")
        if cancel_stage == "progress":
            kwargs["stream_handler"]("progress", {"progress": 60})
        return {"html_content": "<html>done</html>"}

    fake.generate_report.side_effect = generate
    publish_event = task.publish_event

    def publish(event, payload):
        publish_event(event, payload)
        if event == cancel_stage or payload.get("stage") == cancel_stage:
            task.update_status("cancelled", task.progress)

    task.publish_event = publish
    monkeypatch.setattr(interface, "report_agent", fake)
    monkeypatch.setattr(interface, "current_task", task)
    monkeypatch.setattr(interface, "check_engines_ready", lambda _run_id: {"ready": True, "latest_files": {}})

    interface.run_report_generation(task, "Auntie")

    assert task.status == "cancelled"
    assert fake.generate_report.call_count == 1
    assert not any(event["type"] in {"completed", "error"} for event in task.event_history)


@pytest.mark.parametrize("late_reservation", [False, True])
def test_cancelled_worker_reserves_agent_until_it_exits(monkeypatch, late_reservation):
    from flask import Flask
    from ReportEngine import flask_interface as interface
    task = interface.ReportTask("Auntie", "draining-worker")
    task.status = "cancelled"
    task.worker_running = True
    monkeypatch.setattr(interface, "current_task", None)
    monkeypatch.setattr(interface, "tasks_registry", {} if late_reservation else {task.task_id: task})
    monkeypatch.setattr(interface, "report_agent", Mock())
    monkeypatch.setattr(interface, "clear_report_log", lambda: None)
    thread = Mock()
    monkeypatch.setattr(interface.threading, "Thread", thread)

    def ready(_run_id):
        if late_reservation:
            interface.tasks_registry[task.task_id] = task
        return {"ready": True, "latest_files": {}}

    monkeypatch.setattr(interface, "check_engines_ready", ready)
    app = Flask(__name__)
    app.register_blueprint(interface.report_bp, url_prefix="/api/report")

    response = app.test_client().post("/api/report/generate", json={"query": "Auntie"})

    assert response.status_code == 409
    assert task.worker_running is True
    assert thread.call_count == 0


def test_cancelled_task_status_is_terminal_even_for_late_progress():
    from ReportEngine import flask_interface as interface
    task = interface.ReportTask("Auntie", "cancelled-terminal")
    task.update_status("cancelled", 40)

    for status in ("running", "completed", "error"):
        task.update_status(status, 100)

    assert task.status == "cancelled"
    assert task.progress == 40
