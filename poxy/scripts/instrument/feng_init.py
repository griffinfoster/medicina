#! /usr/bin/env python
""" 
Script for initializing F Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
import poxy

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_init.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-p', '--skip_prog', dest='prog_fpga',action='store_false', default=True, 
        help='Skip FPGA programming (assumes already programmed).  Default: program the FPGAs')
    p.add_option('-d', '--adc_debug', dest='adc_debug',action='store_true', default=False, 
        help='Turn on ADC debug mode')
    p.add_option('-e', '--skip_eq', dest='prog_eq',action='store_false', default=True, 
        help='Skip configuration of the correlator equalization.  Default: set the EQ according to config file.')
    p.add_option('-c', '--skip_phs_eq', dest='prog_phs_eq',action='store_false', default=True, 
        help='Skip configuration of the phase equalisation.  Default: Initialise phase multipliers to zero.')
    p.add_option('-n', '--noise', dest='noise',action='store_true', default=False, 
        help='Turn on the test noise signals.  Default: noise off')
    p.add_option('-C', '--cal', dest='cal',action='store_true', default=False, 
        help='Feed X-engine with phase calibrated signals.')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    verbose=opts.verbose
    prog_fpga=opts.prog_fpga
    noise=opts.noise

    print 'Loading configuration file and connecting...'
    feng=poxy.medInstrument.fEngine(args[0],program=prog_fpga)

    print '\n======================'
    print 'Initial configuration:'
    print '======================'

    # ARM THE FENGINE
    print ''' Arming F Engine and setting FFT Shift...''',
    sys.stdout.flush()
    trig_time=feng.feng_arm()
    print ' Armed. Expect trigger at %s local (%s UTC).'%(time.strftime('%H:%M:%S',time.localtime(trig_time)),time.strftime('%H:%M:%S',time.gmtime(trig_time))), 
    print 'SPEAD time meta packet has been sent.'

    #Control Settings
    sync_arm = False
    sync_rst = False
    adc_debug = opts.adc_debug
    xaui_rcv_rst = False
    fft_shift=feng.fft_shift

    time.sleep(0.1)
    feng.set_fft_shift(feng.fft_shift)
    feng.xaui_tx_en(True)
    feng.arm_sync()

    # Set ADC Debug Mode
    print ' Using test inputs?', opts.adc_debug
    feng.debug_signals(opts.adc_debug)

    # Set White Noise Mode
    print ' Using White Noise generators?', opts.noise
    feng.white_noise(opts.noise)

    # Set phase cal mode
    print ' X-engine is using phase calibrated output?', opts.cal
    feng.use_phase_cal(opts.cal)

    # SET INITIAL EQUALIZATION LEVELS
    if opts.prog_eq:
        print ''' Setting X-Engine Amplitude Equalization...''',
        feng.eq_init_amp(load_pickle=False, verbose=opts.verbose, use_base=True, use_bandpass=True, use_cal=False)
        feng.spead_eq_amp_meta_issue()
        time.sleep(0.1)
        sys.stdout.flush()
        print 'done.'
    else: ' Skipping Equalization'

    # SET INITIAL PHASE COEFFICIENTS
    if opts.prog_phs_eq:
        print ''' Setting Phase Equalization...''',
        feng.eq_init_phs(verbose=opts.verbose, load_pickle=False)
        feng.spead_eq_phs_meta_issue()
        time.sleep(0.1)
        sys.stdout.flush()
        print 'done.'
    else: ' Skipping Phase EQ'

    # Check status
    print ''' Checking status...'''
    status = feng.read_status()
    for reg in status:
        for stat_id,stat_val in reg.iteritems():
            print '    STATUS: %s%s: %s' %(stat_id, ' '*(30-len(stat_id)), stat_val['val']),
            if stat_val['val'] != stat_val['default']:
                print '\t!!!!!!!!!!'
            else:
                print ''
    sys.stdout.flush()

    # PRINT SW_REG
    for fpga in feng.fpgas:
        rv = feng.feng_read_ctrl(fpga)
        print ' ',rv

