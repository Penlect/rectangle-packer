#!/usr/bin/env python3
"""Benchmark rpack package

This module test rpack performance and packing density quality.

These are the performance tests:

* Uniform side length test
* Sequence of squares test
* Uniform area test (todo)

# TODO Square-packing problem NxN

"""

# Built-in
import asyncio
import argparse
import concurrent.futures
import multiprocessing
import os
import pickle
import random
import statistics
import time
import math

# Package
import rpack

# Random seed fixed - make benchmark repeatable
SEED = 81611

# Number of rectangles to generate for each size
N_STEP = 10
N_MAX = 100

# Random side-length of rectangles
M_STEP = 100
M_MAX = 1_000

SQUARE_MAX = 100
CIRCUM_MAX = 100


# Rectangle sources
# =================

def rectangles_square(n: int):
    """Return `n` square rectangles from (1, 1) to (n, n)"""
    return [(i, i) for i in reversed(range(1, n + 1))]

def rectangles_circum(n: int):
    """Return `n` fixed circumference rectangles, w + h = n"""
    output = list()
    for i in range(1, n + 1):
        output.append((i, n - i + 1))
    output.sort(key=lambda x: x[1], reverse=True)
    return output

def rectangles_unif_side(n: int, m: int):
    """Return list of `n` rec. with random side lengths `unif{0, m}`"""
    return [(random.randint(1, m), random.randint(1, m))
            for _ in range(n)]

def rectangles_unif_area(n: int, m: int):
    """Return list of `n` rec. with random area `unif{0, m}`"""
    output = list()
    for _ in range(n):
        area = random.randint(1, m)
        width = random.randint(1, area)
        height = area//width
        # Randomly transpose rectangle
        if random.choice([True, False]):
            output.append((height, width))
        output.append((width, height))
    return output

# Executor tasks
# ==============

async def run_rectangles_square(exe, output_dir: str):
    futures = dict()
    loop = asyncio.get_running_loop()
    for n in range(1, SQUARE_MAX + 1):
        rec = rectangles_square(n)
        f = loop.run_in_executor(exe, rpack.pack, rec)
        futures[f] = rec
    output_file = os.path.join(output_dir, f'square{SQUARE_MAX}.pickle')
    with open(output_file, 'wb') as out_f:
        for f, rec in futures.items():
            pos = await f
            pickle.dump((rec, pos), out_f)
    print('Done:', output_file)


async def run_rectangles_circum(exe, output_dir: str):
    futures = dict()
    loop = asyncio.get_running_loop()
    for n in range(1, CIRCUM_MAX + 1):
        rec = rectangles_circum(n)
        f = loop.run_in_executor(exe, rpack.pack, rec)
        futures[f] = rec
    output_file = os.path.join(output_dir, f'circum{CIRCUM_MAX}.pickle')
    with open(output_file, 'wb') as out_f:
        for f, rec in futures.items():
            pos = await f
            pickle.dump((rec, pos), out_f)
    print('Done:', output_file)


def no_samples(n: int):
    b = math.log(100)/90
    a = 100*math.exp(b*100)
    return int(a*math.exp(-b*n))


def task(rec):
    # Measure time used by rpack.pack
    t0 = time.monotonic_ns()
    pos = rpack.pack(rec)
    t1 = time.monotonic_ns()
    return pos, t1 - t0


async def run_rectangles_random(exe, output_dir: str, rec_func):
    """Build arguments of multiprocess task"""
    futures = dict()
    loop = asyncio.get_running_loop()
    progress = dict()
    for n in range(N_STEP, N_MAX + 1, N_STEP):
        for m in range(M_STEP, M_MAX + 1, M_STEP):
            prefix = rec_func.__name__.replace('rectangles_', '')
            name = f'{prefix}{n:03}n{m:04}m.pickle'
            output_file = os.path.join(output_dir, name)
            if m == M_MAX:
                s = no_samples(n)
            elif n == N_MAX:
                s = 100
            else:
                s = 10
            progress[output_file] = s
            for _ in range(s):
                rec = rec_func(n, m)
                f = loop.run_in_executor(exe, task, rec)
                futures[f] = output_file, rec

    files = dict()
    try:
        for f, (output_file, rec) in futures.items():
            pos, dt = await f
            if output_file not in files:
                files[output_file] = open(output_file, 'wb')
            out_f = files[output_file]
            pickle.dump((rec, pos, dt), out_f)
            progress[output_file] -= 1
            if progress[output_file] == 0:
                del progress[output_file]
                print('Done:', output_file, end='. ')
                print('Files remaining:', len(progress))
    finally:
        for f in files.values():
            f.close()


async def main(args):
    random.seed(SEED)
    os.makedirs(args.output_dir, exist_ok=True)
    max_workers = args.max_workers
    with concurrent.futures.ProcessPoolExecutor(max_workers) as exe:
        await asyncio.gather(
            asyncio.create_task(run_rectangles_square(exe, args.output_dir)),
            asyncio.create_task(run_rectangles_circum(exe, args.output_dir)),
            asyncio.create_task(run_rectangles_random(exe, args.output_dir, rectangles_unif_side)),
            # asyncio.create_task(run_rectangles_random(exe, args.output_dir, rectangles_unif_area)),
        )


PARSER = argparse.ArgumentParser()
PARSER.add_argument(
    '--max-workers', '-j',
    type=int,
    default=min(30, multiprocessing.cpu_count() - 2),
    help='Max cpu count for workers.')
PARSER.add_argument(
    '--output-dir', '-o',
    # Example output_dir: /tmp/rpack/1.1.0-13-g18920b5-dirty/data
    type=str,
    default='/tmp/rpack/data',
    help='Measurements output directory.')

if __name__ == '__main__':
    args = PARSER.parse_args()
    asyncio.run(main(args))
