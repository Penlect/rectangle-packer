"""Generate documentation from verified campaigns and matched revision comparisons."""

from __future__ import annotations

import json
import os
from pathlib import Path

from benchmark.plot import PLOT_STEMS
from benchmark.results import (
    _build_summary,
    _sha256_file,
    load_campaign,
    verify_plot_source,
)


def duration(seconds):
    if seconds is None:
        return "—"
    for limit, multiplier, unit in (
        (1e-6, 1e9, "ns"),
        (1e-3, 1e6, "µs"),
        (1, 1e3, "ms"),
    ):
        if seconds < limit:
            return f"{seconds * multiplier:.3g} {unit}"
    return f"{seconds:.3g} s"


def _percent(value):
    return "—" if value is None else f"{value * 100:.2f}%"


def _heading(title, marker="="):
    return title + "\n" + marker * len(title) + "\n\n"


def _table(headers, rows):
    lines = [
        ".. list-table::",
        "   :header-rows: 1",
        "   :class: benchmark-table",
        "",
        "   * - " + headers[0],
    ]
    lines.extend("     - " + header for header in headers[1:])
    for row in rows:
        row = [" ".join(str(value).splitlines()) for value in row]
        lines.append("   * - " + str(row[0]))
        lines.extend("     - " + str(value) for value in row[1:])
    return "\n".join(lines) + "\n\n"


def _label(row):
    return row["family"].replace("_", " ").capitalize()


def _case_label(row):
    label = row["family"] + f" n={row['n']}"
    for field in ("scale", "parameter", "instance"):
        if row[field] is not None:
            label += f" {field}={row[field]}"
    return label


def _median_interval(stats):
    if stats is None:
        return "—"
    text = duration(stats["median"])
    interval = stats["median_ci95"]
    if interval is not None:
        text += f" [{duration(interval[0])}, {duration(interval[1])}]"
    return text


def _performance_table(rows):
    entries = []
    for row in sorted(rows, key=lambda row: (row["family"], row["n"])):
        timing = row["time_seconds"]
        density = row["density"]
        timeouts = row["outcomes"].get("timeout", 0)
        entries.append(
            (
                _label(row),
                row["n"],
                row["distinct_inputs"],
                _median_interval(timing),
                duration(timing["p90"]) if timing else "—",
                duration(timing["p95"]) if timing and not timeouts else "—",
                _percent(density["median"]) if density else "—",
                timeouts,
            )
        )
    return _table(
        (
            "Family",
            "Rectangles",
            "Inputs",
            "Median [95% interval]",
            "p90",
            "p95",
            "Median density",
            "Timeouts",
        ),
        entries,
    )


def _verified_summary(directory):
    manifest, records = load_campaign(directory)
    if manifest["benchmark_schema_version"] != 2:
        raise ValueError(
            "generated campaign reports require schema 2; retain historical reports separately"
        )
    summary_path = directory / "summary.json"
    if not summary_path.exists():
        raise ValueError(
            "publish the self-contained campaign before generating its documentation page"
        )
    summary = json.loads(summary_path.read_text())
    expected = json.loads(
        json.dumps(
            _build_summary(records, manifest, manifest["algorithms"]), allow_nan=False
        )
    )
    if summary != expected:
        raise ValueError("saved summary does not match the complete campaign")
    binding = json.loads((directory / "plot_manifest.json").read_text())
    verify_plot_source(directory, binding)
    if binding["summary_sha256"] != _sha256_file(summary_path):
        raise ValueError("published summary does not match the plot binding")
    if (
        binding["results_uncompressed_sha256"]
        != manifest["results_uncompressed_sha256"]
    ):
        raise ValueError("published plots refer to different measurements")
    if set(binding["figures"]) != {stem + ".svg" for stem in PLOT_STEMS}:
        raise ValueError("published figure list is incomplete")
    for name, digest in binding["figures"].items():
        path = directory / name
        if (_sha256_file(path) if path.exists() else None) != digest:
            raise ValueError(f"published figure does not match its binding: {name}")
    return manifest, records, summary, binding


