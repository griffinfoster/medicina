#!/usr/bin/python
"""
Rotate zenith UV data to a particular source.  Can specify 'zen' to phase data
to zenith, or nothing at all to just remove delay/offset phase components.
"""

import aipy as a, numpy as n, sys, os, optparse
import h5py as h5
import time

o = optparse.OptionParser()
o.set_usage('phs2src.py [options] *.uv')
o.set_description(__doc__)
a.scripting.add_standard_options(o, cal=True, src=True)
o.add_option('--setphs', dest='setphs', action='store_true',
    help='Instead of rotating phase, assign a phase corresponding to the specified source.')
o.add_option('-t', '--timescale', dest='scale_timestamp', default=False, action='store_true',
    help='Treat the values in the timestamp array as MCNTs from a correlator, and scale them appropriately')
opts,args = o.parse_args(sys.argv[1:])

# Parse command-line options
filein_name = args[0]
fh = h5.File(filein_name,'r')
nchans = fh.attrs.get('n_chans')
# AIPY like frequencies in GHz
adc_clk = float(fh.attrs.get('adc_clk'))/1e9
bandwidth = float(fh.attrs.get('bandwidth'))/1e9
#cfreq = float(fh.attrs.get('center_freq'))/1e9
print 'USING HARD CODED CENTER FREQ -- 408MHz'
cfreq = 0.408
sdf = bandwidth/nchans # start freq
sfreq = cfreq - (bandwidth/2)

print 'sdf: %.9f' %sdf
print 'sfreq: %.9f' %sfreq
print 'nchan: %d' %nchans

start_time = fh.attrs.get('sync_time') #Unix start time corresponding to MCNT=0
mcnt_scale_factor = fh.attrs.get('scale_factor_timestamp')

aa = a.cal.get_aa(opts.cal, sdf, sfreq, nchans)
if not opts.src is None:
    if not opts.src.startswith('zen'):
        srclist,cutoff,catalogs = a.scripting.parse_srcs(opts.src, opts.cat)
        src = a.cal.get_catalog(opts.cal, srclist, cutoff, catalogs).values()[0]
    else: src = 'z'
else: src = None
fh.close()

# A pipe to use for phasing to a source
curtime = None
def phs(uv):
    global curtime
    print 'Copying data to memory'
    data = n.array(uv['xeng_raw0'][:,:,:,:,1] + 1j*uv['xeng_raw0'][:,:,:,:,0], dtype=complex) # uv['xengine_raw0'] is a [time,chans,baseline,pol,r/i] array
    bl_order = uv['bl_order'][:]
    times = uv['timestamp0'][:]
    n_stokes = uv.attrs['n_stokes']
    n_times=len(times)
    print 'Beginning processing'
    for t_index, t in enumerate(times):
        if opts.scale_timestamp:
            t_unix = start_time + (t/mcnt_scale_factor)
        else:
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
                    if opts.setphs: data[t_index,:,bl_index,:] = aa.unphs2src(n.abs(data[t_index,:,bl_index,:]), src, i, j)
                    elif src is None: data[t_index,:,bl_index,:] *= n.exp(-1j*n.pi*aa.get_phs_offset(i,j))
                    else: data[t_index,:,bl_index,pol_index] = aa.phs2src(data[t_index,:,bl_index,pol_index], src, i, j)
                except(a.phs.PointingError):
                    data[t_index,:,bl_index,pol_index] *= 0 #Catch pointing errors e.g. source below horizon
                    print 'Pointing Error! data set to zero'

    
    data.real[n.isnan(data.real)]=0
    data.imag[n.isnan(data.imag)]=0
    print 'Writing phased data to file'
    uv['xeng_raw0'][:,:,:,:,1] = data.real
    uv['xeng_raw0'][:,:,:,:,0] = data.imag
    return data

# Process data
for filename in args:
    if not opts.src is None: uvofile = filename + '.' + opts.src
    else: uvofile = filename + 'P'
    print 'Copying', filename,'->',uvofile
    if os.path.exists(uvofile):
        print 'File exists: skipping'
        continue
    os.system('cp -p %s %s' %(filename,uvofile)) #Copy the hd5 file
    # Open the output file for editing
    print 'Opening %s as an hdf5 data file.' %uvofile
    uvo = h5.File(uvofile, 'r+')
    #print phs(uvo)
    phs(uvo)
    print 'Closing output file'
    uvo.close()
    print 'done'

