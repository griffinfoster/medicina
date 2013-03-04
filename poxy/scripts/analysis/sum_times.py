#!/usr/bin/env python

import numpy as n
import math, sys, os, h5py

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
    o.add_option('-a', '--all', dest='all', action='store_true',
        help='Sum all integrations into one integration')
    o.add_option('-d', '--decimate', dest='decimate', default=2,
        help='Number of integrations to average over, if the there is a not integer number then the remainder integrations are dropped. default:2')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        h5fns = args

def copy_attrs(fhi,fho):
    for a in fhi.attrs.iteritems():
        fho.attrs.create(a[0], a[1])

def sum_times(cm,ts,dec):
    nfreqs=cm.shape[1]
    nbls=cm.shape[2]
    npols=cm.shape[3]
    dec_cm=n.zeros((len(ts)/dec,nfreqs,nbls,npols,2))
    dec_ts=n.zeros(len(ts)/dec)
    time_index=0
    for t in range(len(dec_ts)):
        next_ts=0
        next_cm=n.zeros((nfreqs,nbls,npols,2))
        for i in range(dec):
            next_ts+=ts[time_index+i]
            next_cm+=cm[time_index+i]
        next_ts=next_ts/dec
        next_cm=next_cm/dec
        time_index+=dec
        dec_ts[t]=next_ts
        dec_cm[t]=next_cm
    return dec_ts,dec_cm

def append_history(fh,hist_str):
    if not('history' in fh.keys()):
        rv = fh.create_dataset('history', data=n.array([hist_str]))
    else:
        hv = fh['history'].value
        del fh['history']
        if type(hv) == n.ndarray: new_hist=n.append(hv,n.array([hist_str]))
        else: new_hist=n.array([[hv],[hist_str]])
        rv = fh.create_dataset('history', data=new_hist)

# Process data
for fni in args:
    fno = fni + 'A'
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
        elif item[0] == 'timestamp0':
            ts=fhi.get(item[0])
        else:
            if type(fhi[item[0]]) == h5py.highlevel.Group:
                tmp_grp = fhi.get(item[0])
                fho.copy(tmp_grp,item[0])
            else:
                fho.create_dataset(item[0],data=item[1])
    
    decimate = int(opts.decimate)
    if opts.all: decimate=len(ts.value)

    #ignore the last time samples based on the decimation value
    n_ts = len(ts.value) - len(ts.value) % decimate
    #sum channels
    dec_ts,dec_cm = sum_times(cm.value[:n_ts],ts.value[:n_ts],decimate)
    
    #write ts and cm to file
    fho.create_dataset('timestamp0',data=dec_ts)
    fho.create_dataset('xeng_raw0',data=dec_cm)
    
    #write history log and update atrributes
    fho.attrs['n_accs']=fhi.attrs['n_accs']*decimate
    fho.attrs['int_time']=fhi.attrs['int_time']*decimate
    hist_str="SUM_TIMES: Summed and averaged by %i integrations, removed %i integrations at the end of the file."%(decimate,len(ts.value)%decimate)
    print hist_str
    append_history(fho,hist_str)
    
    fho.close()
    fhi.close()
