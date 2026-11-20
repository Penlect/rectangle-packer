"""Compare complete campaigns using identical frozen inputs and explicit environments."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

from benchmark import suite
from benchmark.results import load_campaign, sample_statistics
from benchmark.storage import new_directory, write_json

GROUP_FIELDS = ("benchmark", "algorithm", "family", "n", "scale", "parameter")
ENVIRONMENT_FIELDS = (
    "machine_label",
    "platform",
    "cpu_model",
    "cpu_governors",
    "python_version",
    "measurement_mode",
    "workers",
    "worker_cpus",
    "timing_blocks",
    "target_time_ns",
    "max_repeat",
    "timeout_seconds",
)


def _group_summary(rows, identity, *, bootstrap=True):
    by_input = defaultdict(list)
    for row in rows:
        by_input[row["input_sha256"]].append(row)
    timings, areas, densities = [], [], []
    for repeated in by_input.values():
        for field, values in (
            ("runtime_ratio", timings),
            ("area_ratio", areas),
            ("density_change", densities),
        ):
            measured = [row[field] for row in repeated if row[field] is not None]
            if measured:
                values.append(statistics.median(measured))
    return {
        "jobs": len(rows),
        "distinct_inputs": len(by_input),
        "outcome_pairs": dict(
            Counter(
                row["baseline_status"] + " -> " + row["candidate_status"]
                for row in rows
            )
        ),
        "runtime_ratio": sample_statistics(
            timings, suite.stable_seed("time", identity), bootstrap=bootstrap
        ),
        "area_ratio": sample_statistics(
            areas, suite.stable_seed("area", identity), bootstrap=bootstrap
        ),
        "density_change": sample_statistics(
            densities, suite.stable_seed("density", identity), bootstrap=bootstrap
        ),
        "inputs_over_5_percent_slower": sum(ratio > 1.05 for ratio in timings),
        "inputs_with_larger_area": sum(ratio > 1 for ratio in areas),
    }


def compare_campaigns(
    baseline_dir: Path,
    candidate_dir: Path,
    output_dir: Path,
    *,
    allow_environment_change=False,
) -> dict:
    baseline, baseline_records = load_campaign(baseline_dir)
    candidate, candidate_records = load_campaign(candidate_dir)
    if any(m["benchmark_schema_version"] != 2 for m in (baseline, candidate)):
        raise ValueError("revision comparison requires schema-2 frozen input corpora")
    if baseline["corpus_sha256"] != candidate["corpus_sha256"]:
        raise ValueError(
            "input corpora differ; rerun the candidate with --corpus from the baseline"
        )
    differences = {
        name: {"baseline": baseline.get(name), "candidate": candidate.get(name)}
        for name in ENVIRONMENT_FIELDS
        if baseline.get(name) != candidate.get(name)
    }
    if not baseline.get("machine_label") or not candidate.get("machine_label"):
        differences["machine_identity"] = {
            "baseline": "unverified",
            "candidate": "unverified",
        }
    # Build flags are part of the comparison conditions; binary hashes and source
    # revisions are intentionally allowed to differ between candidates.
    for name in ("environment", "package_versions", "compiler"):
        a, b = (m.get("build") or {} for m in (baseline, candidate))
        if a.get(name) != b.get(name):
            differences["build." + name] = {
                "baseline": a.get(name),
                "candidate": b.get(name),
            }
    if differences and not allow_environment_change:
        raise ValueError(
            "comparison conditions differ: "
            + ", ".join(differences)
            + "; use --allow-environment-change for an explicitly uncontrolled comparison"
        )
    left = {suite.record_key(record): record for record in baseline_records}
    right = {suite.record_key(record): record for record in candidate_records}
    if left.keys() != right.keys():
        raise ValueError("campaign job identities differ")
    rows = []
    groups = defaultdict(list)
    for key in sorted(left, key=repr):
        a, b = left[key], right[key]
        if a["input_sha256"] != b["input_sha256"]:
            raise ValueError("matched job has different rectangle or constraint data")
        row = {field: a[field] for field in suite.JOB_KEY_FIELDS}
        row.update(
            input_sha256=a["input_sha256"],
            baseline_status=a["status"],
            candidate_status=b["status"],
            runtime_ratio=None,
            area_ratio=None,
            density_change=None,
            baseline_seconds=None,
            candidate_seconds=None,
        )
        if a["status"] == b["status"] and a["status"] != "timeout":
            row.update(
                runtime_ratio=b["time_per_call_ns"] / a["time_per_call_ns"],
                baseline_seconds=a["time_per_call_ns"] / 1e9,
                candidate_seconds=b["time_per_call_ns"] / 1e9,
            )
        if a["status"] == b["status"] == "ok":
            row.update(
                area_ratio=(b["bbox_width"] * b["bbox_height"])
                / (a["bbox_width"] * a["bbox_height"]),
                density_change=b["density"] - a["density"],
            )
        rows.append(row)
        groups[tuple(a[field] for field in GROUP_FIELDS)].append(row)
    summary = {
        "comparison_schema_version": 1,
        "baseline": {
            "source": baseline["source"],
            "extension_sha256": baseline["extension_sha256"],
            "results_sha256": baseline["results_uncompressed_sha256"],
        },
        "candidate": {
            "source": candidate["source"],
            "extension_sha256": candidate["extension_sha256"],
            "results_sha256": candidate["results_uncompressed_sha256"],
        },
        "corpus_sha256": baseline["corpus_sha256"],
        "controlled_conditions": not differences,
        "condition_differences": differences,
        "same_library_source": baseline["source"]["library_source_sha256"]
        == candidate["source"]["library_source_sha256"],
        # Different scales share a base geometry, and fixed fixtures are not
        # random samples. Describe this mixture without an iid bootstrap CI.
        "overall": _group_summary(rows, "overall", bootstrap=False),
        "overall_interval_basis": "none: mixed fixed and correlated workload families",
        "groups": [
            {**dict(zip(GROUP_FIELDS, key)), **_group_summary(group, repr(key))}
            for key, group in sorted(groups.items(), key=lambda item: repr(item[0]))
        ],
        "outcome_changes": [
            row for row in rows if row["baseline_status"] != row["candidate_status"]
        ],
        "largest_slowdowns": sorted(
            (row for row in rows if row["runtime_ratio"] is not None),
            key=lambda row: row["runtime_ratio"],
            reverse=True,
        )[:20],
        "largest_area_increases": sorted(
            (
                row
                for row in rows
                if row["area_ratio"] is not None and row["area_ratio"] > 1
            ),
            key=lambda row: row["area_ratio"],
            reverse=True,
        )[:20],
    }
    from benchmark.report import comparison_report

    with new_directory(output_dir) as staging:
        write_json(staging / "comparison.json", summary)
        with (staging / "paired-results.jsonl").open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        (staging / "report.rst").write_text(
            comparison_report(summary), encoding="utf-8"
        )
    print(f"Comparison written to {output_dir}")
    return summary
