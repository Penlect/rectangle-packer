#!/usr/bin/env python3
"""Visualize rpack packing & benchmark results

Sync files from Bucket:

$ gsutil -m rsync -r gs://bucket.penlect.com/rpack artifacts/

"""

# Built-in
import argparse
import os
import re
import pickle
import math
from pathlib import Path

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

# Select a non-interactive backend so we can run on a server
matplotlib.use("Agg")

# Filename pattern of measurement files
REGEX_FILE = re.compile(r'unif_side(\d+)n(\d+)m.pickle')
IMG_EXT = frozenset({'png', 'svg', 'pdf'})


def load(directory):
    """Load measurements from directory"""
    data = dict()
    for f in Path(directory).iterdir():
        match = REGEX_FILE.match(f.name)
        if match:
            n, m = match.groups()
            n, m = int(n), int(m)
            with open(f, 'rb') as h:
                data[n, m] = list()
                while True:
                    try:
                        data[n, m].append(pickle.load(h))
                    except EOFError:
                        break
    return data


def load_simple(directory, prefix):
    data = list()
    for f in Path(directory).iterdir():
        if f.name.startswith(prefix):
            with open(f, 'rb') as h:
                while True:
                    try:
                        rec, pos = pickle.load(h)
                    except EOFError:
                        break
                    else:
                        data.append((rec, pos))
            break
    return data


def plot_time(ax, mean_t):
    # Computation time

    mean_t = list()
    mean_f = list()
    for key in sorted(data):
        t, a, p = data[key]
        mean_t.append(sum(t)/len(t)/1e9)
        f = [aa/pp for aa, pp in zip(a, p)]
        mean_f.append(sum(f)/len(f))
    mean_t = np.array(mean_t).reshape((10, 10))
    mean_f = np.array(mean_f).reshape((10, 10))

    im = ax.imshow(
        mean_t, origin='lower', interpolation='none')
    ct = ax.contour(
        mean_t, levels=[1], origin='lower', colors=['red'])
    ax.clabel(ct, ct.levels, inline=True, fmt='%r sec')
    ax.set_xticklabels([100*i for i in range(1, 11)])
    ax.set_yticklabels([10*i for i in range(1, 11)])
    ax.set_xticks([i for i in range(0, 10)])
    ax.set_yticks([i for i in range(0, 10)])
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    cb = plt.colorbar(im, cax=cax)
    ax.set_title('Computation time (sec)')
    ax.set_xlabel('size')
    ax.set_ylabel('rectangles')


def asdf_plot_packing_density(ax, mean_f):
    # Computation time
    im = ax.imshow(
        mean_f, origin='lower', interpolation='none')
    ct = ax.contour(
        mean_f, levels=[np.mean(mean_f)], origin='lower', colors=['red'])
    ax.clabel(ct, ct.levels, inline=True, fmt='%.1f %%')
    ax.set_xticklabels([100*i for i in range(1, 11)])
    ax.set_yticklabels([10*i for i in range(1, 11)])
    ax.set_xticks([i for i in range(0, 10)])
    ax.set_yticks([i for i in range(0, 10)])
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    cb = plt.colorbar(im, cax=cax)
    ax.set_title('Packing density (%)')
    ax.set_xlabel('size')


def plot_packing_density_by_n(data):
    m = 1_000
    x = list()
    for n in range(10, 101, 10):
        f = list()
        for rec, pos, _ in data[n, m]:
            w, h = rpack.enclosing_size(rec, pos)
            a = sum(x*y for x, y in rec)
            f.append(a/(w*h))
        x.append(f)

    fig, ax = plt.subplots(tight_layout=True)
    bplot = ax.boxplot(
        x,
        sym='.',
        vert=True,
        patch_artist=True,
        showfliers=True,
        labels=list(range(10, 101, 10)),
        showmeans=True,
        medianprops=dict(color='black')
    )
    # fill with colors
    for patch in bplot['boxes']:
        patch.set_facecolor('lightblue')
    # ax.set_ylim([0.7, None])
    ax.yaxis.grid(True)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.yaxis.set_major_locator(mtick.MultipleLocator(0.05))
    ax.yaxis.set_minor_locator(mtick.MultipleLocator(0.01))
    ax.set_title(rf'Packing density, rectangle side lengths ~ $Unif\{{1, {m}\}}$')
    ax.set_xlabel('Number of rectangles')

    for ext in IMG_EXT:
        plt.savefig(os.path.join(args.output_dir, f'packing_density_by_n.{ext}'))
    fig.clf()
    plt.close()


