#!/usr/bin/env python
"""
Adds CASPER correlator bl order
Reorders the data for single polarization complex data and removes the duplicate correlations
Aligns the timestamp array
Creates EQ subgroup
Option: divide by accumulation length to get the averaged 8bit values
Option: Corrects the polarization ordering for the real component, [yy, xy, yx, xx] -> [xx, yy, xy, yx]
Corrects bl index 135 channel ordering
"""

import numpy as n
import math, time, h5py, sys, os
import poxy

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
    o.add_option('-a', '--acc', dest='acc', default=False, action='store_true',
        help='Divide the data by the accumulation length to get averaged 8bit values.')
    o.add_option('-r', '--roll', dest='roll', default=True, action='store_false',
        help='Do not roll the XX pol by one bl index step forward.')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        h5fns = args

def isodd(num): return num & 1 and True or False

st=time.time()

red_bl = [0,2,5,9,14,20,27,35,44,53,62,71,80,89,98,107]

#map output antenna labels to a logical array layout
rewire = {
        0:0,   16:1,   1:2,  17:3,
        2:4,   18:5,   3:6,  19:7,
        4:8,   20:9,   5:10, 21:11,
        6:12,  22:13,  7:14, 23:15,
        8:16,  24:17,  9:18, 25:19,
        10:20, 26:21, 11:22, 27:23,
        12:24, 28:25, 13:26, 29:27,
        14:28, 30:29, 15:30, 31:31  }

hist_str = """CORR CORRECT:Corrected Correlator output to be aligned with the Medicina array layout,
set to single polarization, removed redundant baselines"""

