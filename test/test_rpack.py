
from collections import namedtuple
import unittest

import rpack

R = namedtuple('R', 'width height x y')


def enclosing_size(sizes, positions):
    """Return enclosing size of rectangles having sizes and positions"""
    rectangles = [R(*size, *pos) for size, pos in zip(sizes, positions)]
    width = max(r.width + r.x for r in rectangles)
    height = max(r.height + r.y for r in rectangles)
    return width, height


class TestPack(unittest.TestCase):
    def test_enclosing_size(self):
        """Single rectangle should be positioned in origin"""
        sizes = [(3, 5), (1, 1), (1, 1)]
        positions = [(0, 0), (3, 0), (0, 5)]
        width, height = enclosing_size(sizes, positions)
        self.assertEqual(width, 4)
        self.assertEqual(height, 6)

    def test_origin(self):
        """Single rectangle should be positioned in origin"""
        rectangles = [(3, 5)]
        positions = [(0, 0)]
        self.assertEqual(rpack.pack(rectangles), positions)

    def test_basic_pack(self):
        """Single rectangle should be positioned in origin"""
        sizes = [(2, 2), (2, 2), (2, 2), (3, 3)]
        positions = rpack.pack(sizes)
        width, height = enclosing_size(sizes, positions)
        self.assertEqual(width*height, 25)

    def test_medium_pack(self):
        sizes = [(i, i) for i in range(20, 1, -1)]
        positions = rpack.pack(sizes)
        width, height = enclosing_size(sizes, positions)
        self.assertLessEqual(width*height, 3045)

    def test_empty(self):
        """Empty input should give empty output"""
        rectangles = []
        positions = []
        self.assertEqual(rpack.pack(rectangles), positions)

    def test_valueerror(self):
        """Non-number should raise ValueError"""
        # Todo: SystemError
        with self.assertRaises(SystemError):
            rectangles = [('sd', 5)]
            rpack.pack(rectangles)


if __name__ == '__main__':
    unittest.main()