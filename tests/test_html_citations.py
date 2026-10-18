import unittest

from common.provenance.citation_service import CitationService
from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from ReportEngine.core.stitcher import DocumentComposer
from ReportEngine.renderers.html_renderer import HTMLRenderer
from ReportEngine.renderers.markdown_renderer import MarkdownRenderer


class HtmlCitationTests(unittest.TestCase):
    def test_template_headings_survive_both_provenance_gates(self):
        from ReportEngine.core import TemplateSection
        from ReportEngine.ir import IRValidator
        from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode

        section = TemplateSection(
            title="1.0 报告摘要", slug="summary", order=10, depth=1,
            raw_title="1.0 报告摘要", chapter_id="S1", outline=["1.1 事件概述"],
        )
        chapter = {
            "chapterId": "S1", "title": section.title,
            "blocks": [
                {"type": "heading", "level": 2, "text": "1.1 事件概述",
                 "subtitle": "调查已持续92天"},
                {"type": "heading", "level": 3, "text": "调查已持续92天"},
            ],
        }
        bundle = ProvenanceBundle()
        node = ChapterGenerationNode(llm_client=None, validator=IRValidator(), storage=None)
        node._sanitize_provenance_claims(chapter, bundle, section)
        metadata = {"templateOverview": {"chapters": [section.to_dict()]}}

        document = DocumentComposer().build_document("heading-report", metadata, [chapter], bundle)
        headings = document["chapters"][0]["blocks"]

        self.assertIn("1.1 事件概述", [block.get("text") for block in headings])
        self.assertTrue(all("subtitle" not in block for block in headings))
        html = HTMLRenderer().render(document)
        markdown = MarkdownRenderer().render(document)
        self.assertIn("1.1 事件概述", html)
        self.assertIn("1.1 事件概述", markdown)
        self.assertNotIn("调查已持续92天", html)
        self.assertNotIn("调查已持续92天", markdown)

    def test_document_head_uses_valid_mathjax_config_and_inline_favicon(self):
        html = HTMLRenderer().render(
            {
                "metadata": {"title": "Renderer smoke test"},
                "chapters": [],
                "provenanceBundle": {},
            }
        )

        self.assertIn('<link rel="icon" href="data:," />', html)
        tex_config = html.split("tex: {", 1)[1].split("options: {", 1)[0]
        options_config = html.split("options: {", 1)[1].split("}", 1)[0]
        self.assertIn("processEscapes: true", tex_config)
        self.assertNotIn("processEscapes", options_config)

    def test_unsupported_placeholder_paragraph_is_not_rendered(self):
        renderer = HTMLRenderer()
        html = renderer._render_paragraph(
            {
                "type": "paragraph",
                "inlines": [{"text": "本段未检索到可追溯证据。"}],
                "claims": [],
                "citation_refs": [],
                "support_status": "unsupported",
            }
        )

        self.assertEqual(html, "")

    def test_paragraph_renders_clickable_hover_citation(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="s1",
                    title="Official release",
                    url="https://example.com/original",
                    platform="example.com",
                    publish_time="2026-09-01",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="e1",
                    source_id="s1",
                    snippet="The reported value was 42.",
                    meta={"selection_reason": "直接匹配章节主题"},
                )
            ],
        )
        renderer = HTMLRenderer()
        renderer.citation_service = CitationService(bundle)
        html = renderer._render_paragraph(
            {
                "type": "paragraph",
                "inlines": [{"text": "The value was 42."}],
                "claims": [
                    {
                        "claim_id": "c1",
                        "text": "The value was 42.",
                        "claim_type": "metric",
                        "evidence_ids": ["e1"],
                        "support_status": "supported",
                    }
                ],
                "citation_refs": ["e1"],
                "support_status": "supported",
            }
        )
        self.assertIn('class="citation-ref"', html)
        self.assertIn('href="https://example.com/original"', html)
        self.assertIn("Official release", html)
        self.assertIn("The reported value was 42.", html)
        self.assertIn("直接匹配章节主题", html)

    def test_claim_scoped_reason_overrides_global_evidence_reason(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="s1",
                    title="Shared source",
                    url="https://example.com/shared",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="e1",
                    source_id="s1",
                    snippet="鹅腿阿姨在清华大学附近摆摊。",
                    meta={"selection_reason": "旧章节理由"},
                )
            ],
        )
        renderer = HTMLRenderer()
        renderer.citation_service = CitationService(bundle)

        html = renderer._render_paragraph(
            {
                "type": "paragraph",
                "inlines": [{"text": "鹅腿阿姨在清华大学附近摆摊。"}],
                "claims": [
                    {
                        "text": "鹅腿阿姨在清华大学附近摆摊。",
                        "claim_type": "fact",
                        "evidence_ids": ["e1"],
                        "support_status": "supported",
                        "meta": {
                            "evidence_selection_reasons": {"e1": "当前章节理由"}
                        },
                    }
                ],
                "citation_refs": ["e1"],
                "support_status": "supported",
            }
        )

        self.assertIn("引用理由：当前章节理由", html)
        self.assertNotIn("旧章节理由", html)

    def test_composed_document_carries_a_claim_through_to_clickable_html(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="official-source",
                    source_type="news",
                    title="Official announcement",
                    url="https://example.com/announcement",
                    platform="example.com",
                    publish_time="2026-09-01",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="official-evidence",
                    source_id="official-source",
                    agent="query_engine",
                    evidence_type="news",
                    snippet="The official announcement reports 42 completed cases.",
                    meta={"selection_reason": "官方公告直接给出该指标"},
                )
            ],
        )
        chapter = {
            "chapterId": "S1",
            "title": "Findings",
            "order": 10,
            "blocks": [
                {"type": "heading", "level": 2, "text": "Findings", "anchor": "findings"},
                {
                    "type": "paragraph",
                    "inlines": [{"text": "The official announcement reports 42 completed cases."}],
                    "claims": [
                        {
                            "claim_id": "completed-cases",
                            "text": "The official announcement reports 42 completed cases.",
                            "claim_type": "metric",
                            "evidence_ids": ["official-evidence"],
                        }
                    ],
                },
            ],
        }

        document = DocumentComposer().build_document("report-1", {}, [chapter], bundle)
        html = HTMLRenderer().render(document)

        self.assertIn("official-evidence", document["provenanceIndex"]["evidence"])
        self.assertIn("completed-cases", document["claimIndex"])
        self.assertTrue(document["provenanceEnforced"])
        self.assertIn('href="https://example.com/announcement"', html)
        self.assertIn('class="citation-ref"', html)
        self.assertIn("引用理由：官方公告直接给出该指标", html)

    def test_composer_drops_root_provenance_and_rejects_weak_inference(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="source-1",
                    source_type="web",
                    url="https://example.com/source-1",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="evidence-1",
                    source_id="source-1",
                    evidence_type="web",
                    snippet="原料标注需要保持真实。",
                )
            ],
        )
        chapter = {
            "chapterId": "S1",
            "title": "结论",
            "order": 10,
            "claims": [
                {
                    "claim_id": "root-only",
                    "text": "这条主张不在可渲染块中。",
                    "claim_type": "fact",
                    "evidence_ids": ["evidence-1"],
                }
            ],
            "citation_refs": ["evidence-1"],
            "support_status": "supported",
            "blocks": [
                {
                    "type": "heading",
                    "level": 2,
                    "text": "结论",
                    "anchor": "conclusion",
                },
                {
                    "type": "paragraph",
                    "inlines": [{"text": "实现机会需要完成原料真实标注。"}],
                    "claims": [
                        {
                            "claim_id": "weak-inference",
                            "text": "实现机会需要完成原料真实标注。",
                            "claim_type": "inference",
                            "evidence_ids": ["evidence-1"],
                        }
                    ],
                },
            ],
        }

        document = DocumentComposer().build_document("report-1", {}, [chapter], bundle)
        composed_chapter = document["chapters"][0]

        self.assertNotIn("claims", composed_chapter)
        self.assertNotIn("citation_refs", composed_chapter)
        self.assertNotIn("support_status", composed_chapter)
        self.assertEqual([block["type"] for block in composed_chapter["blocks"]], ["heading"])
        self.assertEqual(document["claimIndex"], {})

    def test_internal_citation_renders_lineage_without_self_link(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(
                source_id="db-source", source_type="database", title="内部帖子库",
                retrieved_time="2026-09-10T09:00:00Z",
                locator={"table": "posts"},
            )],
            evidence=[EvidenceRecord(
                evidence_id="db-evidence", source_id="db-source",
                agent="insight_engine", evidence_type="db_row", snippet="样本值为 42",
                scope={
                    "query_time": "2026-09-10T09:00:00Z", "table": "posts",
                    "filters": {"topic": "测试"}, "time_window": {"kind": "unbounded"},
                    "sample_size": 1, "aggregation_method": "record_lookup",
                    "row_ids": ["row-42"], "primary_key": "row-42",
                },
            )],
        )
        block = {
            "type": "paragraph", "inlines": [{"text": "样本值为 42"}],
            "claims": [{"claim_id": "c1", "text": "样本值为 42", "claim_type": "metric",
                        "evidence_ids": ["db-evidence"], "support_status": "supported"}],
            "citation_refs": ["db-evidence"], "support_status": "supported",
        }
        renderer = HTMLRenderer()
        renderer.citation_service = CitationService(bundle)
        html = renderer._render_paragraph(block)

        self.assertIn('class="citation-internal"', html)
        self.assertNotIn('href="#citation-', html)
        self.assertIn("表 posts", html)
        self.assertIn("row-42", html)
        self.assertIn("检索于 2026-09-10T09:00:00Z", html)

        markdown = MarkdownRenderer().render({
            "metadata": {"title": "测试"},
            "chapters": [{"title": "章节", "blocks": [block]}],
            "provenanceBundle": bundle.to_dict(),
        })
        self.assertIn("内部数据：表 posts", markdown)
        self.assertIn("row-42", markdown)

    def test_markdown_renders_external_citation_and_prediction_label(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s1", title="来源", url="https://example.com")],
            evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", snippet="依据")],
        )
        markdown = MarkdownRenderer().render({
            "metadata": {"title": "测试"},
            "chapters": [{"title": "章节", "blocks": [{
                "type": "paragraph", "inlines": [{"text": "未来可能增长"}],
                "claims": [{"claim_id": "p1", "text": "未来可能增长",
                            "claim_type": "prediction", "evidence_ids": ["e1"],
                            "support_status": "predicted"}],
                "citation_refs": ["e1"], "support_status": "predicted",
            }]}],
            "provenanceBundle": bundle.to_dict(),
        })

        self.assertIn("**[预测]**", markdown)
        self.assertIn('[[1]](https://example.com "来源")', markdown)

    def test_rich_block_renders_parent_citation_in_html_and_markdown(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s1", title="来源", url="https://example.com")],
            evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", snippet="依据")],
        )
        block = {
            "type": "callout",
            "title": "风险提示",
            "blocks": [{"type": "paragraph", "inlines": [{"text": "容器内事实"}]}],
            "claims": [{
                "claim_id": "c1",
                "text": "容器内事实",
                "claim_type": "fact",
                "evidence_ids": ["e1"],
            }],
            "citation_refs": ["e1"],
            "support_status": "supported",
        }
        document = {
            "metadata": {"title": "测试"},
            "chapters": [{"title": "章节", "blocks": [block]}],
            "provenanceBundle": bundle.to_dict(),
        }

        html = HTMLRenderer().render(document)
        markdown = MarkdownRenderer().render(document)

        self.assertIn('class="block-provenance support-supported"', html)
        self.assertIn('href="https://example.com"', html)
        self.assertIn('[[1]](https://example.com "来源")', markdown)


if __name__ == "__main__":
    unittest.main()
