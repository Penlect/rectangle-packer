"""rpack build script"""

import re
from pathlib import Path

from setuptools import setup, Extension, find_packages


def package_version_from_init() -> str:
    with open("rpack/__init__.py", encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(r'^__version__ = "([^"]+)"$', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Failed to read __version__ from rpack/__init__.py")
    return match.group(1)


ext_modules = [
    Extension(
        "rpack._core",
        sources=["rpack/_core.pyx", "src/rpackcore.c"],
        include_dirs=["include"],
    ),
]
for e in ext_modules:
    e.cython_directives = {"language_level": "3", "embedsignature": True}

setup(
    name="rectangle-packer",
    version=package_version_from_init(),
    author="Daniel Andersson",
    author_email="daniel.4ndersson@gmail.com",
    description="Pack a set of rectangles into a bounding box with minimum area",
    long_description=Path("README-pypi.rst").read_text(encoding="utf-8"),
    long_description_content_type="text/x-rst",
    license="MIT",
    keywords="pack rectangle packing rectangles enclosing 2D",
    url="https://github.com/Penlect/rectangle-packer",
    ext_modules=ext_modules,
    packages=find_packages(exclude=("test",)),
    include_package_data=True,
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Programming Language :: C",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
