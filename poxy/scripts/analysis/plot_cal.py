#! /usr/bin/env python

import numpy as n
import pylab
import sys
import pickle as pickle

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

from optparse import OptionParser

p = OptionParser()
p.set_usage('plot_cal.py [options] Calibration_pickle_files')
p.set_description(__doc__)
p.add_option('-c', '--chan', dest='chan', type='string', default='0_1023',
    help='Chan range to plot')
p.add_option('-a', '--ants', dest='ants', type='string', default='0_31',
    help='Antennas to plot')

opts, args = p.parse_args(sys.argv[1:])

gain_files = args

chan_range = convert_arg_range(opts.chan)
ant_range = convert_arg_range(opts.ants)

cals = []
calnames = []
n_files = len(gain_files)
for f in gain_files:
    print "Reading pickle file %s" %f
    calnames.append(f.split('/')[-1])
    fh = open(f,'r')
    pk = pickle.load(fh)
    g = pk['cal']
    eq = pk['eq_master'][:,:]
    #cals.append(g/n.transpose(eq))
    cals.append(g)
    fh.close()

n_chans,n_ants = cals[0].shape

##renormalise the coefficients (the EQ isn't normalised)
normed_cal = n.zeros([n_files,n_chans,n_ants], dtype=complex)
for i in range(n_files):
    norm_factor = cals[i][:,0]
    for ant in range(n_ants):
        normed_cal[i,:,ant] = cals[i][:,ant]/cals[i][:,0]

ants_to_plot = len(ant_range)
x_subplots = float(ants_to_plot) / n.floor(n.sqrt(ants_to_plot))
y_subplots = n.ceil(float(ants_to_plot)/x_subplots)


pylab.figure(0)
for an,ant in enumerate(ant_range):
    pylab.subplot(x_subplots,y_subplots,an+1)
    pylab.title("Ant %d, amp"%ant)
    for cn,cal in enumerate(normed_cal):
        pylab.plot(n.abs(cal[chan_range,ant]),label=calnames[cn])
pylab.legend()
    
pylab.figure(1)
pylab.title('phase')
for an,ant in enumerate(ant_range):
    pylab.subplot(x_subplots,y_subplots,an+1)
    pylab.title("Ant %d, phs"%ant)
    for cn,cal in enumerate(normed_cal):
        pylab.plot(n.angle(cal[chan_range,ant]), label=calnames[cn])
pylab.legend()

pylab.show()
     

