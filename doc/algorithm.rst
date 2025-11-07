=============
The Algorithm
=============

To find the minimum bounding box, a lot of candidate bounding boxes
are tested.

The algorithm keeps track of a grid of cells internally.  Each cell
belongs to a column and a row. The index of the column and row are
used together as a key in a lookup table (known as the "jump matrix")
which contains the information needed to decide if the corresponding
cell is free or occupied.

As more and more rectangles are added, the grid gets partitioned in
smaller and smaller pieces, and the number of cells, columns and rows
increases.

If all rectangles are successfully packed inside a bounding box, its
area is recorded and another candidate with a smaller area is selected.
The procedure continues with that candidate until all feasible bounding
boxes have been tested. The best candidate is used for the final
packing, and the rectangles' positions from that packing are returned by
:py:func:`rpack.pack`.

Extra grid lines have been added to the image below to demonstrate how
these cells are created.

.. figure:: https://penlect.com/rpack/2.0.2/img/example_grid.gif
   :alt: compute time
   :align: center

The algorithm is not documented any further yet; until it is, study
``src/rpackcore.c`` and ``rpack/_core.pyx`` for more details.
