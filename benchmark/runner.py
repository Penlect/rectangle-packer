"""Measure frozen workloads in isolated workers and retain complete benchmark evidence."""

from __future__ import annotations

from collections import Counter, deque
import gc
import json
import math
import multiprocessing
from multiprocessing.connection import wait
import os
from pathlib import Path
import platform
import random
import re
import sys
import statistics
import time
import traceback
from typing import Any

from benchmark import corpus, provenance, suite
from benchmark.storage import sha256_file, write_json

ALGORITHMS = {"default": "rpack.pack()"}
WORKER_CPU: int | None = None


class InvalidPackingError(RuntimeError):
    """The packer returned invalid geometry or an unexpected outcome."""


def _read_topology_value(cpu_dir: Path, filename: str, default: str) -> str:
    path = cpu_dir / "topology" / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return platform.processor() or None


def _cpu_governors(cpus: list[int]) -> list[str]:
    governors = set()
    for cpu in cpus:
        path = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        try:
            governors.add(path.read_text(encoding="utf-8").strip())
        except OSError:
            continue
    return sorted(governors)


def _affinity_cpus() -> list[int]:
    if hasattr(os, "sched_getaffinity"):
        try:
            return sorted(os.sched_getaffinity(0))
        except OSError:
            pass
    return list(range(os.cpu_count() or 1))


def _first_logical_cpu_per_core() -> list[int]:
    available = set(_affinity_cpus())
    mapping: dict[tuple[str, str], int] = {}
    cpu_dirs = sorted(
        Path("/sys/devices/system/cpu").glob("cpu[0-9]*"),
        key=lambda path: int(path.name[3:]),
    )
    for cpu_dir in cpu_dirs:
        cpu = int(cpu_dir.name[3:])
        if cpu not in available:
            continue
        package_id = _read_topology_value(cpu_dir, "physical_package_id", "0")
        core_id = _read_topology_value(cpu_dir, "core_id", str(cpu))
        mapping.setdefault((package_id, core_id), cpu)
    if mapping:
        return [
            mapping[key]
            for key in sorted(
                mapping,
                key=lambda key: (int(key[0]), int(key[1])),
            )
        ]
    return sorted(available)


def _generate_sizes(job: suite.Job) -> list[tuple[int, int]]:
    return [tuple(size) for size in suite.generate_input(job)["sizes"]]


