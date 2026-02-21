"""Big-int fallback helpers for the :mod:`rpack` public API.

This module is used when the C core raises :class:`OverflowError` because one
or more geometry values do not fit in C ``long``. The fallback strategy is:

1. Validate and normalize Python-int inputs.
2. Try exact axis-wise ``gcd`` reduction.
3. If still too large, build a conservative power-of-two approximation.
4. Pack with the C core, rescale to original units, and revalidate explicit
   bounds.

The approximation never returns overlapping placements, but under strict bounds
it may return false negatives (``PackingImpossibleError`` for an instance that
is feasible in original units).
"""

from __future__ import annotations

import ctypes
import math
from typing import Iterable, List, Optional, Sequence, Tuple

from rpack._core import pack as _pack
from rpack._core import PackingImpossibleError

_CLONG_BITS = ctypes.sizeof(ctypes.c_long) * 8
_CLONG_MAX = (1 << (_CLONG_BITS - 1)) - 1

Size = Tuple[int, int]
Position = Tuple[int, int]
Sizes = List[Size]
Positions = List[Position]


def _ceil_div(a: int, b: int) -> int:
    """Return ``ceil(a / b)`` for positive integers."""
    return (a + b - 1) // b


def _ceil_sqrt(value: int) -> int:
    """Return ``ceil(sqrt(value))`` for non-negative integers."""
    root = math.isqrt(value)
    if root * root == value:
        return root
    return root + 1


def _next_power_of_two(value: int) -> int:
    """Round ``value`` up to the next power of two (minimum ``1``)."""
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def _normalize_positive_bound(bound: Optional[int]) -> Optional[int]:
    """Treat negative/unspecified bounds as unbounded (``None``)."""
    if bound is None or bound < 0:
        return None
    return bound


def _bound_arg(bound: Optional[int]) -> int:
    """Map Python bound semantics to C-core sentinel semantics."""
    return -1 if bound is None else bound


def _validate_sizes_for_bigint_fallback(
    sizes: Iterable[Size],
) -> Sizes:
    """Validate rectangle sizes for the fallback path."""
    validated = []
    for width, height in sizes:
        if not isinstance(width, int):
            raise TypeError("Rectangle width must be an integer")
        if not isinstance(height, int):
            raise TypeError("Rectangle height must be an integer")
        if width <= 0:
            raise ValueError("Rectangle width must be positive integer")
        if height <= 0:
            raise ValueError("Rectangle height must be positive integer")
        validated.append((width, height))
    return validated


def _fits_clong_core(
    sizes: Sizes,
    max_width: Optional[int],
    max_height: Optional[int],
) -> bool:
    """Return whether instance bookkeeping can fit in C ``long``."""
    if max_width is not None and max_width > _CLONG_MAX:
        return False
    if max_height is not None and max_height > _CLONG_MAX:
        return False

    sum_width = 0
    sum_height = 0
    total_area = 0
    for width, height in sizes:
        if width > _CLONG_MAX or height > _CLONG_MAX:
            return False
        if width > _CLONG_MAX // height:
            return False
        sum_width += width
        sum_height += height
        if sum_width > _CLONG_MAX or sum_height > _CLONG_MAX:
            return False
        total_area += width * height
        if total_area > _CLONG_MAX:
            return False
    return True


