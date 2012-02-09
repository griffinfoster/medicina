#!/usr/bin/env python
"""
Takes an hd5 file containing spatial image data and iffts / cuts redundant pixels to return an hd5 containing
the correlation matrix (with no redundant baselines)
"""

import numpy as n
import math, time, h5py, sys
#import pylab

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] *.h5')
    o.set_description(__doc__)
    o.add_option('-a', '--acc', dest='acc', default=False, action='store_true',
        help='Divide the data by the accumulation length to get averaged 8bit values.')
    opts, args = o.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify a hdf5 file! \nExiting.'
        exit()
    else:
        h5fns = args

n_files = len(h5fns)
for N,fn in enumerate(h5fns):
    print '##### Processing file %s (File %d of %d) #####' %(fn,N+1,n_files)
    fh = h5py.File(fn,'r')
    new_fn = fn + "_corr"
    new_fh = h5py.File(new_fn,'w')

    #copy over attributes
    print 'Copying attributes to new file'
    for a in fh.attrs.iteritems():
        new_fh.attrs.create(a[0], a[1])

    print 'Getting image file parameters'
    n_ants = fh.attrs.get('n_ants')
    n_chans = fh.attrs.get('n_chans')
    image_shape = fh.attrs.get('image_shape')
    n_ts = len(fh['seng_raw0'])

    if n_chans == None:
        print 'nchans unspecified, harcoding to 1024'
        n_chans = 1024

    if image_shape == None:
        print 'Couldn\'t find image_shape attribute. Reading image dimensions from data:',
        #Catch the case the image_shape attribute does not exist
        #And extract the shape information from the data itself
        image_shape = n.array(fh['seng_raw0'].shape[2:4], dtype=int)
        print image_shape
    if len(image_shape) != 2:
        print 'Current conv_image.py script can only cope with 2D antenna arrays. Exiting'
        exit()
    n_bls = n.prod(image_shape//2) + n.prod(image_shape//2 -1)
    print 'Number of baselines to be generated in output file: %d' %(n_bls)
    n_stokes = fh.attrs.get('n_stokes')
    n_accs = fh.attrs.get('n_accs')
    new_fh.attrs.create("n_bls",n_bls)
  
    #copy timestamps over, removing the first element of the array
    print 'Converting timestamps to UNIX time, and copying to output file.'
    tv = fh['timestamp0'].value[:n_ts] #(don't remove first entry, since there seems to be the last entry missing)
    # Convert timestamps
    t_offset = fh.attrs.get('sync_time')
    t_scale_factor = float(fh.attrs.get('adc_clk')/2/fh.attrs.get('seng_acc_len'))
    new_fh.create_dataset('timestamp0', data=(t_offset+tv/t_scale_factor))
    
    ##create EQ subgroup
    #eq_group=new_fh.create_group("EQ")
    #for ds in fh.iterkeys():
    #    if ds.startswith('eq_amp'):
    #        rv=eq_group.create_dataset(ds, data=fh[ds])

    #create an empty dataset to file in with corrected data
    nx = image_shape[0]//2
    ny = image_shape[1]//2
    print 'Creating empty data set'
    sp_shape = (n_ts,n_chans,n_bls,n_stokes,2) #2 for real/imag
    new_fh.create_dataset('xeng_raw0', sp_shape, dtype=float)
    #Create a new dataset for baseline indices

    print 'Creating bl_order attribute...',
    new_fh.create_dataset('bl_order', (n_bls,2), dtype=int)
    bl_order_block = n.zeros([n_ants,2],dtype=int)
    for i in range(n_ants):
        bl_order_block[i] = [0,n_ants - (1+i//ny)*ny + i%ny]
        #print 'appending', [0,n_ants - (1+i//ny)*ny + i%ny]
    new_fh['bl_order'][0:n_ants] = bl_order_block
    bl_order_block = bl_order_block + n.array([ny-1,0])
    new_fh['bl_order'][n_ants:] = bl_order_block.reshape(nx,ny,2)[0:-1,0:-1].reshape((nx-1)*(ny-1),2) #add the top left block
    #print bl_order_block.reshape(nx,ny,2)[0:-1,0:-1].reshape((nx-1)*(ny-1),2) #add the top left block
    print 'done.'

    
    # iFFT the image along the spatial dimensions (leave times,channels and pols intact)
    # Get the unique baselines, and cut off the extra correlations from overpadding with zeros in the hardware spatial fft
    print 'Performing iFFT on data'
    corr = n.fft.fftshift(n.fft.ifft2(fh['seng_raw0'], axes=(2,3)),axes=(2,3))
    fh.flush()
    corr0 = n.conj(corr[:,-1::-1,1:nx+1,ny:,:]) #top right block #flip spectrum #conjugate (to match bl_order)
    corr1 = n.conj(corr[:,-1::-1,1:nx,1:ny,:]) #top left block #flip spectrum #conjugate (to match bl_order)
    del(corr)

    #print corr[0,0,:,:,0].real
    #pylab.pcolor(corr[0,0,:,:,0].real)
    #pylab.colorbar()
    #pylab.show()

    print 'Reshaping data array into list of correlations'
    #print corr0.shape
    #print corr1.shape
    corr0 = corr0.reshape((n_ts,n_chans,n_ants,n_stokes))
    corr1 = corr1.reshape((n_ts,n_chans,(nx-1)*(ny-1),n_stokes))

    print 'Updating output file'
    new_fh['xeng_raw0'][:,:,0:n_ants,:,0] = corr0.real
    new_fh['xeng_raw0'][:,:,0:n_ants,:,1] = corr0.imag
    new_fh['xeng_raw0'][:,:,n_ants:n_ants+((nx-1)*(ny-1)),:,0] = corr1.real
    new_fh['xeng_raw0'][:,:,n_ants:n_ants+((nx-1)*(ny-1)),:,1] = corr1.imag
    
    ##convert data to floats and divide by the number of correlator accumulations
    #acc=n.array(acc,dtype=float)
    #if opts.acc: acc=acc/n_accs

    print 'Closing input/output file'
    fh.close()
    new_fh.close()

