from setuptools import setup, Extension, find_packages

with open('README.rst') as readme_file:
    long_description = readme_file.read()

setup(
    name='rectangle-packer',
    version='1.1.0',
    author='Daniel Andersson',
    author_email='daniel.4ndersson@gmail.com',
    description='Pack a set of rectangles into an enclosing rectangle with minimum area',
    long_description=long_description,
    license='MIT',
    keywords='pack rectangle packing rectangles enclosing 2D',
    url='https://github.com/Penlect/rectangle-packer',
    ext_modules=[
        Extension('rpack._rpack',
                  sources=['src/rpack.c', 'src/areapack.c', 'src/taskpack.c'],
                  include_dirs=['include'])],
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Programming Language :: C',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython'
    ]
)
