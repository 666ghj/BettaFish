"""Table exports retain the same source and claim semantics as HTML."""

from copy import deepcopy
import json

import pytest

from common.provenance.citation_service import CitationService
from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from ReportEngine.core import ChapterStorage, DocumentComposer, TemplateSection
from ReportEngine.ir import IRValidator
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode
from ReportEngine.renderers import HTMLRenderer, MarkdownRenderer


FACT = "今天热度为 42。"
URL = "https://example.com/heat"


def paragraph(text, claim_type="metric"):
    return {
        "type": "paragraph", "inlines": [{"text": text}],
        "claims": [{"text": text, "claim_type": claim_type, "evidence_ids": ["e1"]}],
    }


def test_real_chapter_table_exports_citations_and_distinguishes_predictions(tmp_path):
    bundle = ProvenanceBundle(
        agent="query_engine", meta={"query": "今天热度"},
        sources=[SourceRecord(source_id="s1", source_type="web", url=URL)],
        evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", evidence_type="web", snippet=FACT)],
    )
    raw = {"chapterId": "S1", "title": "热度", "anchor": "heat", "order": 1,
           "blocks": [{"type": "table", "rows": [{"cells": [
        {"blocks": [paragraph(FACT)]},
        {"blocks": [paragraph(FACT, "prediction")]},
    ]}]}]}

    class FixedModel:
        def stream_invoke(self, *args, **kwargs):
            yield json.dumps(raw, ensure_ascii=False)

    storage = ChapterStorage(str(tmp_path / "chapters"))
    section = TemplateSection("热度", "heat", 1, 2, "热度", chapter_id="S1")
    node = ChapterGenerationNode(FixedModel(), IRValidator(), storage, error_log_dir=tmp_path / "errors")
    chapter = node.run(
        section, {"query": "今天热度", "provenance_bundle": bundle, "enforce_provenance": True},
        storage.start_session("table-export", {"query": "今天热度"}),
    )
    document = DocumentComposer().build_document("table-export", {}, [chapter], bundle)

    html = HTMLRenderer().render(deepcopy(document))
    markdown = MarkdownRenderer().render(deepcopy(document))

    assert len(document["claimIndex"]) == 2
    assert html.count(f'href="{URL}"') == 2
    assert '<span class="claim-kind-badge">预测</span>' in html
    assert markdown.count(f"[[1]]({URL}") == 2
    assert markdown.count("**[预测]**") == 1
    assert f"| {FACT} [[1]]" in markdown
    assert f"| **[预测]** {FACT} [[1]]" in markdown


@pytest.mark.parametrize("claim_type,label", [("prediction", "预测"), ("recommendation", "建议")])
def test_nested_table_list_preserves_labels_and_escapes_citation_metadata(claim_type, label):
    bundle = ProvenanceBundle(
        sources=[SourceRecord(source_id="s1", url=URL + "?tag=A|B", title="来源A|B\n详情")],
        evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", snippet=FACT)],
    )
    renderer = MarkdownRenderer()
    renderer.citation_service = CitationService(bundle)
    cell = {"blocks": [{"type": "list", "items": [[paragraph("A|B\n后续建议", claim_type)]]}]}

    rendered = renderer._render_cell_content(cell)

    assert rendered.count(f"**[{label}]**") == 1
    assert rendered.count("[[1]]") == 1
    assert "A\\|B 后续建议" in rendered
    assert URL + "?tag=A%7CB" in rendered
    assert '"来源A\\|B 详情"' in rendered
    assert "\n" not in rendered


def test_internal_lineage_in_table_is_visible_without_breaking_columns():
    bundle = ProvenanceBundle(
        sources=[SourceRecord(source_id="s1", source_type="database", retrieved_time="2026-10-18T12:00:00Z")],
        evidence=[EvidenceRecord(
            evidence_id="e1", source_id="s1", evidence_type="db_row", snippet=FACT,
            scope={"table": "posts", "row_ids": ["42"], "filters": {"topic": "A|B"},
                   "query_time": "2026-10-18T12:00:00Z", "time_window": {"kind": "unbounded"}},
        )],
    )
    renderer = MarkdownRenderer()
    renderer.citation_service = CitationService(bundle)

    rendered = renderer._render_cell_content({"blocks": [paragraph(FACT)]})

    assert "内部数据" in rendered
    assert "表 posts" in rendered and "行 42" in rendered
    assert "A\\|B" in rendered
    assert "2026-10-18T12:00:00Z" in rendered


def test_table_heading_retains_its_own_citation():
    renderer = MarkdownRenderer()
    renderer.citation_service = CitationService(ProvenanceBundle(
        sources=[SourceRecord(source_id="s1", url=URL)],
        evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", snippet=FACT)],
    ))
    heading = {"type": "heading", "text": FACT, "citation_refs": ["e1"]}

    rendered = renderer._render_cell_content({"blocks": [heading]})

    assert FACT in rendered
    assert f"[[1]]({URL}" in rendered


def test_table_paragraph_keeps_existing_unsupported_placeholder_filter():
    renderer = MarkdownRenderer()
    cell = {"blocks": [{"type": "paragraph", "inlines": [{"text": "本段未检索到可追溯证据。"}],
                        "support_status": "unsupported", "claims": [], "citation_refs": []}]}

    assert renderer._render_cell_content(cell) == ""
