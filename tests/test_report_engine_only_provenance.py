import tempfile
import unittest
from pathlib import Path

from common.provenance.io import save_sidecar
from common.provenance.models import EvidenceRecord, ProvenanceBundle, SourceRecord
from report_engine_only import load_provenance_bundle
from ReportEngine.agent import InsufficientInputError, ReportAgent


class ReportEngineOnlyProvenanceTests(unittest.TestCase):
    def _write_report(
        self,
        root: Path,
        engine: str,
        query: str | None,
        *,
        run_id: str = "",
        bundle_agent: str | None = None,
    ) -> str:
        report = root / f"{engine}.md"
        report.write_text(f"{engine} report", encoding="utf-8")
        meta = {"query": query} if query is not None else {}
        if run_id:
            meta["run_id"] = run_id
        agent = bundle_agent or f"{engine}_engine"
        save_sidecar(
            ProvenanceBundle(
                agent=agent,
                sources=[
                    SourceRecord(
                        source_id=f"{engine}-source",
                        agent=agent,
                        source_type="web",
                        url=f"https://example.com/{engine}",
                    )
                ],
                evidence=[
                    EvidenceRecord(
                        evidence_id=f"{engine}-evidence",
                        source_id=f"{engine}-source",
                        agent=agent,
                        evidence_type="web",
                        snippet=query or "missing query",
                    )
                ],
                meta=meta,
            ),
            report,
        )
        return str(report)

    def test_matching_sidecars_supply_the_authoritative_query(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                engine: self._write_report(root, engine, "清华鹅腿阿姨")
                for engine in ("query", "media", "insight")
            }

            bundle = load_provenance_bundle(files)

        self.assertEqual(bundle.meta["query"], "清华鹅腿阿姨")
        self.assertEqual(len(bundle.evidence), 3)

    def test_mixed_sidecar_queries_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                "query": self._write_report(root, "query", "清华鹅腿阿姨"),
                "media": self._write_report(root, "media", "另一个主题"),
                "insight": self._write_report(root, "insight", "清华鹅腿阿姨"),
            }

            with self.assertRaisesRegex(ValueError, "查询主题不一致"):
                load_provenance_bundle(files)

    def test_explicit_query_must_match_sidecar_query(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                engine: self._write_report(root, engine, "清华鹅腿阿姨")
                for engine in ("query", "media", "insight")
            }

            with self.assertRaisesRegex(ValueError, "--query"):
                load_provenance_bundle(files, expected_query="另一个主题")

    def test_missing_sidecar_query_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                "query": self._write_report(root, "query", "清华鹅腿阿姨"),
                "media": self._write_report(root, "media", None),
                "insight": self._write_report(root, "insight", "清华鹅腿阿姨"),
            }

            with self.assertRaisesRegex(ValueError, "meta.query"):
                load_provenance_bundle(files)

    def test_sidecar_from_wrong_engine_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                "query": self._write_report(root, "query", "清华鹅腿阿姨"),
                "media": self._write_report(
                    root,
                    "media",
                    "清华鹅腿阿姨",
                    bundle_agent="query_engine",
                ),
                "insight": self._write_report(root, "insight", "清华鹅腿阿姨"),
            }

            with self.assertRaisesRegex(ValueError, "错误的 provenance sidecar"):
                load_provenance_bundle(files)

    def test_sidecars_from_different_runs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                "query": self._write_report(root, "query", "清华鹅腿阿姨", run_id="run-a"),
                "media": self._write_report(root, "media", "清华鹅腿阿姨", run_id="run-b"),
                "insight": self._write_report(root, "insight", "清华鹅腿阿姨", run_id="run-a"),
            }

            with self.assertRaisesRegex(ValueError, "不同运行轮次"):
                load_provenance_bundle(files)

    def test_report_agent_rejects_missing_sidecar_when_query_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = root / "query.md"
            report.write_text("query report", encoding="utf-8")
            agent = ReportAgent.__new__(ReportAgent)

            with self.assertRaisesRegex(InsufficientInputError, "缺少 provenance sidecar"):
                agent.load_input_files(
                    {"query": str(report)},
                    expected_query="清华鹅腿阿姨",
                )

    def test_report_agent_rejects_malformed_sidecar_when_query_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = root / "query.md"
            report.write_text("query report", encoding="utf-8")
            report.with_suffix(".provenance.json").write_text(
                "{broken", encoding="utf-8"
            )
            agent = ReportAgent.__new__(ReportAgent)

            with self.assertRaisesRegex(InsufficientInputError, "sidecar"):
                agent.load_input_files(
                    {"query": str(report)},
                    expected_query="清华鹅腿阿姨",
                )


if __name__ == "__main__":
    unittest.main()
