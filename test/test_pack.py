"""Test pack._core module"""

# Built-in
import random
import unittest

# Local
import rpack
import rpack._rpack
import rpack._core


# TEST CORE UTILS
# ===============

class TestPackingDensity(unittest.TestCase):

    def test_max_density(self):
        p = rpack._core.packing_density([(10, 10)], [(0, 0)])
        self.assertEqual(p, 1)

class TestOverlapping(unittest.TestCase):

    def test_overlapping_true(self):
        sizes = [(10, 10), (10, 10)]
        pos = [(0, 0), (9, 9)]
        index = rpack._core.overlapping(sizes, pos)
        self.assertEqual(index, (0, 1))

    def test_overlapping_false(self):
        sizes = [(10, 10), (10, 10)]
        pos = [(0, 0), (10, 10)]
        index = rpack._core.overlapping(sizes, pos)
        self.assertFalse(index)

class TestBboxSize(unittest.TestCase):

    def test_enclosing_size(self):
        """Test enclosing size helper function"""
        sizes = [(3, 5), (1, 1), (1, 1)]
        pos = [(0, 0), (3, 0), (0, 5)]
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertEqual(width, 4)
        self.assertEqual(height, 6)

# TEST INPUT
# ==========

class TestPackInput(unittest.TestCase):
    """Test how rpack.pack handles bad input"""

    def test_empty(self):
        """Empty input should give empty output"""
        self.assertListEqual(rpack.pack([]), [])

    def test_zero(self):
        """Zero number should raise ValueError"""
        with self.assertRaises(ValueError):
            rpack.pack([(0, 0)])

    def test_negative(self):
        """Negative number should raise ValueError"""
        with self.assertRaises(ValueError):
            rpack.pack([(3, -5)])
        with self.assertRaises(ValueError):
            rpack.pack([(-3, 5)])
        with self.assertRaises(ValueError):
            rpack.pack([(-3, -5)])

    def test_not_iterable(self):
        """None should raise TypeError"""
        with self.assertRaises(TypeError):
            rpack.pack(None)

    def test_not_height_width(self):
        """[None] should raise TypeError"""
        with self.assertRaises(TypeError):
            rpack.pack([None])

    def test_not_integers(self):
        """Non-number should raise TypeError"""
        with self.assertRaises(TypeError):
            rpack.pack([('garnet', 9)])
        with self.assertRaises(TypeError):
            rpack.pack([(9, 'alexandros')])

    def test_floats(self):
        with self.assertRaises(TypeError):
            rpack.pack([[1.99, 1.99]])


