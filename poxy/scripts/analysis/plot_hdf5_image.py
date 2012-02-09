#!/usr/bin/env python
"""
General plotting tool to plot SPEAD based transform imager output
"""

import numpy, h5py, time, sys, math
import ephem
from matplotlib import rc
rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']})
## for Palatino and other serif fonts use:
#rc('font',**{'family':'serif','serif':['Palatino']})
rc('text', usetex=True)
import pylab
import matplotlib.cm as cm

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] CONFIG_FILE')
    o.set_description(__doc__)
    o.add_option('-c', '--chan', dest='chan_index', default='all',
        help='Select which channels to plot. Options are <ch_i>,...,<ch_j>, or a range <ch_i>_<ch_j>. Default=all')
    o.add_option('-x', '--xpixel', dest='xpixel', type='string', default='all',
        help='Select which x-pixels to plot. Options are <pixel0>,...,<pixeln>, or a range <pixel0>_<pixeln>, or all. Default=all')
    o.add_option('-y', '--ypixel', dest='ypixel', type='string', default='all',
        help='Select which y-pixels to plot. Options are <pixel0>,...,<pixeln>, or a range <pixel0>_<pixeln>, or all. Default=all')
    o.add_option('-m', '--mode', dest='mode', default='lin',
        help='Plotting mode: lin, log. Default=log')
    o.add_option('-p', '--pol', dest='pol', default='all',
        help='Select which polarization to plot (xx,yy,xy,yx,all). Default=all')
    o.add_option('-t', '--time', dest='time', type='string', default='all', help='Select which time sample to plot. Default=all')
    o.add_option('-s', '--scale', dest='time_scale', type='string', default='time', help='Select unit of time axis. time=hours since reference. ha=hour angle')
    o.add_option('--legend', dest='legend', action='store_true',
        help='Show a legend for every plot.')
    o.add_option('--share', dest='share', action='store_true',
        help='Share plots in a single frame.')
    o.add_option('--title', dest='title', default=None,
        help='Use the --title flag to manually enter text from the command line for graph titles.')
    o.add_option('-n', '--normalise', dest='normalise', action='store_true', default=False,
        help='Use the --normalise flag to scale 0db to the maximum value in the plot.')
    o.add_option('--ha_fudge', dest='ha_fudge', type='float', default=0.0,
        help='Fudge factor to shift the time axis (for the case where incorrect calibration has been used)')
    o.add_option('-o', '--offset', dest='offset', type='int', default=0,
        help='Multiplicative factor to plot multiple lines on the same axis with an offset')
    o.add_option('--monotone', dest='monotone', action='store_true', default=False,
        help='Plot all lines in black')
    o.add_option('-z', '--zeropad', dest='zeropad', type='int', default=0,
        help='Increase number of pixels by a given factor (in both dimensions)')
    o.add_option('--transit', dest='transit', action='store_true', default=False,
        help='Use only the time sample closest to ha=0. Naively coded -- will still load ALL the data!')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        fnames = args

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

pol_map = {'xx':0,'yy':1,'xy':2,'yx':3}
map_pol = ['xx','yy','xy','yx']
def convert_pol(arg):
    """Parse polarization options"""
    if arg == 'all': return [pol_map['xx'], pol_map['yy'], pol_map['xy'], pol_map['yx']]
    else:
        arg = arg.split(',')
        rv = []
        for pi in arg: rv.append(pol_map[pi])
        return rv

def gen_obs(lat=None,long=None,el=0,telescope=None):
    obs = ephem.Observer()
    if telescope == 'Medicina':
        obs.lat = '44:31:24.88'
        obs.long = '11:38:45.56'
    elif ((lat is not None) and (long is not None)):
        obs.lat = lat
        obs.long = long
    else:
        raise ValueError("Unknown observatory: %s" %telescope)
    return obs

def gen_time_axis(timestamps,scale,offset):
    """ Return a list of real times from the timestamp vector"""
    # get the timestamps
    timestamps = numpy.array(timestamps, dtype=float)
    t = numpy.zeros(len(timestamps),dtype=numpy.float64)
    t = numpy.array(offset + timestamps/scale,dtype=numpy.float64) #UNIX times
    t_range = t[-1] - t[0]
    gmt_ref = time.gmtime(t[0]) # Start time in UTC
    jd_ref = ephem.julian_date(gmt_ref[0:6])

    if t_range < 300:
        scale = 'Seconds since %.4d/%.2d/%.2d %.2d:%.2d:%.2d UTC' %(gmt_ref[0:6])
        t = (t-t[0])
    elif t_range < 60*60*3:
        scale = 'Minutes since %.2d/%.2d/%.2d %.2d:%.2d:%.2d UTC' %(gmt_ref[0:6])
        t = (t-t[0])/60
    else:
        scale = 'Hours since %.2d/%.2d/%.2d %.2d:%.2d:%.2d UTC' %(gmt_ref[0:6])
        t = (t-t[0])/60/60
    return {'times':t, 'scale':scale, 'ref':t[0], 'gmtref':gmt_ref, 'jd_ref':jd_ref, 'unit':''}

