"""Check partial packings against the corresponding input prefix geometry."""

import ctypes
import itertools
import random
import unittest

import rpack


class TestPartialResultCorrespondence(unittest.TestCase):
    def assert_valid_prefix(self, sizes, positions, max_width, max_height):
        self.assertIsInstance(positions, list)
        self.assertLessEqual(len(positions), len(sizes))
        for i, (x, y) in enumerate(positions):
            self.assertIsInstance(positions[i], tuple)
            self.assertIsInstance(x, int)
            self.assertIsInstance(y, int)
            w, h = sizes[i]
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, max_width)
            self.assertLessEqual(y + h, max_height)
            for j in range(i):
                x2, y2 = positions[j]
                w2, h2 = sizes[j]
                self.assertTrue(
                    x + w <= x2
                    or x2 + w2 <= x
                    or y + h <= y2
                    or y2 + h2 <= y,
                    f"input rectangles {j} and {i} overlap",
                )

    def partial(self, sizes, bounds):
        original_sizes = list(sizes)
        with self.assertRaises(rpack.PackingImpossibleError) as caught:
            rpack.pack(sizes, max_width=bounds[0], max_height=bounds[1])
        self.assertEqual(list(sizes), original_sizes)
        self.assertEqual(len(caught.exception.args), 2)
        message, positions = caught.exception.args
        self.assertEqual(message, "Partial result")
        self.assertLess(len(positions), len(sizes))
        self.assert_valid_prefix(sizes, positions, *bounds)
        return positions

    def test_omitted_middle_input_stops_prefix(self):
        positions = self.partial([(1, 3), (3, 1), (2, 3)], (3, 3))
        self.assertEqual(positions, [(2, 0)])

    def test_omitted_first_input_returns_empty_prefix(self):
        positions = self.partial([(2, 1), (1, 2), (5, 8)], (6, 8))
        self.assertEqual(positions, [])

    def test_keeps_whole_prefix_before_gap(self):
        positions = self.partial([(3, 2), (2, 2), (4, 1), (1, 2)], (4, 4))
        self.assertEqual(positions, [(0, 0), (0, 2)])

    def test_keeps_all_positions_when_placed_indices_have_no_gap(self):
        positions = self.partial([(3, 2), (2, 2), (1, 2), (4, 1)], (4, 4))
        self.assertEqual(positions, [(0, 0), (0, 2), (3, 0)])

    def test_identical_rectangles_keep_capacity_prefix(self):
        for size in ((1, 10), (3, 5)):
            w, h = size
            for count in (10, 31):
                for capacity in (1, count // 2, count - 1):
                    for horizontal in (False, True):
                        bounds = (
                            (w * capacity, h) if horizontal else (w, h * capacity)
                        )
                        with self.subTest(size=size, count=count, bounds=bounds):
                            positions = self.partial([size] * count, bounds)
                            expected = [
                                (i * w, 0) if horizontal else (0, i * h)
                                for i in range(capacity)
                            ]
                            self.assertEqual(positions, expected)

    def test_duplicate_group_still_stops_at_different_missing_size(self):
        for first_small in (0, 1, 3, 5, 8):
            sizes = [(2, 3)] * 10
            sizes.insert(first_small, (1, 2))
            for swap_axes in (False, True):
                oriented = [(h, w) for w, h in sizes] if swap_axes else sizes
                bounds = (15, 2) if swap_axes else (2, 15)
                with self.subTest(first_small=first_small, swap_axes=swap_axes):
                    positions = self.partial(oriented, bounds)
                    expected = [
                        (3 * i, 0) if swap_axes else (0, 3 * i)
                        for i in range(min(first_small, 5))
                    ]
                    self.assertEqual(positions, expected)

    def test_bigint_identical_rectangles_keep_capacity_prefix(self):
        factor = 1 << (ctypes.sizeof(ctypes.c_long) * 8)
        for sx, sy in ((factor, 1), (1, factor), (7 * factor, 11 * factor)):
            for horizontal in (False, True):
                size = (3 * sx, 5 * sy)
                w, h = size
                bounds = (5 * w, h) if horizontal else (w, 5 * h)
                with self.subTest(size=size, horizontal=horizontal):
                    positions = self.partial([size] * 10, bounds)
                    expected = [
                        (i * w, 0) if horizontal else (0, i * h)
                        for i in range(5)
                    ]
                    self.assertEqual(positions, expected)

    def test_bigint_rounded_duplicates_preserve_input_order(self):
        factor = 1 << (ctypes.sizeof(ctypes.c_long) * 8)
        w, h = 3 * factor, 5 * factor
        # Distinct, coprime sides become equal only after ceil approximation.
        sizes = [(w - i, h - i) for i in range(1, 11)]
        for capacity in (5, 10):
            for horizontal in (False, True):
                bounds = (capacity * w, h) if horizontal else (w, capacity * h)
                with self.subTest(capacity=capacity, horizontal=horizontal):
                    if capacity < len(sizes):
                        positions = self.partial(sizes, bounds)
                    else:
                        positions = rpack.pack(sizes, *bounds)
                        self.assert_valid_prefix(sizes, positions, *bounds)
                    expected = [
                        (i * w, 0) if horizontal else (0, i * h)
                        for i in range(capacity)
                    ]
                    self.assertEqual(positions, expected)

    def test_reordered_inputs_and_swapped_axes(self):
        fixtures = [
            ([(1, 3), (3, 1), (2, 3)], (3, 3)),
            ([(2, 1), (1, 2), (5, 8)], (6, 8)),
            ([(3, 2), (2, 2), (4, 1), (1, 2)], (4, 4)),
        ]
        for sizes, bounds in fixtures:
            for order in itertools.permutations(sizes):
                for swap_axes in (False, True):
                    oriented = (
                        [(h, w) for w, h in order] if swap_axes else list(order)
                    )
                    limits = bounds[::-1] if swap_axes else bounds
                    with self.subTest(sizes=oriented, bounds=limits):
                        self.partial(oriented, limits)

    def test_bigint_gcd_rescales_prefix_coordinates(self):
        factor = 1 << (ctypes.sizeof(ctypes.c_long) * 8)
        fixtures = [
            ([(1, 3), (3, 1), (2, 3)], (3, 3), [(2, 0)]),
            ([(3, 2), (2, 2), (4, 1), (1, 2)], (4, 4), [(0, 0), (0, 2)]),
        ]
        for base, bounds, expected in fixtures:
            for sx, sy in ((factor, 1), (1, factor), (factor, factor * 3)):
                sizes = [(w * sx, h * sy) for w, h in base]
                with self.subTest(sizes=sizes):
                    positions = self.partial(
                        sizes, (bounds[0] * sx, bounds[1] * sy)
                    )
                    self.assertEqual(
                        positions, [(x * sx, y * sy) for x, y in expected]
                    )

    def test_bigint_approximation_rescales_prefix_coordinates(self):
        factor = 1 << (ctypes.sizeof(ctypes.c_long) * 8)
        # Subtracting one makes each axis gcd one; areas still exceed C long.
        # Ceiling approximation restores multiples of factor for these inputs.
        fixtures = [
            ([(1, 3), (3, 1), (2, 3)], (3, 3), [(2, 0)]),
            ([(3, 2), (2, 2), (4, 1), (1, 2)], (4, 4), [(0, 0), (0, 2)]),
        ]
        for base, bounds, expected in fixtures:
            sizes = [(w * factor - 1, h * factor - 1) for w, h in base]
            with self.subTest(sizes=sizes):
                positions = self.partial(
                    sizes, (bounds[0] * factor, bounds[1] * factor)
                )
                self.assertEqual(
                    positions, [(x * factor, y * factor) for x, y in expected]
                )

    def test_bigint_combined_gcd_and_approximation_with_swapped_axes(self):
        factor = 1 << (ctypes.sizeof(ctypes.c_long) * 8)
        fixtures = [
            ([(1, 3), (3, 1), (2, 3)], (3, 3)),
            ([(3, 2), (2, 2), (4, 1), (1, 2)], (4, 4)),
        ]
        for base, bounds in fixtures:
            for swap_axes in (False, True):
                oriented = [(h, w) for w, h in base] if swap_axes else base
                limits = bounds[::-1] if swap_axes else bounds
                # Exact gcd factors differ between axes; the reduced sizes
                # still overflow and need conservative approximation too.
                sizes = [
                    (7 * (w * factor - 1), 11 * (h * factor - 1))
                    for w, h in oriented
                ]
                with self.subTest(sizes=sizes, swap_axes=swap_axes):
                    expected = self.partial(oriented, limits)
                    positions = self.partial(
                        sizes, (7 * limits[0] * factor, 11 * limits[1] * factor)
                    )
                    self.assertEqual(
                        positions,
                        [(7 * x * factor, 11 * y * factor) for x, y in expected],
                    )

    def test_seeded_constrained_packings(self):
        rng = random.Random(20261106)
        partial_count = full_count = 0
        for case in range(1000):
            sizes = [
                (rng.randint(1, 10), rng.randint(1, 10))
                for _ in range(rng.randint(2, 8))
            ]
            bounds = (
                rng.randint(max(w for w, _ in sizes), sum(w for w, _ in sizes)),
                rng.randint(max(h for _, h in sizes), sum(h for _, h in sizes)),
            )
            with self.subTest(case=case, sizes=sizes, bounds=bounds):
                try:
                    positions = rpack.pack(sizes, *bounds)
                except rpack.PackingImpossibleError as error:
                    partial_count += 1
                    self.assertEqual(len(error.args), 2)
                    self.assertEqual(error.args[0], "Partial result")
                    positions = error.args[1]
                    self.assertLess(len(positions), len(sizes))
                else:
                    full_count += 1
                    self.assertEqual(len(positions), len(sizes))
                self.assert_valid_prefix(sizes, positions, *bounds)
        self.assertGreater(partial_count, 0)
        self.assertGreater(full_count, 0)
