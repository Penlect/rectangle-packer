
# Built-in
from collections import namedtuple
import random

# PyPI
import pytest

# Local
import rpack

R = namedtuple('R', 'width height x y')


def enclosing_size(sizes, positions):
    """Return enclosing size of rectangles having sizes and positions"""
    rectangles = [R(*size, *pos) for size, pos in zip(sizes, positions)]
    width = max(r.width + r.x for r in rectangles)
    height = max(r.height + r.y for r in rectangles)
    return width, height


def test_enclosing_size():
    """Test enclosing size helper function"""
    sizes = [(3, 5), (1, 1), (1, 1)]
    positions = [(0, 0), (3, 0), (0, 5)]
    width, height = enclosing_size(sizes, positions)
    assert width == 4
    assert height == 6

def test_origin():
    """Single rectangle should be positioned in origin"""
    rectangles = [(3, 5)]
    positions = [(0, 0)]
    assert rpack.pack(rectangles) == positions

def test_perfect_pack():
    """Pack rectangles to perfect rectangle

    Like this::

        aaa  bb  cc  -->  aaabb
        aaa  bb           aaabb
        aaa               aaacc
    """
    rectangles = [(3, 3), (2, 2), (2, 1)]
    positions = [(0, 0), (3, 0), (3, 2)]
    assert rpack.pack(rectangles) == positions

def test_basic_pack():
    """Single rectangle should be positioned in origin"""
    sizes = [(2, 2), (2, 2), (2, 2), (3, 3)]
    positions = rpack.pack(sizes)
    width, height = enclosing_size(sizes, positions)
    assert width*height == 25

def test_medium_pack():
    sizes = [(i, i) for i in range(20, 1, -1)]
    positions = rpack.pack(sizes)
    width, height = enclosing_size(sizes, positions)
    assert width*height <= 3045

def test_no_overlap():
    """Make sure no rectangles overlap"""
    random.seed(123)
    rectangles = [(random.randint(50, 100), random.randint(50, 100))
                  for _ in range(40)]
    positions = rpack.pack(rectangles)
    for i, ((x1, y1), (w1, h1)) in enumerate(zip(positions, rectangles)):
        for j, ((x2, y2), (w2, h2)) in enumerate(zip(positions, rectangles)):
            if i != j:
                disjoint_in_x = (x1 + w1 <= x2 or x2 + w2 <= x1)
                disjoint_in_y = (y1 + h1 <= y2 or y2 + h2 <= y1)
                assert disjoint_in_x or disjoint_in_y

# TEST INPUT
# ==========

def test_empty():
    """Empty input should give empty output"""
    rectangles = []
    positions = []
    assert rpack.pack(rectangles) == positions

def test_zero():
    """Zero number should raise ValueError"""
    with pytest.raises(ValueError):
        rpack.pack([(0, 0)])

def test_negative():
    """Negative number should raise ValueError"""
    with pytest.raises(ValueError):
        rpack.pack([(3, -5)])
    with pytest.raises(ValueError):
        rpack.pack([(-3, 5)])
    with pytest.raises(ValueError):
        rpack.pack([(-3, -5)])

def test_not_iterable():
    """Non-number should raise ValueError"""
    with pytest.raises(TypeError):
        rpack.pack(None)

def test_not_height_width():
    """Non-number should raise ValueError"""
    with pytest.raises(TypeError):
        rpack.pack([None])

def test_not_integers():
    """Non-number should raise ValueError"""
    with pytest.raises(TypeError):
        rpack.pack([('garnet', 9)])
    with pytest.raises(TypeError):
        rpack.pack([(9, 'alexandros')])

def test_floats():
    with pytest.raises(TypeError):
        rpack.pack([[1.99, 1.99]])