def gen_ha_axis(timestamps,scale,offset,RA):
    """ Return a list of real times from the timestamp vector"""
    # get the timestamps
    timestamps = numpy.array(timestamps, dtype=float)
    t = numpy.zeros(len(timestamps),dtype=numpy.float64)
    t = numpy.array(offset + timestamps/scale,dtype=numpy.float64) #UNIX times
    gmt_ref = time.gmtime(t[0]) # Start time in UTC
    jd_ref = ephem.julian_date(gmt_ref[0:6])
    ha = numpy.zeros_like(t)
    for i,ti in enumerate(t):
        obs.date = ephem.Date(time.gmtime(ti)[0:6])
        #print "time is", obs.date
        ha[i] = obs.sidereal_time() - RA
        #print obs.sidereal_time(), RA, obs.sidereal_time()-RA
    # Unwrap the phases, otherwise weird things can happen
    # When the lst crosses midnight
    ha = numpy.unwrap(ha)
    ha = numpy.rad2deg(ha)
    ha = ha + opts.ha_fudge
    return {'times':ha, 'scale':"Hour Angle", 'ref':RA, 'gmtref':gmt_ref, 'jd_ref':jd_ref, 'unit':'[degrees]'}

n_files = len(fnames)
for fi, fname in enumerate(fnames):
    print "Opening:",fname
    fh = h5py.File(fname, 'r')
    if opts.time is 'all':
        time_index=range(fh['seng_raw0'].shape[0])
    else: time_index = convert_arg_range(opts.time)
    if fi==0:
        # Generate the ephem Observer from the location of the observatory in the file
        print 'Telescope: %s' %fh.attrs.get('telescope')
        print 'Source: %s' %fh.attrs.get('source')
        obs = gen_obs(telescope=fh.attrs.get('telescope'))
        if opts.chan_index == 'all': chan_index = range(0,fh.attrs.get('n_chans'))
        else: chan_index = convert_arg_range(opts.chan_index)
        # Can only use one vector as an index at a time
        dn = fh.get('seng_raw0')[time_index]
        dn = dn[:,chan_index]

        # Get time indices
        t = fh['timestamp0'][time_index]

        if opts.xpixel == 'all': x_pixels = numpy.arange(dn.shape[2])
        else: x_pixels = convert_arg_range(opts.xpixel)
        
        if opts.ypixel == 'all': y_pixels = numpy.arange(dn.shape[3])
        else: y_pixels = convert_arg_range(opts.ypixel)
        
        n_stokes = fh.attrs.get('n_stokes')
        if n_stokes == 1:
            is_single_pol = True
        n_ants = fh.attrs.get('n_ants')
        pols = convert_pol(opts.pol)[0:n_stokes]
        n_pols = len(pols)
        d = dn
    
    else: 
        dn = fh.get('seng_raw0')[time_index]
        dn = dn[:,chan_index]
        d = numpy.concatenate((d,dn))
        t = numpy.append(t,fh['timestamp0'][time_index])
    if fi==n_files-1:
        #Generate proper times
        scale_factor = float(fh.attrs.get('adc_clk')/2/fh.attrs.get('seng_acc_len'))
        if opts.time_scale == 'time':
            t = gen_time_axis(t,scale_factor,fh.attrs.get('sync_time'))
        else:
            t = gen_ha_axis(t,scale_factor,fh.attrs.get('sync_time'),ephem.hours('23:23:26.0'))
    fh.close()


plot_waterfall = ((len(time_index))!=1)&(len(chan_index)!=1)
plot_image = ((len(chan_index)==1) & ((len(time_index)==1) or opts.transit))
plot_spectrum = ((len(chan_index)!=1)& ((len(time_index)==1) or opts.transit))
plot_transit = ((len(chan_index)==1)&(len(time_index)!=1))

#Recast the data as float, to prevent any weirdness later on
d = numpy.array(d, dtype=float)

