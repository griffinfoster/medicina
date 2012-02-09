#! /usr/bin/env python

import numpy as n
import pylab
import ant_array
import os,sys

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('seng_init.py [options] CONFIG_FILE')
    p.set_description(__doc__)

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify an antenna array configuration file! \nExiting.'
        exit()

    print 'Loading configuration file %s' %(args[0])
    array = ant_array.Array(args[0])

    pi = n.pi

    pos = n.zeros([array.n_ants,2])
    for a in range(array.n_ants):
        pos[a,:] = array.loc(a)[0:2]

    k = 2*pi #We measure antenna positions in units of wavelength

    x_range = n.arange(-50,50,0.2, dtype=float)
    y_range = n.arange(-50,50,0.2, dtype=float)
    ### Get rid of zeros to save some headaches during divisions
    x_range[x_range==0] = 1e-12
    y_range[y_range==0] = 1e-12
    n_xs = len(x_range)
    n_ys = len(y_range)
    
    max_angle = 8. #degrees at edge of plot
    h = x_range[-1]/n.tan(max_angle*(pi/180.))

    theta_range = n.zeros([len(x_range),len(y_range)])
    phi_range   = n.zeros([len(x_range),len(y_range)])

    for xn,x in enumerate(x_range):
        theta_range[xn,:] = n.arctan(n.sqrt(x**2+y_range**2)/h)

    for xn,x in enumerate(x_range):
        phi_range[xn,:] = n.arctan(y_range/x)

    response = n.zeros([len(x_range),len(y_range)], dtype=float)
    x_response = n.zeros([len(x_range)],dtype=complex)
    y_response = n.zeros([len(y_range)],dtype=complex)

    for xn,x in enumerate(x_range):
        print 'Calculating x slice %d of %d' %(xn+1,n_xs)
        angle_vec = n.array([n.sin(theta_range[xn,n_ys/2])*n.cos(phi_range[xn,n_ys/2]), n.sin(theta_range[xn,n_ys/2])*n.sin(phi_range[xn,n_ys/2])]) #y=0 slice
        for antpos in pos:
            x_response[xn] += n.exp(1j*k*n.sum(antpos*angle_vec))
    for yn,y in enumerate(y_range):
        print 'Calculating y slice %d of %d' %(yn+1,n_ys)
        angle_vec = n.array([n.sin(theta_range[n_xs/2,yn])*n.cos(phi_range[n_xs/2,yn]), n.sin(theta_range[n_xs/2,yn])*n.sin(phi_range[n_xs/2,yn])]) #x=0 slice
        for antpos in pos:
            y_response[yn] += n.exp(1j*k*n.sum(antpos*angle_vec))

    #pylab.figure(3)
    #pylab.plot(n.abs(x_response))
    #pylab.plot(n.abs(y_response))
    

    # Calculate power and normalise
    #print response.shape
    for xn in range(n_xs):
        response[xn,:] = n.abs(x_response[xn]*y_response)/len(pos)**2

    #pylab.figure(0)
    #pylab.plot(response[n_xs/2,:])
    #pylab.plot(response[:,n_ys/2])
    angle_plot_range = n.append(-theta_range[n_xs/2][:n_xs/2],theta_range[n_xs/2][n_xs/2:])
    angle_plot_range = angle_plot_range * 180./pi
    pylab.figure(0)
    pylab.pcolor(angle_plot_range,angle_plot_range,response.transpose())
    pylab.xlim(angle_plot_range[0],angle_plot_range[-1])
    pylab.ylim(angle_plot_range[0],angle_plot_range[-1])
    pylab.xlabel('Degrees from zenith (with flat sky)')
    pylab.ylabel('Degrees from zenith (with flat sky)')
    pylab.colorbar()
    pylab.show()

