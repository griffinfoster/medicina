#!/usr/bin/env python
"""
Takes an hd5 file containing spatial image data and iffts, phases, and re-ffts back to image space, with the aim of moving the
central synthesized beam to coincide with the centre of the primary beam.
"""

import numpy as n
import math, time, h5py, sys, os
import poxy
import pylab

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options]  ARRAY_CONFIG_FILE *.h5')
    o.set_description(__doc__)
    o.add_option('-d', '--dec', dest='dec', default=0.0, type='float',
        help='Target declination of central beam in degrees. Default = 0.0')
    o.add_option('-r', '--ra', dest='ra', default=0.0, type='float',
        help='RA correction in degrees. Default = 0.0')
    opts, args = o.parse_args(sys.argv[1:])
    if len(args)<2:
        print 'Please specify an array xml file and an hdf5 file! \nExiting.'
        exit()
    else:
        print 'Loading configuration file %s ...' %args[0],
        array = poxy.ant_array.Array(args[0])
        print 'done'
        h5fns = args[1:]

dec = opts.dec

# By default (if hardware steering is not supported), the central beam points to the zenith.
# Use the array location information to turn this into a dec

array_lat, array_lon = array.get_ref_loc()
zenith = array_lat #in degrees
point_dir_deg = zenith-opts.dec  #pointing direction relative to zenith with 0 = zenith
point_dir = n.deg2rad(point_dir_deg)
print 'Declination of zenith:', zenith
print 'Pointing declination:', dec
print 'Pointing direction relative to broadside (degrees):', point_dir_deg

ra_corr_deg = opts.ra
ra_corr = n.deg2rad(ra_corr_deg)
print 'RA correction (degrees):', ra_corr_deg

# Calculate the trig factor corresponding to this pointing
trig_factor = n.sin(point_dir)

# Antenna position unit, relating positions in the config file to m.
fudge = 1.006
c = 299792458.0
ant_pos_unit = fudge*c/408e6 #Wavelengths at 408MHz

# Create the array of phases
path_diff_by_ant= n.zeros(array.n_ants) #Path delays in m
for ant in range(array.n_ants):
    x,y,z = array.loc(ant)
    path_diff_by_ant[ant] = array.loc(ant)[1]*ant_pos_unit*trig_factor
    #print 'antenna:',ant,'path diff', array.loc(ant)[1]

#TODO read these from the data file
obs_freq =  408e6
n_chans = 1024
n_stokes = 1
bw = 40e6/2
start_f = obs_freq - (bw/2)
df = bw/n_chans
ants_x = 4
ants_y = 8
dx = (-26.8875321 - (-34.8875321)) * ant_pos_unit * trig_factor #convert to m
dy = (20.414123 - 6.804708       ) * ant_pos_unit * trig_factor #convert to m

freqs = n.arange(start_f,start_f+bw,df)
wavelengths = 3e8/freqs
# Flip wavelength vector because medicina spectra are inverted
wavelengths = wavelengths[::-1]


print 'Calculating phase weight matrix...',
phase_weights = n.zeros([2*ants_y, 2*ants_x,  n_chans], dtype=complex)
for ant_y in range(ants_y):
    for ant_x in range(ants_x):
        #TODO make this generic -- not just duitable for shifting dec
        #phases_tr = -2*n.pi*(ant_y*dy)/wavelengths #negative, since we want to compensate for the path differences
        phases_tr = -2*n.pi*(ant_y*dy*n.cos(ra_corr) + ant_x*dx*n.sin(ra_corr))/wavelengths
        phases_tl = -2*n.pi*(ant_y*dy*n.cos(ra_corr) + -ant_x*dx*n.sin(ra_corr))/wavelengths
        phases_br = -2*n.pi*(-ant_y*dy*n.cos(ra_corr) + ant_x*dx*n.sin(ra_corr))/wavelengths
        phases_bl = -2*n.pi*(-ant_y*dy*n.cos(ra_corr) + -ant_x*dx*n.sin(ra_corr))/wavelengths
        # Fill top right corner of matrix
        phase_weights[ants_y + ant_y][ants_x + ant_x] = (n.cos(phases_tr)+n.sin(phases_tr)*1j)
        # Fill top left corner of matrix
        phase_weights[ants_y + ant_y][ants_x - ant_x] = (n.cos(phases_tl)+n.sin(phases_tl)*1j)
        # Fill bottom right corner of matrix
        phase_weights[ants_y - ant_y][ants_x + ant_x] = (n.cos(phases_br)+n.sin(phases_br)*1j)
        # Fill bottom left corner of matrix
        phase_weights[ants_y - ant_y][ants_x - ant_x] = (n.cos(phases_bl)+n.sin(phases_bl)*1j)
        