#If reqd -- grab the closest data point to transit
if opts.transit:
    print 'Finding closest time sample to transit'
    if opts.time_scale != 'ha':
        raise ValueError('time scale is not "ha", but attempting to find transit at t=0. Run again with -s ha option')
    transit_idx = (numpy.abs(t['times'][1:])).argmin() + 1
    print 'Closest time index is %d' %(transit_idx)
    print 'Closest time is ha = %f degrees' %(t['times'][transit_idx])
    d = d[transit_idx:transit_idx+1,:,:,:,:]

if opts.normalise:
    print 'Normalising maximum value to 0dB'
    d /= numpy.max(d)
    y_axis_ref = ''
else:
    y_axis_ref = '(Arbitrary Reference)'

if plot_image:
    for pn,pi in enumerate(pols):
        di = d[0,0,:,:,pn]
        #interpolate the image by fft & zero padding
        if opts.zeropad != 0:
            x,y = di.shape
            di = numpy.array(di,dtype=complex)
            d_zp = numpy.zeros([opts.zeropad*(x-1), opts.zeropad*(y-1)], dtype=complex)
            di = numpy.fft.fftshift(numpy.fft.ifft2(di))[1:,1:]
            d_zp[-(x-1):,-(y-1):] = di
            #d_zp=di
            di = numpy.abs(numpy.fft.fft2(d_zp))
            if opts.normalise:
                di /= numpy.max(di) #renormalise since the interpolated values may be greater than the data points

        if opts.mode.startswith('log'):
            di = numpy.array(di,dtype=float)
            di[di!=0] = 10*numpy.log10(di[di!=0])
            
        pylab.figure(pn)
        pylab.pcolor(numpy.fft.fftshift(di))
        pylab.xlim(0,di.shape[1])
        pylab.ylim(0,di.shape[0])
        #pylab.pcolor(numpy.fft.fftshift(di,axes=[1]))
        pylab.colorbar()
        pylab.title('Channel %d. Pol %s' %(chan_index[0], map_pol[pi]))
else:
    n_pixels = len(pols)*len(y_pixels)*len(x_pixels)
    for yn, y in enumerate(y_pixels):
        for xn, x in enumerate(x_pixels):
            for pn, pi in enumerate(pols):
                pixel_n = (pn*len(y_pixels)*len(x_pixels))+(yn*len(x_pixels))+xn
                pylab.figure(pn)
                if not opts.share:
                    pylab.subplot(len(y_pixels), len(x_pixels), len(x_pixels)*yn+xn+1)
                    dmin,dmax = None,None
                di = d[:,:,x,y,pi]
                ##channel selection
                #di = di[:,chan_index]
                #if opts.mode.startswith('lin'):
                #    di = numpy.absolute(di)
                if opts.mode.startswith('log'):
                    di = 10*numpy.log10(di)
                    ylabel = 'Power %s [dB]' %y_axis_ref
                    y_unit = 'dB'
                else:
                    ylabel = 'Power (linear) %s' %y_axis_ref
                    y_unit = ''

                offset = opts.offset*(len(x_pixels)*yn + xn)
                di = di + offset
                
                if opts.offset == 0:
                    if is_single_pol:
                        label = 'pixel (%d,%d)' %(x,y)
                    else:
                        label = 'pixel (%d,%d) %s' %(x,y,map_pol[pi])
                else:
                    if is_single_pol:
                        label = 'pixel (%d,%d) (Offset = %d %s)' %(x,y,offset,y_unit)
                    else:
                        label = 'pixel (%d,%d) %s (Offset = %d %s)' %(x,y,map_pol[pi],offset,y_unit)

                if not opts.share:
                    if di.max()>dmax: dmax=di.max()
                    if di.min()<dmin: dmin=di.max()
                if plot_waterfall:
                    pylab.imshow(di, label=label)
                elif plot_transit:
                    #pylab.title('Beam Power at %f MHz' %(chan2freq(opts.chan)))
                    if opts.monotone:
                        pylab.plot(t['times'],di,'k',label=label) #plot in black
                    else:
                        pylab.plot(t['times'],di,color=cm.jet(pixel_n/float(n_pixels),1),label=label)
                    pylab.xlabel(t['scale']+' %s'%t['unit'])
                    pylab.ylabel(ylabel)
                else:
                    pylab.plot(di[0],label=label)
                if not opts.share and opts.legend:
                    pylab.legend()
    
            if not opts.share:
                if not plot_waterfall:
                    pylab.ylim(dmin,dmax)
                #pylab.title('pixel (%d,%d) %s' %(x,y,map_pol[pi]))

if opts.share and opts.legend: pylab.legend()
if opts.title is not None: pylab.title(opts.title)
pylab.show()
