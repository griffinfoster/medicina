#!/usr/bin/env python
"""
Print attributes and history of a correlator h5 file
"""

import numpy as n
import math, sys, os, optparse
from scipy import optimize
import h5py
import time
import pylab

o = optparse.OptionParser()
o.set_usage('corr_h5_info.py [options] *.h5')
o.set_description(__doc__)
opts,args = o.parse_args(sys.argv[1:])
if args==[]:
    print 'Please specify a hdf5 file! \nExiting.'
    exit()
else:
    fnames = args

def print_key(key,grp,prefix):
    if type(grp[key]) == h5py.highlevel.Dataset: print prefix, 'Dataset:', key, grp[key].shape
    elif type(grp[key]) == h5py.highlevel.Group:
        print prefix, 'Group:', key
        prefix+='\t'
        print_all_keys(grp[key],prefix)

def print_all_keys(grp,prefix):
    for key in grp.iterkeys():
        print_key(key,grp,prefix)

for fi, fname in enumerate(fnames):
    print "Opening:",fname, "(%d of %d)"%(fi+1,len(fnames))
    fh = h5py.File(fname, 'r')
   
    print '\nAttributes:'
    for attr in fh.attrs.items(): print '\t', attr[0] , ':', attr[1]

    if 'history' in fh.keys():
        print '\nHistory:'
        print fh['history'].value
        #for hv in fh['history'].value: print '\t',hv
  
    print '\nLayout:'
    print_all_keys(fh,'')

    fh.flush()
    fh.close()

