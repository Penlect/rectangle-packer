PYTHON ?= python3
CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=c99 -pedantic -Wmissing-prototypes -Wstrict-prototypes \
	-Wold-style-definition -O3
CPPFLAGS ?= -I include/
VERSION = $(shell sed -n -E 's/^__version__ = "([^"]+)"/\1/p' rpack/__init__.py)
SDIST = rectangle_packer-$(VERSION).tar.gz

all:

build: dist/$(SDIST)

sdist: dist/$(SDIST)

# Build extension module and source distribution
dist/$(SDIST): src/*.c include/*.h rpack/*.pyx rpack/*.pxd pyproject.toml setup.py README-pypi.rst
	-rm -rf build/
	$(PYTHON) setup.py build_ext --inplace
	$(PYTHON) -m build --sdist --no-isolation --outdir dist || $(PYTHON) setup.py sdist
	test -f dist/$(SDIST)

# Generate cython annotations
rpack/_core.html: rpack/_core.pyx
	$(PYTHON) -m cython -a -3 rpack/_core.pyx

# Build program to run C-level test cases
test/c_tests: src/rpackcore.c include/rpackcore.h
	$(CC) $(CFLAGS) $(CPPFLAGS) src/rpackcore.c -o test/c_tests

# Run Python and C-level test cases
test: build test/c_tests
	./test/c_tests
	$(PYTHON) -W default -u -m unittest discover -v -s test/

# Run benchmark and create plots
benchmark:
	$(PYTHON) -u -O misc/crunch.py --output-dir artifacts/$(VERSION)/data
	$(PYTHON) -u misc/recstat.py --input-dir artifacts/$(VERSION)/data --output-dir artifacts/$(VERSION)/img

# Build sphinx documentation: HTML
doc: doc/*.rst doc/conf.py build
	$(MAKE) -C doc html

# Remove non-VCS files
clean:
	-$(MAKE) -C doc clean
	-rm -rf dist/ build/ artifacts/
	-rm -rf *.egg-info/
	-rm rpack/*.so
	-rm rpack/_core.c
	-rm rpack/_core.html
	-rm test/c_tests
	-find . -type d -name __pycache__ -prune -exec rm -rf {} +
	-rm -rf .eggs

.PHONY: all build sdist test benchmark doc clean