def plot_packing_density_by_m(data):
    n = 100
    m = 1_000
    x = list()
    total = list()
    for m in range(100, 1001, 100):
        f = list()
        for rec, pos, _ in data[100, m]:
            w, h = rpack.enclosing_size(rec, pos)
            a = sum(x*y for x, y in rec)
            f.append(a/(w*h))
        x.append(f)
        total.extend(f)
    x.append(total)

    fig, ax = plt.subplots(tight_layout=True)
    ax.axhline(
        np.array(total).mean(),
        color=matplotlib.rcParams['boxplot.meanprops.markerfacecolor'],
        linewidth=1,
        linestyle=':'
    )
    bplot = ax.boxplot(
        x,
        sym='.',
        vert=True,
        patch_artist=True,
        labels=list(range(100, 1001, 100)) + ['total'],
        # positions=list(range(1, 11)) + [11.25],
        # widths=[0.5]*10 + [1],
        showmeans=True,
        medianprops=dict(color='black')
    )
    # fill with colors
    colors = ['lightblue']*10 + ['lightgreen']
    for patch, color in zip(bplot['boxes'], colors):
        patch.set_facecolor(color)
    # ax.set_xlim([None, 13])
    ax.yaxis.grid(True)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
    ax.yaxis.set_major_locator(mtick.MultipleLocator(0.01))
    ax.yaxis.set_minor_locator(mtick.MultipleLocator(0.001))
    ax.set_title('Packing density')
    ax.set_xlabel(rf'rectangle side lengths ~ $Unif\{{1, m\}}$, ${n} \leq m \leq {m}$')

    for ext in IMG_EXT:
        plt.savefig(os.path.join(args.output_dir, f'packing_density_by_m.{ext}'))
    fig.clf()
    plt.close()


def plot_enclosing(data):
    w = list()
    h = list()

    fig, ax = plt.subplots(tight_layout=True)
    ax.grid(True)
    m = 1_000
    # the scatter plot:
    for n in [10, 20, 30, 50, 100]:
        ew = list()
        eh = list()
        for rec, pos, t in data[n, m]:
            w, h = rpack.enclosing_size(rec, pos)
            ew.append(w)
            eh.append(h)
        ew = np.array(ew)/math.sqrt(n)
        eh = np.array(eh)/math.sqrt(n)
        # f = [aa/(w*h) for aa, (w, h) in zip(a, zip(ew, eh))]
        color = 'black' if n == 100 else None
        ax.scatter(ew, eh, c=color, s=0.2, label=f'$n = {n}$')

    ax.legend(markerscale=5)
    ax.set_aspect('equal')
    ax.set_xlim([0, None])
    ax.set_ylim([0, None])
    ax.set_title(
        'Resulting enclosings,\n'
        rf'$n$ = No. rectangles, side lengths ~ $Unif\{{1, {m}\}}$')
    ax.set_ylabel(r'Enclosing height / $\sqrt{n}$')
    ax.set_xlabel(r'Enclosing width / $\sqrt{n}$')
    for ext in IMG_EXT:
        plt.savefig(os.path.join(args.output_dir, f'enclosing.{ext}'))
    fig.clf()
    plt.close()


def plot_computation_time_by_n(data):
    x = list(range(10, 101, 10))
    y = list()
    s = list()
    m = 1_000
    for n in x:
        t = np.array([(ns/1e9) for rec, pos, ns in data[n, m]])
        t_mean = t.mean()
        t_std = t.std()
        y.append(t_mean)
        s.append(t_std)
    y = np.array(y)
    s = np.array(s)

    pol = np.polyfit(x, y, 3)
    p = np.poly1d(pol)
    yy = [p(xx) for xx in x]

    fig, ax = plt.subplots(tight_layout=True)
    ax.errorbar(x, y, s, fmt='--o', label='Measurement')
    ax.plot(x, yy, label='Polyfit $t = αn^3 + βn^2 + γn + δ$'
                         '\nα={:.2g}, β={:.2g} γ={:.2g} δ={:.2g}'.format(*pol))
    ax.grid(True)
    ax.xaxis.set_major_locator(mtick.MultipleLocator(10))
    ax.set_title(rf'Computation time, rectangle side lengths ~ $Unif\{{1, {m}\}}$')
    ax.set_xlabel('Number of rectangles')
    ax.set_ylabel('Seconds')
    ax.legend(loc='upper left')

    for ext in IMG_EXT:
        plt.savefig(os.path.join(args.output_dir, f'computation_time_by_n.{ext}'))
    fig.clf()
    plt.close()


