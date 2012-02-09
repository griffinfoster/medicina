#! /usr/bin/env python
"""
(Re)Issues SPEAD metadata and data descriptors so that receivers will be able to interpret the data.
"""

import time, sys, numpy, os, logging
from poxy import katcp_wrapper, medInstrument, log_handlers, xmlParser

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
    p.set_usage('xeng_spead_issue.py [options] CONFIG_FILE')
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
    print 'done'
    feng=medInstrument.fEngine(args[0],lh,program=False,check_adc=False)

    print 'Loading source observation file...'
    src=xmlParser.xmlObject(args[1]).xmlobj
    print 'done'

    print ''' Issuing static metadata...''',
    sys.stdout.flush()
    xeng.spead_static_meta_issue()
    print 'SPEAD packet sent.'

    print ''' Issuing timing metadata...''',
    sys.stdout.flush()
    xeng.spead_time_meta_issue()
    print 'SPEAD packet sent.'

    print ''' Issuing data descriptors...''',
    sys.stdout.flush()
    xeng.spead_data_descriptor_issue()
    print 'SPEAD packet sent.'
    
    print ''' Issuing observation metadata...''',
    sys.stdout.flush()
    xeng.spead_obs_meta_issue(src.name,src.dec,src.telescope,src.operator)
    print 'SPEAD packet sent.'
    
    print ''' Issuing EQ data...''',
    sys.stdout.flush()
    feng.eq_init_amp(load_pickle=True)
    feng.spead_eq_amp_meta_issue()
    print 'SPEAD packet sent.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

