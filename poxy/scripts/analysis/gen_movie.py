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

n_files = len(fnames)
for fi, fname in enumerate(fnames):
    print "Opening:",fname,"(%d of %d)" %(fi+1,n_files)
    fh = h5py.File(fname, 'r')
    t = fh.get('timestamp0')
    time_index=range(len(t))
    if fi==0:
        chan_index = convert_arg_range(opts.chan_index)
        if len(chan_index) != 1:
            print 'ERROR: Movies can only be made from single channels. Exiting'
            exit()
        # Can only use one vector as an index at a time
        dn = fh.get('seng_raw0')[time_index]
        dn = dn[:,chan_index]

        x_pixels = numpy.arange(dn.shape[2])
        
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
    fh.close()

#### Filenames
output_basename = '/media/95a5548c-ba5a-41e2-a63d-05503586ce0b/med_movies/'


time_slices = len(d)
x_range = numpy.arange(7)
y_range = numpy.arange(15)
for t in range(time_slices):
    print 'Generating image %d of %d' %(t+1,time_slices)
    for pn,pi in enumerate(pols):
        di = d[t,0,:,:,pn]
        if opts.mode.startswith('log'):
            di = numpy.array(di,dtype=float)
            di[di!=0] = 10*numpy.log10(di[di!=0])
        #Data massaging
        #di = numpy.roll(di,-1,axis=1)
        di = di**2
        pylab.figure(4*pn+t)
        pylab.pcolor(x_range,y_range,numpy.fft.fftshift(di)[0:15,1:]) #get rid of the pixels which are made of 2 halves
        #pylab.imshow(numpy.fft.fftshift(di,axes=[0]))
        #pylab.pcolor(numpy.fft.fftshift(di,axes=[0]))
        pylab.clim(8000**2,45000**2)
        pylab.colorbar()
        pylab.title('Channel %d. Pol %s. Time %d' %(chan_index[0], map_pol[pi],t))
        pylab.savefig(output_basename+'image%.4d.png'%t)
        pylab.close(4*pn+t)

#if not opts.share or opts.legend: pylab.legend()
#pylab.show()
