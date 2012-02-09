#! /usr/bin/env python
'''
A script to calculate the antenna gain vector, g, using the 
Column ratio gain estimation (COL) method described in:
"Gain Decomposition Methods for Radio Telescope Arrays"
A.J. Boonstra & A.J. van der Veen
'''

import numpy as n
import pylab
import h5py
import sys
import cPickle as pickle
from optparse import OptionParser

p = OptionParser()
p.set_usage('gaincal.py [options] INST_CONFIG_FILE GAIN_CAL_FILE')
p.set_description(__doc__)
p.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
        help='Print lots of lovely debug information')
p.add_option('-c', '--chan_range', dest='chan_range', default='0_-1',
        help='Calibration fit channel range in form \'<start_chan>_<stop_chan>\'. Default: 0_-1 (i.e. all channels)')
p.add_option('-t', '--time_range', dest='time_range', default='0_-1',
        help='Time range to average before calculating calibration \'<start_time>_<stop_time>\'. Default: 0_-1 (i.e. all times in file)')


opts, args = p.parse_args(sys.argv[1:])

fnames= args
time_start, time_stop = map(int,opts.time_range.split('_'))

#Channels over which to fit corrections
chan_start, chan_stop = map(int,opts.chan_range.split('_'))

# Load the hdf5 data file and perform an average over the time axis (axis 0)
#print 'Loading hdf5 file %s' %(hd5_fname)
#fh = h5py.File(hd5_fname,'r')
#d_all_t = fh['xeng_raw0'][t_range,:,:,0,:]
#d_all_t = d_all_t[:,:,:,1]+d_all_t[:,:,:,0]*1j #complexify
n_files = len(fnames)
for fi, fname in enumerate(fnames):
    print "Opening: %s (%d of %d)" %(fname, fi+1, n_files)
    fh = h5py.File(fname, 'r')
    t = fh.get('timestamp0')
    if fi==0:
        # Get some parameters
        calname = fname+'.cal'
        n_ants = fh.attrs.get('n_ants')
        n_chans= fh.attrs.get('n_chans')
        bl_order = fh['bl_order'][:]
        print 'Number of antennas:', n_ants
        print 'Number of channels:', n_chans
        bl_order = fh['bl_order'].value
        d = fh.get('xeng_raw0')[:,:,:,0,:]
    else: d = n.concatenate((d, fh.get('xeng_raw0')[:,:,:,0,:]))
    fh.close()
d = d[:,:,:,1]+d[:,:,:,0]*1j #complexify
print 'Averaging time range %d - %d' %(time_start, time_stop)
d = n.mean(d[time_start:time_stop,:,:],axis=0)

g = n.zeros(n_ants,dtype=complex)
#Prepare to store as a correlation matrix
R = n.zeros([n_chans,n_ants,n_ants],dtype=complex) 
# Go through the different baselines and populate the matrix
for bl_n, bl in enumerate(bl_order):
    #print 'Populating baseline %d of correlation matrix' %bl_n
    R[:,bl[0],bl[1]] = d[:,bl_n]
    R[:,bl[1],bl[0]] = n.conj(d[:,bl_n])

print 'Using subset of antennas -- TESTING ONLY!!!!'
ant_range = [0,8,16,24,4,12,20,28]
R = R[:,ant_range,:]
R = R[:,:,ant_range]
n_ants = len(R[0][0])
print 'New R matrix shape:', R.shape
print 'New n_ants:', n_ants

#R = R[610] #pick a frequency channel for testing

# Solve the equation c[i] = alpha[i,j]*c[j] by least squares
# where alpha is the ratio between two elements
# of the complex gain vector g, and c is a column
# of the matrix R.
# See "Gain Decomposition Methods for Radio Telescope Arrays"
# A.J. Boonstra & A.J. van der Veen

