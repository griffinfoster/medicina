#!/usr/bin/env python
"""
Takes an hd5 file containing spatial image data and iffts / cuts redundant pixels to return an hd5 containing
the correlation matrix (with no redundant baselines)
"""

import numpy as n
import math, time, h5py, sys
import pylab

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

eqrewire = {
    0:0,   8:1,  16:2,  24:3,
    4:4,  12:5,  20:6,  28:7,
    1:8,   9:9,  17:10, 25:11,
    5:12, 13:13, 21:14, 29:15,
    2:16, 10:17, 18:18, 26:19,
    6:20, 14:21, 22:22, 30:23,
    3:24, 11:25, 19:26, 27:27,
    7:28, 15:29, 23:30, 31:31  }
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

    #create EQ subgroup, rename EQs to single pol
    eq_group=new_fh.create_group("EQ")
    for ds in fh.iterkeys():
        if ds.startswith('eq_amp_coeff'):
            if ds.startswith('eq_amp_coeff_cal'):
                prefix='eq_amp_coeff_cal_'
            elif ds.startswith('eq_amp_coeff_bandpass'):
                prefix='eq_amp_coeff_bandpass_'
            elif ds.startswith('eq_amp_coeff_base'):
                prefix='eq_amp_coeff_base_'
            else:
               prefix='eq_amp_coeff_'

            ant=int(ds.split('_')[-1][:-1])
            if ds[-1] == 'y': print "WHOA! Y-pol EQ value found in", ds
            ant=eqrewire[ant]
            new_key = prefix + '%ix'%ant
            rv=eq_group.create_dataset(new_key, data=fh[ds])
        elif ds.startswith('eq_phs_coeff'):
            if ds.startswith('eq_phs_coeff_cal'):
                prefix='eq_phs_coeff_cal_'
            elif ds.startswith('eq_phs_coeff_bandpass'):
                prefix='eq_phs_coeff_bandpass_'
            elif ds.startswith('eq_phs_coeff_base'):
                prefix='eq_phs_coeff_base_'
            else:
               prefix='eq_phs_coeff_'

            ant=int(ds.split('_')[-1][:-1])
            if ds[-1] == 'y': print "WHOA! Y-pol EQ value found in", ds
            ant=eqrewire[ant]
            new_key = prefix + '%ix'%ant
            rv=eq_group.create_dataset(new_key, data=fh[ds])
        elif ds.startswith('eq_amp'):
            rv=eq_group.create_dataset(ds, data=fh[ds])

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
    #t_scale_factor = float(fh.attrs.get('adc_clk')/2/fh.attrs.get('seng_acc_len'))
    t_scale_factor = fh.attrs.get('scale_factor_timestamp')
    new_fh.create_dataset('timestamp0', data=(t_offset+tv/t_scale_factor))
    #Since we now have unix times -- set the offset to 0, and scale factor to 1 in the new file.
    #This way, if any future scripts try and convert the times to unix, they will not mess them up
    new_fh.attrs['scale_factor_timestamp'] = 1.0
    new_fh.attrs['sync_time'] = 0.0
    
    #create an empty dataset to file in with corrected data
    nx = image_shape[0]//2
    ny = image_shape[1]//2
    print 'Creating empty data set'
    sp_shape = (n_ts,n_chans,n_bls,n_stokes,2) #2 for real/imag
    new_fh.create_dataset('xeng_raw0', sp_shape, dtype=float)
    #Create a new dataset for baseline indices

    print 'Creating bl_order attribute...',
    bl_matrix= n.zeros([2*nx, 2*ny,2])
    for x in range(nx):
        for y in range(ny):
            # Fill the matrix, with the prefered reference values added last
            # Fill top left corner of matrix
            bl_matrix[nx+x,ny-y] = [x,ny-1-y]
            # Fill top right corner of matrix -- these are baselines relative to bottom left corner (ant 0)
            bl_matrix[nx+x,ny+y] = [x,y]

    print bl_matrix

    #bl_matrix[bl_matrix[:,:,0]<0] = bl_matrix[bl_matrix[:,:,0]<0] + nx-1
    #bl_matrix[bl_matrix[:,:,1]<0] = bl_matrix[bl_matrix[:,:,1]<0] + ny-1
    #print bl_matrix

    bl0 = ny*bl_matrix[nx:,ny:,0] + bl_matrix[nx:,ny:,1]       #top right 
    bl1 = ny*bl_matrix[nx+1:,1:ny,0] + bl_matrix[nx+1:,1:ny,1] #top left

    print bl0
    print bl1

    bl0 = bl0.reshape(n_ants)
    bl1 = bl1.reshape((nx-1)*(ny-1))

    print bl0
    print bl1

    new_fh.create_dataset('bl_order', (n_bls,2), dtype=int)
    new_fh['bl_order'][0:n_ants,0] = 0
    new_fh['bl_order'][0:n_ants,1] = bl0  #After the FFT the top right data will need conjugating
    new_fh['bl_order'][n_ants:,0] = ny-1  #After the FFT the bottom left data Will need conjugating
    new_fh['bl_order'][n_ants:,1] = bl1
    print 'done.'

    
    # iFFT the image along the spatial dimensions (leave times,channels and pols intact)
    # Get the unique baselines, and cut off the extra correlations from overpadding with zeros in the hardware spatial fft
    print 'Performing iFFT on data'
    corr = n.fft.fftshift(n.fft.ifft2(fh['seng_raw0'], axes=(2,3)),axes=(2,3))
    #pylab.figure()
    #pylab.subplot(2,2,1)
    #pylab.pcolor(n.abs(corr[450,600,:,:,0]))
    #pylab.colorbar()
    #pylab.subplot(2,2,2)
    #pylab.pcolor(n.angle(corr[450,600,:,:,0]))
    #pylab.colorbar()
    #pylab.subplot(2,2,3)
    #pylab.pcolor(n.real(corr[450,600,:,:,0]))
    #pylab.colorbar()
    #pylab.subplot(2,2,4)
    #pylab.pcolor(n.imag(corr[450,600,:,:,0]))
    #pylab.colorbar()


    fh.flush()
    corr0 = n.conj(corr[:,-1::-1,nx:,ny:,:])    #top right block #flip spectrum #conjugate (to match bl_order)
    corr1 = n.conj(corr[:,-1::-1,nx+1:,1:ny,:]) #top left block #flip spectrum #conjugate
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
    # 0 Imag!!!
    # 1 Real (seriously, who does that)
    new_fh['xeng_raw0'][:,:,0:n_ants,:,1] = corr0.real
    new_fh['xeng_raw0'][:,:,0:n_ants,:,0] = corr0.imag
    new_fh['xeng_raw0'][:,:,n_ants:n_ants+((nx-1)*(ny-1)),:,1] = corr1.real
    new_fh['xeng_raw0'][:,:,n_ants:n_ants+((nx-1)*(ny-1)),:,0] = corr1.imag
    
    ##convert data to floats and divide by the number of correlator accumulations
    #acc=n.array(acc,dtype=float)
    #if opts.acc: acc=acc/n_accs

    print 'Closing input/output file'
    fh.close()
    new_fh.close()

    #pylab.show()
