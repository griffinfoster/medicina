#! /usr/bin/env python
"""
(Re)Issues SPEAD metadata and data descriptors so that receivers will be able to interpret the data.
"""

import time, sys, numpy, os, logging
from poxy import medInstrument, log_handlers, xmlParser

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
    p.set_usage('seng_spead_issue.py [options] CONFIG_FILE [OBSERVATION FILE]')
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
    seng=medInstrument.sEngine(args[0],lh,program=False,passive=True)
    feng=medInstrument.fEngine(args[0],lh,program=False,check_adc=False,passive=True)
    print 'done'

    
    seng.load_eq(verbose=opts.verbose)
    print ''' Issuing static metadata...''',
    sys.stdout.flush()
    seng.spead_static_meta_issue()
    seng.seng_spead_eq_meta_issue()
    print 'SPEAD packet sent.'
    
    print ''' Issuing timing metadata...''',
    sys.stdout.flush()
    seng.spead_dynamic_meta_issue()
    print 'SPEAD packet sent.'
    
    print ''' Issuing data descriptors...''',
    sys.stdout.flush()
    seng.spead_seng_data_descriptor_issue()
    print 'SPEAD packet sent.'

    print ''' Issuing EQ data...''',
    sys.stdout.flush()
    feng.eq_init_amp(load_pickle=True)
    feng.spead_eq_amp_meta_issue()
    feng.eq_init_phs(load_pickle=True)
    feng.spead_eq_phs_meta_issue()
    print 'SPEAD packet sent.'

    if len(args)==2:
        print 'Loading source observation file...',
        src=xmlParser.xmlObject(args[1]).xmlobj
        print 'done'

        print ''' Issuing observation metadata...''',
        sys.stdout.flush()
        seng.spead_obs_meta_issue(src.name,src.dec,src.telescope,src.operator)
        print 'SPEAD packet sent.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

