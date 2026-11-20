"""Create small synthetic campaigns with valid geometry and explicit test build evidence."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmark import corpus, provenance, runner, suite
from benchmark.storage import sha256_file, write_json


def make_campaign(directory: Path, factor=1, *, seed_offset=0, timeout=False):
    directory.mkdir()
    jobs = [
        suite.Job(
            "count_sweep",
            "default",
            "uniform",
            n=3,
            scale=10,
            instance=i,
            seed=i + seed_offset,
        )
        for i in range(3)
    ]
    cases = corpus.make_cases(jobs)
    records = [runner._measure_case(case, 1000, 1, 3) for case in cases]
    for index, record in enumerate(records, 1):
        blocks = [factor * index * value for value in (900, 1000, 1100)]
        record.update(
            repeat=1,
            timing_blocks_ns=blocks,
            elapsed_ns=sum(blocks),
            time_per_call_ns=float(blocks[1]),
        )
    if timeout:
        records[0] = {
            **cases[0]["job"],
            "input_sha256": cases[0]["input_sha256"],
            "status": "timeout",
            "timeout_seconds": 10,
            "worker_cpu": 0,
        }
    corpus.write_cases(directory / "corpus.jsonl.gz", cases)
    source = provenance.identify_source()
    provenance.source_archive(directory / "source.tar.gz", source)
    (directory / "build.log").write_text("Synthetic fixture: no compiler invocation.\n")
    (directory / "results.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )
    manifest = {
        "benchmark_schema_version": 2,
        "status": "complete",
        "profile": "fixture",
        "algorithms": ["default"],
        "expected_job_count": len(jobs),
        "completed_job_count": len(jobs),
        "job_grid_sha256": suite.job_grid_sha256(suite.job_key(job) for job in jobs),
        "corpus_sha256": corpus.corpus_digest(cases),
        "corpus_file": "corpus.jsonl.gz",
        "corpus_file_sha256": sha256_file(directory / "corpus.jsonl.gz"),
        "source": source,
        "source_archive_sha256": sha256_file(directory / "source.tar.gz"),
        "extension_sha256": hashlib.sha256(b"synthetic extension identity").hexdigest(),
        "build": {
            "log_file": "build.log",
            "log_sha256": sha256_file(directory / "build.log"),
            "environment": {},
            "package_versions": {},
        },
        "results_file": "results.jsonl",
        "results_sha256": sha256_file(directory / "results.jsonl"),
        "results_uncompressed_sha256": sha256_file(directory / "results.jsonl"),
        "outcomes": dict(Counter(record["status"] for record in records)),
        "timing_blocks": 3,
        "target_time_ns": 1000,
        "max_repeat": 1,
        "timeout_seconds": 10,
        "hostname": "test-host",
        "machine_label": "test-machine",
        "platform": "test platform",
        "cpu_model": "test CPU",
        "cpu_governors": ["test"],
        "python_version": "3.13",
        "rpack_version": "fixture",
        "measurement_mode": "latency",
        "workers": 1,
        "worker_cpus": [0],
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "finished_timestamp_utc": "2026-01-01T00:00:10Z",
        "measurement_seconds": 10,
    }
    write_json(directory / "manifest.json", manifest)
    return manifest, records, cases
