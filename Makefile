# Grab version and tags from GIT
VERSION = $(shell git describe --tags --always)
TAG = $(shell git describe --tags --abbrev=0)
SDIST = rectangle-packer-$(VERSION).tar.gz
IMG_HOST = "https://penlect.com"
PYTHON = "python3"

all:

build: dist/$(SDIST)

# Build extension module and source distribution
dist/$(SDIST): src/*.c include/*.h rpack/*.pyx rpack/*.pxd
	-rm -rf build/
	sed -i -E "s/__version__ = '(.*)'/__version__ = '$(VERSION)'/g" rpack/__init__.py
	$(PYTHON) setup.py build_ext --inplace
	$(PYTHON) setup.py sdist
	test -f dist/$(SDIST)

# Generate cython annotations
rpack/_core.html: rpack/_core.pyx
	$(PYTHON) -m cython -a -3 rpack/_core.pyx

# Build program to run C-level test cases
test/c_tests: src/rpackcore.c include/rpackcore.h
	gcc -Wall -Wextra -std=c99 -pedantic -Wmissing-prototypes -Wstrict-prototypes \
	    -Wold-style-definition -I include/ src/rpackcore.c -O3 -o test/c_tests

# Run Python and C-level test cases
test: build test/c_tests rpack/_core.html
	./test/c_tests
	$(PYTHON) -W default -u -m unittest discover -v -s test/

# Run benchmark and create plots
benchmark:
	$(PYTHON) -u -O misc/crunch.py --output-dir artifacts/$(VERSION)/data
	$(PYTHON) -u misc/recstat.py --input-dir artifacts/$(VERSION)/data --output-dir artifacts/$(VERSION)/img

# Build sphinx documentation: HTML + PDF
# Not very nice, but use sed to update all versions in image urls
doc: doc/*.rst doc/conf.py build
	sed -i -E "s@$(IMG_HOST)/rpack/(.*)/img/@$(IMG_HOST)/rpack/$(VERSION)/img/@g" doc/*.rst rpack/__init__.py
	cd doc && make html latexpdf

# Remove non-VCS files
clean:
	sed -i -E "s/__version__ = '(.*)'/__version__ = '$(TAG)'/g" rpack/__init__.py
	sed -i -E "s@$(IMG_HOST)/rpack/(.*)/img/@$(IMG_HOST)/rpack/$(TAG)/img/@g" doc/*.rst rpack/__init__.py
	-cd doc && make clean
	-rm -rf dist/ build/ artifacts/
	-rm -rf *.egg-info/
	-rm rpack/*.so
	-rm rpack/_core.c
	-rm rpack/_core.html
	-rm test/c_tests
	-rm -rf **/__pycache__/
	-rm -rf __pycache__/
	-rm -rf .eggs

.PHONY: all build sdist test benchmark doc clean
