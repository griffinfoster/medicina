import bitOperations
import numpy as np
import struct as s
import time

class SnapBlock():
    def __init__(self,fpgas,ram_path='',ctrl_path='',addr_path='',depth='',input_sel='',sync_sel='',sync_delay='',quiet=False):
        self.bram = ram_path
        self.ctrl = ctrl_path
        self.depth = depth
        self.addr = addr_path
        self.fpgas = fpgas
        self.input_sel = input_sel
        self.sync_sel = sync_sel
        self.sync_delay = sync_delay
        self.quiet = quiet
    def new_capture(self,sw_trig=False):
        for fpga in self.fpgas:
            #fpga.blindwrite(self.ctrl,'\x00\x00\x00\x00')
            #fpga.blindwrite(self.ctrl,s.pack('>L',1+(int(sw_trig)*2)+4))
            fpga.write_int(self.ctrl,0)
            fpga.write_int(self.ctrl,5)
            while (fpga.read_int(self.addr)!=(self.depth-1)):
                print 'waiting for data...'
                time.sleep(0.01)
        return [fpga.read(self.bram,self.depth*4) for fpga in self.fpgas]
    def set_input(self,sel):
        for fn,fpga in enumerate(self.fpgas):
            if not self.quiet:
                print "Setting input register (%s) of FPGA %d to value %d" %(self.input_sel,fn,sel)
            #fpga.blindwrite(self.input_sel,s.pack('>L',sel))
            fpga.write_int(self.input_sel,sel)
    def set_sync(self,sel):
        for fn,fpga in enumerate(self.fpgas):
            if not self.quiet:
                print "Setting sync register (%s) of FPGA %d to value %d" %(self.sync_sel,fn,sel)
            #fpga.blindwrite(self.sync_sel,s.pack('>L',sel))
            fpga.write_int(self.sync_sel,sel)
    def set_sync_delay(self,sel):
        for fpga in self.fpgas:
            fpga.blindwrite(self.sync_sel,s.pack('>L',sel))

