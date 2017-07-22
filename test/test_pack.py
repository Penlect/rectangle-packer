
from collections import namedtuple
import random

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.pyplot import cm
import numpy as np

import rpack as hw

R = namedtuple('R', 'id width height x y')

print(hw.helloworld())
print()

test1 = [
    (12,32),
    (43,145),
    (123,56),
    (34,244),
    (54,234),
    (2,4)
]
test1 = list(sorted(test1, key=lambda x: -x[-1]))
print(test1)

test1 = [
    (40,48),
    (22,32),
    (95,26),
    (83,11)
]


result = [R(*[item[0], *item[1], *item[2]]) for item in hw.pack(test1)]

width = max(r.width + r.x for r in result)
height = max(r.height + r.y for r in result)
print(width, height)
norm = max(width, height)

print(result)

color=cm.rainbow(np.linspace(0.2, 0.8, len(result)))
fig1 = plt.figure()
ax1 = fig1.add_subplot(111, aspect='equal')
ax1.set_xlim([0,norm])
ax1.set_ylim([0,norm])
ax1.grid()
for r, c in zip(result, color):
    ax1.add_patch(
        patches.Rectangle(
            (r.x, r.y),   # (x,y)
            r.width,          # width
            r.height,          # height
            facecolor=c
        )
    )
plt.gca().invert_yaxis()
plt.show()