#! /usr/bin/env python
"""
Automatically set the Amplitude equalisation rams in the Fengines to
equalise power across the observational band, and across multiple input signals.
Automatically scale signals before quantisation to meet a target variance.
"""
import time, sys,struct,logging, os
from poxy import katcp_wrapper, medInstrument,log_handlers, bitOperations, plot_tools
import numpy as np
import pylab, math

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        im.disconnect_all()
    except: pass
    raise
    exit()

def exit_clean():
    try:
        im.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_plot_spectra.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-s', '--sigma', dest='sigma', type='float', default=1.0, 
        help='Target bit sigma. Default is 1 bit. Only relevent for quantisation config')
    p.add_option('-c', '--clip', dest='clip', action='store_true', default=False, 
        help='Zero out bins with persistent RFI -- not yet implemented')
    p.add_option('-a', '--ant', dest='ant', action='store_true', default=False, 
        help='Calibrate each antenna uniquely')
    p.add_option('-d', '--dc', dest='dc',action='store_true', default=False, 
        help='Zero out DC bin')
    p.add_option('-N', '--N', dest='N', type='int', default=4, 
        help='Number of snaps of each antenna to perform before calculating statistics. Default: 4')
    p.add_option('-b', '--bandpass', dest='bandpass', default=None, 
        help='Use this flag, along with an hdf5 correlation file, to flatten the bandpass of each antenna based on autocorrelations')
    p.add_option('-q', '--quant_config', dest='quant_config', action='store_true', default=False, 
        help='Perform automatic configuration of pre-quantize scaling. Scaling is constant across band, but can be antenna-dependent using -a flag')
    p.add_option('-r', '--chan_range', dest='chan_range', default='0_-1', 
        help='Use this flag to limit calculation and uploading of coefficients in the channel range <start_chan>_<end_chan>. Default: 0_-1 (use all)')
    p.add_option('-t', '--tolerance', dest='tolerance', type='float', default=0.02, 
        help='Fractional error allowed in the EQ. Default: 0.02')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