class Spectras18(SnapBlock):
    def __init__(self,fpgas,ram_path='',ctrl_path='',addr_path='',depth=1024,input_sel='',sync_sel='',sync_delay='',n_chans=256,n_ants=32,n_pols=1,sync_index=0, quiet=False):
        SnapBlock.__init__(self,fpgas,ram_path=ram_path,ctrl_path=ctrl_path,addr_path=addr_path,depth=1024,input_sel=input_sel,sync_sel=sync_sel,sync_delay=sync_delay,quiet=quiet)
        self.n_chans = n_chans
        self.depth = depth
        self.n_ants = n_ants
        self.n_pols = n_pols
        self.n_fpgas = len(fpgas)
        self.sync_index = sync_index
        self.n_snaps = self.n_pols*self.n_ants*self.n_chans/self.depth
        self.chans_per_snap = self.depth/self.n_chans
        #self.snap_sel_offset = (self.n_snaps//2)
    def get_spectras(self):
        ANT_MUX_MAP = [0,4,1,5,2,6,3,7]
        data = np.array([], dtype=complex)
        for sel in range(self.n_snaps):
            self.set_input(4*self.sync_index+(sel//(8/self.chans_per_snap)))
            self.set_sync(self.sync_index + ((sel%(8/self.chans_per_snap))<<3))
            data = np.append(data,self.unpack(self.new_capture()))
        data=data.reshape(self.n_fpgas,self.n_ants,self.n_pols,self.n_chans)
        data_reordered = np.zeros_like(data)
        for ant_block in range(self.n_ants//8):
            for block_index in range(8):
                data_reordered[:,8*ant_block+ANT_MUX_MAP[block_index],:,:] = data[:,8*ant_block+block_index,:,:]
        return data_reordered
    def unpack(self,data):
        data_list = [np.array(s.unpack('>%dh'%(2*self.depth),data[fn])) for fn in range(self.n_fpgas)]
        return [data_list[fn][0::2]+1j*data_list[fn][1::2] for fn in range(self.n_fpgas)]

class SpectrasQuant(SnapBlock):
    def __init__(self,fpgas,ram_path='',ctrl_path='',addr_path='',depth=1024,input_sel='',sync_sel='',sync_delay='',n_chans=256,n_ants=32,n_pols=1,sync_index=0,ants_per_word=4,quiet=False, data_index=0):
        SnapBlock.__init__(self,fpgas,ram_path=ram_path,ctrl_path=ctrl_path,addr_path=addr_path,depth=1024,input_sel=input_sel,sync_sel=sync_sel,sync_delay=sync_delay,quiet=quiet)
        self.depth = depth
        self.n_chans = n_chans
        self.n_ants = n_ants
        self.n_pols = n_pols
        self.n_fpgas = len(fpgas)
        self.ants_per_word = ants_per_word
        self.sync_index = sync_index
        self.n_snaps = self.n_pols*self.n_ants*self.n_chans/(self.depth*self.ants_per_word)
        self.chans_per_snap = self.depth/self.n_chans
        self.data_index=data_index
    def get_spectras(self):
        data = np.array([])
        for sel in range(self.n_snaps):
            self.set_input(self.data_index+(sel//8))
            self.set_sync(self.sync_index + ((sel%(8/self.chans_per_snap))<<3))
            data = np.append(data,self.unpack(self.new_capture()))
        data = data.reshape(self.n_fpgas,self.n_ants,self.n_pols,self.n_chans)
        reordered_data = np.zeros_like(data)
        ANT_MUX_MAP=np.array([0,4,1,5,2,6,3,7])
        ANT_CRAM_MAP=np.array([0,8,16,24])
        reorder_map = np.array([])
        for j in range(8):
            reorder_map = np.append(reorder_map,ANT_CRAM_MAP+ANT_MUX_MAP[j])
        for ant in range(32):
            reordered_data[:,reorder_map[ant],:,:] = data[:,ant,:,:]
        return reordered_data 
    def unpack(self,data):
        word_width = int(32/self.ants_per_word)
        r_i_width = int(word_width/2)
        mask = (2**word_width)-1
        data_list = [np.array(s.unpack('>%dL'%self.depth,data[fn])) for fn in range(self.n_fpgas)]
        ret_data_all_fpgas = np.array([])
        for fn in range(self.n_fpgas):
            ret_data = np.array([])
            for i in range(self.ants_per_word):
                ret_data = np.append(ret_data,bitOperations.uint2cplx((data_list[fn]&(mask<<((self.ants_per_word-1-i)*word_width)))>>((self.ants_per_word-1-i)*word_width),r_i_width))
            ret_data_all_fpgas = np.append(ret_data_all_fpgas,ret_data)
        return ret_data_all_fpgas


class SpectrasTranspose(SnapBlock):
    def __init__(self,fpgas,ram_path='',ctrl_path='',addr_path='',depth=1024,input_sel='',sync_sel='',sync_delay='',n_chans=256,n_ants=32,n_pols=1,sync_index=0,ants_per_word=4,delay_path='',int_len=128,quiet=False):
        SnapBlock.__init__(self,fpgas,ram_path=ram_path,ctrl_path=ctrl_path,addr_path=addr_path,depth=1024,input_sel=input_sel,sync_sel=sync_sel,sync_delay=sync_delay,quiet=quiet)
        self.delay_path = delay_path
        self.n_chans = n_chans
        self.n_ants = n_ants
        self.n_pols = n_pols
        self.n_fpgas = len(fpgas)
        self.ants_per_word = ants_per_word
        self.sync_index = sync_index
        self.int_len = int_len
        self.n_snaps = self.n_pols*self.n_ants*self.n_chans*self.int_len/(self.depth*self.ants_per_word)
    def get_spectras(self):
        data = np.array([])
        for sel in range(self.n_snaps):
            print ' Capture %d of %d' %(sel,self.n_snaps)
            self.set_input(14)
            if sel==0:
                self.set_sync(self.sync_index+((1024*sel+1)<<4))
            else:
                self.set_sync(self.sync_index+(1024*sel<<4))

            data = np.append(data,self.unpack(self.new_capture()))
        return data.flatten()
    def unpack(self,data):
        word_width = int(32/self.ants_per_word)
        mask = (2**word_width)-1
        data_list = [np.array(s.unpack('>%dB'%(self.depth*self.ants_per_word),data[fn])) for fn in range(self.n_fpgas)]
        ret_data = np.array([])
        for fn in range(self.n_fpgas):
            ret_data = np.append(ret_data,bitOperations.uint2cplx(data_list[fn],word_width))
        return ret_data




    



    

