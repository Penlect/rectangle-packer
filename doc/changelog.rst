=========
Changelog
=========

Version 2.0.1 (2021-05-13)
==========================

**Bugfixes:**

* ``rpack.pack()`` behaved incorrectly when the arguments ``max_width`` and/or ``max_height`` were used. For instance, it could return incorrect rectangle positions which made the rectangles overlap.

Version 2.0.0 (2020-12-29)
==========================

**Added:**

* Two new keyword arguments to ``rpack.pack()`` named ``max_width``
  and ``max_height`` used to optionally set restrictions on the
  resulting bounding box.
* Exception ``PackingImpossibleError``.
* Function ``rpack.bbox_size``.
* Function ``rpack.packing_density``.
* Function ``rpack.overlapping``.
* Build dependency to Cython.

**Changed:**

* Improved ``rpack.pack()`` algorithm to yield higher packing density.
* Improved ``rpack.pack()`` time complexity; ~x100 faster compared to
  version 1.1.0.
* The rectangles are sorted internally in ``rpack.pack()`` so the
  input ordering does no longer matter.
* Renamed ``rpack.enclosing_size`` to ``rpack.bbox_size``.

**Removed/deprecated:**

* Function ``rpack.group()``. It is still available at
  ``rpack._rpack.group()`` but will be removed completely in the
  future.
* Old implementation of ``rpack.pack()``. It is still available at
  ``rpack._rpack.pack()`` but will be removed in the future.

**Other changes:**

* Updated Sphinx documentation.


Version 1.1.0 (2019-01-26)
==========================

**Added:**

* New function ``rpack.group()``.
* Sphinx docs.

**Changed:**

* Improved test cases.
* Improved error handling.

Version 1.0.0 (2017-07-23)
==========================

**Added:**

* First implementation.
