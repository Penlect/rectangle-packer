"""Load, validate and summarize benchmark evidence without plotting dependencies."""

from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
from json import JSONDecodeError
import math
import random
import statistics
import tarfile
from pathlib import Path
from typing import Any

from benchmark import corpus, suite


class BenchmarkValidationError(ValueError):
    """Raised when benchmark inputs are malformed or incomplete."""


def _load_manifest(input_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchmarkValidationError(f"missing manifest file in {input_dir}") from exc
    except JSONDecodeError as exc:
        raise BenchmarkValidationError(f"failed to parse manifest.json: {exc}") from exc


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_results_content(path: Path) -> str:
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_records(
    input_dir: Path, manifest: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    manifest = manifest or {}
    filename = manifest.get("results_file", "results.jsonl")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise BenchmarkValidationError(f"invalid results filename: {filename!r}")
    path = input_dir / filename
    if not path.exists():
        raise BenchmarkValidationError(f"missing results file at {path}")
    expected_sha256 = manifest.get("results_sha256")
    if expected_sha256 is not None:
        actual_sha256 = _sha256_file(path)
        if actual_sha256 != expected_sha256:
            raise BenchmarkValidationError(
                f"results file digest does not match manifest: "
                f"{actual_sha256} != {expected_sha256}"
            )
    expected_content_sha256 = manifest.get("results_uncompressed_sha256")
    if expected_content_sha256 is not None:
        actual_content_sha256 = _sha256_results_content(path)
        if actual_content_sha256 != expected_content_sha256:
            raise BenchmarkValidationError(
                "uncompressed results digest does not match manifest: "
                f"{actual_content_sha256} != {expected_content_sha256}"
            )

    records: list[dict[str, Any]] = []
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except JSONDecodeError as exc:
                raise BenchmarkValidationError(
                    f"failed to parse results.jsonl line {lineno}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise BenchmarkValidationError(
                    f"results.jsonl line {lineno} did not contain a JSON object"
                )
            records.append(record)
    return records


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        raise BenchmarkValidationError("cannot summarize an empty sample set")
    data = sorted(float(value) for value in values)

    def quantile(fraction: float) -> float:
        # Match NumPy's default linear interpolation without requiring NumPy
        # in validation-only and wheel-test environments.
        position = (len(data) - 1) * fraction
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return data[low]
        weight = position - low
        return data[low] * (1.0 - weight) + data[high] * weight

    return {
        "min": data[0],
        "p10": quantile(0.10),
        "median": quantile(0.50),
        "p90": quantile(0.90),
        "max": data[-1],
    }


def _fit_power_law(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2:
        return None
    x = [math.log(value) for value in x_values]
    y = [math.log(value) for value in y_values]
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    denominator = sum((value - x_mean) ** 2 for value in x)
    if denominator == 0:
        return None
    return (
        sum((x_value - x_mean) * (y_value - y_mean) for x_value, y_value in zip(x, y))
        / denominator
    )


def _format_job_key(key: tuple[object, ...]) -> str:
    return ", ".join(
        f"{field}={value!r}" for field, value in zip(suite.JOB_KEY_FIELDS, key)
    )


def _example_lines(lines: list[int]) -> str:
    head = ", ".join(str(line) for line in lines[:3])
    if len(lines) > 3:
        head += ", ..."
    return head


def _validate_records(records: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    status = manifest.get("status")
    if status != "complete":
        raise BenchmarkValidationError(
            f"manifest status is {status!r}; expected 'complete' before plotting"
        )
    schema_version = manifest.get("benchmark_schema_version")
    if type(schema_version) is not int or schema_version not in (1, 2):
        raise BenchmarkValidationError(
            f"unsupported benchmark schema {schema_version!r}; "
            "supported versions are 1 and 2"
        )
    if schema_version == 2:
        _validate_configuration(manifest)
    algorithm_names = manifest.get("algorithms")
    if not isinstance(algorithm_names, list) or not algorithm_names:
        raise BenchmarkValidationError(
            "manifest does not define a non-empty algorithm list"
        )
    if any(not isinstance(name, str) or not name for name in algorithm_names):
        raise BenchmarkValidationError("manifest algorithms must be nonempty strings")
    if len(algorithm_names) != len(set(algorithm_names)):
        raise BenchmarkValidationError("manifest algorithm names must be unique")

    actual_keys: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for lineno, record in enumerate(records, start=1):
        try:
            key = suite.record_key(record)
        except ValueError as exc:
            raise BenchmarkValidationError(
                f"results.jsonl line {lineno}: {exc}"
            ) from exc
        actual_keys[key].append(lineno)

    manifest_expected = manifest.get("expected_job_count")
    if type(manifest_expected) is not int or manifest_expected <= 0:
        raise BenchmarkValidationError(
            f"manifest expected job count is invalid: {manifest_expected!r}"
        )
    manifest_completed = manifest.get("completed_job_count")
    if type(manifest_completed) is not int or manifest_completed < 0:
        raise BenchmarkValidationError("invalid completed job count")
    expected_digest = manifest.get("job_grid_sha256")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise BenchmarkValidationError(
            f"manifest job-grid digest is invalid: {expected_digest!r}"
        )

    duplicate_keys = {
        key: lines for key, lines in actual_keys.items() if len(lines) > 1
    }
    actual_digest = suite.job_grid_sha256(actual_keys)

    count_matches = manifest_expected == len(records)
    completed_matches = manifest_completed == len(records)
    digest_matches = expected_digest == actual_digest
    if not duplicate_keys and count_matches and completed_matches and digest_matches:
        for lineno, record in enumerate(records, 1):
            try:
                _validate_measurement(record, manifest)
            except (KeyError, TypeError, ValueError) as exc:
                raise BenchmarkValidationError(
                    f"invalid measurement at line {lineno}: {exc}"
                ) from exc
        if schema_version == 2:
            if dict(Counter(r["status"] for r in records)) != manifest.get("outcomes"):
                raise BenchmarkValidationError(
                    "manifest outcome counts do not match measurements"
                )
        return

    # When the current suite still describes this run, retain precise missing
    # and extra job diagnostics. The manifest digest remains authoritative so
    # historical runs do not become invalid merely because the suite evolves.
    expected_keys: set[tuple[object, ...]] | None = None
    profile_name = manifest.get("profile")
    if profile_name in suite.PROFILES:
        current_jobs = suite.build_jobs(suite.PROFILES[profile_name], algorithm_names)
        current_keys = {suite.job_key(job) for job in current_jobs}
        if suite.job_grid_sha256(current_keys) == expected_digest:
            expected_keys = current_keys

    missing_keys = sorted(expected_keys - actual_keys.keys()) if expected_keys else []
    extra_keys = sorted(actual_keys.keys() - expected_keys) if expected_keys else []

    message = ["benchmark results failed validation:"]
    if not count_matches:
        message.append(
            "- expected job count does not match results.jsonl line count: "
            f"{manifest_expected} != {len(records)}"
        )
    if not completed_matches:
        message.append(
            "- completed job count does not match results.jsonl line count: "
            f"{manifest_completed!r} != {len(records)}"
        )
    if not digest_matches:
        message.append(
            f"- job-grid digest does not match manifest: {actual_digest} != {expected_digest}"
        )
    if missing_keys:
        message.append(f"- missing {len(missing_keys)} expected record(s)")
        for key in missing_keys[:5]:
            message.append(f"  { _format_job_key(key) }")
    if extra_keys:
        message.append(f"- found {len(extra_keys)} unexpected record(s)")
        for key in extra_keys[:5]:
            message.append(f"  { _format_job_key(key) }")
    if duplicate_keys:
        message.append(f"- found {len(duplicate_keys)} duplicated record key(s)")
        for key, lines in list(duplicate_keys.items())[:5]:
            message.append(f"  {_format_job_key(key)} at lines {_example_lines(lines)}")
    raise BenchmarkValidationError("\n".join(message))


def _select_algorithms(
    manifest: dict[str, Any], requested_algorithms: list[str] | None
) -> list[str]:
    available = manifest["algorithms"]
    if not requested_algorithms:
        return available
    unknown = sorted(set(requested_algorithms) - set(available))
    if unknown:
        raise BenchmarkValidationError(
            "requested algorithm(s) are not present in the benchmark results: "
            + ", ".join(unknown)
        )
    return [algorithm for algorithm in available if algorithm in requested_algorithms]


def _filter_records(
    records: list[dict[str, Any]], algorithm_names: list[str]
) -> list[dict[str, Any]]:
    selected = set(algorithm_names)
    return [record for record in records if record["algorithm"] in selected]


def _family_label(family: str) -> str:
    definition = suite.RANDOM_FAMILIES.get(family)
    if definition is not None:
        return definition.label
    return family.replace("_", " ").title()


def _family_description(family: str) -> str | None:
    definition = suite.RANDOM_FAMILIES.get(family)
    return definition.description if definition is not None else None


def _ordered_families(families: set[str], preferred: tuple[str, ...]) -> list[str]:
    """Return known families in display order followed by historical additions."""
    ordered = [family for family in preferred if family in families]
    ordered.extend(sorted(families - set(ordered)))
    return ordered


def _summarize_count_sweep(
    records: list[dict[str, Any]], algorithm_names: list[str]
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["benchmark"] == "count_sweep":
            grouped[(record["algorithm"], record["family"], record["n"])].append(record)

    summary: dict[str, Any] = {}
    for algorithm in algorithm_names:
        family_summary: dict[str, Any] = {}
        families = {
            family
            for record_algorithm, family, _ in grouped
            if record_algorithm == algorithm
        }
        for family in _ordered_families(families, suite.COUNT_SWEEP_FAMILIES):
            points = []
            n_values = sorted(
                n
                for record_algorithm, record_family, n in grouped
                if record_algorithm == algorithm and record_family == family
            )
            for n in n_values:
                samples = grouped[(algorithm, family, n)]
                points.append(
                    {
                        "n": n,
                        "time_seconds": _quantiles(
                            [sample["time_per_call_ns"] / 1e9 for sample in samples]
                        ),
                        "density": _quantiles(
                            [sample["density"] for sample in samples]
                        ),
                        "count": len(samples),
                    }
                )
            slope_points = [point for point in points if point["n"] >= 40]
            family_summary[family] = {
                "label": _family_label(family),
                "description": _family_description(family),
                "variation_basis": "different generated input instances",
                "power_law_exponent": _fit_power_law(
                    [point["n"] for point in slope_points],
                    [point["time_seconds"]["median"] for point in slope_points],
                ),
                "points": points,
            }
        summary[algorithm] = family_summary
    return summary


def _summarize_scale_sweep(
    records: list[dict[str, Any]], algorithm_names: list[str]
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["benchmark"] == "scale_sweep":
            grouped[(record["algorithm"], record["family"], record["scale"])].append(
                record
            )

    summary: dict[str, Any] = {}
    for algorithm in algorithm_names:
        family_summary: dict[str, Any] = {}
        families = {
            family
            for record_algorithm, family, _ in grouped
            if record_algorithm == algorithm
        }
        for family in _ordered_families(families, suite.SCALE_SWEEP_FAMILIES):
            points = []
            scale_values = sorted(
                scale
                for record_algorithm, record_family, scale in grouped
                if record_algorithm == algorithm and record_family == family
            )
            baseline_scale = scale_values[0]
            baseline_by_instance = {
                sample["instance"]: sample["time_per_call_ns"]
                for sample in grouped[(algorithm, family, baseline_scale)]
            }
            for scale in scale_values:
                samples = grouped[(algorithm, family, scale)]
                fallback_share = sum(
                    sample["used_bigint_fallback"] for sample in samples
                ) / len(samples)
                relative_times = [
                    sample["time_per_call_ns"]
                    / baseline_by_instance[sample["instance"]]
                    for sample in samples
                    if sample["instance"] in baseline_by_instance
                ]
                points.append(
                    {
                        "scale": scale,
                        "time_seconds": _quantiles(
                            [sample["time_per_call_ns"] / 1e9 for sample in samples]
                        ),
                        "density": _quantiles(
                            [sample["density"] for sample in samples]
                        ),
                        "relative_time": (
                            _quantiles(relative_times) if relative_times else None
                        ),
                        "fallback_share": fallback_share,
                        "count": len(samples),
                    }
                )
            family_summary[family] = {
                "label": _family_label(family),
                "description": _family_description(family),
                "variation_basis": (
                    "matched generated instances; relative time is paired to "
                    f"scale {baseline_scale}"
                ),
                "baseline_scale": baseline_scale,
                "points": points,
            }
        summary[algorithm] = family_summary
    return summary


def _summarize_structured(
    records: list[dict[str, Any]], algorithm_names: list[str]
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["benchmark"] == "structured":
            grouped[(record["algorithm"], record["family"], record["n"])].append(record)

    summary: dict[str, Any] = {}
    for algorithm in algorithm_names:
        family_summary: dict[str, Any] = {}
        families = {
            family
            for record_algorithm, family, _ in grouped
            if record_algorithm == algorithm
        }
        for family in _ordered_families(families, ("squares", "fixed_perimeter")):
            points = []
            n_values = sorted(
                n
                for record_algorithm, record_family, n in grouped
                if record_algorithm == algorithm and record_family == family
            )
            for n in n_values:
                samples = grouped[(algorithm, family, n)]
                points.append(
                    {
                        "n": n,
                        "time_seconds": _quantiles(
                            [sample["time_per_call_ns"] / 1e9 for sample in samples]
                        ),
                        "density": _quantiles(
                            [sample["density"] for sample in samples]
                        ),
                        "count": len(samples),
                    }
                )
            family_summary[family] = {
                "label": _family_label(family),
                "variation_basis": "repeated timing blocks for one fixed input",
                "points": points,
            }
        summary[algorithm] = family_summary
    return summary


def _summarize_pathology(
    records: list[dict[str, Any]], algorithm_names: list[str]
) -> dict[str, Any]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    guardrails: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["benchmark"] != "pathology":
            continue
        if record["family"] == "thin_pathology":
            grouped[(record["algorithm"], record["parameter"])].append(record)
        elif record["family"] == "pathology_guardrail":
            guardrails[record["algorithm"]].append(record)

    summary: dict[str, Any] = {}
    for algorithm in algorithm_names:
        heights = sorted(
            height
            for record_algorithm, height in grouped
            if record_algorithm == algorithm
        )
        pathology_points = [
            {
                "height": height,
                "time_seconds": _quantiles(
                    [
                        sample["time_per_call_ns"] / 1e9
                        for sample in grouped[(algorithm, height)]
                    ]
                ),
                "density": _quantiles(
                    [sample["density"] for sample in grouped[(algorithm, height)]]
                ),
                "count": len(grouped[(algorithm, height)]),
            }
            for height in heights
        ]
        guardrail_samples = guardrails[algorithm]
        if not pathology_points and not guardrail_samples:
            continue
        summary[algorithm] = {
            "thin_pathology": pathology_points,
            "thin_pathology_variation_basis": (
                "repeated timing blocks for one fixed input"
            ),
            "guardrail": (
                {
                    "label": "Uniform random reference",
                    "variation_basis": "different generated input instances",
                    "time_seconds": _quantiles(
                        [
                            sample["time_per_call_ns"] / 1e9
                            for sample in guardrail_samples
                        ]
                    ),
                    "density": _quantiles(
                        [sample["density"] for sample in guardrail_samples]
                    ),
                    "count": len(guardrail_samples),
                }
                if guardrail_samples
                else None
            ),
        }
    return summary


def _build_summary(records, manifest, algorithm_names):
    successful = [r for r in records if r.get("status", "ok") == "ok"]
    summary = {
        "manifest": manifest,
        "selected_algorithms": algorithm_names,
        "validated_record_count": len(records),
        "count_sweep": _summarize_count_sweep(successful, algorithm_names),
        "scale_sweep": _summarize_scale_sweep(successful, algorithm_names),
        "structured": _summarize_structured(successful, algorithm_names),
        "pathology": _summarize_pathology(successful, algorithm_names),
    }
    if manifest["benchmark_schema_version"] == 2:
        summary["workloads"] = summarize_workloads(records)
        summary["outcomes"] = dict(Counter(r["status"] for r in records))
    return summary


def _positive(value, name, integer=False):
    if (
        type(value) not in ((int,) if integer else (int, float))
        or (type(value) is float and not math.isfinite(value))
        or value <= 0
    ):
        raise ValueError(f"{name} must be finite and positive")


def _digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("invalid SHA-256 digest")


def _validate_configuration(manifest):
    try:
        for name in ("workers", "timing_blocks", "target_time_ns", "max_repeat"):
            _positive(manifest[name], name, integer=True)
        _positive(manifest["timeout_seconds"], "timeout_seconds")
        if manifest["timing_blocks"] < 2:
            raise ValueError("at least two timing blocks are required")
        cpus = manifest["worker_cpus"]
        if (
            not isinstance(cpus, list)
            or len(cpus) != manifest["workers"]
            or any(type(cpu) is not int or cpu < 0 for cpu in cpus)
            or len(set(cpus)) != len(cpus)
        ):
            raise ValueError("invalid worker CPU assignments")
        mode = "latency" if manifest["workers"] == 1 else "concurrent"
        if manifest["measurement_mode"] != mode:
            raise ValueError("measurement mode disagrees with worker count")
    except (KeyError, TypeError, ValueError) as exc:
        raise BenchmarkValidationError(
            f"invalid measurement configuration: {exc}"
        ) from exc


def _validate_measurement(record: dict, manifest: dict) -> None:
    if record["algorithm"] not in manifest["algorithms"]:
        raise ValueError("record algorithm is absent from manifest")
    for key in ("benchmark", "family", "algorithm"):
        if not isinstance(record[key], str) or not record[key]:
            raise ValueError(f"invalid {key}")
    _positive(record["n"], "n", integer=True)
    for name in ("scale", "parameter", "instance", "seed"):
        value = record[name]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"invalid job identity field {name}")
    schema = manifest["benchmark_schema_version"]
    status = record.get("status", "ok") if schema == 1 else record["status"]
    if status not in ("ok", "infeasible", "timeout"):
        raise ValueError("completed campaigns cannot contain unknown or error outcomes")
    if schema == 2:
        _digest(record["input_sha256"])
        if (
            record.get("worker_cpu") is not None
            and record["worker_cpu"] not in manifest["worker_cpus"]
        ):
            raise ValueError("recorded CPU is absent from the worker assignments")
    if status == "timeout":
        _positive(record["timeout_seconds"], "timeout_seconds")
        if record["timeout_seconds"] != manifest["timeout_seconds"]:
            raise ValueError("timeout does not match manifest")
        if any(
            record.get(key) is not None
            for key in ("time_per_call_ns", "density", "bbox_width", "bbox_height")
        ):
            raise ValueError(
                "timeouts must not masquerade as measured timings or packings"
            )
        return
    _positive(record["time_per_call_ns"], "time_per_call_ns")
    _positive(record["repeat"], "repeat", integer=True)
    _positive(record["elapsed_ns"], "elapsed_ns", integer=True)
    _positive(record["total_area"], "total_area", integer=True)
    if schema == 2:
        if record["repeat"] > manifest["max_repeat"]:
            raise ValueError("repeat count exceeds manifest limit")
        blocks = record["timing_blocks_ns"]
        if not isinstance(blocks, list) or len(blocks) != manifest["timing_blocks"]:
            raise ValueError("timing block count does not match manifest")
        for block in blocks:
            _positive(block, "timing block", integer=True)
        if sum(blocks) != record["elapsed_ns"]:
            raise ValueError("elapsed_ns does not equal the sum of timing blocks")
        expected_time = statistics.median(blocks) / record["repeat"]
        if record["fallback_path"] not in ("native", "exact_gcd", "approximate"):
            raise ValueError("invalid fallback path")
        if record["used_bigint_fallback"] is not (record["fallback_path"] != "native"):
            raise ValueError("fallback flag disagrees with observed route")
    else:
        expected_time = record["elapsed_ns"] / record["repeat"]
    if not math.isclose(record["time_per_call_ns"], expected_time, rel_tol=1e-12):
        raise ValueError("per-call timing does not match raw timings and repeat count")
    if status == "ok":
        _positive(record["bbox_width"], "bbox_width", integer=True)
        _positive(record["bbox_height"], "bbox_height", integer=True)
        _positive(record["density"], "density")
        density = record["total_area"] / (record["bbox_width"] * record["bbox_height"])
        if (
            record["density"] > 1
            or density > 1
            or not math.isclose(density, record["density"], rel_tol=1e-12)
        ):
            raise ValueError("density does not match the recorded areas")
    elif any(
        record.get(key) is not None for key in ("density", "bbox_width", "bbox_height")
    ):
        raise ValueError("infeasible packings cannot have complete-packing geometry")
    if (
        record["benchmark"] == "scale_sweep"
        and type(record["used_bigint_fallback"]) is not bool
    ):
        raise ValueError("fallback flag must be boolean")


def load_campaign(directory: Path):
    """Verify measurements and, for schema 2, their exact inputs and build evidence."""
    manifest = _load_manifest(directory)
    records = _load_records(directory, manifest)
    _validate_records(records, manifest)
    if manifest["benchmark_schema_version"] == 1:
        return manifest, records
    for filename, digest in (
        ("corpus.jsonl.gz", manifest["corpus_file_sha256"]),
        ("source.tar.gz", manifest["source_archive_sha256"]),
    ):
        if _sha256_file(directory / filename) != digest:
            raise BenchmarkValidationError(f"{filename} digest does not match manifest")
    if manifest["corpus_file"] != "corpus.jsonl.gz":
        raise BenchmarkValidationError("unsupported corpus filename")
    cases = corpus.load_cases(directory / "corpus.jsonl.gz")
    if corpus.corpus_digest(cases) != manifest["corpus_sha256"]:
        raise BenchmarkValidationError("corpus digest does not match manifest")
    by_key = {suite.record_key(case["job"]): case for case in cases}
    if set(by_key) != {suite.record_key(record) for record in records}:
        raise BenchmarkValidationError("corpus jobs do not match measurements")
    for record in records:
        case = by_key[suite.record_key(record)]
        if case["input_sha256"] != record["input_sha256"]:
            raise BenchmarkValidationError(
                "measurement input does not match frozen corpus"
            )
        if record["status"] == "timeout":
            continue
        workload = case["input"]
        if record["status"] != workload["expected_status"]:
            raise BenchmarkValidationError(
                "packing outcome does not match workload expectation"
            )
        if record["total_area"] != sum(w * h for w, h in workload["sizes"]):
            raise BenchmarkValidationError(
                "recorded area does not match input rectangles"
            )
        if record["status"] == "ok":
            for axis in ("width", "height"):
                bound = workload["max_" + axis]
                if bound is not None and record["bbox_" + axis] > bound:
                    raise BenchmarkValidationError(
                        "recorded bounding box exceeds input constraints"
                    )
    verify_source_archive(directory / "source.tar.gz", manifest["source"])
    build = manifest.get("build")
    if build is not None:
        if (
            build["log_file"] != "build.log"
            or _sha256_file(directory / "build.log") != build["log_sha256"]
        ):
            raise BenchmarkValidationError("build log digest does not match manifest")
    _digest(manifest["extension_sha256"])
    return manifest, records


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_median_interval(values, seed=0, resamples=1000):
    """Percentile bootstrap across independent inputs, not calls within an input."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    medians = [
        statistics.median(rng.choices(values, k=len(values))) for _ in range(resamples)
    ]
    return [percentile(medians, 0.025), percentile(medians, 0.975)]


def sample_statistics(values, seed=0, *, bootstrap=True):
    if not values:
        return None
    return {
        "count": len(values),
        "min": min(values),
        "p10": percentile(values, 0.1),
        "median": statistics.median(values),
        "p90": percentile(values, 0.9),
        "p95": percentile(values, 0.95),
        "max": max(values),
        "median_ci95": bootstrap_median_interval(values, seed) if bootstrap else None,
    }


def summarize_workloads(records):
    fields = ("benchmark", "algorithm", "family", "n", "scale", "parameter")
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[name] for name in fields)].append(record)
    summary = []
    for key, samples in sorted(groups.items(), key=lambda item: repr(item[0])):
        timed = [r for r in samples if r["status"] != "timeout"]
        successful = [r for r in timed if r["status"] == "ok"]
        # A corpus can intentionally repeat deterministic fixtures. Such copies
        # must not inflate the number of independent observations in an interval.
        by_input = defaultdict(list)
        for record in timed:
            by_input[record["input_sha256"]].append(record["time_per_call_ns"] / 1e9)
        values = [statistics.median(times) for times in by_input.values()]
        densities = defaultdict(list)
        for record in successful:
            densities[record["input_sha256"]].append(record["density"])
        density_values = [statistics.median(values) for values in densities.values()]
        repeat_spreads = [
            percentile(r["timing_blocks_ns"], 0.9)
            / percentile(r["timing_blocks_ns"], 0.1)
            for r in timed
        ]
        summary.append(
            {
                **dict(zip(fields, key)),
                "jobs": len(samples),
                "distinct_inputs": len({r["input_sha256"] for r in samples}),
                "outcomes": dict(Counter(r["status"] for r in samples)),
                "time_seconds": sample_statistics(values, suite.stable_seed(*key)),
                "density": sample_statistics(
                    density_values,
                    suite.stable_seed("density", *key),
                ),
                "median_within_input_p90_p10_ratio": (
                    statistics.median(repeat_spreads) if repeat_spreads else None
                ),
                "fallback_paths": dict(Counter(r["fallback_path"] for r in timed)),
            }
        )
    return summary


def verify_source_archive(path: Path, source: dict) -> None:
    from benchmark.provenance import _library_file

    files = source["files"]
    if hashlib.sha256(corpus.canonical(files)).hexdigest() != source["source_sha256"]:
        raise BenchmarkValidationError("source file list digest is incorrect")
    library_files = {
        name: digest for name, digest in files.items() if _library_file(name)
    }
    if (
        hashlib.sha256(corpus.canonical(library_files)).hexdigest()
        != source["library_source_sha256"]
    ):
        raise BenchmarkValidationError("library source digest is incorrect")
    with tarfile.open(path) as archive:
        actual = {
            entry.name: hashlib.sha256(archive.extractfile(entry).read()).hexdigest()
            for entry in archive.getmembers()
            if entry.isfile() and entry.name != "benchmark-source.json"
        }
        if "benchmark-source.json" in archive.getnames():
            if json.load(archive.extractfile("benchmark-source.json")) != source:
                raise BenchmarkValidationError(
                    "archived source identity differs from manifest"
                )
    if actual != files:
        raise BenchmarkValidationError(
            "source archive differs from recorded source files"
        )


def verify_plot_source(directory: Path, binding: dict) -> None:
    version = binding.get("plot_schema_version")
    if version not in (1, 2):
        raise BenchmarkValidationError("unsupported plot manifest; regenerate plots")
    if version == 2:
        path = directory / "plot-source.tar.gz"
        if _sha256_file(path) != binding["plot_source_archive_sha256"]:
            raise BenchmarkValidationError(
                "plot source archive digest does not match manifest"
            )
        verify_source_archive(path, binding["plot_source"])
