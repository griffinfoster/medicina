#!/usr/bin/env python
"""
Script to generate a data file for Adrian Lui's redundant baseline calibration code
"""

import numpy, pylab, h5py, time, sys, math
import poxy

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] CONFIG_FILE')
    o.set_description(__doc__)
    o.add_option('-t', '--time', dest='time', default=None,
            help='Time range over which to average. I.e. average from t=0 to t=<time>. Default: Average over whole file')
    opts, args = o.parse_args(sys.argv[1:])
    if len(args)<2:
        print 'Please specify an antenna config and hdf5 file! \nExiting.'
        exit()
    else:
        hd5_fname = args[1]
        array_file = args[0]

# Load the array config file
array = poxy.ant_array.Array(array_file)

# Load the hdf5 data file and perform an average over the time axis (axis 0)
fh = h5py.File(hd5_fname,'r')
if opts.time == None:
    t_range = numpy.arange(len(fh['xeng_raw0']))
else:
    t_range = numpy.arange(int(opts.time))
d = numpy.average(fh['xeng_raw0'][t_range,:,:,0,:], axis=0) #All channels, all bl's, single pol
#d[:,1] = all channels, all bl's, real
#d[:,0] = all channels, all bl's, imag 

bl_order = fh['bl_order'][:]
n_ants = fh.attrs.get('n_ants')
bl_reorder = numpy.zeros(len(bl_order))
bl_index=0
for i in range(n_ants):
    for j in range(i,n_ants):
        for bl_n, bl in enumerate(bl_order):
            if (bl[0]==i) and (bl[1]==j):
                print bl_index
                bl_reorder[bl_index] = bl_n
                bl_index+=1

# Open the output file
f = open('red_bl_data.txt','w')

for chan in range(len(d)):
    print 'Writing output file: channel %d' %chan
    for bl_n in bl_reorder:
        bl = bl_order[bl_n]
        #print 'Writing baseline index %d: [%d,%d]' %(bl_n,bl[0],bl[1])
        # get antenna numbers
        ant_a = bl[0]
        ant_b = bl[1]
        # get antenna locations
        loc_a = array.loc(ant_a)
        loc_b = array.loc(ant_b)
        #get uv
        u = ant_b%4 - ant_a%4
        v = ant_b//4 - ant_a//4
        # get data
        re = d[chan,bl_n,1]
        im = d[chan,bl_n,0]

        if bl[0]!=bl[1]:
            # write line to file
            f.write('%d\t%d\t%d\t%d\t%f\t%f\n' %(u,v,ant_a+1,ant_b+1,re,im)) #index ants from 1

fh.close()
f.close()
exit()







