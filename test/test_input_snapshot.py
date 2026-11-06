"""Check input snapshots in bounded subprocesses with allocator guards enabled."""

import os
import subprocess
import sys
import textwrap
import unittest


_CHECK_SNAPSHOT = """
import rpack
from rpack._core import RectangleSet, pack as core_pack

def check(factory, expected):
    expected_positions = rpack.pack(expected)
    assert rpack.pack(factory()) == expected_positions
    assert core_pack(factory(), -1, -1) == expected_positions
    if not expected:
        try:
            RectangleSet(factory())
        except ValueError as error:
            assert str(error) == 'sizes must not be empty'
        else:
            raise AssertionError('empty RectangleSet accepted')
        return
    rectangles = list(RectangleSet(factory()))
    assert len(rectangles) == len(expected)
    for index, (rectangle, (width, height)) in enumerate(zip(rectangles, expected)):
        assert rectangle == dict(width=width, height=height, x=-1, y=-1,
            index=index, area=width * height, wide=width >= height, rotated=False)
"""


class TestInputSnapshot(unittest.TestCase):
    def check_in_subprocess(self, script):
        # A regression must fail this test, rather than corrupt the test runner.
        # Keep child assertions active even when PYTHONOPTIMIZE is inherited.
        completed = subprocess.run(
            [sys.executable, "-c", _CHECK_SNAPSHOT + textwrap.dedent(script)],
            env={
                **os.environ,
                "PYTHONMALLOC": "debug",
                "PYTHONFAULTHANDLER": "1",
                "PYTHONOPTIMIZE": "0",
            },
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_inaccurate_lengths(self):
        self.check_in_subprocess("""
            expected = [(3, 5), (4, 2)]
            for base in (list, tuple):
                for reported in (0, 1, 3):
                    class Sizes(base):
                        def __len__(self):
                            return reported
                    check(lambda: Sizes(expected), expected)
                    check(lambda: Sizes(), [])
        """)

    def test_length_changes_between_calls(self):
        self.check_in_subprocess("""
            class Sizes(list):
                calls = 0
                def __len__(self):
                    self.calls += 1
                    return self.calls
            expected = [(3, 5), (4, 2)]
            check(lambda: Sizes(expected), expected)
        """)

    def test_overridden_iteration_order_and_count(self):
        self.check_in_subprocess("""
            expected = [(3, 5), (4, 2)]
            class Sizes(list):
                def __iter__(self):
                    return iter(expected)
            check(lambda: Sizes([(9, 9)]), expected)
        """)

    def test_mutation_during_outer_materialization(self):
        self.check_in_subprocess("""
            class Sizes(list):
                def __iter__(self):
                    yield self[0]
                    self.clear()
                    yield (4, 2)
            check(lambda: Sizes([(3, 5)]), [(3, 5), (4, 2)])
        """)

    def test_mutation_during_length_hint(self):
        self.check_in_subprocess("""
            for mutation in ('append', 'clear', 'replace'):
                class Sizes(list):
                    mutated = False
                    def __iter__(self):
                        # Tuple construction need not request a length hint.
                        # Exercise the callback during materialization anyway.
                        len(self)
                        return super().__iter__()
                    def __len__(self):
                        if not self.mutated:
                            # Some runtimes also request their own length hint.
                            self.mutated = True
                            if mutation == 'append':
                                self.append((7, 8))
                            elif mutation == 'clear':
                                self.clear()
                            else:
                                self[:] = [(4, 2), (3, 5)]
                        return 9
                expected = {
                    'append': [(3, 5), (7, 8)],
                    'clear': [],
                    'replace': [(4, 2), (3, 5)],
                }[mutation]
                check(lambda: Sizes([(3, 5)]), expected)
        """)

    def test_mutation_while_unpacking_rectangles(self):
        self.check_in_subprocess("""
            for mutation in ('append', 'clear', 'replace'):
                def factory():
                    class Pair:
                        def __iter__(self):
                            if mutation == 'append':
                                sizes.append((7, 8))
                            elif mutation == 'clear':
                                sizes.clear()
                            else:
                                sizes[1] = (7, 8)
                            return iter((3, 5))
                    sizes = [Pair(), (4, 2)]
                    return sizes
                check(factory, [(3, 5), (4, 2)])
        """)

    def test_iterables_are_consumed_once(self):
        self.check_in_subprocess("""
            expected = [(3, 5), (4, 2)]
            check(lambda: (size for size in expected), expected)
            check(lambda: tuple(expected), expected)
            class Sequence:
                def __len__(self):
                    return 1
                def __getitem__(self, index):
                    return expected[index]
            check(Sequence, expected)
            class Sizes(list):
                calls = 0
                def __iter__(self):
                    self.calls += 1
                    assert self.calls == 1
                    return super().__iter__()
            check(lambda: Sizes(expected), expected)
        """)

    def test_bigint_retry_uses_same_outer_snapshot(self):
        self.check_in_subprocess("""
            import ctypes
            side = 1 << (ctypes.sizeof(ctypes.c_long) * 8 - 1)
            expected = [(side, 1), (side, 2)]
            class Pair:
                def __iter__(self):
                    sizes.clear()
                    return iter(expected[0])
            class Sizes(list):
                calls = 0
                def __iter__(self):
                    self.calls += 1
                    assert self.calls == 1
                    return super().__iter__()
            sizes = Sizes([Pair(), expected[1]])
            assert rpack.pack(sizes) == rpack.pack(expected)
        """)

    def test_validation_errors_are_preserved(self):
        self.check_in_subprocess("""
            errors = [
                ([(1.5, 1)], TypeError, 'Rectangle width must be an integer'),
                ([(1, None)], TypeError, 'Rectangle height must be an integer'),
                ([(0, 1)], ValueError, 'Rectangle width must be positive integer'),
                ([(1, -1)], ValueError, 'Rectangle height must be positive integer'),
            ]
            for sizes, exception, message in errors:
                for construct in (rpack.pack, RectangleSet):
                    try:
                        # Also exercise cleanup after one native entry is written.
                        construct(iter([(3, 5), *sizes]))
                    except exception as error:
                        assert str(error) == message
                    else:
                        raise AssertionError('invalid rectangle accepted')
        """)

    def test_iteration_errors_are_preserved(self):
        self.check_in_subprocess("""
            error = RuntimeError('iteration failed')
            def broken_sizes():
                yield (3, 5)
                raise error
            class BrokenPair:
                def __iter__(self):
                    raise error
            for factory in (broken_sizes, lambda: [(3, 5), BrokenPair()]):
                for construct in (
                    rpack.pack, lambda sizes: core_pack(sizes, -1, -1), RectangleSet
                ):
                    try:
                        construct(factory())
                    except RuntimeError as caught:
                        assert caught is error
                    else:
                        raise AssertionError('iteration error swallowed')
        """)