phase_weights = n.transpose(phase_weights, axes=(2,0,1)).reshape(n_chans, 2*ants_y, 2*ants_x, n_stokes)
pylab.pcolor(n.angle(phase_weights[600,:,:,0]))
pylab.colorbar()
print 'done'

n_files = len(h5fns)
for N,fn in enumerate(h5fns):
    print '##### Processing file %s (File %d of %d) #####' %(fn,N+1,n_files)
    new_fn = fn + ".dec%.1f" %dec

    #copy over attributes
    print 'Copying file...',
    os.system('cp -p %s %s' %(fn,new_fn)) #Copy the hd5 file
    fh = h5py.File(fn,'r')
    new_fh = h5py.File(new_fn,'r+')
    print 'done'

    #for a in fh.attrs.iteritems():
    #    new_fh.attrs.create(a[0], a[1])

    print 'Getting image file parameters'
    n_ants = fh.attrs.get('n_ants')
    n_chans = fh.attrs.get('n_chans')
    image_shape = fh.attrs.get('image_shape')
    n_ts = len(fh['seng_raw0'])

    if n_chans == None:
        print 'nchans unspecified, defaulting to 1024'
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
    n_stokes = fh.attrs.get('n_stokes')
    n_accs = fh.attrs.get('n_accs')
  
    ##copy timestamps over, removing the first element of the array
    #print 'Copying timestamps to output file.'
    #tv = fh['timestamp0'].value[:n_ts] #(don't remove first entry, since there seems to be the last entry missing)
    
    # iFFT the image along the spatial dimensions (leave times,channels and pols intact)
    # Get the unique baselines, and cut off the extra correlations from overpadding with zeros in the hardware spatial fft
    pylab.figure()
    pylab.subplot(2,1,1)
    pylab.title('original image')
    pylab.pcolor(n.fft.fftshift(n.abs(fh['seng_raw0'][0,600,:,:,0])))
    pylab.colorbar()
    pylab.subplot(2,1,2)
    pylab.pcolor(n.angle(n.fft.fftshift(fh['seng_raw0'][0,600,:,:,0])))
    pylab.colorbar()
    print 'Performing iFFT on data'
    #print 'original shape', fh['seng_raw0'].shape
    corr = n.fft.fftshift(n.fft.ifft2(fh['seng_raw0'], axes=(2,3)),axes=(2,3))
    pylab.figure()
    pylab.subplot(2,1,1)
    pylab.title('After iFFT -> correlations')
    pylab.pcolor(n.abs(corr[0,600,:,:,0]))
    pylab.colorbar()
    pylab.subplot(2,1,2)
    pylab.pcolor(n.angle(corr[0,600,:,:,0]))
    pylab.colorbar()
    print 'Multiplying by phase corrections'
    #print 'corr shape', corr.shape
    #print 'weights shape', phase_weights.shape
    corr = corr*phase_weights
    pylab.figure()
    pylab.subplot(2,1,1)
    pylab.title('After phase weight multiplication')
    pylab.pcolor(n.abs(corr[0,600,:,:,0]))
    pylab.colorbar()
    pylab.subplot(2,1,2)
    pylab.pcolor(n.angle(corr[0,600,:,:,0]))
    pylab.colorbar()
    #print corr.shape
    print 'Returning to image space'
    corr = n.fft.fft2(corr, axes=(2,3))
    pylab.figure()
    pylab.subplot(2,2,1)
    pylab.title('After fft back to image space')
    pylab.pcolor(n.abs(corr[0,600,:,:,0]))
    pylab.colorbar()
    pylab.subplot(2,2,2)
    pylab.pcolor(n.angle(corr[0,600,:,:,0]))
    pylab.colorbar()
    pylab.subplot(2,2,3)
    pylab.pcolor(n.real(corr[0,600,:,:,0]))
    pylab.colorbar()
    pylab.subplot(2,2,4)
    pylab.pcolor(n.imag(corr[0,600,:,:,0]))
    pylab.colorbar()
    #print corr.shape
    print 'Writing to disk'

    new_fh['seng_raw0'][:,:,:,:,:] = n.abs(corr)

    print 'Closing input/output file'
    fh.close()
    new_fh.close()
#pylab.show()

