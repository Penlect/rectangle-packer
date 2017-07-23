
from collections import namedtuple
import datetime
import time
import math
import random
from random import randint
random.seed(a=124)

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.pyplot import cm
import numpy as np
from pygit2 import Repository

import rpack

R = namedtuple('R', 'width height x y')

def enclosing_size(sizes, positions):
    """Return enclosing size of rectangles having sizes and positions"""
    rectangles = [R(*size, *pos) for size, pos in zip(sizes, positions)]
    width = max(r.width + r.x for r in rectangles)
    height = max(r.height + r.y for r in rectangles)
    return (width, height), rectangles


def plot(sizes, append=''):

    t0 = time.time()
    positions = rpack.pack(sizes)
    t1 = time.time()
    (width, height), rectangles = enclosing_size(sizes, positions)

    norm = max(width, height)

    color = cm.rainbow(np.linspace(0, 1, len(rectangles)))
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111, aspect='equal')

    ax1.set_xlim([0, norm])
    ax1.set_ylim([0, norm])
    for r, c in zip(rectangles, color):
        ax1.add_patch(
            patches.Rectangle(
                (r.x, r.y),
                r.width,
                r.height,
                facecolor=c,
                edgecolor='k'
            )
        )
    ax1.add_patch(
        patches.Rectangle(
            (0, 0),
            width,
            height,
            fill=False,
            linewidth=2
        )
    )

    ax1.invert_yaxis()

    coverage = sum(w*h for w, h in sizes)/(width*height)
    ax1.set_title(f'Area coverage: {coverage:.3f}%, t = {(t1 - t0):.3f}s')
    ax1.yaxis.set_label_position("right")
    ax1.set_ylabel(f'Enclosing height: {height}')
    ax1.set_xlabel(f'Enclosing width: {width}')

    timestamp = '{:%Y-%m-%d_%H%M%S}'.format(datetime.datetime.now())
    branch = Repository('..').head.shorthand
    plt.savefig(f'{branch}_{timestamp}_{append}.png')
    plt.clf()


def run_plots():
    plot([(i, i) for i in range(1, 51)],
         append='SquaresInc50')
    plot([(i, i) for i in range(50, 0, -1)],
         append='SquaresDec50')

    plot([(i, i) for i in range(1, 81)],
         append='SquaresInc80')
    plot([(i, i) for i in range(80, 0, -1)],
         append='SquaresDec80')

    def cosy(x):
        return int(max(10, math.cos(2*math.pi*x/80)*100))

    def siny(x):
        return int(max(10, math.sin(2*math.pi*x/80)*100))

    plot([(cosy(i), siny(i)) for i in range(0, 80)],
         append='cosy')
    plot([(siny(i), cosy(i)) for i in range(0, 80)],
         append='siny')

def average_time(nr_rectangles):
    N = 10
    t0 = time.time()
    for i in range(N):
        sizes = [(randint(10, 120), randint(10, 120)) for _ in range(nr_rectangles)]
        positions = rpack.pack(sizes)
    t1 = time.time()
    return (t1 - t0)/N

def run_timer():
    timestamp = '{:%Y-%m-%d_%H%M%S}'.format(datetime.datetime.now())
    branch = Repository('..').head.shorthand
    x = list()
    y = list()
    with open(f'{branch}_{timestamp}_TIME.txt', 'w') as f:
        for nr_rectangles in range(10, 140, 10):
            print('Nr rec: ', nr_rectangles)
            x.append(nr_rectangles)
            t = average_time(nr_rectangles)
            y.append(t)
            print('Average time: ', t)
            f.write(f'{nr_rectangles},{t}\n')

    z = np.polyfit(x, y, 3)
    print(z)
    p = np.poly1d(z)
    print(p)

    plt.plot(x, y, '*', x, [p(a) for a in x], '-')
    plt.show()

if __name__ == '__main__':
    run_plots()
    run_timer()