Niter = 1
for iter_n in range(Niter):
    print 'Iteration %d' %iter_n
    print 'Solving for alpha'
    
    alpha = n.zeros_like(R)
    a = n.zeros_like(R)
    b = n.zeros_like(R)
    
    for i in range(n_ants):
        for j in range(n_ants):
            if i!=j:
                for k in range(n_ants):
                    if ((k!=i) and (k!=j)):
                        a[:,i,j] += (n.conj(R[:,k,i])*R[:,k,j])
                        b[:,i,j] += (n.conj(R[:,k,i])*R[:,k,i])
    
    alpha = a/b
    
    print 'Estimating |g[i]|^2'
    
    # Estimate |g[i]|^2
    mod_g_squared = n.zeros([n_chans,n_ants,n_ants])
    for i in range(n_ants):
        for j in range(n_ants):
            if i!=j:
                mod_g_squared[:,i,j] = n.real(alpha[:,i,j]*n.conj(R[:,i,j]))
    #print mod_g_squared
    
    # Average over all columns
    mod_g_squared = n.sum(mod_g_squared, axis=2)/(n_ants-1.)
    #TODO Make script able to calculate coefficients based on subsets of antennas
    
    # Replace the diagonal elements in R with the mod_g_squared values
    # (The existing entries have a noise term, independent of the antenna
    # g is estimated as: g = u[1]*sqrt(lamda[1])
    # where lamda[1] is the largest eigenvalue, and u[1] the corresponding
    #vector
    
    print 'Finding Eigenvalues'
    R[n.isnan(R)]=0.0
    V = n.zeros_like(R)
    W = n.zeros([n_chans,n_ants],dtype=complex)
    for chan in range(n_chans):
        W[chan],V[chan] = n.linalg.eig(R[chan])
    #print W,V
    #print W
    
    print 'Finding Largest Eigenvalue'
    lamda_max = n.zeros(n_chans,dtype=complex)
    eig_vec_max = n.zeros([n_chans,n_ants],dtype=complex)
    for chan in range(n_chans):
        lamda_max_index = 0
        for i in range(n_ants):
            if W[chan,i] > lamda_max[chan]:
                lamda_max[chan] = W[chan,i]
                lamda_max_index = i
        eig_vec_max[chan] = V[chan,:,lamda_max_index]
    
    print 'Largest Eigenvalue:', lamda_max
    #print 'Corresponding Eigenvector:', eig_vec_max
    
    # Finally, return the estimated gain vector
    g = n.zeros([n_chans,n_ants],dtype=complex)
    for chan in range(n_chans):
        #g[chan,:] = eig_vec_max[chan,:]*n.sqrt(lamda_max[chan]) #Scale by the eigenvalue if you want powers to be calibrated to unity
        g[chan,:] = eig_vec_max[chan,:]*n.sqrt(n_ants) #eigenvectors are normalised, so multiply by sqrt(32) to make mean power correction unity

    # Only use coefficients in the useful channel range. Outside this range just use the coefficients from the edges of the good band
    for ant in range(n_ants):
        g[0:chan_start,ant] = g[chan_start,ant]
        g[chan_stop:,ant] = g[chan_stop,ant]
    #print g[610]
    g[g==0]=1

    f = open(calname+'.pkl', 'w')
    pickle.dump(g,f)
    f.close()
    
    print 'Correcting R matrix'
    Rc = n.zeros_like(R)
    for i in range(n_ants):
        for j in range(n_ants):
            Rc[:,i,j] = R[:,i,j] / g[:,i] / n.conj(g[:,j])
    #R=Rc

##plot the amp corrections as a function of frequency
#pylab.figure(12)
#for ant in range(n_ants):
#    pylab.plot(n.abs(g[:,ant]), '+')
#    fit_coeffs = n.polyfit(n.arange(fit_start,fit_stop), g[fit_start:fit_stop,ant], 4)
#    fit = n.polyval(fit_coeffs, n.arange(n_chans))
#    pylab.plot(n.abs(fit))



test_chan=610 #For plotting

pylab.figure(0)
pylab.subplot(2,2,1)
pylab.title('Phase Before Correction (chan %d)' %test_chan)
pylab.pcolor(n.angle(R[test_chan]))
pylab.colorbar()
pylab.subplot(2,2,2)
pylab.title('Amp Before Correction (chan %d)' %test_chan)
pylab.pcolor(n.abs(R[test_chan]))
pylab.colorbar()
pylab.subplot(2,2,3)
pylab.title('Phase After Correction (chan %d)' %test_chan)
pylab.pcolor(n.angle(Rc[test_chan]))
pylab.colorbar()
pylab.subplot(2,2,4)
pylab.title('Amp After Correction (chan %d)' %test_chan)
pylab.pcolor(n.abs(Rc[test_chan]))
pylab.colorbar()

#pylab.figure(1)
#pylab.subplot(2,2,1)
#pylab.title('Phase Before Correction (chan %d)' %test_chan)
#pylab.plot(n.angle(R[test_chan]).flatten())
#pylab.subplot(2,2,2)
#pylab.title('Amp Before Correction (chan %d)' %test_chan)
#pylab.plot(n.abs(R[test_chan]).flatten())
#pylab.subplot(2,2,3)
#pylab.title('Phase After Correction (chan %d)' %test_chan)
#pylab.plot(n.angle(Rc[test_chan]).flatten())
#pylab.subplot(2,2,4)
#pylab.title('Amp After Correction (chan %d)' %test_chan)
#pylab.plot(n.abs(Rc[test_chan]).flatten())
pylab.show()

