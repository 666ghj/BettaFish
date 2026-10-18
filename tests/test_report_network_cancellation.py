"""Active cancellation must end real OpenAI requests and their local sockets."""

import json
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event
from time import monotonic
from unittest.mock import Mock

import pytest
from flask import Flask

from common.cancellation import CancellationToken, cancellation_scope
from common.provenance.io import save_sidecar
from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from ReportEngine.agent import ReportAgent
from ReportEngine.core import ChapterStorage, DocumentComposer, TemplateSection
from ReportEngine.ir import IRValidator
from ReportEngine.llms import base as llm_module
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode
from ReportEngine.nodes.document_layout_node import DocumentLayoutNode
from ReportEngine.renderers import HTMLRenderer
from ReportEngine.state import ReportState
from ReportEngine.utils.config import Settings
from tests.report_network_test_support import BackgroundCall, LocalCompletionServer, ResponseStep


TEXT = "Auntie sells food at Tsinghua."
LAYOUT = {"title": "Offline report", "hero": {}, "tocPlan": [], "tocTitle": "Contents"}


@pytest.fixture(autouse=True)
def bounded_network_failures(monkeypatch):
    # If cancellation regresses, server teardown must not leave six 60-second
    # retries behind. The backoff-specific test enables its one required retry.
    monkeypatch.setattr(llm_module.LLM_RETRY_CONFIG, "max_retries", 0)


def _client(server):
    client = llm_module.LLMClient("offline-key", "offline", server.base_url)
    client.timeout = 10
    return client


def _in_scope(token, callback):
    with cancellation_scope(token):
        return callback()


def _wait_for_phase(step):
    event = {
        "before_headers": step.received,
        "before_token": step.headers_sent,
        "before_json_body": step.headers_sent,
        "after_token": step.token_sent,
    }[step.mode]
    assert event.wait(5), f"The local request did not reach {step.mode}"


def _assert_prompt_cancellation(token, caller, step=None):
    started = monotonic()
    deadline = started + 2
    cancellation = BackgroundCall(token.cancel)
    milestones = [
        (cancellation.done, "Cancellation itself did not return"),
        (caller.done, "The blocked model request did not exit"),
    ]
    if step:
        milestones.append((step.peer_closed, "The real HTTP socket remained open"))
    for event, description in milestones:
        assert event.wait(max(0, deadline - monotonic())), description
    assert cancellation.error is None
    assert isinstance(caller.error, CancelledError), repr(caller.error)
    assert monotonic() - started < 2
    if step:
        assert step.closed_at is not None and step.closed_at < deadline


@pytest.mark.parametrize(("method", "phase"), [
    ("stream", "before_headers"),
    ("stream", "before_token"),
    ("stream", "after_token"),
    ("joined_stream", "before_token"),
    ("invoke", "before_headers"),
    ("invoke", "before_json_body"),
])
def test_cancel_real_request_closes_socket_and_client_can_be_reused(method, phase):
    stalled = ResponseStep(phase, "partial response")
    response_mode = "json" if method == "invoke" else "stream"
    success = ResponseStep(response_mode, "fresh task response")
    token = CancellationToken()
    first_chunk = Event()

    with LocalCompletionServer(stalled, success) as server:
        client = _client(server)

        def request():
            if method == "invoke":
                return client.invoke("offline system", "offline user")
            if method == "joined_stream":
                return client.stream_invoke_to_string("offline system", "offline user")
            chunks = []
            for chunk in client.stream_invoke("offline system", "offline user"):
                chunks.append(chunk)
                first_chunk.set()
            return "".join(chunks)

        caller = BackgroundCall(lambda: _in_scope(token, request))
        try:
            _wait_for_phase(stalled)
            if phase == "after_token":
                assert first_chunk.wait(5), "The caller never consumed the first SSE delta"
            _assert_prompt_cancellation(token, caller, stalled)
            token.cancel()  # Public cancellation remains safe when repeated.
            assert server.request_count == 1

            fresh = BackgroundCall(lambda: _in_scope(CancellationToken(), request))
            assert fresh.finish() == "fresh task response"
            assert server.request_count == 2
            assert not server.errors
        finally:
            server.close()
            caller.done.wait(5)
            client.client.close()


