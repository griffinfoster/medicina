#!/usr/bin/env python
'''
Grabs the contents of "snap_pack" (one per FPGA) at the output of the X eng
Assumes the correlator is already initialsed and running etc.
Only good for 4 bit X engines with accumulation length of 128 and demux of 8.
'''
import time, numpy, pylab, struct, sys, logging
import katcp_wrapper, medInstrument, xmlParser, log_handlers

#brams
brams=['bram']
dev_name_base = 'snap_pack'

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        xeng.disconnect_all()
    except: pass
    raise
    exit()

def exit_clean():
    try:
        xeng.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('xeng_snap_pack.py [options] CONFIG_FILE')
    p.add_option('-m', '--manual', dest='manual', action='store_true', default=True, help='Manually trigger snap block.')
    p.add_option('-s', '--snap', dest='snap_block', default='0', help='Select which packet snap block, default 0')
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', help='Print all the decoded (including zero valued) results (be verbose).')
    p.set_description(__doc__)
    opts, args = p.parse_args(sys.argv[1:])

    manual = opts.manual
    snap_block = opts.snap_block

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

report=[]
lh=log_handlers.DebugLogHandler()

try:

    print 'Loading configuration file and connecting...',
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done'

    binary_point = 3
    n_chans=xeng.n_chans
    num_bits = 4
    adc_bits = xeng.adc_bits
    adc_levels_acc_len = xeng.adc_levels_acc_len
    x_per_fpga = xeng.x_per_fpga
    n_ants = xeng.n_ants
    n_stokes = 4
    xeng_acc_len = xeng.xeng_acc_len
    n_bls = xeng.n_bls

    report = dict()

    if num_bits !=4:
        print 'ERR: this script is only written to interpret 4 bit data. Your F engine outputs %i bits.'%num_bits
        exit_fail()
    if xeng_acc_len !=128:
        print 'ERR: this script is only written to interpret data from X engines with acc length of 128. Your X engine accumulates for %i samples.'%xeng_acc_len
        exit_fail()

    print '------------------------'
    print 'Triggering capture...',
    sys.stdout.flush()
    bram_dmp=xeng.xeng_snap(dev_name_base+snap_block, brams, man_trig = manual, wait_period = 4)
    print 'done.'

    print 'Unpacking bram contents...'
    sys.stdout.flush()
    bram_data=[]
    for f, fpga in enumerate(xeng.xfpgas):
        unpack_length=(bram_dmp['lengths'][f])
        print " Unpacking %i values from %s."%(unpack_length, xeng.servers[f][0])
        if unpack_length>0:
            bram_data.append(struct.unpack('>%ii'%(unpack_length), bram_dmp[brams[0]][f]))
        else:
            print " Got no data back for %s."%xeng.servers[f][0]
            bram_data.append([])
    print 'Done.'
    print '========================\n'

    for x, fpga in enumerate(xeng.xfpgas):
        print '--------------------'
        print '\nX-engine %i'%(x)
        print '--------------------'
        for li in range(len(bram_data[x])):
            print li, bram_data[x][li]
        print 'Done with %s, X-engine %i.'%(xeng.servers[x][0],x)
    print 'Done with all.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

