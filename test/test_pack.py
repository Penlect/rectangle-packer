"""Test rpack._core module"""

# Built-in
import ctypes
import random
import subprocess
import sys
import unittest

# Local
import rpack
import rpack._core


def _bbox_size_py(sizes, positions):
    width = 0
    height = 0
    for (rect_w, rect_h), (x, y) in zip(sizes, positions):
        width = max(width, x + rect_w)
        height = max(height, y + rect_h)
    return width, height


def _overlapping_py(sizes, positions):
    n = len(sizes)
    for i in range(n):
        w1, h1 = sizes[i]
        x1, y1 = positions[i]
        for j in range(i + 1, n):
            w2, h2 = sizes[j]
            x2, y2 = positions[j]
            disjoint_in_x = x1 + w1 <= x2 or x2 + w2 <= x1
            disjoint_in_y = y1 + h1 <= y2 or y2 + h2 <= y1
            if not (disjoint_in_x or disjoint_in_y):
                return (i, j)
    return None


# TEST CORE UTILS
# ===============


class TestPackingDensity(unittest.TestCase):
    def test_max_density(self):
        p = rpack._core.packing_density([(10, 10)], [(0, 0)])
        self.assertEqual(p, 1)

    def test_bigint_density_helper(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        sizes = [(long_max + 1, 1)]
        pos = [(0, 0)]
        self.assertEqual(rpack.packing_density(sizes, pos), 1.0)

    def test_bigint_density_helper_rejects_non_integer_inputs(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        with self.assertRaises(TypeError):
            rpack.packing_density([(long_max + 1, 1.2)], [(0, 0)])
        with self.assertRaises(TypeError):
            rpack.packing_density([(long_max + 1, 1)], [(0.0, 0)])

    def test_bigint_density_helper_guards_sum_wraparound(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        width = (long_max // 2) + 2
        sizes = [(width, 1), (width, 1)]
        positions = [(0, 0), (width, 0)]
        self.assertEqual(rpack.packing_density(sizes, positions), 1.0)

    def test_core_packing_density_raises_on_sum_wraparound(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        width = (long_max // 2) + 2
        sizes = [(width, 1), (width, 1)]
        positions = [(0, 0), (width, 0)]
        with self.assertRaises(OverflowError):
            rpack._core.packing_density(sizes, positions)


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

    def test_bigint_overlapping_helper(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        sizes = [(long_max + 1, 1), (2, 2)]
        pos = [(0, 0), (long_max, 0)]
        self.assertEqual(rpack.overlapping(sizes, pos), (0, 1))

    def test_bigint_overlapping_helper_rejects_non_integer_inputs(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        with self.assertRaises(TypeError):
            rpack.overlapping([(long_max + 1, 1.2)], [(0, 0)])
        with self.assertRaises(TypeError):
            rpack.overlapping([(long_max + 1, 1)], [(0, 0.0)])

    def test_core_overlapping_raises_on_sum_wraparound(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        width = (long_max // 2) + 2
        with self.assertRaises(OverflowError):
            rpack._core.overlapping([(width, 1)], [(width, 0)])


class TestBboxSize(unittest.TestCase):
    def test_enclosing_size(self):
        """Test enclosing size helper function"""
        sizes = [(3, 5), (1, 1), (1, 1)]
        pos = [(0, 0), (3, 0), (0, 5)]
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertEqual(width, 4)
        self.assertEqual(height, 6)

    def test_enclosing_size_bigint_helper(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        sizes = [(long_max + 1, 1), (2, 3)]
        pos = [(long_max + 5, 0), (0, 0)]
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertEqual(width, 2 * long_max + 6)
        self.assertEqual(height, 3)

    def test_enclosing_size_bigint_helper_rejects_non_integer_inputs(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        with self.assertRaises(TypeError):
            rpack.enclosing_size([(long_max + 1, 1.2)], [(0, 0)])
        with self.assertRaises(TypeError):
            rpack.enclosing_size([(long_max + 1, 1)], [(0, 0.0)])

    def test_enclosing_size_bigint_helper_rejects_mismatched_lengths(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        sizes = [(long_max + 1, 1), (2, 3)]
        positions = [(0, 0)]
        with self.assertRaises(IndexError):
            rpack.enclosing_size(sizes, positions)

    def test_enclosing_size_bigint_helper_guards_sum_wraparound(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        width = (long_max // 2) + 2
        sizes = [(width, 1), (width, 1)]
        positions = [(0, 0), (width, 0)]
        self.assertEqual(rpack.enclosing_size(sizes, positions), (2 * width, 1))

    def test_core_bbox_size_raises_on_sum_wraparound(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        width = (long_max // 2) + 2
        sizes = [(width, 1), (width, 1)]
        positions = [(0, 0), (width, 0)]
        with self.assertRaises(OverflowError):
            rpack._core.bbox_size(sizes, positions)


# TEST INPUT
# ==========


class TestPackInput(unittest.TestCase):
    """Test how rpack.pack handles bad input"""

    _LONG_BITS = ctypes.sizeof(ctypes.c_long) * 8
    _LONG_MAX = (1 << (_LONG_BITS - 1)) - 1

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
            rpack.pack([("garnet", 9)])
        with self.assertRaises(TypeError):
            rpack.pack([(9, "alexandros")])

    def test_floats(self):
        with self.assertRaises(TypeError):
            rpack.pack([[1.99, 1.99]])

    def test_area_overflow_fallback(self):
        too_wide = self._LONG_MAX // 2 + 1
        self.assertEqual(rpack.pack([(too_wide, 2)]), [(0, 0)])

    def test_total_area_overflow_fallback(self):
        side = self._LONG_MAX // 2 + 1
        sizes = [(side, 1), (side, 1)]
        pos = rpack.pack(sizes)
        self.assertEqual(len(pos), 2)
        self.assertIsNone(_overlapping_py(sizes, pos))

    def test_side_larger_than_c_long_fallback(self):
        too_wide = self._LONG_MAX + 1
        self.assertEqual(rpack.pack([(too_wide, 1)]), [(0, 0)])

    def test_large_side_with_constraints_fallback(self):
        side = self._LONG_MAX + 1
        sizes = [(side, 1), (side, 1)]
        max_width = side * 2
        max_height = 1
        pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
        width, height = _bbox_size_py(sizes, pos)
        self.assertLessEqual(width, max_width)
        self.assertLessEqual(height, max_height)
        self.assertIsNone(_overlapping_py(sizes, pos))

    def test_approximation_never_violates_explicit_max_width(self):
        sizes = [(self._LONG_MAX // 2, 1), (self._LONG_MAX // 2 + 2, 1)]
        max_width = sum(width for width, _ in sizes)
        try:
            pos = rpack.pack(sizes, max_width=max_width, max_height=1)
        except rpack.PackingImpossibleError:
            return
        width, height = _bbox_size_py(sizes, pos)
        self.assertLessEqual(width, max_width)
        self.assertLessEqual(height, 1)
        self.assertIsNone(_overlapping_py(sizes, pos))

    def test_approximation_never_violates_explicit_max_height(self):
        sizes = [(1, self._LONG_MAX // 2), (1, self._LONG_MAX // 2 + 2)]
        max_height = sum(height for _, height in sizes)
        try:
            pos = rpack.pack(sizes, max_width=1, max_height=max_height)
        except rpack.PackingImpossibleError:
            return
        width, height = _bbox_size_py(sizes, pos)
        self.assertLessEqual(width, 1)
        self.assertLessEqual(height, max_height)
        self.assertIsNone(_overlapping_py(sizes, pos))

    def test_bigint_fallback_remaps_zero_bound_artifact(self):
        sizes = [
            (1, self._LONG_MAX + 1),
            (1, self._LONG_MAX + 2),
        ]
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack(sizes, max_width=1)
        self.assertEqual(
            error.exception.args[0],
            "max_width too small under bigint approximation",
        )

    def test_bigint_fallback_preserves_positive_bound_after_gcd_reduction(self):
        side = self._LONG_MAX + 2
        sizes = [(side, 1), (side, 1)]
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack(sizes, max_width=1)
        self.assertEqual(
            error.exception.args[0],
            "max_width too small under bigint approximation",
        )

    def test_bigint_fallback_remaps_zero_height_artifact(self):
        sizes = [
            (self._LONG_MAX + 1, 1),
            (self._LONG_MAX + 2, 1),
        ]
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack(sizes, max_height=1)
        self.assertEqual(
            error.exception.args[0],
            "max_height too small under bigint approximation",
        )

    def test_bigint_fallback_partial_result_uses_original_coordinates(self):
        side = self._LONG_MAX + 1
        sizes = [(side, 1)] * 3
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack(sizes, max_width=2 * side, max_height=1)
        self.assertEqual(error.exception.args[0], "Partial result")
        self.assertEqual(error.exception.args[1], [(0, 0), (side, 0)])

    def test_bigint_huge_bound_does_not_timeout(self):
        script = (
            "import rpack\n"
            "rpack.pack([(1, 1)], max_width=1 << 200000)\n"
            "print('ok')\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "ok")

    def test_huge_nonbinding_width_with_tight_height(self):
        script = (
            "import rpack\n"
            "print(rpack.pack([(1, 1)], max_width=1 << 200000, max_height=1))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "[(0, 0)]")

    def test_huge_nonbinding_height_with_tight_width(self):
        script = (
            "import rpack\n"
            "print(rpack.pack([(1, 1)], max_width=1, max_height=1 << 200000))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "[(0, 0)]")

    def test_huge_negative_bounds_behave_unbounded(self):
        script = (
            "import rpack\n"
            "print(rpack.pack([(1, 1)], max_width=-(1 << 200000), max_height=-(1 << 200000)))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "[(0, 0)]")

    def test_empty_with_huge_bound_returns_empty(self):
        script = (
            "import rpack\n"
            "print(rpack.pack([], max_width=1 << 200000))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertEqual(completed.stdout.strip(), "[]")

    def test_nonbinding_bounds_do_not_break_fallback(self):
        sizes = [
            (9223372036854778009, 5),
            (9223372036854776841, 3),
        ]
        max_width = sum(width for width, _ in sizes)
        max_height = sum(height for _, height in sizes)
        try:
            pos = rpack.pack(sizes, max_width=max_width, max_height=max_height)
        except rpack.PackingImpossibleError:
            return
        width, height = _bbox_size_py(sizes, pos)
        self.assertLessEqual(width, max_width)
        self.assertLessEqual(height, max_height)
        self.assertIsNone(_overlapping_py(sizes, pos))

    def test_partial_result_rescales_y_axis_with_bigint_fallback(self):
        side = self._LONG_MAX + 1
        sizes = [(1, side)] * 3
        max_width = 1
        max_height = 2 * side
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack(sizes, max_width=max_width, max_height=max_height)
        self.assertEqual(error.exception.args[0], "Partial result")
        self.assertEqual(error.exception.args[1], [(0, 0), (0, side)])

    def test_max_width_zero_message_preserved_in_fallback(self):
        side = self._LONG_MAX + 1
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_width zero"):
            rpack.pack([(side, 1)], max_width=0)

    def test_max_height_zero_message_preserved_in_fallback(self):
        side = self._LONG_MAX + 1
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_height zero"):
            rpack.pack([(1, side)], max_height=0)


class TestPackInputBoundingBoxRestrictions(unittest.TestCase):
    """Test how rpack.pack handles bad input"""

    def test_none(self):
        self.assertListEqual(rpack.pack([(10, 10)], None), [(0, 0)])

    def test_max_width(self):
        pos = rpack.pack([(2, 2)] * 4, max_width=3)
        self.assertSetEqual(set(pos), {(0, 2 * i) for i in range(4)})

    def test_max_width_bad(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_width"):
            rpack.pack([(2, 2)], max_width=1)

    def test_max_width_ok(self):
        rpack.pack([(2, 2)], max_width=2)

    def test_max_height(self):
        pos = rpack.pack([(2, 2)] * 4, max_height=3)
        self.assertSetEqual(set(pos), {(2 * i, 0) for i in range(4)})

    def test_max_height_bad(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_height"):
            rpack.pack([(2, 2)], max_height=1)

    def test_max_height_ok(self):
        rpack.pack([(2, 2)], max_height=2)

    def test_max_width_zero(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_width zero"):
            rpack.pack([(2, 2)], max_width=0)

    def test_max_height_zero(self):
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "max_height zero"):
            rpack.pack([(2, 2)], max_height=0)

    def test_partial_result(self):
        with self.assertRaises(rpack.PackingImpossibleError) as error:
            rpack.pack([(2, 2)] * 4, max_width=3, max_height=3)
        self.assertEqual(error.exception.args[0], "Partial result")
        self.assertEqual(error.exception.args[1], [(0, 0)])

    def test_partial_result_simple(self):
        sizes = [(14, 17), (10, 16)]
        max_width, max_height = (22, 25)
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "Partial"):
            rpack.pack(sizes, max_width=max_width, max_height=max_height)

    def test_partial_result_width(self):
        sizes = [(10, 1)] * 10
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "Partial") as err:
            rpack.pack(sizes, max_width=50, max_height=1)
        self.assertCountEqual(
            err.exception.args[1], [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)]
        )

    def test_partial_result_height(self):
        sizes = [(1, 10)] * 10
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "Partial") as err:
            rpack.pack(sizes, max_width=1, max_height=50)
        self.assertCountEqual(
            err.exception.args[1], [(0, 0), (0, 10), (0, 20), (0, 30), (0, 40)]
        )

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
        with self.assertRaisesRegex(rpack.PackingImpossibleError, "Partial"):
            rpack.pack(sizes, max_width=max_width, max_height=max_height)

    @unittest.skip("long running")
    def test_max_width_height_long_running(self):
        random.seed(123)
        try:
            while True:
                n = random.randint(1, 20)
                m = 20
                sizes = [(random.randint(1, m), random.randint(1, m)) for _ in range(n)]
                max_width = random.randint(1, m * n + 10)
                max_height = random.randint(1, m * n + 10)
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

    _THIN_PATHOLOGY_BASE = [
        (936469, 1),
        (956023, 480880),
        (762663, 456585),
        (522456, 924841),
        (193372, 365467),
        (505745, 921750),
        (127245, 805540),
        (234482, 384004),
        (986956, 278825),
        (787627, 59839),
    ]

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
        self.assertEqual(width * height, 25)

    def test_medium_pack(self):
        sizes = [(i, i) for i in range(20, 1, -1)]
        pos = rpack.pack(sizes)
        width, height = rpack.enclosing_size(sizes, pos)
        self.assertLessEqual(width * height, 3045)

    def test_helpers_accept_bigint_pack_results(self):
        long_bits = ctypes.sizeof(ctypes.c_long) * 8
        long_max = (1 << (long_bits - 1)) - 1
        sizes = [(long_max + 1, 1), (long_max + 1, 1)]
        pos = rpack.pack(sizes)
        self.assertEqual(rpack.bbox_size(sizes, pos), _bbox_size_py(sizes, pos))
        self.assertIsNone(rpack.overlapping(sizes, pos))
        bbox_width, bbox_height = rpack.bbox_size(sizes, pos)
        expected = sum(width * height for width, height in sizes) / (
            bbox_width * bbox_height
        )
        self.assertEqual(rpack.packing_density(sizes, pos), expected)

    def test_no_overlap(self):
        """Make sure no rectangles overlap"""
        for i in range(10, 101, 10):
            with self.subTest(seed=i):
                random.seed(i)
                sizes = [
                    (random.randint(1, i), random.randint(1, i)) for _ in range(110 - i)
                ]
                pos = rpack.pack(sizes)
                self.assertFalse(rpack._core.overlapping(sizes, pos))

    @unittest.skipIf(
        ctypes.sizeof(ctypes.c_long) < 8,
        "thin-pathology fixture exceeds 32-bit C long area limits",
    )
    def test_thin_pathology_quality(self):
        """Keep quality stable for the known thin-rectangle edge case."""
        # Lock known issue reference outputs so search-step tuning does not
        # silently degrade bbox quality while improving runtime.
        expected = {
            1: ((1155446, 2200971), 0.9212547369575843),
            5: ((1155446, 2200975), 0.9212545356431094),
        }
        for h, (bbox_expected, density_expected) in expected.items():
            with self.subTest(h=h):
                sizes = list(self._THIN_PATHOLOGY_BASE)
                sizes[0] = (sizes[0][0], h)
                pos = rpack.pack(sizes)
                self.assertFalse(rpack._core.overlapping(sizes, pos))
                self.assertEqual(rpack.bbox_size(sizes, pos), bbox_expected)
                self.assertAlmostEqual(
                    rpack.packing_density(sizes, pos),
                    density_expected,
                    places=12,
                )

    @unittest.skipIf(
        ctypes.sizeof(ctypes.c_long) < 8,
        "regression only applies when C long is wider than 32-bit int",
    )
    def test_pack_does_not_stall_above_32bit_int_height(self):
        """Large heights above 2^31 should not trigger comparator overflow stalls."""
        script = (
            "import rpack\n"
            "pos = rpack.pack([(1, 2147483648)] * 2)\n"
            "print(pos)\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=True,
        )
        self.assertIn("[(0, 0), (1, 0)]", completed.stdout.strip())

    @unittest.skipIf(
        ctypes.sizeof(ctypes.c_long) < 8,
        "fixture uses values above 32-bit C long to force bigint fallback",
    )
    def test_bigint_axis_gcd_reduction_matches_small_instance(self):
        scale = 10**20
        big_sizes = [
            (3 * scale, 5 * scale),
            (4 * scale, 2 * scale),
            (2 * scale, 2 * scale),
        ]
        small_sizes = [(3, 5), (4, 2), (2, 2)]
        small_pos = rpack.pack(small_sizes)
        big_pos = rpack.pack(big_sizes)
        self.assertEqual(big_pos, [(x * scale, y * scale) for x, y in small_pos])
