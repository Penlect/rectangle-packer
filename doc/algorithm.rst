
=============
The Algorithm
=============

To find the minimum bounding box, a lot of candidate bounding boxes
are tested.

The algorithm keeps track of a grid of cells internally.  Each cell
belongs to a column and a row. The index of the column and row are
used together as a key in a lookup table (known as the "jump matrix")
which contains and information needed to decide if the corresponding
cell is free or occupied.

As more and more rectangles are added, the grid gets partitioned in
smaller and smaller pieces, and the number of cells, columns and rows
increases.

If all rectangles were successfully packed inside the bounding box,
its area is recorded and another bounding box, with smaller area is
selected - and the procedure continues on that candidate. When all
feasible bounding boxes are tested, the best one is used for the final
packing. The rectangles' positions from this final packing is returned
by :py:func:`rpack.pack`.

Extra grid lines have been added to the image below to demonstrate how
these cells are created.

.. only:: latex

  .. image:: https://penlect.com/rpack/2.0.1/img/example_grid.pdf
     :alt: compute time
     :align: center

.. only:: html

  .. figure:: https://penlect.com/rpack/2.0.1/img/example_grid.gif
     :alt: compute time
     :align: center

The algorithm is not documented more than this yet. Until it is, you
will have to study the files ``src/rpackcore.c`` and
``rpack/_core.pyx`` for more details.
