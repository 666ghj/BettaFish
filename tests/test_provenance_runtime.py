import unittest
import copy
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.io import save_sidecar, sidecar_path
from common.provenance.runtime import (
    RuntimeCapacityError,
    RuntimeProvenanceStore,
    append_runtime_forum_message,
    publish_runtime_result,
    read_runtime_forum_context,
)
from ReportEngine.core.stitcher import DocumentComposer
from ReportEngine.agent import ReportAgent
from ReportEngine.state import ReportState


class RuntimeProvenanceTests(unittest.TestCase):
    def test_begin_defaults_to_all_engines_only_when_selection_is_omitted(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("topic")

        self.assertEqual(
            store.context(run_id)["expected"],
            ["query", "media", "insight"],
        )

        with self.assertRaisesRegex(ValueError, "不能为空"):
            store.begin("topic", [])

    def test_begin_rejects_unknown_duplicate_and_non_collection_engines(self):
        store = RuntimeProvenanceStore()

        with self.assertRaisesRegex(ValueError, "不支持"):
            store.begin("topic", ["query", "other"])
        with self.assertRaisesRegex(ValueError, "重复"):
            store.begin("topic", ["query", "QUERY"])
        with self.assertRaisesRegex(ValueError, "列表"):
            store.begin("topic", "query")

    def test_forum_evidence_ids_never_treat_strings_as_character_ids(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)

            def forum_path(run_id, engine):
                return root / "forum_runs" / run_id / f"{engine}.jsonl"

            with patch(
                "common.provenance.runtime._runtime_forum_path",
                side_effect=forum_path,
            ):
                self.assertFalse(
                    append_runtime_forum_message("run-a", "query", "消息", "evidence-1")
                )
                self.assertTrue(
                    append_runtime_forum_message(
                        "run-a", "query", "消息", ["evidence-1"]
                    )
                )
                self.assertEqual(
                    read_runtime_forum_context("run-a", "evidence-1"),
                    "",
                )
                context = read_runtime_forum_context("run-a", ["evidence-1"])

        self.assertIn('EVIDENCE_IDS:["evidence-1"]', context)

    def test_empty_engine_result_is_retained_for_the_current_run(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("test topic", ["query", "insight"])
        store.publish(
            run_id,
            "query",
            "test topic",
            "query report",
            ProvenanceBundle(
                agent="query_engine",
                meta={"query": "test topic", "run_id": run_id},
            ),
        )
        store.publish(
            run_id,
            "insight",
            "test topic",
            "no internal evidence",
            ProvenanceBundle(
                agent="insight_engine",
                meta={"query": "test topic", "run_id": run_id},
            ),
        )

        inputs = store.inputs(run_id, "test topic")

        self.assertEqual(inputs["reports"], ["query report", "", "no internal evidence"])
        self.assertEqual(inputs["provenance_bundle"].evidence, [])

    def test_document_composer_rejects_external_evidence_without_a_source_url(self):
        bundle = ProvenanceBundle(
            agent="query_engine",
            sources=[SourceRecord(source_id="source-1", source_type="web", title="missing link")],
            evidence=[
                EvidenceRecord(
                    evidence_id="evidence-1",
                    source_id="source-1",
                    agent="query_engine",
                    evidence_type="web",
                    snippet="A claimed fact.",
                )
            ],
        )
        chapter = {
            "chapterId": "S1",
            "title": "Evidence",
            "order": 10,
            "blocks": [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "A claimed fact."}],
                    "claims": [
                        {
                            "claim_id": "claim-1",
                            "text": "A claimed fact.",
                            "claim_type": "fact",
                            "evidence_ids": ["evidence-1"],
                        }
                    ],
                }
            ],
        }

        document = DocumentComposer().build_document("report-1", {}, [chapter], bundle)

        self.assertEqual(document["provenanceIndex"]["evidence"], {})
        blocks = document["chapters"][0]["blocks"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "heading")
        self.assertNotIn("本段未检索到可追溯证据", str(blocks))

    def test_document_composer_preserves_normalized_bundle_identity(self):
        bundle = ProvenanceBundle(
            bundle_id="normalized-bundle",
            agent="report_engine",
            sources=[SourceRecord(source_id="source-1", source_type="web", url="https://example.com")],
            evidence=[
                EvidenceRecord(
                    evidence_id="evidence-1",
                    source_id="source-1",
                    evidence_type="web",
                    snippet="A claimed fact.",
                )
            ],
        )
        chapter = {
            "chapterId": "S1",
            "title": "Evidence",
            "order": 10,
            "blocks": [
                {"type": "heading", "level": 2, "text": "Evidence", "anchor": "evidence"},
                {
                    "type": "paragraph",
                    "inlines": [{"text": "A claimed fact."}],
                    "claims": [
                        {
                            "claim_id": "claim-1",
                            "text": "A claimed fact.",
                            "claim_type": "fact",
                            "evidence_ids": ["evidence-1"],
                        }
                    ],
                },
            ],
        }
        before = copy.deepcopy(bundle.to_dict())

        document = DocumentComposer().build_document("report-1", {}, [chapter], bundle)

        self.assertEqual(document["provenanceBundle"]["bundle_id"], "normalized-bundle")
        self.assertEqual(set(document["claimIndex"]), {"claim-1"})
        self.assertEqual(bundle.to_dict(), before)

    def test_failed_engine_is_terminal_and_reported_separately(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("topic", ["query", "insight"])
        store.publish(
            run_id,
            "query",
            "topic",
            "done",
            ProvenanceBundle(
                agent="query_engine",
                meta={"query": "topic", "run_id": run_id},
            ),
        )
        store.fail(run_id, "insight", "topic", "model unavailable")

        status = store.status(run_id)

        self.assertFalse(status["ready"])
        self.assertEqual(status["missing_files"], [])
        self.assertEqual(status["failed"], {"insight": "model unavailable"})
        with self.assertRaisesRegex(ValueError, "model unavailable"):
            store.inputs(run_id, "topic")

    def test_first_terminal_engine_result_wins_and_duplicates_are_idempotent(self):
        success_first = RuntimeProvenanceStore()
        success_run = success_first.begin("topic", ["query"])
        bundle = ProvenanceBundle(
            agent="query_engine",
            meta={"query": "topic", "run_id": success_run},
        )
        self.assertTrue(success_first.publish(success_run, "query", "topic", "done", bundle))
        self.assertFalse(success_first.publish(success_run, "query", "topic", "duplicate", bundle))
        self.assertFalse(success_first.fail(success_run, "query", "topic", "late error"))
        self.assertTrue(success_first.status(success_run)["ready"])
        self.assertEqual(success_first.inputs(success_run, "topic")["reports"][0], "done")

        failure_first = RuntimeProvenanceStore()
        failure_run = failure_first.begin("topic", ["query"])
        self.assertTrue(failure_first.fail(failure_run, "query", "topic", "first error"))
        self.assertFalse(failure_first.publish(failure_run, "query", "topic", "late", bundle))
        self.assertEqual(
            failure_first.status(failure_run)["failed"],
            {"query": "first error"},
        )

    def test_runtime_rejects_bundle_from_a_different_run_or_query(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("topic", ["query"])

        with self.assertRaisesRegex(ValueError, "运行任务"):
            store.publish(
                run_id,
                "query",
                "topic",
                "report",
                ProvenanceBundle(
                    agent="query_engine",
                    meta={"query": "topic", "run_id": "other-run"},
                ),
            )

        with self.assertRaisesRegex(ValueError, "报告查询"):
            store.publish(
                run_id,
                "query",
                "topic",
                "report",
                ProvenanceBundle(
                    agent="query_engine",
                    meta={"query": "other-topic", "run_id": run_id},
                ),
            )

    def test_runtime_rejects_foreign_record_agent(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("topic", ["query"])

        with self.assertRaisesRegex(ValueError, "source"):
            store.publish(
                run_id,
                "query",
                "topic",
                "report",
                ProvenanceBundle(
                    agent="query_engine",
                    sources=[SourceRecord(source_id="s", agent="media_engine")],
                    meta={"query": "topic", "run_id": run_id},
                ),
            )

    def test_runtime_rejects_missing_record_agent(self):
        store = RuntimeProvenanceStore()
        run_id = store.begin("topic", ["query"])

        with self.assertRaisesRegex(ValueError, "缺少发布引擎身份"):
            store.publish(
                run_id,
                "query",
                "topic",
                "report",
                ProvenanceBundle(
                    agent="query_engine",
                    sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com")],
                    evidence=[EvidenceRecord(
                        evidence_id="e",
                        source_id="s",
                        evidence_type="web",
                        snippet="事实",
                    )],
                    meta={"query": "topic", "run_id": run_id},
                ),
            )

    def test_active_and_terminal_runs_expire_by_their_own_ttls(self):
        now = [0.0]
        store = RuntimeProvenanceStore(
            active_ttl_seconds=10,
            terminal_ttl_seconds=3,
            clock=lambda: now[0],
        )
        active = store.begin("active", ["query"])
        now[0] = 10.0
        with self.assertRaisesRegex(ValueError, "过期或不存在"):
            store.context(active)

        terminal = store.begin("terminal", ["query"])
        store.publish(
            terminal,
            "query",
            "terminal",
            "done",
            ProvenanceBundle(
                agent="query_engine",
                meta={"query": "terminal", "run_id": terminal},
            ),
        )
        now[0] = 13.0
        self.assertFalse(store.status(terminal)["ready"])

    def test_runtime_forum_context_is_run_scoped_and_evidence_checked(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)

            def forum_path(run_id, engine):
                return root / "forum_runs" / run_id / f"{engine}.jsonl"

            with patch(
                "common.provenance.runtime._runtime_forum_path",
                side_effect=forum_path,
            ):
                self.assertTrue(append_runtime_forum_message("run-a", "query", "A消息", ["a1"]))
                self.assertTrue(append_runtime_forum_message("run-b", "query", "B消息", ["b1"]))
                self.assertTrue(append_runtime_forum_message("run-a", "media", "外来证据", ["b1"]))

                context = read_runtime_forum_context("run-a", {"a1"})

        self.assertIn("A消息", context)
        self.assertIn('EVIDENCE_IDS:["a1"]', context)
        self.assertNotIn("B消息", context)
        self.assertNotIn("外来证据", context)

    def test_forum_context_keeps_allowed_evidence_beyond_200_records(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)

            def forum_path(run_id, engine):
                return root / "forum_runs" / run_id / f"{engine}.jsonl"

            with patch(
                "common.provenance.runtime._runtime_forum_path",
                side_effect=forum_path,
            ):
                append_runtime_forum_message("run-large", "query", "合法来源摘要", ["e200"])
                append_runtime_forum_message("run-large", "media", "未知来源摘要", ["foreign"])

                context = read_runtime_forum_context(
                    "run-large", [f"e{index}" for index in range(201)]
                )

        self.assertIn("合法来源摘要", context)
        self.assertIn('EVIDENCE_IDS:["e200"]', context)
        self.assertNotIn("未知来源摘要", context)

    def test_capacity_limit_rejects_new_run_when_all_slots_are_active(self):
        store = RuntimeProvenanceStore(max_runs=1)
        first = store.begin("first", ["query"])

        with self.assertRaisesRegex(RuntimeCapacityError, "容量已满"):
            store.begin("second", ["query"])
        self.assertEqual(store.context(first)["query"], "first")

    def test_capacity_limit_reclaims_oldest_terminal_run(self):
        store = RuntimeProvenanceStore(max_runs=1)
        first = store.begin("first", ["query"])
        store.publish(
            first,
            "query",
            "first",
            "done",
            ProvenanceBundle(
                agent="query_engine",
                meta={"query": "first", "run_id": first},
            ),
        )

        second = store.begin("second", ["query"])

        with self.assertRaisesRegex(ValueError, "过期或不存在"):
            store.context(first)
        self.assertEqual(store.context(second)["query"], "second")

    def test_capacity_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "大于 0"):
            RuntimeProvenanceStore(max_runs=0)

    def test_saved_ir_state_and_sidecar_share_exact_final_bundle(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "reports"
            ir_dir = output_dir / "ir"
            output_dir.mkdir()
            ir_dir.mkdir()
            bundle = ProvenanceBundle(
                bundle_id="final-bundle",
                agent="report_engine",
                claims=[],
            )
            agent = ReportAgent.__new__(ReportAgent)
            agent.config = SimpleNamespace(
                OUTPUT_DIR=str(output_dir),
                DOCUMENT_IR_OUTPUT_DIR=str(ir_dir),
            )
            agent.state = ReportState(query="topic", provenance_bundle=bundle)
            document_ir = {"provenanceBundle": bundle.to_dict(), "chapters": []}

            paths = agent._save_report("<html></html>", document_ir, "report-1")

            saved_ir = json.loads(Path(paths["ir_filepath"]).read_text(encoding="utf-8"))
            saved_state = json.loads(Path(paths["state_filepath"]).read_text(encoding="utf-8"))
            saved_sidecar = json.loads(
                Path(paths["provenance_filepath"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved_ir["provenanceBundle"], bundle.to_dict())
            self.assertEqual(saved_state["provenance_bundle"], bundle.to_dict())
            self.assertEqual(saved_sidecar, bundle.to_dict())
            html_suffix = paths["report_filename"].removeprefix("final_report_topic_").removesuffix(".html")
            self.assertEqual(
                paths["ir_filename"],
                f"report_ir_topic_{html_suffix}.json",
            )
            self.assertEqual(
                paths["state_filename"],
                f"report_state_topic_{html_suffix}.json",
            )
            self.assertEqual(
                paths["provenance_filename"],
                f"final_report_topic_{html_suffix}.provenance.json",
            )

    def test_malformed_sidecar_does_not_shift_report_slots(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            paths = {}
            for engine, text_value in (("query", "Q"), ("media", "M"), ("insight", "I")):
                report_path = root / f"{engine}.md"
                report_path.write_text(text_value, encoding="utf-8")
                paths[engine] = str(report_path)
            (root / "query.provenance.json").write_text("{broken", encoding="utf-8")
            agent = ReportAgent.__new__(ReportAgent)

            loaded = agent.load_input_files(paths)

            self.assertEqual(loaded["reports"], ["Q", "M", "I"])
            self.assertEqual(loaded["provenance_bundle"].evidence, [])

    def test_legacy_disk_input_rejects_sidecar_from_another_query(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            report_path = Path(temp_dir) / "query.md"
            report_path.write_text("old report", encoding="utf-8")
            save_sidecar(
                ProvenanceBundle(agent="query_engine", meta={"query": "旧查询"}),
                report_path,
            )
            agent = ReportAgent.__new__(ReportAgent)

            with self.assertRaisesRegex(ValueError, "与当前查询不匹配"):
                agent.load_input_files(
                    {"query": str(report_path)},
                    expected_query="新查询",
                )

    def test_sidecar_write_is_atomic_and_preserves_previous_file_on_replace_failure(self):
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            report_path.write_text("report", encoding="utf-8")
            target = sidecar_path(report_path)
            target.write_text('{"previous": true}', encoding="utf-8")

            with patch("common.provenance.io.os.replace", side_effect=OSError("interrupted")):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    save_sidecar(ProvenanceBundle(bundle_id="new"), report_path)

            self.assertEqual(target.read_text(encoding="utf-8"), '{"previous": true}')
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_legacy_reports_without_provenance_fail_as_insufficient_input(self):
        agent = ReportAgent.__new__(ReportAgent)
        agent.state = ReportState(query="topic")
        agent.state.metadata.query = "topic"
        agent._normalize_reports = ReportAgent._normalize_reports.__get__(agent)
        agent._normalize_provenance_bundle = ReportAgent._normalize_provenance_bundle.__get__(agent)

        with self.assertRaisesRegex(ValueError, "insufficient-input"):
            agent.generate_report("topic", ["Q", "M", "I"], save_report=False)

        self.assertEqual(agent.state.status, "failed")

    def test_duplicate_claim_ids_are_namespaced_in_blocks_and_index(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s1", source_type="web", url="https://example.com")],
            evidence=[EvidenceRecord(
                evidence_id="e1", source_id="s1", evidence_type="web",
                snippet="First fact. Second fact.",
            )],
        )
        chapters = []
        for chapter_id, text_value in (("S1", "First fact."), ("S2", "Second fact.")):
            chapters.append({
                "chapterId": chapter_id, "title": chapter_id, "order": len(chapters) + 1,
                "blocks": [{
                    "type": "paragraph", "inlines": [{"text": text_value}],
                    "claims": [{"claim_id": "c1", "text": text_value,
                                "claim_type": "fact", "evidence_ids": ["e1"]}],
                }],
            })

        document = DocumentComposer().build_document("report", {}, chapters, bundle)
        block_ids = [chapter["blocks"][0]["claims"][0]["claim_id"]
                     for chapter in document["chapters"]]

        self.assertEqual(block_ids, ["c1", "S2--c1"])
        self.assertEqual(set(document["claimIndex"]), {"c1", "S2--c1"})

    @patch.dict(
        "os.environ",
        {
            "BETTAFISH_PROVENANCE_ENDPOINT": "http://127.0.0.1/callback",
            "BETTAFISH_PROVENANCE_TOKEN": "secret-token",
        },
        clear=False,
    )
    @patch("common.provenance.runtime.build_opener")
    def test_runtime_publish_sends_token_and_retries_transient_failure(self, build_opener):
        response = Mock(status=200)
        response.read.return_value = b'{"success": true}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = build_opener.return_value
        opener.open.side_effect = [OSError("temporary"), response]

        published = publish_runtime_result(
            "run-1",
            "query",
            "topic",
            "report",
            ProvenanceBundle(agent="query_engine"),
        )

        self.assertTrue(published)
        self.assertEqual(opener.open.call_count, 2)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("X-provenance-token"), "secret-token")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 15)

    @patch.dict(
        "os.environ",
        {
            "BETTAFISH_PROVENANCE_ENDPOINT": "http://127.0.0.1/callback",
            "BETTAFISH_PROVENANCE_TOKEN": "secret-token",
        },
        clear=False,
    )
    @patch("common.provenance.runtime.build_opener")
    def test_runtime_publish_rejects_http_200_business_failure(self, build_opener):
        response = Mock(status=200)
        response.read.return_value = '{"success": false, "error": "容量已满"}'.encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        build_opener.return_value.open.return_value = response

        with self.assertRaisesRegex(RuntimeError, "容量已满"):
            publish_runtime_result(
                "run-1",
                "query",
                "topic",
                "report",
                ProvenanceBundle(agent="query_engine"),
            )

    def test_runtime_publish_bypasses_inherited_proxy_for_loopback(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"success": true}')

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/callback"
        try:
            with patch.dict(os.environ, {
                "BETTAFISH_PROVENANCE_ENDPOINT": endpoint,
                "BETTAFISH_PROVENANCE_TOKEN": "local-secret",
                "HTTP_PROXY": "http://127.0.0.1:1",
                "HTTPS_PROXY": "http://127.0.0.1:1",
                "NO_PROXY": "",
            }, clear=False):
                self.assertTrue(publish_runtime_result(
                    "run-local", "query", "topic", "report",
                    ProvenanceBundle(agent="query_engine"),
                ))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(len(received), 1)
        self.assertEqual(json.loads(received[0])["run_id"], "run-local")

    @patch.dict("os.environ", {
        "BETTAFISH_PROVENANCE_ENDPOINT": "https://example.com/callback",
    }, clear=False)
    def test_runtime_publish_rejects_non_loopback_endpoint(self):
        with self.assertRaisesRegex(RuntimeError, "回环地址"):
            publish_runtime_result(
                "run-remote", "query", "topic", "report",
                ProvenanceBundle(agent="query_engine"),
            )


if __name__ == "__main__":
    unittest.main()
