#!/usr/bin/env python

'''
Grabs the contents of "snap_descramble" for analysis.
Grabs an entire spectrum by default.
Assumes the correlator is already initialsed and running etc.

'''
import time, numpy, struct, sys, logging, katcp
import katcp_wrapper, medInstrument, log_handlers

#brams
bram='bram'
#dev_name = 'snap_descramble_old'
dev_name = 'snap_descramble0'
xeng_on_this_fpga=0

# OOB signalling bit offsets:
data_bit_width =16
data_bit_offset = 16
mcnt_bit_width = 13
mcnt_bit_offset = 3
valid_bit = 2
flag_bit = 1
rcvd_bit = 0


mcnt_mask = (2**(mcnt_bit_width+mcnt_bit_offset)) -(2**mcnt_bit_offset)
data_mask = (2**(data_bit_width+data_bit_offset)) -(2**data_bit_offset)

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

def ip2str(pkt_ip):
    ip_4 = (pkt_ip&((2**32)-(2**24)))>>24
    ip_3 = (pkt_ip&((2**24)-(2**16)))>>16
    ip_2 = (pkt_ip&((2**16)-(2**8)))>>8
    ip_1 = (pkt_ip&((2**8)-(2**0)))>>0
    #print 'IP:%i. decoded to: %i.%i.%i.%i'%(pkt_ip,ip_4,ip_3,ip_2,ip_1)
    return '%i.%i.%i.%i'%(ip_4,ip_3,ip_2,ip_1)    

def xeng_in_unpack(f,start_index):

    sum_polQ_r = 0
    sum_polQ_i = 0
    sum_polI_r = 0
    sum_polI_i = 0

    rcvd_errs = 0
    flag_errs = 0

    #average the packet contents from the very first entry
    for slice_index in range(xeng_acc_len):
        abs_index = start_index + slice_index
        polQ_r = (bram_oob[f]['data'][abs_index] & ((2**(16)) - (2**(12))))>>(12)
        polQ_i = (bram_oob[f]['data'][abs_index] & ((2**(12)) - (2**(8))))>>(8)
        polI_r = (bram_oob[f]['data'][abs_index] & ((2**(8)) - (2**(4))))>>(4)
        polI_i = (bram_oob[f]['data'][abs_index] & ((2**(4)) - (2**(0))))>>0

        #square each number and then sum it
        sum_polQ_r += (float(((numpy.int8(polQ_r << 4)>> 4)))/(2**binary_point))**2
        sum_polQ_i += (float(((numpy.int8(polQ_i << 4)>> 4)))/(2**binary_point))**2
        sum_polI_r += (float(((numpy.int8(polI_r << 4)>> 4)))/(2**binary_point))**2
        sum_polI_i += (float(((numpy.int8(polI_i << 4)>> 4)))/(2**binary_point))**2

        if not bram_oob[f]['rcvd'][abs_index]: rcvd_errs +=1
        if bram_oob[f]['flag'][abs_index]: flag_errs +=1

    num_accs = xeng_acc_len

    level_polQ_r = numpy.sqrt(float(sum_polQ_r)/ num_accs)
    level_polQ_i = numpy.sqrt(float(sum_polQ_i)/ num_accs)
    level_polI_r = numpy.sqrt(float(sum_polI_r)/ num_accs)
    level_polI_i = numpy.sqrt(float(sum_polI_i)/ num_accs)

    rms_polQ = numpy.sqrt(((level_polQ_r)**2)  +  ((level_polQ_i)**2))
    rms_polI = numpy.sqrt(((level_polI_r)**2)  +  ((level_polI_i)**2))

    if level_polQ_r < 1.0/(2**num_bits):
        ave_bits_used_Q_r = 0
    else:
        ave_bits_used_Q_r = numpy.log2(level_polQ_r*(2**binary_point))

    if level_polQ_i < 1.0/(2**num_bits):
        ave_bits_used_Q_i = 0
    else:
        ave_bits_used_Q_i = numpy.log2(level_polQ_i*(2**binary_point))

    if level_polI_r < 1.0/(2**num_bits):
        ave_bits_used_I_r = 0
    else:
        ave_bits_used_I_r = numpy.log2(level_polI_r*(2**binary_point))

    if level_polI_i < 1.0/(2**num_bits):
        ave_bits_used_I_i = 0
    else:
        ave_bits_used_I_i = numpy.log2(level_polI_i*(2**binary_point))

    return {'rms_polQ':rms_polQ,\
            'rms_polI':rms_polI,\
            'rcvd_errs':rcvd_errs,\
            'flag_errs':flag_errs,\
            'ave_bits_used_Q_r':ave_bits_used_Q_r,\
            'ave_bits_used_Q_i':ave_bits_used_Q_i,\
            'ave_bits_used_I_r':ave_bits_used_I_r,\
            'ave_bits_used_I_i':ave_bits_used_I_i}


