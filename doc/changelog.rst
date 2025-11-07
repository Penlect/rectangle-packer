=========
Changelog
=========

Unreleased
==========

**Removed:**

* Extension module ``rpack._rpack`` along with the legacy ``rpack.group``
  implementation and deprecated ``rpack._rpack.pack`` entry point.


Version 2.0.5 (2025-11-07)
==========================

**Added:**

* Binary wheels and packaging metadata for Python 3.14.

**Bugfixes:**

* ``rpack.pack()`` now preserves ``max_width``/``max_height`` values of zero so
  that impossible packings raise ``PackingImpossibleError`` correctly instead of
  being treated as unbounded.


Version 2.0.4 (2025-03-30)
==========================

**Other changes:**

* Publishing a release on GitHub now uploads the built distribution to PyPI
  automatically.


Version 2.0.3 (2025-03-30)
==========================

**Changed:**

* Documentation builds target HTML only, removing the LaTeX toolchain and
  updating the Read the Docs configuration accordingly.
* Reformatted the Python sources and documentation helpers with ``black`` to
  standardize code style across the project.
* Improved the release workflow to handle PyPI uploads reliably, including
  fixing the long description metadata and skipping artefacts that were already
  published.

**Bugfixes:**

* Removed unused bookkeeping in ``taskpack.c`` to silence compiler warnings.


Version 2.0.2 (2023-10-10)
==========================

**Added:**

* Declared support for Python 3.12 in the package metadata.

**Changed:**

* Adopted GitHub Actions (cibuildwheel) for building release artefacts across
  supported platforms.
* Updated hosted documentation assets and build configuration.
* Relaxed the Cython build configuration to stay compatible with newer Cython
  releases while silencing future ``nogil`` signature warnings.

**Bugfixes:**

* Restored compatibility with Cython 3 when compiling the extension module.


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
