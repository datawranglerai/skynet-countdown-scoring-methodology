"""Integrity of the frozen evidence and its separately stored historical references."""

import json
import unittest
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit

from skynet_countdown.benchmark import BenchmarkDataset

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "examples/benchmarks"


class BenchmarkDataTests(unittest.TestCase):
    dataset: ClassVar[BenchmarkDataset]
    assessments: ClassVar[dict[str, Any]]
    sources: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls):
        cls.dataset = BenchmarkDataset.model_validate_json(
            (BENCHMARKS / "benchmark.json").read_text(encoding="utf-8")
        )
        cls.assessments = {
            item["id"]: item
            for item in json.loads((BENCHMARKS / "assessments.json").read_text(encoding="utf-8"))
        }
        cls.sources = {
            item["assessment_id"]: item
            for item in json.loads(
                (BENCHMARKS / "source_manifest.json").read_text(encoding="utf-8")
            )["records"]
        }

    def test_export_hashes_and_selected_source_manifest_match(self):
        for source in self.dataset.provenance["source_exports"].values():
            self.assertEqual(sha256((ROOT / source["path"]).read_bytes()).hexdigest(), source["sha256"])
        selected = {key for key, source in self.sources.items() if source["selected"]}
        self.assertEqual(selected, {case.provenance["assessment_id"] for case in self.dataset.cases})
        for case in self.dataset.cases:
            with self.subTest(story=case.story.id):
                provenance = case.provenance["source"]
                source = self.sources[case.provenance["assessment_id"]]
                self.assertEqual(source["status"], "retrieved")
                self.assertEqual(provenance["response_sha256"], source["response_sha256"])
                self.assertEqual(provenance["resolved_url"], source["resolved_url"])
                self.assertEqual(provenance["content_kind"], "source_grounded_summary")
                content = case.story.content
                assert content is not None
                self.assertEqual(
                    sha256(content.encode("utf-8")).hexdigest(),
                    provenance["content_sha256"],
                )
                self.assertFalse(case.story.metadata)

    def test_selected_events_and_source_paths_are_unique(self):
        cases = self.dataset.cases
        self.assertEqual(len({case.provenance["event_id"] for case in cases}), len(cases))
        canonical = [urlsplit(case.provenance["source"]["resolved_url"]) for case in cases]
        self.assertEqual(len({(url.netloc, url.path.rstrip("/")) for url in canonical}), len(cases))

    def test_historical_component_ratings_are_preserved_without_relabelling(self):
        amplifier_columns = {
            "governance_vacuum": "amp_governance_vacuum_score",
            "autonomy_without_oversight": "amp_autonomy_score",
            "human_capability_erosion": "amp_capability_erosion_score",
            "sentience_self_preservation": "amp_sentience_score",
            "physical_weaponisation": "amp_physical_score",
        }
        for case in self.dataset.cases:
            with self.subTest(story=case.story.id):
                row = self.assessments[case.provenance["assessment_id"]]
                self.assertEqual(case.provenance["event_id"], row["event_id"])
                self.assertEqual(str(case.story.source_url), row["source_url"])
                for key in ("t1", "t2", "t3"):
                    self.assertEqual(getattr(case.reference.trifecta, key).score, row[key + "_score"])
                for key, column in amplifier_columns.items():
                    self.assertEqual(getattr(case.reference.amplifiers, key).score, row[column])
                self.assertEqual(case.reference.is_leading_indicator, row["is_leading_indicator"])
                self.assertEqual(case.provenance["historical_raw_total"], row["total_score"])
                self.assertNotIn("\ue200", case.reference.model_dump_json())


if __name__ == "__main__":
    unittest.main()
