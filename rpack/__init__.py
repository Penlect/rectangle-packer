"""Rectangle packing for fixed-orientation 2D rectangles.

Use :func:`pack` to place rectangles given as ``(width, height)`` tuples.
The result is a list of ``(x, y)`` lower-left coordinates in input order.

Public API:

* :func:`pack`: Compute non-overlapping positions with small enclosing area.
* :exc:`PackingImpossibleError`: Raised when given size constraints are
  impossible to satisfy.
* :func:`bbox_size` / :data:`enclosing_size`: Compute enclosing box dimensions
  for a set of rectangles and positions.
* :func:`packing_density`: Compute area utilization for a packing.
* :func:`overlapping`: Detect whether any rectangles overlap.

Example::

    >>> import rpack
    >>> sizes = [(58, 206), (231, 176), (35, 113), (46, 109)]
    >>> positions = rpack.pack(sizes)
"""

# Module metadata
__author__ = "Daniel Andersson"
__maintainer__ = __author__
__email__ = "daniel.4ndersson@gmail.com"
__contact__ = __email__
__copyright__ = "Copyright (c) 2017 Daniel Andersson"
__license__ = "MIT"
__url__ = "https://github.com/Penlect/rectangle-packer"
__version__ = "2.0.6"

# Built-in
from typing import Iterable, List, Tuple

# Local modules
from rpack._bigint_fallback import (
    bbox_size_with_bigint_fallback as _bbox_size_with_bigint_fallback,
)
from rpack._bigint_fallback import (
    overlapping_with_bigint_fallback as _overlapping_with_bigint_fallback,
)
from rpack._bigint_fallback import (
    pack_with_bigint_fallback as _pack_with_bigint_fallback,
)
from rpack._bigint_fallback import (
    packing_density_with_bigint_fallback as _packing_density_with_bigint_fallback,
)

# Extension modules
from rpack._core import (
    pack as _pack,
    PackingImpossibleError,
    bbox_size as _core_bbox_size,
    packing_density as _core_packing_density,
    overlapping as _core_overlapping,
)

__all__ = [
    "pack",
    "PackingImpossibleError",
    "bbox_size",
    "enclosing_size",
    "packing_density",
    "overlapping",
]


def bbox_size(sizes, positions) -> Tuple[int, int]:
    try:
        return _core_bbox_size(sizes, positions)
    except OverflowError:
        return _bbox_size_with_bigint_fallback(sizes, positions)


def packing_density(sizes, positions) -> float:
    try:
        return _core_packing_density(sizes, positions)
    except OverflowError:
        return _packing_density_with_bigint_fallback(sizes, positions)


def overlapping(sizes, positions):
    try:
        return _core_overlapping(sizes, positions)
    except OverflowError:
        return _overlapping_with_bigint_fallback(sizes, positions)


enclosing_size = bbox_size


def pack(
    sizes: Iterable[Tuple[int, int]], max_width=None, max_height=None
) -> List[Tuple[int, int]]:
    """Pack rectangles into a bounding box with minimal area.

    The result is returned as a list of coordinates "(x, y)", which
    specifices the location of each corresponding input rectangle's
    lower left corner.

    The helper function :py:func:`bbox_size` can be used to compute
    the width and height of the resulting bounding box.  And
    :py:func:`packing_density` can be used to evaluate the packing
    quality.

    The algorithm will sort the input in different ways internally so
    there is no need to sort ``sizes`` in advance.

    The GIL is released when C-intensive code is running.  Execution
    time increases by the number *and* size of input rectangles.  If
    this becomes a problem, you might need to implement your own
    `divide-and-conquer algorithm`_.

    Very large Python integers are supported through a fallback path:
    first exact axis-wise ``gcd`` reduction is attempted, and if the
    instance still does not fit C ``long`` bookkeeping, a conservative
    power-of-two scaling approximation is used.  This approximation is
    safe (no overlaps when scaled back) but can produce false negatives
    under strict ``max_width``/``max_height`` constraints.

    **Example**::

        # Import the module
        >>> import rpack

        # Create a bunch of rectangles (width, height)
        >>> sizes = [(58, 206), (231, 176), (35, 113), (46, 109)]

        # Pack
        >>> positions = rpack.pack(sizes)

        # The result will be a list of (x, y) positions:
        >>> positions
        [(0, 0), (58, 0), (289, 0), (289, 113)]

    ..  _`divide-and-conquer algorithm`: https://en.wikipedia.org/wiki/Divide-and-conquer_algorithm

    :param sizes: "(width, height)" of the rectangles to pack.  *Note:
        integer values only!*
    :type sizes: Iterable[Tuple[int, int]]

    :param max_width: Force the enclosing rectangle to not exceed a
        maximum width.  If not possible,
        :py:exc:`rpack.PackingImpossibleError` will be raised.
    :type max_width: Union[None, int]

    :param max_height: Force the enclosing rectangle to not exceed a
        maximum height.  If not possible,
        :py:exc:`rpack.PackingImpossibleError` will be raised.
    :type max_height: Union[None, int]

    :return: List of positions (x, y) of the input rectangles.
    :rtype: List[Tuple[int, int]]
    """
    if max_width is not None and not isinstance(max_width, int):
        raise TypeError("max_width must be an integer")
    if max_height is not None and not isinstance(max_height, int):
        raise TypeError("max_height must be an integer")
    if not isinstance(sizes, list):
        sizes = list(sizes)
    mw = -1 if max_width is None else max_width
    mh = -1 if max_height is None else max_height
    try:
        return _pack(sizes, mw, mh)
    except OverflowError:
        # For instances that overflow C long bookkeeping, retry by first
        # applying exact axis-wise gcd reduction, and then (if still needed)
        # a conservative ceil-based power-of-two approximation.
        return _pack_with_bigint_fallback(sizes, max_width, max_height)
