
from collections import namedtuple
import datetime
import time
import math
import random

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.pyplot import cm
from matplotlib.animation import FuncAnimation, ImageMagickFileWriter
import numpy as np

import logging
import matplotlib.animation
matplotlib.animation._log.setLevel(logging.DEBUG)

import rpack

R = namedtuple('R', 'width height x y')

def enclosing_size(sizes, positions):
    """Return enclosing size of rectangles having sizes and positions"""
    rectangles = [R(*size, *pos) for size, pos in zip(sizes, positions)]
    width = max(r.width + r.x for r in rectangles)
    height = max(r.height + r.y for r in rectangles)
    return width, height


def fancy_plot(sizes, positions):
    width, height = enclosing_size(sizes, positions)
    limit = max(width, height)*1.1
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim([0, limit*0.95])
    ax.set_ylim([0, limit*0.74])
    ax.invert_yaxis()
    def update(ps):
        if ps is None:
            x, y = [width, width], [0, height]
            ax.plot(x, y, 'k', linewidth=2)
            x, y = [0, width], [height, height]
            ax.plot(x, y, 'k', linewidth=2)
            return
        pos, rec = ps
        x, y = pos
        w, h = rec
        ax.add_patch(
            patches.Rectangle(
                (x, y), w, h,
                edgecolor='k'
            )
        )

    x = list(zip(positions, sizes)) + [None]
    anim = FuncAnimation(fig, update, frames=x, interval=80, repeat_delay=3000)
    #anim.save('dynamic_images.mp4', dpi=80)
    anim.save('pack.gif', dpi=80, writer='imagemagick')
    fig.show()

def timeitstuff():
    import timeit

    y = list()
    x = list(range(100, 10_000, 100)) + list(range(10_000, 100_000, 1_000))

    try:
        for i, nr_tasks in enumerate(x):
            data = [random.random() for _ in range(nr_tasks)]
            t = timeit.repeat("rpack.group(data, 5)", globals=globals(),
                              number=10)
            t = min(t) / 10
            y.append(t)
            with open('log.txt', 'a') as f:
                f.write(str(t) + '\n')
            print(f'{i}/{len(x)}', t)
    finally:
        import matplotlib.pyplot as plt
        plt.plot(x[:len(y)], y)
        plt.show()

if __name__ == '__main__':
    from random import randint
    random.seed(a=13)
    sizes = [(randint(50, 300), randint(50, 300)) for _ in range(30)]
    sizes.sort(key=lambda r: -r[1])
    positions = rpack.pack(sizes)
    fancy_plot(sizes, positions)