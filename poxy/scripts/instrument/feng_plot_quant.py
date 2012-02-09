#! /usr/bin/env python
"""
Plot a Quantized Spectra off the F Engine
"""
import time, sys, struct, numpy, pylab
import katcp_wrapper, medInstrument, xmlParser, bitOperations, log_handlers

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
    p.set_usage('feng_plot_quant.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-s', '--spectra', dest='snap_id', default=0, 
        help='Select which Quantize Snap Block, default=0')

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
    
    for fn,fpga in enumerate(inst.ffpgas):
        inst.write_int('quant_snap_snap_sel_reg',int(opts.snap_id),fpga)
        spectra=inst.snap(fpga,'quant_snap_snap',8192)

        pwr_spec0 = []
        pwr_spec1 = []
        pwr_spec2 = []
        pwr_spec3 = []
        for c,channel in enumerate(spectra):
            s0 = channel&(2**8-1)
            s1 = (channel>>8)&(2**8-1)
            s2 = (channel>>16)&(2**8-1)
            s3 = (channel>>24)&(2**8-1)
        
            pwr0 = bitOperations.uint2pow(s0,4)
            pwr1 = bitOperations.uint2pow(s1,4)
            pwr2 = bitOperations.uint2pow(s2,4)
            pwr3 = bitOperations.uint2pow(s3,4)
            
            pwr_spec0.append(pwr0)
            pwr_spec1.append(pwr1)
            pwr_spec2.append(pwr2)
            pwr_spec3.append(pwr3)
        
        pwr_spec0 = numpy.array(pwr_spec0)
        pwr_spec1 = numpy.array(pwr_spec1)
        pwr_spec2 = numpy.array(pwr_spec2)
        pwr_spec3 = numpy.array(pwr_spec3)
        
        pylab.subplot(221)
        pylab.plot(pwr_spec0)
        pylab.subplot(222)
        pylab.plot(pwr_spec1)
        pylab.subplot(223)
        pylab.plot(pwr_spec2)
        pylab.subplot(224)
        pylab.plot(pwr_spec3)
        pylab.show()

except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit_clean()
