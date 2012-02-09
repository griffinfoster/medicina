#! /usr/bin/env python
""" 
Script to report on the status of the X Engine of the Medicina Correlator/SpatialFFT
"""

import time, sys, numpy, os, katcp, socket, struct
from poxy import katcp_wrapper, medInstrument, log_handlers

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
    p.set_usage('xeng_status.py [options] CONFIG_FILE')
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
    xeng=medInstrument.xEngine(args[0],lh,program=False)
    print 'done'

    start_t = time.time()
    #clear the screen:
    print '%c[2J'%chr(27)
    
    while True:
        
        for fn, fpga in enumerate(xeng.xfpgas):
            xaui_errs = [xeng.read_uint('xaui_err%i'%(x), fpga) for x in range(xeng.n_xaui)]
            xaui_rx_cnt = [xeng.read_uint('xaui_cnt%i'%(x), fpga) for x in range(xeng.n_xaui)]
            #xaui_pkt_cnt = [xeng.read_uint('xaui_pkt_cnt%i'%(x), fpga) for x in range(xeng.n_xaui)]
            xaui_mcnt = [xeng.read_uint('xaui_sync_mcnt%i'%(x), fpga) for x in range(xeng.n_xaui)]
            gbe_tx_errs = [xeng.read_uint('gbe_tx_err_cnt%i'%(x), fpga) for x in range(xeng.n_xaui)]
            gbe_tx_cnt = [xeng.read_uint('gbe_tx_cnt%i'%(x), fpga) for x in range(xeng.n_xaui)]

            #x_cnt = [xeng.read_uint('pkt_reord_cnt%i'%(x), fpga) for x in range(xeng.x_per_fpga)]
            #x_miss = [xeng.read_uint('pkt_reord_err%i'%(x), fpga) for x in range(xeng.x_per_fpga)]
            #last_miss_ant = [xeng.read_uint('last_missing_ant%i'%(x), fpga) for x in range(xeng.x_per_fpga)]

            vacc_cnt = [xeng.read_uint('vacc_cnt%i'%(x), fpga) for x in range(xeng.x_per_fpga)]
            vacc_errs = [xeng.read_uint('vacc_err_cnt%i'%(x), fpga) for x in range(xeng.x_per_fpga)]
            vacc_status = [xeng.read_uint('vacc_ld_status0', fpga)]

            pack_out_cnt = [xeng.read_uint('pack_out_cnt%i'%(x), fpga) for x in range(xeng.x_per_fpga)]
            pack_out_errs = [xeng.read_uint('pack_out_err%i'%(x), fpga) for x in range(xeng.x_per_fpga)]

            p_valid_out_cnt = [xeng.read_uint('p_valid_out_cnt', fpga) for x in range(xeng.x_per_fpga)]
            p_eof_cnt = [xeng.read_uint('p_eof_cnt', fpga) for x in range(xeng.x_per_fpga)]
            p_err_cnt = [xeng.read_uint('p_err_cnt', fpga) for x in range(xeng.x_per_fpga)]
            p_valid_in_cnt = [xeng.read_uint('p_valid_in_cnt', fpga) for x in range(xeng.x_per_fpga)]
            p_pkt_rdy_cnt = [xeng.read_uint('p_pkt_rdy_cnt', fpga) for x in range(xeng.x_per_fpga)]
            p_rb_done_cnt = [xeng.read_uint('p_rb_done_cnt', fpga) for x in range(xeng.x_per_fpga)]
            
            g_valid_cnt = [xeng.read_uint('g_valid_cnt', fpga) for x in range(xeng.x_per_fpga)]
            g_eof_cnt = [xeng.read_uint('g_eof_cnt', fpga) for x in range(xeng.x_per_fpga)]
            g_send0_cnt = [xeng.read_uint('g_send0_cnt', fpga) for x in range(xeng.x_per_fpga)]
            g_send1_cnt = [xeng.read_uint('g_send1_cnt', fpga) for x in range(xeng.x_per_fpga)]
            flushing_cnt = [xeng.read_uint('g_send1_cnt1', fpga) for x in range(xeng.x_per_fpga)]

            vacc_vld_cnt = [xeng.read_uint('vacc_vld_cnt', fpga) for x in range(xeng.x_per_fpga)]
            vacc_sync_cnt = [xeng.read_uint('vacc_sync_cnt', fpga) for x in range(xeng.x_per_fpga)]
            xeng_vld_cnt = [xeng.read_uint('xeng_vld_cnt', fpga) for x in range(xeng.x_per_fpga)]
            xeng_sync_cnt = [xeng.read_uint('xeng_sync_cnt', fpga) for x in range(xeng.x_per_fpga)]

            """
            vacc_cnt = [xeng.read_uint('vacc_cnt%i'%(x), fpga) for x in range(1)]
            vacc_errs = [xeng.read_uint('vacc_err_cnt%i'%(x), fpga) for x in range(1)]
            vacc_status = [xeng.read_uint('vacc_ld_status0', fpga)]

            pack_out_cnt = [xeng.read_uint('pack_out_cnt%i'%(x), fpga) for x in range(1)]
            pack_out_errs = [xeng.read_uint('pack_out_err%i'%(x), fpga) for x in range(1)]

            p_valid_out_cnt = [xeng.read_uint('p_valid_out_cnt', fpga) for x in range(1)]
            p_eof_cnt = [xeng.read_uint('p_eof_cnt', fpga) for x in range(1)]
            p_err_cnt = [xeng.read_uint('p_err_cnt', fpga) for x in range(1)]
            p_valid_in_cnt = [xeng.read_uint('p_valid_in_cnt', fpga) for x in range(1)]
            p_pkt_rdy_cnt = [xeng.read_uint('p_pkt_rdy_cnt', fpga) for x in range(1)]
            p_rb_done_cnt = [xeng.read_uint('p_rb_done_cnt', fpga) for x in range(1)]
            
            g_valid_cnt = [xeng.read_uint('g_valid_cnt', fpga) for x in range(1)]
            g_eof_cnt = [xeng.read_uint('g_eof_cnt', fpga) for x in range(1)]
            g_send0_cnt = [xeng.read_uint('g_send0_cnt', fpga) for x in range(1)]
            #g_send1_cnt = [xeng.read_uint('g_send1_cnt', fpga) for x in range(1)]
            flushing_cnt = [xeng.read_uint('g_send1_cnt1', fpga) for x in range(1)]

            vacc_vld_cnt = [xeng.read_uint('vacc_vld_cnt', fpga) for x in range(1)]
            vacc_sync_cnt = [xeng.read_uint('vacc_sync_cnt', fpga) for x in range(1)]
            xeng_vld_cnt = [xeng.read_uint('xeng_vld_cnt', fpga) for x in range(1)]
            xeng_sync_cnt = [xeng.read_uint('xeng_sync_cnt', fpga) for x in range(1)]
            """

            print '%c[2J'%chr(27)
            print '  ', xeng.servers[fn]

            for x in range(xeng.n_xaui):
                print '\tXAUI%i         RX cnt: %10i    Errors: %10i'%(x,xaui_rx_cnt[x],xaui_errs[x])
                #print '\tXAUI%i PKT     RX cnt: %10i'%(x,xaui_pkt_cnt[x])
                print '\tXAUI%i MCNT       cnt: %10i'%(x,xaui_mcnt[x])
                print '\t10GbE%i        TX cnt: %10i    Errors: %10i'%(x,gbe_tx_cnt[x],gbe_tx_errs[x]) 

                print '\tValid Out         cnt: %i'%(p_valid_out_cnt[x])
                print '\tEOF               cnt: %i'%(p_eof_cnt[x])
                print '\tErr               cnt: %i'%(p_err_cnt[x])
                print '\tValid In          cnt: %i'%(p_valid_in_cnt[x])
                print '\tPkt Rdy           cnt: %i'%(p_pkt_rdy_cnt[x])
                print '\tRB Done           cnt: %i'%(p_rb_done_cnt[x])
                print '\tFlushing          cnt: %i'%(flushing_cnt[x])
                
                print '\tTGE Valid         cnt: %i'%(g_valid_cnt[x])
                print '\tTGE EOF           cnt: %i'%(g_eof_cnt[x])
                print '\tTGE send0         cnt: %i'%(g_send0_cnt[x])
                print '\tTGE send1         cnt: %i'%(g_send1_cnt[x])

                print '\tVacc Sync         cnt: %i'%(vacc_sync_cnt[x])
                print '\tVacc Vld          cnt: %i'%(vacc_vld_cnt[x])
                print '\tXeng Sync         cnt: %i'%(xeng_sync_cnt[x])
                print '\tXeng Vld          cnt: %i'%(xeng_vld_cnt[x])
            
            for x in range(xeng.x_per_fpga):
                #for x in range(1):
                #print '\tX engine%i Spectr cnt: %10i    Errors: %10i'%(x,x_cnt[x],x_miss[x]),
                #if x_miss[x]>0: print 'Last missing antenna: %i'%last_miss_ant[x]
                #else: print '' 
                print "\tVector Accum%i    cnt: %10i    Errors: %10i   Status:%10i"%(x,vacc_cnt[x],vacc_errs[x],vacc_status[0])
                print "\tPack Out%i        cnt: %10i    Errors: %10i"%(x,pack_out_cnt[x],pack_out_errs[x])
            print ''

        print 'Time:', time.time() - start_t
        time.sleep(2)

except KeyboardInterrupt:
    exit_clean()
except:
    exit_fail()

