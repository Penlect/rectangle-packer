"""Test reproducibility and validation contracts in the benchmark pipeline."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from benchmark import plot as benchmark_plot
from benchmark import suite
from benchmark import results as benchmark_results
from benchmark.results import BenchmarkValidationError, _validate_records
from benchmark.publish import publish_benchmark
from benchmark.runner import _generate_sizes


def _records(jobs: list[suite.Job]) -> list[dict[str, object]]:
    return [
        {
            **asdict(job),
            "time_per_call_ns": float(index * 1_000),
            "elapsed_ns": index * 1_000,
            "repeat": 1,
            "density": 0.9,
            "total_area": job.n * 9,
            "bbox_width": 10,
            "bbox_height": job.n,
            "used_bigint_fallback": False,
        }
        for index, job in enumerate(jobs, 1)
    ]


def _measured_records(jobs: list[suite.Job]) -> list[dict[str, object]]:
    records = _records(jobs)
    for index, record in enumerate(records, start=1):
        record.update(
            time_per_call_ns=float(index * 1_000),
            density=0.9,
            used_bigint_fallback=False,
        )
    return records


def _manifest(jobs: list[suite.Job], profile: str = "historical") -> dict[str, object]:
    keys = [suite.job_key(job) for job in jobs]
    algorithms = list(dict.fromkeys(job.algorithm for job in jobs))
    return {
        "benchmark_schema_version": 1,
        "status": "complete",
        "profile": profile,
        "algorithms": algorithms,
        "expected_job_count": len(jobs),
        "completed_job_count": len(jobs),
        "job_grid_sha256": suite.job_grid_sha256(keys),
    }


def _plot_test_campaign(input_dir: Path, plot_dir: Path) -> dict[str, object]:
    """Exercise plot provenance without depending on Matplotlib."""

    def write_figure(summary, algorithms, output_dir):
        (output_dir / "benchmark_random_overview.svg").write_text(
            "<svg>" + json.dumps(summary, sort_keys=True) + "</svg>", encoding="utf-8"
        )

    with mock.patch.object(
        benchmark_plot, "_load_plot_dependencies"
    ), mock.patch.object(
        benchmark_plot, "_plot_random_overview", side_effect=write_figure
    ):
        return benchmark_plot.plot_benchmarks(input_dir, plot_dir)


class TestBenchmarkSuite(unittest.TestCase):
    def test_scale_sweep_keeps_fixed_geometry(self) -> None:
        seed = suite.stable_seed(suite.BASE_SEED, "scale_sweep", "uniform", 0)
        base_job = suite.Job(
            benchmark="scale_sweep",
            algorithm="default",
            family="uniform",
            n=suite.SCALE_SWEEP_N,
            scale=1,
            instance=0,
            seed=seed,
        )
        scaled_job = replace(base_job, scale=64)

        base_sizes = _generate_sizes(base_job)
        scaled_sizes = _generate_sizes(scaled_job)

        self.assertEqual(
            scaled_sizes,
            [(width * 64, height * 64) for width, height in base_sizes],
        )

    def test_algorithms_share_the_same_job_grid(self) -> None:
        jobs = suite.build_jobs(suite.PROFILES["smoke"], ["first", "second"])
        first = [replace(job, algorithm="") for job in jobs if job.algorithm == "first"]
        second = [
            replace(job, algorithm="") for job in jobs if job.algorithm == "second"
        ]

        self.assertEqual(first, second)

    def test_job_grid_digest_is_order_independent_and_sensitive(self) -> None:
        jobs = suite.build_jobs(suite.PROFILES["smoke"], ["default"])
        keys = [suite.job_key(job) for job in jobs]

        self.assertEqual(
            suite.job_grid_sha256(keys),
            suite.job_grid_sha256(reversed(keys)),
        )
        self.assertNotEqual(
            suite.job_grid_sha256(keys),
            suite.job_grid_sha256(keys[:-1]),
        )


class TestBenchmarkValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = [
            suite.Job(
                benchmark="count_sweep",
                algorithm="default",
                family="uniform",
                n=10,
                scale=1000,
                instance=instance,
                seed=instance,
            )
            for instance in range(2)
        ]

    def test_manifest_digest_validates_without_current_profile(self) -> None:
        _validate_records(_records(self.jobs), _manifest(self.jobs))

    def test_historical_run_is_summarized_from_its_records(self) -> None:
        records = _measured_records(self.jobs)
        manifest = _manifest(self.jobs)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            input_dir.mkdir()
            (input_dir / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (input_dir / "results.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            with mock.patch.object(
                benchmark_plot, "_load_plot_dependencies"
            ), mock.patch.object(
                benchmark_plot, "_plot_random_overview"
            ) as random_plot, mock.patch.object(
                benchmark_plot, "_plot_scale_sweep"
            ), mock.patch.object(
                benchmark_plot, "_plot_structured"
            ), mock.patch.object(
                benchmark_plot, "_plot_pathology"
            ):
                random_plot.side_effect = lambda summary, algorithms, output_dir: (
                    output_dir / "benchmark_random_overview.svg"
                ).write_text("<svg/>")
                summary = benchmark_plot.plot_benchmarks(input_dir, output_dir)

            random_plot.assert_called_once()
            points = summary["count_sweep"]["default"]["uniform"]["points"]
            self.assertEqual([point["n"] for point in points], [10])
            self.assertFalse(summary["scale_sweep"]["default"])

    def test_scale_summary_uses_paired_instance_slowdowns(self) -> None:
        jobs = [
            suite.Job(
                benchmark="scale_sweep",
                algorithm="default",
                family="uniform",
                n=2,
                scale=scale,
                instance=instance,
                seed=instance,
            )
            for scale in (1, 4)
            for instance in (0, 1)
        ]
        records = _measured_records(jobs)
        times = {(record["scale"], record["instance"]): record for record in records}
        times[(1, 0)]["time_per_call_ns"] = 10.0
        times[(1, 1)]["time_per_call_ns"] = 20.0
        times[(4, 0)]["time_per_call_ns"] = 20.0
        times[(4, 1)]["time_per_call_ns"] = 60.0

        summary = benchmark_results._summarize_scale_sweep(records, ["default"])
        scaled = summary["default"]["uniform"]["points"][1]
        self.assertEqual(scaled["relative_time"]["median"], 2.5)

    def test_publication_includes_verified_compressed_raw_results(self) -> None:
        records = _measured_records(self.jobs)
        manifest = _manifest(self.jobs)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            plot_dir = root / "plots"
            data_dir = root / "published-data"
            image_dir = root / "published-images"
            input_dir.mkdir()
            plot_dir.mkdir()
            (input_dir / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (input_dir / "results.jsonl").write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            _plot_test_campaign(input_dir, plot_dir)

            published = publish_benchmark(
                input_dir,
                plot_dir,
                data_dir,
            )
            loaded = benchmark_results._load_records(data_dir, published)
            first_artifact = (data_dir / "results.jsonl.gz").read_bytes()
            second_dir = root / "second-publication"
            republished = publish_benchmark(input_dir, plot_dir, second_dir)
            with self.assertRaises(FileExistsError):
                publish_benchmark(input_dir, plot_dir, data_dir)

            self.assertEqual(loaded, records)
            self.assertEqual(published["results_file"], "results.jsonl.gz")
            self.assertEqual(len(published["results_sha256"]), 64)
            self.assertEqual(republished["results_sha256"], published["results_sha256"])
            self.assertEqual(
                (data_dir / "results.jsonl.gz").read_bytes(), first_artifact
            )
            binding = json.loads((data_dir / "plot_manifest.json").read_text())
            self.assertEqual(
                binding["results_uncompressed_sha256"],
                published["results_uncompressed_sha256"],
            )
            self.assertEqual(
                binding["summary_sha256"],
                benchmark_results._sha256_file(data_dir / "summary.json"),
            )
            self.assertEqual(
                binding["figures"]["benchmark_random_overview.svg"],
                benchmark_results._sha256_file(
                    data_dir / "benchmark_random_overview.svg"
                ),
            )

            with (data_dir / "results.jsonl.gz").open("ab") as fh:
                fh.write(b"corrupt")
            with self.assertRaisesRegex(
                BenchmarkValidationError, "digest does not match manifest"
            ):
                benchmark_results._load_records(data_dir, published)

    def test_publication_rejects_stale_or_damaged_plot_artifacts(self) -> None:
        for damage in (
            "measurements",
            "summary",
            "figure",
            "missing_figure",
            "missing_manifest",
        ):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory(
                prefix="TMP_rpack_publish_"
            ) as tmp:
                root = Path(tmp)
                input_dir, plot_dir = root / "input", root / "plots"
                input_dir.mkdir()
                records = _measured_records(self.jobs)
                manifest = _manifest(self.jobs)
                raw_path = input_dir / "results.jsonl"
                (input_dir / "manifest.json").write_text(json.dumps(manifest))
                raw_path.write_text(
                    "".join(json.dumps(record) + "\n" for record in records)
                )
                _plot_test_campaign(input_dir, plot_dir)
                if damage == "measurements":
                    # Same jobs and record count, different measured timings.
                    for record in records:
                        record["time_per_call_ns"] *= 1000
                    raw_path.write_text(
                        "".join(json.dumps(record) + "\n" for record in records)
                    )
                elif damage == "summary":
                    summary_path = plot_dir / "benchmark_summary.json"
                    summary = json.loads(summary_path.read_text())
                    summary["count_sweep"]["default"]["uniform"]["points"][0][
                        "time_seconds"
                    ]["median"] = 1.0
                    summary_path.write_text(json.dumps(summary))
                elif damage == "figure":
                    (plot_dir / "benchmark_random_overview.svg").write_text(
                        "<svg>stale</svg>"
                    )
                elif damage == "missing_figure":
                    (plot_dir / "benchmark_random_overview.svg").unlink()
                else:
                    (plot_dir / "plot_manifest.json").unlink()

                data_dir, image_dir = root / "published", root / "images"
                data_dir.mkdir()
                image_dir.mkdir()
                (data_dir / "manifest.json").write_text("original data")
                (image_dir / "benchmark_random_overview.svg").write_text(
                    "original image"
                )
                with self.assertRaises(ValueError):
                    publish_benchmark(input_dir, plot_dir, data_dir)
                self.assertEqual(
                    (data_dir / "manifest.json").read_text(), "original data"
                )
                self.assertEqual(
                    (image_dir / "benchmark_random_overview.svg").read_text(),
                    "original image",
                )
                self.assertFalse((data_dir / "results.jsonl.gz").exists())

    def test_interrupted_plotting_invalidates_previous_completion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="TMP_rpack_plot_") as tmp:
            root = Path(tmp)
            input_dir, plot_dir = root / "input", root / "plots"
            input_dir.mkdir()
            (input_dir / "manifest.json").write_text(json.dumps(_manifest(self.jobs)))
            (input_dir / "results.jsonl").write_text(
                "".join(
                    json.dumps(record) + "\n" for record in _measured_records(self.jobs)
                )
            )
            _plot_test_campaign(input_dir, plot_dir)
            with mock.patch.object(
                benchmark_plot, "_load_plot_dependencies"
            ), mock.patch.object(
                benchmark_plot,
                "_plot_random_overview",
                side_effect=RuntimeError("plot failed"),
            ), self.assertRaisesRegex(
                RuntimeError, "plot failed"
            ):
                benchmark_plot.plot_benchmarks(input_dir, plot_dir)
            self.assertFalse((plot_dir / "plot_manifest.json").exists())

    def test_validation_module_does_not_require_plot_dependencies(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        subprocess.run(
            [sys.executable, "-S", "-c", "import benchmark.plot"],
            cwd=project_root,
            check=True,
        )

    def test_duplicate_records_are_rejected(self) -> None:
        records = _records(self.jobs)
        records.append(records[0].copy())
        manifest = _manifest(self.jobs)
        manifest["expected_job_count"] = len(records)
        manifest["completed_job_count"] = len(records)

        with self.assertRaisesRegex(BenchmarkValidationError, "duplicated record key"):
            _validate_records(records, manifest)

    def test_changed_job_grid_is_rejected(self) -> None:
        records = _records(self.jobs[:-1])
        manifest = _manifest(self.jobs)
        manifest["completed_job_count"] = len(records)

        with self.assertRaisesRegex(BenchmarkValidationError, "job-grid digest"):
            _validate_records(records, manifest)

    def test_current_profile_reports_missing_job(self) -> None:
        jobs = suite.build_jobs(suite.PROFILES["smoke"], ["default"])
        records = _records(jobs[:-1])
        manifest = _manifest(jobs, profile="smoke")
        manifest["completed_job_count"] = len(records)

        with self.assertRaisesRegex(
            BenchmarkValidationError, "missing 1 expected record"
        ):
            _validate_records(records, manifest)


if __name__ == "__main__":
    unittest.main()
