#!/usr/bin/env python3
"""Benchmark rpack"""

# Built-in
import argparse
import asyncio
import concurrent.futures
import datetime as dt
import json
import pathlib
import platform
import random
import struct
import timeit

# Project
import rpack

random.seed(123)


def rectangles_unif_side(n: int, m: int) -> list[tuple[float, float]]:
    """Return list of `n` rec. with random side lengths `unif{0, m}`"""
    return [(random.randint(1, m), random.randint(1, m)) for _ in range(n)]


def _measurement(func, sizes):
    duration = min(
        timeit.repeat("_ = func(sizes)", repeat=10, number=1, globals=locals())
    )
    pos = func(sizes)
    density = rpack.packing_density(sizes, pos)
    return duration, density, sizes  # Return sizes as well


async def main(args):
    n, m = args.number_of_rectangles, args.max_side_length
    with concurrent.futures.ProcessPoolExecutor() as exe:
        max_duration = 0
        slowest_sizes = None

        async def measurement():
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                exe,
                _measurement,
                rpack.pack,
                rectangles_unif_side(n, m),
            )

        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base_filename = f"{timestamp}_{n}n_{m}m_py{platform.python_version()}"
        bin_filename = base_filename + ".bin"
        json_filename = base_filename + "_slowest.json"

        with open(args.output_dir / bin_filename, "ab") as fh:
            pending = set()
            samples = 0
            try:
                while True:
                    while len(pending) < args.cpus:
                        pending.add(asyncio.create_task(measurement()))
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in done:
                        duration, density, sizes = await t
                        fh.write(struct.pack("ff", duration, density))
                        # print(duration, density)

                        # Track the slowest case
                        if duration > max_duration:
                            max_duration = duration
                            slowest_sizes = sizes

                        samples += 1
                        if samples >= args.samples:
                            break
                    if samples >= args.samples:
                        break
            finally:
                if slowest_sizes:
                    # Save the slowest case to JSON
                    slowest_case = {
                        "duration": max_duration,
                        "rectangles": slowest_sizes,
                    }
                    with open(args.output_dir / json_filename, "w") as json_file:
                        json.dump(slowest_case, json_file, indent=2)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--number-of-rectangles",
    "-n",
    type=int,
    default=100,
    help="Number of rectangles to pack (default: %(default)s).",
)
parser.add_argument(
    "--max-side-length",
    "-m",
    type=int,
    default=1000,
    help="Max side length of random rectangle (default: %(default)s).",
)
parser.add_argument(
    "--samples",
    type=int,
    default=float("inf"),
    help="Number of samples to compute (default: %(default)s).",
)
parser.add_argument(
    "--cpus",
    "-c",
    type=int,
    default=10,
    help="Number of CPUs to use (default: %(default)s).",
)
parser.add_argument(
    "--output-dir",
    "-o",
    type=pathlib.Path,
    default=pathlib.Path.cwd(),
    help="Output directory (default: %(default)s).",
)


if __name__ == "__main__":
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("Bye")
