#!/usr/bin/env python

import numpy as n
import math, sys, os, h5py
import cPickle as pickle
import scipy.io

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
    o.add_option('-t', '--time', dest='time', default=0,
        help='Select which integration to write to the output file based on the time index, Default:0')
    o.add_option('-c', '--chan', dest='chan', default='all',
        help='Select which channel to write to the output file. Can be a signle channel, a range chi_chj or all, Default:all')
    o.add_option('-o', '--ouput', dest='output', default='mat',
        help='Select the output format for the correlation matrix: MAT, Pickle. Default:mat')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        h5fns = args

def convert_arg_range(arg):
    """Split apart command-line lists/ranges into a list of numbers."""
    arg = arg.split(',')
    init = [map(int, option.split('_')) for option in arg]
    rv = []
    for i in init:
        if len(i) == 1:
            rv.append(i[0])
        elif len(i) == 2:
            rv.extend(range(i[0],i[1]+1))
    return rv

# Process data
for fni in args:
    print 'Opening:',fni
    fhi = h5py.File(fni, 'r')

    time_index=int(opts.time)
    if opts.chan.startswith('all'):
        chan_index = range(fhi.attrs['n_chans'])
    else: chan_index=convert_arg_range(opts.chan)

    xeng_intp=fhi['xeng_raw0']
    xeng_int = xeng_intp.value[time_index,chan_index]
    
    nants=fhi.attrs['n_ants']
    #correlation matrix is nants x nants x nchans x real/imag
    cm=n.zeros((len(chan_index),nants,nants,2))
    for bl,ij in enumerate(fhi['bl_order'].value):
        cm[:,ij[0],ij[1]]=xeng_int[:,bl,0]
    
    unix_time=fhi['timestamp0'].value[time_index]
    unix_time=int(unix_time)
    fno="cm_%i"%(unix_time)
    if opts.output.startswith('p'):
        fno=fno+".pkl"
        pklfh = open(fno, 'wb')
        print "Writing Correlation Matrix to Pickles file:",fno
        pickle.dump(cm, pklfh)
    elif opts.output.startswith('m'):
        fno=fno+".mat"
        print "Writing Correlation Matrix to MAT file:",fno
        scipy.io.savemat(fno,{'cm':cm},appendmat=False)

    fhi.close()
