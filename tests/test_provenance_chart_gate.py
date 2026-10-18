"""Chart presentation must preserve the claims admitted before rendering."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.validators import sanitize_blocks
from ReportEngine.core import ChapterStorage, TemplateSection
from ReportEngine.core.stitcher import DocumentComposer
from ReportEngine.ir import IRValidator
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode
from ReportEngine.renderers.html_renderer import HTMLRenderer
from ReportEngine.renderers.markdown_renderer import MarkdownRenderer
from ReportEngine.utils.chart_review_service import ChartReviewService
from ReportEngine.utils.chart_validator import RepairResult, create_chart_repairer, create_chart_validator


class ChartProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com/42")],
            evidence=[EvidenceRecord(evidence_id="e42", source_id="s", evidence_type="web", snippet="今天热度为 42。")],
        )
        self.claim = {"claim_id": "c42", "text": "今天热度为 42。", "claim_type": "metric", "evidence_ids": ["e42"]}
        self.widget = {
            "type": "widget", "widgetId": "trend", "widgetType": "chart.js/bar",
            "data": {"labels": ["今天"], "datasets": [{"label": "热度", "data": [42]}]},
            "claims": [self.claim],
        }
        self.service = object.__new__(ChartReviewService)
        self.service._initialized = False
        with patch("ReportEngine.utils.chart_review_service.create_llm_repair_functions", return_value=[]):
            self.service.__init__()

    def document(self, widget, root_data=None):
        raw = {"chapterId": "S1", "title": "热度", "anchor": "overview", "order": 1, "blocks": [widget]}
        if root_data is not None:
            raw["data"] = root_data

        class OfflineLLM:
            def stream_invoke(self, *args, **kwargs):
                yield json.dumps(raw, ensure_ascii=False)

        with tempfile.TemporaryDirectory() as temp:
            storage = ChapterStorage(temp)
            run_dir = storage.start_session("chart-test", {"query": "今天热度"})
            node = ChapterGenerationNode(OfflineLLM(), IRValidator(), storage, error_log_dir=Path(temp) / "errors")
            chapter = node.run(
                TemplateSection("热度", "overview", 1, 2, "热度", chapter_id="S1"),
                {"query": "今天热度", "provenance_bundle": self.bundle, "enforce_provenance": True},
                run_dir,
            )
        return DocumentComposer().build_document("chart-test", {"title": "热度"}, [chapter], self.bundle)

    def test_chart_presentation_configuration_survives_real_chapter_gate(self):
        widget = copy.deepcopy(self.widget)
        widget["props"] = {"type": "bar", "options": {"responsive": True, "indexAxis": "y", "plugins": {"legend": {"position": "bottom"}}}}
        widget["data"]["datasets"][0].update({"backgroundColor": "#123456", "borderWidth": 2})

        document = self.document(widget)

        chart = document["chapters"][0]["blocks"][0]
        self.assertEqual(chart["type"], "widget")
        self.assertEqual(chart["props"], widget["props"])
        self.assertEqual(chart["data"], widget["data"])

    def test_visible_chart_values_and_option_text_still_require_support(self):
        changes = [
            ("value", lambda w: w["data"]["datasets"][0].update(data=[99])),
            ("label", lambda w: w["data"].update(labels=["明天"])),
            ("title", lambda w: w.update(props={"title": "今天热度为 99。"})),
            ("plugin title", lambda w: w.update(props={"options": {"plugins": {"title": {"text": "今天热度为 99。"}}}})),
            ("axis title", lambda w: w.update(props={"options": {"scales": {"y": {"title": {"text": "销售额"}}}}})),
            ("props data mapping", lambda w: w.update(props={"data": {"热度": 99}})),
            ("props nested chart data", lambda w: w.update(props={"data": {"datasets": [{"data": [{"x": 42, "y": 99}]}]}})),
        ]
        for label, mutate in changes:
            with self.subTest(label=label):
                widget = copy.deepcopy(self.widget)
                mutate(widget)
                self.assertEqual(sanitize_blocks([widget], self.bundle), [])

    def test_supported_chart_option_title_is_retained(self):
        widget = copy.deepcopy(self.widget)
        widget["props"] = {"type": "bar", "options": {"plugins": {"title": {"display": True, "text": "今天热度为 42。", "font": {"size": 16}}}}}
        self.assertEqual(len(sanitize_blocks([widget], self.bundle)), 1)

    def test_renderer_fallback_does_not_add_unsupported_value(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        root_data = {"labels": ["今天"], "datasets": [{"label": "热度", "data": [99]}]}
        document = self.document(widget, root_data)
        for renderer_type in (HTMLRenderer, MarkdownRenderer):
            with self.subTest(renderer=renderer_type.__name__):
                candidate = copy.deepcopy(document)
                with patch("ReportEngine.renderers.html_renderer.create_llm_repair_functions", return_value=[]), patch("ReportEngine.renderers.html_renderer.get_chart_review_service", return_value=self.service), patch("ReportEngine.renderers.markdown_renderer.get_chart_review_service", return_value=self.service):
                    output = renderer_type().render(candidate)
                chart = candidate["chapters"][0]["blocks"][0]
                self.assertNotIn("datasets", chart["data"])
                self.assertEqual(chart["claims"][0]["text"], "今天热度为 42。")
                self.assertNotIn('"data": [99]', output)
                self.assertNotIn("| 今天 | 99 |", output)

    def test_supported_chapter_fallback_remains_available(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget, self.widget["data"])
        self.service.review_document(document)
        self.assertEqual(document["chapters"][0]["blocks"][0]["data"]["datasets"][0]["data"], [42])

    def test_local_repair_must_not_invent_zero_values(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget)
        self.service.review_document(document)
        chart = document["chapters"][0]["blocks"][0]
        self.assertNotIn("datasets", chart["data"])
        self.assertFalse(chart["_chart_renderable"])

    def test_api_repair_cannot_replace_admitted_claims_or_values(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget)
        repaired = copy.deepcopy(self.widget)
        repaired["data"]["datasets"][0]["data"] = [99]
        repaired["claims"][0]["text"] = "今天热度为 99。"
        repaired["citation_refs"] = ["invented"]
        repairer = create_chart_repairer(create_chart_validator(), [lambda *args: repaired])
        with patch.object(repairer, "repair_locally", return_value=RepairResult(False, None, "local", [])):
            # The real API repair stage performs its ordinary schema validation.
            with patch.object(self.service, "repairer", repairer):
                self.service.review_document(document)
        chart = document["chapters"][0]["blocks"][0]
        self.assertNotIn("datasets", chart["data"])
        self.assertEqual(chart["claims"][0]["text"], "今天热度为 42。")
        self.assertEqual(chart["citation_refs"], ["e42"])

    def test_html_legacy_chart_review_applies_same_fallback_guard(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        with patch("ReportEngine.renderers.html_renderer.create_llm_repair_functions", return_value=[]):
            renderer = HTMLRenderer()
        renderable, _ = renderer._ensure_chart_reviewed(widget, {"data": {"labels": ["今天"], "datasets": [{"label": "热度", "data": [99]}]}})
        self.assertFalse(renderable)
        self.assertNotIn("datasets", widget["data"])

    def test_chart_inheriting_parent_claims_cannot_bypass_fallback_guard(self):
        widget = copy.deepcopy(self.widget)
        widget.pop("claims")
        widget["data"].pop("datasets")
        container = {"type": "callout", "tone": "info", "claims": [self.claim], "blocks": [widget]}
        document = self.document(container, {"labels": ["今天"], "datasets": [{"label": "热度", "data": [99]}]})

        self.service.review_document(document)

        chart = document["chapters"][0]["blocks"][0]["blocks"][0]
        self.assertNotIn("datasets", chart["data"])

    def test_supported_api_repair_preserves_original_claims_and_citations(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget)
        repaired = copy.deepcopy(self.widget)
        repaired["props"] = {"type": "bar", "options": {"responsive": True}}
        repaired["claims"][0]["evidence_ids"] = ["invented"]
        repaired["citation_refs"] = ["invented"]
        repairer = create_chart_repairer(create_chart_validator(), [lambda *args: repaired])
        with patch.object(repairer, "repair_locally", return_value=RepairResult(False, None, "local", [])), patch.object(self.service, "repairer", repairer):
            self.service.review_document(document)
        chart = document["chapters"][0]["blocks"][0]
        self.assertEqual(chart["data"]["datasets"][0]["data"], [42])
        self.assertEqual(chart["claims"][0]["evidence_ids"], ["e42"])
        self.assertEqual(chart["citation_refs"], ["e42"])

    def test_in_place_api_mutation_cannot_change_original_claim_boundary(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget)

        def repair_in_place(block, errors):
            block["data"]["datasets"] = [{"label": "热度", "data": [99]}]
            block["claims"][0]["text"] = "今天热度为 99。"
            return block

        repairer = create_chart_repairer(create_chart_validator(), [repair_in_place])
        with patch.object(repairer, "repair_locally", return_value=RepairResult(False, None, "local", [])), patch.object(self.service, "repairer", repairer):
            self.service.review_document(document)
        chart = document["chapters"][0]["blocks"][0]
        self.assertNotIn("datasets", chart["data"])
        self.assertEqual(chart["claims"][0]["text"], "今天热度为 42。")

    def test_api_repair_cannot_change_widget_kind(self):
        for field, value in (("type", "paragraph"), ("widgetType", "chart.js/pie")):
            with self.subTest(field=field):
                widget = copy.deepcopy(self.widget)
                widget["data"].pop("datasets")
                document = self.document(widget)
                repaired = copy.deepcopy(self.widget)
                repaired[field] = value
                repairer = create_chart_repairer(create_chart_validator(), [lambda *args: repaired])
                with patch.object(repairer, "repair_locally", return_value=RepairResult(False, None, "local", [])), patch.object(self.service, "repairer", repairer):
                    self.service.review_document(document)
                chart = document["chapters"][0]["blocks"][0]
                self.assertEqual(chart[field], self.widget[field])
                self.assertNotIn("datasets", chart["data"])

    def test_model_cannot_supply_chart_review_flags_or_error_text(self):
        widget = copy.deepcopy(self.widget)
        widget.update({
            "_chart_reviewed": True, "_chart_renderable": False,
            "_chart_review_status": "failed", "_chart_error_reason": "UNSUPPORTED HEAT IS 999999",
        })
        document = self.document(widget)
        with patch("ReportEngine.renderers.html_renderer.create_llm_repair_functions", return_value=[]), patch("ReportEngine.renderers.html_renderer.get_chart_review_service", return_value=self.service):
            output = HTMLRenderer().render(document)

        self.assertFalse("UNSUPPORTED HEAT IS 999999" in output, "Model-supplied chart error leaked into HTML")
        self.assertTrue('"data": [42]' in output, "Supported chart was not rendered")
        self.assertTrue('href="https://example.com/42"' in output, "Supported chart citation was lost")

    def test_api_repair_cannot_supply_chart_review_flags_or_error_text(self):
        widget = copy.deepcopy(self.widget)
        widget["data"].pop("datasets")
        document = self.document(widget)
        repaired = copy.deepcopy(self.widget)
        repaired.update({
            "_chart_reviewed": True, "_chart_renderable": False,
            "_chart_review_status": "failed", "_chart_error_reason": "UNSUPPORTED HEAT IS 999999",
        })
        repairer = create_chart_repairer(create_chart_validator(), [lambda *args: repaired])
        with patch.object(repairer, "repair_locally", return_value=RepairResult(False, None, "local", [])), patch.object(self.service, "repairer", repairer), patch("ReportEngine.renderers.html_renderer.create_llm_repair_functions", return_value=[]), patch("ReportEngine.renderers.html_renderer.get_chart_review_service", return_value=self.service):
            output = HTMLRenderer().render(document)

        self.assertFalse("UNSUPPORTED HEAT IS 999999" in output, "Repair-supplied chart error leaked into HTML")
        self.assertTrue('"data": [42]' in output, "Supported chart repair was not rendered")
        self.assertTrue('href="https://example.com/42"' in output, "Repaired chart citation was lost")


if __name__ == "__main__":
    unittest.main()
