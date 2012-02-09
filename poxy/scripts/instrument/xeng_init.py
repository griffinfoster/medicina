#! /usr/bin/env python
""" 
Script for initializing X Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
import poxy

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('xeng_init.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-c', '--check', dest='check_errs',action='store_true', default=False, 
        help='After initializing the X Engine check for possible errors.  Default: do not check for errors')
    p.add_option('-o', '--output_tge', dest='output_tge',action='store_false', default=True, 
        help='Do not intialize 10 GbE Output')
    p.add_option('-p', '--skip_prog', dest='prog_fpga',action='store_false', default=True, 
        help='Skip FPGA programming (assumes already programmed).  Default: program the FPGAs')
    p.add_option('-s', '--spead', dest='spead',action='store_false', default=True, 
        help='Skip sending SPEAD meta packets.  Default: send SPEAD meta packets')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')
    p.add_option('-w', '--wait', dest='wait', default=10000, 
        help='Number off clocks to wait before transmitting 10 GbE Packets, for subsecond accumulations set to 1000 default: 10000')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    verbose=opts.verbose
    prog_fpga=opts.prog_fpga
    check_errs=opts.check_errs
    output_tge=opts.output_tge

    print '\n======================'
    print 'Initial configuration:'
    print '======================'
    
    print ' Loading configuration file and connecting...'
    xeng=poxy.medInstrument.xEngine(args[0],program=prog_fpga)
    print ' done'
    feng=poxy.medInstrument.fEngine(args[0],program=False,check_adc=False)
    
    # Set the secondary accumulation length, the X Engine does a 128 sample first stage accumulation
    # acc_num to time conversion:
    # qdr_acc_len*xeng_acc_len*n_chans/data_clk
    acc_time=xeng.int_time
    print ''' Setting the QDR accumulation length to %i, the total integration time is %f (s) ...'''%(xeng.qdr_acc_len,xeng.int_time),
    for fpga in xeng.xfpgas: xeng.xeng_set_qdr_acc_len(fpga)
    print 'done'

    # Sync and Arm Vector Accumulators
    print ''' Arming Vector Accumulator ...''',
    xeng.xeng_vacc_sync(feng)
    print 'done'
    
    # Set board IDs
    print ''' Setting Board IDs ...''',
    for f,fpga in enumerate(xeng.xfpgas):
        xeng.write_int('board_id',f,fpga)
        print f,
    print 'done'

    #10 gbe mux wait time
    mux_wait_time = int(opts.wait)
    print ''' Setting 10 GbE Wait Time  ...''',
    for f,fpga in enumerate(xeng.xfpgas):
        xeng.write_int('mux_idle_clk',mux_wait_time,fpga)
        print mux_wait_time, ' clks ',
    print 'done'

    # Reset Error Counters
    print ' Reseting error counters...',
    xeng.rst_errs()
    print 'done'

    if check_errs:
        print ' Waiting on system before checking for Errors...'
        time.sleep(acc_time*2.)
        print ' done'

        # Check XAUI links are good
        print ' XAUI links good...',
        for fpga in xeng.xfpgas: print xeng.xeng_check_xaui_error(fpga),
        print ''

        # Check Vector Accumulators have no errors and are receiving data
        print ' Checking Vaccs...',
        for fpga in xeng.xfpgas: print xeng.xeng_check_vacc(fpga,verbose=True),
        print ''

    print ' Sending SPEAD metatdata and data descriptors...',
    sys.stdout.flush()
    if opts.spead:
        xeng.spead_static_meta_issue()
        xeng.spead_time_meta_issue()
        xeng.spead_data_descriptor_issue()
        print 'done'
    else: print 'skipped.'

    # Output over 10 GbE to rx computer
    if output_tge:
        print ' Enabling UDP output...',
        sys.stdout.flush()
        xeng.enable_10gbe_tx()
        print  'done'

        print ' Configuring UDP 10GbE output to %s:%i...'%(xeng.rx_udp_ip_str,xeng.rx_udp_port)
        sys.stdout.flush()
        for fpga in xeng.xfpgas: xeng.config_udp_output(fpga)
        print ''

