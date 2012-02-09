#! /usr/bin/env python
""" 
Script for setting the control register of the F Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
import katcp_wrapper, medInstrument, xmlParser, log_handlers

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        mnst.disconnect_all()
    except: pass
    exit()

def exit_clean():
    try:
        inst.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_ctrl.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-d', '--adc_debug', dest='adc_debug',action='store_true', default=False, 
        help='Turn on ADC debug mode')
    p.add_option('-i', '--inter', dest='inter',action='store_true', default=False, 
        help='Do not perform an interleaving reorder for the xengine channels.')
    p.add_option('-n', '--noise', dest='noise',action='store_true', default=False, 
        help='Turn on the test noise signals.  Default: noise off')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    verbose=opts.verbose

lh=log_handlers.DebugLogHandler()

try:
    print 'Loading configuration file and connecting...',
    inst=medInstrument.fEngine(args[0],lh)
    print 'done'

    #Control Settings
    inter = opts.inter
    sync_arm = False
    noise=opts.noise
    sync_rst = False
    adc_debug = opts.adc_debug
    xaui_tx_en = True
    fft_shift=inst.fft_shift

    # Set CTRL register
    print ''' Setting Ctrl Register on F Engine...'''
    print '   Initialising register...',
    inst.initialise_ctrl_sw()
    print 'done'
    print '   Setting fft shift to %d (%s)' %(fft_shift, numpy.binary_repr(fft_shift))
    inst.set_fft_shift(fft_shift)
    print '   Using adc debug inputs?', opts.adc_debug
    inst.debug_signals(opts.adc_debug)
    print '   Xaui TX enable?', xaui_tx_en
    inst.xaui_tx_en(xaui_tx_en)
    print '   Using white noise input?', noise
    inst.white_noise(noise)
    print '   White noise reset:', False
    inst.white_noise_rst(False)

    print ' done'

    # PRINT SW_REG
    for fpga in inst.ffpgas:
        rv = inst.feng_read_ctrl(fpga)
        print ''
        print rv

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

