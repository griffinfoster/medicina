#! /usr/bin/env python
""" 
Script for Arming the F Engine of the Medicina Correlator/SpatialFFT
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
    p.set_usage('feng_arm.py [options] CONFIG_FILE')
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

    print '\n======================'
    print 'Initial configuration:'
    print '======================'
    # Get the current ctrl sw state
    print ''' Getting the current ctrl_sw state''',
    inst.get_ctrl_sw()
    print 'done'

    # ARM THE FENGINE
    print ''' Arming F Engine...''',
    trig_time=inst.feng_arm()
    print ' Armed. Expect trigger at %s local (%s UTC).'%(time.strftime('%H:%M:%S',time.localtime(trig_time)),time.strftime('%H:%M:%S',time.gmtime(trig_time))), 
    print 'SPEAD time meta packet has been sent.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