def campaign_report(directory: Path, page_directory: Path) -> str:
    manifest, records, summary, binding = _verified_summary(directory)
    prefix = Path(
        os.path.relpath(directory.resolve(), page_directory.resolve())
    ).as_posix()
    date = manifest["timestamp_utc"][:10]
    mode = manifest["measurement_mode"]
    title = f"{mode.capitalize()} campaign — {date}"
    source = manifest["source"]
    revision = source.get("library_git_revision") or source["library_source_sha256"]
    calls = sum(
        record.get("repeat", 0) * len(record.get("timing_blocks_ns", []))
        for record in records
    )
    inputs = len({record["input_sha256"] for record in records})
    text = _heading(title)
    text += (
        f"These measurements describe the source snapshot at library revision ``{revision}``\n"
        f"(package version string ``{manifest['rpack_version']}``). The revision identifies\n"
        "the measured implementation; the version string alone does not establish a released build.\n\n"
    )
    text += _table(
        ("Measurement", "Value"),
        (
            (
                "Machine label / processor",
                (manifest.get("machine_label") or "anonymous")
                + " / "
                + str(manifest["cpu_model"]),
            ),
            ("System", manifest["platform"]),
            ("Python", manifest["python_version"]),
            ("Mode / workers", f"{mode} / {manifest['workers']}"),
            ("Requested CPU affinity", ", ".join(map(str, manifest["worker_cpus"]))),
            ("CPU governor", ", ".join(manifest["cpu_governors"]) or "unavailable"),
            (
                (
                    "Collection dates (UTC)"
                    if manifest.get("publication_privacy_version")
                    else "Recorded interval (UTC)"
                ),
                manifest["timestamp_utc"] + " to " + manifest["finished_timestamp_utc"],
            ),
            (
                "Measurement wall time",
                f"{manifest['measurement_seconds'] / 3600:.2f} hours",
            ),
            ("Workloads / distinct exact inputs", f"{len(records):,} / {inputs:,}"),
            (
                "Timing blocks / target per block",
                f"{manifest['timing_blocks']} / {duration(manifest['target_time_ns'] / 1e9)}",
            ),
            (
                "Completed timed packing calls",
                f"{calls:,} (warmup and calibration excluded)",
            ),
            ("Deadline for an entire job", duration(manifest["timeout_seconds"])),
        ),
    )
    if mode == "concurrent":
        text += (
            "Calls were measured under concurrent CPU load. These values include contention\n"
            "and frequency effects and should not be read as isolated single-thread latency.\n\n"
        )
    else:
        text += (
            "One worker measured latency with the other physical cores available.\n"
            "This controls intentional benchmark contention; it does not guarantee the absence\n"
            "of operating-system noise or predict performance on another machine.\n\n"
        )
    text += _heading("How to read the tables")
    text += (
        "Each input contributes the median of its timed blocks. Table percentiles describe\n"
        "variation between inputs, not individual calls. Brackets give a 95% percentile-bootstrap\n"
        "interval for the input-population median, using 1,000 deterministic resamples.\n"
        "Repeated calls and duplicate inputs are not extra independent samples.\n"
        "A fixed fixture has no input-population interval. Intervals do not account for\n"
        "systematic run-to-run changes in frequency, temperature, or background activity.\n\n"
        "The random families are synthetic distributions, not a sample of user applications.\n"
        "Tail estimates from small input counts, especially below 20, are uncertain.\n"
        "Dimensions are integer units, and rectangles keep their orientation. Packing density\n"
        "measures occupied area inside the returned bounding box, not closeness to a known optimum.\n\n"
    )
    outcomes = summary["outcomes"]
    text += _table(
        ("Outcome", "Jobs"),
        (
            ("Valid complete packing", outcomes.get("ok", 0)),
            (
                "Expected failure on deliberately infeasible bounds",
                outcomes.get("infeasible", 0),
            ),
            ("Job deadline exceeded", outcomes.get("timeout", 0)),
        ),
    )
    if outcomes.get("timeout", 0):
        text += (
            "**Some workloads timed out.** All timing and density summaries below are conditional\n"
            "on completed jobs; omitting timed-out cases can understate the slow tail.\n"
            "The p95 cell is suppressed for any group containing a timeout. A job deadline\n"
            "covers warmup, calibration and all blocks, so it is not a per-call lower bound.\n\n"
        )

    def figure(stem, caption):
        if binding["figures"].get(stem + ".svg") is None:
            return ""
        return (
            f".. figure:: {prefix}/{stem}.svg\n   :alt: {caption}\n   :align: center\n\n"
            f"   {caption} Completed packings only; consult outcome counts for timeouts.\n\n"
        )

    workloads = summary["workloads"]
    text += _heading("Rectangle count and input shape")
    text += (
        "Uniform sides use independent dimensions in [1, 1000]. Log-uniform sides\n"
        "cover that same range with more small pieces. The area/aspect mixture combines\n"
        "log-uniform areas with aspect ratios between 1/16 and 16. These distributions\n"
        "exercise different search costs even at equal rectangle counts.\n\n"
    )
    text += figure(
        "benchmark_random_overview",
        "Median runtime and density; shading spans input p10–p90.",
    )
    text += _performance_table(
        [row for row in workloads if row["benchmark"] == "count_sweep"]
    )
    text += _heading("Coordinate scaling and exact bigint reduction")
    text += (
        "These cases multiply fixed base geometries by powers of two. Their common factors\n"
        "allow exact GCD reduction after native integer bookkeeping overflows. They do not\n"
        "represent general huge coprime coordinates; those appear in the scenario table below.\n\n"
    )
    text += figure(
        "benchmark_scale_sweep",
        "Runtime, matched-input slowdown and observed fallback share.",
    )
    text += _heading("Structured inputs and the thin-rectangle fixture")
    text += (
        "The square sequence and fixed-perimeter sequence are fixed inputs at each length.\n"
        "The thin-rectangle sweep modifies one height in a known stress fixture. Repeated\n"
        "timing blocks measure noise on those fixtures, not a population of geometries.\n\n"
    )
    text += figure(
        "benchmark_structured_inputs",
        "Runtime and density of fixed structured sequences.",
    )
    text += figure(
        "benchmark_thin_pathology",
        "Thin-rectangle stress case, compared with a random reference median.",
    )
    text += _heading("Constraints, approximation and regression fixtures")
    text += (
        "The approximate-bigint family uses 32 huge rectangles with coprime coordinates.\n"
        "Sprite-like cases constrain either width or height to 512 units. Duplicate tiles\n"
        "draw sides from 8, 16, 32 and 64 units. The exact grid is 64 identical tiles inside\n"
        "a 128-by-128 bound. The two deliberately impossible families measure failure-path\n"
        "latency and have no complete-packing density. Regression fixtures are small\n"
        "specific inputs; they are not representative application distributions.\n\n"
    )
    text += _performance_table(
        [row for row in workloads if row["benchmark"] == "scenario"]
    )
    routes = {}
    for row in workloads:
        for name, count in row["fallback_paths"].items():
            routes[name] = routes.get(name, 0) + count
    text += _table(("Observed warmup route", "Completed jobs"), sorted(routes.items()))
    text += _heading("Evidence and reuse")
    text += (
        "All displayed values are generated from the verified campaign. The corpus stores\n"
        "the exact rectangles, bounds and expected outcomes; the raw records preserve every\n"
        "timing block and repeat count. Reuse this corpus to evaluate another implementation\n"
        "without relying on the current random generator.\n\n"
    )
    downloads = (
        ("manifest.json", "Machine, source and build manifest"),
        ("summary.json", "Full numeric summary"),
        ("results.jsonl.gz", "Compressed raw measurements"),
        ("corpus.jsonl.gz", "Exact input corpus"),
        ("source.tar.gz", "Measured source snapshot"),
        ("build.log", "Native compiler log"),
        ("plot_manifest.json", "Figure and summary bindings"),
    )
    for filename, label in downloads:
        text += f"* :download:`{label} <{prefix}/{filename}>`\n"
    if (directory / "plot-source.tar.gz").exists():
        text += f"* :download:`Plot and report source snapshot <{prefix}/plot-source.tar.gz>`\n"
    text += (
        f"\nCorpus fingerprint: ``{manifest['corpus_sha256']}``.\n\n"
        f"Native extension fingerprint: ``{manifest['extension_sha256']}``.\n"
    )
    return text


