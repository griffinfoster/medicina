#!/usr/bin/python
"""Reweight the Medicina baselines based on redundancy applying a baseline cal"""

import numpy
import sys
from pyrap.tables import *

"""Medicina specific"""
nants=32
weights=numpy.zeros((nants,nants))
weights[0,1]=24
weights[0,2]=16
weights[0,3]=8
weights[0,4]=28
weights[0,5]=21
weights[0,6]=14
weights[0,7]=7
weights[0,8]=24
weights[0,9]=18
weights[0,10]=12
weights[0,11]=6
weights[0,12]=20
weights[0,13]=15
weights[0,14]=10
weights[0,15]=5
weights[0,16]=16
weights[0,17]=12
weights[0,18]=8
weights[0,19]=4
weights[0,20]=12
weights[0,21]=9
weights[0,22]=6
weights[0,23]=3
weights[0,24]=8
weights[0,25]=6
weights[0,26]=4
weights[0,27]=2
weights[0,28]=4
weights[0,29]=3
weights[0,30]=2
weights[0,31]=1
weights[3,4]=7
weights[3,5]=14
weights[3,6]=21
weights[3,8]=6
weights[3,9]=12
weights[3,10]=18
weights[3,12]=5
weights[3,13]=10
weights[3,14]=15
weights[3,16]=4
weights[3,17]=8
weights[3,18]=12
weights[3,20]=3
weights[3,21]=6
weights[3,22]=9
weights[3,24]=2
weights[3,25]=4
weights[3,26]=6
weights[3,28]=1
weights[3,29]=2
weights[3,30]=3

if __name__ == '__main__':                                                                                                                          
    from optparse import OptionParser
    p = OptionParser()
    p.set_usage('%prog [options] MS_FILE')
    p.set_description(__doc__)
    opts, args = p.parse_args(sys.argv[1:])

    for i in args:
        print "Reweighting CORRECTED_DATA:",i
        ms = table(i,readonly=False)
        dd=ms.getcol('CORRECTED_DATA')
        ant1=ms.getcol('ANTENNA1')
        ant2=ms.getcol('ANTENNA2')
        for aid,a in enumerate(ant1):
            if ant1[aid]==ant2[aid]: w=weights[ant1[aid],ant2[aid]]
            elif ant1[aid]<ant2[aid]: w=weights[ant1[aid],ant2[aid]]
            elif ant1[aid]>ant2[aid]: w=weights[ant2[aid],ant1[aid]]
            dd[aid]=dd[aid]*w
        ms.putcol('CORRECTED_DATA',dd)
        ms.close()

