#! /usr/bin/env python

import sys
import h5py
import numpy as n
import pylab

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('bandpass_coeff_gen.py [options] <hdf5 data file>')
    p.set_description(__doc__)
    p.add_option('-a', '--average', dest='average',action='store_true', default=False, 
        help='Average antennas.')
    p.add_option('-n', '--n', dest='n', type='int', default=4, 
        help='polynomial fitting order. Default=4.')
    p.add_option('-c', '--chan_range', dest='chan_range', type='string', default='0_-1', 
        help='Channel range to fit. <start_chan>_<end_chan>')
    p.add_option('-r', '--rfi_threshold', dest='rfi_threshold', type='float', default=2.2, 
        help='Amplitude over which signal is clipped')

    opts, args = p.parse_args(sys.argv[1:])

    hdf5_file = args[0]

    [start_chan,end_chan] = map(int, opts.chan_range.split('_'))

    print 'Opening file %s' %hdf5_file
    fh = h5py.File(hdf5_file,'r')
    n_ants = fh.attrs.get('n_ants')
    n_chans= fh.attrs.get('n_chans')
    n_bls = fh.attrs.get('n_bls')
    eq = fh.get('EQ')
    print 'N_ants:', n_ants
    print 'N_chans:', n_chans
    
    n_coeffs = len(eq['eq_amp_coeff_0x'][-1])
    dec_factor = n_chans/n_coeffs
    old_bandpass_coeffs = n.array([n_ants,n_chans])
    eq_array_bandpass = n.zeros([n_ants,n_chans])
    bandpass_data = n.zeros([n_ants,n_chans])
    corr_data = fh['xeng_raw0'][0,:,:,0,1] #all ants, all channels, x-pol, real
    bl_order = fh.get('bl_order')
    for i in range(n_bls):
        if bl_order[i,0] == bl_order[i,1]:
            bandpass_data[bl_order[i,0],:] = corr_data[:,i]
    print 'Number of EQ coefficients: %d. Number of channels: %d.'%(n_coeffs,n_chans)
    print 'Decimation factor: %d' %dec_factor
    for ant in range(n_ants):
        for i in range(n_coeffs):
            eq_array_bandpass[ant,i*dec_factor:(i+1)*dec_factor] = eq['eq_amp_coeff_bandpass_%dx'%ant][-1][i]
    
    bandpass_data = n.sqrt(bandpass_data)
    bandpass_data = bandpass_data / eq_array_bandpass

    if opts.average:
        bandpass_data = bandpass_data.mean(axis=0)
        bandpass_data = bandpass_data.reshape(1,n_chans)
        n_ants=1

    #RFI clipping
    print "Clipping signal values over %f"%opts.rfi_threshold
    bandpass_data[bandpass_data>opts.rfi_threshold] = opts.rfi_threshold

    #Perform fit
    coeffs = n.zeros([n_ants,opts.n+1])
    fit = n.zeros([n_ants,n_chans])
    print 'Fitting for channels %d - %d with polynomial of order %d'%(start_chan, end_chan,opts.n)
    for an, ant in enumerate(bandpass_data):
        coeffs[an] = n.polyfit(n.arange(n_chans)[start_chan:end_chan], ant[start_chan:end_chan], opts.n)
        fit[an] = n.polyval(coeffs[an],n.arange(n_chans))
        print "Coefficients for Antenna %d:" %(an), coeffs[an]

    pylab.subplot(2,1,1)
    for an,ant_bp in enumerate(bandpass_data):
        pylab.semilogy(ant_bp)
        pylab.semilogy(fit[an])
        pylab.semilogy(ant/fit[an])
    pylab.subplot(2,1,2)
    for bp_coeff in eq_array_bandpass:
        pylab.semilogy(bp_coeff[bp_coeff!=0])


    pylab.show()



