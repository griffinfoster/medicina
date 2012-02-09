#! /usr/bin/env python

import numpy, pylab, sys
import poxy

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('seng_init.py [options] CONFIG_FILE')
    p.set_description(__doc__)

    opts, args = p.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify an antenna array configuration file! \nExiting.'
        exit()

    print 'Loading configuration file...',
    array = poxy.ant_array.Array(args[0])

    xpos = numpy.zeros(array.n_ants)
    ypos = numpy.zeros(array.n_ants)
    for a in range(array.n_ants):
        pos = array.loc(a)
        xpos[a] = pos[0]
        ypos[a] = pos[1]

    plot_size = numpy.max([xpos.max(),ypos.max()])*1.2
    
    pylab.scatter(xpos,ypos,c='b')
    pylab.scatter(0,0,c='r',s=400,marker=[6,1,0])
    pylab.annotate('%s\n%s' %(array.ref_ant.position.lat, array.ref_ant.position.long), (2,2))
    for a in range(array.n_ants):
        pylab.annotate(array.ants[a].name, (xpos[a],ypos[a]))
    #pylab.xlim(-plot_size,plot_size)
    #pylab.ylim(-plot_size,plot_size)
    pylab.show()
