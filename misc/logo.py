"""Module for generating the rectangle-packer logo"""

# Built-in
import os
import random
import subprocess

# PyPI
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mtick
import  matplotlib.animation as mani
from matplotlib.backends.backend_pdf import PdfPages
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np

# Project
import rpack
from misc.recstat import PlotPacking, best_first

# Select a non-interactive backend so we can run on a server
matplotlib.use("Agg")


def candidates():
    """Find bbox with golden ratio proportions"""
    cands = list()
    try:
        i = 0
        while True:
            i += 1
            random.seed(i)
            sizes = [(random.randint(50, 1000), random.randint(50, 1000))
                     for _ in range(random.randint(30, 40))]
            pos = rpack.pack(sizes)
            rho = rpack.packing_density(sizes, pos)
            w, h = rpack.bbox_size(sizes, pos)
            if abs(w/h - 1.61803398875) < 0.01:
                print('Found candidate:', rho, 'seed', i)
                cands.append((rho, sizes, pos, i))
    except KeyboardInterrupt:
        pass
    cands.sort(reverse=True)
    return cands[0:10]


def searcher(output_dir):
    for i, (rho, sizes, pos, seed) in enumerate(candidates()):
        print(i, rho, seed)
        file = os.path.join(output_dir, f'{i:02}_logo_{seed}')
        p = PlotPacking(sizes, pos, trim=True)
        for spine in p.ax.spines.values():
            spine.set_linewidth(2)
        p.animation(file, 1, 0, dpi=40)
        p = PlotPacking(sizes, pos, trim=True)
        for spine in p.ax.spines.values():
            spine.set_linewidth(2)
        while p.feed():
            pass
        p.save(file)


def logo(output_dir='.'):
    """Create GIF logo used in sphinx documentation"""
    random.seed(232460)
    sizes = [(random.randint(50, 1000), random.randint(50, 1000))
             for _ in range(random.randint(30, 40))]
    pos = rpack.pack(sizes)
    # Sort the rectangles so the animation will plot them from left to
    # right.
    sizes = [s for s, _ in sorted(zip(sizes, pos), key=lambda x: x[1])]
    pos.sort()
    # Create animation
    p = PlotPacking(sizes, pos, trim=True)
    for spine in p.ax.spines.values():
        spine.set_linewidth(0)
    p.animation(os.path.join(output_dir, f'logo'), 1, 0, dpi=40)
    p = PlotPacking(sizes, pos, trim=True)
    for spine in p.ax.spines.values():
        spine.set_linewidth(0)
    while p.feed():
        pass
    p.save(os.path.join(output_dir, f'logo'))
    # Post process gif to only loop animation one time.
    subprocess.run('convert -loop 1 logo.gif logo.gif', shell=True, check=True)


if __name__ == '__main__':
    logo()