def test_flask_cancel_interrupts_real_worker_and_releases_agent_for_next_report(tmp_path, monkeypatch):
    from ReportEngine import flask_interface as interface

    stalled = ResponseStep("after_token", '{"partial":')
    steps = [
        ResponseStep("stream", json.dumps(LAYOUT)), stalled,
        ResponseStep("stream", json.dumps(LAYOUT)), ResponseStep("stream", _chapter()),
    ]
    worker_done = {}
    worker_errors = []
    cancellation_seen = Event()
    chapter_received = Event()
    with LocalCompletionServer(*steps) as server:
        client = _client(server)
        agent, bundle = _agent(tmp_path, client)
        input_dir = tmp_path / "inputs"
        input_dir.mkdir()
        input_paths = {}
        for engine in ("query", "media", "insight"):
            path = input_dir / f"{engine}.md"
            path.write_text(TEXT, encoding="utf-8")
            engine_bundle = ProvenanceBundle(
                agent=f"{engine}_engine", meta={"query": "Auntie"},
            )
            if engine == "query":
                engine_bundle.sources = [SourceRecord.from_dict(source.to_dict()) for source in bundle.sources]
                engine_bundle.evidence = [EvidenceRecord.from_dict(evidence.to_dict()) for evidence in bundle.evidence]
                for record in (*engine_bundle.sources, *engine_bundle.evidence):
                    record.agent = engine_bundle.agent
            save_sidecar(engine_bundle, path)
            input_paths[engine] = str(path)

        real_generate = agent.generate_report

        def observe_generate(**kwargs):
            real_handler = kwargs["stream_handler"]

            def observe_event(event, data):
                real_handler(event, data)
                if event == "chapter_chunk" and data.get("delta"):
                    chapter_received.set()

            kwargs["stream_handler"] = observe_event
            try:
                return real_generate(**kwargs)
            except CancelledError:
                cancellation_seen.set()
                raise

        real_worker = interface.run_report_generation

        def observe_worker(task, *args):
            done = worker_done.setdefault(task.task_id, Event())
            try:
                real_worker(task, *args)
            except BaseException as error:
                worker_errors.append(error)
            finally:
                done.set()

        monkeypatch.setattr(agent, "generate_report", observe_generate)
        monkeypatch.setattr(interface, "report_agent", agent)
        monkeypatch.setattr(interface, "current_task", None)
        monkeypatch.setattr(interface, "tasks_registry", {})
        monkeypatch.setattr(interface, "run_report_generation", observe_worker)
        # Read the three real Markdown/sidecar files through load_input_files;
        # only the unrelated directory-baseline polling and shared log reset
        # are bypassed. The routes, workers, Agent and model transports are real.
        monkeypatch.setattr(interface, "check_engines_ready", lambda _run: {
            "ready": True, "latest_files": input_paths,
        })
        monkeypatch.setattr(interface, "clear_report_log", lambda: None)
        app = Flask(__name__)
        app.register_blueprint(interface.report_bp, url_prefix="/api/report")
        web = app.test_client()

        try:
            started = web.post("/api/report/generate", json={"query": "Auntie"})
            assert started.status_code == 200, started.get_json()
            task_id = started.get_json()["task_id"]
            task = interface.tasks_registry[task_id]
            _wait_for_phase(stalled)
            assert chapter_received.wait(5), "The real worker never captured the partial chapter"
            assert task.worker_running
            assert not task.cancellation_token.is_cancelled()

            cancellation_started = monotonic()
            deadline = cancellation_started + 2
            cancellation = BackgroundCall(lambda: app.test_client().post(f"/api/report/cancel/{task_id}"))
            for event, description in (
                (cancellation.done, "The cancellation HTTP route did not return"),
                (worker_done[task_id], "The real Report worker did not release its resources"),
                (stalled.peer_closed, "The cancelled worker left its model HTTP socket open"),
            ):
                assert event.wait(max(0, deadline - monotonic())), description
            assert cancellation.error is None
            assert cancellation.result.status_code == 200
            assert cancellation.result.get_json()["success"]
            assert monotonic() - cancellation_started < 2
            assert stalled.closed_at is not None and stalled.closed_at < deadline
            assert cancellation_seen.is_set(), "The real Agent did not unwind via CancelledError"
            assert task.cancellation_token.is_cancelled()
            assert task.status == agent.state.status == "cancelled"
            assert task.worker_running is False
            assert not task.html_content and not task.report_file_path
            assert not any(event["type"] in {"error", "completed", "html_ready"} for event in task.event_history)
            assert any(event["type"] == "cancelled" for event in task.event_history)
            for directory in (tmp_path / "output", tmp_path / "ir"):
                assert not list(directory.rglob("*"))
            assert next((tmp_path / "chapters").glob("*/*/stream.raw")).read_text(encoding="utf-8") == ""
            assert not worker_errors

            fresh_response = web.post("/api/report/generate", json={"query": "Auntie"})
            assert fresh_response.status_code == 200, fresh_response.get_json()
            fresh_id = fresh_response.get_json()["task_id"]
            assert fresh_id != task_id
            fresh_task = interface.tasks_registry[fresh_id]
            assert fresh_task.cancellation_token is not task.cancellation_token
            assert not fresh_task.cancellation_token.is_cancelled()
            assert worker_done.setdefault(fresh_id, Event()).wait(5)
            assert fresh_task.status == agent.state.status == "completed"
            assert fresh_task.worker_running is False
            assert not worker_errors
            assert any(event["type"] == "completed" for event in fresh_task.event_history)
            assert not any(event["type"] in {"error", "cancelled"} for event in fresh_task.event_history)
            result = web.get(f"/api/report/result/{fresh_id}")
            assert result.status_code == 200
            assert 'href="https://example.com/auntie"' in result.get_data(as_text=True)
            assert Path(fresh_task.report_file_path).is_file()
            assert Path(fresh_task.ir_file_path).is_file()
            assert Path(fresh_task.state_file_path).is_file()
            assert Path(fresh_task.report_file_path).with_suffix(".provenance.json").is_file()
            assert server.request_count == 4
            assert not server.errors
        finally:
            for registered_task in interface.tasks_registry.values():
                registered_task.cancellation_token.cancel()
            server.close()
            for done in worker_done.values():
                done.wait(5)
            client.client.close()


