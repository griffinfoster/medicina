from setuptools import setup
import os, sys, glob

__version__ = '0.1'

setup(name = 'poxy',
      version = __version__,
      description = 'Control scripts and analysis tools for CASPER based instruments',
      requires = ['katcp', 'pylab', 'numpy', 'spead'],
      provides = ['poxy'],
      package_dir = {'poxy':'src'},
      packages = ['poxy'],
      scripts=glob.glob('scripts/instrument/*.py')+glob.glob('scripts/analysis/*.py')+glob.glob('scripts/instrument/*.ui'),
)
