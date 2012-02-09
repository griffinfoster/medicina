#!/usr/bin/env python
"""
Reset the flags to False
"""

import numpy as n
import math, sys, os, optparse
from scipy import optimize
import h5py
import time
import pylab

o = optparse.OptionParser()
o.set_usage('rst_flags.py [options] *.h5')
o.set_description(__doc__)
opts,args = o.parse_args(sys.argv[1:])
if args==[]:
    print 'Please specify a hdf5 file! \nExiting.'
    exit()
else:
    fnames = args

def append_history(fh,hist_str):
    if not('history' in fh.keys()):
        rv = new_fh.create_dataset('history', data=n.array(hist_str))
    else:
        hv = fh['history'].value
        del fh['history']
        if type(hv) == n.ndarray: new_hist=n.append(hv,n.array([hist_str]))
        else: new_hist=n.array([[hv],[hist_str]])
        rv = fh.create_dataset('history', data=new_hist)

for fi, fname in enumerate(fnames):
    print "Opening:",fname, "(%d of %d)"%(fi+1,len(fnames))
    fh = h5py.File(fname, 'a')
    flags = n.zeros(fh['flags'].shape, dtype=bool)
    fh['flags'][:]=flags
    hist_str="RST FLAGS: reset all flags to False."
    print hist_str
    append_history(fh,hist_str)
    fh.flush()
    fh.close()

