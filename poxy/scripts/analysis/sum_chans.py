#!/usr/bin/env python

import numpy as n
import math, sys, os, h5py

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
    o.add_option('-d', '--decimate', dest='decimate', default=1,
        help='Number of channels to sum and average over, Default:1')
    o.add_option('-s', '--start', dest='start', default=None,
        help='Drop channels before this channel, start collapse here')
    o.add_option('-e', '--end', dest='end', default=None,
        help='Drop channels after this channel, end collapse here')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        h5fns = args

def copy_attrs(fhi,fho):
    for a in fhi.attrs.iteritems():
        fho.attrs.create(a[0], a[1])

def append_history(fh,hist_str):
    if not('history' in fh.keys()):
        rv = fh.create_dataset('history', data=n.array([hist_str]))
    else:
        hv = fh['history'].value
        del fh['history']
        if type(hv) == n.ndarray: new_hist=n.append(hv,n.array([hist_str]))
        else: new_hist=n.array([[hv],[hist_str]])
        rv = fh.create_dataset('history', data=new_hist)

def sum_chan(cm,dec):
    nts=cm.shape[0]
    nfreqs=cm.shape[1]
    nbls=cm.shape[2]
    npols=cm.shape[3]
    dec_cm=n.zeros((nts,nfreqs/dec,nbls,npols,2))
    ch_index=0
    for ch in range(nfreqs/dec):
        next_cm=n.zeros((nts,nbls,npols,2))
        for i in range(dec):
            next_cm+=cm[:,ch_index+i]
        next_cm=next_cm/dec
        ch_index+=dec
        dec_cm[:,ch]=next_cm
    return dec_cm

# Process data
for fni in args:
    fno = fni + 'F'
    if os.path.exists(fno):
        print 'File exists: skipping'
        continue
    print 'Opening:',fno
    fhi = h5py.File(fni, 'r')
    fho = h5py.File(fno, 'w')
    #copy attributes
    copy_attrs(fhi,fho)
    #copy datasets/groups except timestamps0 and xeng_raw0
    for item in fhi.iteritems():
        if item[0] == 'xeng_raw0':
            cm=fhi.get(item[0]) 
        else:
            if type(fhi[item[0]]) == h5py.highlevel.Group:
                tmp_grp = fhi.get(item[0])
                fho.copy(tmp_grp,item[0])
            else:
                fho.create_dataset(item[0],data=item[1])
    
    nchani=fhi.attrs['n_chans']
    decimate=int(opts.decimate)
    if opts.start is None: ch_start=0
    else: ch_start=int(opts.start)
    if opts.end is None: ch_end=nchani
    else: ch_end=int(opts.end)
    n_ch = ch_end-ch_start
    #ignore the last channels to get an integer number of channels
    n_ch-=n_ch%decimate
    ch_end=n_ch+ch_start
    
    #sum channels
    dec_cm=sum_chan(cm[:,ch_start:ch_end],decimate)
    #write ts and cm to file
    fho.create_dataset('xeng_raw0',data=dec_cm)
    
    #write history log and update attributes
    sdf=fhi.attrs['bandwidth']/fhi.attrs['n_chans']
    fho.attrs['n_chans']=n_ch/decimate
    fho.attrs['bandwidth']=n_ch*sdf
    #sfreq=fhi.attrs['center_freq']-nchani/2*sdf
    sfreq=ch_start*sdf + (fhi.attrs['center_freq']-fhi.attrs['bandwidth']/2.)
    fho.attrs['center_freq']=sfreq+n_ch*sdf/2.
    print 'chan0 freq:', ch_start*sdf + (fhi.attrs['center_freq']-fhi.attrs['bandwidth']/2.)
    print 'chanN-1 freq:', ch_end*sdf + (fhi.attrs['center_freq']-fhi.attrs['bandwidth']/2.)
    print 'start freq:',sfreq
    print 'center freq:', fho.attrs['center_freq']
    print 'number of channels:',fho.attrs['n_chans']
    print 'bandwidth:',fho.attrs['bandwidth']
    hist_str="SUM_CHANS: Summed and averaged by %i channels, start at freq_ch%i, and at freq_ch%i removed %i channels at the end of the band."%(decimate,ch_start,ch_end,n_ch%decimate)
    append_history(fho,hist_str)
    
    fho.close()
    fhi.close()
