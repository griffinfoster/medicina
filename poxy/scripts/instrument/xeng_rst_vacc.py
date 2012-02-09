#! /usr/bin/env python
""" 
Script to reset the X Engine vector accumulator of the Medicina Correlator/SpatialFFT
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
    p.set_usage('xeng_rst_vacc.py [options] CONFIG_FILE')
    p.set_description(__doc__)
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
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    feng=medInstrument.fEngine(args[0],lh,program=False)
    print 'done'

    print('\nResetting vector accumulators...'),
    sys.stdout.flush()
    xeng.get_ctrl_sw(ctrl='ctrl')
    """print xeng.ctrl_sw
    xeng.change_ctrl_sw_bits(0, 0, 1, ctrl='ctrl')
    print xeng.ctrl_sw
    xeng.change_ctrl_sw_bits(0, 0, 0, ctrl='ctrl')
    print xeng.ctrl_sw"""
    xeng.rst_vacc()
    xeng.get_ctrl_sw(ctrl='ctrl')
    # Sync and Arm Vector Accumulators
    xeng.xeng_vacc_sync(feng)
   
    #reset errors
    xeng.rst_errs()
    """for fpga in xeng.xfpgas:
        xeng.xeng_ctrl_set(fpga, vacc_rst=False, gbe_out_enable=True)
        xeng.xeng_ctrl_set(fpga, vacc_rst=True, gbe_out_enable=True)
        time.sleep(1)
        xeng.xeng_ctrl_set(fpga, vacc_rst=False, gbe_out_enable=True)
        xeng.xeng_vacc_sync()
    """
    print 'done.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