def plot_computation_time_by_m(data):
    x = list(range(100, 1001, 100))
    n = 100
    y = list()
    s = list()
    for m in x:
        t = np.array([(ns/1e9) for rec, pos, ns in data[n, m]])
        t_mean = t.mean()
        t_std = t.std()
        y.append(t_mean)
        s.append(t_std)
    y = np.array(y)
    s = np.array(s)

    pol = np.polyfit(x, y, 1)
    p = np.poly1d(pol)
    yy = [p(xx) for xx in x]

    fig, ax = plt.subplots(tight_layout=True)
    ax.errorbar(x, y, s, fmt='--o', label='Measurement')
    ax.plot(x, yy, label='Polyfit $t = αn + β$'
                         '\nα={:.2g}, β={:.2g}'.format(*pol))
    ax.grid(True)
    ax.xaxis.set_major_locator(mtick.MultipleLocator(n))
    ax.set_title(f'Computation time, {n} rectangles')
    ax.set_xlabel(rf'rectangle side lengths ~ $Unif\{{1, m\}}$, ${n} \leq m \leq {m}$')
    ax.set_ylabel('Seconds')
    ax.legend(loc='upper left')

    for ext in IMG_EXT:
        plt.savefig(os.path.join(args.output_dir, f'computation_time_by_m.{ext}'))
    fig.clf()
    plt.close()


def rectangle_color(w, h):
    r = min(w, h)/max(w, h)/2
    if h < w:
        r = 1 - r
    r = r/2 + 0.3
    return plt.get_cmap('viridis')(r)


class PlotPacking:

    def __init__(self, rec, pos, gridlines=False, title='', trim=False):
        """Initialization of PlotPacking"""
        self.rec = rec
        self.pos = pos
        self.gridlines = gridlines
        self.index = None
        self.encl_w, self.encl_h = rpack.enclosing_size(rec, pos)
        self.density = sum(w*h for w, h in rec)/(self.encl_w*self.encl_h)
        if trim:
            self.fig = plt.figure(figsize=(6, 6*self.encl_h/self.encl_w))
            self.ax = self.fig.add_axes([0.01, 0.01, 0.98, 0.98])
        else:
            self.fig, self.ax = plt.subplots(tight_layout=True)
            self.ax.set_aspect('equal')
        self.ax.invert_yaxis()
        self.ax.set_xlim([0, self.encl_w])
        self.ax.set_ylim([self.encl_h, 0])
        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        if title and not trim:
            self.ax.set_title(
                f'Packing density {100*self.density:.2f}% '
                f'({self.encl_w} x {self.encl_h})' + title)

    def feed(self, *args):
        artists = list()
        if self.index is None:
            self.index = 0
            return [self.ax]
        try:
            w, h = self.rec[self.index]
            x, y = self.pos[self.index]
        except IndexError:
            return []
        else:
            p = patches.Rectangle(
                (x, y), w, h,
                edgecolor='k',
                facecolor=rectangle_color(w, h)
            )
            self.ax.add_patch(p)
            artists.append(p)
            if self.gridlines:
                hline = self.ax.axhline(y+h, color='k', linestyle='-', linewidth=0.5)
                vline = self.ax.axvline(x+w, color='k', linestyle='-', linewidth=0.5)
                artists.append(hline)
                artists.append(vline)
            self.index += 1
            return artists

    def save(self, output_file):
        for ext in IMG_EXT:
            plt.savefig(f'{output_file}.{ext}', bbox_inches='tight')
        self.fig.clf()
        plt.close()

    def animation(self, output_file, pack_duration=3, duration=10, **kwargs):
        frames = list(range(len(self.rec)))
        interval = int(1_000*pack_duration/len(frames))
        frames.extend([None] * int(len(frames)*(duration/pack_duration)))
        anim = mani.FuncAnimation(self.fig, self.feed, frames=frames, interval=interval)
        if 'dpi' not in kwargs:
            kwargs['dpi'] = 80
        anim.save(f'{output_file}.gif', writer='imagemagick', **kwargs)
        self.fig.clf()
        plt.close()


def packing_density(rec, pos):
    w, h = rpack.enclosing_size(rec, pos)
    return sum(x*y for x, y in rec)/(w*h)

def best_first(samples):
    x = list()
    for rec, pos, _ in samples:
        f = packing_density(rec, pos)
        x.append((f, rec, pos))
    x.sort(reverse=True)
    return x


def plot_packing_extremes(data):
    for n in [10, 100]:
        m = 1000
        toplist = best_first(data[n, m])
        for case in [('best', toplist[0]), ('worst', toplist[-1])]:
            name, (_, rec, pos) = case
            p = PlotPacking(
                rec, pos, title=f', {n} rectangles.')
            while p.feed():
                pass
            p.save(os.path.join(args.output_dir, f'packing_{name}_{n}'))


def plot_packing_golden_ratio(data):
    candidates = list()
    for n in range(40, 101, 10):
        for m in range(100, 1001, 100):
            for rec, pos, _ in data[n, m]:
                w, h = rpack.bbox_size(rec, pos)
                rho = rpack.packing_density(rec, pos)
                candidates.append((round(abs(w/h - 1.61803398875), 2), -rho, rec, pos))
    candidates.sort()
    _, _, rec, pos = candidates[0]
    p = PlotPacking(
        rec, pos, title=f', {len(rec)} rectangles.')
    while p.feed():
        pass
    p.save(os.path.join(args.output_dir, f'packing_phi'))