def test_real_503_retry_wait_is_cancelled_without_another_request(monkeypatch):
    class ObservedToken(CancellationToken):
        def __init__(self):
            super().__init__()
            self.wait_started = Event()

        def wait(self, timeout):
            self.wait_started.set()
            return super().wait(timeout)

    token = ObservedToken()
    monkeypatch.setattr(llm_module.LLM_RETRY_CONFIG, "max_retries", 1)
    monkeypatch.setattr(llm_module.LLM_RETRY_CONFIG, "initial_delay", 5)
    failed = ResponseStep("retry")
    with LocalCompletionServer(failed) as server:
        client = _client(server)
        caller = BackgroundCall(lambda: _in_scope(token, lambda: client.invoke("offline", "offline")))
        try:
            assert failed.received.wait(5)
            assert token.wait_started.wait(3), "The real 503 retry did not enter token.wait"
            _assert_prompt_cancellation(token, caller)
            assert server.request_count == 1
            assert not server.errors
        finally:
            token.cancel()
            server.close()
            caller.done.wait(6)
            client.client.close()


def _chapter():
    return json.dumps({
        "chapterId": "ignored", "title": "Overview", "anchor": "ignored", "order": 1,
        "blocks": [{"type": "paragraph", "inlines": [{"text": TEXT}],
                    "claims": [{"text": TEXT, "claim_type": "fact", "evidence_ids": ["e1"]}]}],
    })


