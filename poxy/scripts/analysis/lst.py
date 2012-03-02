#!/usr/bin/python
"""
Output LST, Julian date, and Sun position at the provided location
"""

import sys, optparse, ephem

o = optparse.OptionParser()
o.set_usage('lst [options] jd1 jd2 ...')
o.set_description(__doc__)
o.add_option('--lat', dest='lat', default=50.0, type='float',
    help='Latitude in degrees, Default: 50.0')
o.add_option('--lon', dest='lon', default=0.0, type='float',
    help='Longitude in degrees, Default: 0.0')
opts, args = o.parse_args(sys.argv[1:])

def juldate2ephem(num):
    """Convert Julian date to ephem date, measured from noon, Dec. 31, 1899."""
    return ephem.date(num - 2415020.)

def ephem2juldate(num):
    """Convert ephem date (measured from noon, Dec. 31, 1899) to Julian date."""
    return float(num + 2415020.)

sun=ephem.Sun()
obs=ephem.Observer()
obs.long=opts.lon*(ephem.pi/180.)
obs.lat=opts.lat*(ephem.pi/180.)
obs.epoch=2000.0

if len(args) == 0: args = [ephem.julian_date()]
for jd in map(float, args):
    obs.date=juldate2ephem(jd)
    sun.compute(obs)
    print 'LST:', obs.sidereal_time(),
    ra=obs.sidereal_time()
    print '(',(ra.real/(ephem.pi))*180.,')',
    print '     Julian Date:', jd,
    print '     Day:', obs.date
    print 'Sun is at (RA, DEC):', str((str(sun.ra), str(sun.dec)))

