"""Exercise saved evidence, process cancellation, and overwrite protections."""

from dataclasses import replace
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest import mock

from benchmark import corpus, provenance, results, runner, suite
from benchmark.publish import _compress_results, publish_benchmark
from benchmark.storage import new_directory

if __package__:
    from .test_benchmark import _manifest, _measured_records, _plot_test_campaign
else:
    from test_benchmark import _manifest, _measured_records, _plot_test_campaign


def _controlled_worker(connection, cpu, target, repeat, blocks, runtime):
    case = connection.recv()
    if case["job"]["instance"] == 0:
        time.sleep(30)
    else:
        connection.send({**case["job"], "status": "ok"})


def _failing_worker(connection, cpu, target, repeat, blocks, runtime):
    case = connection.recv()
    if case["job"]["instance"] == 0:
        connection.send(
            {**case["job"], "status": "error", "error": "intentional failure"}
        )
    else:
        time.sleep(30)


def _crashing_worker(connection, cpu, target, repeat, blocks, runtime):
    connection.recv()
    os._exit(7)


def _preloaded_worker(*args):
    import rpack

    runner._worker(*args)


class TestBenchmarkEvidence(unittest.TestCase):
    def test_reusing_output_directory_preserves_every_byte(self):
        with tempfile.TemporaryDirectory(prefix="TMP_bench_") as directory:
            root = Path(directory)
            for name in ("manifest.json", "results.jsonl"):
                (root / name).write_text("previous evidence")
            with self.assertRaises(FileExistsError):
                runner.run_benchmarks(root, "smoke", rebuild=False)
            for name in ("manifest.json", "results.jsonl"):
                self.assertEqual((root / name).read_text(), "previous evidence")

    def test_same_file_compression_cannot_truncate_input(self):
        with tempfile.TemporaryDirectory(prefix="TMP_bench_") as directory:
            source = Path(directory) / "results.jsonl.gz"
            source.write_bytes(gzip.compress(b"previous evidence"))
            before = source.read_bytes()
            with self.assertRaises(ValueError):
                _compress_results(source, source)
            alias = source.with_name("alias.gz")
            # Windows can restrict symlink creation even for a writable directory.
            try:
                alias.symlink_to(source)
            except OSError:
                self.assertEqual(source.read_bytes(), before)
                return
            with self.assertRaises(ValueError):
                _compress_results(source, alias)
            self.assertEqual(source.read_bytes(), before)

    def test_publication_cannot_republish_over_its_input(self):
        job = suite.Job(
            "count_sweep", "default", "uniform", n=10, scale=1000, instance=0, seed=0
        )
        with tempfile.TemporaryDirectory(prefix="TMP_bench_") as directory:
            root = Path(directory)
            incoming = root / "input"
            incoming.mkdir()
            (incoming / "manifest.json").write_text(json.dumps(_manifest([job])))
            (incoming / "results.jsonl").write_text(
                json.dumps(_measured_records([job])[0]) + "\n"
            )
            _plot_test_campaign(incoming, root / "plots")
            published = root / "published"
            publish_benchmark(incoming, root / "plots", published)
            before = {p.name: p.read_bytes() for p in published.iterdir()}
            _plot_test_campaign(published, root / "replots")
            with self.assertRaises(FileExistsError):
                publish_benchmark(published, root / "replots", published)
            self.assertEqual(
                {p.name: p.read_bytes() for p in published.iterdir()}, before
            )

    def test_failed_staging_leaves_no_completed_destination(self):
        with tempfile.TemporaryDirectory(prefix="TMP_bench_") as directory:
            destination = Path(directory) / "published"
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                with new_directory(destination) as stage:
                    (stage / "manifest.json").write_text("partial")
                    raise RuntimeError("interrupted")
            self.assertFalse(destination.exists())
            destination.mkdir()
            with self.assertRaises(FileExistsError):
                with new_directory(destination):
                    self.fail("must refuse even an empty existing directory")
            self.assertTrue(destination.is_dir())

    def test_corpus_fingerprints_actual_geometry_and_bounds(self):
        job = suite.Job("structured", "default", "squares", n=3, instance=0)
        cases = corpus.make_cases([job])
        before = corpus.corpus_digest(cases)
        cases[0]["input"]["sizes"][0][0] += 1
        with self.assertRaisesRegex(ValueError, "digest"):
            corpus.validate_cases(cases)
        cases[0]["input_sha256"] = corpus.input_digest(cases[0]["input"])
        self.assertNotEqual(corpus.corpus_digest(cases), before)
        old_input = cases[0]["input_sha256"]
        cases[0]["input"]["max_width"] = 10
        self.assertNotEqual(corpus.input_digest(cases[0]["input"]), old_input)

    def test_export_detects_modified_sources(self):
        with tempfile.TemporaryDirectory(prefix="TMP_bench_") as directory:
            source_root = Path(directory) / "source"
            for name in (
                "setup.py",
                "pyproject.toml",
                "rpack/__init__.py",
                "rpack/_core.pyx",
                "src/rpackcore.c",
            ):
                path = source_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# source fixture\n")
            destination = Path(directory) / "export"
            original = provenance.export_sources(destination, root=source_root)
            self.assertEqual(provenance.identify_source(destination), original)
            path = destination / "rpack/__init__.py"
            path.write_text(path.read_text() + "\n# source mutation\n")
            changed = provenance.identify_source(destination)
            self.assertTrue(changed["git_dirty"])
            self.assertNotEqual(changed["source_sha256"], original["source_sha256"])

    def test_invalid_measurements_are_rejected(self):
        job = suite.Job(
            "count_sweep", "default", "uniform", n=10, scale=1000, instance=0, seed=0
        )
        for field, value in (
            ("time_per_call_ns", -1),
            ("time_per_call_ns", float("nan")),
            ("density", 2),
            ("repeat", 0),
            ("elapsed_ns", 0),
            ("total_area", True),
            ("bbox_height", -1),
        ):
            with self.subTest(field=field, value=value):
                records = _measured_records([job])
                records[0][field] = value
                with self.assertRaises(results.BenchmarkValidationError):
                    results._validate_records(records, _manifest([job]))

    def test_negative_positions_and_bound_violations_are_rejected(self):
        with self.assertRaises(runner.InvalidPackingError):
            runner._validate_positions([(1, 1), (1, 1)], [(-1, 0), (3, 0)], None)
        with self.assertRaises(runner.InvalidPackingError):
            runner._validate_positions([(2, 2)], [(0, 0)], None, max_width=1)

    def test_fallback_routes_and_outcomes_are_observed(self):
        jobs = [
            suite.Job(
                "scale_sweep",
                "default",
                "uniform",
                n=64,
                scale=2**28,
                instance=0,
                seed=7,
            )
        ]
        for family in (
            "bigint_approximate",
            "bounded_exact_grid",
            "bounded_impossible",
        ):
            jobs.append(
                suite.Job(
                    "scenario",
                    "default",
                    family,
                    n=suite.SCENARIO_COUNTS[family],
                    instance=0,
                    seed=7,
                )
            )
        records = [
            runner._measure_case(case, 1_000, 1, 2) for case in corpus.make_cases(jobs)
        ]
        self.assertEqual(records[0]["fallback_path"], "exact_gcd")
        self.assertEqual(records[1]["fallback_path"], "approximate")
        self.assertEqual(records[2]["density"], 1)
        self.assertEqual(records[3]["status"], "infeasible")
        self.assertIsNone(records[3]["density"])
        manifest = _manifest(jobs)
        manifest.update(
            benchmark_schema_version=2,
            workers=1,
            worker_cpus=[0],
            measurement_mode="latency",
            timing_blocks=2,
            target_time_ns=1_000,
            max_repeat=1,
            timeout_seconds=600,
            outcomes={"ok": 3, "infeasible": 1},
        )
        results._validate_records(records, manifest)
        records[0]["timing_blocks_ns"][0] += 10
        with self.assertRaises(results.BenchmarkValidationError):
            results._validate_records(records, manifest)


