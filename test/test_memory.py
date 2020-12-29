"""Search for memory leaks in rectangle-packer.

Since this project involves C code there is always a risk of bugs
causing memory leaks.  This module uses memory_profiler to check
memory usage over time.

https://pypi.org/project/memory-profiler/

Run this command::

    $ mprof run python3 -m test.test_memory; and mprof plot

"""

# Builtin
import argparse
import time
import random
from random import randint

# Package
import rpack


def randrec():
    length = randint(1, 100)
    return [(randint(1, 1000), randint(1, 1000)) for _ in range(length)]


def randneg():
    length = randint(1, 100)
    return [(-randint(1, 1000), -randint(1, 1000)) for _ in range(length)]


def randtype():
    length = randint(1, 100)
    return [(None, 'string') for _ in range(length)]


def randrest():
    return random.choices([None, randint(1, 1000)], [0.9, 0.1])[0]


def main(args):
    random.seed(0)
    t0 = time.time()
    while time.time() - t0 < args.duration:
        func = random.choices([randrec, randneg, randtype], [0.8, 0.1, 0.1])
        sizes = func[0]()
        try:
            pos = rpack.pack(sizes)
        except Exception:
            pass
        else:
            if pos:
                rpack.packing_density(sizes, pos)
                rpack.bbox_size(sizes, pos)
                rpack.overlapping(sizes, pos)


parser = argparse.ArgumentParser()
parser.add_argument('duration', type=int, help='Seconds to run')

if __name__ == '__main__':
    args = parser.parse_args()
    main(args)