def write_report(directory: Path, destination: Path) -> None:
    text = campaign_report(directory, destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Generated pages are versioned artifacts too; updating requires a new path
    # or an explicit removal by the maintainer, never an implicit overwrite.
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(text)
    print(f"Documentation page written to {destination}")


def comparison_report(summary: dict) -> str:
    text = _heading("Matched benchmark comparison")
    text += _table(
        ("Measurement", "Identity"),
        (
            (
                label + " library revision",
                summary[name]["source"].get("library_git_revision")
                or summary[name]["source"]["library_source_sha256"],
            )
            for name, label in (("baseline", "Baseline"), ("candidate", "Candidate"))
        ),
    )
    text += f"Frozen corpus fingerprint: ``{summary['corpus_sha256']}``.\n\n"
    text += (
        "Runtime ratios are candidate / baseline: values above one are slower.\n"
        "Bounding-box area ratios above one mean a larger enclosing box for the same input.\n"
        "Intervals resample independent inputs, not timing-loop iterations.\n"
        "They do not account for systematic machine drift; repeat a comparison before\n"
        "attributing a small difference to a code change.\n\n"
    )
    if not summary["controlled_conditions"]:
        text += "**Uncontrolled comparison:** execution conditions differ.\n\n"
        text += _table(
            ("Condition", "Baseline", "Candidate"),
            (
                (name, str(value["baseline"]), str(value["candidate"]))
                for name, value in summary["condition_differences"].items()
            ),
        )
    if summary["same_library_source"]:
        text += "Both runs use identical library source. "
        text += (
            "This comparison measures repeatability.\n\n"
            if summary["controlled_conditions"]
            else "Differences reflect the execution conditions and measurement noise.\n\n"
        )
    overall = summary["overall"]
    ratio = overall["runtime_ratio"]
    if ratio:
        text += f"Across {ratio['count']} distinct timed inputs, the median runtime ratio is **{ratio['median']:.4f}x**.\n\n"
    text += (
        "This aggregate gives equal weight to distinct benchmark inputs; it is not an\n"
        "application workload mix. No overall confidence interval is reported: fixed fixtures\n"
        "and scaled variants of the same geometry are not independent population samples.\n"
        "Intervals below apply within individual workload groups. Timeouts are outcome\n"
        "changes, never zero-duration samples.\n\n"
    )
    text += _table(
        ("Outcome transition", "Jobs"), sorted(overall["outcome_pairs"].items())
    )
    text += _heading("Workload groups")
    rows = []
    for group in sorted(
        summary["groups"],
        key=lambda group: (
            group["benchmark"],
            group["algorithm"],
            group["family"],
            group["n"],
            group["scale"] or 0,
            group["parameter"] or 0,
        ),
    ):
        timing, area = group["runtime_ratio"], group["area_ratio"]
        label = group["family"] + f" n={group['n']}"
        if group["scale"] is not None:
            label += f" scale={group['scale']}"
        if group["parameter"] is not None:
            label += f" parameter={group['parameter']}"
        ratio_text = "—"
        if timing:
            ratio_text = f"{timing['median']:.4f}x"
            if timing["median_ci95"] is not None:
                low, high = timing["median_ci95"]
                ratio_text += f" [{low:.4f}, {high:.4f}]"
        rows.append(
            (
                label,
                group["distinct_inputs"],
                ratio_text,
                f"{area['median']:.6f}x" if area else "—",
                group["inputs_over_5_percent_slower"],
                group["inputs_with_larger_area"],
            )
        )
    text += _table(
        (
            "Workload",
            "Inputs",
            "Runtime ratio [95% interval]",
            "Median area ratio",
            "Inputs >5% slower",
            "Inputs with larger boxes",
        ),
        rows,
    )
    text += _heading("Largest observed slowdowns")
    text += "These are individual-input observations, not independently confirmed regressions.\n\n"
    text += _table(
        ("Workload / instance", "Baseline", "Candidate", "Ratio"),
        (
            (
                _case_label(row),
                duration(row["baseline_seconds"]),
                duration(row["candidate_seconds"]),
                f"{row['runtime_ratio']:.4f}x",
            )
            for row in summary["largest_slowdowns"]
        ),
    )
    if summary["largest_area_increases"]:
        text += _heading("Larger enclosing boxes")
        text += _table(
            ("Workload / instance", "Area ratio", "Density change"),
            (
                (
                    _case_label(row),
                    f"{row['area_ratio']:.6f}x",
                    f"{row['density_change'] * 100:+.4f} percentage points",
                )
                for row in summary["largest_area_increases"]
            ),
        )
    return text
