#! /usr/bin/env python
""" 
Script to select the X Engine TVG of the Medicina Correlator/SpatialFFT
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
    p.set_usage('xeng_tvg_xeng.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-m', '--mode', dest='mode', default=0,
        help='Mode 1: 4 bit counters, Mode 2: fixed values, Mode 3: fixed values cycled thru different antennas, default: 0, no TVG')
    p.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = p.parse_args(sys.argv[1:])
    mode = int(opts.mode)

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    verbose=opts.verbose

lh=log_handlers.DebugLogHandler()

try:
    print 'Loading configuration file and connecting...',
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done'

    print('\nSetting the X Engine TVGs to Mode: %i...'%(mode)),
    sys.stdout.flush()
    for fpga in xeng.xfpgas:
        xeng.xeng_tvg_xeng(fpga,mode)
    print 'done.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

