"""rpack build script"""

import importlib.util
from setuptools import setup, Extension, find_packages

# The package can't be imported at this point since the extension
# module rpack._core does not exist yet. Therefore, we import
# __init__.py partially.
with open('rpack/__init__.py') as init:
    lines = list()
    for line in init.readlines():
        if line.startswith(('from ', 'import ')):
            break
        lines.append(line)
spec = importlib.util.spec_from_loader('init', loader=None)
init = importlib.util.module_from_spec(spec)
exec(''.join(lines), init.__dict__)

# Generate the readme file from the doc string.
with open('README.rst', 'w') as readme_file:
    lines = init.__doc__.splitlines()[1:]
    content = '\n'.join(lines).lstrip()
    # Github/gitlab does not like pdf
    content = content.replace('.pdf', '.png')
    readme_file.write(content)

ext_modules = [
    Extension(
        'rpack._core',
        sources=['rpack/_core.pyx', 'src/rpackcore.c'],
        include_dirs=['include']),
    Extension(
        # The rpack._rpack extension module is deprecated. It will be
        # removed in a future version. This was the implementation
        # used in versions 1.0.0 and 1.1.0.
        'rpack._rpack',
        sources=['src/rpack.c', 'src/areapack.c', 'src/taskpack.c'],
        include_dirs=['include'])
]
for e in ext_modules:
    e.cython_directives = {
        'language_level': '3',
        'embedsignature': True
    }

setup(
    name='rectangle-packer',
    version=init.__version__,
    author=init.__author__,
    author_email=init.__email__,
    description=init.__doc__.splitlines()[0].strip(),
    long_description=init.__doc__,
    license=init.__license__,
    keywords='pack rectangle packing rectangles enclosing 2D',
    url=init.__url__,
    ext_modules=ext_modules,
    packages=find_packages(exclude=("test",)),
    include_package_data=True,
    setup_requires=[
        'setuptools>=18.0',
        'cython'
    ],
    test_suite="test",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Programming Language :: C',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython'
    ]
)
