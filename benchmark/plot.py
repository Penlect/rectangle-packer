"""Plot and summarize benchmark results."""

from __future__ import annotations

import json
from importlib import metadata
import platform
import math
from pathlib import Path
from typing import Any

from benchmark import provenance
from benchmark.results import (
    load_campaign,
    _build_summary,
    _filter_records,
    _select_algorithms,
    _sha256_file,
    _sha256_results_content,
)

plt: Any
FuncFormatter: Any
PercentFormatter: Any


FAMILY_COLORS = {
    "uniform": "#0f4c5c",
    "log_uniform": "#e36414",
    "area_aspect": "#5f0f40",
    "squares": "#0f4c5c",
    "fixed_perimeter": "#9a031e",
    "thin_pathology": "#9a031e",
    "pathology_guardrail": "#0f4c5c",
}
ALGORITHM_LINESTYLES = ("-", "--", ":", "-.")
PLOT_STEMS = (
    "benchmark_random_overview",
    "benchmark_scale_sweep",
    "benchmark_structured_inputs",
    "benchmark_thin_pathology",
)


def _load_plot_dependencies() -> None:
    """Import optional plotting dependencies only when plots are requested."""
    global FuncFormatter, PercentFormatter, plt
    try:
        import matplotlib
    except ModuleNotFoundError as exc:
        raise RuntimeError("benchmark plotting requires python3-matplotlib") from exc

    matplotlib.rcdefaults()
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "rectangle-packer-benchmark"
    from matplotlib import pyplot
    from matplotlib.ticker import FuncFormatter as MatplotlibFuncFormatter
    from matplotlib.ticker import PercentFormatter as MatplotlibPercentFormatter

    plt = pyplot
    FuncFormatter = MatplotlibFuncFormatter
    PercentFormatter = MatplotlibPercentFormatter


def _percent_label(value: float, _: int) -> str:
    return f"{value * 100:.0f}%"


def _save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(svg_path, metadata={"Date": None})
    plt.close(fig)

    # Matplotlib wraps SVG paths with trailing spaces. Normalize them so
    # generated documentation assets pass Git's whitespace checks.
    svg = svg_path.read_text(encoding="utf-8")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
        encoding="utf-8",
    )


def _linestyle_for_algorithm(algorithm: str, algorithm_names: list[str]) -> str:
    index = algorithm_names.index(algorithm)
    return ALGORITHM_LINESTYLES[index % len(ALGORITHM_LINESTYLES)]


def _series_label(
    algorithm: str,
    family_label: str,
    algorithm_names: list[str],
) -> str:
    if len(algorithm_names) == 1:
        return family_label
    return f"{algorithm}: {family_label}"


def _plot_random_overview(
    summary: dict[str, Any], algorithm_names: list[str], output_dir: Path
) -> None:
    fig, (ax_time, ax_density) = plt.subplots(
        2,
        1,
        figsize=(9, 10),
        sharex=True,
        layout="constrained",
    )

    for algorithm in algorithm_names:
        linestyle = _linestyle_for_algorithm(algorithm, algorithm_names)
        for family, family_summary in summary.get(algorithm, {}).items():
            color = FAMILY_COLORS.get(family, "#555555")
            x = [point["n"] for point in family_summary["points"]]
            time_median = [
                point["time_seconds"]["median"] for point in family_summary["points"]
            ]
            time_low = [
                point["time_seconds"]["p10"] for point in family_summary["points"]
            ]
            time_high = [
                point["time_seconds"]["p90"] for point in family_summary["points"]
            ]
            density_median = [
                point["density"]["median"] for point in family_summary["points"]
            ]
            density_low = [
                point["density"]["p10"] for point in family_summary["points"]
            ]
            density_high = [
                point["density"]["p90"] for point in family_summary["points"]
            ]
            label = _series_label(algorithm, family_summary["label"], algorithm_names)
            exponent = family_summary["power_law_exponent"]
            time_label = label
            if exponent is not None and math.isfinite(exponent):
                time_label += f" (~n^{exponent:.1f})"

            ax_time.fill_between(x, time_low, time_high, color=color, alpha=0.10)
            ax_time.plot(
                x,
                time_median,
                marker="o",
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=time_label,
            )

            ax_density.fill_between(
                x, density_low, density_high, color=color, alpha=0.10
            )
            ax_density.plot(
                x,
                density_median,
                marker="o",
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=label,
            )

    ax_time.set_yscale("log")
    ax_time.grid(True, which="both", alpha=0.3)
    ax_time.set_ylabel("Seconds")
    ax_time.set_title("Random-instance overview")
    ax_time.legend()

    ax_density.grid(True, alpha=0.3)
    ax_density.set_xlabel("Number of rectangles")
    ax_density.set_ylabel("Packing density")
    ax_density.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax_density.legend()

    _save_figure(fig, output_dir, "benchmark_random_overview")


