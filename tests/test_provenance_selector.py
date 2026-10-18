import unittest

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.selector import EvidenceSelector


class EvidenceSelectorTests(unittest.TestCase):
    def test_selects_only_top_k_relevant_evidence(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id=f"s{i}", title=f"source {i}") for i in range(4)],
            evidence=[
                EvidenceRecord(evidence_id="climate-1", source_id="s0", snippet="climate policy and carbon market"),
                EvidenceRecord(evidence_id="sports-1", source_id="s1", snippet="football league score"),
                EvidenceRecord(evidence_id="climate-2", source_id="s2", snippet="carbon emissions policy update"),
                EvidenceRecord(evidence_id="music-1", source_id="s3", snippet="concert ticket sales"),
            ],
        )

        selected = EvidenceSelector(top_k=2).select(bundle, chapter_topic="climate carbon policy")

        self.assertEqual(len(selected.evidence), 2)
        self.assertEqual({item.evidence_id for item in selected.evidence}, {"climate-1", "climate-2"})
        self.assertLess(len(selected.evidence), len(bundle.evidence))
        self.assertTrue(all(item.meta.get("selection_reason") for item in selected.evidence))

    def test_chinese_single_character_overlap_cannot_select_unrelated_source(self):
        bundle = ProvenanceBundle(
            sources=[SourceRecord(source_id="unrelated", title="中国电影艺术")],
            evidence=[
                EvidenceRecord(
                    evidence_id="unrelated-evidence",
                    source_id="unrelated",
                    snippet="中国电影艺术正在发展。",
                )
            ],
        )

        selected = EvidenceSelector().select(
            bundle,
            chapter_topic="清华鹅腿阿姨",
        )

        self.assertEqual(selected.evidence, [])

    def test_report_query_selects_topic_evidence_for_generic_chapter(self):
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

        selected = EvidenceSelector().select(
            bundle,
            chapter_topic="报告摘要",
            chapter_draft="概述主要发现和风险",
            report_query="清华鹅腿阿姨",
        )

        self.assertEqual(
            [item.evidence_id for item in selected.evidence],
            ["goose-evidence"],
        )


if __name__ == "__main__":
    unittest.main()
