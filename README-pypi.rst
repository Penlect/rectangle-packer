================
rectangle-packer
================

Fast rectangle packing for Python.

Given a set of rectangles with fixed orientations, ``rectangle-packer`` finds
an enclosing bounding box with small area and no overlaps.

Installation
============

.. code:: sh

    python3 -m pip install rectangle-packer

Quick start
===========

.. code:: python

    import rpack

    sizes = [(58, 206), (231, 176), (35, 113), (46, 109)]
    positions = rpack.pack(sizes)
    print(positions)

The output contains ``(x, y)`` coordinates for each rectangle's lower-left
corner.

Documentation and source
========================

* Documentation: https://rectangle-packer.readthedocs.io/en/latest/
* Source code: https://github.com/Penlect/rectangle-packer

