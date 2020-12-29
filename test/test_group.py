"""Test rpack._rpack.group"""

# Built-in
import random
import unittest

# Local
import rpack._rpack as rpack

class TestGroup(unittest.TestCase):

    def test_flat(self):
        data = [3, 2, 1]
        # Todo: the order should not matter
        self.assertEqual(rpack.group(data, 3), [[3], [2], [1]])


    def test_nr_groups(self):
        with self.assertRaises(ValueError):
            rpack.group([1], -1)
        with self.assertRaises(ValueError):
            rpack.group([1], 0)
        data = list(range(1, 100))
        for nr_groups in range(1, 100):
            assert len(rpack.group(data, nr_groups)) == nr_groups


    def test_empty_list(self):
        self.assertEqual(rpack.group([], 3), [[], [], []])


    def test_input_error(self):
        with self.assertRaises(TypeError):
            rpack.group(None, 3)
        with self.assertRaises(TypeError):
            rpack.group([1, 2, 3], None)
        with self.assertRaises(TypeError):
            rpack.group(None, None)


    def test_performance(self):
        groups = rpack.group(list(range(1000)), 5)
        self.assertEqual(max(sum(g) for g in groups), 99900)


    def test_swap_complete(self):
        """Test that no further "swapping" will improve the result"""
        # Get random data
        data = [random.random() for _ in range(500)]
        nr_groups = random.randint(2, 15)
        # Figure out which group is the maximal-sum group
        groups = rpack.group(data, nr_groups)
        group_sums = [sum(g) for g in groups]
        max_duration = max(group_sums)
        group_id_max = group_sums.index(max_duration)
        max_group = groups[group_id_max]

        # For each element in max_group, try to swap element with other
        # elements in the other groups and check if the "max-group" can
        # be improved.
        for i in range(len(max_group)):
            for group_id, group in enumerate(groups):
                if group_id == group_id_max:
                    # We don't want to swap within the same group
                    continue
                for j in range(len(group)):
                    # Swap
                    group[j], max_group[i] = max_group[i], group[j]
                    # Swap should not make any improvements
                    group_sums = [sum(g) for g in groups]
                    self.assertGreaterEqual(max(group_sums), max_duration)
                    # Undo swap
                    group[j], max_group[i] = max_group[i], group[j]