for fn in h5fns:
    new_fn = fn + "c"
    if os.path.exists(new_fn):
        print "Skipping", new_fn,", already exists"
        continue
    fh = h5py.File(fn,'r')
    new_fh = h5py.File(new_fn,'w')
    print "Processing",fn,"->",new_fn

    #copy over attributes
    for a in fh.attrs.iteritems():
        new_fh.attrs.create(a[0], a[1])
    
    #overwrite new values for single polarization
    n_ants = 2*fh.attrs.get('n_ants')
    n_chans = fh.attrs.get('n_chans')
    n_bls = n_ants * (n_ants+1) / 2
    n_accs = fh.attrs.get('n_accs')
    new_fh.attrs.modify("n_stokes",1)
    new_fh.attrs.modify("n_bls",n_bls)
    new_fh.attrs.modify("n_ants",n_ants)
  
    #copy timestamps over, removing the first element of the array
    #tv = n.delete(fh['timestamp0'].value,0,0)
    tv = fh['timestamp0'].value
    uts = fh.attrs['sync_time']+tv/fh.attrs['scale_factor_timestamp']
    rv = new_fh.create_dataset('timestamp0', data=uts)
    
    #single polarization pol table
    pol_ds = ['xx']*n_bls
    rv = new_fh.create_dataset('pol', data=pol_ds)

    #bl index table
    corr_bl_order = poxy.casper.get_bl_order(fh.attrs.get('n_ants'))
    bl_order = []
    for i,j in corr_bl_order:
        bl_order.extend([
            (i,j),
            (i+n_ants/2, j+n_ants/2),
            (i,j+n_ants/2),
            (i+n_ants/2,j)])
    bl_order = n.array(bl_order)

    #remove redundant bls/reorder bls
    n_red_bl = n.array(red_bl)
    n_red_bl = n_red_bl*4 + 3
    bl_order = n.delete(bl_order,n_red_bl,0)
    #reorder baseline label to match with Medicina layout: 1-1-->0, 1-2-->1, ...
    new_bl_order=[]
    #conjugate when nj>ni and ni is odd and nj is even
    conj_list=[]
    for i,j in bl_order:
        ni=rewire[i]
        nj=rewire[j]
        #if ni > nj: new_bl_order.append([nj,ni])
        #else: new_bl_order.append([ni,nj])
        if ((nj>ni) and isodd(ni) and (not isodd(nj))):
            conj_list.append(1)
        else: conj_list.append(0)
        new_bl_order.append([ni,nj])
    new_bl_order=n.array(new_bl_order)
    conj_list=n.array(conj_list)
    #baseline index which should be conjugated
    conj_ind=n.argwhere(conj_list==1)
    
    #baseline reorder indicies
    bl_compress=[]
    for i,j in new_bl_order: bl_compress.append(1024*i+j)
    bl_compress=n.array(bl_compress)
    ind=n.argsort(bl_compress)
    rv = new_fh.create_dataset('bl_order', data=new_bl_order[ind])

    #create EQ subgroup, rename EQs to single pol
    eq_group=new_fh.create_group("EQ")
    for ds in fh.iterkeys():
        if ds.startswith('eq_amp_coeff'):
            prefix='eq_amp_coeff_'
            ant=int(ds.split('_')[-1][:-1])
            if ds[-1] == 'y': ant+=n_ants/2
            ant=rewire[ant]
            new_key = prefix + '%ix'%ant
            rv=eq_group.create_dataset(new_key, data=fh[ds])
        elif ds.startswith('eq_amp'):
            rv=eq_group.create_dataset(ds, data=fh[ds])

    #create an empty dataset to file in with corrected data
    n_ts = len(new_fh['timestamp0'])
    sp_shape = (n_ts,n_chans,n_bls,1,2)
    chunk_size = (1,n_chans,1,1,2)
    #rv = new_fh.create_dataset('xeng_raw0', sp_shape, chunks=chunk_size, dtype=float)
    rv = new_fh.create_dataset('xeng_raw0', sp_shape, dtype=float)

    #create a dataset for flags the same shape as the corr data
    flags = n.zeros(sp_shape[:4], dtype=bool)
    rv = new_fh.create_dataset('flags', data=flags, dtype=bool)

    total_acc=n.zeros(sp_shape)
    for i,acc in enumerate(fh['xeng_raw0']):
        #align channels for bl index 135, pol index 3
        bl_fix=acc[:,135,3,:]
        bl_fix=n.concatenate((n.roll(bl_fix[:n_chans/2],1,axis=0), n.roll(bl_fix[n_chans/2:],1,axis=0)))
        acc[:,135,3,:]=bl_fix
        
        #roll the xx real data (index 3) to shift all the bl indicies +1, i.e. 120->121, 135->0
        xpol=acc[:,:,3,1]
        xpol=n.roll(xpol,1,axis=1)
        acc[:,:,3,1]=xpol
        
        #roll the polarization data real component [yy, xy, yx, xx] -> [xx, yy, xy, yx]
        acc_real=acc[:,:,:,1]
        acc_real=n.roll(acc_real,1,axis=2)
        acc[:,:,:,1]=acc_real
        
        #flip spectrum
        acc=acc[::-1,...]

        #reshape the data
        acc=n.reshape(acc,(n_chans,544,1,2))
        
        #remove the redundant bls
        acc=n.delete(acc,n_red_bl,1)

        #conjugate baselines
        #acc[:,conj_ind,:,0] = -1 * acc[:,conj_ind,:,0]
        
        #reorder the data to some sort of sensible baseline ordering
        acc=acc[:,ind,:,:]
        
        #convert data to floats and divide by the number of correlator accumulations
        new_acc=n.array(acc,dtype=float)
        if opts.acc: new_acc=new_acc/n_accs
        
        #new_fh['xeng_raw0'][i]=acc
        total_acc[i]=new_acc
    new_fh['xeng_raw0'][:]=total_acc
    
    if not('history' in fh.keys()):
        rv = new_fh.create_dataset('history', data=n.array([hist_str]))
    else:
        tv = fh['history'].value
        new_hist=[]
        for hv in tv:
            new_hist.append(hv)
        new_hist.append(hist_str)
        rv = new_fh.create_dataset('history', data=n.array(new_hist))

    fh.flush()
    fh.close()
    new_fh.flush()
    new_fh.close()
    print time.time()-st
    st=time.time()
