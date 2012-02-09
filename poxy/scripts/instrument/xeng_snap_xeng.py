#!/usr/bin/env python
'''
Grabs the contents of "snap_xeng0" (one per FPGA) at the output of the X eng
and prints any non-zero values.
Assumes the correlator is already initialsed and running etc.
Only good for 4 bit X engines with accumulation length of 128 and demux of 8.

Author: Jason Manley\n
Revisions:\n
2010-08-05: JRM Mods to support corr-0.5.0  
2010-07-29: PVP Cleanup as part of the move to ROACH F-Engines. Testing still needed.\n
2009------: JRM Initial revision.\n
'''
import time, numpy, pylab, struct, sys, logging
import katcp_wrapper, medInstrument, xmlParser, log_handlers

#brams
brams=['bram']
dev_name = 'snap_xeng0'

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
    p.set_usage('xeng_snap_xeng.py [options] CONFIG_FILE')
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', help='Print all the decoded (including zero valued) results (be verbose).')
    p.add_option('-o', '--ch_offset', dest='ch_offset', type='int', default=0, help='Start capturing at specified channel number. Default is 0.')
    p.set_description(__doc__)
    opts, args = p.parse_args(sys.argv[1:])

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
    ch_offset = opts.ch_offset

    if num_bits !=4:
        print 'ERR: this script is only written to interpret 4 bit data. Your F engine outputs %i bits.'%num_bits
        exit_fail()
    if xeng_acc_len !=128:
        print 'ERR: this script is only written to interpret data from X engines with acc length of 128. Your X engine accumulates for %i samples.'%xeng_acc_len
        exit_fail()

    print '------------------------'
    print 'Triggering capture...',
    offset = ch_offset * n_stokes * n_bls * 2   #hardcoded for demux of 8
    print "at offset %i..."%offset,
    sys.stdout.flush()
    bram_dmp=xeng.xeng_snap(dev_name, brams, man_trig = False, wait_period = 2, offset = offset)
    print 'done.'

    print 'Unpacking bram contents...'
    #hardcode unpack of 16 bit values. Assumes bitgrowth of log2(128)=7 bits and input of 4_3 * 4_3.
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
        for li in range(len(bram_data[x]) / 2):
            #index over complex numbers in bram
            index = li + bram_dmp['offsets'][x] / 2
            stokes = index % n_stokes
            bls_index = (index / n_stokes) % n_bls
            freq = (index / n_stokes / n_bls) * x_per_fpga * len(xeng.xfpgas) + x
            #i, j = c.get_bl_order()[bls_index]
            real_val = bram_data[x][li * 2]
            imag_val = bram_data[x][li * 2 + 1]
            if (real_val != 0) or (imag_val != 0) or opts.verbose:
                print '[%s] [%4i]: Freq: %i. Stokes: %i. Raw value: 0x%05x + 0x%05xj (%6i + %6ij).'%(xeng.servers[x][0], index, freq, stokes, real_val, imag_val, real_val, imag_val)
        print 'Done with %s, X-engine %i.'%(xeng.servers[x][0],x)
    print 'Done with all.'

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

exit_clean()

