#!/usr/bin/env python3
"""Plot output of benchmark"""

# Built-in
import argparse
import pathlib
import struct
import mmap

# Third-party
import matplotlib
import matplotlib.pyplot as plt


def main(args):
    dt = list()
    rho = list()
    with open(args.file, "r+b") as fh:
        with mmap.mmap(fh.fileno(), 0) as mm:
            records = struct.iter_unpack("ff", mm)
            for duration, density in records:
                dt.append(duration)
                rho.append(density)
    dt.sort()
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle(args.file.name)
    ax[0].semilogy(dt)
    ax[0].grid(True)
    ax[0].set_title("Computational duration")
    ax[0].set_ylabel("Seconds")
    ax[0].set_xlabel("Rectangles")
    ax[1].hist(rho, bins=50, density=True, rwidth=0.9)
    ax[1].set_title("Packing density distribution")
    ax[1].set_xlabel("Packing density")
    plt.tight_layout()
    plt.show()


parser = argparse.ArgumentParser()
parser.add_argument(
    "file",
    type=pathlib.Path,
    help="Binary output file from benchmark.",
)

if __name__ == "__main__":
    args = parser.parse_args()
    try:
        main(args)
    except KeyboardInterrupt:
        print("Bye")