def _plot_scale_sweep(
    summary: dict[str, Any], algorithm_names: list[str], output_dir: Path
) -> None:
    fig, (ax_time, ax_relative, ax_fallback) = plt.subplots(
        3,
        1,
        figsize=(9, 11),
        sharex=True,
        height_ratios=(3, 2, 1.5),
        layout="constrained",
    )

    for algorithm in algorithm_names:
        linestyle = _linestyle_for_algorithm(algorithm, algorithm_names)
        for family, family_summary in summary.get(algorithm, {}).items():
            color = FAMILY_COLORS.get(family, "#555555")
            x = [point["scale"] for point in family_summary["points"]]
            y = [point["time_seconds"]["median"] for point in family_summary["points"]]
            y_low = [point["time_seconds"]["p10"] for point in family_summary["points"]]
            y_high = [
                point["time_seconds"]["p90"] for point in family_summary["points"]
            ]
            relative = [
                (
                    point["relative_time"]["median"]
                    if point["relative_time"]
                    else float("nan")
                )
                for point in family_summary["points"]
            ]
            relative_low = [
                (
                    point["relative_time"]["p10"]
                    if point["relative_time"]
                    else float("nan")
                )
                for point in family_summary["points"]
            ]
            relative_high = [
                (
                    point["relative_time"]["p90"]
                    if point["relative_time"]
                    else float("nan")
                )
                for point in family_summary["points"]
            ]
            fallback_share = [
                point["fallback_share"] for point in family_summary["points"]
            ]
            label = _series_label(algorithm, family_summary["label"], algorithm_names)

            ax_time.fill_between(x, y_low, y_high, color=color, alpha=0.10)
            ax_time.plot(
                x,
                y,
                marker="o",
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=label,
            )
            ax_relative.fill_between(
                x, relative_low, relative_high, color=color, alpha=0.10
            )
            ax_relative.plot(
                x,
                relative,
                marker="o",
                color=color,
                linestyle=linestyle,
                linewidth=2,
            )
            ax_fallback.plot(
                x,
                fallback_share,
                marker="o",
                color=color,
                linestyle=linestyle,
                linewidth=2,
            )

    for axis in (ax_time, ax_relative, ax_fallback):
        axis.set_xscale("log", base=2)
        axis.grid(True, which="both", alpha=0.3)

    ax_time.set_yscale("log")
    ax_time.set_ylabel("Seconds")
    ax_time.set_title("Coordinate scaling at fixed geometry")
    ax_time.legend()

    ax_relative.axhline(1.0, color="#555555", linewidth=1, linestyle=":")
    ax_relative.set_yscale("log", base=2)
    ax_relative.set_ylabel("Paired slowdown\n(relative to smallest scale)")

    ax_fallback.set_xlabel("Scale factor")
    ax_fallback.set_ylabel("Fallback share")
    ax_fallback.yaxis.set_major_formatter(FuncFormatter(_percent_label))
    ax_fallback.set_ylim(-0.02, 1.02)

    _save_figure(fig, output_dir, "benchmark_scale_sweep")


def _plot_structured(
    summary: dict[str, Any], algorithm_names: list[str], output_dir: Path
) -> None:
    fig, (ax_time, ax_density) = plt.subplots(
        2, 1, figsize=(9, 8), sharex=True, layout="constrained"
    )
    for algorithm in algorithm_names:
        linestyle = _linestyle_for_algorithm(algorithm, algorithm_names)
        for family, family_summary in summary.get(algorithm, {}).items():
            color = FAMILY_COLORS.get(family, "#555555")
            points = family_summary["points"]
            x = [point["n"] for point in points]
            runtime = [point["time_seconds"]["median"] for point in points]
            density = [point["density"]["median"] for point in points]
            label = _series_label(algorithm, family_summary["label"], algorithm_names)
            ax_time.plot(
                x,
                runtime,
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=label,
            )
            ax_density.plot(
                x, density, color=color, linestyle=linestyle, linewidth=2, label=label
            )

    ax_time.set_yscale("log")
    ax_time.grid(True, which="both", alpha=0.3)
    ax_time.set_ylabel("Seconds")
    ax_time.set_title("Structured deterministic families")
    ax_time.legend()
    ax_density.grid(True, alpha=0.3)
    ax_density.set_xlabel("Sequence length n")
    ax_density.set_ylabel("Packing density")
    ax_density.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax_density.legend()
    _save_figure(fig, output_dir, "benchmark_structured_inputs")


