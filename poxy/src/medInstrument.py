#! /usr/bin/env python
"""
Control functions and interface for the Medicina Correlator/SpatialFFT instrument
"""

import katcp,katcp_wrapper,log_handlers,equalization
import xmlParser
import time,struct,numpy,logging,socket,os
import cPickle as pickle

class Instrument:
    fpgas = []
    servers = []
    def __init__(self, config_file, log_handler=None, passive=False):
        """passive: when true, do not attempt communication with FPGAs, useful for reading the config file in RX scripts
        """
        self.log_handler = log_handler

        self.config = xmlParser.xmlObject(config_file).xmlobj #python object containing all the information from the xml file
        self.config_file = config_file

        self.n_feng=len(self.config.fengine)
        self.n_xeng=len(self.config.xengine)
        self.n_seng=len(self.config.sengine)

        #F Engine Parameters
        self.fConf = self.config.fengine
        self.sync_time = self.load_sync()
        self.adc_clk = float(self.config.fengine.adc.clk)
        self.adc_levels_acc_len = int(self.config.fengine.adc.acc_len)
        self.adc_bits = int(self.config.fengine.adc.bits)
        self.fft_shift = int(self.config.fengine.fft_shift)
        self.n_ants_per_feng = int(self.config.fengine.n_ants)
        self.ant_mux = int(self.config.fengine.ant_mux)
        self.feng_clk = self.adc_clk * self.ant_mux
        self.n_ants = int(self.config.fengine.n_ants)*self.n_feng
        self.n_stokes = int(self.config.fengine.n_stokes)
        self.n_bls = self.n_ants * (self.n_ants+1)/2
        self.pols = ['x','y']
        self.n_pols = 2
        self.n_antpols = self.n_ants * self.n_pols
        self.n_chans = int(self.config.fengine.n_chan)
        self.feng_bits = int(self.config.fengine.eq[0].n_bits)

        #X Engine Parameters
        self.xeng_clk = int(self.config.xengine.clk)
        self.xeng_acc_len = int(self.config.xengine.xeng_acc_len)
        self.qdr_acc_len = int(self.config.xengine.qdr_acc_len)
        self.n_accs = self.xeng_acc_len * self.qdr_acc_len
        self.n_xaui = int(self.config.xengine.n_xaui)
        self.x_per_fpga = int(self.config.xengine.x_per_fpga)

        self.bandwidth = self.adc_clk / 2
        self.center_freq = self.config.fengine.obs_freq
        #self.center_freq = self.bandwidth / 2
        self.int_time = self.n_accs * self.n_chans / (self.adc_clk/2)
        self.timestamp_scale_factor = self.bandwidth / self.ant_mux / self.xeng_acc_len
        self.mcnt_scale_factor = self.feng_clk / (len(self.pols) * self.n_ants * self.xeng_acc_len / self.ant_mux)
        #pcnt: the bottom log(self.n_chans) bits are taken off the MCNT and then the remaining MCNT bits are the MSBs of a 40 bit value
        self.pcnt_scale_factor = self.mcnt_scale_factor / 256.
        self.xeng_sample_bits = 32

        #RX/SPEAD Parameters
        self.spead_ip_str = str(self.config.xengine.udp_output.spead_ip)
        self.spead_ip = struct.unpack('>I',socket.inet_aton(self.spead_ip_str))[0]
        self.tx_udp_ip_str = str(self.config.xengine.udp_output.tx_ip)
        self.tx_udp_ip = struct.unpack('>I',socket.inet_aton(self.tx_udp_ip_str))[0]
        self.rx_udp_ip_str = str(self.config.xengine.udp_output.rx_ip)
        self.rx_udp_ip = struct.unpack('>I',socket.inet_aton(self.rx_udp_ip_str))[0]
        self.rx_udp_port = int(self.config.xengine.udp_output.rx_port)
        self.spead_listeners = ([self.config.xengine.udp_output.spead_ip, self.config.xengine.udp_output.rx_port],[self.config.receiver.sengine.spead_ip, self.config.receiver.sengine.rx_port])
        self.seng_spead_rx_ip_str = self.config.receiver.sengine.spead_ip
        self.seng_spead_rx_port = self.config.receiver.sengine.rx_port
       
    def connect_to_servers(self):
        self.fpgas=[katcp_wrapper.FpgaClient(s[0],s[1],timeout=10) for s in self.servers]

    def configure_loggers(self):
        # Setup Message Logging for when things break
        if self.log_handler == None: self.log_handler=log_handlers.DebugLogHandler()
        self.loggers=[logging.getLogger(s[0]) for s in self.servers]
        for logger in (self.loggers): logger.addHandler(self.log_handler)

    def check_katcp_connections(self,verbose=False):
        """Returns a boolean result of a KATCP ping to all connected boards."""
        result = True
        for fn,fpga in enumerate(self.fpgas):
            try:
                fpga.ping()
                if verbose: print 'Connection to %s ok.'%self.servers[fn]
            except:
                if verbose: print 'Failure connecting to %s.'%self.servers[fn]
                result = False
        return result
    
    def __del__(self):
        self.disconnect()

    def disconnect(self):
        """Stop all TCP KATCP links to all FPGAs of a given type defined in the config file."""
        try:
            for fpga in (self.fpgas): fpga.stop()
        except:
            pass

    def disconnect_all(self):
        ##backwards compatibility
        self.disconnect()
    
    def prog(self,ctrl='ctrl_sw'):
        """Programs all the FPGAs."""
        self.deprog()
        time.sleep(.1)
        for fn,fpga in enumerate(self.fpgas):
            print '   Programming %s with bitstream %s' %(self.servers[fn][0],self.bitstream)
            fpga.progdev(self.bitstream)
        # Update the control software after programming
        self.get_ctrl_sw(ctrl=ctrl)

    def deprog(self):
        """Deprograms all the FPGAs."""
        print '   Deprogramming FPGAs'
        for fpga in self.fpgas: fpga.progdev('')
    
    def read_uint(self, register, fpga):
        """Reads a value from register 'register' from an fpga."""
        return fpga.read_uint(register)

    def read_uint_all(self, register):
        return [fpga.read_uint(register) for fpga in self.fpgas]

    def write_int(self,register,value,fpga):
        """Writes to a 32-bit software register to an fpga."""
        fpga.write_int(register,value)

    def write_int_all(self,register,value):
        for fpga in self.fpgas:
            fpga.write_int(register,value)

    def load_sync(self):
        """Determines if a pickle file with the sync_time exists, returns that value else return 0"""
        base_dir = os.path.dirname(self.config_file)
        base_name = os.path.basename(self.config_file)
        pkl_file = base_dir + "/sync_" + base_name.split(".xml")[0]+".pkl"
        sync_time = 0
        try:
            sync_time = pickle.load(open(pkl_file))
        except:
            print "No previous Sync Time found, defaulting to 0 seconds since the Unix Epoch"
        return sync_time

    def initialise_ctrl_sw(self,ctrl='ctrl_sw'):
        """Initialises the control software register to zero."""
        self.ctrl_sw=0
        self.write_ctrl_sw(ctrl=ctrl)

    def write_ctrl_sw(self,ctrl='ctrl_sw'):
        for fpga in self.fpgas: self.write_int(ctrl,self.ctrl_sw,fpga)

    def change_ctrl_sw_bits(self, lsb, msb, val, ctrl='ctrl_sw'):
        num_bits = msb-lsb+1
        if val > (2**num_bits - 1):
            print 'ctrl_sw MSB:', msb
            print 'ctrl_sw LSB:', lsb
            print 'ctrl_sw Value:', val
            raise ValueError("ERROR: Attempting to write value to ctrl_sw which exceeds available bit width")
        # Create a mask which has value 0 over the bits to be changed
        mask = (2**32-1) - ((2**num_bits - 1) << lsb)
        # Remove the current value stored in the ctrl_sw bits to be changed
        self.ctrl_sw = self.ctrl_sw & mask
        # Insert the new value
        self.ctrl_sw = self.ctrl_sw + (val << lsb)
        # Write
        self.write_ctrl_sw(ctrl)

    def get_ctrl_sw(self,ctrl='ctrl_sw'):
        """Updates the ctrl_sw attribute with the current value of the ctrl_sw register"""
        self.ctrl_sw = self.read_uint(ctrl, self.fpgas[0])
        return self.ctrl_sw

    def get_ant_location(self, ant):
        """ Returns the (ffpga_n,feng_input,start_addr) location for a given antenna. Ant is integer, as are all returns."""
        if ant > self.n_ants:
            raise RuntimeError("There is no antenna %i in this design (total %i antennas)."%(ant,self.config['n_ants']))
        ffpga_n = int(ant/self.n_ants_per_feng)
        feng_input = ant % self.n_ants_per_feng
        return (ffpga_n,feng_input)

    def snap(self,fpga,register,chans,ext_trig=False,ext_we=True,ext_ctrl='',capture=True):
        if capture:
            if ext_ctrl != '':
                ctrl_reg = ext_ctrl
            else:
                ctrl_reg = register+'_ctrl'
            # trigger snap
            fpga.write_int(ctrl_reg, 0)
            if ext_trig and ext_we:
                fpga.write_int(ctrl_reg, 7)
            elif ext_we:
                fpga.write_int(ctrl_reg, 5)
            else:
                fpga.write_int(ctrl_reg, 1)
            target_addr = chans-1
            addr = 0
            while (fpga.read_int(register+'_addr') != target_addr):
                time.sleep(0.1)
            #read bram and format as list of uints
        return self.str2ulist(fpga.read(register+'_bram', 4*chans))

    def time_from_mcnt(self,mcnt):
        """Returns the unix time UTC equivalent to the input MCNT."""
        return self.sync_time+float(mcnt)/float(self.mcnt_scale_factor)

    def mcnt_from_time(self,time_seconds):
        """Returns the mcnt of the correlator from a given UTC system time (seconds since Unix Epoch)."""
        return int((time_seconds - self.sync_time)*self.mcnt_scale_factor)

    def str2ulist(self, string):
        list_len = len(string)/4
        unpack_fmt = '>'+'L'*list_len
        return struct.unpack(unpack_fmt, string)
    
    def bit_string(self, val, width):
        bitstring = ''
        for i in range(width):
            bitstring += str((val & (1<<i))>>i)
        return bitstring

    def spead_sync_meta_issue(self):
        """Issues a SPEAD packet to notify the receiver that we've resync'd the system, acc len has changed etc."""
        import spead
        
        tx=spead.Transmitter(spead.TransportUDPtx(self.spead_ip_str, self.rx_udp_port))
        ig=spead.ItemGroup()

        ig.add_item(name='sync_time',id=0x1027,
                    description="Time at which the system was last synchronised in seconds since the Unix Epoch.",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=self.sync_time)

        tx.send_heap(ig.get_heap())

    def spead_sync_meta_issue_all_listeners(self):
        """Issues a SPEAD packet to notify the receiver that we've resync'd the system, acc len has changed etc. Issues SPEAD packets to both X and S engine receivers"""
        import spead

        for l in self.spead_listeners:
            tx = spead.Transmitter(spead.TransportUDPtx(l[0], l[1]))
            ig=spead.ItemGroup()

            ig.add_item(name='sync_time',id=0x1027,
                        description="Time at which the system was last synchronised in seconds since the Unix Epoch.",
                        shape=[],fmt=spead.mkfmt(('f',64)),
                        init_val=self.sync_time)

            # Send
            tx.send_heap(ig.get_heap())

