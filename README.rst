rectangle-packer
================
Rectangle packing program.

Given a set of rectangles with fixed orientations, we want to
find an enclosing rectangle of minimum area that contains
them all with no overlap.

This project is inspired by the blog post
`Fast Optimizing Rectangle Packing Algorithm for Building CSS Sprites
<http://www.codeproject.com/Articles/210979/Fast-optimizing-rectangle-packing-algorithm-for-bu>`_
written by Matt Perdeck.

.. image:: example.png
    :alt: Example

Installation
------------

Download the package or clone the repository, then install with:

.. code:: sh

    $ python setup.py install

or use pypi:

.. code:: sh

    $ pip install rectangle-packer


.. note:: *Only Python 3 is supported. Legacy Python (2.7 and earlier)
          is not supported.*

Basic Usage
-----------

.. code:: python
    import rpack  # This is the module name

    # Create a bunch of rectangles (width, height)
    recs = [(58, 206), (231, 176), (35, 113), (46, 109), (68, 65), (90, 63)]

    # Run the algorithm
    positions = rpack.pack(recs)

    # The result will be a list of (x, y) positions:
    >>> positions
    [(0, 0), (58, 0), (289, 0), (289, 113), (58, 176), (126, 176)]

The output positions are the top left corner coordinates of each
rectangle in the input (if we assume origin is in the top left corner).

These positions will yield a packing with no overlaps and enclosing
area as small as possible.

*For best result, sort the rectangles by height, highest first,
before running* `rpack.pack`. The algorithm is probably far from
the best available. But in most cases it gives quite good results.

Note that you can only provide **positive integers** as rectangle width
and height.

## Example

.. image:: example2.png
    :alt: Example2

The following image is contributed by `Paul Brodersen <http://paulbrodersen.pythonanywhere.com/>`_,
and illustrates how this package can be used on a real problem
(discussed here: `stackoverflow <https://stackoverflow.com/a/53156709/2912349>`_).

.. image:: https://i.stack.imgur.com/kLat8.png
    :alt: PaulBrodersenExample
    :width: 640px