try:
    print ' Connecting...',
    im = medInstrument.fEngine(args[0],lh,program=False)
    print 'done'
    start_t = time.time()

    Nchans = im.fConf.n_chan
    Nants = im.fConf.n_ants_sp
    Npols = im.fConf.pols_per_ant
    

    # Initialise Amp EQ brams
    print ''' Getting Current Amplitude Equalization...'''
    im.eq_init_amp(load_pickle=True)
    #We can now access coefficients via im.eq_amp.coeff['master'][n_ant,n_pol(x:0,y:1),nchan]

    # Set up snap blocks
    print ''' Initialising Snap blocks...'''
    sync_index = 1 #Defines the snap mux input representing amp data
    #sync_index = 0 #Defines the snap mux input representing fft data
    x_ss = 'x_snap'
    y_ss = 'y_snap'
    ctrl_reg = 'snap_ctrl'
    snap_sel_ss = 'snap_sel_reg'
    sync_sel_ss = 'sync_sel_reg'

    snap_x = plot_tools.Spectras18(im.fpgas, ram_path=x_ss+'_snap_bram', ctrl_path=ctrl_reg,
                                   addr_path=x_ss+'_snap_addr', input_sel=x_ss+'_'+snap_sel_ss,
                                   sync_sel=x_ss+'_'+sync_sel_ss,sync_index=sync_index, n_ants=Nants,
                                   n_chans=Nchans, quiet=True)
    snap_y = plot_tools.Spectras18(im.fpgas, ram_path=y_ss+'_snap_bram', ctrl_path=ctrl_reg,
                                   addr_path=y_ss+'_snap_addr', input_sel=y_ss+'_'+snap_sel_ss,
                                   sync_sel=y_ss+'_'+sync_sel_ss,sync_index=sync_index, n_ants=Nants,
                                   n_chans=Nchans,quiet=True)
    
    if opts.dc:
        #zero DC bin
        print ' Zero-ing DC bins...',
        im.eq_amp.coeff['base'].coeff[:,:,0]=0 #Set bin zero of all ants & all pols to zero
        print 'done.'
        print ' Writing coefficients...',
        im.eq_write_all_amp(use_base=True, use_bandpass=True, use_cal=True)
        print 'done.'
        print ' Updating pickle file...',
        im.eq_amp.write_pkl()
        print 'done.'

    N = int(opts.N)

    #spec = np.zeros([N,Nants,2,Nchans])
    #print ''' Grabbing Data...'''
    #for n in range(N):
    #    print '   Snap %d of %d' %(n+1,N)
    #    spec[n,:,0,:] = np.abs(snap_x.get_spectras()[:,:,0,:].reshape(Nants,Nchans))
    #    #power_spec_x = spec_x.real**2 + spec_x.imag**2
    #    #power_spec_y = spec_y.real**2 + spec_y.imag**2

    #histo, bin_edges = np.histogram(spec,bins=64)
    #bin_centers = bin_edges[0:-1] + ((bin_edges[1]-bin_edges[0])/2)
    #pylab.plot(bin_centers,histo)
    #pylab.show()

    #Parse channel range option
    start_chan, stop_chan = map(int,opts.chan_range.split('_'))
    chan_range = range(Nchans)[start_chan:stop_chan]
    Nchan_range = len(chan_range)

    spec = np.zeros([N,Nants,Npols,Nchan_range], dtype=complex)
    if opts.quant_config:
            if opts.ant:
                ants_left = range(Nants)
                pols_left = [range(im.fConf.pols_per_ant) for i in range(Nants)]
                while len(ants_left) != 0:
                    print '''\n Grabbing Data...'''
                    for n in range(N):
                        print '   Snap %d of %d' %(n+1,N)
                        spec[n,:,0,:] = snap_x.get_spectras()[:,:,0,chan_range].reshape(Nants,Nchan_range)
                        if im.fConf.pols_per_ant == 2:
                            spec[n,:,1,:] = snap_y.get_spectras()[:,:,0,chan_range].reshape(Nants,Nchan_range)
                    for ant in range(Nants):
                        for pol in pols_left[ant]:
                            print '\n ANTENNA %d' %(ant)
                            ant_n=ant
                            pol_n=pol
                            print ' ANTENNA %d, POL %s' %(ant_n, ['x','y'][pol_n])
                            mean_power = np.mean(spec[:,ant,pol,:].real**2 + spec[:,ant,pol,:].imag**2) #Take power of antenna of interest. Average over samples and channels
                            var = (np.var(spec[:,ant,pol,:].real) + np.var(spec[:,ant,pol,:].imag))/2 #Take variance of antenna of interest

                            # Scale for 16_12 binary // This makes one LSB = 1 after we cast to 4_3
                            mean_power = mean_power/((2**12)**2)
                            var = var/((2**12)**2)
                            sigma=np.sqrt(var)

                            print ' Mean power:', mean_power
                            print ' Mean amplitude: %f LSBs' %(np.sqrt(mean_power))
                            print ' Bit Sigma: %f LSBs' %(sigma)
                            correction = opts.sigma/sigma
                            print ' Target sigma is %f LSBs. Correction factor to reach target is %f' %(opts.sigma, correction)
                            im.eq_amp.coeff['base'].modify_coeffs(ant_n, pol_n, correction, closed_loop=1)
                            if (np.abs(1-correction)<opts.tolerance):
                                #If the antpol satisfies the EQ tolerance, remove it from the todo list
                                print ' ANT %d, POL %s done.' %(ant,['x','y'][pol])
                                pols_left[ant].remove(pol)
                                if len(pols_left[ant])==0:
                                    #If both pols of a given ant are done, remove the antenna from the todo list.
                                    ants_left.remove(ant)
                            print ' Writing coefficients'
                            im.eq_write_all_amp(verbose=False, use_base=True, use_bandpass=True, use_cal=True)
                            im.eq_amp.write_pkl()
                            print ' ANTS LEFT:', ants_left
            else:
                correction = 10000
                while (np.abs(1-correction)>opts.tolerance):
                    print '''\n Grabbing Data...'''
                    for n in range(N):
                        print '   Snap %d of %d' %(n+1,N)
                        spec[n,:,0,:] = snap_x.get_spectras()[:,:,0,chan_range].reshape(Nants,Nchan_range)
                        if im.fConf.pols_per_ant == 2:
                            spec[n,:,1,:] = snap_y.get_spectras()[:,:,0,chan_range].reshape(Nants,Nchan_range)
                    mean_power = np.mean(spec.real**2 + spec.imag**2)
                    var = (np.var(spec.real) + np.var(spec.imag))/2 #Take variance of antenna of interest

                    # Scale for 16_12 binary // This makes one LSB = 1 after we cast to 4_3
                    mean_power = mean_power/((2**12)**2)
                    var = var/((2**12)**2)
                    sigma=np.sqrt(var)
                    
                    print ' Mean power:', mean_power
                    print ' Mean amplitude: %f LSBs' %(np.sqrt(mean_power))
                    print ' Bit Sigma: %f LSBs' %(sigma)
                    correction = opts.sigma/sigma
                    print ' Target sigma is %f LSBs. Correction factor to reach target is %f' %(opts.sigma, correction)
                    for ant in range(Nants):
                        for pol in range(im.fConf.pols_per_ant):
                            ant_n=ant
                            pol_n=pol
                        im.eq_amp.coeff['base'].modify_coeffs(ant_n, pol_n, correction, closed_loop=1)
                    #hist,bins = np.histogram(spec.real, bins=16)
                    ##print bins
                    ##hist[hist==np.max(hist)]=0
                    ##print spec.real
                    #pylab.subplot(2,1,1)
                    #pylab.plot(spec.flatten().real, 'o')
                    #pylab.subplot(2,1,2)
                    ##hist[hist==np.max(hist)]=0
                    #pylab.plot(bins[1:],hist)
                    #pylab.show()
                    if (np.abs(1-correction)<0.01):
                        print '\n Stopping, with residual correction %f' %correction
                        break
                    print ' Writing coefficients'
                    im.eq_write_all_amp(verbose=False, use_base=True, use_bandpass=True, use_cal=True)
                    im.eq_amp.write_pkl()
                    print 'Coefficients now:', im.eq_amp.coeff['master'].coeff[0,0,2]


    if opts.bandpass is not None:
        # Flatten passbands and equalise different antenna
        print ' Calibrating Antenna passbands'
        # Open correlation file
        import h5py
        fh = h5py.File(opts.bandpass,'r')
        # Get the correlation matrix parameters
        # Read the autocorrelations
        print fh['xeng_raw0']
        pol_indices = {'xx':0, 'yy':1, 'xy':2, 'yx':3}
        autocorrelations = np.zeros([Nants,Npols,Nchans])
        for bl_n, bl in enumerate(fh['bl_order'][:]):
            if bl[0]==bl[1]:
                for p in range(Npols):
                    autocorrelations[bl,p,:] = fh['xeng_raw0'][0,:,bl_n,p,1]

        print autocorrelations[:,:,500]
        pylab.ion()
        pylab.figure(0)
        for n,auto_corr in enumerate(autocorrelations):
            for pol in ['xx','yy'][0:Npols]:
                pol_index = pol_indices[pol]
                pylab.plot(10*np.log10(auto_corr[pol_index]), label='Ant %d%s'%(n,pol))
        #pylab.plot(mean_power, 'o', label='Mean Power')
        pylab.title('Autocorrelation Spectrum')
        pylab.xlabel('Frequency Channel')
        pylab.ylabel('Power (dB arb ref)')
        pylab.legend()
        pylab.draw()

        try:
            fit_start_f = float(raw_input('  Enter start frequency for fitting in GHz - '))
        except:
            fit_start_f = xrange[0]
            print '   Error interpretting input. Setting start frequency to lowest frequency in correlation matrix: %f MHz' %fit_start_f
        
        try:
            fit_stop_f  = float(raw_input('  Enter stop frequency for fitting in GHz - '))
        except:
            fit_stop_f = xrange[-1]
            print '   Error interpretting input. Setting stop frequency to highest frequency in correlation matrix: %f MHz' %fit_stop_f

        try:
            order = int(raw_input('  Enter the polynomial order to fit - '))
        except:
            order = 4
            print '   Error interpretting input. Setting fitting order to %d' %order

        fit_start_bin = int((fit_start_f - start_f)/df)
        fit_stop_bin = int((fit_stop_f - start_f)/df)+1

        print '  Fitting bandpasses'
        fit_coeffs = np.zeros([nants,2,order+1])
        mean_amp_fit_coeffs = np.zeros(order+1)
        for ant,autocorr in enumerate(autocorrelations.real):
            for pol in ['xx','yy']:
                pol_index = pol_indices[pol]
                fit_coeffs[ant][pol_index] = np.polyfit(xrange[fit_start_bin:fit_stop_bin], np.sqrt(autocorr[pol_index][fit_start_bin:fit_stop_bin]), order)
        mean_amp_fit_coeffs = fit_coeffs[ant][pol_index] = np.polyfit(xrange[fit_start_bin:fit_stop_bin], np.sqrt(mean_power[fit_start_bin:fit_stop_bin]), order)

        # Plot the fit on top of the correlations to check nothing crazy is happening.
        pylab.figure(1)
        for n in range(nants):
            for pol in ['xx','yy']:
                pol_index = pol_indices[pol]
                pylab.semilogy(xrange,np.sqrt(autocorrelations[n][pol_index].real))
                pylab.semilogy(xrange,np.polyval(fit_coeffs[n][pol_index],xrange))
        pylab.semilogy(xrange,np.polyval(mean_amp_fit_coeffs,xrange), 'o')
        pylab.title('Autocorrelation Spectrum')
        pylab.xlabel('Frequency (GHz)')
        pylab.ylabel('Log Power (arb unit)')
        pylab.draw()
            
        print '  Interpolating fit onto coefficient frequencies'
        mean_amp_fit = np.polyval(mean_amp_fit_coeffs,im.ampcf[int(im.config['antennas']['subbands'][0])][0]['x'].get_freq_points()) # Interpolate the mean power coefficients onto the cal coefficient points
        for fn, fpga in enumerate(im.fpgas):
            subband = int(im.config['antennas']['subbands'][fn])
            for ant in range(Nants_real):
                for pol in ['x','y']:
                    pol_index = pol_indices[pol*2] # Turn 'x' into 'xx', etc.
                    # interpolate fit
                    coeffs = np.polyval(fit_coeffs[ant][pol_index],im.ampcf[subband][ant][pol].get_freq_points())
                    # turn the coefficients into a correction which will bring the channel in line with the mean
                    coeffs = np.mean(mean_amp_fit) / coeffs #Set all channels of all antennas to mean power
                    # Catch the infinite coefficients
                    coeffs[np.isinf(coeffs)] = 0
                    # Modify existing coeffs
                    print "   Mean correction for ant %d, pol %s: %f" %(ant,pol,np.mean(coeffs))
                    im.ampcf[subband][ant][pol].modify_coeffs(coeffs, closed_loop=1)
        print '  Writing Coefficients'
        im.write_amp_eq()
        pylab.show()


except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit()
