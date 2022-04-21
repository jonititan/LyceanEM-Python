from setuptools import setup, find_packages
import versioneer
packages=find_packages(include=['lyceanem','lyceanem.*'])

setup(
  name='LyceanEM',
  version=versioneer.get_versions()["version"],
  description='LyceanEM is a Python library for modelling electromagnetic propagation for sensors and communications. You can find the documentation at https://lyceanem-python.readthedocs.io/en/latest/',
  packages=packages,
  python_requires='>=3.7',
  cmdclass=versioneer.get_cmdclass(),
  install_requires=[
    'numpy~=1.21',
    'open3d~=0.9.0.0',
    'matplotlib~=3.3.4',
    'numba~=0.55.0',
    'solidpython~=1.1.1',
    'scipy~=1.6.2',
  ],
  package_dir={'lyceanem.electromagnetics':'./lyceanem/electromagnetics',
               'lyceanem.geometry':'./lyceanem/geometry',
               'lyceanem.models':'./lyceanem/models',
               'lyceanem.raycasting':'./lyceanem/raycasting',
               'lyceanem':'./',
               },
  url='https://lyceanem-python.readthedocs.io/en/latest/index.html',
  author='Timothy Pelham',
  author_email='t.g.pelham@bristol.ac.uk',
  classifiers=[
        # https://pypi.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 3 - Alpha",
        "Environment :: GPU :: NVIDIA CUDA",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Other Audience",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Education",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Mathematics",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Scientific/Engineering :: Electromagnetics",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
  long_description=open('README.rst').read(),
  long_description_content_type='text/x-rst',
)