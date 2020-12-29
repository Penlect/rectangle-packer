
# Built-in
import doctest
import random
import timeit
import unittest

# Project
import rpack
import rpack._core


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(rpack))
    tests.addTests(doctest.DocTestSuite(rpack._core))
    return tests


def test(n):
    random.seed(0)
    sizes = [(random.randint(1, 1000), random.randint(1, 1000)) for _ in range(n)]
    pos = rpack.pack(sizes)
    assert not rpack._core.overlapping(sizes, pos)
    w, h = rpack._core.bbox_size(sizes, pos)
    p = rpack._core.packing_density(sizes, pos)
    print(f'encl (w={w} x h={h}), area={w*h}, rho={p}')


class TestTimeComplexity(unittest.TestCase):

    def test(self):
        for i in range(10, 101, 10):
            r = timeit.repeat(stmt=f'test({i})', number=1, repeat=1, globals=globals())
            print(i, r)
