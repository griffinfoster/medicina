#! /usr/bin/env python
""" 
Script to select the Vacc TVG of the Medicina Correlator/SpatialFFT
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
    p.set_usage('xeng_tvg_vacc.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-c', '--cnt', dest='cnt', action='store_true', default=False,
        help='Input a counter into the vacc.')
    p.add_option('-f', '--fixed', dest='const', default=-1,
        help='Input a constant into the vacc.')
    p.add_option('-v', '--valid', dest='valid', action='store_true', default=False,
        help='Generate a valid signal, default: use the xeng output valid signal')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

enable=False
data_sel=False
valid_sel=False
inject_cnt=False
rst=False

try:
    print 'Loading configuration file and connecting...',
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done'

    num_pulses=1000000
    #group_period=1048576
    group_period=557056*2
    n_per_group=557056

    print('\nSetting the Vacc TVGs: ...'),
    sys.stdout.flush()
    if int(opts.const) > 0:
        c=int(opts.const)
        #for fpga in xeng.xfpgas:
        #    xeng.write_int('vacc_tvg1_write1',c,fpga)
        #    xeng.write_int('vacc_tvg2_write1',c,fpga)
        data_sel = True
    if opts.cnt: inject_cnt=True
    if opts.valid:
        valid_sel=True
        #rst=True
        #enable=True
        for fpga in xeng.xfpgas:
            xeng.write_int('vacc_tvg1_n_pulses',num_pulses,fpga)
            xeng.write_int('vacc_tvg1_group_period',group_period,fpga)
            xeng.write_int('vacc_tvg1_n_per_group',n_per_group,fpga)
            xeng.write_int('vacc_tvg2_n_pulses',num_pulses,fpga)
            xeng.write_int('vacc_tvg2_group_period',group_period,fpga)
            xeng.write_int('vacc_tvg2_n_per_group',n_per_group,fpga)
    for fpga in xeng.xfpgas:
        xeng.xeng_tvg_vacc(fpga,enable=enable,data_sel=data_sel,valid_sel=valid_sel,inject_cnt=inject_cnt,rst=rst)
    print 'done.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

