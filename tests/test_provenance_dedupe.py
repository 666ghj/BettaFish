import unittest

from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from common.provenance.normalizer import dedupe_bundle, merge_bundles
from common.provenance.selector import EvidenceSelector


class ProvenanceDedupeTests(unittest.TestCase):
    def _deduped_count(self, evidence_type, locator=None, scope=None, snippet="same"):
        locator = locator or {}
        scope = scope or {}
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(source_id="s1", source_type="web", url="https://example.com/item", locator=locator),
                SourceRecord(source_id="s2", source_type="web", url="https://example.com/item/", locator=locator),
            ],
            evidence=[
                EvidenceRecord(evidence_id="e1", source_id="s1", evidence_type=evidence_type, snippet=snippet, scope=scope),
                EvidenceRecord(evidence_id="e2", source_id="s2", evidence_type=evidence_type, snippet=snippet, scope=scope),
            ],
        )
        return len(dedupe_bundle(bundle).evidence)

    def test_web_uses_url_locator_and_content_hash(self):
        self.assertEqual(self._deduped_count("web", locator={"page": 2}), 1)

    def test_video_comment_uses_post_comment_timestamp(self):
        scope = {"post_id": "p1", "comment_id": "c1", "timestamp": "00:42"}
        self.assertEqual(self._deduped_count("comment", scope=scope), 1)

    def test_db_row_uses_table_and_primary_key(self):
        self.assertEqual(self._deduped_count("db_row", scope={"table": "posts", "primary_key": 7}), 1)

    def test_db_agg_uses_full_query_signature(self):
        scope = {
            "table": "posts",
            "metric": "count",
            "filters": {"platform": "weibo"},
            "time_window": {"start": "2026-01-01", "end": "2026-01-31"},
            "aggregation_method": "count",
        }
        self.assertEqual(self._deduped_count("db_agg", scope=scope), 1)

    def test_merge_bundle_id_is_deterministic(self):
        bundle = ProvenanceBundle(
            agent="query_engine",
            bundle_id="input-bundle",
            sources=[SourceRecord(source_id="s1", source_type="web", url="https://example.com")],
            evidence=[EvidenceRecord(evidence_id="e1", source_id="s1", evidence_type="web", snippet="fact")],
        )

        first = merge_bundles([bundle])
        second = merge_bundles([bundle])
        merged_again = merge_bundles([first])

        self.assertEqual(first.bundle_id, second.bundle_id)
        self.assertEqual(first.bundle_id, merged_again.bundle_id)
        self.assertEqual(merged_again.meta["input_bundle_ids"], ["input-bundle"])

    def test_duplicate_source_keeps_richer_later_attribution(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(
                    source_id="s1",
                    agent="query_engine",
                    source_type="web",
                    url="https://example.com/item",
                    title="短标题",
                ),
                SourceRecord(
                    source_id="s2",
                    agent="media_engine",
                    source_type="web",
                    url="https://example.com/item/",
                    title="更完整的来源标题",
                    author="作者",
                    publish_time="2026-09-01",
                ),
            ],
            evidence=[],
        )

        source = dedupe_bundle(bundle).sources[0]

        self.assertEqual(source.title, "更完整的来源标题")
        self.assertEqual(source.author, "作者")
        self.assertEqual(source.publish_time, "2026-09-01")
        self.assertEqual(source.meta["agents"], ["query_engine", "media_engine"])

    def test_updated_database_row_is_not_aliased_to_old_content(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(source_id="s1", source_type="database", title="posts", locator={"table": "posts"}),
                SourceRecord(source_id="s2", source_type="database", title="posts", locator={"table": "posts"}),
            ],
            evidence=[
                EvidenceRecord(evidence_id="old", source_id="s1", evidence_type="db_row",
                               snippet="recall announced", scope={"table": "posts", "primary_key": 7}),
                EvidenceRecord(evidence_id="new", source_id="s2", evidence_type="db_row",
                               snippet="recall withdrawn", scope={"table": "posts", "primary_key": 7}),
            ],
        )

        deduped = dedupe_bundle(bundle)

        self.assertEqual({item.evidence_id for item in deduped.evidence}, {"old", "new"})
        self.assertEqual(deduped.meta["evidence_aliases"], {})

    def test_updated_media_record_is_not_aliased_to_old_content(self):
        bundle = ProvenanceBundle(
            sources=[
                SourceRecord(source_id="s1", source_type="video", platform="douyin",
                             locator={"post_id": "p7"}),
                SourceRecord(source_id="s2", source_type="video", platform="douyin",
                             locator={"post_id": "p7"}),
            ],
            evidence=[
                EvidenceRecord(evidence_id="old", source_id="s1", evidence_type="video",
                               snippet="旧字幕", scope={"post_id": "p7"}),
                EvidenceRecord(evidence_id="new", source_id="s2", evidence_type="video",
                               snippet="新字幕", scope={"post_id": "p7"}),
            ],
        )

        deduped = dedupe_bundle(bundle)

        self.assertEqual({item.evidence_id for item in deduped.evidence}, {"old", "new"})
        self.assertEqual(deduped.meta["evidence_aliases"], {})

    def test_identical_content_unions_contexts_and_selection_is_order_independent(self):
        source = SourceRecord(source_id="s", source_type="web", url="https://example.com/item")
        first = EvidenceRecord(evidence_id="z", source_id="s", evidence_type="web",
                               snippet="共同事实", scope={"subject": "第一章", "query": "甲"})
        second = EvidenceRecord(evidence_id="a", source_id="s", evidence_type="web",
                                snippet="共同事实", scope={"subject": "第二章", "query": "乙"})
        selector = EvidenceSelector()

        selected_forward = selector.select(
            ProvenanceBundle(sources=[source], evidence=[first, second]),
            chapter_topic="第二章",
        )
        selected_reverse = selector.select(
            ProvenanceBundle(sources=[source], evidence=[second, first]),
            chapter_topic="第二章",
        )

        self.assertEqual([item.evidence_id for item in selected_forward.evidence], ["a"])
        self.assertEqual([item.evidence_id for item in selected_reverse.evidence], ["a"])
        contexts = selected_forward.evidence[0].meta["retrieval_contexts"]
        self.assertEqual({item["subject"] for item in contexts}, {"第一章", "第二章"})


if __name__ == "__main__":
    unittest.main()
