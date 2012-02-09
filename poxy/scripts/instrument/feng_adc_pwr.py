#! /usr/bin/env python
"""
Read and Output the F Engine ADC Power Register
"""

import time, sys, struct, numpy
import random
import katcp_wrapper, medInstrument, xmlParser, log_handlers

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
    p.set_usage('feng_adc_pwr.py CONFIG_FILE')
    p.set_description(__doc__)

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()

print 'Connecting...',
inst=medInstrument.fEngine(args[0],lh)
print 'done'

# Get the current control software reg values, just....because
inst.get_ctrl_sw()

start_t = time.time()
adc_levels_acc_len = inst.adc_levels_acc_len
adc_bits = inst.adc_bits

#clear the screen:
print '%c[2J'%chr(27)

#print '%c[27;39;49m'%chr(27)
#print '%c[?25h'%chr(27)
#print '%c[7;34m'%chr(27)

while True:
    # move cursor home
    adc_pwr = []
    for fn,fpga in enumerate(inst.ffpgas):
        #overflows = inst.feng_read_of(fpga)
        adc_pwr.append([])
        for ant in range( int(inst.config.fengine.n_ants) ):
            fpga.write_int('adc_sw_adc_sel',ant*2)
            time.sleep(.1)
            rv=fpga.read_uint('adc_sw_adc_sum_sq')
            adc_pwr[fn].append(rv)
            
            fpga.write_int('adc_sw_adc_sel',ant*2+1)
            time.sleep(.1)
            rv=fpga.read_uint('adc_sw_adc_sum_sq')
            adc_pwr[fn].append(rv)
        print '%c[2J'%chr(27)
        #color=random.randint(30,37)
        #print '%c[7;%im'%(chr(27),color)
        #bcolor=random.randint(40,47)
        #print '%c[7;%im'%(chr(27),bcolor)
        #print '  ', im.servers[fn]
        for ant in range( int(inst.config.fengine.n_ants) ):
            pwrX = float(adc_pwr[fn][ant*2])
            rmsX = numpy.sqrt(pwrX/adc_levels_acc_len)/(2**(adc_bits-1))
            bitsX = max(numpy.log2(rmsX * (2**(adc_bits))), 0.)
            pwrY = float(adc_pwr[fn][ant*2+1])
            rmsY = numpy.sqrt(pwrY/adc_levels_acc_len)/(2**(adc_bits-1))
            bitsY = max(numpy.log2(rmsY * (2**(adc_bits))),0.)
            if ant<10: print '\tADC0%i:     polX:%.5f (%2.2f bits used)     polY:%.5f (%2.2f bits used)'%(ant,rmsX,bitsX,rmsY,bitsY)
            else: print '\tADC%i:     polX:%.5f (%2.2f bits used)     polY:%.5f (%2.2f bits used)'%(ant,rmsX,bitsX,rmsY,bitsY)

    print 'Time:', time.time() - start_t
    time.sleep(2)

