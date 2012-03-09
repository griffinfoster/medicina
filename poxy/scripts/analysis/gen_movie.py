#!/usr/bin/env python
"""
General plotting tool to plot SPEAD based transform imager output
"""

import numpy, pylab, h5py, time, sys, math

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] CONFIG_FILE')
    o.set_description(__doc__)
    o.add_option('-c', '--chan', dest='chan_index', default='all',
        help='Select which channels to plot. Options are <ch_i>,...,<ch_j>, or a range <ch_i>_<ch_j>. Default=all')
    o.add_option('-m', '--mode', dest='mode', default='lin',
        help='Plotting mode: lin, log. Default=log')
    o.add_option('-p', '--pol', dest='pol', default='all',
        help='Select which polarization to plot (xx,yy,xy,yx,all). Default=all')
    o.add_option('-t', '--time', dest='time', type='string', default='all', help='Select which time sample to plot. Default=all')
    o.add_option('--legend', dest='legend', action='store_true',
        help='Show a legend for every plot.')
    o.add_option('--share', dest='share', action='store_true',
        help='Share plots in a single frame.')
    o.add_option('-d', '--decimate', dest='decimate', default=1, type='int',
        help='Decimation factor')
    o.add_option('-z', '--zeropad', dest='zeropad', default=0, type='int',
        help='Zeropadding factor when creating images')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        fnames = args

    dec_factor = opts.decimate
    z_factor = opts.zeropad

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

def gen_time_axis(timestamps,scale,offset):
    """ Return a list of real times from the timestamp vector"""
    # get the timestamps
    timestamps = numpy.array(timestamps, dtype=float)
    t = numpy.zeros(len(timestamps),dtype=numpy.float64)
    t = numpy.array(offset + timestamps/scale,dtype=numpy.float64) #UNIX times
    return map(time.ctime,t) # Times in UTC



n_files = len(fnames)
for fi, fname in enumerate(fnames):
    print "Opening:",fname,"(%d of %d)" %(fi+1,n_files)
    fh = h5py.File(fname, 'r')
    t = fh.get('timestamp0')
    time_index=range(0,len(t),dec_factor)
    if fi==0:
        chan_index = convert_arg_range(opts.chan_index)
        if len(chan_index) != 1:
            print 'ERROR: Movies can only be made from single channels. Exiting'
            exit()
        # Can only use one vector as an index at a time
        dn = fh.get('seng_raw0')[time_index]
        dn = dn[:,chan_index]
        timestamps = fh.get('timestamp0')[time_index]

        x_pixels = numpy.arange(dn.shape[2])

        time_scale_factor = float(fh.attrs.get('adc_clk')/2/fh.attrs.get('seng_acc_len'))
        time_offset = fh.attrs.get('sync_time')
        
        pixels = numpy.arange(dn.shape[3])
        
        n_stokes = fh.attrs.get('n_stokes')
        n_ants = fh.attrs.get('n_ants')
        pols = convert_pol(opts.pol)[0:n_stokes]
        n_pols = len(pols)
        d = dn
    
    else: 
        dn = fh.get('seng_raw0')[time_index]
        dn = dn[:,chan_index]
        d = numpy.concatenate((d,dn))
        timestamps = numpy.append(timestamps,fh.get('timestamp0')[time_index])
    fh.close()

#Generate real times from timestamps
real_times = gen_time_axis(timestamps, time_scale_factor, time_offset)

#### Filenames
output_basename = './med_movies/'


time_slices, chans, x, y, polarisations = d.shape
print "Number of time slices:", time_slices

#interpolate the image by fft & zero padding
if opts.zeropad != 0:
    d = numpy.array(d,dtype=complex)
    d_zp = numpy.zeros([time_slices, chans, opts.zeropad*(x-1), opts.zeropad*(y-1), polarisations], dtype=complex)
    d = numpy.fft.fftshift(numpy.fft.ifft2(d, axes=(2,3)),axes=(2,3))[:,:,1:,1:,:]
    d_zp[:,:,-(x-1):,-(y-1):,:] = d
    #d_zp=di
    d = numpy.abs(numpy.fft.fft2(d_zp,axes=(2,3)))


if opts.mode.startswith('log'):
    d = numpy.array(di,dtype=float)
    d[d!=0] = 10*numpy.log10(d[d!=0])

c_max = d.max()
c_min = d.min()

x_range = numpy.arange(d.shape[3]-1)
y_range = numpy.arange(d.shape[2]-1)
print "image has size: %d x %d" %(len(x_range),len(y_range))
for t in range(time_slices):
    print 'Generating image %d of %d' %(t+1,time_slices)
    for pn,pi in enumerate(pols):
        di = d[t,0,:,:,pn]
        pylab.figure(4*pn+t)
        pylab.pcolor(x_range,y_range,numpy.fft.fftshift(di)[0:-1,1:]) #get rid of the pixels which are made of 2 halves
        #pylab.pcolor(x_range,y_range,numpy.fft.fftshift(di))
        #pylab.imshow(numpy.fft.fftshift(di,axes=[0]))
        #pylab.pcolor(numpy.fft.fftshift(di,axes=[0]))
        pylab.clim(c_min,c_max)
        pylab.colorbar()
        pylab.title('Channel %d. Pol %s. %s' %(chan_index[0], map_pol[pi],real_times[t]))
        pylab.savefig(output_basename+'image%.4d.png'%t)
        pylab.close(4*pn+t)

#if not opts.share or opts.legend: pylab.legend()
#pylab.show()
