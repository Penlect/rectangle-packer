"""Test paired comparisons and data-derived reports without expensive benchmark runs."""

import json
from pathlib import Path
import tempfile
import unittest

from benchmark.compare import compare_campaigns
from benchmark.publish import publish_benchmark
from benchmark.report import write_report
from benchmark.results import load_campaign
from benchmark.storage import write_json

if __package__:
    from .benchmark_fixtures import make_campaign
    from .test_benchmark import _plot_test_campaign
else:
    from benchmark_fixtures import make_campaign
    from test_benchmark import _plot_test_campaign


class TestBenchmarkComparison(unittest.TestCase):
    def test_invalid_configuration_cannot_be_compared(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            manifest, _, _ = make_campaign(root / "run")
            for key, value in (
                ("workers", True),
                ("timing_blocks", 1),
                ("timeout_seconds", -1),
            ):
                with self.subTest(key=key):
                    write_json(root / "run/manifest.json", {**manifest, key: value})
                    with self.assertRaisesRegex(
                        ValueError, "invalid measurement configuration"
                    ):
                        load_campaign(root / "run")

    def test_library_identity_is_checked_against_archived_files(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            manifest, _, _ = make_campaign(root / "run")
            manifest["source"]["library_source_sha256"] = "0" * 64
            write_json(root / "run/manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "library source digest"):
                load_campaign(root / "run")

    def test_known_runtime_ratio_and_unchanged_quality(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            make_campaign(root / "baseline")
            make_campaign(root / "candidate", factor=2)
            result = compare_campaigns(
                root / "baseline", root / "candidate", root / "comparison"
            )
            self.assertEqual(result["overall"]["runtime_ratio"]["median"], 2)
            self.assertIsNone(result["overall"]["runtime_ratio"]["median_ci95"])
            self.assertEqual(
                result["groups"][0]["runtime_ratio"]["median_ci95"], [2, 2]
            )
            self.assertEqual(result["overall"]["area_ratio"]["median"], 1)
            self.assertEqual(result["overall"]["density_change"]["median"], 0)
            self.assertTrue(result["controlled_conditions"])
            self.assertIn("2.0000x", (root / "comparison/report.rst").read_text())
            with self.assertRaises(FileExistsError):
                compare_campaigns(
                    root / "baseline", root / "candidate", root / "comparison"
                )

    def test_different_inputs_are_not_compared(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            make_campaign(root / "baseline")
            make_campaign(root / "candidate", seed_offset=10)
            with self.assertRaisesRegex(ValueError, "corpora differ"):
                compare_campaigns(
                    root / "baseline", root / "candidate", root / "comparison"
                )
            self.assertFalse((root / "comparison").exists())

    def test_environment_changes_require_explicit_opt_in(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            make_campaign(root / "baseline")
            manifest, _, _ = make_campaign(root / "candidate")
            manifest.update(
                workers=8, worker_cpus=list(range(8)), measurement_mode="concurrent"
            )
            write_json(root / "candidate/manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "conditions differ"):
                compare_campaigns(
                    root / "baseline", root / "candidate", root / "comparison"
                )
            result = compare_campaigns(
                root / "baseline",
                root / "candidate",
                root / "comparison",
                allow_environment_change=True,
            )
            self.assertFalse(result["controlled_conditions"])
            self.assertIn(
                "Uncontrolled comparison", (root / "comparison/report.rst").read_text()
            )

    def test_timeout_is_an_outcome_change_not_a_fast_measurement(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            make_campaign(root / "baseline")
            make_campaign(root / "candidate", timeout=True)
            result = compare_campaigns(
                root / "baseline", root / "candidate", root / "comparison"
            )
            self.assertEqual(result["overall"]["runtime_ratio"]["count"], 2)
            self.assertEqual(result["overall"]["outcome_pairs"]["ok -> timeout"], 1)
            self.assertEqual(len(result["outcome_changes"]), 1)
            self.assertIsNone(result["outcome_changes"][0]["runtime_ratio"])

    def test_corpus_changes_are_detected_even_with_unchanged_job_labels(self):
        with tempfile.TemporaryDirectory(prefix="TMP_compare_") as directory:
            root = Path(directory)
            manifest, records, _ = make_campaign(root / "campaign")
            records[0]["input_sha256"] = "0" * 64
            raw = root / "campaign/results.jsonl"
            raw.write_text("".join(json.dumps(r) + "\n" for r in records))
            from benchmark.storage import sha256_file

            manifest["results_sha256"] = manifest["results_uncompressed_sha256"] = (
                sha256_file(raw)
            )
            write_json(root / "campaign/manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "input does not match"):
                load_campaign(root / "campaign")


class TestBenchmarkReport(unittest.TestCase):
    def test_report_uses_verified_data_and_local_campaign_links(self):
        with tempfile.TemporaryDirectory(prefix="TMP_report_") as directory:
            root = Path(directory)
            make_campaign(root / "run")
            _plot_test_campaign(root / "run", root / "plots")
            publish_benchmark(root / "run", root / "plots", root / "published")
            page = root / "docs/campaign.rst"
            write_report(root / "published", page)
            text = page.read_text()
            self.assertIn("test-machine / test CPU", text)
            self.assertIn("../published/results.jsonl.gz", text)
            self.assertIn("../published/benchmark_random_overview.svg", text)
            self.assertIn("3 / 3", text)
            self.assertNotIn("2026-07-15", text)
            with self.assertRaises(FileExistsError):
                write_report(root / "published", page)
            self.assertEqual(page.read_text(), text)
            (root / "published/benchmark_random_overview.svg").write_text(
                "damaged figure"
            )
            with self.assertRaisesRegex(ValueError, "figure does not match"):
                write_report(root / "published", root / "bad.rst")
            self.assertFalse((root / "bad.rst").exists())

    def test_report_does_not_hide_timeouts(self):
        with tempfile.TemporaryDirectory(prefix="TMP_report_") as directory:
            root = Path(directory)
            make_campaign(root / "run", timeout=True)
            _plot_test_campaign(root / "run", root / "plots")
            publish_benchmark(root / "run", root / "plots", root / "published")
            write_report(root / "published", root / "campaign.rst")
            self.assertIn(
                "Some workloads timed out", (root / "campaign.rst").read_text()
            )


if __name__ == "__main__":
    unittest.main()