def _agent(tmp_path, client):
    agent = ReportAgent.__new__(ReportAgent)
    agent.config = Settings(
        _env_file=None,
        CHAPTER_JSON_MAX_ATTEMPTS=1,
        OUTPUT_DIR=str(tmp_path / "output"),
        DOCUMENT_IR_OUTPUT_DIR=str(tmp_path / "ir"),
    )
    agent.state = ReportState()
    agent.chapter_storage = ChapterStorage(str(tmp_path / "chapters"))
    agent.validator = IRValidator()
    agent.chapter_generation_node = ChapterGenerationNode(
        client, agent.validator, agent.chapter_storage, error_log_dir=tmp_path / "errors"
    )
    agent.document_composer = DocumentComposer()
    agent.renderer = HTMLRenderer()
    agent._select_template = Mock(return_value={
        "template_name": "offline", "template_content": "## Overview",
    })
    agent._slice_template = Mock(return_value=[
        TemplateSection("Overview", "overview", 10, 2, "Overview", chapter_id="S1"),
    ])
    agent.document_layout_node = DocumentLayoutNode(client)
    agent.word_budget_node = Mock()
    agent.word_budget_node.run.return_value = {
        "chapters": [{"chapterId": "S1", "targetWords": 1000}],
        "totalWords": 1000, "globalGuidelines": [],
    }
    bundle = ProvenanceBundle(
        agent="report_engine", meta={"query": "Auntie"},
        sources=[SourceRecord(source_id="s1", source_type="web", url="https://example.com/auntie")],
        evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", evidence_type="web", snippet=TEXT)],
    )
    return agent, bundle


@pytest.mark.parametrize("stage", ["layout", "chapter"])
@pytest.mark.parametrize("phase", ["before_headers", "before_token", "after_token"])
def test_report_cancel_discards_partial_and_next_real_report_completes(tmp_path, stage, phase):
    stalled = ResponseStep(phase, '{"partial":')
    steps = [] if stage == "layout" else [ResponseStep("stream", json.dumps(LAYOUT))]
    steps.extend([stalled, ResponseStep("stream", json.dumps(LAYOUT)), ResponseStep("stream", _chapter())])
    token = CancellationToken()
    events = []
    chapter_delta = Event()

    def handle_event(event, data):
        events.append((event, data))
        if event == "chapter_chunk" and data.get("delta"):
            chapter_delta.set()

    with LocalCompletionServer(*steps) as server:
        client = _client(server)
        agent, bundle = _agent(tmp_path, client)

        def generate(active_token):
            return _in_scope(active_token, lambda: agent.generate_report(
                "Auntie", [TEXT], provenance_bundle=bundle,
                cancel_check=active_token.is_cancelled, stream_handler=handle_event,
            ))

        caller = BackgroundCall(lambda: generate(token))
        try:
            _wait_for_phase(stalled)
            if stage == "chapter" and phase == "after_token":
                assert chapter_delta.wait(5), "The chapter never captured its first real SSE delta"
            _assert_prompt_cancellation(token, caller, stalled)
            assert agent.state.status == "cancelled"
            assert not any(event in {"completed", "error", "html_ready"} for event, _ in events)
            assert not any(data.get("status") == "error" for _, data in events)
            for directory in (tmp_path / "output", tmp_path / "ir"):
                assert not list(directory.rglob("*")), "Cancellation persisted a final report artifact"
            raw_files = list((tmp_path / "chapters").glob("*/*/stream.raw"))
            assert len(raw_files) == (1 if stage == "chapter" else 0)
            assert all(path.read_text(encoding="utf-8") == "" for path in raw_files)

            cancelled_task_id = agent.state.task_id
            events.clear()
            fresh = BackgroundCall(lambda: generate(CancellationToken()))
            result = fresh.finish()
            assert agent.state.task_id != cancelled_task_id
            assert agent.state.status == "completed"
            assert '<!DOCTYPE html>' in result["html_content"]
            assert 'href="https://example.com/auntie"' in result["html_content"]
            for key in ("report_filepath", "ir_filepath", "state_filepath", "provenance_filepath"):
                assert Path(result[key]).is_file()
            compiled = json.loads(Path(result["ir_filepath"]).read_text(encoding="utf-8"))
            sidecar = json.loads(Path(result["provenance_filepath"]).read_text(encoding="utf-8"))
            assert compiled["provenanceBundle"] == sidecar
            assert len(compiled["claimIndex"]) == 1
            assert server.request_count == (3 if stage == "layout" else 4)
            assert not server.errors
        finally:
            server.close()
            caller.done.wait(5)
            client.client.close()
