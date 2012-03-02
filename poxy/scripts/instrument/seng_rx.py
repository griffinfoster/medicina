#!/usr/bin/env python
"""This script receives data from S engines with contiguous frequency bands (i.e. NOT interleaved), assembles a complete integration and then stores to disk (in h5 format) and forwards to the signal displays.
Original Author: Simon Ratcliffe"""

import numpy as np, spead, logging, sys, time, h5py, os
from poxy import katcp_wrapper, medInstrument, log_handlers
import ephem

logging.basicConfig(level=logging.WARN)
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)

def conv_time(t):
    """Convert standard unix time (seconds since 1970) to a Julian Date"""
    t_tup = time.gmtime(t)[:6]
    return ephem.julian_date(t_tup)

if __name__ == '__main__':
    from optparse import OptionParser
    p = OptionParser()
    p.set_usage('%prog [options] CONFIG_FILE')
    p.set_description(__doc__)
    p.add_option('-a', '--disable_autoscale', dest='acc_scale',action='store_false', default=True,
       help='Do not autoscale the data by dividing down by the number of accumulations.  Default: Scale back by n_accs.')
    p.add_option('-s', '--single_capture', dest='single_capture', action='store_true', default=False,
        help='Only do a single capture (one MIRIAD file). Default: continuously create new MIRIAD files.')
    p.add_option('-t', '--time', dest='time', type='int', default=-1,
        help='Override the config file and generate data files with this length (in seconds). Set to zero to capture one integration. (or don\'t because this seems to break everything')
    opts, args = p.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()
    else:
        acc_scale=opts.acc_scale
        inst=medInstrument.Instrument(args[0], passive=True)
        data_ip= inst.config.receiver.sengine.rx_ip
        data_port = inst.config.receiver.sengine.rx_port
        if opts.time != -1:
            file_time = opts.time
        else:
            file_time = inst.config.receiver.sengine.file_time

print 'Recording file of length %d seconds' %file_time

if opts.single_capture:
    print '    #### Only capturing one file of data ####'

print 'Initalising SPEAD transports...'
print "Expecting data on %s:%d" %(data_ip,data_port)
sys.stdout.flush()
rx = spead.TransportUDPrx(data_port, pkt_count=2048, buffer_size=102400000)
ig = spead.ItemGroup()

t_index = '%7.5f'%conv_time(time.time())
#t_index = str(int(time.time()))

# Create the file to write
fn = "img." + t_index + ".h5"
print 'Creating file: %s' %fn,
f = h5py.File(fn, mode="w")
print 'done.'

data_ds = None
ts_ds = None
idx = 0
dump_size = 0
datasets = {}
datasets_index = {}
# we need these bits of meta data before being able to assemble and transmit signal display data
meta_required = ['n_chans','n_stokes','n_sengs','n_ants','sync_time', 'n_beams']
meta = {}
sd_frame = None
sd_slots = None
timestamp = None
write_enabled = True

last_save_time = time.time()
recording=False

try:
    for heap in spead.iterheaps(rx):
        ig.update(heap)
        for name in ig.keys():
            item = ig.get_item(name)
            if not item._changed and datasets.has_key(name): continue #the item has not changed and we already have a record of it.
            if name in meta_required:
                meta_required.pop(meta_required.index(name))
                print meta_required
                if len(meta_required) == 0:
                    print 'I have all the meta data I need...'
                    sd_frame = np.zeros((ig['n_chans'],ig['n_ants']*4,ig['n_stokes']),dtype=np.uint32)
                    print "Got the required metadata. Initialised sd frame to shape",sd_frame.shape
                    sd_slots = np.zeros(ig['n_sengs']) #create an SD slot for each S engine. This keeps track of which engines' data have been received for this integration.

            if not datasets.has_key(name):
                # check to see if we have encountered this type before
                shape = ig[name].shape if item.shape == -1 else item.shape
                if not name.startswith('timestamp'):
                    dtype = np.dtype(type(ig[name])) if shape == [] else item.dtype                 
                else:
                    dtype = np.uint64
                if dtype is None: dtype = ig[name].dtype
                # if we can't get a dtype from the descriptor try and get one from the value
                print "Creating dataset for name:",name,", shape:",shape,", dtype:",dtype
                f.create_dataset(name,[1] + ([] if list(shape) == [1] else list(shape)), maxshape=[None] + ([] if list(shape) == [1] else list(shape)), dtype=dtype)
                if not name.startswith('timestamp'):
                   dump_size += np.multiply.reduce(shape) * dtype.itemsize
                datasets[name] = f[name]
                datasets_index[name] = 0
                if not item._changed:
                    continue
            else:
                print "Adding",name,"to dataset. New size is",datasets_index[name]+1
                f[name].resize(datasets_index[name]+1, axis=0)

            if name.startswith("seng_raw") and datasets_index[name]==0:
                recording=True
                last_save_time=time.time()

            f[name][datasets_index[name]] = ig[name]
            item._changed = False
            datasets_index[name] += 1

            if time.time() - last_save_time > file_time and recording and name.startswith("seng_raw"):
                last_save_time = time.time()
                next_datasets = {}
                next_datasets_index = {}
                #create the next file
                t_index = '%7.5f'%conv_time(time.time())
                #t_index = str(int(time.time()))
                new_fn = "img." + t_index + ".h5"
                new_f = h5py.File(new_fn, mode="w")
                #close current file
                print "Writing file: %s"%(fn)
                for (name,idx) in datasets_index.iteritems():
                    #if idx == 1 and not name.startswith('eq'):
                    if not name.startswith('timestamp') and not name.startswith('seng_raw') and not name.startswith('eq'):
                        #next_datasets[name] = f[name].value[0]
                        next_datasets[name] = f[name].value[-1]
                        next_datasets_index[name] = 0
                        
                        if (type(f[name].value[0])==np.string_):
                            new_f.create_dataset(name,[1], data=f[name].value[-1])
                        else:
                            new_f.create_dataset(name,[1], maxshape=[None], dtype=type(f[name].value[-1]))
                        new_f[name][next_datasets_index[name]] = f[name].value[-1]
                        next_datasets_index[name] += 1
                        
                        print "Repacking dataset",name,"as an attribute as it is singular.",
                        f['/'].attrs[name] = f[name].value[-1]
                        print 'done'
                        f.__delitem__(name)
                    elif name.startswith('eq'):
                        #carry over the last EQ values
                        shape = f[name].value[-1].shape
                        new_f.create_dataset(name,[1] + ([] if list(shape) == [1] else list(shape)), maxshape=[None] + ([] if list(shape) == [1] else list(shape)), dtype=f[name].dtype)
                        new_f[name][0]=f[name].value[-1]
                        next_datasets[name] = f[name]
                        next_datasets_index[name] = 0
                f.flush()
                f.close()
                if opts.single_capture:
                    print 'Single file captured. Exiting.'
                    new_f.close()
                    os.system('rm %s' %new_fn) #Bit of a hack -- The code above creates the next file before closing the first
                    exit()
                print "Starting file: %s"%(new_fn)
                f = new_f
                #print next_datasets, next_datasets_index
                datasets = next_datasets
                datasets_index = next_datasets_index

except KeyboardInterrupt:
    print "Closing file."
    for (name,idx) in datasets_index.iteritems():
        if not name.startswith('timestamp') and not name.startswith('seng_raw') and not name.startswith('eq'):
            print "Repacking dataset",name,"as an attribute as it is singular."
            f['/'].attrs[name] = f[name].value[-1]
            f.__delitem__(name)

    f.flush()
    f.close()