class fEngine(Instrument):
    def __init__(self, config_file, log_handler=None, passive=False, program=False, check_adc=True):
        Instrument.__init__(self, config_file, log_handler=log_handler, passive=passive)
        self.servers=[ [(self.config.fengine['name']),int(self.config.fengine['port'])] ]
        Instrument.fpgas += self.fpgas
        self.bitstream=str(self.config.fengine.bitstream)
        
        if not passive:
            self.connect_to_servers()
            self.configure_loggers()
            time.sleep(.1)
            if not self.check_katcp_connections():
                self.check_katcp_connections(verbose=True)
                raise RuntimeError("Connection to FPGA boards failed.")
            ##For backwards compatibility
            self.ffpgas = self.fpgas
            Instrument.fpgas += self.fpgas
            if program:
                self.prog_feng()
                self.initialise_ctrl_sw()
            else:
                print '   Getting current ctrl_sw state and Checking ADC alignment'
                self.get_ctrl_sw()
                if check_adc:
                    time.sleep(0.5)
                    self.check_adc_sync()
                    time.sleep(0.5)
                    self.check_adc_sync()
                    time.sleep(0.5)
                    self.check_adc_sync()
                    time.sleep(0.5)
                    self.check_adc_sync()
                    time.sleep(0.5)
                    self.check_adc_sync()

    def prog_feng(self):
        self.prog()
        for fn,fpga in enumerate(self.fpgas):
            print   '   Calibrating ADC on %s' %(self.servers[fn][0])
            self.adc_cal(fpga);
            time.sleep(0.05)
            fpga.write_int('adc_spi_ctrl', 1)
            time.sleep(.05)
            fpga.write_int('adc_spi_ctrl', 0)
            time.sleep(.05)
        time.sleep(0.5)
        self.check_adc_sync()
        time.sleep(0.5)
        self.check_adc_sync()
        time.sleep(0.5)
        self.check_adc_sync()
        time.sleep(0.5)
        self.check_adc_sync()
        time.sleep(0.5)
        self.check_adc_sync()

    def check_adc_sync(self):
        for fn,fpga in enumerate(self.fpgas):
            rv = fpga.read_uint('adc_sync_test')
            while (rv&0b111) != 1:
                fpga.write_int('adc_spi_ctrl', 1)
                time.sleep(.05)
                fpga.write_int('adc_spi_ctrl', 0)
                time.sleep(.05)
                print '    ERROR: adc sync test returns %i'%rv
                rv = fpga.read_uint('adc_sync_test')
            print '    SUCCESS: adc sync test returns %i (1 = ADC syncs present & aligned)' %rv


    def set_fft_shift(self, shift):
        self.change_ctrl_sw_bits(0,10,shift)

    def arm_sync(self):
        self.change_ctrl_sw_bits(11,11,0)
        self.change_ctrl_sw_bits(11,11,1)

    def sync_arm_rst(self):
        self.change_ctrl_sw_bits(11,11,0)

    def send_sync(self):
        self.change_ctrl_sw_bits(12,12,0)
        self.change_ctrl_sw_bits(12,12,1)

    def xaui_tx_en(self,val):
        self.change_ctrl_sw_bits(13,13,int(val))

    def debug_signals(self,val):
        self.change_ctrl_sw_bits(14,14,int(val))

    def white_noise(self,val):
        self.change_ctrl_sw_bits(15,15,int(val))

    def white_noise_rst(self,val):
        self.change_ctrl_sw_bits(16,16,int(val))

    def status_flag_rst(self):
        self.change_ctrl_sw_bits(19,19,1)
        self.change_ctrl_sw_bits(19,19,0)

    def use_phase_cal(self, val):
        self.change_ctrl_sw_bits(20,20,int(val))

    def feng_write_ctrl(self, fpga, adc_debug=False, sync_rst=False, sync_arm=False, xaui_rcv_rst=False, white_noise=False, white_noise_rst=False, inter=False, fft_shift=(2**11)-1):
        """Writes a value to the F engine control register."""
        value = inter << 17 | white_noise_rst << 16 | white_noise << 15 | adc_debug << 14 | xaui_rcv_rst << 13 | sync_rst << 12 | sync_arm << 11 | fft_shift 
        self.write_int('ctrl_sw',value,fpga)

    def feng_read_ctrl(self, fpga):
        """Reads and decodes the values from the F engine control register."""
        value = self.read_uint('ctrl_sw',fpga)
        return [{'fft_shift':value&(2**11-1),
                 'sync_arm':bool(value&(1<<11)),
                 'sync_rst':bool(value&(1<<12)),
                 'xaui_rcv_rst':bool(value&(1<<13)),
                 'adc_debug':bool(value&(1<<14)),
                 'white_noise':bool(value&(1<<15)),
                 'white_noise_rst':bool(value&(1<<16)),
                 'interleave':bool(value&(1<<17))}]

    def read_status(self, trig=True, sleeptime=3):
        if trig:
            self.status_flag_rst()
            time.sleep(sleeptime)
        all_values = self.read_uint_all('status')
        return [{
                 'Amp EQ Overflow'               :{'val':bool(value&(1<<1)),  'default':False},
                 'FFT Overflow'                  :{'val':bool(value&(1<<2)),  'default':False},
                 'Phase EQ Overflow'             :{'val':bool(value&(1<<4)),  'default':False},
                 'Sync Gen Armed'                :{'val':bool(value&(1<<6)), 'default':False}} for value in all_values]
    def feng_read_of(self, fpga):
        """Reads and decodes the values from the F engine overflow register."""
        value = self.read_uint('of_reg',fpga)
        return {'X_XAUI':bool(value&(1<<15)),
                'S_XAUI':bool(value&(1<<14)),
                'fft0':bool(value&(1<<13)),
                'fft1':bool(value&(1<<12)),
                'amp0':bool(value&(1<<11)),
                'amp1':bool(value&(1<<10)),
                'amp2':bool(value&(1<<9)),
                'amp3':bool(value&(1<<8)),
                's0':bool(value&(1<<7)),
                's1':bool(value&(1<<6)),
                's2':bool(value&(1<<5)),
                's3':bool(value&(1<<4)),
                'x0':bool(value&(1<<3)),
                'x1':bool(value&(1<<2)),
                'x2':bool(value&(1<<1)),
                'x3':bool(value&(1<<0))}

    def feng_arm(self, spead_update=True):
        """Arms all F engines, records arm time in config file and issues SPEAD update. Returns the UTC time at which the system was sync'd in seconds since the Unix epoch (MCNT=0)"""
        #wait for within 100ms of a half-second, then send out the arm signal.
        ready=(int(time.time()*10)%5)==0
        while not ready:
            ready=(int(time.time()*10)%5)==0
        trig_time=time.time()
        self.arm_sync() #implicitally affects all FPGAs
        self.sync_time=trig_time
        #self.sync_arm_rst()
        self.send_sync()
        if spead_update: self.spead_sync_meta_issue_all_listeners()
        base_dir = os.path.dirname(self.config_file)
        base_name = os.path.basename(self.config_file)
        pkl_file = base_dir + "/sync_" + base_name.split(".xml")[0]+".pkl"
        pickle.dump(self.sync_time, open(pkl_file, "wb"))
        return trig_time

    def adc_cal(self, fpga, calreg='x64_adc_ctrl', debug=False):
        # Some Addresses...
        CTRL       = 0
        DELAY_CTRL = 0x4
        DATASEL    = 0x8
        DATAVAL    = 0xc

        for j in range(0,8):
            if debug: print '%d: '%(j)
            #select bit
            fpga.blindwrite(calreg, '%c%c%c%c'%(0x0,0x0,0x0,j//2), DATASEL)
            #reset dll
            fpga.blindwrite(calreg, '%c%c%c%c'%(0x0,0x0,0x0,(1<<j)), DELAY_CTRL)
            if debug: print "ready\tstable\tval0"
            stable = 1
            prev_val = 0
            while(stable==1):
                fpga.blindwrite(calreg, '%c%c%c%c'%(0x0,0xff,(1<<j),0x0), DELAY_CTRL)
                #val = numpy.fromstring(fpga.read(calreg,4,DATAVAL), count=4, dtype='uint8')
                val    = struct.unpack('>L', (fpga.read(calreg,4,DATAVAL)))[0]
                val0   = (val & ((0xffff)<<(16*(j%2))))>>(16*(j%2))
                stable = (val0&0x1000)>>12
                ready  = (val0&0x2000)>>13
                fclk_sampled = self.bit_string((val0&0x0fff),12)
                if val0 != prev_val and prev_val != 0:
                    break
                prev_val = val0
                if debug: print '%d\t%d\t%s' %(ready, stable, fclk_sampled)
            if debug: print ''
            for i in range(10):
                fpga.blindwrite(calreg, '%c%c%c%c'%(0x0,0xff,(1<<j),0x0), DELAY_CTRL)
                #val = numpy.fromstring(fpga.read(calreg,4,DATAVAL), count=4, dtype='uint8')
                val    = struct.unpack('>L', (fpga.read(calreg,4,DATAVAL)))[0]
                val0   = (val & ((0xffff)<<(16*(j%2))))>>(16*(j%2))
                stable = (val0&0x1000)>>12
                ready  = (val0&0x2000)>>13
                fclk_sampled = self.bit_string((val0&0x0fff),12)
                if debug: print '%d\t%d\t%s' %(ready, stable, fclk_sampled)
            if debug:print ''

    def feng_get_current_mcnt(self, fpga):
        msw = self.read_uint('xengine_mcnt_msb', fpga)
        lsw = self.read_uint('xengine_mcnt_lsb', fpga)
        return ((msw << 32) + lsw)
   
    #def eq_load(self,name,mode,source='config',fmt='poly'):
    #    """Return an EQ object for an equalization block based on config file or a pickle file that has already been generated"""
    #    base_dir = os.path.dirname(self.config_file)
    #    base_name = os.path.basename(self.config_file)
    #    pkl_file = base_dir + "/eq_"+ name + "_" + mode + ".pkl"
    #    if source.startswith('p'):
    #        eqi=equalization.EQ()
    #        eqi.read_pkl(pkl_file)
    #    else:
    #        eq_config=self.eq_get_config(name,mode,fmt=fmt)
    #        init_coeff=numpy.array(eq_config['values'],dtype=float).reshape(self.fConf.n_ants_sp,self.fConf.pols_per_ant, self.fConf.n_chan)
    #        #Construct EQ
    #        eqi=equalization.EQ(mode=eq_config['mode'],nchans=self.n_chans,nants=self.n_ants,npols=self.n_pols,decimation=eq_config['decimation'],fn=pkl_file)
    #        #TODO Set initial values
    #       
    #    return eqi

    def eq_save(self,name,mode,eqi):
        """Save the equalization settings for a specified EQ"""
        base_dir = os.path.dirname(self.config_file)
        base_name = os.path.basename(self.config_file)
        pkl_file = base_dir + "/eq_"+ name + "_" + mode + ".pkl"
        eqi.write_pkl(pkl_file)

    def eq_get_config(self,name,mode,level='base',fmt='poly'):
        """Get the contents of the EQ setting for a given name/mode in the config file"""
        pol_map={'x':0, 'y':1}
        for id, eq in enumerate(self.config.fengine.eq):
            eq_name = eq['name']
            eq_mode = eq['type']
            eq_level = eq['level']
            start_chan = eq['start_chan']
            end_chan = eq['end_chan']
            eq_decimation = eq.decimation
            if (eq_name == name and eq_mode == mode and eq_level==level):
                if fmt == 'poly':
                    coeff = [[0. for x in range(self.fConf.pols_per_ant)] for y in range(self.fConf.n_ants_sp)]
                    for eqi in self.config.fengine.eq[id].eq_poly:
                        eq_val_id = eqi['id']
                        eq_val_pol = eqi['pol']
                        eq_val = str(eqi)
                        poly = eq_val.split(',')
                        poly = map(float, poly)
                        coeff[eq_val_id][pol_map[eq_val_pol]]=numpy.array(poly)
                elif fmt == 'coeff':
                    coeff = numpy.zeros((self.n_antpols,1,self.n_chans/eq_decimation))
                    for eqi in self.config.fengine.eq[id].eq_coeff:
                        eq_val_id = eqi['id']
                        eq_val_pol = eqi['pol']
                        eq_val = str(eqi)
                        eq_val = ' '.join(eq_val.split())
                        equalization = eq_val.split(' ')
                        equalization = map(float, equalization)
                        coeff[eq_val_id][pol_map[eq_val_pol],0,:]=equalization
                return {'values':coeff, 'mode':eq_mode, 'level':eq_level, 'fmt':fmt, 'decimation':eq_decimation, 'start_chan':start_chan, 'end_chan':end_chan}
        return None #if the EQ values don't exist in the config file

    def eq_read_amp(self,eqi,ant,pol='x'):
        """Return the BRAM coefficents for the Amplitude EQ for a given antpol on the F Engine"""
        ANT_REMAP = [0,2,4,6,1,3,5,7] #antenna 0 comes out the fft first, ant 1 comes out third, ant 2 5th, etc...
        # order out it [0,4,1,5,2,6,3,7]
        name='xengine'
        mode='amp'
        ffpga_n,feng_input = self.get_ant_location(ant)
        fpga=self.ffpgas[ffpga_n]
        pol_n = {'x':0,'y':1}[pol]
        phy_input=int((feng_input//(self.ant_mux*2))+(2*pol_n))
        register_name='amp_EQ%i_coeff_bram'%phy_input
        n_coeffs = eqi.nchans/eqi.dec
        start_addr = (ANT_REMAP[ant%(self.ant_mux*2)]) * n_coeffs
        bd=self.ffpgas[ffpga_n].read(register_name,n_coeffs*4,offset=start_addr*4)
        coeffs = self.str2ulist(bd)
        return numpy.array(coeffs)
   
    def eq_read_amp_all(self,eqi):
        """Return an array of all the Amplitude coefficents"""
        coeffs = []
        pol_n=['x','y']
        for ant in range(eqi.nants):
            for pol in pol_n:
                coeffs.append(self.eq_read_amp(eqi,ant,pol))
        return numpy.array(coeffs)

    def eq_write_all_amp(self,send_spead_update=True,verbose=False,use_base=False,use_bandpass=False,use_cal=False):
        """Write to Amplitude BRAM the equalization coefficents for a given antpol on the F Engine"""
        self.eq_amp.build_coeffs(use_base=use_base,use_bandpass=use_bandpass,use_cal=use_cal)
        coeffs = self.eq_amp.coeff['master'].get_real_fp(32,0,signed=False)
        if verbose:
            print 'Coefficient 256 for all pols'
            print coeffs[:,:,256]
            print 'ABS'
            print numpy.abs(coeffs[:,:,256])
        uints = numpy.array(coeffs,dtype=numpy.uint32)
        MAP = [0,4,1,5,2,6,3,7]
        #TODO: we use n_ants_sp here as the number of ants per fpga, and the TOTAL number of ants.
        #In general these are not the same. Fix.
        for fpga in self.fpgas:
            for pn,pol in enumerate(['x','y'][0:self.fConf.pols_per_ant]):
                for eq_subsys in range(self.fConf.n_ants_sp//8):
                    bin_str = ''
                    for ant_mux_index in range(8):
                        offset = self.fConf.n_chan/self.eq_amp.dec*MAP*4 #Offset in bytes, not words
                        if verbose:
                            print '(ant %d%s): Packing %d coefficients to be written to ram %d' %(MAP[ant_mux_index]+8*eq_subsys,pol,len(uints[MAP[ant_mux_index],pn]),eq_subsys)
                        bin_str = bin_str + numpy.array(uints[MAP[ant_mux_index]+8*eq_subsys,pn],dtype='>u4').tostring()
                        if verbose:
                            print 'Coefficients as packed:'
                            print uints[MAP[ant_mux_index]+8*eq_subsys,pn]
                        #for uint in uints[ant,pn]:
                        #    bin_str = bin_str + struct.pack('>L', uint)
                    if verbose:
                        print 'Writing %d coeffs to amp_EQ%d_coeff_bram' %(len(bin_str)/4,eq_subsys)
                    fpga.write('amp_EQ%d_coeff_bram' %eq_subsys, bin_str)
        # Update the pkl file
        self.eq_amp.write_pkl()
        if send_spead_update:
            self.spead_eq_amp_meta_issue()

    #def eq_write_amp_orig(self,eqi,ant,pol='x',verbose=False):
    #    """Write to Amplitude BRAM the equalization coefficents for a given antpol on the F Engine"""
    #    ANT_REMAP = [0,2,4,6,1,3,5,7] #antenna 0 comes out the fft first, ant 1 comes out third, ant 2 5th, etc...
    #    # order out it [0,4,1,5,2,6,3,7]
    #    name='xengine'
    #    mode='amp'
    #    ffpga_n,feng_input = self.get_ant_location(ant)
    #    fpga=self.ffpgas[ffpga_n]
    #    pol_n = {'x':0,'y':1}[pol]
    #    phy_input=int((feng_input//(self.ant_mux*2))+(2*pol_n))
    #    register_name='amp_EQ%i_coeff_bram'%phy_input
    #    n_coeffs = eqi.nchans/eqi.dec
    #    start_addr = (ANT_REMAP[ant%(self.ant_mux*2)]) * n_coeffs
    #    coeffs = eqi.coeff[ant,pol_n,:]
    #    coeff_str=''
    #    for i,v in enumerate(coeffs):
    #        if verbose:
    #            print '''Initialising EQ for antenna %i%c, input %i (register %s)'s index %i to '''%(ant,pol,feng_input,register_name,i+start_addr),v
    #        coeff_str += struct.pack('>L', long(v))
    #    fpga.write(register_name,coeff_str,offset=start_addr*4)

    #def eq_write_amp_all(self,eqi,verbose=False):
    #    """Write all of the Amplitude coefficents"""
    #    pol_n=['x','y']
    #    for ant in range(eqi.nants):
    #        for pol in pol_n:
    #            self.eq_write_amp(eqi,ant,pol,verbose=verbose)
    # 
    #def eq_init_amp(self,source='config',fmt='poly',verbose=False):
    #    """Initialize the Amplitude Equalization coefficents and write values to BRAM"""
    #    name='xengine'
    #    mode='amp'
    #    self.eq_amp=self.eq_load(name,mode,source=source,fmt=fmt)
    #    self.eq_write_amp_all(self.eq_amp,verbose=verbose)
    #    self.eq_save(name,mode,self.eq_amp)

    def eq_init_amp(self,load_pickle=False,verbose=False,use_base=True,use_bandpass=True,use_cal=True,fmt='poly',write=True):
        name='xengine'
        mode = 'amp'
        base_dir = os.path.dirname(self.config_file)
        base_name = os.path.basename(self.config_file)
        pkl_file = base_dir + "/eq_"+ name + "_" + 'amp' + ".pkl"
        if load_pickle:
            try:
                #Try and open the coefficient pickle file
                self.eq_amp = equalization.EQ()
                self.eq_amp.read_pkl(pkl_file)
            except:
                print 'Tried to load amp coeffs from %s and failed' %pkl_file
                print 'Initializing new coefficients'
                self.eq_init_amp(load_pickle=False, verbose=verbose)
        else:
            self.eq_amp = equalization.EQ(mode='amp',nchans=self.fConf.n_chan, nants=self.fConf.n_ants_sp, npols=self.fConf.pols_per_ant, decimation=2, dtype=float, fn=pkl_file)
            # Write the config values
            for eq_level in ['base','bandpass','calibration']:
                eq_config=self.eq_get_config(name,mode,eq_level,fmt=fmt)
                if eq_config is not None: #if the coefficients exist in the config file
                    #Update the coefficients with the contents of the config file
                    if eq_config['fmt'] == 'poly':
                        for ant in range(self.fConf.n_ants_sp):
                            for pol in range(self.fConf.pols_per_ant):
                                self.eq_amp.coeff[eq_level].poly_coeff(ant,pol,eq_config['values'][ant][pol],start_chan=eq_config['start_chan'],end_chan=eq_config['end_chan'])
                    else:
                        self.eq_amp.coeff[eq_level].set_coeffs(eq_config['values'].reshape(self.eq_amp.shape))
        if write:
            # Write coefficients
            self.eq_write_all_amp(verbose=verbose, use_base=use_base, use_bandpass=use_bandpass, use_cal=use_cal)
        # Write pickle file
        self.eq_amp.write_pkl()

    def spead_eq_amp_meta_issue(self):
        """Issues a SPEAD heap for the Amplitude EQ settings."""
        import spead
        for l in self.spead_listeners:
            tx=spead.Transmitter(spead.TransportUDPtx(l[0],l[1]))
            ig=spead.ItemGroup()

            for ant in range(self.fConf.n_ants_sp):
                for pn,pol in enumerate(['x','y'][0:self.fConf.pols_per_ant]):
                    ig.add_item(name="eq_amp_coeff_%i%c"%(ant,pol),id=0x1400+ant*self.n_pols+pn,
                        description="The unitless per-channel digital amplitude scaling factors implemented prior to requantisation, post-FFT, for input %i%c."%(ant,pol),
                        init_val=self.eq_amp.coeff['master'].get_coeffs()[ant,pn,:])

            ig.add_item(name='eq_amp_time',id=0x1500,
                    description="Time at which the amplitude EQ coefficents last changed.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=numpy.ceil(time.time()))
            #Send heap
            tx.send_heap(ig.get_heap())

    def eq_init_phs(self,load_pickle=False,verbose=False, use_base=True,use_bandpass=True,use_cal=True, fmt='poly', write=True):
        name='xengine'
        mode='phs'
        base_dir = os.path.dirname(self.config_file)
        base_name = os.path.basename(self.config_file)
        pkl_file = base_dir + "/eq_"+ name + "_" + 'phs' + ".pkl"
        if load_pickle:
            try:
                #Try and open the coefficient pickle file
                self.eq_phs = equalization.EQ()
                self.eq_phs.read_pkl(pkl_file)
            except:
                print 'Tried to load phase coeffs from %s and failed' %pkl_file
                print 'Initializing new coefficients'
                self.eq_init_phs(load_pickle=False, verbose=verbose)
        else:
            self.eq_phs = equalization.EQ(mode='phs',nchans=self.fConf.n_chan, nants=self.fConf.n_ants_sp, npols=self.fConf.pols_per_ant, decimation=2, dtype=complex, fn=pkl_file)
            # Write the config values
            for eq_level in ['base','bandpass','calibration']:
                eq_config=self.eq_get_config(name,mode,eq_level,fmt=fmt)
                if eq_config is not None: #if the coefficients exist in the config file
                    #Update the coefficients with the contents of the config file
                    if eq_config['fmt'] == 'poly':
                        for ant in range(self.fConf.n_ants_sp):
                            for pol in range(self.fConf.pols_per_ant):
                                self.eq_phs.coeff[eq_level].poly_coeff(ant,pol,eq_config['values'][ant][pol],start_chan=eq_config['start_chan'],end_chan=eq_config['end_chan'])
                    else:
                        self.eq_phs.coeff[eq_level].set_coeffs(eq_config['values'].reshape(self.eq_phs.shape))
        if write:
            # Write coefficients
            self.eq_write_all_phs(verbose=verbose, use_base=use_base, use_bandpass=use_bandpass, use_cal=use_cal)
        # Write pickle file
        self.eq_phs.write_pkl()

    def eq_write_all_phs(self,send_spead_update=True,verbose=False, use_base=False, use_bandpass=False, use_cal=False):
        """Write to Phase BRAM the equalization coefficents for a given antpol on the F Engine"""
        self.eq_phs.build_coeffs(use_base=use_base,use_bandpass=use_bandpass,use_cal=use_cal)
        coeffs = self.eq_phs.coeff['master'].get_complex_fp(16,15)
        if verbose:
            print 'Coefficient 256 for all pols'
            print coeffs[:,:,256]
            print 'ABS'
            print numpy.abs(coeffs[:,:,256])
            print 'PHASE (degrees)'
            print numpy.angle(coeffs[:,:,256])*180./numpy.pi
        uints = ((numpy.array(coeffs.real,dtype=int)&0xffff)<<16)+(numpy.array(coeffs.imag,dtype=int)&0xffff)
        MAP = [0,4,1,5,2,6,3,7]
        #TODO: we use n_ants_sp here as the number of ants per fpga, and the TOTAL number of ants.
        #In general these are not the same. Fix.
        for fpga in self.fpgas:
            for pn,pol in enumerate(['x','y'][0:self.fConf.pols_per_ant]):
                for eq_subsys in range(self.fConf.n_ants_sp//8):
                    bin_str = ''
                    for ant_mux_index in range(8):
                        offset = self.fConf.n_chan/self.eq_phs.dec*MAP*4 #Offset in bytes, not words
                        if verbose:
                            print '(ant %d%s): Packing %d coefficients to be written to ram %d' %(MAP[ant_mux_index]+8*eq_subsys,pol,len(uints[MAP[ant_mux_index],pn]),eq_subsys)
                        bin_str = bin_str + numpy.array(uints[MAP[ant_mux_index]+8*eq_subsys,pn],dtype='>u4').tostring()
                        if verbose:
                            print 'Coefficients as packed:'
                            print uints[MAP[ant_mux_index]+8*eq_subsys,pn]
                        #for uint in uints[ant,pn]:
                        #    bin_str = bin_str + struct.pack('>L', uint)
                    if verbose:
                        print 'Writing %d coeffs to phase_EQ%d_coeff_bram' %(len(bin_str)/4,eq_subsys)
                    fpga.write('phase_EQ%d_coeff_bram' %eq_subsys, bin_str)
        # Update the pkl file
        self.eq_phs.write_pkl()
        if send_spead_update:
            self.spead_eq_phs_meta_issue()
        
    def spead_eq_phs_meta_issue(self):
        """Issues a SPEAD heap for the Phase EQ settings."""
        import spead
        for l in self.spead_listeners:
            tx=spead.Transmitter(spead.TransportUDPtx(l[0],l[1]))
            ig=spead.ItemGroup()

            for ant in range(self.fConf.n_ants_sp):
                for pn,pol in enumerate(['x','y'][0:self.fConf.pols_per_ant]):
                    ig.add_item(name="eq_phs_coeff_%i%c"%(ant,pol),id=0x2400+ant*self.n_pols+pn,
                        description="The per-channel digital phase correction factors implemented prior to requantisation, post-FFT, for input %i%c."%(ant,pol),
                        init_val=self.eq_phs.coeff['master'].get_coeffs()[ant,pn,:])

            ig.add_item(name='eq_phs_time',id=0x2500,
                    description="Time at which the phase EQ coefficents last changed.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=numpy.ceil(time.time()))
            tx.send_heap(ig.get_heap())

class xEngine(Instrument):
    def __init__(self, config_file, log_handler=None, passive=False, program=False):
        Instrument.__init__(self, config_file, log_handler=log_handler, passive=passive)
        self.servers=[ [(self.config.xengine['name']),int(self.config.xengine['port'])] ]
        Instrument.servers += self.servers
        self.bitstream=str(self.config.xengine.bitstream)

        if not passive:
            self.connect_to_servers()
            self.configure_loggers()
            time.sleep(1)
            if not self.check_katcp_connections():
                self.check_katcp_connections(verbose=True)
                raise RuntimeError("Connection to FPGA boards failed.")
            ##For backwards compatibility
            self.xfpgas = self.fpgas
            Instrument.fpgas += self.fpgas
            if program:
                self.prog(ctrl='ctrl')
                self.initialise_ctrl_sw(ctrl='ctrl')
            else:
                print '   Getting current ctrl_sw state'
                self.get_ctrl_sw(ctrl='ctrl')

    def rst_errs(self):
        """ Reset the error counters on the X Engine"""
        self.change_ctrl_sw_bits(8, 8, 1, ctrl='ctrl')
        self.change_ctrl_sw_bits(8, 8, 0, ctrl='ctrl')

    def rst_vacc(self):
        """ Reset the vacc on the X Engine"""
        self.change_ctrl_sw_bits(0, 0, 1, ctrl='ctrl')
        self.change_ctrl_sw_bits(0, 0, 0, ctrl='ctrl')
   
    def enable_10gbe_tx(self):
        """ Enable 10 GbE output"""
        self.change_ctrl_sw_bits(16, 16, 1, ctrl='ctrl')
   
    def xeng_check_xaui_error(self,fpga,verbose=False):
        """Returns a boolean indicating if any X engines have bad incomming XAUI links.
        Checks that data is flowing and that no errors have occured."""
        rv = True
        for x in range(self.n_xaui):
            cnt_check = self.read_uint('xaui_cnt%i'%(x),fpga)
            err_check = self.read_uint('xaui_err%i'%x,fpga)
            if (cnt_check == 0):
                rv=False
                if verbose: print '\tNo F engine data on %s, XAUI port %i.'%(fpga.host,x)
            if (err_check !=0):
                if verbose: print '\tBad F engine data on %s, XAUI port %i.'%(fpga.host,x)
                rv=False
        return rv

    def xeng_snap(self,dev_name,brams,man_trig=False,man_valid=False,wait_period=1,offset=-1,circular_capture=False):
        """Triggers and retrieves data from the a snap block device on all the X engines. Depending on the hardware capabilities, it can optionally capture with an offset. The actual captured length and starting offset is returned with the dictionary of data for each FPGA (useful if you've done a circular capture and can't calculate this yourself).\n
        \tdev_name: string, name of the snap block.\n
        \tman_trig: boolean, Trigger the snap block manually.\n
        \toffset: integer, wait this number of valids before beginning capture. Set to negative value if your hardware doesn't support this or the circular capture function.\n
        \tcircular_capture: boolean, Enable the circular capture function.\n
        \twait_period: integer, wait this number of seconds between triggering and trying to read-back the data.\n
        \tbrams: list, names of the bram components.\n
        \tRETURNS: dictionary with keywords: \n
        \t\tlengths: list of integers matching number of valids captured off each fpga.\n
        \t\toffset: optional (depending on snap block version) list of number of valids elapsed since last trigger on each fpga.
        \t\t{brams}: list of data from each fpga for corresponding bram.\n
        """
        #2010-02-14: Ignore tr_en_cnt if man trig
        #2009-12-14: Expect tr_en_cnt register now if not simple snap block.
        #2009-11-09: Added circular capturing.
        #2009-11-06. Fix to offset triggering.
        if offset >= 0:
            for fpga in self.xfpgas: self.write_int(dev_name+'_trig_offset',offset, fpga)
            #print 'Capturing from snap offset %i'%offset

        #print 'Triggering Capture...',
        for fpga in self.xfpgas:
            self.write_int(dev_name+'_ctrl',(0 + (man_trig<<1) + (man_valid<<2) + (circular_capture<<3)), fpga)
            self.write_int(dev_name+'_ctrl',(1 + (man_trig<<1) + (man_valid<<2) + (circular_capture<<3)), fpga)

        done=False
        start_time=time.time()
        while not (done and (offset>0 or circular_capture)) and ((time.time()-start_time)<wait_period): 
            addr= [self.read_uint(dev_name+'_addr', fpga) for fpga in self.xfpgas]
            done_list=[not bool(i & 0x80000000) for i in addr]
            if (done_list == [True for i in self.servers]): done=True
        bs = [self.read_uint(dev_name+'_addr', fpga) for fpga in self.xfpgas]
        bram_sizes=[i&0x7fffffff for i in bs]
        bram_dmp={'lengths':numpy.add(bram_sizes,1)}
        bram_dmp['offsets']=[0 for f in self.xfpgas]
        #print 'Addr+1:',bram_dmp['lengths']
        for f,fpga in enumerate(self.xfpgas):
            if (bram_sizes[f] != fpga.read_uint(dev_name+'_addr')&0x7fffffff) or bram_sizes[f]==0:
                #if address is still changing, then the snap block didn't finish capturing. we return empty.  
                print "Looks like snap block on %s didn't finish."%self.servers[f]
                bram_dmp['lengths'][f]=0
                bram_dmp['offsets'][f]=0
                bram_sizes[f]=0

        if (circular_capture or (offset>=0)) and not man_trig:
            bd = [self.read_uint(dev_name+'_tr_en_cnt', fpga) for fpga in self.xfpgas]
            bram_dmp['offsets']=numpy.subtract(numpy.add(bd,offset),bram_sizes)
            #print 'Valids since offset trig:',self.read_uint_all(dev_name+'_tr_en_cnt')
            #print 'offsets:',bram_dmp['offsets']
        else: bram_dmp['offsets']=[0 for f in self.xfpgas]
    
        for f,fpga in enumerate(self.xfpgas):
            if (bram_dmp['offsets'][f] < 0):  
                raise RuntimeError('SNAP block hardware or logic failure happened. Returning no data.')
                bram_dmp['lengths'][f]=0
                bram_dmp['offsets'][f]=0
                bram_sizes[f]=0

        for b,bram in enumerate(brams):
            bram_path = dev_name+'_'+bram
            bram_dmp[bram]=[]
            for f,fpga in enumerate(self.xfpgas):
                if (bram_sizes[f] == 0): 
                    bram_dmp[bram].append([])
                else: 
                    bram_dmp[bram].append(fpga.read(bram_path,(bram_sizes[f]+1)*4))
        return bram_dmp

    def xeng_set_qdr_acc_len(self, fpga, n_accs=-1,spead_update=True):
        """Set the QDR Accumulation Length (in # of spectrum accumulations). If not specified, get the config from the config file."""
        if n_accs<0: n_accs=self.qdr_acc_len
        self.write_int('acc_len', n_accs, fpga)
        #self.vacc_sync() #this is needed in case we decrease the accumulation period on a new_acc transition where some vaccs would then be out of sync
        #if spead_update: self.spead_time_meta_issue()

    def xeng_get_current_mcnt(self, fpga):
        return [self.read_uint('xaui_sync_mcnt%i'%(x), fpga) for x in range(self.n_xaui)]

    def xeng_vacc_sync(self,ffpga):
        """Arms all QDR vector accumulators to start accumulating at a given time. If no time is specified, after about a second from now."""
        
        arm_cnt0={}
        ld_cnt0={}
        #for loc_xeng_n in range(self.x_per_fpga):
        for loc_xeng_n in range(1):
            for xf_n,srv in enumerate(self.servers):
                xeng_n = loc_xeng_n * self.x_per_fpga + xf_n
                cnts=self.xfpgas[xf_n].read_uint('vacc_ld_status%i'%loc_xeng_n)
                arm_cnt0[xeng_n]=cnts>>16
                ld_cnt0[xeng_n]=cnts&0xffff

        min_ld_time = 0.5
        mcnt = ffpga.feng_get_current_mcnt(ffpga.ffpgas[0])
        ld_mcnt = int(mcnt + min_ld_time*self.mcnt_scale_factor)
        #print mcnt, ld_mcnt

        for fpga in self.xfpgas:
            self.write_int('vacc_time_lsw',(ld_mcnt&0xffffffff),fpga)
            self.write_int('vacc_time_msw',(ld_mcnt>>32)+1<<31,fpga)
            self.write_int('vacc_time_msw',(ld_mcnt>>32)+0<<31,fpga)

        time.sleep(self.time_from_mcnt(ld_mcnt) - self.time_from_mcnt(mcnt))
        after_mcnt = ffpga.feng_get_current_mcnt(ffpga.ffpgas[0])
        #print 'after_mcnt', after_mcnt
        time.sleep(0.2) #account for a crazy network latency
        
        #for loc_xeng_n in range(self.x_per_fpga):
        for loc_xeng_n in range(1):
            for xf_n,srv in enumerate(self.servers):
                xeng_n = loc_xeng_n * self.x_per_fpga + xf_n
                cnts=self.xfpgas[xf_n].read_uint('vacc_ld_status%i'%loc_xeng_n)
                #print xeng_n, cnts
                if ((cnts>>16)==0): 
                    raise RuntimeError('Xeng %i on %s appears to be held in reset.'%(loc_xeng_n,srv))
                if (arm_cnt0[xeng_n] == (cnts>>16)):
                    raise RuntimeError('Xeng %i on %s did not arm.'%(loc_xeng_n,srv))
                if (ld_cnt0[xeng_n] >= (cnts&0xffff)): 
                    print 'before: %i, target: %i, after: %i'%(mcnt,ld_mcnt,after_mcnt)
                    print 'start: %10.3f, target: %10.3f, after: %10.3f'%(self.time_from_mcnt(mcnt),self.time_from_mcnt(ld_mcnt),self.time_from_mcnt(after_mcnt))
                    if after_mcnt > ld_mcnt: raise RuntimeError('We missed loading the registers by about %4.1f ms.'%((after_mcnt-ld_mcnt)/self.mcnt_scale_factor* 1000))
                    else: raise RuntimeError('Xeng %i on %s did not load correctly for an unknown reason.'%(loc_xeng_n,srv))

    def xeng_check_vacc(self,fpga,verbose=False):
        """Returns boolean pass/fail to indicate if an X engine has vector accumulator errors."""
        rv = True
        for x in range(self.x_per_fpga):
            err_check = self.read_uint('vacc_err_cnt%i'%(x),fpga)
            cnt_check = self.read_uint('vacc_cnt%i'%(x),fpga)
            if err_check !=0:
                if verbose: print '\tVector accumulator errors on %s, X engine %i.'%(fpga.host,x)
                rv=False
            if cnt_check == 0:
                if verbose: print '\tNo vector accumulator data on %s, X engine %i.'%(fpga.host,x)
                rv=False
        return rv

    def xeng_ctrl_set(self,fpga, gbe_out_enable=False, cnt_rst=False, gbe_out_rst=False, vacc_rst=False):
        """Writes a value to the Xengine control register."""
        value = gbe_out_enable<<16 | cnt_rst<<8 | gbe_out_rst<<11 | vacc_rst<<0
        self.write_int('ctrl',value,fpga)

    def xeng_tvg_xeng(self,fpga,mode=0):
        """Select Xengine TVG. Disables VACC (and other) TVGs in the process. Mode can be:
           0: no TVG selected.
           1: select 4-bit counters. Real components count up, imaginary components count down. Bot polarisations have equal values.
           2: Fixed numbers: Pol0real=0.125, Pol0imag=-0.75, Pol1real=0.5, Pol1imag=-0.2
           3: Fixed numbers, cycle through antennas"""
        
        #if mode>4 or mode<0:
        #    raise RuntimeError("Invalid mode selection. Mode must be in range(0,4).")
        #else:
        #    self.write_int('tvg_sel',mode<<3,fpga)
        self.write_int('tvg_sel',mode<<3,fpga)
   
    def xeng_tvg_vacc(self,fpga,enable=False,data_sel=False,valid_sel=False,inject_cnt=False,rst=False):
        value = rst << 14 | inject_cnt << 13 | valid_sel << 11 | data_sel << 10 | enable << 9
        self.write_int('tvg_sel',value,fpga)

    def config_udp_output(self,fpga):
        """Configures the X engine 10GbE output cores."""
        self.write_int('gbe_out_port',self.rx_udp_port,fpga)
        self.write_int('gbe_out_ip',self.rx_udp_ip,fpga)
        self.xeng_ctrl_set(fpga, gbe_out_enable=True)
        for f,fpga in enumerate(self.xfpgas):
            ip = self.tx_udp_ip
            port = self.rx_udp_port
            mac = (2<<40) + (2<<32) + ip
            tap_dev = 'xengtge0'
            fpga.tap_start(tap_dev,'tge_out',mac,ip,port)
            #fpga.tap_start(tap_dev,'tge_out0',mac,ip,port)
            print "  Xengine FPGA:%s is transmitting from IP:%s Port:%i MAC:%i"%(fpga.host,self.tx_udp_ip_str,port,mac)

    def spead_static_meta_issue(self):
        """ Issues the SPEAD metadata packets containing the payload and options descriptors and unpack sequences."""
        import spead
        tx=spead.Transmitter(spead.TransportUDPtx(self.spead_ip_str, self.rx_udp_port))
        ig=spead.ItemGroup()

        ig.add_item(name="adc_clk",id=0x1007,
            description="Clock rate of ADC (samples per second).",
            shape=[],fmt=spead.mkfmt(('u',64)),
            init_val=self.adc_clk)

        ig.add_item(name="n_bls",id=0x1008,
            description="The total number of baselines in the data product.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_bls)

        ig.add_item(name="n_chans",id=0x1009,
            description="The total number of frequency channels present in any integration.",
            shape=[], fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_chans)

        ig.add_item(name="n_ants",id=0x100A,
            description="The total number of dual-pol antennas in the system.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_ants)

        ig.add_item(name="n_xengs",id=0x100B,
            description="The total number of X engines in the system.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_xeng)

        ig.add_item(name="center_freq",id=0x1011,
            description="The center frequency of the DBE in Hz, 64-bit IEEE floating-point number.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.center_freq)

        ig.add_item(name="bandwidth",id=0x1013,
            description="The analogue bandwidth of the digitally processed signal in Hz.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.bandwidth)

        
        #1015/1016 are taken (see time_metadata_issue below)

        ig.add_item(name="fft_shift",id=0x101E,
            description="The FFT bitshift pattern. F-engine correlator internals.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.fft_shift)

        ig.add_item(name="xeng_acc_len",id=0x101F,
            description="Number of spectra accumulated inside X engine. Determines minimum integration time and user-configurable integration time stepsize. X-engine correlator internals.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.xeng_acc_len)

        ig.add_item(name="requant_bits",id=0x1020,
            description="Number of bits after requantisation in the F engines (post FFT and any phasing stages).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.feng_bits)

        ig.add_item(name="rx_udp_port",id=0x1022,
            description="Destination UDP port for X engine output.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.rx_udp_port)

        ig.add_item(name="xeng_rate",id=0x1026,
            description="Target clock rate of processing engines (xeng).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.xeng_clk)

        ig.add_item(name="n_stokes",id=0x1040,
            description="Number of Stokes parameters in output.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_stokes)

        ig.add_item(name="x_per_fpga",id=0x1041,
            description="Number of X engines per FPGA.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.x_per_fpga)

        ig.add_item(name="n_ants_per_xaui",id=0x1042,
            description="Number of antennas' data per XAUI link.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_ants_per_feng)

        ig.add_item(name="ddc_mix_freq",id=0x1043,
            description="Digital downconverter mixing freqency as a fraction of the ADC sampling frequency. eg: 0.25. Set to zero if no DDC is present.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=0.)

        ig.add_item(name="ddc_decimation",id=0x1044,
            description="Frequency decimation of the digital downconverter (determines how much bandwidth is processed) eg: 4",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=1)

        ig.add_item(name="adc_bits",id=0x1045,
            description="ADC quantisation (bits).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.adc_bits)

        ig.add_item(name="scale_factor_timestamp",id=0x1046,
            description="Timestamp scaling factor. Divide the SPEAD data packet timestamp by this number to get back to seconds since last sync.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.pcnt_scale_factor)

        ig.add_item(name="xeng_out_bits_per_sample",id=0x1048,
            description="The number of bits per value of the xeng accumulator output. Note this is for a single value, not the combined complex size.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.xeng_sample_bits)

        
        tx.send_heap(ig.get_heap())
    
    def spead_time_meta_issue(self):
        """Issues a SPEAD packet to notify the receiver that we've resync'd the system, acc len has changed etc."""
        import spead
        
        tx=spead.Transmitter(spead.TransportUDPtx(self.spead_ip_str, self.rx_udp_port))
        ig=spead.ItemGroup()
        
        ig.add_item(name="n_accs",id=0x1015,
                    description="The number of spectra that are accumulated per integration.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=self.n_accs)

        ig.add_item(name="int_time",id=0x1016,
                    description="Approximate (it's a float!) integration time per accumulation in seconds.",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=self.int_time)

        ig.add_item(name='sync_time',id=0x1027,
                    description="Time at which the system was last synchronised in seconds since the Unix Epoch.",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=self.sync_time)

        tx.send_heap(ig.get_heap())

    def spead_obs_meta_issue(self,source,dec,telescope,operator):
        """Issues a SPEAD packet with information on the source and observatory"""
        import spead
        
        tx=spead.Transmitter(spead.TransportUDPtx(self.spead_ip_str, self.rx_udp_port))
        ig=spead.ItemGroup()
      
        ig.add_item(name="source",id=0x2100,
                    description="Observed Source",
                    shape=[],init_val=numpy.array([source]),
                    ndarray=(numpy.str,(1,)))

        ig.add_item(name="dec",id=0x2101,
                    description="Observation declination",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=dec)

        ig.add_item(name='telescope',id=0x2102,
                    description=telescope,
                    shape=[],init_val=numpy.array([telescope]),
                    ndarray=(numpy.str,(1,)))

        ig.add_item(name='operator',id=0x2103,
                    description=operator,
                    shape=[],init_val=numpy.array([operator]),
                    ndarray=(numpy.str,(1,)))
        
        tx.send_heap(ig.get_heap())
    
    def spead_data_descriptor_issue(self):
        """ Issues the SPEAD data descriptors for the HW 10GbE output, to enable receivers to decode the data."""
        import spead
        tx=spead.Transmitter(spead.TransportUDPtx(self.spead_ip_str, self.rx_udp_port))
        ig=spead.ItemGroup()

        if self.xeng_sample_bits != 32: raise RuntimeError("Invalid bitwidth of X engine output. You specified %i, but I'm hardcoded for 32."%self.xeng_sample_bits)

        for x in range(self.n_xeng):
            ig.add_item(name=('timestamp%i'%x), id=0x1600+x,
                description='Timestamp of start of this integration. uint counting multiples of ADC samples since last sync (sync_time, id=0x1027). Divide this number by timestamp_scale (id=0x1046) to get back to seconds since last sync when this integration was actually started. Note that the receiver will need to figure out the centre timestamp of the accumulation (eg, by adding half of int_time, id 0x1016).',
                shape=[], fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                init_val=0)

            ig.add_item(name=("xeng_raw%i"%x),id=(0x1800+x),
                description="Raw data for xengine %i out of %i. Frequency channels are split amongst xengines. Frequencies are distributed to xengines in a round-robin fashion, starting with engine 0. Data from all X engines must thus be combed or interleaved together to get continuous frequencies. Each xengine calculates all baselines (n_bls given by SPEAD ID 0x100B) for a given frequency channel. For a given baseline, -SPEAD ID 0x1040- stokes parameters are calculated (nominally 4 since xengines are natively dual-polarisation; software remapping is required for single-baseline designs). Each stokes parameter consists of a complex number (two real and imaginary unsigned integers)."%(x,self.n_xeng),
                ndarray=(numpy.dtype(numpy.int32),(self.n_chans/self.n_xeng,self.n_bls,self.n_stokes,2)))

        tx.send_heap(ig.get_heap())

class sEngine(Instrument):
    def __init__(self, config_file, log_handler=None, passive=False, program=False):
        Instrument.__init__(self, config_file, log_handler=log_handler, passive=passive)
        self.servers=[ [(self.config.sengine['name']),int(self.config.sengine['port'])] ]
        self.bitstream=str(self.config.sengine.bitstream)
        Instrument.servers += self.servers

        #S Engine Parameters
        self.sConf = self.config.sengine
        self.fConf = self.config.fengine

        self.bandwidth = float(self.fConf.adc.clk) / 2
        self.center_freq = self.fConf.obs_freq
        #self.center_freq = self.bandwidth / 2
        self.int_time = float(self.sConf.int_acc_len * self.sConf.acc_len * self.fConf.n_chan) / (self.bandwidth)
        self.timestamp_scale_factor = self.bandwidth / self.sConf.int_acc_len
        self.pcnt_scale_factor = float(self.fConf.adc.clk / 2. / float(self.sConf.int_acc_len))

        self.x_dim = self.sConf.grid.x_dim
        self.y_dim = self.sConf.grid.y_dim

        self.ant_layout = [self.x_dim,self.y_dim]
        self.image_shape = numpy.array([2*self.x_dim if self.x_dim!=1 else self.x_dim, 2*self.y_dim if self.y_dim!=1 else self.y_dim], dtype=numpy.int32)
        #self.image_shape = [int(dim.data) for dim in self.sConf.grid.dimensions]
        n_beams=1
        for dim in self.image_shape:
            n_beams = n_beams*dim
        self.n_beams = n_beams

        if not passive:
            self.connect_to_servers()
            self.configure_loggers()
            time.sleep(1)
            if not self.check_katcp_connections():
                self.check_katcp_connections(verbose=True)
                raise RuntimeError("Connection to FPGA boards failed.")
            ##For backwards compatibility
            self.sfpgas = self.fpgas
            Instrument.fpgas += self.fpgas
            if program:
                self.prog()
                self.initialise_ctrl_sw()
            else:
                print '   Getting current ctrl_sw state'
                self.get_ctrl_sw()

    def set_x_fft_shift(self,val):
        self.change_ctrl_sw_bits(0,2,val)

    def set_y_fft_shift(self,val):
        self.change_ctrl_sw_bits(3,6,val)

    def xaui_tvg_en(self,val):
        self.change_ctrl_sw_bits(7,7,int(val))

    def set_x_fft_mask(self,val):
        self.change_ctrl_sw_bits(8,11,val)

    def set_y_fft_mask(self,val):
        self.change_ctrl_sw_bits(12,19,val)

    def reset_packet_cnt(self):
        self.change_ctrl_sw_bits(24,24,0)
        self.change_ctrl_sw_bits(24,24,1)
        self.change_ctrl_sw_bits(24,24,0)

    def reset_acc_cnt(self):
        self.change_ctrl_sw_bits(29,29,0)
        self.change_ctrl_sw_bits(29,29,1)
        self.change_ctrl_sw_bits(29,29,0)

    def reset_xaui(self):
        self.change_ctrl_sw_bits(30,30,0)
        self.change_ctrl_sw_bits(30,30,1)
        self.change_ctrl_sw_bits(30,30,0)

    def status_flag_rst(self):
        self.change_ctrl_sw_bits(28,28,0)
        self.change_ctrl_sw_bits(28,28,1)
        self.change_ctrl_sw_bits(28,28,0)

    def set_acc_len(self, acc_len):
        self.write_int_all('acc_len', acc_len)

    def set_acc_scale(self, val):
        self.write_int_all('acc_scale', val)

    def read_status(self, trig=True, sleeptime=3):
        if trig:
            self.status_flag_rst()
            time.sleep(sleeptime)
        all_values = self.read_uint_all('status')
        return [{'XAUI EOF Received'             :{'val':bool(value&(1<<0)),  'default':True},
                 'XAUI Packet Error'             :{'val':bool(value&(1<<1)),  'default':False},
                 'QDR Vacc Error'                :{'val':bool(value&(1<<2)),  'default':False},
                 'QDR New Accumulation'          :{'val':bool(value&(1<<3)),  'default':True},
                 'QDR Input Valid'               :{'val':bool(value&(1<<4)),  'default':True},
                 'QDR Input Sync'                :{'val':bool(value&(1<<5)),  'default':True},
                 'Xaui Buffer Output Sync'       :{'val':bool(value&(1<<6)),  'default':True},
                 'XAUI Buffer Valid Out'         :{'val':bool(value&(1<<7)),  'default':True},
                 'XAUI RX Valid'                 :{'val':bool(value&(1<<8)),  'default':True},
                 'S-Engine Accumulator Overflow' :{'val':bool(value&(1<<9)),  'default':False},
                 'S-Engine Y-FFT Overflow'       :{'val':bool(value&(1<<10)), 'default':False},
                 'S-Engine X-FFT Overflow'       :{'val':bool(value&(1<<11)), 'default':False}} for value in all_values]

    def config_udp_output(self,fpga):
        """Configures the X engine 10GbE output cores."""
        self.write_int('gbe_out_port',self.sengine.udp_output.rx_port,fpga)
        self.write_int('gbe_out_ip',self.sengine.udp_output.rx_ip,fpga)
        for f,fpga in enumerate(self.fpgas):
            ip = self.sengine.udp_output.tx_ip
            port = self.sengine.udp_output.rx_port
            mac = (2<<40) + (2<<32) + ip
            tap_dev = 'sengtge0'
            fpga.tap_start(tap_dev,'tge_out',mac,ip,port)
            #fpga.tap_start(tap_dev,'tge_out0',mac,ip,port)
            print "  S-Engine FPGA:%s is transmitting from IP:%s Port:%i MAC:%i"%(fpga.host,ip,port,mac)

    def spead_static_meta_issue(self):
        """ Issues the SPEAD metadata packets containing the payload and options descriptors and unpack sequences."""
        import spead
        tx=spead.Transmitter(spead.TransportUDPtx(self.config.receiver.sengine.spead_ip, self.config.receiver.sengine.rx_port))
        ig=spead.ItemGroup()

        ig.add_item(name="adc_clk",id=0x1007,
            description="Clock rate of ADC (samples per second).",
            shape=[],fmt=spead.mkfmt(('u',64)),
            init_val=self.fConf.adc.clk)

        ig.add_item(name="n_beams",id=0x2008,
            description="The total number of pixels in the data product.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_beams)

        ig.add_item(name="n_chans",id=0x1009,
            description="The total number of frequency channels present in any integration.",
            shape=[], fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.fConf.n_chan)

        ig.add_item(name="n_ants",id=0x2000,
            description="The total number of SINGLE OR DUAL-POL antennas in the system.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.n_ants)

        ig.add_item(name="is_dual_pol",id=0x2001,
            description="One if the data recorded comes from a dual pol receiver. Zero otherwise.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=int(self.sConf.is_dual_pol))

        ig.add_item(name="n_sengs",id=0x200B,
            description="The total number of S engines in the system.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.n_seng)

        ig.add_item(name="center_freq",id=0x1011,
            description="The center frequency of the DBE in Hz, 64-bit IEEE floating-point number.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.center_freq)

        ig.add_item(name="bandwidth",id=0x1013,
            description="The analogue bandwidth of the digitally processed signal in Hz.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.bandwidth)

        
        #1015/1016 are taken (see time_metadata_issue below)

        ig.add_item(name="fft_shift",id=0x101E,
            description="The FFT bitshift pattern. F-engine correlator internals.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.fConf.fft_shift)

        ig.add_item(name="seng_acc_len",id=0x201F,
            description="Number of spectra accumulated inside S engine. Determines minimum integration time and user-configurable integration time stepsize. S-engine correlator internals.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.int_acc_len)

        ig.add_item(name="requant_bits",id=0x1020,
            description="Number of bits after requantisation in the F engines (post FFT and any phasing stages).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.bits)

        ig.add_item(name="seng_rx_udp_port",id=0x2022,
            description="Destination UDP port for S engine output.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.udp_output.rx_port)

        ig.add_item(name="seng_rate",id=0x2026,
            description="Target clock rate of processing engines (seng).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.clk)

        ig.add_item(name="n_stokes",id=0x1040,
            description="Number of Stokes parameters in output.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.n_stokes)

        ig.add_item(name="s_per_fpga",id=0x2041,
            description="Number of S engines per FPGA.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.s_per_fpga)

        #TODO integrate this stuff into the config file rather than hard-coding
        ig.add_item(name="ddc_mix_freq",id=0x1043,
            description="Digital downconverter mixing freqency as a fraction of the ADC sampling frequency. eg: 0.25. Set to zero if no DDC is present.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=0.)

        ig.add_item(name="ddc_decimation",id=0x1044,
            description="Frequency decimation of the digital downconverter (determines how much bandwidth is processed) eg: 4",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=1)

        ig.add_item(name="adc_bits",id=0x1045,
            description="ADC quantisation (bits).",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.fConf.adc.bits)

        ig.add_item(name="scale_factor_timestamp",id=0x1046,
            description="Timestamp scaling factor. Divide the SPEAD data packet timestamp by this number to get back to seconds since last sync.",
            shape=[],fmt=spead.mkfmt(('f',64)),
            init_val=self.pcnt_scale_factor)

        ig.add_item(name="seng_out_bits_per_sample",id=0x1148,
            description="The number of bits per value of the s-eng accumulator output.",
            shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
            init_val=self.sConf.bits_out)

        tx.send_heap(ig.get_heap())
    
    def spead_dynamic_meta_issue(self):
        """Issues a SPEAD packet to notify the receiver that we've resync'd the system, acc len has changed etc."""
        import spead
        
        tx=spead.Transmitter(spead.TransportUDPtx(self.config.receiver.sengine.spead_ip, self.config.receiver.sengine.rx_port))
        ig=spead.ItemGroup()
        
        ig.add_item(name="n_accs",id=0x1015,
                    description="The number of spectra that are accumulated per integration.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=self.sConf.acc_len)

        ig.add_item(name="int_time",id=0x1016,
                    description="Approximate (it's a float!) integration time per accumulation in seconds.",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=self.int_time)

        ig.add_item(name='sync_time',id=0x1027,
                    description="Time at which the system was last synchronised in seconds since the Unix Epoch.",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=self.load_sync())

        ig.add_item(name='x_fft_shift',id=0x1150,
                    description="FFT shift value controlling shifting in the first (x) dimension of the spatial FFT.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=self.sConf.acc_scale)

        ig.add_item(name='y_fft_shift',id=0x1151,
                    description="FFT shift value controlling shifting in the second (y) dimension of the spatial FFT.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=self.sConf.y_fft_shift)

        ig.add_item(name='acc_scale_factor',id=0x1152,
                    description="Scale factor used to convert from 36 bit spatial FFT output to 16bit QDR vacc input.",
                    shape=[],fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                    init_val=self.sConf.acc_scale)

        tx.send_heap(ig.get_heap())

    def spead_obs_meta_issue(self,source,dec,telescope,operator):
        """Issues a SPEAD packet with information on the source and observatory"""
        import spead
        
        tx=spead.Transmitter(spead.TransportUDPtx(self.config.receiver.sengine.spead_ip, self.config.receiver.sengine.rx_port))
        ig=spead.ItemGroup()
      
        ig.add_item(name="source",id=0x2100,
                    description="Observed Source",
                    shape=[],init_val=numpy.array([source]),
                    ndarray=(numpy.str,(1,)))

        ig.add_item(name="dec",id=0x2101,
                    description="Observation declination",
                    shape=[],fmt=spead.mkfmt(('f',64)),
                    init_val=dec)

        ig.add_item(name='telescope',id=0x2102,
                    description=telescope,
                    shape=[],init_val=numpy.array([telescope]),
                    ndarray=(numpy.str,(1,)))

        ig.add_item(name='operator',id=0x2103,
                    description=operator,
                    shape=[],init_val=numpy.array([operator]),
                    ndarray=(numpy.str,(1,)))
        
        tx.send_heap(ig.get_heap())

    def spead_seng_data_descriptor_issue(self):
        """ Issues the SPEAD data descriptors for the HW 10GbE output, to enable receivers to decode the data."""
        import spead
        tx=spead.Transmitter(spead.TransportUDPtx(self.config.receiver.sengine.spead_ip, self.config.receiver.sengine.rx_port))
        ig=spead.ItemGroup()

        if self.sConf.bits_out != 32: raise RuntimeError("Invalid bitwidth of S engine output. You specified %i, but I'm hardcoded for 32."%self.sConf.bits_out)

        for x in range(self.n_seng):
            ig.add_item(name=('timestamp%i'%x), id=0x1700+x,
                description='Timestamp of start of this integration. uint counting multiples of ADC samples since last sync (sync_time, id=0x1027). Divide this number by timestamp_scale (id=0x1046) to get back to seconds since last sync when this integration was actually started. Note that the receiver will need to figure out the centre timestamp of the accumulation (eg, by adding half of int_time, id 0x1016).',
                shape=[], fmt=spead.mkfmt(('u',spead.ADDRSIZE)),
                init_val=0)

            ig.add_item(name=("seng_raw%i"%x),id=(0x1900+x),
                description="Raw data for S-engine %i out of %i. Frequency channels are split amongst s-engines. Frequencies are distributed to xengines in contiguous blocks, starting with engine 0. Data from all S engines must thus be combined to cover the whole observed band. Each sengine calculates all beams for a given frequency channel. For a given beam, -SPEAD ID 0x1040- stokes parameters are calculated. Each stokes parameter consists of a single uint, which represents acculumated power."%(x,self.n_seng),
                ndarray=(numpy.dtype(numpy.uint32),(self.n_chans/self.n_seng,self.image_shape[1],self.image_shape[0],self.sConf.n_stokes)))

        tx.send_heap(ig.get_heap())
