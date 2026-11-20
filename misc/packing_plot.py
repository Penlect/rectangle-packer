"""Render rectangle packings and animations used by the logo utility."""

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib import patches
from matplotlib import animation as mani

import rpack

IMG_EXT = frozenset(("png", "svg", "pdf"))


def rectangle_color(w, h):
    r = min(w, h) / max(w, h) / 2
    if h < w:
        r = 1 - r
    r = r / 2 + 0.3
    return plt.get_cmap("viridis")(r)


class PlotPacking:
    def __init__(self, rec, pos, gridlines=False, title="", trim=False):
        """Initialization of PlotPacking"""
        self.rec = rec
        self.pos = pos
        self.gridlines = gridlines
        self.index = None
        self.encl_w, self.encl_h = rpack.enclosing_size(rec, pos)
        self.density = sum(w * h for w, h in rec) / (self.encl_w * self.encl_h)
        if trim:
            self.fig = plt.figure(figsize=(6, 6 * self.encl_h / self.encl_w))
            self.ax = self.fig.add_axes([0.01, 0.01, 0.98, 0.98])
        else:
            self.fig, self.ax = plt.subplots(tight_layout=True)
            self.ax.set_aspect("equal")
        self.ax.invert_yaxis()
        self.ax.set_xlim([0, self.encl_w])
        self.ax.set_ylim([self.encl_h, 0])
        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        if title and not trim:
            self.ax.set_title(
                f"Packing density {100*self.density:.2f}% "
                f"({self.encl_w} x {self.encl_h})" + title
            )

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
                (x, y), w, h, edgecolor="k", facecolor=rectangle_color(w, h)
            )
            self.ax.add_patch(p)
            artists.append(p)
            if self.gridlines:
                hline = self.ax.axhline(y + h, color="k", linestyle="-", linewidth=0.5)
                vline = self.ax.axvline(x + w, color="k", linestyle="-", linewidth=0.5)
                artists.append(hline)
                artists.append(vline)
            self.index += 1
            return artists

    def save(self, output_file):
        for ext in IMG_EXT:
            plt.savefig(f"{output_file}.{ext}", bbox_inches="tight")
        self.fig.clf()
        plt.close()

    def animation(self, output_file, pack_duration=3, duration=10, **kwargs):
        frames = list(range(len(self.rec)))
        interval = int(1_000 * pack_duration / len(frames))
        frames.extend([None] * int(len(frames) * (duration / pack_duration)))
        anim = mani.FuncAnimation(self.fig, self.feed, frames=frames, interval=interval)
        if "dpi" not in kwargs:
            kwargs["dpi"] = 80
        anim.save(f"{output_file}.gif", writer="imagemagick", **kwargs)
        self.fig.clf()
        plt.close()