class TestBenchmarkWorkers(unittest.TestCase):
    def setUp(self):
        self.cases = corpus.make_cases(
            [
                suite.Job("structured", "default", "squares", n=1, instance=i)
                for i in range(2)
            ]
        )
        self.before = {p.pid for p in multiprocessing.active_children()}

    def tearDown(self):
        self.assertEqual(
            {p.pid for p in multiprocessing.active_children()}, self.before
        )

    def test_timeout_kills_worker_and_continues(self):
        started = time.monotonic()
        records = list(
            runner._execute_cases(
                self.cases, [0], 1000, 1, 2, 2, worker_target=_controlled_worker
            )
        )
        self.assertEqual([r["status"] for r in records], ["timeout", "ok"])
        self.assertLess(time.monotonic() - started, 10)

    def test_failure_stops_other_workers_without_waiting(self):
        started = time.monotonic()
        records = list(
            runner._execute_cases(
                self.cases, [0, 1], 1000, 1, 2, 30, worker_target=_failing_worker
            )
        )
        self.assertEqual([r["status"] for r in records], ["error"])
        self.assertLess(time.monotonic() - started, 5)

    def test_native_crash_is_a_failure_not_a_hang(self):
        records = list(
            runner._execute_cases(
                self.cases, [0], 1000, 1, 2, 30, worker_target=_crashing_worker
            )
        )
        self.assertEqual([r["status"] for r in records], ["error"])

    def test_closing_consumer_reaps_workers(self):
        stream = runner._execute_cases(
            self.cases, [0], 1000, 1, 2, 0.5, worker_target=_controlled_worker
        )
        self.assertEqual(next(stream)["status"], "timeout")
        stream.close()

    def test_worker_uses_its_build_even_when_caller_imported_rpack(self):
        import rpack
        import rpack._core

        with tempfile.TemporaryDirectory(prefix="TMP_runtime_") as directory:
            runtime = Path(directory)
            package = runtime / "rpack"
            package.mkdir()
            for path in Path(rpack.__file__).parent.glob("*.py"):
                shutil.copyfile(path, package / path.name)
            native = Path(rpack._core.__file__)
            shutil.copyfile(native, package / native.name)
            with (package / "__init__.py").open("a") as stream:
                stream.write("\ndef pack(sizes, **bounds):\n    return [(1, 1)]\n")
            records = list(
                runner._execute_cases(
                    self.cases[:1],
                    [0],
                    1000,
                    1,
                    2,
                    5,
                    worker_target=_preloaded_worker,
                    runtime_root=runtime,
                )
            )
            self.assertEqual(records[0]["status"], "ok")
            self.assertEqual(records[0]["density"], 0.25)


if __name__ == "__main__":
    unittest.main()
