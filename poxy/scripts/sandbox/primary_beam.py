#! /usr/bin/env python
import numpy as n
import pylab

Dx = 4.
Dy = 4.
pi = n.pi
lamda = 3e8/408e6
k = 2*pi/lamda

max_theta = 30. #Theta range to plot in degrees
#max_theta = max_theta*(pi/180.)

x_range = n.arange(-10,10,0.1,dtype=float)
y_range = n.arange(-10,10,0.1,dtype=float)
n_xs = len(x_range)
n_ys = len(y_range)

h = x_range[-1]/n.tan(max_theta*(pi/180)) # h scale to turn x,y into angles
theta_range = n.arange(-max_theta,max_theta,2*max_theta/float(n_xs))

a = n.zeros([n_xs,n_ys])
ax = n.sinc(Dx*k*(x_range/n.sqrt(h**2 + x_range**2))/2/pi) #n.sinc(x) is defined as sin(pi*x)/(pi*x)
ay = n.sinc(Dy*k*(y_range/n.sqrt(h**2 + y_range**2))/2/pi)

#sinc_arg_range = Dx*k*(x_range/n.sqrt(h**2 + x_range**2))/2
for x in range(n_xs):
    a[x] = ax[x]*ay

a = a**2
pylab.figure(0)
pylab.pcolor(theta_range,theta_range,a)
pylab.xlim(theta_range[0],theta_range[-1])
pylab.ylim(theta_range[0],theta_range[-1])
pylab.colorbar()

#pylab.figure(1)
#pylab.plot(theta_range,10*n.log10(a[n_xs/2]))
pylab.show()



