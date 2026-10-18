import unittest

from common.provenance.models import ClaimRecord, EvidenceRecord, ProvenanceBundle, SourceRecord


class ProvenanceModelTests(unittest.TestCase):
    def test_bundle_roundtrip_preserves_records(self):
        bundle = ProvenanceBundle(
            bundle_id="bundle-1",
            agent="query_engine",
            sources=[SourceRecord(source_id="src-1", title="Source", url="https://example.com/a")],
            evidence=[EvidenceRecord(evidence_id="ev-1", source_id="src-1", snippet="Evidence")],
            claims=[ClaimRecord(claim_id="cl-1", text="Claim", evidence_ids=["ev-1"], status="supported")],
        )

        restored = ProvenanceBundle.from_dict(bundle.to_dict())

        self.assertEqual(restored.bundle_id, "bundle-1")
        self.assertEqual(restored.sources[0].url, "https://example.com/a")
        self.assertEqual(restored.evidence[0].snippet, "Evidence")
        self.assertEqual(restored.claims[0].evidence_ids, ["ev-1"])

    def test_legacy_and_missing_fields_get_stable_defaults(self):
        bundle = ProvenanceBundle.from_dict(
            {
                "agent": "legacy",
                "source_records": [{"id": "src-old", "published_at": "2026-01-01"}],
                "evidence_records": [{"id": "ev-old", "content": "legacy evidence"}],
                "claims": [{"id": "cl-old", "citation_refs": "ev-old"}],
            }
        )

        self.assertEqual(bundle.sources[0].source_id, "src-old")
        self.assertEqual(bundle.sources[0].publish_time, "2026-01-01")
        self.assertEqual(bundle.evidence[0].snippet, "legacy evidence")
        self.assertEqual(bundle.claims[0].evidence_ids, ["ev-old"])
        self.assertIsInstance(bundle.meta, dict)


if __name__ == "__main__":
    unittest.main()
