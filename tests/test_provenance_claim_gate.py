import unittest

from common.provenance.models import ClaimRecord, EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.validators import (
    filter_valid_evidence,
    gate_claim,
    sanitize_blocks,
    sanitize_claim_block,
)


class ClaimGateTests(unittest.TestCase):
    def test_image_metadata_is_retained_for_audit_but_cannot_support_claims(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="image-source",
                    source_type="social",
                    url="https://example.com/image",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="image-evidence",
                    source_id="image-source",
                    evidence_type="image_metadata",
                    snippet="image-001.jpg",
                )
            ],
            claims=[
                ClaimRecord(
                    claim_id="image-claim",
                    text="清华鹅腿阿姨",
                    claim_type="fact",
                    evidence_ids=["image-evidence"],
                )
            ],
        )

        filtered = filter_valid_evidence(bundle)

        self.assertEqual([item.evidence_id for item in filtered.evidence], ["image-evidence"])
        self.assertEqual(filtered.claims, [])

    def test_fact_and_metric_require_evidence(self):
        fact = gate_claim(ClaimRecord(claim_id="f", text="fact", claim_type="fact"), {"e1"})
        metric = gate_claim(ClaimRecord(claim_id="m", text="42%", claim_type="metric"), {"e1"})
        self.assertFalse(fact.allowed)
        self.assertFalse(metric.allowed)

    def test_inference_requires_two_and_prediction_is_marked(self):
        weak = gate_claim(
            ClaimRecord(claim_id="i", text="inference", claim_type="inference", evidence_ids=["e1"]),
            {"e1", "e2"},
        )
        strong = gate_claim(
            ClaimRecord(claim_id="i2", text="inference", claim_type="inference", evidence_ids=["e1", "e2"]),
            {"e1", "e2"},
        )
        prediction = gate_claim(ClaimRecord(claim_id="p", text="future", claim_type="prediction"), set())
        self.assertFalse(weak.allowed)
        self.assertEqual(weak.claim.status, "weak")
        self.assertEqual(strong.claim.status, "supported")
        self.assertEqual(prediction.claim.status, "predicted")

    def test_removes_only_unsupported_fact_from_mixed_block(self):
        block = {
            "type": "paragraph",
            "inlines": [{"text": "Supported fact. Unsupported fact."}],
            "claims": [
                {"claim_id": "ok", "text": "Supported fact.", "claim_type": "fact", "evidence_ids": ["e1"]},
                {"claim_id": "bad", "text": "Unsupported fact.", "claim_type": "fact", "evidence_ids": []},
            ],
        }
        sanitized = sanitize_claim_block(block, {"e1"})
        text = "".join(item["text"] for item in sanitized["inlines"])
        self.assertIn("Supported fact.", text)
        self.assertNotIn("Unsupported fact.", text)
        self.assertEqual(sanitized["citation_refs"], ["e1"])

    def test_empty_block_is_omitted_after_all_claims_removed(self):
        block = {
            "type": "paragraph",
            "inlines": [{"text": "Unsupported fact."}],
            "claims": [{"claim_id": "bad", "text": "Unsupported fact.", "claim_type": "fact"}],
        }
        sanitized = sanitize_claim_block(block, set())
        self.assertEqual(sanitized, {})

    def test_insight_evidence_without_internal_lineage_is_filtered(self):
        bundle = ProvenanceBundle(
            agent="insight_engine",
            sources=[SourceRecord(source_id="db", source_type="database", locator={"table": "posts"})],
            evidence=[
                EvidenceRecord(
                    evidence_id="bad-db-row",
                    source_id="db",
                    agent="insight_engine",
                    evidence_type="db_row",
                    snippet="42 orders",
                    scope={"table": "posts", "sample_size": 1},
                )
            ],
        )
        self.assertEqual(filter_valid_evidence(bundle).evidence, [])

    def test_rich_blocks_preserve_structure_and_are_idempotent(self):
        claims = [
            {
                "claim_id": "rich-claim",
                "text": "今天热度为 42。",
                "claim_type": "metric",
                "evidence_ids": ["e1"],
            }
        ]
        blocks = [
            {
                "type": "widget",
                "widgetId": "trend",
                "widgetType": "chart.js/line",
                "data": {"labels": ["今天"], "datasets": [{"label": "热度", "data": [42]}]},
                "claims": claims,
            },
            {
                "type": "table",
                "caption": "热度",
                "rows": [
                    {
                        "cells": [
                            {
                                "blocks": [
                                    {
                                        "type": "paragraph",
                                        "inlines": [{"text": "42"}],
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "claims": claims,
            },
            {
                "type": "list",
                "listType": "bullet",
                "items": [
                    [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "热度为 42。"}],
                        }
                    ]
                ],
                "claims": claims,
            },
        ]
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s1", source_type="web", url="https://example.com")],
            evidence=[
                EvidenceRecord(
                    evidence_id="e1",
                    source_id="s1",
                    evidence_type="web",
                    snippet="今天热度为 42。",
                )
            ],
        )

        sanitized = sanitize_blocks(blocks, bundle)

        self.assertEqual([item["type"] for item in sanitized], ["widget", "table", "list"])
        self.assertEqual(sanitized[0]["data"], blocks[0]["data"])
        self.assertEqual(sanitized[1]["rows"], blocks[1]["rows"])
        self.assertEqual(sanitized[2]["items"], blocks[2]["items"])
        self.assertEqual(sanitize_blocks(sanitized, bundle), sanitized)

    def test_rich_block_is_rejected_when_any_claim_is_unsupported(self):
        block = {
            "type": "widget",
            "widgetId": "trend",
            "widgetType": "chart.js/line",
            "data": {"labels": ["今天"], "datasets": [{"data": [42]}]},
            "claims": [
                {
                    "claim_id": "ok",
                    "text": "热度为 42。",
                    "claim_type": "metric",
                    "evidence_ids": ["e1"],
                },
                {
                    "claim_id": "bad",
                    "text": "热度为 99。",
                    "claim_type": "metric",
                    "evidence_ids": [],
                },
            ],
        }

        self.assertEqual(sanitize_blocks([block], {"e1"}), [])

    def test_numeric_gate_preserves_sign_and_normalizes_decimal_values(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com")],
            evidence=[EvidenceRecord(evidence_id="e", source_id="s", evidence_type="web",
                                     snippet="该指标同比为 -7.00%。")],
        )

        wrong_sign = gate_claim(
            ClaimRecord(text="该指标同比为 +7%。", claim_type="metric", evidence_ids=["e"]),
            bundle,
        )
        equivalent = gate_claim(
            ClaimRecord(text="该指标同比为 -7%。", claim_type="metric", evidence_ids=["e"]),
            bundle,
        )

        self.assertFalse(wrong_sign.allowed)
        self.assertTrue(equivalent.allowed)

    def test_same_number_from_unrelated_subject_cannot_support_claim(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="s",
                    source_type="web",
                    url="https://example.com/company",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="e",
                    source_id="s",
                    evidence_type="web",
                    snippet="该公司有 100 名员工。",
                )
            ],
        )

        unrelated = gate_claim(
            ClaimRecord(
                text="鹅腿摊位卖出 100 个鹅腿。",
                claim_type="metric",
                evidence_ids=["e"],
            ),
            bundle,
        )

        self.assertFalse(unrelated.allowed)

    def test_shared_subject_alone_cannot_support_a_different_fact(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="s",
                    source_type="web",
                    url="https://example.com/goose-leg-auntie",
                )
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="e",
                    source_id="s",
                    evidence_type="web",
                    snippet="鹅腿阿姨在清华大学附近摆摊售卖鹅腿。",
                )
            ],
        )

        unsupported = gate_claim(
            ClaimRecord(
                text="鹅腿阿姨来自江西。",
                claim_type="fact",
                evidence_ids=["e"],
            ),
            bundle,
        )
        supported = gate_claim(
            ClaimRecord(
                text="鹅腿阿姨在清华大学附近摆摊。",
                claim_type="fact",
                evidence_ids=["e"],
            ),
            bundle,
        )

        self.assertFalse(unsupported.allowed)
        self.assertTrue(supported.allowed)

    def test_same_number_with_a_different_unit_cannot_support_metric(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com")],
            evidence=[
                EvidenceRecord(
                    evidence_id="e",
                    source_id="s",
                    evidence_type="web",
                    snippet="鹅腿售价为 15 元。",
                )
            ],
        )

        result = gate_claim(
            ClaimRecord(
                text="鹅腿售价为 15 万元。",
                claim_type="metric",
                evidence_ids=["e"],
            ),
            bundle,
        )

        self.assertFalse(result.allowed)

    def test_every_displayed_evidence_must_support_the_fact_independently(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(source_id="good-source", source_type="web", url="https://example.com/good"),
                SourceRecord(source_id="bad-source", source_type="web", url="https://example.com/bad"),
            ],
            evidence=[
                EvidenceRecord(
                    evidence_id="good",
                    source_id="good-source",
                    evidence_type="web",
                    snippet="鹅腿售价为 15 元。",
                ),
                EvidenceRecord(
                    evidence_id="bad",
                    source_id="bad-source",
                    evidence_type="web",
                    snippet="鹅腿摊位已经经营 15 年。",
                ),
            ],
        )

        result = gate_claim(
            ClaimRecord(
                text="鹅腿售价为 15 元。",
                claim_type="metric",
                evidence_ids=["good", "bad"],
            ),
            bundle,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.claim.evidence_ids, ["good"])

    def test_parent_claim_does_not_let_unrelated_list_item_hitchhike(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com")],
            evidence=[
                EvidenceRecord(
                    evidence_id="e",
                    source_id="s",
                    evidence_type="web",
                    snippet="鹅腿售价为 15 元。",
                )
            ],
        )
        block = {
            "type": "list",
            "items": [
                [{"type": "paragraph", "inlines": [{"text": "鹅腿售价为 15 元。"}]}],
                [{"type": "paragraph", "inlines": [{"text": "摊位年收入为 15 万元。"}]}],
            ],
            "claims": [
                {
                    "text": "鹅腿售价为 15 元。",
                    "claim_type": "metric",
                    "evidence_ids": ["e"],
                }
            ],
        }

        sanitized = sanitize_blocks([block], bundle)

        self.assertEqual(len(sanitized), 1)
        self.assertEqual(len(sanitized[0]["items"]), 1)
        self.assertIn("售价", str(sanitized[0]["items"]))
        self.assertNotIn("年收入", str(sanitized[0]["items"]))

    def test_one_unsupported_table_cell_rejects_the_whole_table(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="s", source_type="web", url="https://example.com")],
            evidence=[
                EvidenceRecord(
                    evidence_id="e",
                    source_id="s",
                    evidence_type="web",
                    snippet="鹅腿售价为 15 元。",
                )
            ],
        )
        block = {
            "type": "table",
            "rows": [
                {
                    "cells": [
                        {"blocks": [{"type": "paragraph", "inlines": [{"text": "鹅腿售价为 15 元。"}]}]},
                        {"blocks": [{"type": "paragraph", "inlines": [{"text": "摊位年收入为 999 万元。"}]}]},
                    ]
                }
            ],
            "claims": [
                {
                    "text": "鹅腿售价为 15 元。",
                    "claim_type": "metric",
                    "evidence_ids": ["e"],
                }
            ],
        }

        self.assertEqual(sanitize_blocks([block], bundle), [])

    def test_rich_leaf_cannot_borrow_claim_from_the_same_subject(self):
        claim = {"text": "Auntie sells food at Tsinghua.", "claim_type": "fact", "evidence_ids": ["e"]}
        block = {
            "type": "kpiGrid", "claims": [claim],
            "items": [{"label": "Auntie was arrested by police", "value": "CONFIRMED"}],
        }

        self.assertEqual(sanitize_blocks([block], {"e"}), [])

    def test_supported_rich_value_cannot_hide_a_second_unsupported_value(self):
        claim = {"text": "Auntie sells food at Tsinghua.", "claim_type": "fact", "evidence_ids": ["e"]}
        block = {
            "type": "kpiGrid", "claims": [claim],
            "items": [
                {"label": "Auntie", "value": "sells food at Tsinghua"},
                {"label": "Auntie", "value": "was arrested by police"},
            ],
        }

        self.assertEqual(sanitize_blocks([block], {"e"}), [])

    def test_container_keeps_supported_body_but_discards_unclaimed_title(self):
        text = "Auntie sells food at Tsinghua."
        block = {
            "type": "callout", "title": "Auntie was arrested by police",
            "claims": [{"text": text, "claim_type": "fact", "evidence_ids": ["e"]}],
            "blocks": [{"type": "paragraph", "inlines": [{"text": text}]}],
        }

        sanitized = sanitize_blocks([block], {"e"})

        self.assertEqual(len(sanitized), 1)
        self.assertNotIn("title", sanitized[0])
        self.assertEqual(sanitized[0]["blocks"][0]["inlines"], block["blocks"][0]["inlines"])

    def test_inherited_paragraph_must_preserve_number_units(self):
        block = {
            "type": "callout",
            "claims": [{"text": "Annual sales increased 42 people.", "claim_type": "metric", "evidence_ids": ["e"]}],
            "blocks": [{"type": "paragraph", "inlines": [{"text": "Annual sales increased 42%."}]}],
        }

        self.assertEqual(sanitize_blocks([block], {"e"}), [])

    def test_unclaimed_fact_heading_is_not_a_structural_escape_hatch(self):
        block = {"type": "heading", "level": 2, "text": "Auntie was arrested by police"}

        self.assertEqual(sanitize_blocks([block], set()), [])

    def test_widget_date_label_must_be_covered_by_claims(self):
        block = {
            "type": "widget", "widgetId": "trend", "widgetType": "chart.js/line",
            "data": {"labels": ["tomorrow"], "datasets": [{"label": "views", "data": [42]}]},
            "claims": [{"text": "views reached 42", "claim_type": "metric", "evidence_ids": ["e"]}],
        }

        self.assertEqual(sanitize_blocks([block], {"e"}), [])

    def test_supported_kpi_preserves_explicit_unit_and_presentation(self):
        block = {
            "type": "kpiGrid", "cols": 2,
            "items": [{"label": "sales", "value": "42", "unit": "%", "deltaTone": "up"}],
            "claims": [{"text": "sales reached 42%", "claim_type": "metric", "evidence_ids": ["e"]}],
        }

        sanitized = sanitize_blocks([block], {"e"})

        self.assertEqual(len(sanitized), 1)
        self.assertEqual(sanitized[0]["items"], block["items"])
        self.assertEqual(sanitize_blocks(sanitized, {"e"}), sanitized)

    def test_trusted_heading_retains_only_structural_fields(self):
        block = {
            "type": "heading", "level": 2, "text": "Overview", "anchor": "overview",
            "subtitle": "Auntie was arrested by police", "inlines": [{"text": "fabricated"}],
        }

        sanitized = sanitize_blocks([block], set(), trusted_headings={"Overview"})

        self.assertEqual(sanitized, [{"type": "heading", "level": 2, "text": "Overview", "anchor": "overview"}])

    def test_trusted_heading_whitelist_follows_nested_containers(self):
        block = {
            "type": "list", "items": [[{"type": "heading", "level": 3, "text": "Overview"}]],
        }

        sanitized = sanitize_blocks([block], set(), trusted_headings={"Overview"})

        self.assertEqual(sanitized, [block])

    def test_inherited_blocks_cannot_supply_their_own_unverified_citations(self):
        text = "Auntie sells food at Tsinghua."
        block = {
            "type": "callout",
            "claims": [{"text": text, "claim_type": "fact", "evidence_ids": ["e1"]}],
            "blocks": [{
                "type": "paragraph", "inlines": [{"text": text}],
                "citation_refs": ["e2"], "support_status": "predicted",
            }, {
                "type": "kpiGrid", "items": [{"label": "Auntie", "value": "sells food at Tsinghua"}],
                "citation_refs": ["e2"], "support_status": "supported",
            }],
        }

        sanitized = sanitize_blocks([block], {"e1", "e2"})

        self.assertEqual(sanitized[0]["citation_refs"], ["e1"])
        for child in sanitized[0]["blocks"]:
            self.assertNotIn("citation_refs", child)
            self.assertNotIn("support_status", child)

    def test_table_discards_unsupported_caption_without_losing_supported_cells(self):
        text = "Auntie sells food at Tsinghua."
        block = {
            "type": "table", "caption": "Auntie was arrested by police",
            "claims": [{"text": text, "claim_type": "fact", "evidence_ids": ["e"]}],
            "rows": [{"cells": [{"blocks": [{"type": "paragraph", "inlines": [{"text": text}]}]}]}],
        }

        sanitized = sanitize_blocks([block], {"e"})

        self.assertEqual(len(sanitized), 1)
        self.assertNotIn("caption", sanitized[0])
        self.assertEqual(sanitized[0]["rows"], block["rows"])


if __name__ == "__main__":
    unittest.main()
