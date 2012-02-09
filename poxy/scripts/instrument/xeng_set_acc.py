#! /usr/bin/env python
""" 
Script to set the QDR accumulation length of the X Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
import katcp_wrapper, medInstrument, log_handlers

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        xeng.disconnect_all()
    except: pass
    exit()

def exit_clean():
    try:
        xeng.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('xeng_set_acc.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-a', '--acc', dest='acc_num', default=1024,
        help='Set the QDR accumulation length, default: 1024')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = p.parse_args(sys.argv[1:])
    acc_num = int(opts.acc_num)

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    verbose=opts.verbose

lh=log_handlers.DebugLogHandler()

try:
    print 'Loading configuration file and connecting...',
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done'

    # Set the secondary accumulation length, the X Engine does a 128 sample first stage accumulation
    # acc_num to time conversion:
    # qdr_acc_len*xeng_acc_len*n_chans/data_clk
    int_time = acc_num * xeng.xeng_acc_len * xeng.n_chans / (xeng.adc_clk/2)
    print ''' Setting the QDR accumulation length to %i, the total integration time is %f (s) ...'''%(acc_num,int_time),
    for fpga in xeng.xfpgas: xeng.xeng_set_qdr_acc_len(fpga, n_accs=acc_num)
    print 'done'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

