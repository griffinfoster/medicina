#! /usr/bin/env python
'''
'''

import numpy as n
import sys
import pylab
import poxy
import cPickle as pickle

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('gaincal_load.py [options] INST_CONFIG_FILE GAIN_CAL_FILE')
    p.set_description(__doc__)
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
            help='Print lots of lovely debug information')
    p.add_option('-c', '--closed_loop', dest='closed_loop',action='store_true', default=False,
            help='Use this flag to modify (by multiplication), rather than replace, the current calibration coefficient set')

    opts, args = p.parse_args(sys.argv[1:])

    if len(args)<2:
        print 'Please specify an instrument configuration and gain calibration file! \nExiting.'
        exit()

    print 'Loading Instrument config file (%s) and connecting...' %(args[0])
    feng=poxy.medInstrument.fEngine(args[0],program=False)
    feng.eq_init_phs(load_pickle=True)
    feng.eq_init_amp(load_pickle=True)
    fConf = feng.fConf
    n_ants = fConf.n_ants

    print 'Loading Gain calibration file: %s' %(args[1])
    f = open(args[1])
    g = 1./pickle.load(f) #g is an [nchans,nants] array
    f.close()

    # The correlator does not order antennas in the same way as the
    # F-engine, so remap them here...
    ant_remap = [0, 8,16,24,4,12,20,28,
                 1, 9,17,25,5,13,21,29,
                 2,10,18,26,6,14,22,30,
                 3,11,19,27,7,15,23,31]
    #print '!!!!!!!!!!!!!DEBUG!!!!!!!!!!!!!'
    #print 'NOT UPLOADING CORRECTIONS FOR ALL CHANNELS!'
    #ant_remap = [0,1,2,3,4,5,6,7]

    pylab.subplot(4,1,1)
    pylab.plot(n.abs(g[:,0]))
    pylab.subplot(4,1,2)
    pylab.plot(n.angle(g[:,0]))
    pylab.subplot(4,1,3)
    pylab.plot(n.abs(g[:,1]))
    pylab.subplot(4,1,4)
    pylab.plot(n.angle(g[:,1]))
    pylab.show()
    #for ant in range(fConf.n_ants_sp):
    for ant in range(8):
        amp_coeffs = n.array(n.abs(g[:,ant_remap[ant]]),dtype=float)
        phase_coeffs = n.array(g[:,ant_remap[ant]]/amp_coeffs,dtype=complex)
        #amp_coeffs = n.ones_like(amp_coeffs)
        feng.eq_phs.coeff['cal'].modify_coeffs(ant,0,phase_coeffs[::-1],closed_loop=opts.closed_loop, verbose=opts.verbose) #Reverse coeffs because medicina spectrum is inverted
        feng.eq_amp.coeff['cal'].modify_coeffs(ant,0,amp_coeffs[::-1],closed_loop=opts.closed_loop, verbose=opts.verbose) #Reverse coeffs because medicina spectrum is inverted
    print ' Writing phase coefficients...',
    feng.eq_write_all_phs(verbose=opts.verbose, use_base=True, use_bandpass=True, use_cal=True)
    feng.eq_phs.write_pkl()
    print 'done'
    print ' Writing amp coefficients...',
    feng.eq_write_all_amp(verbose=opts.verbose, use_base=True, use_bandpass=True, use_cal=True)
    feng.eq_amp.write_pkl()
    print 'done'

