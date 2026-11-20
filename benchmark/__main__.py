"""Command line interface for benchmark runs, comparisons and immutable reports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import uuid

from benchmark import suite


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Build and measure a new immutable campaign.")
    run.add_argument("--output-dir", "-o", type=Path)
    run.add_argument(
        "--machine-label",
        help="Optional public label shared by runs on one machine; do not use its hostname.",
    )
    run.add_argument("--profile", choices=sorted(suite.PROFILES), default="full")
    run.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Physical cores to use; 1 measures isolated latency (default).",
    )
    run.add_argument(
        "--corpus", type=Path, help="Reuse a previous run's exact corpus.jsonl.gz."
    )
    run.add_argument(
        "--timing-blocks", type=int, help="Override the profile's block count (>=2)."
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=600,
        help="Deadline per job, including warmup and all timing blocks (seconds).",
    )
    plot = commands.add_parser("plot", help="Plot a complete, verified campaign.")
    plot.add_argument("--input-dir", "-i", type=Path, required=True)
    plot.add_argument("--output-dir", "-o", type=Path, required=True)
    plot.add_argument("--algorithm", dest="algorithms", action="append")
    publish = commands.add_parser(
        "publish", help="Stage a self-contained immutable campaign."
    )
    publish.add_argument("--input-dir", type=Path, required=True)
    publish.add_argument("--plot-dir", type=Path, required=True)
    publish.add_argument("--output-dir", type=Path, required=True)
    publish.add_argument(
        "--machine-label", help="Optional public alias for this measurement machine."
    )
    report = commands.add_parser(
        "report", help="Generate a documentation page from verified evidence."
    )
    report.add_argument("--input-dir", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser(
        "compare", help="Compare matched inputs across two revisions."
    )
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--output-dir", type=Path, required=True)
    compare.add_argument("--allow-environment-change", action="store_true")
    export = commands.add_parser(
        "export", help="Export buildable sources with verified origin metadata."
    )
    export.add_argument("--output-dir", type=Path, required=True)
    export.add_argument(
        "--library-ref",
        help="Use library sources from this Git revision with the current harness.",
    )
    args = parser.parse_args(argv)
    if args.command == "run":
        from benchmark.runner import run_benchmarks

        destination = args.output_dir or Path("artifacts/benchmarks") / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        run_benchmarks(
            destination,
            args.profile,
            args.workers,
            corpus_path=args.corpus,
            timing_blocks=args.timing_blocks,
            timeout_seconds=args.timeout,
            machine_label=args.machine_label,
        )
    elif args.command == "plot":
        from benchmark.plot import plot_benchmarks

        plot_benchmarks(args.input_dir, args.output_dir, args.algorithms)
    elif args.command == "publish":
        from benchmark.publish import publish_benchmark

        publish_benchmark(
            args.input_dir,
            args.plot_dir,
            args.output_dir,
            machine_label=args.machine_label,
        )
    elif args.command == "report":
        from benchmark.report import write_report

        write_report(args.input_dir, args.output)
    elif args.command == "compare":
        from benchmark.compare import compare_campaigns

        compare_campaigns(
            args.baseline,
            args.candidate,
            args.output_dir,
            allow_environment_change=args.allow_environment_change,
        )
    elif args.command == "export":
        from benchmark.provenance import export_sources

        export_sources(args.output_dir, library_ref=args.library_ref)
        print(f"Buildable sources exported to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
