#! /usr/bin/env python
""" 
Script for initializing S Engine of the Medicina seng.ger
"""
import time, sys, numpy, os, katcp, socket, struct
from poxy import katcp_wrapper, medInstrument, xmlParser, log_handlers
import subprocess

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        seng.disconnect_all()
    except: pass
    exit()

def exit_clean():
    try:
        seng.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('seng_init.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-p', '--skip_prog', dest='prog_fpga',action='store_false', default=True, 
        help='Skip FPGA programming (assumes already programmed).  Default: program the FPGAs')
    p.add_option('-b', '--beam_tvg', dest='beam_tvg',action='store_true', default=False, 
        help='Use this flag to enable the beam test vector generator (over 10GbE).  Default: TVG disabled')
    p.add_option('-x', '--xmask', dest='xmask', default=0, 
        help='Mask one or more of the 4 X-FFT inputs with zeros. Valid values are 4 bit integers')
    p.add_option('-y', '--ymask', dest='ymask', default=0, 
        help='Mask one or more of the 8 Y-FFT inputs with zeros. Valid values are 8 bit integers')
    p.add_option('-e', '--trivial_eq', dest='trivial_eq', action='store_false', default=True, 
            help='Apply inverse EQ coefficients (this ensures calibration is correct if noise powers are different) Default: False')
    p.add_option('-t', '--tx', dest='tx', action='store_true', default=False, 
        help='(Re)start the tx script corr_tx_spead.py on the imager ROACH')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        config_file = None
        print 'Using default config file'
    else:
        config_file = args[0]

    verbose=opts.verbose
    prog_fpga=opts.prog_fpga

lh=log_handlers.DebugLogHandler()

try:
    print 'Loading configuration file and connecting...'
    seng = medInstrument.sEngine(config_file,lh,program=opts.prog_fpga)

    sConf = seng.config.sengine
    rec_conf = seng.config.receiver.sengine
    f_conf = seng.config.fengine
    s_conf = seng.sConf
    tx_dest_ip = rec_conf.rx_ip
    tx_dest_port = rec_conf.rx_port
    tx_script_name = '/root/medicina/corr_tx_spead.py'
    int_time = 2*f_conf.n_chan * s_conf.int_acc_len * s_conf.acc_len / float(f_conf.adc.clk)

    print '\n======================'
    print 'Initial configuration:'
    print '======================'

    # Set the x-fft shifting schedule (3 stages)
    print (''' Setting x-fft shifting schedule to %i ...'''%(sConf.x_fft_shift)),
    sys.stdout.flush()
    seng.set_x_fft_shift(sConf.x_fft_shift)
    print '\t%s' %('done')

    # Set the y-fft shifting schedule (4 stages)
    print (''' Setting the y-fft shifting schedule to %i ...'''%(sConf.y_fft_shift)),
    sys.stdout.flush()
    seng.set_y_fft_shift(sConf.y_fft_shift)
    print '\t%s' %('done')

    # Set the window functions (initialise to 1)
    print (''' Initialising the fft windowing functions to 1 ...''')
    sys.stdout.flush()
    seng.init_x_window()
    seng.init_y_window()
    print '\t%s' %('done')

    # Set the pre-QDR scaling
    print (''' Setting the pre-QDR scaling to %i ...'''%(sConf.acc_scale)),
    sys.stdout.flush()
    seng.set_acc_scale(sConf.acc_scale)
    print '\t\t%s' %('done')

    # Set the Accumulation Length (number of vectors to accumulate)
    print (''' Setting the accumulation length to %i ...'''%(sConf.acc_len)),
    sys.stdout.flush()
    seng.set_acc_len(sConf.acc_len)
    print '\t%s' %('done')
    
    # Mask inputs to spatial FFTs
    xmask = int(opts.xmask)
    ymask = int(opts.ymask)
    print ''' Setting X-FFT mask to %i...''' %xmask,
    seng.set_x_fft_mask(xmask)
    print '\t%s' %('done')
    print ''' Setting Y-FFT mask to %i...''' %ymask,
    seng.set_y_fft_mask(ymask)
    print '\t%s' %('done')

    # Set EQ bram
    if opts.trivial_eq:
        print ''' Loading trivial EQ coefficients into S-engine ...'''
    else:
        print ''' Loading inverse EQ coefficients into S-engine ...'''
    seng.load_eq(use_trivial=opts.trivial_eq,verbose=opts.verbose)

    #Set beam output connection
    print ''' Configuring 10GbE beam output'''
    seng.configure_beam_output()
    seng.tge_reset()

    #Set beam test vector generator
    print ''' Setting beam test vector generator status to:''', opts.beam_tvg
    seng.beam_tvg_en(opts.beam_tvg)

    #Check beam output rate
    print ''' Checking beam output:'''
    seng.reset_packet_cnt()
    init_val = numpy.array(seng.read_uint_all('gbe_packet_cnt'))
    time.sleep(1)
    final_val = numpy.array(seng.read_uint_all('gbe_packet_cnt'))
    packet_cnt = final_val-init_val
    for pn,p in enumerate(packet_cnt):
        print '    FPGA %d: Sent %d packets in the last second' %(pn,p)


    # Check status
    print ''' Checking status...'''
    status = seng.read_status(sleeptime=5)
    for reg in status:
        for stat_id,stat_val in reg.iteritems():
            print '    STATUS: %s%s: %s' %(stat_id, ' '*(30-len(stat_id)), stat_val['val']),
            if stat_val['val'] != stat_val['default']:
                print '\t!!!!!!!!!!'
            else:
                print ''
    sys.stdout.flush()

    if opts.tx:
        # Start TX script
        print ' Starting remote TX scripts'
        for server in seng.servers:
            print '    Starting TX script on server', server
            print '    Getting BOF PID...',
            pidproc = subprocess.Popen('ssh root@%s pidof %s' %(server[0],seng.sConf.bitstream),
                                       shell=True, stdout = subprocess.PIPE)
            pid = int(pidproc.communicate()[0])
            print '    PID is', pid
            print '    Killing previous instances of tx script...',
            sys.stdout.flush()
            subprocess.call('ssh root@%s killall python > /dev/null' %(server[0]), shell=True)
            time.sleep(0.1)
            print 'done'
            print '    Starting data sender...',
            udp_tx = subprocess.Popen('ssh -f root@%s "/usr/bin/python -u %s -x %d -i %s -k %d %d" | head -12' %(server[0], tx_script_name, s_conf.s_per_fpga, tx_dest_ip, tx_dest_port, pid), bufsize=0, shell=True, stdout=subprocess.PIPE)
            print 'done'

            print '\n    Waiting for sender to start transmitting. This will take ~%d seconds' %(8*int_time)
            sender_message = udp_tx.communicate()[0]
            print '\n    Sender says...'
            print '----------------------------------------------'
            print '%s' %sender_message
            print '----------------------------------------------'

        if 'Grabbed' in sender_message:
            print 'It looks like the roach is transmitting. Continuing'
        else:
            print 'ERROR: ROACH does not appear to be sending data properly. Check sync/clock etc. Exiting'
            exit()


except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()
