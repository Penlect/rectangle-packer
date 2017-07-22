from setuptools import setup, Extension

with open('README.md') as readme_file:
    long_description = readme_file.read()

setup(
    name='rectangle-packer',
    version='1.0.0',
    author='Daniel Andersson',
    author_email='daniel.4ndersson@gmail.com',
    description='Pack a set of rectangles into an enclosing rectangle with minimum area',
    long_description=long_description,
    license='MIT',
    keywords='pack rectangle packing rectangles enclosing',
    url='https://github.com/Penlect/rectangle-packer',
    ext_modules=[Extension('rpack',sources=['src/rpack.c',
                                            'src/algorithm.c',
                                            'src/placing.c'],
                           include_dirs=['include'])],
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Programming Language :: C',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython'
    ]
)
