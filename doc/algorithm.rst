=============
The Algorithm
=============

Overview
========

The goal of :py:func:`rpack.pack` is to place all input rectangles
without overlap inside a bounding box with as small area as possible
(best effort). The implementation is a fast heuristic with strong
practical results, not a formal proof-of-optimality solver.

At a high level, the algorithm repeatedly asks two questions:

1. For this candidate bounding box, can all rectangles be packed?
2. If yes, can we make the box area even smaller and still succeed?

To answer these questions efficiently, the core uses a dynamic grid
representation plus a search loop that adapts its step size when it
detects stalled progress.


Terminology
===========

The terms below are used throughout this page:

* bounding box:
  the outer rectangle that contains the whole packing.
* candidate bounding box:
  one width/height pair currently being tested.
* feasible candidate:
  a candidate where all rectangles can be placed.
* area bound:
  the best feasible area found so far; future candidates must beat it.
* grid cell:
  one rectangular free/occupied region in the internal partitioned grid.
* ``delta``:
  a suggested height increment from one candidate to the next.
* non-improving iteration:
  a candidate test that does not reduce the best area bound.
* coarse step:
  a larger height jump used after repeated non-improving low-``delta``
  iterations.
* local refinement:
  a bounded neighborhood scan near the best coarse result.


End-to-End Flow
===============

Input preparation and safety checks
-----------------------------------

Before searching starts, the Cython layer validates and summarizes
input rectangles:

* widths and heights must be positive integers,
* each rectangle area must fit in the internal integer range,
* the total area must also fit in range.

It also computes aggregate values such as max width, max height, total
width, and total height. These are used to derive hard lower/upper
bounds for legal bounding boxes.


Strategy sweep (ordering and global transpose)
----------------------------------------------

The solver does not rely on a single rectangle order. It evaluates four
strategy variants and keeps the best result:

1. original orientation, sorted by height,
2. original orientation, sorted by width,
3. globally transposed instance, sorted by height,
4. globally transposed instance, sorted by width.

Here, "globally transposed" means all rectangles are solved in swapped
axes (width/height exchanged), and the final coordinates are transposed
back before returning. This explores a different search geometry without
changing the user-visible rectangle sizes.


Feasibility test for one candidate
----------------------------------

For one specific candidate width and height, feasibility is tested by
placing rectangles one by one into an initially empty internal grid.

Each placement performs:

1. region search:
   find the first free region that can hold the rectangle,
2. split/update:
   cut row/column boundaries where needed and mark the occupied region.

If any rectangle cannot be placed, the candidate is infeasible.
If all are placed, the candidate is feasible and yields a used width,
used height, and area.


Internal grid model
-------------------

The core does not allocate one cell per coordinate. Instead it stores a
partitioned grid where boundaries appear only where needed.

It uses three coupled structures:

* row and column cell lists:
  ordered linked lists that store segment end positions,
* jump matrix:
  a row/column lookup table for occupancy and skip pointers,
* region descriptor:
  the candidate row/column span for the current rectangle.

As rectangles are placed, rows and columns are split at rectangle
borders. This creates finer cells only where geometric detail is needed.

The jump matrix stores either:

* free (empty entry),
* a pointer to the next row cell to jump to,
* a sentinel meaning "column is full here".

This lets the search skip known blocked zones quickly instead of
retesting them cell-by-cell.

Extra grid lines have been added to the image below to demonstrate how
cells are created.

.. figure:: _static/img/example_grid.gif
   :alt: partitioned packing grid example
   :align: center


Bounding-box search loop
------------------------

For one strategy variant, the core searches candidate boxes by
increasing height and tightening width from the current area bound.

The loop maintains:

* current candidate ``(width, height)``,
* best feasible area and dimensions found so far,
* bounds from user constraints and rectangle minima.

After each candidate test:

* on success:
  the best area bound is reduced,
* on failure (or no improvement):
  height is increased by an adaptive step and width is recomputed so the
  next candidate stays below the current best area.

This "increase height, decrease width" pattern explores candidates of
strictly smaller area than the current best feasible result.


Search-step acceleration
========================

Why acceleration is needed
--------------------------

In some thin-rectangle edge cases, the raw ``delta`` signal can stay
very small for a long run of non-improving candidates. A naive loop then
checks too many near-identical heights and spends most time in repeated
failed feasibility checks.


Coarse phase (stall escape)
---------------------------

To avoid that stall pattern, the search monitors repeated
non-improving low-``delta`` iterations. When the streak crosses a
threshold, it activates coarse stepping:

* the coarse step grows geometrically (doubling),
* growth is capped by a maximum coarse-step limit,
* larger raw ``delta`` values require longer streaks before activation.

In practice, this means:

* very low ``delta`` stalls are escaped quickly,
* moderate ``delta`` regions are treated more conservatively.


Local refine phase (quality recovery)
-------------------------------------

If coarse stepping was used, the solver performs a bounded local sweep
around the best coarse height found. This recovers candidate quality
near the coarse optimum while keeping runtime bounded.

The refine radius is limited, and refinement only runs when coarse
stepping actually occurred.

In simple terms: jump faster through obviously bad territory, then scan
locally around the best jump result before finalizing.


What the algorithm optimizes
============================

Primary objective:

* minimize bounding-box area for the tested strategy.

Secondary behavior:

* maintain high packing density,
* avoid pathological runtime spikes caused by excessive tiny-step scans.

Because rectangle packing is combinatorial and this implementation is
heuristic, the best practical result is pursued rather than guaranteed
global optimality.


Complexity and practical behavior
=================================

Runtime depends on both:

* rectangle count,
* rectangle size scale and shape distribution.

The dominant cost is repeated feasibility testing of candidate boxes.
The adaptive coarse/refine logic primarily improves worst-tail behavior
for thin-rectangle pathologies while preserving strong behavior on
typical random-style inputs.


Implementation map
==================

For maintainers who want to correlate this description with the source:

* public orchestration and strategy sweep:
  ``rpack/_core.pyx``
* grid structures and placement/search core:
  ``src/rpackcore.c``
* C data structure declarations:
  ``include/rpackcore.h``
