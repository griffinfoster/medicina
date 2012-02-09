#!/usr/bin/env python

"""
Combine multiple HDF5 Correlator Files into one file, carry over attributes and metadata sets from
the first file only.
"""

import numpy as n
import math, sys, os, h5py

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
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

# Process data
hist_str="COMBINE_FILES: Appended files "
file_cnt=0
for fni in args:
    #copy metadata from first file
    if file_cnt==0:
        fno = fni + 'a'
        if os.path.exists(fno):
            print 'File exists: skipping'
            break
        print 'Opening:',fno
        fho = h5py.File(fno, 'w')
        fhi = h5py.File(fni, 'r')
        #copy attributes
        copy_attrs(fhi,fho)
        #copy datasets/groups except timestamps0 and xeng_raw0
        for item in fhi.iteritems():
            if item[0] == 'xeng_raw0':
                comb_cm=fhi.get(item[0]).value
            elif item[0] == 'timestamp0':
                comb_ts=fhi.get(item[0]).value
            else:
                if type(fhi[item[0]]) == h5py.highlevel.Group:
                    tmp_grp = fhi.get(item[0])
                    fho.copy(tmp_grp,item[0])
                else:
                    fho.create_dataset(item[0],data=item[1])
        fhi.close()
    else:
        print fni
        fhi = h5py.File(fni, 'r')
        comb_cm=n.concatenate((comb_cm,fhi.get('xeng_raw0').value))
        comb_ts=n.concatenate((comb_ts,fhi.get('timestamp0').value))
        fhi.close()
    hist_str+="%s, "%fno
    file_cnt+=1

#write ts and cm to file
fho.create_dataset('timestamp0',data=comb_ts)
fho.create_dataset('xeng_raw0',data=comb_cm)

fho.attrs['n_accs']=len(comb_ts)
print hist_str
append_history(fho,hist_str)