def _choose_repeat_count(estimate_ns: int, target_ns: int, max_repeat: int) -> int:
    return max(1, min(max_repeat, target_ns // max(1, estimate_ns)))


def _validate_positions(sizes, positions, job, max_width=None, max_height=None):
    if len(positions) != len(sizes):
        raise InvalidPackingError("position count does not match input")
    boxes = []
    for (width, height), position in zip(sizes, positions):
        if len(position) != 2 or any(type(v) is not int or v < 0 for v in position):
            raise InvalidPackingError(
                "positions must contain nonnegative integer coordinates"
            )
        x, y = position
        boxes.append((x, y, x + width, y + height))
    width = max(box[2] for box in boxes)
    height = max(box[3] for box in boxes)
    if (max_width is not None and width > max_width) or (
        max_height is not None and height > max_height
    ):
        raise InvalidPackingError("packing exceeds explicit bounds")
    # Independent integer geometry avoids validating the packer with its own helpers.
    active = []
    for box in sorted(boxes):
        active = [other for other in active if other[2] > box[0]]
        if any(box[1] < other[3] and other[1] < box[3] for other in active):
            raise InvalidPackingError("packing contains overlapping rectangles")
        active.append(box)
    area = sum(w * h for w, h in sizes)
    return width, height, area / (width * height)


def _warmup(call) -> str:
    """Observe the actual fallback route during the untimed warmup only."""
    import rpack
    from rpack import _bigint_fallback as bigint

    route = "native"
    original_fallback = rpack._pack_with_bigint_fallback
    original_approximation = bigint._build_approximation

    def fallback(*args, **kwargs):
        nonlocal route
        route = "exact_gcd"
        return original_fallback(*args, **kwargs)

    def approximation(sizes, max_width, max_height, scale):
        nonlocal route
        # The fallback also calls this helper with scale=1 after exact gcd
        # reduction; only a larger divisor introduces approximation.
        if scale > 1:
            route = "approximate"
        return original_approximation(sizes, max_width, max_height, scale)

    rpack._pack_with_bigint_fallback = fallback
    bigint._build_approximation = approximation
    try:
        call()
    finally:
        rpack._pack_with_bigint_fallback = original_fallback
        bigint._build_approximation = original_approximation
    return route


def _measure_case(
    case: dict, target_ns: int, max_repeat: int, timing_blocks: int
) -> dict:
    import rpack

    workload = case["input"]
    sizes = [tuple(size) for size in workload["sizes"]]
    bounds = {
        key: workload[key]
        for key in ("max_width", "max_height")
        if workload[key] is not None
    }

    def call():
        try:
            return rpack.pack(sizes, **bounds)
        except rpack.PackingImpossibleError as exc:
            if workload["expected_status"] != "infeasible":
                raise InvalidPackingError(
                    f"unexpected packing failure: {exc.args[0]}"
                ) from exc
            return None

    enabled = gc.isenabled()
    if enabled:
        gc.disable()
    try:
        # Tracing is removed before calibration and every saved timing block.
        fallback_path = _warmup(call)
        started = time.perf_counter_ns()
        call()
        estimate = time.perf_counter_ns() - started
        repeat = _choose_repeat_count(estimate, target_ns, max_repeat)
        blocks = []
        for _ in range(timing_blocks):
            started = time.perf_counter_ns()
            for _ in range(repeat):
                positions = call()
            blocks.append(time.perf_counter_ns() - started)
    finally:
        if enabled:
            gc.enable()

    status = "infeasible" if positions is None else "ok"
    if status != workload["expected_status"]:
        raise InvalidPackingError("packing outcome differs from the frozen workload")
    record = {
        **case["job"],
        "input_sha256": case["input_sha256"],
        "worker_cpu": WORKER_CPU,
        "status": status,
        "repeat": repeat,
        "timing_blocks_ns": blocks,
        "elapsed_ns": sum(blocks),
        "time_per_call_ns": statistics.median(blocks) / repeat,
        "total_area": sum(w * h for w, h in sizes),
        "bbox_width": None,
        "bbox_height": None,
        "density": None,
        "fallback_path": fallback_path,
    }
    record["used_bigint_fallback"] = record["fallback_path"] != "native"
    if status == "ok":
        width, height, density = _validate_positions(
            sizes, positions, case["job"], workload["max_width"], workload["max_height"]
        )
        record.update(bbox_width=width, bbox_height=height, density=density)
    return record


def _worker(
    connection,
    cpu: int,
    target_ns: int,
    max_repeat: int,
    timing_blocks: int,
    runtime_root,
):
    global WORKER_CPU
    if runtime_root is not None:
        # Spawn may re-import a caller that already imports rpack. Discard only
        # that child's package cache before selecting this run's isolated build.
        for name in list(sys.modules):
            if name == "rpack" or name.startswith("rpack."):
                del sys.modules[name]
        sys.path.insert(0, str(runtime_root))
    WORKER_CPU = None
    if hasattr(os, "sched_setaffinity"):
        try:
            os.sched_setaffinity(0, {cpu})
            WORKER_CPU = cpu
        except OSError:
            pass
    try:
        while True:
            case = connection.recv()
            try:
                import rpack._core

                if runtime_root is not None and Path(
                    rpack._core.__file__
                ).resolve().parent != (Path(runtime_root).resolve() / "rpack"):
                    raise RuntimeError("worker imported a different native extension")
                record = _measure_case(case, target_ns, max_repeat, timing_blocks)
            except Exception:
                record = {
                    **case["job"],
                    "input_sha256": case["input_sha256"],
                    "status": "error",
                    "worker_cpu": WORKER_CPU,
                    "error": traceback.format_exc(),
                }
            connection.send(record)
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


def _stop_worker(slot: dict) -> None:
    process = slot["process"]
    if process.is_alive():
        process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join()
    slot["connection"].close()


def _execute_cases(
    cases,
    worker_cpus,
    target_ns,
    max_repeat,
    timing_blocks,
    timeout_seconds,
    worker_target=_worker,
    runtime_root=None,
):
    """Keep one in-flight job per worker; kill hung workers and stop promptly on error."""
    context = multiprocessing.get_context("spawn")
    pending = deque(cases)
    slots = []

    def start(cpu):
        parent, child = context.Pipe()
        process = context.Process(
            target=worker_target,
            args=(child, cpu, target_ns, max_repeat, timing_blocks, runtime_root),
        )
        process.start()
        child.close()
        slot = {"process": process, "connection": parent, "cpu": cpu}
        case = pending.popleft()
        parent.send(case)
        slot.update(case=case, started=time.monotonic())
        return slot

    try:
        for cpu in worker_cpus:
            if pending:
                slots.append(start(cpu))
        while slots:
            ready = wait([slot["connection"] for slot in slots], timeout=0.05)
            for slot in list(slots):
                record = None
                if slot["connection"] in ready:
                    try:
                        record = slot["connection"].recv()
                    except (EOFError, OSError):
                        record = {
                            **slot["case"]["job"],
                            "input_sha256": slot["case"]["input_sha256"],
                            "status": "error",
                            "error": "worker exited without a result",
                        }
                elif time.monotonic() - slot["started"] >= timeout_seconds:
                    record = {
                        **slot["case"]["job"],
                        "input_sha256": slot["case"]["input_sha256"],
                        "status": "timeout",
                        "timeout_seconds": timeout_seconds,
                        "worker_cpu": slot["cpu"],
                    }
                    _stop_worker(slot)
                if record is None:
                    continue
                # Stop other CPU work before handing an error back to the caller.
                if record["status"] == "error":
                    for active in slots:
                        _stop_worker(active)
                    slots.clear()
                    yield record
                    return
                yield record
                if pending:
                    if record["status"] == "timeout":
                        slots[slots.index(slot)] = start(slot["cpu"])
                    else:
                        case = pending.popleft()
                        slot["connection"].send(case)
                        slot.update(case=case, started=time.monotonic())
                else:
                    if record["status"] != "timeout":
                        _stop_worker(slot)
                    slots.remove(slot)
    finally:
        for slot in slots:
            _stop_worker(slot)


def run_benchmarks(
    output_dir: Path,
    profile_name="full",
    workers=None,
    algorithm_names=None,
    *,
    corpus_path=None,
    timing_blocks=None,
    timeout_seconds=600.0,
    rebuild=True,
    machine_label=None,
) -> dict[str, Any]:
    from benchmark.privacy import machine_label as validate_machine_label

    machine_label = validate_machine_label(machine_label)
    if profile_name not in suite.PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    profile = suite.PROFILES[profile_name]
    algorithm_names = algorithm_names or ["default"]
    if algorithm_names != ["default"]:
        raise ValueError("the runner supports exactly one algorithm: default")
    workers = 1 if workers is None else workers
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    timing_blocks = profile.timing_blocks if timing_blocks is None else timing_blocks
    if type(timing_blocks) is not int or timing_blocks < 2:
        raise ValueError("at least two timing blocks are required")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout must be finite and positive")
    worker_cpus = _first_logical_cpu_per_core()
    if workers > len(worker_cpus):
        raise ValueError(f"only {len(worker_cpus)} physical cores are available")
    worker_cpus = worker_cpus[:workers]
    if corpus_path is None:
        cases = corpus.make_cases(suite.build_jobs(profile, algorithm_names))
    else:
        cases = corpus.load_cases(Path(corpus_path))
        if any(case["job"]["algorithm"] != "default" for case in cases):
            raise ValueError("corpus contains an unsupported algorithm")
    corpus.validate_cases(cases)
    source = provenance.identify_source()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "benchmark_schema_version": suite.BENCHMARK_SCHEMA_VERSION,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine_label": machine_label,
        "platform": platform.system() + "-" + platform.machine(),
        "cpu_model": _cpu_model(),
        "cpu_governors": _cpu_governors(worker_cpus),
        "python_version": platform.python_version(),
        "rpack_version": re.search(
            r'^__version__ = "([^"]+)"',
            (provenance.ROOT / "rpack/__init__.py").read_text(),
            re.M,
        )[1],
        "workers": workers,
        "worker_cpus": worker_cpus,
        "measurement_mode": "latency" if workers == 1 else "concurrent",
        "profile": profile_name,
        "algorithms": algorithm_names,
        "target_time_ns": profile.target_time_ns,
        "max_repeat": profile.max_repeat,
        "timing_blocks": timing_blocks,
        "timeout_seconds": timeout_seconds,
        "source": source,
        "git_revision": source["git_revision"],
        "corpus_file": "corpus.jsonl.gz",
        "corpus_sha256": corpus.corpus_digest(cases),
        "job_grid_sha256": suite.job_grid_sha256(
            suite.record_key(c["job"]) for c in cases
        ),
        "expected_job_count": len(cases),
        "completed_job_count": 0,
        "results_file": "results.jsonl",
        "results_compression": "none",
        "status": "running",
        "outcomes": {},
    }
    write_json(output_dir / "manifest.json", manifest)
    started = time.monotonic()
    records_path = output_dir / "results.jsonl"
    outcomes = Counter()
    stream = None
    try:
        corpus.write_cases(output_dir / manifest["corpus_file"], cases)
        manifest["corpus_file_sha256"] = sha256_file(
            output_dir / manifest["corpus_file"]
        )
        provenance.source_archive(output_dir / "source.tar.gz", source)
        manifest["source_archive_sha256"] = sha256_file(output_dir / "source.tar.gz")
        manifest["build"] = (
            provenance.build_extension(output_dir / "build.log") if rebuild else None
        )
        runtime_root = output_dir / "runtime" if rebuild else provenance.ROOT
        import importlib.machinery

        binaries = [
            runtime_root / "rpack" / ("_core" + suffix)
            for suffix in importlib.machinery.EXTENSION_SUFFIXES
        ]
        binaries = [path for path in binaries if path.is_file()]
        if len(binaries) != 1:
            raise RuntimeError(
                "expected exactly one native extension for this interpreter"
            )
        binary = binaries[0]
        manifest["extension_sha256"] = sha256_file(binary)
        manifest["extension_filename"] = binary.name
        manifest["build_seconds"] = time.monotonic() - started
        shuffle_seed = suite.stable_seed(
            suite.BASE_SEED, "job-order", manifest["corpus_sha256"]
        )
        manifest["job_order_seed"] = shuffle_seed
        random.Random(shuffle_seed).shuffle(cases)
        write_json(output_dir / "manifest.json", manifest)
        print(
            f"Running {len(cases)} jobs, {timing_blocks} blocks, {workers} worker(s), "
            f"{timeout_seconds:g}s deadline/job on CPUs {worker_cpus}.",
            flush=True,
        )
        measured_at = time.monotonic()
        last_update = measured_at
        stream = _execute_cases(
            cases,
            worker_cpus,
            profile.target_time_ns,
            profile.max_repeat,
            timing_blocks,
            timeout_seconds,
            runtime_root=runtime_root,
        )
        with records_path.open("x", encoding="utf-8") as results:
            for record in stream:
                results.write(
                    json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
                )
                results.flush()
                outcomes[record["status"]] += 1
                manifest["completed_job_count"] += 1
                manifest["outcomes"] = dict(outcomes)
                if record["status"] == "error":
                    raise RuntimeError(record["error"])
                completed = manifest["completed_job_count"]
                now = time.monotonic()
                if (
                    completed % 50 == 0
                    or now - last_update >= 30
                    or completed == len(cases)
                ):
                    manifest["measurement_seconds"] = now - measured_at
                    write_json(output_dir / "manifest.json", manifest)
                    print(
                        f"[{completed}/{len(cases)}] elapsed={now-measured_at:.1f}s "
                        f"outcomes={dict(outcomes)}",
                        flush=True,
                    )
                    last_update = now
        manifest["measurement_seconds"] = time.monotonic() - measured_at
        if provenance.identify_source()["source_sha256"] != source["source_sha256"]:
            raise RuntimeError("sources changed during the benchmark")
        if sha256_file(binary) != manifest["extension_sha256"]:
            raise RuntimeError("native extension changed during the benchmark")
        manifest["status"] = "complete"
    except BaseException as exc:
        manifest["status"] = (
            "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        )
        manifest["error"] = str(exc)
        raise
    finally:
        if stream is not None:
            stream.close()
        manifest["duration_seconds"] = time.monotonic() - started
        manifest["finished_timestamp_utc"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        if records_path.exists():
            manifest["results_sha256"] = sha256_file(records_path)
            manifest["results_uncompressed_sha256"] = manifest["results_sha256"]
        write_json(output_dir / "manifest.json", manifest)
    print(f"Results written to {records_path}", flush=True)
    return manifest