if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('snap_10gbe_tx.py [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-n', '--n_chans', dest='n_chans', type='int', default=0,
        help='How many channels should we retrieve?')   
    p.add_option('-v', '--verbose', dest='verbose', action='store_true',
        help='Print raw contents.')   
    p.add_option('-r', '--raw', dest='raw', action='store_true',
        help='Capture raw data (as opposed to only valid data).')   
    p.add_option('-t', '--trigger', dest='man_trigger', action='store_true',
        help='Trigger snap block manually.')   
    p.add_option('-c', '--circ', dest='circ', action='store_true',
        help='Enable circular buffering, waiting for error in datastream before capturing.')   

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

    if opts.man_trigger:
        man_trigger = True
        print 'NOTE: expected frequencies and antenna indices will be wrong with manual trigger option.'
    else:
        man_trigger = False

    if opts.raw:
        raw_capture = True
        print 'NOTE: number of decoded frequency channels will not be accurate with RAW capture mode.'
    else:
        raw_capture = False

    n_chans= opts.n_chans

lh=log_handlers.DebugLogHandler()

try:
    print 'Parsing configuration file...',
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done.'

    servers = xeng.servers
    binary_point = 3
    num_bits = 4
    xeng_acc_len=xeng.xeng_acc_len
    n_ants=xeng.n_ants
    x_per_fpga=xeng.x_per_fpga
    n_ants_per_xaui=xeng.n_ants_per_feng
    n_xeng = x_per_fpga*len(servers)
    if n_chans==0: n_chans=xeng.n_chans
    exp_len_from_descr = n_chans/n_xeng * n_ants * xeng_acc_len

    if opts.circ:
        print 'Enabling circular-buffer capture on snap block.\n Triggering and Capturing, waiting 2 seconds for error...',
        sys.stdout.flush()
        bram_dmp=xeng.xeng_snap(dev_name,[bram],man_trig=man_trigger,man_valid=raw_capture,wait_period=5,offset=0,circular_capture=True)
        print 'done.'
    else:
        print 'Trying to retrieve %i words from each x engine...'%exp_len_from_descr

        print '------------------------'
        #bram_dmp = [[0 for i in range(exp_len_from_descr*4)] for f in fpgas]
        print 'Triggering and capturing from offset 0 ...',
        bram_dmp=xeng.xeng_snap(dev_name,[bram],man_trig=man_trigger,man_valid=raw_capture,wait_period=1) #,offset=0)
        print 'done'
        report = dict()

        while bram_dmp['lengths'][0]<exp_len_from_descr:
            print 'Triggering and capturing at offset %i...'%bram_dmp['lengths'][0],
            bram_tmp=xeng.xeng_snap(dev_name,[bram],man_trig=man_trigger,man_valid=raw_capture,wait_period=1) #,offset=bram_dmp['lengths'][0])
            for f,fpga in enumerate(xeng.xfpgas):
                bram_dmp[bram][f] += bram_tmp[bram][f]
            print 'done'
            for f,fpga in enumerate(xeng.xfpgas):
                if (bram_tmp['lengths'][f] != bram_tmp['lengths'][f-1]): raise RuntimeError('Not all X engines captured the same amount of snapshot data.')
                bram_dmp['lengths'][f] += bram_tmp['lengths'][f]
            time.sleep(0.1)
        for f,fpga in enumerate(xeng.xfpgas):
            bram_dmp[bram][f]=''.join(bram_dmp[bram][f])

    #print 'BRAM DUMPS:'
    #print bram_dmp

    for f,fpga in enumerate(xeng.xfpgas):
        print 'Got %i words starting at offset %i from %s'%(bram_dmp['lengths'][f],bram_dmp['offsets'][f],xeng.servers[f][0])

