#!/usr/bin/python
"""Fix MS wieghts column after converting from a FITS-IDI file"""

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
        print "Correcting Weights for:",i
        ms = table(i,readonly=False)
        ws=ms.col('WEIGHT_SPECTRUM')
        ws_data=ws.getcol()
        ws_data=numpy.ones_like(ws_data)
        ms.putcol('WEIGHT_SPECTRUM', ws_data)
        ms.close()

