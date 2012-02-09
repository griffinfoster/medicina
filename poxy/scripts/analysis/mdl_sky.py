#!/usr/bin/env python
"""
Generate a model of the sky based on a time range, config file and source catalog
"""

import aipy as a, numpy as n, sys, os, optparse
import h5py as h5
import time

o = optparse.OptionParser()
o.set_usage('mdl_sky.py [options] *.h5')
o.set_description(__doc__)
a.scripting.add_standard_options(o, cal=True, src=True)
opts,args = o.parse_args(sys.argv[1:])

# Parse command-line options
filein_name = args[0]
fh = h5.File(filein_name,'r')
nchans = fh.attrs.get('n_chans')
# AIPY like frequencies in GHz
adc_clk = float(fh.attrs.get('adc_clk'))/1e9
bandwidth = float(fh.attrs.get('bandwidth'))/1e9
cfreq = float(fh.attrs.get('center_freq'))/1e9
sdf = bandwidth/nchans # start freq
sfreq = cfreq - (bandwidth/2)

print 'sdf: %.9f' %sdf
print 'sfreq: %.9f' %sfreq
print 'nchan: %d' %nchans

aa = a.cal.get_aa(opts.cal, sdf, sfreq, nchans)
srclist,cutoff,catalogs = a.scripting.parse_srcs(opts.src, opts.cat)
src = a.cal.get_catalog(opts.cal, srclist, cutoff, catalogs).values()[0]
fh.close()

# A pipe to use for generating phases
curtime = None
def mdl_phs(uv):
    global curtime
    print 'In the phs method'
    #data = n.zeros_like(uv['xeng_raw0'][:,:,:,:,1] + 1j*uv['xeng_raw0'][:,:,:,:,0]) # uv['xengine_raw0'] is a [time,chans,baseline,pol,r,i] array
    data = n.ones(uv['xeng_raw0'][:,:,:,:,0].shape) + 1j*n.zeros(uv['xeng_raw0'][:,:,:,:,1].shape)
    print 'Allocated array'
    bl_order = uv['bl_order'][:]
    times = uv['timestamp0'][:]
    n_stokes = uv.attrs['n_stokes']
    n_times=len(times)
    for t_index, t in enumerate(times):
        t_unix = t
        gmt = time.gmtime(t_unix)
        print 'Processing time slice %d of %d, %.2d/%.2d/%.4d %.2d:%.2d:%.2d UTC' %(t_index+1,n_times,gmt.tm_mday, gmt.tm_mon, gmt.tm_year, gmt.tm_hour, gmt.tm_min, gmt.tm_sec)
        if curtime != t_unix:
            curtime = t_unix
            aa.set_jultime(a.ephem.julian_date(gmt[0:6]))
            if not src is None and not type(src) == str: src.compute(aa)
        for bl_index, bl in enumerate(bl_order):
            i,j = bl
            for pol_index in range(n_stokes):
                if i == j: pass
                try:
                    data[t_index,:,bl_index,pol_index] = 1/aa.gen_phs(src,i,j)
                except(a.phs.PointingError):
                    data[t_index,:,bl_index,pol_index] *= 0 #Catch pointing errors e.g. source below horizon
                    print 'Pointing Error! data set to zero'

    
    data.real[n.isnan(data.real)]=0
    data.imag[n.isnan(data.imag)]=0
    uv['xeng_raw0'][:,:,:,:,1] = data.real
    uv['xeng_raw0'][:,:,:,:,0] = data.imag
    return data

# Process data
for filename in args:
    mdlfile = filename + '.mdl'
    print 'Copying', filename,'->',mdlfile
    if os.path.exists(mdlfile):
        print 'File exists: skipping'
        continue
    os.system('cp -p %s %s' %(filename,mdlfile)) #Copy the hd5 file
    # Open the output file for editing
    print 'Opening %s as an hdf5 data file.' %mdlfile
    mdlh = h5.File(mdlfile, 'r+')
    mdl_phs(mdlh)
    mdlh.close()

