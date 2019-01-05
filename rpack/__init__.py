"""Module docs"""

# Built-in
import collections
from typing import Iterable, Tuple, List

# Local
from . import _rpack


def pack(sizes: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Pack rectangles into an enclosing rectangle with minimal area.

    No rectangles will overlap.

    The GIL is released when C-intensive code is running. Execution
    time increase by number *and* size of rectangles.

    Example::

        # Create a bunch of rectangles (width, height)
        >>> sizes = [(58, 206), (231, 176), (35, 113), (46, 109)]

        # Pack
        >>> positions = rpack.pack(sizes)

        # The result will be a list of (x, y) positions:
        >>> positions
        [(0, 0), (58, 0), (289, 0), (289, 113)]

    :param sizes: Iterable of 2-tuples "(width, height)" of the
        rectangles to pack. **Note: integer values only!**
    :return: List of 2-tuples "(x, y)" of positions of the input
        rectangles. The position refers to the top left corner of the
        rectangle in a coordinate system where the origin is in the top
        left corner.
    """
    return _rpack.pack(sizes)


def group(heights: Iterable[float], nr_groups: int) -> List[List[float]]:
    """Group objects and minimize maximum group sum

    The GIL is released when C-intensive code is running.

    :param heights: Iterable of objects which implements float(object).
    :param nr_groups: Nr of groups.
    :type nr_groups: int
    :return: List of lists. Each list represents a group and contains
        the groups objects.
    """
    return _rpack.group(heights, nr_groups)


_R = collections.namedtuple('R', 'width height x y')


def enclosing_size(sizes, positions):
    """Return enclosing size of rectangles having sizes and positions.

    Useful to compute the enclosing size of the output of
    :py:func:`rpack.pack`.

    Example::

        >>> sizes = [(58, 206), (231, 176), (35, 113), (46, 109)]
        >>> positions = rpack.pack(sizes)

        >>> enclosing_size(sizes, positions)
        (335, 222)


    """
    rectangles = [_R(*size, *pos) for size, pos in zip(sizes, positions)]
    width = max(r.width + r.x for r in rectangles)
    height = max(r.height + r.y for r in rectangles)
    return width, height
