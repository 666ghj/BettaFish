import unittest

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from ReportEngine.agent import ReportAgent
from ReportEngine.core import TemplateSection
from ReportEngine.ir import ALLOWED_BLOCK_TYPES, IRValidator
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode


class ChapterSanitizationTestCase(unittest.TestCase):
    """Lightweight regression tests for the chapter sanitization helpers."""

    def setUp(self):
        self.node = ChapterGenerationNode(llm_client=None, validator=IRValidator(), storage=None)

    def test_table_cell_empty_blocks_repaired(self):
        chapter = {
            "blocks": [
                {
                    "type": "table",
                    "rows": [
                        {
                            "cells": [
                                {"blocks": []},
                                {"text": "同比变化", "blocks": None},
                            ]
                        }
                    ],
                }
            ]
        }
        self.node._sanitize_chapter_blocks(chapter)
        table_block = chapter["blocks"][0]
        cells = table_block["rows"][0]["cells"]
        self.assertEqual(len(cells), 2)
        for cell in cells:
            blocks = cell.get("blocks")
            self.assertIsInstance(blocks, list)
            self.assertGreater(len(blocks), 0)
            for block in blocks:
                self.assertEqual(block.get("type"), "paragraph")

    def test_table_rows_scalar_values_expanded(self):
        chapter = {"blocks": [{"type": "table", "rows": ["全国趋势"]}]}
        self.node._sanitize_chapter_blocks(chapter)
        table_block = chapter["blocks"][0]
        self.assertEqual(len(table_block["rows"]), 1)
        row = table_block["rows"][0]
        self.assertIn("cells", row)
        self.assertEqual(len(row["cells"]), 1)
        cell = row["cells"][0]
        self.assertIsInstance(cell.get("blocks"), list)
        self.assertEqual(
            cell["blocks"][0]["inlines"][0]["text"],
            "全国趋势",
        )

    def test_engine_quote_validation(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "insight",
                    "title": "Insight Agent",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "来自 Insight Engine 的观点"}],
                        }
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertTrue(valid, errors)
        self.assertFalse(errors)

    def test_engine_quote_rejects_disallowed_marks_and_blocks(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "media",
                    "title": "Media Agent",
                    "blocks": [
                        {"type": "math", "latex": "x=y"},
                        {
                            "type": "paragraph",
                            "inlines": [
                                {"text": "test", "marks": [{"type": "color"}]}
                            ],
                        },
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertFalse(valid)
        self.assertTrue(any("仅允许 paragraph" in err for err in errors))
        self.assertTrue(any("仅允许 bold/italic" in err for err in errors))

    def test_engine_quote_sanitization_strips_disallowed(self):
        chapter = {
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "query",
                    "blocks": [
                        {"type": "list", "items": [["非法"]]},
                        {
                            "type": "paragraph",
                            "inlines": [
                                {
                                    "text": "abc",
                                    "marks": [{"type": "bold"}, {"type": "highlight"}],
                                }
                            ],
                        },
                    ],
                }
            ]
        }
        node = self.node
        node._sanitize_chapter_blocks(chapter)
        eq_block = chapter["blocks"][0]
        self.assertEqual(eq_block["type"], "engineQuote")
        self.assertEqual(eq_block.get("title"), "Query Agent")
        inner_blocks = eq_block.get("blocks")
        self.assertTrue(all(b.get("type") == "paragraph" for b in inner_blocks))
        marks = inner_blocks[0]["inlines"][0].get("marks")
        self.assertEqual(marks, [])
        marks2 = inner_blocks[1]["inlines"][0].get("marks")
        self.assertEqual(marks2, [{"type": "bold"}])

    def test_engine_quote_title_must_match_engine(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "query",
                    "title": "Media Agent",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "错误标题"}],
                        }
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertFalse(valid)
        self.assertTrue(any("title 必须与engine一致" in err for err in errors))

    def test_chapter_payload_keeps_reports_data_and_full_ir_capabilities(self):
        section = TemplateSection(
            title="Test",
            slug="test",
            order=10,
            depth=1,
            raw_title="Test",
            chapter_id="S1",
        )
        reports = {
            "query_engine": "query report",
            "media_engine": "media report",
            "insight_engine": "insight report",
        }

        payload = self.node._build_payload(
            section,
            {
                "query": "topic",
                "reports": reports,
                "data_bundles": [{"kind": "dataset"}],
                "provenance_bundle": ProvenanceBundle(agent="report_engine"),
            },
        )

        self.assertEqual(payload["reports"], reports)
        self.assertEqual(payload["dataBundles"], [{"kind": "dataset"}])
        self.assertEqual(payload["constraints"]["allowedBlocks"], ALLOWED_BLOCK_TYPES)
        self.assertTrue(payload["constraints"]["styleHints"]["expectWidgets"])
        self.assertTrue(payload["provenancePolicy"]["reportsAreContextOnly"])

    def test_generic_chapter_payload_selects_evidence_using_global_query(self):
        section = TemplateSection(
            title="报告摘要",
            slug="summary",
            order=10,
            depth=1,
            raw_title="报告摘要",
            chapter_id="S1",
        )
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="goose", title="清华鹅腿阿姨走红")],
            evidence=[
                EvidenceRecord(
                    evidence_id="goose-evidence",
                    source_id="goose",
                    snippet="清华鹅腿阿姨在校园附近摆摊售卖鹅腿。",
                )
            ],
        )

        payload = self.node._build_payload(
            section,
            {
                "query": "清华鹅腿阿姨",
                "reports": {},
                "provenance_bundle": bundle,
            },
        )

        self.assertEqual(
            [item["evidence_id"] for item in payload["selectedEvidence"]["evidence"]],
            ["goose-evidence"],
        )

    def test_chapter_selection_does_not_mutate_global_evidence_metadata(self):
        section = TemplateSection(
            title="清华事件摘要",
            slug="summary",
            order=10,
            depth=1,
            raw_title="清华事件摘要",
            chapter_id="S1",
        )
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="goose", title="清华鹅腿阿姨走红")],
            evidence=[
                EvidenceRecord(
                    evidence_id="goose-evidence",
                    source_id="goose",
                    snippet="清华鹅腿阿姨在校园附近摆摊。",
                )
            ],
        )

        payload = self.node._build_payload(
            section,
            {"query": "清华鹅腿阿姨", "reports": {}, "provenance_bundle": bundle},
        )

        self.assertTrue(
            payload["selectedEvidence"]["evidence"][0]["meta"]["selection_reason"]
        )
        self.assertNotIn("selection_reason", bundle.evidence[0].meta)
        self.assertNotIn("selection_score", bundle.evidence[0].meta)

    def test_layout_metadata_cannot_bypass_claim_gate(self):
        sections = [
            TemplateSection(
                title="1.0 报告摘要",
                slug="section-1-0",
                order=10,
                depth=1,
                raw_title="1.0 报告摘要",
                chapter_id="S1",
            ),
            TemplateSection(
                title="2.0 风险评估",
                slug="section-2-0",
                order=20,
                depth=1,
                raw_title="2.0 风险评估",
                chapter_id="S2",
            ),
        ]
        layout = {
            "title": "未经引用的事实标题",
            "subtitle": "16元商品",
            "tagline": "调查已持续92天",
            "tocTitle": "带事实的目录标题",
            "tocPlan": [
                {
                    "chapterId": "S1",
                    "anchor": "unsafe-anchor",
                    "display": "未经引用的事实章节名",
                    "description": "未经引用的事实说明",
                    "allowSwot": True,
                },
                {
                    "chapterId": "S2",
                    "display": "另一条未经引用的事实",
                    "allowPest": False,
                },
            ],
            "hero": {"summary": "未经引用的摘要", "kpis": [{"value": "92"}]},
            "themeTokens": {"colors": {"primary": "#123456"}},
        }
        bundle = ProvenanceBundle(evidence=[])

        sanitized = ReportAgent._sanitize_layout_for_provenance(
            object(),
            layout,
            bundle,
            query="测试主题",
            sections=sections,
            template_name="社会公共热点事件分析报告模板",
        )

        self.assertEqual(sanitized["title"], "测试主题 - 舆情洞察报告")
        self.assertEqual(sanitized["subtitle"], "社会公共热点事件分析报告模板")
        self.assertEqual(sanitized["tagline"], "")
        self.assertEqual(sanitized["tocTitle"], "报告目录")
        self.assertEqual(
            sanitized["tocPlan"],
            [
                {
                    "chapterId": "S1",
                    "anchor": "section-1-0",
                    "display": "1.0 报告摘要",
                    "allowSwot": True,
                },
                {
                    "chapterId": "S2",
                    "anchor": "section-2-0",
                    "display": "2.0 风险评估",
                    "allowPest": False,
                },
            ],
        )
        self.assertEqual(sanitized["hero"]["summary"], "")
        self.assertEqual(sanitized["hero"]["kpis"], [])
        self.assertEqual(sanitized["themeTokens"], layout["themeTokens"])

    def test_unclaimed_generated_headings_are_removed_but_template_headings_remain(self):
        section = TemplateSection(
            title="1.0 报告摘要",
            slug="section-1-0",
            order=10,
            depth=1,
            raw_title="1.0 报告摘要",
            chapter_id="S1",
            outline=["1.1 事件概述"],
        )
        bundle = ProvenanceBundle()
        chapter = {
            "blocks": [
                {"type": "heading", "level": 2, "text": "1.1 事件概述"},
                {"type": "heading", "level": 3, "text": "调查已持续92天"},
            ]
        }

        self.node._sanitize_provenance_claims(chapter, bundle, section)

        self.assertEqual(
            [block["text"] for block in chapter["blocks"]],
            ["1.1 事件概述"],
        )


if __name__ == "__main__":
    unittest.main()
