"""Store exact benchmark inputs independently of the generator and packing revision."""

from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

from benchmark import suite


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def input_digest(workload: dict) -> str:
    return hashlib.sha256(canonical(workload)).hexdigest()


def corpus_digest(cases: list[dict]) -> str:
    identities = sorted(
        canonical({"job": c["job"], "input_sha256": c["input_sha256"]}) for c in cases
    )
    return hashlib.sha256(b"\n".join(identities) + b"\n").hexdigest()


def make_cases(jobs: list[suite.Job]) -> list[dict]:
    cases = []
    for job in jobs:
        workload = suite.generate_input(job)
        cases.append(
            {
                "job": asdict(job),
                "input": workload,
                "input_sha256": input_digest(workload),
            }
        )
    return cases


def validate_cases(cases: list[dict]) -> None:
    if not cases:
        raise ValueError("benchmark corpus is empty")
    keys = set()
    for case in cases:
        job = suite.Job(**case["job"])
        key = suite.job_key(job)
        if key in keys:
            raise ValueError("duplicate job in benchmark corpus")
        keys.add(key)
        workload = case["input"]
        if set(workload) != {"sizes", "max_width", "max_height", "expected_status"}:
            raise ValueError("invalid workload fields")
        sizes = workload["sizes"]
        if not isinstance(sizes, list) or not sizes or len(sizes) != job.n:
            raise ValueError("corpus rectangle count does not match job")
        if any(
            not isinstance(size, list)
            or len(size) != 2
            or any(type(side) is not int or side <= 0 for side in size)
            for size in sizes
        ):
            raise ValueError("corpus sides must be positive integers")
        for name in ("max_width", "max_height"):
            bound = workload[name]
            if bound is not None and (type(bound) is not int or bound < 0):
                raise ValueError("corpus bounds must be nonnegative integers or null")
        if workload["expected_status"] not in ("ok", "infeasible"):
            raise ValueError("invalid expected packing outcome")
        if input_digest(workload) != case["input_sha256"]:
            raise ValueError(
                "corpus input digest does not match its rectangles and bounds"
            )


def write_cases(path: Path, cases: list[dict]) -> None:
    validate_cases(cases)
    with path.open("xb") as output:
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=output) as stream:
            for case in cases:
                stream.write(canonical(case) + b"\n")


def load_cases(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        cases = [json.loads(line) for line in stream if line.strip()]
    validate_cases(cases)
    return cases