class TestPackInputBoundingBoxRestrictions(unittest.TestCase):
    """Test how rpack.pack handles bad input"""

    def test_none(self):
        self.assertListEqual(rpack.pack([(10, 10)], None), [(0, 0)])

    def test_max_width(self):
        pos = rpack.pack([(2, 2)]*4, max_width=3)
        self.assertSetEqual(set(pos), {(0, 2*i) for i in range(4)})

    def test_max_width_bad(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'max_width'):
            rpack.pack([(2, 2)], max_width=1)

    def test_max_width_ok(self):
        rpack.pack([(2, 2)], max_width=2)

    def test_max_height(self):
        pos = rpack.pack([(2, 2)]*4, max_height=3)
        self.assertSetEqual(set(pos), {(2*i, 0) for i in range(4)})

    def test_max_height_bad(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'max_height'):
            rpack.pack([(2, 2)], max_height=1)

    def test_max_height_ok(self):
        rpack.pack([(2, 2)], max_height=2)

    def test_partial_result(self):
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack([(2, 2)]*4, max_width=3, max_height=3)
        self.assertEqual(error.exception.args[0], 'Partial result')
        self.assertEqual(error.exception.args[1], [(0, 0)])

    def test_partial_result_simple(self):
        sizes = [(14, 17), (10, 16)]
        max_width, max_height = (22, 25)
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'Partial'):
            rpack.pack(sizes, max_width=max_width, max_height=max_height)

    def test_partial_result_width(self):
        sizes = [(10, 1)]*10
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'Partial') as err:
            rpack.pack(sizes, max_width=50, max_height=1)
        self.assertCountEqual(err.exception.args[1], [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)])

    def test_partial_result_height(self):
        sizes = [(1, 10)]*10
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'Partial') as err:
            rpack.pack(sizes, max_width=1, max_height=50)
        self.assertCountEqual(err.exception.args[1], [(0, 0), (0, 10), (0, 20), (0, 30), (0, 40)])

    def test_max_width_height_square(self):
        for i in range(1, 101):
            sizes = [(j, j) for j in range(1, i + 1)]
            pos = rpack.pack(sizes, max_width=i)
            w, _ = rpack.bbox_size(sizes, pos)
            self.assertEqual(w, i)
            pos = rpack.pack(sizes, max_height=i)
            _, h = rpack.bbox_size(sizes, pos)
            self.assertEqual(h, i)

    def test_max_width_height_diag(self):
        for i in range(1, 101):
            sizes = [(j, i + 1 - j) for j in range(1, i + 1)]
            pos = rpack.pack(sizes, max_width=i)
            w, _ = rpack.bbox_size(sizes, pos)
            self.assertEqual(w, i)
            pos = rpack.pack(sizes, max_height=i)
            _, h = rpack.bbox_size(sizes, pos)
            self.assertEqual(h, i)

    def test_max_width_height_both(self):
        sizes = [(j, j) for j in range(1, 101)]
        pos = rpack.pack(sizes, max_width=611, max_height=611)
        w, h = rpack.bbox_size(sizes, pos)
        self.assertLessEqual(w, 611)
        self.assertLessEqual(h, 611)

    def test_max_width_height_both2(self):
        sizes = [(2736, 3648), (2736, 3648), (3648, 2736), (2736, 3648), (2736, 3648)]
        max_height = max_width = 14130
        pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
        self.assertLessEqual(max(*rpack.bbox_size(sizes, pos)), max_width)
        index = rpack._core.overlapping(sizes, pos)
        self.assertFalse(index)

    def test_max_width_height_both3(self):
        sizes = [(3, 4), (3, 4), (4, 3), (3, 4), (3, 4)]
        max_height = max_width = 9
        pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
        self.assertLessEqual(max(*rpack.bbox_size(sizes, pos)), max_width)
        index = rpack._core.overlapping(sizes, pos)
        self.assertFalse(index)

    def test_max_width_height_both4(self):
        sizes = [(3, 4), (3, 4), (4, 3), (3, 4), (3, 4)]
        max_width, max_height = (16, 4)
        pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
        w, h = rpack.bbox_size(sizes, pos)
        self.assertLessEqual(w, max_width)
        self.assertLessEqual(h, max_height)
        index = rpack._core.overlapping(sizes, pos)
        self.assertFalse(index)

    def test_max_width_height_minimal_no_overlap(self):
        sizes = [(11, 17), (11, 6)]
        max_width, max_height = (21, 22)
        with self.assertRaisesRegex(rpack.PackingImpossibleError, 'Partial'):
            rpack.pack(sizes, max_width=max_width, max_height=max_height)

    @unittest.skip("long running")
    def test_max_width_height_long_running(self):
        random.seed(123)
        try:
            while True:
                n = random.randint(1, 20)
                m = 20
                sizes = [(random.randint(1, m), random.randint(1, m)) for _ in range(n)]
                max_width = random.randint(1, m*n + 10)
                max_height = random.randint(1, m*n + 10)
                try:
                    pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
                except rpack.PackingImpossibleError:
                    continue
                else:
                    w, h = rpack.bbox_size(sizes, pos)
                    assert w <= max_width
                    assert h <= max_height
                    assert not rpack.overlapping(sizes, pos)
        except KeyboardInterrupt:
            print("Stopped.")


# TEST OUTPUT
# ===========

class TestPackOutput(unittest.TestCase):
    """Test/compare output of rpack.pack"""

    def test_origin(self):
        """Single rectangle should be positioned in origin"""
        sizes = [(3, 5)]
        pos = [(0, 0)]
        self.assertListEqual(rpack.pack(sizes), pos)

    def test_perfect_pack(self):
        """Pack rectangles to perfect rectangle

        Like this::

            aaa  bb  cc  -->  aaabb
            aaa  bb           aaabb
            aaa               aaacc
        """
        sizes = [(3, 3), (2, 2), (2, 1)]
        pos = [(0, 0), (3, 0), (3, 2)]
        self.assertListEqual(rpack.pack(sizes), pos)

    def test_basic_pack(self):
        """Basic pack: four 2x2 and one 3x3"""
        sizes = [(2, 2), (2, 2), (2, 2), (3, 3)]
        pos = rpack.pack(sizes)
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertEqual(width*height, 25)

    def test_medium_pack(self):
        sizes = [(i, i) for i in range(20, 1, -1)]
        pos = rpack.pack(sizes)
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertLessEqual(width*height, 3045)

    def test_no_overlap(self):
        """Make sure no rectangles overlap"""
        for i in range(10, 101, 10):
            with self.subTest(seed=i):
                random.seed(i)
                sizes = [(random.randint(1, i), random.randint(1, i))
                         for _ in range(110 - i)]
                pos = rpack.pack(sizes)
                self.assertFalse(rpack._core.overlapping(sizes, pos))

    def test_backwards_compatible(self):
        for i in range(10):
            random.seed(i)
            sizes = [(random.randint(1, 50), random.randint(1, 50)) for _ in range(20)]
            pos1 = rpack._rpack.pack(sizes)
            self.assertFalse(rpack._core.overlapping(sizes, pos1))
            pos2 = rpack.pack(sizes)
            self.assertFalse(rpack._core.overlapping(sizes, pos2))
            self.assertLessEqual(
                rpack._core.packing_density(sizes, pos1),
                rpack._core.packing_density(sizes, pos2))