def _reduce_by_axis_gcd(
    sizes: Sizes,
    max_width: Optional[int],
    max_height: Optional[int],
) -> Tuple[Sizes, Optional[int], Optional[int], int, int]:
    """Apply exact axis-wise ``gcd`` reduction when possible."""
    gcd_width = 0
    gcd_height = 0
    for width, height in sizes:
        gcd_width = math.gcd(gcd_width, width)
        gcd_height = math.gcd(gcd_height, height)
        if gcd_width == 1 and gcd_height == 1:
            break
    if gcd_width <= 1 and gcd_height <= 1:
        return sizes, max_width, max_height, 1, 1

    reduced_sizes = [
        (width // gcd_width, height // gcd_height) for width, height in sizes
    ]
    reduced_max_width = None if max_width is None else max_width // gcd_width
    reduced_max_height = None if max_height is None else max_height // gcd_height
    return (
        reduced_sizes,
        reduced_max_width,
        reduced_max_height,
        gcd_width,
        gcd_height,
    )


def _build_approximation(
    sizes: Sizes,
    max_width: Optional[int],
    max_height: Optional[int],
    scale: int,
) -> Tuple[Sizes, Optional[int], Optional[int]]:
    """Return ceil-scaled rectangles with floor-scaled bounds."""
    scaled_sizes = [
        (_ceil_div(width, scale), _ceil_div(height, scale))
        for width, height in sizes
    ]
    scaled_max_width = None if max_width is None else max_width // scale
    scaled_max_height = None if max_height is None else max_height // scale
    return scaled_sizes, scaled_max_width, scaled_max_height


def _min_scale_for_floor_bound(bound: Optional[int]) -> int:
    """Return minimum scale so ``bound // scale`` can fit in C ``long``."""
    if bound is None or bound <= _CLONG_MAX:
        return 1
    return bound // (_CLONG_MAX + 1) + 1


def _initial_approx_scale(
    sizes: Sizes,
    max_width: Optional[int],
    max_height: Optional[int],
) -> int:
    """Estimate a power-of-two approximation scale for overflow instances."""
    min_scale = 1
    sum_width = 0
    sum_height = 0
    max_rect_area = 0
    total_area = 0

    for width, height in sizes:
        min_scale = max(min_scale, _ceil_div(width, _CLONG_MAX))
        min_scale = max(min_scale, _ceil_div(height, _CLONG_MAX))
        sum_width += width
        sum_height += height
        rect_area = width * height
        if rect_area > max_rect_area:
            max_rect_area = rect_area
        total_area += rect_area

    min_scale = max(min_scale, _ceil_div(sum_width, _CLONG_MAX))
    min_scale = max(min_scale, _ceil_div(sum_height, _CLONG_MAX))
    if max_width is not None and max_width < sum_width:
        min_scale = max(min_scale, _min_scale_for_floor_bound(max_width))
    if max_height is not None and max_height < sum_height:
        min_scale = max(min_scale, _min_scale_for_floor_bound(max_height))

    # Area is quadratic in scale; these terms avoid many retry loops when the
    # fallback was entered because area bookkeeping exceeded C long limits.
    if max_rect_area > _CLONG_MAX:
        min_scale = max(min_scale, _ceil_sqrt(_ceil_div(max_rect_area, _CLONG_MAX)))
    if total_area > _CLONG_MAX:
        min_scale = max(min_scale, _ceil_sqrt(_ceil_div(total_area, _CLONG_MAX)))

    return _next_power_of_two(min_scale)


def _scale_positions(
    positions: Positions,
    factor_x: int,
    factor_y: int,
) -> Positions:
    """Scale all placement coordinates by axis-specific integer factors."""
    if factor_x == 1 and factor_y == 1:
        return positions
    return [(x * factor_x, y * factor_y) for x, y in positions]


def _bbox_size_py(
    sizes: Sizes,
    positions: Positions,
) -> Size:
    """Compute enclosing width/height with Python integer arithmetic."""
    max_width = 0
    max_height = 0
    for i in range(len(sizes)):
        width, height = sizes[i]
        x, y = positions[i]
        if width + x > max_width:
            max_width = width + x
        if height + y > max_height:
            max_height = height + y
    return max_width, max_height


def _validate_and_materialize_helper_inputs(
    sizes: Sequence[Size],
    positions: Sequence[Position],
) -> Tuple[Sizes, Positions]:
    """Validate helper inputs and materialize them as concrete lists."""
    validated_sizes = []
    validated_positions = []
    for i in range(len(sizes)):
        width, height = sizes[i]
        x, y = positions[i]
        if not isinstance(width, int):
            raise TypeError("Rectangle width must be an integer")
        if not isinstance(height, int):
            raise TypeError("Rectangle height must be an integer")
        if not isinstance(x, int):
            raise TypeError("Rectangle x position must be an integer")
        if not isinstance(y, int):
            raise TypeError("Rectangle y position must be an integer")
        validated_sizes.append((width, height))
        validated_positions.append((x, y))
    return validated_sizes, validated_positions


def _enforce_explicit_bounds(
    sizes: Sizes,
    positions: Positions,
    max_width: Optional[int],
    max_height: Optional[int],
) -> None:
    """Raise ``PackingImpossibleError`` if resulting bbox exceeds a bound."""
    width, height = _bbox_size_py(sizes, positions)
    if max_width is not None and width > max_width:
        raise PackingImpossibleError(
            "max_width exceeded after bigint fallback (positions violate bounds)",
            positions,
        )
    if max_height is not None and height > max_height:
        raise PackingImpossibleError(
            "max_height exceeded after bigint fallback (positions violate bounds)",
            positions,
        )


def _check_scaled_bound_zero_artifact(
    scaled_max_width: Optional[int],
    scaled_max_height: Optional[int],
    original_max_width: Optional[int],
    original_max_height: Optional[int],
) -> None:
    """Reject approximation artifacts where floor-scaling collapses a bound."""
    if (
        scaled_max_width == 0
        and original_max_width is not None
        and original_max_width > 0
    ):
        raise PackingImpossibleError(
            "max_width too small under bigint approximation",
            [],
        )
    if (
        scaled_max_height == 0
        and original_max_height is not None
        and original_max_height > 0
    ):
        raise PackingImpossibleError(
            "max_height too small under bigint approximation",
            [],
        )


def _rescale_packing_error(
    error: PackingImpossibleError,
    factor_x: int,
    factor_y: int,
) -> PackingImpossibleError:
    """Rescale partial positions from approximation units to original units."""
    if len(error.args) < 2:
        return error
    partial = error.args[1]
    if not isinstance(partial, (list, tuple)):
        return error
    return PackingImpossibleError(
        error.args[0],
        _scale_positions(list(partial), factor_x, factor_y),
        *error.args[2:],
    )


def pack_with_bigint_fallback(
    sizes: Sizes,
    max_width: Optional[int],
    max_height: Optional[int],
) -> Positions:
    """Pack rectangles through the bigint fallback pipeline."""
    normalized_sizes = _validate_sizes_for_bigint_fallback(sizes)
    normalized_max_width = _normalize_positive_bound(max_width)
    normalized_max_height = _normalize_positive_bound(max_height)
    # Bounds at or above the one-axis sum are non-binding for this algorithm.
    # Treat them as unbounded through fallback + final validation to avoid
    # approximation-only false negatives.
    effective_max_width = normalized_max_width
    effective_max_height = normalized_max_height
    total_width = sum(width for width, _ in normalized_sizes)
    total_height = sum(height for _, height in normalized_sizes)
    if effective_max_width is not None and effective_max_width >= total_width:
        effective_max_width = None
    if effective_max_height is not None and effective_max_height >= total_height:
        effective_max_height = None
    (
        reduced_sizes,
        reduced_max_width,
        reduced_max_height,
        scale_x,
        scale_y,
    ) = _reduce_by_axis_gcd(
        normalized_sizes,
        effective_max_width,
        effective_max_height,
    )
    reduced_sum_width = sum(width for width, _ in reduced_sizes)
    reduced_sum_height = sum(height for _, height in reduced_sizes)
    if reduced_max_width is not None and reduced_max_width >= reduced_sum_width:
        reduced_max_width = None
    if reduced_max_height is not None and reduced_max_height >= reduced_sum_height:
        reduced_max_height = None

    approx_scale = _initial_approx_scale(
        reduced_sizes,
        reduced_max_width,
        reduced_max_height,
    )
    while True:
        scaled_sizes, scaled_max_width, scaled_max_height = _build_approximation(
            reduced_sizes,
            reduced_max_width,
            reduced_max_height,
            approx_scale,
        )
        _check_scaled_bound_zero_artifact(
            scaled_max_width,
            scaled_max_height,
            normalized_max_width,
            normalized_max_height,
        )
        if not _fits_clong_core(scaled_sizes, scaled_max_width, scaled_max_height):
            approx_scale *= 2
            continue
        factor_x = scale_x * approx_scale
        factor_y = scale_y * approx_scale
        try:
            positions = _pack(
                scaled_sizes,
                _bound_arg(scaled_max_width),
                _bound_arg(scaled_max_height),
            )
        except OverflowError:
            # Defensive retry: if the C core reports overflow, increase the
            # power-of-two scale and reattempt with a smaller approximate
            # instance.
            approx_scale *= 2
            continue
        except PackingImpossibleError as error:
            raise _rescale_packing_error(error, factor_x, factor_y) from None
        # Ceil-scaling of sides can leave quantization gaps after scaling back.
        # We intentionally accept those gaps and skip compaction because the
        # compaction pass was much slower in practice while improving density
        # only by negligible amounts for typical fallback workloads.
        final_positions = _scale_positions(positions, factor_x, factor_y)
        _enforce_explicit_bounds(
            normalized_sizes,
            final_positions,
            normalized_max_width,
            normalized_max_height,
        )
        return final_positions


def bbox_size_with_bigint_fallback(
    sizes: Sequence[Size],
    positions: Sequence[Position],
) -> Size:
    """Python-int fallback for :func:`rpack.bbox_size`."""
    validated_sizes, validated_positions = _validate_and_materialize_helper_inputs(
        sizes,
        positions,
    )
    return _bbox_size_py(validated_sizes, validated_positions)


def packing_density_with_bigint_fallback(
    sizes: Sequence[Size],
    positions: Sequence[Position],
) -> float:
    """Python-int fallback for :func:`rpack.packing_density`."""
    validated_sizes, validated_positions = _validate_and_materialize_helper_inputs(
        sizes,
        positions,
    )
    width, height = _bbox_size_py(validated_sizes, validated_positions)
    area_bounding_box = width * height
    area_rectangles = sum(width * height for width, height in validated_sizes)
    return area_rectangles / area_bounding_box


def overlapping_with_bigint_fallback(
    sizes: Sequence[Size],
    positions: Sequence[Position],
) -> Optional[Tuple[int, int]]:
    """Python-int fallback for :func:`rpack.overlapping`."""
    validated_sizes, validated_positions = _validate_and_materialize_helper_inputs(
        sizes,
        positions,
    )
    n = len(validated_sizes)
    for i in range(n):
        width_1, height_1 = validated_sizes[i]
        x_1, y_1 = validated_positions[i]
        for j in range(i + 1, n):
            width_2, height_2 = validated_sizes[j]
            x_2, y_2 = validated_positions[j]
            disjoint_in_x = (x_1 + width_1 <= x_2 or x_2 + width_2 <= x_1)
            disjoint_in_y = (y_1 + height_1 <= y_2 or y_2 + height_2 <= y_1)
            if not (disjoint_in_x or disjoint_in_y):
                return (i, j)
    return None
