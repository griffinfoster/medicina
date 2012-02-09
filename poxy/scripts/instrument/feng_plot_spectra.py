#! /usr/bin/env python
"""
Plot a Spectra off the F Engine
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
    p.set_usage('feng_plot_spectra.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-c', '--clip', dest='clip',action='store_true', default=False, 
        help='Clip the plots to a max of 5000')
    p.add_option('-s', '--spectra', dest='snap_id', default=0, 
        help='Select which FFT Output Snap Block, default=0')

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
        inst.write_int('spectra_snap_snap_sel_reg',int(opts.snap_id),fpga)
        spectra=inst.snap(fpga,'spectra_snap_snap',8192)
        #time.sleep(.1)
        #spectra=im.snap(fpga,'FFTT_spectra_snap_snap',8192)
        #print im.read_uint_all('FFTT_spectra_snap_snap_addr')
         
        pwr_spec = []
        for c,channel in enumerate(spectra):
            pwr = bitOperations.uint2pow(channel,16)
            pwr_spec.append(pwr)
        pwr_spec = numpy.array(pwr_spec)
        if opts.clip: pwr_spec = pwr_spec.clip(0, 5000)
        pwr_spec = pwr_spec.reshape(8,1024)
         
        pylab.subplot(241)
        pylab.plot(pwr_spec[0])
        #pylab.plot(pwr_spec[0]+pwr_spec[1]+pwr_spec[2]+pwr_spec[3]+pwr_spec[4]+pwr_spec[5]+pwr_spec[7]+pwr_spec[6])
        pylab.subplot(242)
        pylab.plot(pwr_spec[1])
        pylab.subplot(243)
        pylab.plot(pwr_spec[2])
        pylab.subplot(244)
        pylab.plot(pwr_spec[3])
        pylab.subplot(245)
        pylab.plot(pwr_spec[4])
        pylab.subplot(246)
        pylab.plot(pwr_spec[5])
        pylab.subplot(247)
        pylab.plot(pwr_spec[6])
        pylab.subplot(248)
        pylab.plot(pwr_spec[7])
        pylab.show()

except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit_clean()
