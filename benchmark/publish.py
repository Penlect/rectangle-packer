"""Publish a verified benchmark campaign and its documentation assets.

The publication step validates the raw result grid, creates a deterministic
gzip artifact, records hashes for both compressed and uncompressed content,
and copies the matching manifest, summary, and SVG figures into the Sphinx
tree.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, BinaryIO

from benchmark.privacy import check_public_tree, public_manifest, public_source

from benchmark.plot import PLOT_STEMS
from benchmark.results import (
    load_campaign,
    verify_plot_source,
    _build_summary,
    _sha256_file,
    _sha256_results_content,
)


def _copy_and_hash(source: BinaryIO, destination: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
        destination.write(chunk)
    return digest.hexdigest()


def _compress_results(source_path: Path, destination_path: Path) -> tuple[str, str]:
    """Write deterministic gzip data and return raw and compressed hashes."""
    if source_path.resolve() == destination_path.resolve():
        raise ValueError("input and output results must be different files")
    source_opener = gzip.open if source_path.suffix == ".gz" else Path.open
    with source_opener(source_path, "rb") as source:
        with destination_path.open("xb") as raw_destination:
            # Empty filename and mtime zero keep the gzip header reproducible.
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=9,
                mtime=0,
                fileobj=raw_destination,
            ) as destination:
                uncompressed_sha256 = _copy_and_hash(source, destination)

    compressed_digest = hashlib.sha256(destination_path.read_bytes()).hexdigest()
    return uncompressed_sha256, compressed_digest


def publish_benchmark(
    input_dir: Path,
    plot_dir: Path,
    data_output_dir: Path,
    *,
    machine_label: str | None = None,
) -> dict[str, Any]:
    """Validate and publish one benchmark campaign."""
    manifest, records = load_campaign(input_dir)
    if manifest["benchmark_schema_version"] == 2 and manifest.get("build") is None:
        raise ValueError("publication requires a recorded fresh native build")

    summary_path = plot_dir / "benchmark_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("validated_record_count") != len(records):
        raise ValueError("plot summary does not match the validated record count")
    if summary.get("manifest", {}).get("job_grid_sha256") != manifest.get(
        "job_grid_sha256"
    ):
        raise ValueError("plot summary does not match the benchmark manifest")

    source_filename = manifest.get("results_file", "results.jsonl")
    source_path = input_dir / source_filename
    try:
        plot_manifest = json.loads(
            (plot_dir / "plot_manifest.json").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError("missing or invalid plot manifest; regenerate plots") from exc
    verify_plot_source(plot_dir, plot_manifest)
    if plot_manifest.get("results_uncompressed_sha256") != _sha256_results_content(
        source_path
    ):
        raise ValueError("plots do not match the raw benchmark measurements")
    if plot_manifest.get("summary_sha256") != _sha256_file(summary_path):
        raise ValueError("plot summary digest does not match the plot manifest")
    # Publication represents the complete campaign, including all algorithms.
    # JSON normalizes tuples and integer keys in the generated summary.
    expected_summary = json.loads(
        json.dumps(_build_summary(records, manifest, manifest["algorithms"]))
    )
    if summary != expected_summary:
        raise ValueError("plot summary does not match the complete benchmark campaign")
    figures = plot_manifest.get("figures")
    if not isinstance(figures, dict) or set(figures) != {
        f"{stem}.svg" for stem in PLOT_STEMS
    }:
        raise ValueError("plot manifest does not list the expected figures")
    for filename, expected_digest in figures.items():
        source = plot_dir / filename
        actual_digest = _sha256_file(source) if source.exists() else None
        if actual_digest != expected_digest:
            raise ValueError(
                f"figure digest does not match the plot manifest: {filename}"
            )

    from benchmark.storage import new_directory, write_json

    with new_directory(data_output_dir) as staging:
        published_results = staging / "results.jsonl.gz"
        uncompressed_sha256, compressed_sha256 = _compress_results(
            source_path, published_results
        )
        published_manifest, private_names = public_manifest(
            manifest, input_dir, staging
        )
        if machine_label is not None:
            from benchmark.privacy import machine_label as validate_machine_label

            published_manifest["machine_label"] = validate_machine_label(machine_label)
        published_manifest.update(
            results_file=published_results.name,
            results_compression="gzip",
            results_sha256=compressed_sha256,
            results_uncompressed_sha256=uncompressed_sha256,
        )
        write_json(staging / "manifest.json", published_manifest)
        if manifest["benchmark_schema_version"] == 2:
            for filename in ("corpus.jsonl.gz",):
                shutil.copyfile(input_dir / filename, staging / filename)
        published_plot_manifest = {
            key: plot_manifest[key]
            for key in (
                "plot_schema_version",
                "plot_environment",
                "results_uncompressed_sha256",
                "figures",
            )
            if key in plot_manifest
        }
        if plot_manifest["plot_schema_version"] == 2:
            published_plot_manifest["plot_source"] = public_source(
                plot_dir / "plot-source.tar.gz",
                staging / "plot-source.tar.gz",
                private_names=private_names,
            )
            published_plot_manifest["plot_source_archive_sha256"] = _sha256_file(
                staging / "plot-source.tar.gz"
            )
            verify_plot_source(staging, published_plot_manifest)
        published_summary = dict(summary)
        published_summary["manifest"] = published_manifest
        write_json(staging / "summary.json", published_summary)
        for filename, digest in figures.items():
            if digest is not None:
                shutil.copyfile(plot_dir / filename, staging / filename)
                if _sha256_file(staging / filename) != digest:
                    raise ValueError("figure changed during publication")
        published_plot_manifest["summary_sha256"] = _sha256_file(
            staging / "summary.json"
        )
        write_json(staging / "plot_manifest.json", published_plot_manifest)
        # Re-read staged bytes before committing the directory, including the
        # compressed record stream, frozen corpus and complete source archive.
        checked_manifest, checked_records = load_campaign(staging)
        if checked_records != records:
            raise ValueError("measurements changed during publication")
        if checked_manifest != published_manifest:
            raise ValueError("manifest changed during publication")
        check_public_tree(staging, private_names=private_names)
    print(f"Immutable campaign published to {data_output_dir}")
    return published_manifest
