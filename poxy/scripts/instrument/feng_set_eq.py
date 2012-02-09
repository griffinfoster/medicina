#! /usr/bin/env python
""" 
Script for setting the equalization levels of the F Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
from poxy import katcp_wrapper, medInstrument, xmlParser, log_handlers

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
    p.set_usage('feng_set_eq.py [options] CONFIG_FILE')
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
    inst=medInstrument.fEngine(args[0],lh)
    print 'done'

    # SET INITIAL EQUALIZATION LEVELS
    print ''' Setting X-Engine Amplitude Equalization...''',
    inst.eq_set_default_all('xengine','amp',verbose=False)
    time.sleep(0.1)
    sys.stdout.flush()
    print 'done.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

