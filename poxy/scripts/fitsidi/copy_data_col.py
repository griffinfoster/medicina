#!/usr/bin/python
"""Copy the DATA column to a CORRECT_DATA column"""

import numpy
import sys
from pyrap.tables import *

if __name__ == '__main__':                                                                                                                          
    from optparse import OptionParser
    p = OptionParser()
    p.set_usage('%prog [options] MS_FILE')
    p.set_description(__doc__)
    opts, args = p.parse_args(sys.argv[1:])

    for i in args:
        print "Copying DATA -> CORRECTED_DATA:",i
        ms = table(i,readonly=False)
        data=ms.col('DATA')
        dd=data.getcol()
        ms.putcol('CORRECTED_DATA',dd)
        #ws=ms.col('WEIGHT_SPECTRUM')
        #ws_data=ws.getcol()
        #ws_data=numpy.ones_like(ws_data)
        #ms.putcol('WEIGHT_SPECTRUM', ws_data)
        ms.close()