#print 'Total size for each x engine: %i bytes'%len(bram_dmp[0])

    print 'Unpacking bram contents...',
    sys.stdout.flush()
    bram_oob=dict()
    for f,fpga in enumerate(xeng.xfpgas):
        if bram_dmp['lengths'][f]==0: print 'Warning: got nothing back from snap block on %s.'%xeng.servers[f][0]
        else:
            bram_oob[f]={'raw':struct.unpack('>%iL'%(bram_dmp['lengths'][f]),bram_dmp[bram][f])}
            bram_oob[f].update({'rcvd':[bool(i & (2**rcvd_bit)) for i in bram_oob[f]['raw']]})
            bram_oob[f].update({'flag':[bool(i & (2**flag_bit)) for i in bram_oob[f]['raw']]})
            bram_oob[f].update({'valid':[bool(i & (2**valid_bit)) for i in bram_oob[f]['raw']]})
            bram_oob[f].update({'mcnt':[(i&mcnt_mask)>>mcnt_bit_offset for i in bram_oob[f]['raw']]})
            bram_oob[f].update({'data':[(i&data_mask)>>data_bit_offset for i in bram_oob[f]['raw']]})
            #print '\n\nFPGA %i, bramoob:'%f,bram_oob
    print 'Done unpacking.'

    if opts.verbose:
        for f,server in enumerate(xeng.servers):
            i=bram_dmp['offsets'][f]
            for ir in range(bram_dmp['lengths'][f]):
                pkt_mcnt=bram_oob[f]['mcnt'][ir]
                pkt_data=bram_oob[f]['data'][ir]
                exp_ant=(i/xeng_acc_len)%n_ants
                xeng=(x_per_fpga)*f + xeng_on_this_fpga
                exp_mcnt = ((i/xeng_acc_len)/n_ants)*n_xeng + xeng
                exp_freq= (exp_mcnt)%xeng.n_chans
                act_mcnt=(pkt_mcnt+xeng)
                act_freq=act_mcnt%xeng.n_chans
                xeng_slice=i%xeng_acc_len+1
                print '[%s] Xeng%i BRAM IDX: %6i Valid IDX: %10i Rounded MCNT: %6i. Global MCNT: %6i. Freq %4i, Data: 0x%04x. EXPECTING: slice %3i/%3i of ant %3i, freq %3i.'%(server[0],xeng,ir,i,pkt_mcnt,act_mcnt,act_freq,pkt_data,xeng_slice,xeng_acc_len,exp_ant,exp_freq),
                if bram_oob[f]['valid'][ir]: 
                    print '[VALID]',
                    i=i+1
                if bram_oob[f]['rcvd'][ir]: print '[RCVD]',
                if bram_oob[f]['flag'][ir]: print '[FLAG_BAD]',
                print ''


    if not raw_capture and not opts.circ:
        print 'Analysing contents...'
        report = dict()
        mcnts = dict()
        for f,server in enumerate(xeng.servers):
            report[f]=dict()
            for i in range(0,bram_dmp['lengths'][f],xeng_acc_len):        
                pkt_mcnt=bram_oob[f]['mcnt'][i]
                pkt_data=bram_oob[f]['data'][i]
                exp_ant=(i/xeng_acc_len)%n_ants
                exp_freq=(i/xeng_acc_len)/n_ants * n_xeng + ((x_per_fpga)*f + xeng_on_this_fpga)
                xeng_unpkd=xeng_in_unpack(f,i)
                #print xeng_unpkd
                print '[%s] IDX: %6i. ANT: %4i. FREQ: %4i. 4 bit power: PolQ: %4.2f, PolI: %4.2f'%(server[0],i,exp_ant,exp_freq,xeng_unpkd['rms_polQ'],xeng_unpkd['rms_polI']),
                if xeng_unpkd['rcvd_errs']>0: 
                    print '[%i RCV ERRS!]'%xeng_unpkd['rcvd_errs'],
                    if not report[f].has_key('Rcv Errors'):
                        report[f]['Rcv Errors'] = 1
                    else:
                        report[f]['Rcv Errors'] += 1

                if xeng_unpkd['flag_errs']>0: 
                    print '[%i FLAGGED DATA]'%xeng_unpkd['flag_errs'],
                    if not report[f].has_key('Flagged bad data'):
                        report[f]['Flagged bad data'] = 1
                    else:
                        report[f]['Flagged bad data'] += 1
                print ''


        print '\n\nDone with all servers.\nSummary:\n=========================='

        for s,srvr in enumerate(servers):
            print '------------------------'
            print srvr
            print '------------------------'
            for key in report[s].iteritems():
                print key[0],': ',key[1]
        print '=========================='

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

exit_clean()                           

