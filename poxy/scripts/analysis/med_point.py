#! /usr/bin/env python
'''
A script to generate the pointing phases for the medicina BEST-2 Array.
Either enter a target declination, or provide a source config file describing a target
'''

import numpy as n
import sys
import ephem
import pylab
import poxy

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('med_point.py [options] ARRAY_CONFIG_FILE INST_CONFIG_FILE [SOURCE_OBS_FILE]')
    p.set_description(__doc__)
    p.add_option('-d', '--dec', type='string', dest='dec', default='zenith',
            help='The declination at which the telescope is pointed <XX:XX:XX.X> or \'zenith\' Default:zenith')
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
            help='Print lots of lovely debug information')

    opts, args = p.parse_args(sys.argv[1:])

    if len(args)<2:
        print 'Please specify an antenna array and instrument configuration file! \nExiting.'
        exit()
    
    print 'Loading configuration file...',
    array = poxy.ant_array.Array(args[0])
    print 'done'
    
    if len(args)==3:
        dec_from_src = True
        print 'Loading source observation file...',
        src=poxy.xmlParser.xmlObject(args[2]).xmlobj
        print 'done'
    else:
        dec_from_src = False

    feng=poxy.medInstrument.fEngine(args[1],program=False)
    feng.eq_init_phs(load_pickle=True)
    fConf = feng.fConf

    # For the purposes of calculating zenith direction, a
    # assume all antennas have the same lat as the reference
    array_lat, array_lon = array.get_ref_loc()

    if dec_from_src:
        dec = src.dec
    else:
        if opts.dec.startswith('zen'):
            dec = array_lat
        else:
            dec = float(ephem.degrees(opts.dec))*180./n.pi
    print 'Phasing to dec %f' %dec
    dec = dec*(n.pi/180.) # convert to radians


    path_diff_by_chan = n.zeros(array.n_ants) #Path delays in m
    path_diff_by_ant= n.zeros(array.n_ants) #Path delays in m
    zenith = array_lat*n.pi/180. #in radians
    point_dir = zenith-dec #pointing direction relative to zenith with 0 = zenith
    if opts.verbose:
        print 'zenith',zenith
        print 'pointing dec', dec
        print 'pointing direction (degrees):', point_dir*180./n.pi
    trig_factor = n.sin(point_dir)
    if opts.verbose:
        print 'trig factor', trig_factor
    ant_pos_unit = 3e8/408e6 #Wavelengths at 408MHz

    for ant in range(array.n_ants):
        x,y,z = array.loc(ant)
        path_diff_by_chan[array.get_input_num(ant)['x']] = array.loc(ant)[1]*ant_pos_unit*trig_factor
        if opts.verbose:
            print 'antenna:',ant,'input',array.get_input_num(ant)['x'],'path diff', array.loc(ant)[1]
        path_diff_by_ant[ant] = array.loc(ant)[1]*ant_pos_unit*trig_factor

    obs_freq = fConf.obs_freq
    n_chans = fConf.n_chan
    bw = float(fConf.adc.clk)/2
    start_f = obs_freq - (bw/2)
    df = bw/n_chans

    freqs = n.arange(start_f,start_f+bw,df)
    wavelengths = 3e8/freqs
    for ant in range(array.n_ants):
        phases = -2*n.pi*path_diff_by_chan[ant]/wavelengths #negative, since we want to compensate for the path differences
        coeffs = n.cos(phases)+n.sin(phases)*1j
        if opts.verbose:
            print coeffs
        feng.eq_phs.calibrate_coeffs(ant,0,coeffs[::-1],closed_loop=False) #Reverse coeffs because medicina spectrum is inverted
    print ' Writing phase coefficients...',
    feng.eq_write_phs(verbose=opts.verbose)
    print 'done'

if opts.verbose:
    print path_diff_by_chan
pylab.pcolor(path_diff_by_ant.reshape(8,4))
pylab.colorbar()
pylab.show()
