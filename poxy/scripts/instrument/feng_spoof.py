#! /usr/bin/python

HOST = 'tokolosh'
BOFFILE = 'feng_spoof_med.bof'

import corr
import pylab
import time
import numpy as np
import struct
import sys

r = corr.katcp_wrapper.FpgaClient(HOST, 7147)
time.sleep(0.5)
if len(sys.argv)>1:
    if sys.argv[1]=='p':
        print 'clearing FPGA'
        r.progdev('')
        time.sleep(1)
        print  'programming FPGA with boffile %s' %BOFFILE
        r.progdev(BOFFILE)
        time.sleep(1)

xdim = 4*2
ydim = 8*2
xrange=np.array(range(xdim))
yrange=np.array(range(ydim))

xbin = 0
ybin = 0

xwave = 2**1*(np.cos(xbin * 2*np.pi*xrange/float(xdim)) + 1j*np.sin(xbin * 2*np.pi*xrange/float(xdim)))
ywave = 2**1*(np.cos(ybin * 2*np.pi*yrange/float(ydim)) + 1j*np.sin(ybin * 2*np.pi*yrange/float(ydim)))
#xwave = xwave*(1j-1)
#print xwave
#print ywave
#pylab.plot(xwave.real)
#pylab.plot(ywave.real)
#pylab.show()
#print xwave
#print ywave
xwave = xwave[0:4]
ywave = ywave[0:8]

print 'XWAVE!'
print xwave

ant_mask = np.zeros(32, dtype=complex)
for i in range(8):
    print ywave[i]*xwave
    ant_mask[4*i:4*(i+1)] = ywave[i]*xwave

#print ant_mask.real

#pylab.pcolor(ant_mask.reshape(4,8).real)
#pylab.pcolor(ant_mask.reshape(8,4).real)
#pylab.show()

#format as uints
uint_mask = np.zeros(32,dtype=np.uint)
for i in range(len(ant_mask)):
    re = int(ant_mask[i].real)
    im = int(ant_mask[i].imag)
    uint_mask[i] = ((re&0xf)<<4)+(im&0xf)

print 'ant_mask after cramming re/im'
print uint_mask

print 'Generating test vectors'
#ant_mask = np.zeros(32, dtype=np.int)
#ant_mask = np.ones(32, dtype=np.int)

chan_mask = np.zeros(1024, dtype=np.uint)
#ramp = np.arange(2**3)+1
#for i in range(len(chan_mask)/8):
#    chan_mask[8*i:8*(i+1)] = ramp
#'''
#chan_mask[0] = 1
#chan_mask[2] = 1
#chan_mask[1] = 1
#chan_mask[254] = 1
#chan_mask[0:256] = 1
#'''
chan_mask[0]=1

test_vectors = np.array([],dtype=np.uint)
for chan in chan_mask:
    for ant_slice in range(8):
        word = 0
        for ant in range(4):
            word += (uint_mask[4*ant_slice + ant]*chan)<<(8*(3-ant))
            #if chan!=0:
            #    print 'taking number', uint_mask[4*ant_slice+ant]
            #    print 'shifting up by', 8*ant
            #    print (uint_mask[4*ant_slice + ant]*chan)<<(8*ant)
        test_vectors = np.append(test_vectors, word)
    
test_vectors = np.array(test_vectors, dtype=np.uint)
#print test_vectors
#test_vectors[4:]=0
print test_vectors[0:16]

print 'len(test_vectors)', len(test_vectors)

print 'Packing test vectors'
test_vec_str = ''
for word in test_vectors:
    test_vec_str = test_vec_str + struct.pack('>L', word)



print 'uploading coefficients'
r.write('sim_data', test_vec_str)

print 'sending sync'
r.write_int('sync_arm', 0)
r.write_int('sync_arm', 1)
r.write_int('sync_arm', 0)
time.sleep(1)

print 'Armed?: %d' %r.read_int('sync_armed')
