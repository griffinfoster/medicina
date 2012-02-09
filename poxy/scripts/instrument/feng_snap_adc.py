#!/usr/bin/python

import time, sys,struct,logging
import numpy as np
from poxy import medInstrument
import pylab, math
from poxy import bitOperations as CASPER_formats
from poxy import katcp_wrapper, log_handlers

##################################################
TRIGGER = (1<<6)
control_reg = 'adc_sw_adc_sel'
bram = 'adc_sw_adc_bram'
nsamples = 2**10
adc_inputs = 32
adc_bits = 12
adc_volt_range = 1
##################################################

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

def bit2dbm(Vrange, bits, val, imp=50):
    lsb = 2.*Vrange/2**bits
    V = val*lsb
    pow = V**2/imp
    pow_dbm = 10*np.log(pow*1000)
    return pow_dbm

def bit2v(Vrange, bits, val):
    lsb = 2.*Vrange/2**bits
    voltage = val*lsb
    return voltage

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('feng_plot_spectra.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-v', '--v', dest='v', action='store_true', default=False, 
        help='Plot ADC outputs in volts')
    p.add_option('-u', '--update', dest='update', action='store_true', default=False, 
        help='Continuously update plots')

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()




try:
    print ' Connecting...',
    im=medInstrument.fEngine(args[0],lh,program=False)
    print 'done'

    start_t = time.time()

    adc_clock_period = 1./im.fConf.adc.clk
    time_axis = adc_clock_period*np.array(range(nsamples))
    #Turn interactive mode on, for updating plots
    #Turn hold off so updates replace existing plots
    if opts.update:
        pylab.ion()
        pylab.hold(False)
    y_range = np.array(range(-2**(adc_bits-1), 2**(adc_bits-1)))
    if opts.v:
        y_range = [-adc_volt_range, adc_volt_range]
    while(True):
        int_data = []
        try:
            for fn,fpga in enumerate(im.fpgas):
                for channel_index in range(adc_inputs):
                    print ' Snapping channel', channel_index
                    fpga.write_int(control_reg, channel_index)
                    fpga.write_int(control_reg, TRIGGER + channel_index)
                    fpga.write_int(control_reg, channel_index)
                
                    uintdata = struct.unpack('>%dL' %nsamples, fpga.read(bram,4*nsamples))
                    for sample in uintdata:
                        int_data.append(CASPER_formats.uint2int(sample,adc_bits))
                        #int_data.append(sample-2**(adc_bits-1))
    
                if opts.v:
                    for i, voltage in enumerate(int_data):
                        int_data[i] = bit2v(adc_volt_range, adc_bits, voltage)

                all_inputs = np.array(int_data).reshape(adc_inputs, nsamples)
                for i, input in enumerate(all_inputs):
                    pylab.subplot(4, adc_inputs/4, i+1)
                    pylab.title('ADC input %d' %i)
                    pylab.plot(time_axis, input)
                    pylab.ylim(y_range[0], y_range[-1])
                    pylab.xlim(0,time_axis[-1])
                if opts.update:
                    pylab.draw()
                else:
                    pylab.show()
                    exit()
        except(KeyboardInterrupt):
            exit_clean()
        except:
            pass
    
except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit_clean()




   


