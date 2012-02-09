"""Client for communicating with a ROACH board over KATCP.

   @author Simon Cross <simon.cross@ska.ac.za>
   @modified Jason Manley <jason_manley@hotmail.com>
   @Revised 2009/12/01 to include print 10gbe core details.
   @Revised 2010/01/07 to include bulkread
   @Revised 2010/06/28 to include qdr stuff
   """

import struct, re, threading, socket, select, traceback, logging, sys, time, os

from katcp import *
log = logging.getLogger("katcp")


class FpgaClient(BlockingClient):
    """Client for communicating with a ROACH board.

       Notes:
         - All commands are blocking.
         - If there is no response to an issued command, an exception is thrown
           with appropriate message after a timeout waiting for the response.
         - If the TCP connection dies, an exception is thrown with an
           appropriate message.
       """

    def __init__(self, host, port=7147, tb_limit=20, timeout=10.0, logger=log):
        """Create a basic DeviceClient.

           @param self  This object.
           @param host  String: host to connect to.
           @param port  Integer: port to connect to.
           @param tb_limit  Integer: maximum number of stack frames to
                            send in error traceback.
           @param timeout  Float: seconds to wait before timing out on
                           client operations.
           @param logger Object: Logger to log to.
           """
        super(FpgaClient, self).__init__(host, port, tb_limit=tb_limit,timeout=timeout, logger=logger)
        self.host=host
        self._timeout = timeout
        self.start(daemon=True)

    def _request(self, name, *args):
        """Make a blocking request and check the result.
        
           Raise an error if the reply indicates a request failure.

           @param self  This object.
           @param name  String: name of the request message to send.
           @param args  List of strings: request arguments.
           @return  Tuple: containing the reply and a list of inform messages.
           """
        request = Message.request(name, *args)
        reply, informs = self.blocking_request(request,keepalive=True)

        if reply.arguments[0] != Message.OK:
            self._logger.error("Request %s failed.\n  Request: %s\n  Reply: %s."
                    % (request.name, request, reply))

            raise RuntimeError("Request %s failed.\n  Request: %s\n  Reply: %s."
                    % (request.name, request, reply))
        return reply, informs

    def listdev(self):
        """Return a list of register / device names.

           @param self  This object.
           @return  A list of register names.
           """
        reply, informs = self._request("listdev")
        return [i.arguments[0] for i in informs]

    def listbof(self):
        """Return a list of executable files.

           @param self  This object.
           @return  List of strings: list of executable files.
           """
        reply, informs = self._request("listbof")
        return [i.arguments[0] for i in informs]

    def listcmd(self):
        """Return a list of available commands. this should not be made  
           available to the user, but can be used internally to query if a
           command is supported.

           @todo  Implement or remove.
           @param self  This object.
           """
        raise NotImplementedError("LISTCMD not implemented by client.")

    def progdev(self, device_name):
        """Return a status string for the given device.

           @param self  This object.
           @param device_name  String: name of the device.
           @return  String: device status.
           """
        reply, informs = self._request("progdev", device_name)
        return reply.arguments[0]

    def config_10gbe_core(self,device_name,mac,ip,port,arp_table,gateway=1):
        """Hard-codes a 10GbE core with the provided params. It does a blindwrite, so there is no verifcation that configuration was successful (this is necessary since some of these registers are set by the fabric depending on traffic received).

           @param self  This object.
           @param device_name  String: name of the device.
           @param mac   integer: MAC address, 48 bits.
           @param ip    integer: IP address, 32 bits.
           @param port  integer: port of fabric interface (16 bits).
           @param arp_table  list of integers: MAC addresses (48 bits ea).
           """
        #assemble struct for header stuff...
        #0x00 - 0x07: My MAC address
        #0x08 - 0x0b: Not used
        #0x0c - 0x0f: Gateway addr
        #0x10 - 0x13: my IP addr
        #0x14 - 0x17: Not assigned
        #0x18 - 0x1b: Buffer sizes
        #0x1c - 0x1f: Not assigned
        #0x20       : soft reset (bit 0)
        #0x21       : fabric enable (bit 0)
        #0x22 - 0x23: fabric port 
        
        #0x24 - 0x27: XAUI status (bit 2,3,4,5=lane sync, bit6=chan_bond)
        #0x28 - 0x2b: PHY config
 
        #0x28       : RX_eq_mix
        #0x29       : RX_eq_pol
        #0x2a       : TX_preemph
        #0x2b       : TX_diff_ctrl

        #0x1000     : CPU TX buffer
        #0x2000     : CPU RX buffer
        #0x3000     : ARP tables start
        
        ctrl_pack=struct.pack('>QLLLLLLBBH',mac, 0, gateway, ip, 0, 0, 0, 0, 1, port)
        arp_pack=struct.pack('>256Q',*arp_table)
        self.blindwrite(device_name,ctrl_pack,offset=0)
        self.write(device_name,arp_pack,offset=0x3000)

    def tap_start(self, tap_dev, device, mac, ip, port):
        """Program a 10GbE device and start the TAP driver.

            @param self  This object.
            @param device  String: name of the device (as in simulink name).
            @param tap_dev  String: name of the tap device (a Linux identifier). If you want to destroy a device later, you need to use this name.
            @param mac   integer: MAC address, 48 bits.
            @param ip    integer: IP address, 32 bits.
            @param port  integer: port of fabric interface (16 bits).

            Please note that the function definition changed from corr-0.4.0 to corr-0.4.1 to include the tap_dev identifier.
           """
        if len(tap_dev) > 8: raise RuntimeError("Tap device identifier must be shorter than 9 characters. You specified %s for device %s."%(tap_dev,device))

        ip_1 = (ip/(2**24))
        ip_2 = (ip%(2**24))/(2**16)
        ip_3 = (ip%(2**16))/(2**8)
        ip_4 = (ip%(2**8))
        mac0 = (mac & ((1<<48)-(1<<40))) >> 40
        mac1 = (mac & ((1<<40)-(1<<32))) >> 32
        mac2 = (mac & ((1<<32)-(1<<24))) >> 24
        mac3 = (mac & ((1<<24)-(1<<16))) >> 16
        mac4 = (mac & ((1<<16)-(1<<8))) >> 8
        mac5 = (mac & ((1<<8)-(1<<0))) >> 0

        mac_str= "%02X:%02X:%02X:%02X:%02X:%02X"%(mac0,mac1,mac2,mac3,mac4,mac5)
        ip_str="%i.%i.%i.%i"%(ip_1,ip_2,ip_3,ip_4)
        port_str = "%i"%port
 
        self._logger.info("Starting tgtap driver instance for %s: %s %s %s %s %s"%("tap-start", tap_dev, device, ip_str, port_str, mac_str))
        reply, informs = self._request("tap-start", tap_dev, device, ip_str, port_str, mac_str)
        if reply.arguments[0]=='ok': return
        else: raise RuntimeError("Failure starting tap device %s with mac %s, %s:%s"%(device,mac_str,ip_str,port_str))

    def tap_stop(self, device):
        """Stop a TAP driver.

           @param self  This object.
           @param device  String: name of the device you want to stop.
        """

        reply, informs = self._request("tap-stop", device)
        if reply.arguments[0]=='ok': return
        else: raise RuntimeError("Failure stopping tap device %s."%(device))

    def upload_bof(self, bof_file, port=7148):
        """Upload a BORPH file to the ROACH board for execution. 
           @param self  This object.
           @param bof_file  param 
           @param port   Optionally specify the port to use for uploading. Otherwise, default to 7148.
           @return  nothing.
        """
        #NOT YET IMPLEMENTED
        #need to register a new handler for uploadbof informs before sending data, so that we know when the transfer is complete.

        #filesize=os.path.getsize(bof_file)
        #filename=bof_file.split("/")[-1]
        #reply, informs = self._request("uploadbof",str(port),filename,str(filesize))
        #if reply.arguments[0]=='ok':
        #    uploadsocket=socket.socket()
        #    uploadsocket.connect((self.host,port))
        #    uploadsocket.send(open(bof_file).read())
        #    return
        #else: raise RuntimeError("Failure requesting storage of file %s."%(filename))

    def status(self):
        """Return the status of the FPGA.
           @param self  This object.
           @return  String: FPGA status.
           """
        reply, informs = self._request("status")
        return reply.arguments[1]
    
    def ping(self):
        """Tries to ping the FPGA.
           @param self  This object.
           @return  boolean: ping result.
           """
        reply, informs = self._request("watchdog")
        if reply.arguments[0]=='ok': return True
        else: return False

    def execcmd(self, string):
        """Not yet supported.

           @todo  Implement or remove.
           @param self  This object.
           """
        raise NotImplementedError(
            "EXEC not implemented by client.")

    def bulkread(self, device_name, size, offset=0):
        """Return size_bytes of binary data with carriage-return escape-sequenced.
           Uses much fast bulkread katcp command which returns data in pages 
           using informs rather than one read reply, which has significant buffering
           overhead on the ROACH.

           @param self  This object.
           @param device_name  String: name of device / register to read from.
           @param size  Integer: amount of data to read (in bytes).
           @param offset  Integer: offset to read data from (in bytes).
           @return  Bindary string: data read.
           """
        reply, informs = self._request("bulkread", device_name, str(offset), str(size))
        return ''.join([i.arguments[0] for i in informs])

    def read(self, device_name, size, offset=0):
        """Return size_bytes of binary data with carriage-return
           escape-sequenced.

           @param self  This object.
           @param device_name  String: name of device / register to read from.
           @param size  Integer: amount of data to read (in bytes).
           @param offset  Integer: offset to read data from (in bytes).
           @return  Bindary string: data read.
           """
        reply, informs = self._request("read", device_name, str(offset),
            str(size))
        return reply.arguments[1]

    def read_dram(self, size, offset=0,verbose=False):
        """Reads data from a ROACH's DRAM. Reads are done up to 1MB at a time.
           The 64MB indirect address register is automatically incremented as necessary.
           It returns a string, as per the normal 'read' function.
           ROACH has a fixed device name for the DRAM (dram memory).
           Uses bulkread internally.

           @param self    This object.
           @param size    Integer: amount of data to read (in bytes).
           @param offset  Integer: offset to read data from (in bytes).
           @return  Binary string: data read.
        """
        #Modified 2010-01-07 to use bulkread.
        data=[]
        n_reads=0
        last_dram_page = -1

        dram_indirect_page_size=(64*1024*1024)
        #read_chunk_size=(1024*1024)
        if verbose: print 'Reading a total of %8i bytes from offset %8i...'%(size,offset)

        while n_reads < size:
            dram_page=(offset+n_reads)/dram_indirect_page_size
            local_offset = (offset+n_reads)%(dram_indirect_page_size)
            #local_reads = min(read_chunk_size,size-n_reads,dram_indirect_page_size-(offset%dram_indirect_page_size))
            local_reads = min(size-n_reads,dram_indirect_page_size-(offset%dram_indirect_page_size))
            if verbose: print 'Reading %8i bytes from indirect address %4i at local offset %8i...'%(local_reads,dram_page,local_offset)
            if last_dram_page != dram_page: 
                self.write_int('dram_controller',dram_page)
                last_dram_page = dram_page
            local_data=(self.bulkread('dram_memory',local_reads,local_offset))
            data.append(local_data)
            #print 'done'
            n_reads += local_reads
        return ''.join(data)

    def write(self, device_name, data, offset=0):
        """Should issue a read command after the write and compare return to
           the string argument to confirm that data was successfully written.

           Throw exception if not match. (alternative command 'blindwrite' does
           not perform this confirmation).

           @see blindwrite
           @param self  This object.
           @param device_name  String: name of device / register to write to.
           @param data  Byte string: data to write.
           @param offset  Integer: offset to write data to (in bytes)
           """
        self.blindwrite(device_name, data, offset)
        new_data = self.read(device_name, len(data), offset)
        if new_data != data:

            unpacked_wrdata=struct.unpack('>L',data[0:4])[0]
            unpacked_rddata=struct.unpack('>L',new_data[0:4])[0]

            self._logger.error("Verification of write to %s at offset %d failed. Wrote 0x%08x... but got back 0x%08x..."
                % (device_name, offset, unpacked_wrdata, unpacked_rddata))
            raise RuntimeError("Verification of write to %s at offset %d failed. Wrote 0x%08x... but got back 0x%08x..."
                % (device_name, offset, unpacked_wrdata, unpacked_rddata))

    def blindwrite(self, device_name, data, offset=0):
        """Unchecked data write.

           @see write
           @param self  This object.
           @param device_name  String: name of device / register to write to.
           @param data  Byte string: data to write.
           @param offset  Integer: offset to write data to (in bytes)
           """
        assert((type(data)==str))
        self._request("write", device_name, str(offset), data)

    def read_int(self, device_name):
        """Calls .read() command with size=4, offset=0 and
           unpacks returned four bytes into signed 32bit integer.

           @see read
           @param self  This object.
           @param device_name  String: name of device / register to read.
           @return  Integer: value read.
           """
        data = self.read(device_name, 4, 0)
        return struct.unpack(">i", data)[0]

    def write_int(self, device_name, integer, blindwrite=False, offset=0):
        """Calls .write() with optional offset and integer packed into 4 bytes.

           @see write
           @param self  This object.
           @param device_name  String: name of device / register to write to.
           @param integer  Integer: value to write.
           @param blindwrite  Boolean: if true, don't verify the write (calls blindwrite instead of write function).
           @param offset  Integer: position in 32-bit words where to write data. 
           """
        # careful of packing input data into 32 bit - check range: if
        # negative, must be signed int; if positive over 2^16, must be unsigned
        # int.
        if integer < 0:
            data = struct.pack(">i", integer)
        else:
            data = struct.pack(">I", integer)
        if blindwrite:
            self.blindwrite(device_name,data,offset*4)
        else:
            self.write(device_name, data, offset*4)

    def read_uint(self, device_name,offset=0):
        """As in .read_int(), but unpack into 32 bit unsigned int. Optionally read at an offset 32-bit register.

           @see read_int
           @param self  This object.
           @param device_name  String: name of device / register to read from.
           @return  Integer: value read.
           """
        data = self.read(device_name, 4, offset*4)
        return struct.unpack(">I", data)[0]

    def stop(self):
        """Stop the client.

           @param self  This object.
           """
        super(FpgaClient,self).stop()
        self.join(timeout=self._timeout)

    def print_10gbe_core_details(self,dev_name,arp=False, cpu=False):
        """Prints 10GbE core details. 
           @param dev_name string: Name of the core.
           @param arp boolean: Include the ARP table
           @param cpu boolean: Include the cpu packet buffers
        """
        #assemble struct for header stuff...
        #0x00 - 0x07: My MAC address
        #0x08 - 0x0b: Not used
        #0x0c - 0x0f: Gateway addr
        #0x10 - 0x13: my IP addr
        #0x14 - 0x17: Not assigned
        #0x18 - 0x1b: Buffer sizes
        #0x1c - 0x1f: Not assigned
        #0x20       : soft reset (bit 0)
        #0x21       : fabric enable (bit 0)
        #0x22 - 0x23: fabric port 
        #0x24 - 0x27: XAUI status (bit 2,3,4,5=lane sync, bit6=chan_bond)
        #0x28 - 0x2b: PHY config
        #0x28       : RX_eq_mix
        #0x29       : RX_eq_pol
        #0x2a       : TX_preemph
        #0x2b       : TX_diff_ctrl
        #0x1000     : CPU TX buffer
        #0x2000     : CPU RX buffer
        #0x3000     : ARP tables start

        port_dump=list(struct.unpack('>16384B',self.read(dev_name,16384)))
        ip_prefix= '%3d.%3d.%3d.'%(port_dump[0x10],port_dump[0x11],port_dump[0x12])

        print '------------------------'
        print 'GBE0 Configuration...'
        print 'My MAC: ',
        for m in port_dump[02:02+6]:
            print '%02X'%m,
        print ''

        print 'Gateway: ',
        for g in port_dump[0x0c:0x0c+4]:
            print '%3d'%g,
        print ''

        print 'This IP: ',
        for i in port_dump[0x10:0x10+4]:
            print '%3d'%i,
        print ''

        print 'Gateware Port: ',
        print '%5d'%(port_dump[0x22]*(2**8)+port_dump[0x23])

        print 'Fabric interface is currently: ',
        if port_dump[0x21]&1: print 'Enabled'
        else: print 'Disabled'


        print 'XAUI Status: ',
        print '%02X%02X%02X%02X'%(port_dump[0x24],port_dump[0x25],port_dump[0x26],port_dump[0x27])
        print '\t lane sync 0: %i'%bool(port_dump[0x27]&4)
        print '\t lane sync 1: %i'%bool(port_dump[0x27]&8)
        print '\t lane sync 2: %i'%bool(port_dump[0x27]&16)
        print '\t lane sync 3: %i'%bool(port_dump[0x27]&32)
        print '\t Channel bond: %i'%bool(port_dump[0x27]&64)

        print 'XAUI PHY config: '
        print '\tRX_eq_mix: %2X'%port_dump[0x28]
        print '\tRX_eq_pol: %2X'%port_dump[0x29]
        print '\tTX_pre-emph: %2X'%port_dump[0x2a]
        print '\tTX_diff_ctrl: %2X'%port_dump[0x2b]

        if arp:
            print 'ARP Table: '
            for i in range(256):
                print 'IP: %s%3d: MAC:'%(ip_prefix,i),
                for m in port_dump[0x3000+i*8+2:0x3000+i*8+8]:
                    print '%02X'%m,
                print ''

        if cpu:
            print 'CPU TX Interface (at offset 4096bytes):'
            print 'Byte offset:  Contents (Hex)'
            for i in range(4096/8):
                print '%04i:        '%(i*8),
                for l in range(8): print '%02x'%port_dump[4096+8*i+l],
                print ''
            print '------------------------'

            print 'CPU RX Interface (at offset 8192bytes):'
            print 'CPU packet RX buffer unacknowledged data: %i'%port_dump[6*4+3]
            print 'Byte offset:  Contents (Hex)'
            for i in range(port_dump[6*4+3]+8):
                print '%04i:        '%(i*8),
                for l in range(8): print '%02x'%port_dump[8192+8*i+l],
                print ''
        print '------------------------'

    def est_brd_clk(self):
        """Returns the approximate clock rate of the FPGA in MHz."""
        firstpass=self.read_uint('sys_clkcounter')
        time.sleep(2)
        secondpass=self.read_uint('sys_clkcounter')
        if firstpass>secondpass: secondpass=secondpass+(2**32)
        return (secondpass-firstpass)/2000000.

    def qdr_status(self,qdr):
         """Checks QDR status (PHY ready and Calibration). NOT TESTED.
            \n@param qdr integer QDR controller to query.
            \n@return dictionary of calfail and phyrdy boolean responses."""
         #offset 0 is reset (write 0x111111... to reset). offset 4, bit 0 is phyrdy. bit 8 is calfail.
         assert((type(qdr)==int))
         qdr_ctrl = struct.unpack(">I",self.read('qdr%i_ctrl'%qdr, 4, 4))[0]
         return {'phyrdy':bool(qdr_ctrl&0x01),'calfail':bool(qdr_ctrl&(1<<8))}

    def qdr_rst(self,qdr):
         """Performs a reset of the given QDR controller (tries to re-calibrate). NOT TESTED.
            \n@param qdr integer QDR controller to query.
            \n@returns nothing."""
         assert((type(qdr)==int))
         self.write_int('qdr%i_ctrl'%qdr,0xffffffff,blindwrite=True)

    def get_snap(self,dev_name,brams,man_trig=False,man_valid=False,wait_period=1,offset=-1,       circular_capture=False):
        """Grabs all brams from a single snap block on this FPGA device.\n
            \tdev_name: string, name of the snap block.\n
            \tman_trig: boolean, Trigger the snap block manually.\n
            \toffset: integer, wait this number of valids before beginning capture. Set to negative value if    your hardware doesn't support this or the circular capture function.\n
            \tcircular_capture: boolean, Enable the circular capture function.\n
            \twait_period: integer, wait this number of seconds between triggering and trying to read-back the data.\n
            \tbrams: list, names of the bram components.\n
            \tRETURNS: dictionary with keywords: \n
            \t\tlengths: list of integers matching number of valids captured off each fpga.\n
            \t\toffset: optional (depending on snap block version) list of number of valids elapsed since last  trigger on each fpga.
            \t\t{brams}: list of data from each fpga for corresponding bram.\n"""
        #2010-02-19 JRM Updated to match snap_x.
        #WORKING OK 2009-07-01
        if offset >= 0:
            self.write_int(dev_name+'_trig_offset',offset)
            #print 'Capturing from snap offset %i'%offset

        #print 'Triggering Capture...',
        self.write_int(dev_name+'_ctrl',(0 + (man_trig<<1) + (man_valid<<2)))
        self.write_int(dev_name+'_ctrl',(1 + (man_trig<<1) + (man_valid<<2)))

        time.sleep(wait_period)

        done=False
        start_time=time.time()
        while not (done and (offset>0 or circular_capture)) and ((time.time()-start_time)<wait_period):
            addr= self.read_uint(dev_name+'_addr')
            done=bool(addr & 0x80000000)

        bram_size= self.read_uint(dev_name+'_addr')&0x7fffffff
        bram_dmp=dict()
        bram_dmp={'length':bram_size+1}
        bram_dmp['offset']=0
        if (bram_size != self.read_uint(dev_name+'_addr')&0x7fffffff) or bram_size==0:
            #if address is still changing, then the snap block didn't finish capturing. we return empty.  
            print "Looks like snap block didn't finish."
            bram_dmp['length']=0
            bram_dmp['offset']=0
            bram_size=0

        if circular_capture or (offset>=0):
            bram_dmp['offset']=self.read_uint(dev_name+'_tr_en_cnt') + offset - bram_size
        else: bram_dmp['offset']=0

        if (bram_dmp['offset'] < 0):  
            raise RuntimeError('SNAP block hardware or logic failure happened. Returning no data.')
        #if offset<0, there was a big error. this should never happen. unless you held stop high while      resetting before inputting valid data during a circular capture? In any case, zero the output.
            bram_dmp['length']=0
            bram_dmp['offset']=0
            bram_size=0

        for b,bram in enumerate(brams):
            bram_path = dev_name+'_'+bram
            if (bram_size == 0): 
                bram_dmp[bram]=[]
            else: 
                bram_dmp[bram]=(self.read(bram_path,(bram_size+1)*4))
        return bram_dmp

        for b,bram in enumerate(brams):
            bram_path = dev_name+'_'+bram
            if (addr == 0): bram_dmp[bram]=[]
            else: 
                bram_dmp[bram]=(self.read(bram_path,(addr+1)*4))
        return bram_dmp

