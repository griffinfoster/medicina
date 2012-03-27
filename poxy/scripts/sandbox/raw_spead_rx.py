#!/usr/bin/env python
"""This script is a debugging tool for SPEAD tx systems"""

import numpy as np, spead, sys, time, logging

if __name__ == '__main__':
    from optparse import OptionParser
    p = OptionParser()
    p.set_usage('%prog [options] port')
    p.set_description(__doc__)
    opts, args = p.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a port. Exiting.'
        exit()
    else:
        data_port = int(args[0])

# WARN/DEBUG/INFO
logging.basicConfig(level=logging.INFO)
print 'Initalising SPEAD transports...'
print "Data reception on port",data_port
sys.stdout.flush()
rx = spead.TransportUDPrx(data_port, pkt_count=10240, buffer_size=10240000)
ig = spead.ItemGroup()

for i in range(8):
    ig.add_item(
        name= "beam%d"%i,
        id= (6000<<3) + i,
        description= "beam %d from the S-engine"%i,
        shape=[1024]
    )

print ig.keys()
print ig.ids()

print "Entering receive loop"

curr_heap = 0
heap_cnt = 0
pkt_cnt = 0
err_cnt=0
#for heap in spead.iterheaps(rx):
#    a = 0
for pkt in rx.iterpackets():
#    #print pkt.items
    pkt_cnt += 1
    if pkt.heap_cnt != curr_heap:
        print "HEAP: %d had %d packets" %(curr_heap, pkt_cnt)
        #heap_cnt += 1
        #if pkt_cnt != 128:
        #    err_cnt += 1
        #    print "----------------------- %d errors in %d heaps" %(err_cnt,heap_cnt)
        pkt_cnt = 0
        curr_heap = pkt.heap_cnt
#        print len(pkt.payload)
#        print type(pkt.payload[0])
    print 'HEAP: %d, HEAP LEN: %d, N_ITEMS: %d, PAYLOAD_LEN: %d, PAYLOAD_OFFSET: %d' %(pkt.heap_cnt, pkt.heap_len, pkt.n_items, pkt.payload_len, pkt.payload_off)
   # for name in ig.keys():
    #    print
    #    item = ig.get_item(name)
    #    if not item._changed and datasets.has_key(name): continue #the item has not changed and we already have a record of it.
    #    if name in meta_required:
    #        meta_required.pop(meta_required.index(name))
    #        if len(meta_required) == 0:
    #            sd_frame = np.zeros((ig['n_chans'],ig['n_bls'],ig['n_stokes'],2),dtype=np.int32)
    #            print "Got the required metadata. Initialised sd frame to shape",sd_frame.shape
    #            sd_slots = np.zeros(ig['n_xengs']) #create an SD slot for each X engine. This keeps track of which engines' data have been received for this integration.

    #    if not datasets.has_key(name):
    #     # check to see if we have encountered this type before
    #        shape = ig[name].shape if item.shape == -1 else item.shape
    #        dtype = np.dtype(type(ig[name])) if shape == [] else item.dtype                 
    #        if dtype is None: dtype = ig[name].dtype
    #        # if we can't get a dtype from the descriptor try and get one from the value
    #        print "Creating dataset for name:",name,", shape:",shape,", dtype:",dtype
    #        f.create_dataset(name,[1] + ([] if list(shape) == [1] else list(shape)), maxshape=[None] + ([] if list(shape) == [1] else list(shape)), dtype=dtype)
    #        dump_size += np.multiply.reduce(shape) * dtype.itemsize
    #        datasets[name] = f[name]
    #        datasets_index[name] = 0
    #        if not item._changed:
    #            continue
    #    else:
    #        print "Adding",name,"to dataset. New size is",datasets_index[name]+1
    #        f[name].resize(datasets_index[name]+1, axis=0)
