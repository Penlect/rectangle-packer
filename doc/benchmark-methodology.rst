=====================
Benchmark methodology
=====================

Tools for reproducing measurements and evaluating future releases. For a quick
assessment of the released package, see :doc:`benchmarks`.

The public guide keeps one reference dataset for a released version. Refresh
it when a release changes the packing implementation. The 2.1.1 run used
Debian 13 and CPython 3.13.5 with one worker. The CPU used the
``powersave`` governor with variable frequency.

Running a campaign
==================

The runner uses Debian's Python, Cython, compiler and plotting packages. On
Debian 13, the complete build and plotting dependencies can be installed with:

.. code-block:: console

   $ sudo apt-get install gcc make cython3 python3-dev python3-setuptools python3-build python3-wheel python3-matplotlib

``make benchmark-smoke`` runs a small end-to-end check. ``make benchmark``
uses the full profile. Both create a new directory under ``artifacts/`` and
build a fresh native extension inside that run. An existing run directory,
even an empty one, is rejected.

For explicit control:

.. code-block:: console

   $ python3 -m benchmark run --profile smoke --output-dir artifacts/check-001
   $ python3 -m benchmark plot --input-dir artifacts/check-001 --output-dir artifacts/check-001/plots

The default is one worker pinned where supported, leaving other cores
available. ``--workers 8`` measures calls under concurrent load on eight physical
cores. Concurrent runs finish sooner but include contention and frequency
changes; do not compare them directly with single-worker latency.
Avoid other CPU-intensive work on the measurement host in either mode.

The ``publication`` profile increases the number of independent random inputs
and timing blocks, extends the random count sweep to 300 and 400 rectangles,
and includes more constrained and bigint workloads. It can take hours on one
core. ``--timeout 600`` sets the deadline for an entire job: warmup,
calibration and every timing block together. A timeout is recorded explicitly,
the worker is terminated, and the remaining jobs continue. It is not a
600-second lower bound on the duration of a single packing call.

For a remote host, export a buildable source tree with verified origin metadata:

.. code-block:: console

   $ python3 -m benchmark export --output-dir /tmp/TMP_rpack-source

Copy that directory to the measurement host and run the same commands there.
The export includes both the benchmark harness and library source. To measure
an older library with the same harness, add ``--library-ref 2.1.0`` to the
export command. Both revisions and the combined source fingerprint are saved.
The harness requires the bigint-capable API introduced in version 2.1.0.

Use ``--corpus previous-run/corpus.jsonl.gz`` to run exactly the same rectangles,
bounds and expected outcomes against another library build. This freezes the
actual inputs, not just the random seeds or generator parameters.

What is measured
================

Each job warms the packer, calibrates a repeat count, then saves several timing
blocks. A block times repeated calls on one fixed input; the per-input result
is the median block time divided by the number of calls per block. Timing
includes the public Python API and the small calling loop. Input generation,
geometry validation and source hashing are outside the measured blocks.
Garbage collection is disabled during the warmup and timing blocks.

Packing geometry is checked independently using integer coordinates, rectangle
intersections and explicit bounds. The untimed warmup also observes whether
the implementation used the native path, exact GCD reduction, or conservative
bigint approximation; observation hooks are removed before timing.

The suite covers:

* Uniform sides, log-uniform sides and an area/aspect mixture as count grows.
* Matched geometries scaled by powers of two, exercising exact GCD fallback.
* Square and fixed-perimeter sequences, and a known thin-rectangle pathology.
* Huge coprime coordinates that require bigint approximation.
* Width- and height-limited sprite-like inputs, repeated small tile sizes,
  an exact bounded grid, and deliberately infeasible constraints.
* Fixtures for one-square-unit area improvements and large-height stalls.

Input-to-input spread and repeated-timing spread answer different questions.
The current summaries retain both. Bootstrap intervals for a median resample
independent inputs; repeated calls within one input do not count as extra
independent inputs. Fixed fixtures therefore have no input-population interval.
All intervals describe this sampled corpus and machine, not every possible
rectangle distribution or host.

Saving and publishing evidence
==============================

Each schema-2 run retains the exact compressed corpus, raw timing blocks,
outcomes, CPU settings, source snapshot, actual compiler log, and native
extension fingerprint. Source changes during a run are detected. Unexpected
exceptions or invalid packings stop the other workers promptly and mark the
campaign failed. Failed or interrupted campaigns cannot be plotted or published.

