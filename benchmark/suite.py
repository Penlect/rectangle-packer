"""Benchmark suite definitions for :mod:`rpack`."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import json
import math
import random
from typing import Callable

BENCHMARK_SCHEMA_VERSION = 2
BASE_SEED = 20260315

COUNT_SWEEP_SCALE = 1_000
COUNT_SWEEP_VALUES = (10, 20, 40, 80, 120, 160, 200)

SCALE_SWEEP_N = 64
SCALE_SWEEP_BASE_SCALE = 100
SCALE_SWEEP_VALUES = (
    1,
    4,
    16,
    64,
    256,
    1_024,
    4_096,
    16_384,
    65_536,
    262_144,
    1_048_576,
    4_194_304,
    16_777_216,
    67_108_864,
    268_435_456,
)

STRUCTURED_MAX_N = 100

PATHOLOGY_HEIGHTS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1_024, 2_048, 4_096)
PATHOLOGY_BASELINE_N = 10
PATHOLOGY_BASELINE_SCALE = 1_000_000
PATHOLOGY_RECTANGLES = (
    (936469, 1),
    (956023, 480880),
    (762663, 456585),
    (522456, 924841),
    (193372, 365467),
    (505745, 921750),
    (127245, 805540),
    (234482, 384004),
    (986956, 278825),
    (787627, 59839),
)

JOB_KEY_FIELDS = (
    "benchmark",
    "algorithm",
    "family",
    "n",
    "scale",
    "parameter",
    "instance",
    "seed",
)


def stable_seed(*parts: object) -> int:
    """Return a stable integer seed from structured input parts."""
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


def _log_uniform_int(rng: random.Random, low: int, high: int) -> int:
    """Sample an integer from a log-uniform distribution."""
    if low < 1:
        raise ValueError("low must be positive")
    value = math.exp(rng.uniform(math.log(low), math.log(high)))
    return max(low, min(high, int(round(value))))


def rectangles_uniform_sides(
    rng: random.Random, n: int, scale: int
) -> list[tuple[int, int]]:
    """Return rectangles with iid uniform side lengths."""
    return [(rng.randint(1, scale), rng.randint(1, scale)) for _ in range(n)]


def rectangles_log_uniform_sides(
    rng: random.Random, n: int, scale: int
) -> list[tuple[int, int]]:
    """Return rectangles with iid log-uniform side lengths."""
    return [
        (_log_uniform_int(rng, 1, scale), _log_uniform_int(rng, 1, scale))
        for _ in range(n)
    ]


def rectangles_area_aspect(
    rng: random.Random, n: int, scale: int
) -> list[tuple[int, int]]:
    """Return rectangles with broad areas and aspect ratios."""
    output: list[tuple[int, int]] = []
    max_area = scale * scale
    max_aspect = 16.0
    for _ in range(n):
        area = _log_uniform_int(rng, 1, max_area)
        aspect = math.exp(rng.uniform(-math.log(max_aspect), math.log(max_aspect)))
        width = max(1, int(round(math.sqrt(area * aspect))))
        height = max(1, int(round(math.sqrt(area / aspect))))
        output.append((width, height))
    return output


def rectangles_squares(n: int) -> list[tuple[int, int]]:
    """Return the square sequence ``1x1, 2x2, ..., nxn``."""
    return [(i, i) for i in range(n, 0, -1)]


def rectangles_fixed_perimeter(n: int) -> list[tuple[int, int]]:
    """Return all integer rectangles with fixed perimeter proxy ``w + h = n + 1``."""
    sizes = [(i, n - i + 1) for i in range(1, n + 1)]
    sizes.sort(key=lambda item: item[1], reverse=True)
    return sizes


def rectangles_thin_pathology(height: int) -> list[tuple[int, int]]:
    """Return the known thin-rectangle stress case with a variable first height."""
    sizes = list(PATHOLOGY_RECTANGLES)
    first_width, _ = sizes[0]
    sizes[0] = (first_width, height)
    return sizes


@dataclass(frozen=True)
class RandomFamily:
    """Definition of a random input family."""

    name: str
    label: str
    description: str
    generator: Callable[[random.Random, int, int], list[tuple[int, int]]]


RANDOM_FAMILIES = {
    "uniform": RandomFamily(
        name="uniform",
        label="Uniform sides",
        description="Independent side lengths sampled uniformly from [1, m].",
        generator=rectangles_uniform_sides,
    ),
    "log_uniform": RandomFamily(
        name="log_uniform",
        label="Log-uniform sides",
        description="Independent side lengths sampled log-uniformly from [1, m].",
        generator=rectangles_log_uniform_sides,
    ),
    "area_aspect": RandomFamily(
        name="area_aspect",
        label="Area/aspect mix",
        description=(
            "Areas are log-uniform on [1, m^2] and aspect ratios are "
            "log-uniform on [1/16, 16]."
        ),
        generator=rectangles_area_aspect,
    ),
}

COUNT_SWEEP_FAMILIES = tuple(RANDOM_FAMILIES)
SCALE_SWEEP_FAMILIES = tuple(RANDOM_FAMILIES)


@dataclass(frozen=True)
class BenchmarkProfile:
    """Benchmark intensity profile."""

    name: str
    count_instances: dict[int, int]
    scale_instances: int
    structured_repeats: int
    pathology_repeats: int
    pathology_baseline_instances: int
    target_time_ns: int
    max_repeat: int
    timing_blocks: int = 5
    scale_values: tuple[int, ...] = SCALE_SWEEP_VALUES
    structured_values: tuple[int, ...] = tuple(range(1, STRUCTURED_MAX_N + 1))
    scenario_instances: int = 16


PROFILES = {
    "smoke": BenchmarkProfile(
        name="smoke",
        count_instances={10: 2, 20: 2, 40: 2, 80: 1, 120: 1, 160: 1, 200: 1},
        scale_instances=2,
        structured_repeats=1,
        pathology_repeats=1,
        pathology_baseline_instances=4,
        target_time_ns=10_000_000,
        max_repeat=512,
        timing_blocks=3,
        scale_values=(1, 1_024, 16_777_216, 268_435_456),
        structured_values=(1, 10, 40, 100),
        scenario_instances=2,
    ),
    "full": BenchmarkProfile(
        name="full",
        count_instances={10: 256, 20: 256, 40: 192, 80: 128, 120: 96, 160: 64, 200: 48},
        scale_instances=48,
        structured_repeats=1,
        pathology_repeats=1,
        pathology_baseline_instances=160,
        target_time_ns=40_000_000,
        max_repeat=16_384,
        timing_blocks=5,
    ),
    "publication": BenchmarkProfile(
        name="publication",
        count_instances={
            10: 384,
            20: 384,
            40: 288,
            80: 192,
            120: 144,
            160: 96,
            200: 96,
            300: 12,
            400: 6,
        },
        scale_instances=96,
        structured_repeats=1,
        pathology_repeats=1,
        pathology_baseline_instances=256,
        target_time_ns=50_000_000,
        max_repeat=65_536,
        timing_blocks=7,
        scenario_instances=64,
    ),
}


@dataclass(frozen=True)
class Job:
    """One benchmark job."""

    benchmark: str
    algorithm: str
    family: str
    n: int | None = None
    scale: int | None = None
    parameter: int | None = None
    instance: int | None = None
    seed: int | None = None


def job_key(job: Job) -> tuple[object, ...]:
    """Return the canonical identity key for a benchmark job."""
    return tuple(getattr(job, field) for field in JOB_KEY_FIELDS)


def record_key(record: dict[str, object]) -> tuple[object, ...]:
    """Return the canonical identity key for a benchmark record."""
    try:
        return tuple(record[field] for field in JOB_KEY_FIELDS)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"record is missing required field {missing!r}") from exc


def job_grid_sha256(keys: Iterable[tuple[object, ...]]) -> str:
    """Return an order-independent digest of benchmark job identities."""
    serialized_keys = []
    for key in keys:
        if len(key) != len(JOB_KEY_FIELDS):
            raise ValueError(
                f"job key has {len(key)} fields; expected {len(JOB_KEY_FIELDS)}"
            )
        serialized_keys.append(
            json.dumps(
                dict(zip(JOB_KEY_FIELDS, key)),
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    digest = hashlib.sha256()
    for serialized_key in sorted(serialized_keys):
        digest.update(serialized_key.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_jobs(profile: BenchmarkProfile, algorithm_names: list[str]) -> list[Job]:
    """Build the full deterministic job grid for a benchmark run."""
    jobs: list[Job] = []

    for algorithm in algorithm_names:
        for family in COUNT_SWEEP_FAMILIES:
            for n in sorted(profile.count_instances):
                for instance in range(profile.count_instances[n]):
                    jobs.append(
                        Job(
                            benchmark="count_sweep",
                            algorithm=algorithm,
                            family=family,
                            n=n,
                            scale=COUNT_SWEEP_SCALE,
                            instance=instance,
                            seed=stable_seed(
                                BASE_SEED, "count_sweep", family, n, instance
                            ),
                        )
                    )

        for family in SCALE_SWEEP_FAMILIES:
            for scale in profile.scale_values:
                for instance in range(profile.scale_instances):
                    jobs.append(
                        Job(
                            benchmark="scale_sweep",
                            algorithm=algorithm,
                            family=family,
                            n=SCALE_SWEEP_N,
                            scale=scale,
                            instance=instance,
                            # Scale is intentionally omitted so the base geometry is fixed.
                            seed=stable_seed(
                                BASE_SEED, "scale_sweep", family, instance
                            ),
                        )
                    )

        for repeat in range(profile.structured_repeats):
            for n in profile.structured_values:
                jobs.append(
                    Job(
                        benchmark="structured",
                        algorithm=algorithm,
                        family="squares",
                        n=n,
                        instance=repeat,
                    )
                )
                jobs.append(
                    Job(
                        benchmark="structured",
                        algorithm=algorithm,
                        family="fixed_perimeter",
                        n=n,
                        instance=repeat,
                    )
                )

        for repeat in range(profile.pathology_repeats):
            for height in PATHOLOGY_HEIGHTS:
                jobs.append(
                    Job(
                        benchmark="pathology",
                        algorithm=algorithm,
                        family="thin_pathology",
                        n=len(PATHOLOGY_RECTANGLES),
                        parameter=height,
                        instance=repeat,
                    )
                )

        for instance in range(profile.pathology_baseline_instances):
            jobs.append(
                Job(
                    benchmark="pathology",
                    algorithm=algorithm,
                    family="pathology_guardrail",
                    n=PATHOLOGY_BASELINE_N,
                    scale=PATHOLOGY_BASELINE_SCALE,
                    instance=instance,
                    seed=stable_seed(BASE_SEED, "pathology_guardrail", instance),
                )
            )

        for family in SCENARIO_FAMILIES:
            instances = profile.scenario_instances if family in RANDOM_SCENARIOS else 1
            for instance in range(instances):
                jobs.append(
                    Job(
                        benchmark="scenario",
                        algorithm=algorithm,
                        family=family,
                        n=SCENARIO_COUNTS[family],
                        instance=instance,
                        seed=stable_seed(BASE_SEED, "scenario", family, instance),
                    )
                )

    return jobs


SCENARIO_COUNTS = {
    "bigint_approximate": 32,
    "width_limited_sprites": 64,
    "height_limited_sprites": 64,
    "duplicate_tiles": 256,
    "bounded_exact_grid": 64,
    "bounded_impossible": 10,
    "partial_impossible": 10,
    "one_unit_improvement": 4,
    "large_height": 2,
}
SCENARIO_FAMILIES = tuple(SCENARIO_COUNTS)
RANDOM_SCENARIOS = frozenset(
    (
        "bigint_approximate",
        "width_limited_sprites",
        "height_limited_sprites",
        "duplicate_tiles",
    )
)


def generate_input(job: Job) -> dict[str, object]:
    """Materialize a portable workload, including constraints and expected outcome."""
    rng = random.Random(job.seed)
    max_width = max_height = None
    expected_status = "ok"
    if job.benchmark == "count_sweep":
        sizes = RANDOM_FAMILIES[job.family].generator(rng, job.n, job.scale)
    elif job.benchmark == "scale_sweep":
        base = RANDOM_FAMILIES[job.family].generator(rng, job.n, SCALE_SWEEP_BASE_SCALE)
        sizes = [(w * job.scale, h * job.scale) for w, h in base]
    elif job.family == "squares":
        sizes = rectangles_squares(job.n)
    elif job.family == "fixed_perimeter":
        sizes = rectangles_fixed_perimeter(job.n)
    elif job.family == "thin_pathology":
        sizes = rectangles_thin_pathology(job.parameter)
    elif job.family == "pathology_guardrail":
        sizes = rectangles_uniform_sides(rng, job.n, job.scale)
    elif job.family == "bigint_approximate":
        # Adjacent values force both axis gcds to one, preserving huge inputs
        # through exact reduction so the conservative approximation is exercised.
        factor = 1 << 70
        sizes = [
            (
                rng.randint(8, 128) * factor + rng.randrange(1, 100),
                rng.randint(8, 128) * factor + rng.randrange(1, 100),
            )
            for _ in range(job.n)
        ]
        sizes[:2] = [
            (32 * factor + 1, 32 * factor + 1),
            (32 * factor + 2, 32 * factor + 2),
        ]
    elif job.family in ("width_limited_sprites", "height_limited_sprites"):
        sizes = [(rng.randint(8, 256), rng.randint(8, 256)) for _ in range(job.n)]
        if job.family == "width_limited_sprites":
            max_width = 512
        else:
            max_height = 512
    elif job.family == "duplicate_tiles":
        sizes = [
            (rng.choice((8, 16, 32, 64)), rng.choice((8, 16, 32, 64)))
            for _ in range(job.n)
        ]
    elif job.family == "bounded_exact_grid":
        sizes = [(16, 16)] * job.n
        max_width = max_height = 128
    elif job.family == "bounded_impossible":
        sizes = [(32, 32)] * job.n
        max_width = 31
        expected_status = "infeasible"
    elif job.family == "partial_impossible":
        sizes = [(16, 16)] * job.n
        max_width = max_height = 32
        expected_status = "infeasible"
    elif job.family == "one_unit_improvement":
        sizes = [(7, 1), (1, 3), (1, 2), (2, 4)]
    elif job.family == "large_height":
        sizes = [(1, 1 << 31)] * 2
    else:
        raise ValueError(f"unknown benchmark workload: {job}")
    return {
        "sizes": [list(size) for size in sizes],
        "max_width": max_width,
        "max_height": max_height,
        "expected_status": expected_status,
    }