def plot_animations(data):
    candidates = list()
    for n in range(40, 101, 10):
        for m in range(100, 1001, 100):
            for rec, pos, _ in data[n, m]:
                w, h = rpack.bbox_size(rec, pos)
                rho = rpack.packing_density(rec, pos)
                candidates.append((round(abs(w/h - 0.61803398875), 2), -rho, rec, pos))
    candidates.sort()
    _, _, sizes, pos = candidates[0]
    # Sort the rectangles so the animation will plot them from left to
    # right.
    sizes = [s for s, _ in sorted(zip(sizes, pos), key=lambda x: x[1])]
    pos.sort()
    p = PlotPacking(sizes, pos, gridlines=True, trim=True)
    p.animation(os.path.join(args.output_dir, f'example_grid'), 60, 20)
    p = PlotPacking(sizes, pos, gridlines=True, trim=True)
    while p.feed():
        pass
    p.save(os.path.join(args.output_dir, f'example_grid'))


def plot_squares(directory):

    data = load_simple(directory, 'square')

    f = list()
    for (rec, pos) in data:
        w, h = rpack.enclosing_size(rec, pos)
        a = sum(x*y for x, y in rec)
        f.append(a/(w*h))

    with PdfPages(os.path.join(args.output_dir, 'squares.pdf')) as pdf:

        fig, ax = plt.subplots(tight_layout=True)
        ax.plot(list(range(1, len(f) + 1)), f)
        ax.grid(True)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
        ax.xaxis.set_major_locator(mtick.MultipleLocator(10))
        ax.set_title('Packing density, squares')
        ax.set_xlabel('Rectangle max side length (n)')
        pdf.savefig(figure=fig)
        for ext in IMG_EXT:
            plt.savefig(os.path.join(args.output_dir, f'squares_summary.{ext}'))
        fig.clf()
        plt.close()

        for n, (rec, pos) in enumerate(data, start=1):
            if n == 1:
                title = ', square 1x1'
            elif n == 2:
                title = ', squares 1x1 + 2x2'
            else:
                title = f', squares 1x1 ... {n}x{n}'
            p = PlotPacking(rec, pos, title=title)
            while p.feed():
                pass
            pdf.savefig(figure=p.fig)
            p.fig.clf()
            plt.close()


def plot_circums(directory):

    data = load_simple(directory, 'circum')

    f = list()
    for (rec, pos) in data:
        w, h = rpack.enclosing_size(rec, pos)
        a = sum(x*y for x, y in rec)
        f.append(a/(w*h))

    with PdfPages(os.path.join(args.output_dir, 'circum.pdf')) as pdf:

        fig, ax = plt.subplots(tight_layout=True)
        ax.plot(list(range(1, len(f) + 1)), f)
        ax.grid(True)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))
        ax.xaxis.set_major_locator(mtick.MultipleLocator(10))
        ax.set_title('Packing density, fixed circumference rectangles')
        ax.set_xlabel('Rectangle width + height (n)')
        pdf.savefig(figure=fig)
        for ext in IMG_EXT:
            plt.savefig(os.path.join(args.output_dir, f'circum_summary.{ext}'))
        fig.clf()
        plt.close()

        for n, (rec, pos) in enumerate(data, start=1):
            p = PlotPacking(
                rec, pos, title=f', nx1 ... 1xn, n={n}.')
            while p.feed():
                pass
            pdf.savefig(figure=p.fig)
            p.fig.clf()
            plt.close()


def main(args):
    os.makedirs(args.output_dir, exist_ok=True)
    data = load(args.input_dir)

    plot_computation_time_by_m(data)
    plot_packing_density_by_n(data)
    plot_packing_density_by_m(data)
    plot_computation_time_by_n(data)
    plot_enclosing(data)
    plot_packing_extremes(data)
    plot_animations(data)
    plot_squares(args.input_dir)
    plot_circums(args.input_dir)
    plot_packing_golden_ratio(data)


PARSER = argparse.ArgumentParser()
PARSER.add_argument(
    '--input-dir', '-i',
    # Example output_dir: /tmp/rpack/1.1.0-13-g18920b5-dirty/data
    type=str,
    default='/tmp/rpack/data',
    help='Data input directory.')
PARSER.add_argument(
    '--output-dir', '-o',
    # Example output_dir: /tmp/rpack/1.1.0-13-g18920b5-dirty/img
    type=str,
    default='/tmp/rpack/img',
    help='Images output directory.')

if __name__ == '__main__':
    args = PARSER.parse_args()
    main(args)