.. code-block:: console

   $ python3 -m benchmark publish --input-dir artifacts/check-001 --plot-dir artifacts/check-001/plots --output-dir doc/_static/benchmark-data/check-001

Publication verifies the raw measurements and all plot bindings before staging
a self-contained campaign directory. It never overwrites an existing directory
or copies figures over another campaign's images. Raw JSONL is compressed
deterministically. The reader also supports older schema-1 data.

Generate a page whose tables, date and asset links all refer to that campaign:

.. code-block:: console

   $ python3 -m benchmark report --input-dir doc/_static/benchmark-data/check-001 --output doc/benchmarks-check-001.rst

Add that page to the benchmark toctree after reviewing it. Report generation
refuses an existing output file. A new campaign gets a new directory and page;
there is no implicit replacement of an older report. The plotting source
snapshot and plotting dependency versions are retained separately from the
measured library and runner sources, since analysis can occur later.

Comparing revisions
===================

Use the same harness and frozen corpus for both library revisions. For example,
on the measurement host, with these output paths initially absent:

.. code-block:: console

   $ python3 -m benchmark export --library-ref 2.1.1 --output-dir /tmp/TMP_baseline-source
   $ python3 -m benchmark export --output-dir /tmp/TMP_candidate-source
   $ cd /tmp/TMP_baseline-source
   $ python3 -m benchmark run --profile smoke --machine-label machine-1 --output-dir /tmp/TMP_baseline-run
   $ cd /tmp/TMP_candidate-source
   $ python3 -m benchmark run --profile smoke --machine-label machine-1 --corpus /tmp/TMP_baseline-run/corpus.jsonl.gz --output-dir /tmp/TMP_candidate-run
   $ python3 -m benchmark compare /tmp/TMP_baseline-run /tmp/TMP_candidate-run --output-dir /tmp/TMP_comparison

Run the two measurements sequentially. A comparison rejects different input
corpora or different machine labels, worker counts, CPU models, governors, Python versions,
build environments, timing configurations and other recorded conditions.
``--allow-environment-change`` permits an explicitly labeled uncontrolled
comparison, such as exploring one-worker versus concurrent execution; it does
not turn that comparison into evidence about a code change.

``comparison.json`` contains aggregate and per-workload statistics, and
``paired-results.jsonl`` retains every matched input's outcomes, timing ratio
and bounding-box area change. ``report.rst`` provides a readable view. Runtime
and area ratios are candidate divided by baseline: values above one mean
slower calls or larger boxes. Newly timed-out inputs are reported separately,
not assigned zero duration or silently omitted from the outcome counts.

The intervals resample independent inputs. They do not measure systematic
machine drift, so use repeated A/A runs to establish noise and repeat an A/B
comparison before treating a small change as a regression. The largest
individual slowdowns are investigation leads, not automatic pass/fail gates.
The overall median is descriptive: its mixture contains fixed fixtures and
correlated scaled variants, so it has no population confidence interval.
Intervals are provided within individual workload groups instead.
The smoke profile checks the workflow; broader performance conclusions require
the full profile or a corpus representative of the intended application.

Anonymous publication
=====================

``publish`` creates an anonymous public copy by default. Original run directories
remain private and untouched. Public manifests retain CPU and toolchain details
needed to interpret performance, while omitting hostnames, container identifiers,
private Git references, arbitrary metadata fields and exact collection times.
Build-log paths are replaced with placeholders and archive headers are normalized.
Source and artifact hashes are regenerated for the public copies. The exact
input corpus and numeric measurements remain unchanged.

The runner does not record the computer's hostname. To identify measurements
made on the same machine, give both runs an explicit public alias such as
``--machine-label machine-1``. Publication can assign this alias to older runs
with the same option. Labels are user assertions, not hardware attestation;
choose a neutral alias and use it consistently. Comparisons without a label
require ``--allow-environment-change`` and are marked uncontrolled.

Published source snapshots omit Git identifiers and use content hashes instead.
If a known old machine name occurs in harness text, its redaction is recorded.
Publication refuses redaction that would change measured library files, and
rejects recognizable private paths, private network addresses or credential
markers in the resulting evidence, including compressed files. This does not
make arbitrary application inputs or source comments safe to disclose: review
custom corpora and sources before publishing them.

Use the ``publish`` output for distribution. Raw run directories and source
exports can contain private paths and Git metadata and should remain private.
