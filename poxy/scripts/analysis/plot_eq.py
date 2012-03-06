#!/usr/bin/env python
"""
General plotting tool to plot SPEAD based correlator output
"""

import numpy, pylab, h5py, time, sys, math
import poxy

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] CONFIG_FILE')
    o.set_description(__doc__)
    o.add_option('--share', dest='share', action='store_true', default=False,
        help='Share plots in a single frame.')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        fnames = args


pol_map = {'xx':0,'yy':1,'xy':2,'yx':3}
map_pol = ['xx','yy','xy','yx']

eq={}
for fi, fname in enumerate(fnames):
    print "Opening:",fname, "(%d of %d)"%(fi+1,len(fnames))
    fh = h5py.File(fname, 'r')
    if fi==0:
        n_ants = fh.attrs.get('n_ants')
        n_stokes = fh.attrs.get('n_stokes')
        for key in fh.get('EQ').keys(): eq[key] = numpy.array(fh.get('EQ')[key][:][-1])
    fh.flush()
    fh.close()

if n_stokes != 4:
   n_pol = 1
else:
   n_pol = 2

n_subplots=len(eq)-1 #ignore the eq_time
n_subplots_x = int(numpy.floor(n_subplots))
n_subplots_y = numpy.ceil(float(n_subplots)/n_subplots_x)

x_plot=0
y_plot=0
for pol in ['x','y'][0:n_pol]:
    for ant in range(n_ants):
        if not opts.share:
            x_plot = ant%n_subplots_x
            y_plot = ant//n_subplots_y
            pylab.subplot(n_subplots,n_subplots_x,n_subplots_y)
        pylab.plot(eq['eq_amp_coeff_%d%s'%(ant,pol)])

pylab.show()

