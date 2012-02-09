#! /usr/bin/env python
""" 
Script for initializing F Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
from poxy import katcp_wrapper, medInstrument, xmlParser, log_handlers

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        feng.disconnect_all()
    except: pass
    exit()

def exit_clean():
    try:
        feng.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':

    args = sys.argv[1:]

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

#try:
print 'Loading configuration file and connecting...',
feng=medInstrument.fEngine(args[0],lh,program=False)
print 'done'

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

#except KeyboardInterrupt:
#    exit_clean()
#except:
#    exit_fail()

