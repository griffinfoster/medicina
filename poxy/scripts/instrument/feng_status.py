#! /usr/bin/env python
"""
Read F Engine SW Registers for Errors or Overflows
"""
import time, sys, struct, numpy
from poxy import katcp_wrapper, medInstrument, xmlParser, log_handlers

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        inst.disconnect_all()
    except: pass
    raise
    exit()

def exit_clean():
    try:
        inst.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_status.py CONFIG_FILE')
    p.set_description(__doc__)

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

try:
    print 'Connecting...',
    inst=medInstrument.fEngine(args[0],lh)
    print 'done'
    
    start_t = time.time()
    
    #clear the screen:
    print '%c[2J'%chr(27)

    while True:
        # move cursor home
        print '%c[2J'%chr(27)
        for fn,fpga in enumerate(inst.ffpgas):
            xeng_pcnt = inst.feng_get_current_mcnt(fpga)
            overflow = inst.feng_read_of(fpga)
            #print '  ', im.servers[fn]
            print 'X Engine Packet Count: ', xeng_pcnt
            print 'Overflows:'
            for of_id,of_v in overflow.iteritems():
                print '\t%s:%s'%(of_id,of_v)

        print 'Time:', time.time() - start_t
        time.sleep(2)
    
except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit_clean()