def _plot_pathology(
    summary: dict[str, Any], algorithm_names: list[str], output_dir: Path
) -> None:
    fig, (ax_time, ax_density) = plt.subplots(
        2, 1, figsize=(9, 8), sharex=True, layout="constrained"
    )
    for algorithm in algorithm_names:
        linestyle = _linestyle_for_algorithm(algorithm, algorithm_names)
        pathology_points = summary[algorithm]["thin_pathology"]
        guardrail = summary[algorithm]["guardrail"]
        x = [point["height"] for point in pathology_points]
        y = [point["time_seconds"]["median"] for point in pathology_points]
        y_low = [point["time_seconds"]["p10"] for point in pathology_points]
        y_high = [point["time_seconds"]["p90"] for point in pathology_points]
        density = [point["density"]["median"] for point in pathology_points]
        pathology_label = _series_label(
            algorithm, "Thin-rectangle pathology", algorithm_names
        )
        if guardrail is not None:
            guardrail_label = _series_label(
                algorithm,
                "Uniform random reference median",
                algorithm_names,
            )
            # The random reference varies the input while the pathology band
            # repeats one fixture, so showing both percentile bands together
            # would incorrectly suggest equivalent uncertainty semantics.
            ax_time.axhline(
                guardrail["time_seconds"]["median"],
                color=FAMILY_COLORS["pathology_guardrail"],
                linestyle=linestyle,
                linewidth=2,
                label=guardrail_label,
            )
        ax_time.fill_between(
            x, y_low, y_high, color=FAMILY_COLORS["thin_pathology"], alpha=0.10
        )
        ax_time.plot(
            x,
            y,
            marker="o",
            color=FAMILY_COLORS["thin_pathology"],
            linestyle=linestyle,
            linewidth=2,
            label=pathology_label,
        )
        ax_density.plot(
            x,
            density,
            marker="o",
            color=FAMILY_COLORS["thin_pathology"],
            linestyle=linestyle,
            linewidth=2,
        )

    ax_time.set_yscale("log")
    ax_time.grid(True, which="both", alpha=0.3)
    ax_time.set_ylabel("Seconds")
    ax_time.set_title("Thin-rectangle stress test")
    ax_time.legend()
    ax_density.set_xscale("log", base=2)
    ax_density.grid(True, which="both", alpha=0.3)
    ax_density.set_xlabel("Height of the first rectangle")
    ax_density.set_ylabel("Packing density")
    ax_density.yaxis.set_major_formatter(PercentFormatter(1.0))
    _save_figure(fig, output_dir, "benchmark_thin_pathology")


def plot_benchmarks(
    input_dir: Path,
    output_dir: Path,
    algorithm_names: list[str] | None = None,
) -> dict[str, Any]:
    """Generate plots and summary JSON from benchmark results."""
    if (
        output_dir.resolve() == input_dir.resolve()
        or (output_dir / "manifest.json").exists()
    ):
        raise ValueError("plot output must not be a campaign directory")
    _load_plot_dependencies()
    manifest, records = load_campaign(input_dir)
    selected_algorithms = _select_algorithms(manifest, algorithm_names)
    selected_records = _filter_records(records, selected_algorithms)
    summary = _build_summary(selected_records, manifest, selected_algorithms)

    output_dir.mkdir(parents=True, exist_ok=True)
    # An interrupted regeneration must not retain a previous completion record.
    plot_manifest_path = output_dir / "plot_manifest.json"
    plot_manifest_path.unlink(missing_ok=True)
    plot_source = provenance.identify_source()
    plot_source_archive = output_dir / "plot-source.tar.gz"
    plot_source_archive.unlink(missing_ok=True)
    provenance.source_archive(plot_source_archive, plot_source)
    summary_path = output_dir / "benchmark_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    plots = (
        ("benchmark_random_overview", "count_sweep", _plot_random_overview),
        ("benchmark_scale_sweep", "scale_sweep", _plot_scale_sweep),
        ("benchmark_structured_inputs", "structured", _plot_structured),
        ("benchmark_thin_pathology", "pathology", _plot_pathology),
    )
    figures = {}
    for stem, section, plotter in plots:
        path = output_dir / f"{stem}.svg"
        if path.exists():
            path.unlink()
        section_summary = summary[section]
        if any(section_summary.get(algorithm) for algorithm in selected_algorithms):
            plotter(section_summary, selected_algorithms, output_dir)
            figures[path.name] = _sha256_file(path)
        else:
            figures[path.name] = None
    plot_manifest = {
        "plot_schema_version": 2,
        "plot_source": plot_source,
        "plot_source_archive_sha256": _sha256_file(plot_source_archive),
        "plot_environment": {
            "python": platform.python_version(),
            "matplotlib": _package_version("matplotlib"),
            "numpy": _package_version("numpy"),
        },
        "results_uncompressed_sha256": _sha256_results_content(
            input_dir / manifest.get("results_file", "results.jsonl")
        ),
        "summary_sha256": _sha256_file(summary_path),
        "figures": figures,
    }
    if provenance.identify_source()["source_sha256"] != plot_source["source_sha256"]:
        raise ValueError("plotting sources changed while generating figures")
    # Write last, after every figure has completed successfully.
    plot_manifest_path.write_text(
        json.dumps(plot_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Plots written to {output_dir}")
    print(f"Summary written to {summary_path}")
    return summary


def _package_version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
