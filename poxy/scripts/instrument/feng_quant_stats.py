#! /usr/bin/env python
"""
Automatically set the Amplitude equalisation rams in the Fengines to
equalise power across the observational band, and across multiple input signals.
Automatically scale signals before quantisation to meet a target variance.
"""
import time, sys,struct,logging, os
from poxy import katcp_wrapper, medInstrument,log_handlers, bitOperations, plot_tools
import numpy as np
import pylab, math

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        im.disconnect_all()
    except: pass
    raise
    exit()

def exit_clean():
    try:
        im.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_plot_spectra.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-s', '--sigma', dest='sigma', type='float', default=1.0, 
        help='Target bit sigma. Default is 1 bit. Only relevent for quantisation config')
    p.add_option('-a', '--ant_range', dest='ant_range', default='0_-1', 
        help='Which antennas to check')
    p.add_option('-d', '--dc', dest='dc',action='store_true', default=False, 
        help='Zero out DC bin')
    p.add_option('-N', '--N', dest='N', type='int', default=4, 
        help='Number of snaps of each antenna to perform before calculating statistics. Default: 4')
    p.add_option('-r', '--chan_range', dest='chan_range', default='0_-1', 
        help='Use this flag to limit calculation and uploading of coefficients in the channel range <start_chan>_<end_chan>. Default: 0_-1 (use all)')
    p.add_option('-t', '--tolerance', dest='tolerance', type='float', default=0.02, 
        help='Fractional error allowed in the EQ. Default: 0.02')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

try:
    print ' Connecting...',
    im = medInstrument.fEngine(args[0],lh,program=False)
    s = medInstrument.sEngine(args[0],lh,program=False)
    print 'done'
    start_t = time.time()

    Nchans = im.fConf.n_chan
    Nants = im.fConf.n_ants_sp
    Npols = im.fConf.pols_per_ant
    acc_len = s.sConf.int_acc_len
    

    #Parse channel range option
    start_chan, stop_chan = map(int,opts.chan_range.split('_'))
    start_ant, stop_ant = map(int,opts.ant_range.split('_'))
    chan_range = range(Nchans)[start_chan:stop_chan]
    Nchan_range = len(chan_range)
    ant_range = range(Nants)[start_ant:stop_ant]


    #register names
    subsys   = 'bit_use_mon'
    ctrl     = subsys+'_ctrl'
    var_reg  = subsys+'_var'
    mean_reg = subsys+'_mean'
    new_val  = subsys+'_new_val'

    stats_array = np.zeros([Nants, Nchans, 2])
    
    f = im.fpgas[0]
    for na, ant in enumerate(ant_range):
        for nc, chan in enumerate(chan_range):
            f.write_int(ctrl, (1<<31)+(chan<<17)+(ant<<12))
            f.write_int(ctrl, (0<<31)+(chan<<17)+(ant<<12))
            time.sleep(0.01)
            while ((f.read_int(new_val)&0b1) != 1):
                print 'waiting for data: Current \'new_val\' status is', f.read_int(new_val)
                time.sleep(0.01)
            #mean = float(f.read_int(mean_reg)) / acc_len
            #var = float(bitOperations.uint2int((f.read_uint(var_hi)<<32) + f.read_uint(var_lo), 64)) / acc_len
            mean = float(f.read_int(mean_reg)) / acc_len / 2**7
            var = float(f.read_int(var_reg)) / acc_len / 2**14
            sd = np.sqrt(var)
            stats_array[ant,chan,0] = mean
            stats_array[ant,chan,1] = sd

            print 'ANT %d, CHAN %d : MEAN %f, SD %f' %(ant,chan,float(mean),float(sd))

    for ant in range(Nants):
        pylab.subplot(2,1,1)
        pylab.title('Mean')
        pylab.plot(stats_array[ant,chan_range,0])
        pylab.subplot(2,1,2)
        pylab.title('Standard Deviation')
        pylab.plot(stats_array[ant,chan_range,1])
    
    pylab.show()

except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit()
