#! /usr/bin/env python
'''
A script to automatically switch beams, to follow a source
'''

import numpy as np
import sys,os
import ephem,time
import pylab
import poxy

def juldate2ephem(num):
    """Convert Julian date to ephem date, measured from noon, Dec. 31, 1899."""
    return ephem.date(num - 2415020.)

def ephem2juldate(num):
    """Convert ephem date (measured from noon, Dec. 31, 1899) to Julian date."""
    return float(num + 2415020.)

def rotate_about_x(theta,x):
    M = np.array([[1,0,0],[0, np.cos(theta), -np.sin(theta)], [0, np.sin(theta), np.cos(theta)]])
    return np.dot(M,x)

def plot_centres(x_centres,y_centres,x_chosen,y_chosen):
    # plot the positions of the beam centres
    for xn,x_beam in enumerate(x_centres_pc):
        for yn,y_beam in enumerate(y_centres_pc):
            if xn==x_chosen and yn==y_chosen:
                pylab.scatter(np.rad2deg(x_beam),np.rad2deg(y_beam), c='b', marker='o', label=None)
            else:
                pylab.scatter(np.rad2deg(x_beam),np.rad2deg(y_beam), c='r', marker='o', label=None)

def plot_src(src_pos_list, name=None):
    pylab.scatter(np.rad2deg(src_pos_list[:,0]), np.rad2deg(src_pos_list[:,1]), s=80, c='g', marker=(6,1,0), label=name)

if __name__ == '__main__':
    from optparse import OptionParser

    p = OptionParser()
    p.set_usage('seng_track.py [options] [SOURCE_OBS_FILE(s)]')
    p.set_description(__doc__)
    p.add_option('-d', '--dec', type='string', dest='dec', default='zenith',
            help='The declination at which the telescope is pointed <XX:XX:XX.X> or \'zenith\' Default:zenith')
    p.add_option('-s', '--sleep_time', dest='sleep_time', default=10,
            help='Number of seconds between passes of pointing checking. Default:10')
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
            help='Print lots of lovely debug information')
    p.add_option('-A', '--ant_config', dest='ant_config', default=os.environ['ANTCONFIG'],
            help='.xml file containing antenna configuration. Default is $ANTCONFIG=%s'%os.environ['ANTCONFIG'])
    p.add_option('-I', '--inst_config', dest='inst_config', default=os.environ['ROACHCONFIG'],
            help='.xml file containing instrument configuration. Default is $ROACHCONFIG=%s'%os.environ['ROACHCONFIG'])

    opts, args = p.parse_args(sys.argv[1:])

    if len(args)<1:
        print 'Please specify at least one source file for tracking! \nExiting.'
        exit()
    else:
        srcs = []
        print '########################################'
        for source_xml in args:
            print 'Parsing source file:', source_xml
            src = poxy.xmlParser.xmlObject(source_xml).xmlobj
            name = src.name
            ra = ephem.hours(str(src.ra))
            dec = ephem.degrees(str(src.dec))
            epoch = 2000
            flux = 0.0
            print 'Source: %s, RA:%s DEC:%s'%(name,ra,dec)
            ephemline = '%s,f,%s,%s,%f,%d'%(name,ra,dec,flux,epoch)
            srcs.append(ephem.readdb(ephemline))
        # Initialise the beams to (-1,-1), which will get updated
        # on the first pass of the pointing loop later
        src_beams = -1*np.ones([len(srcs),2])
        print '########################################'
    
    print 'Loading configuration file...', opts.ant_config
    array = poxy.ant_array.Array(opts.ant_config)
    
    seng=poxy.medInstrument.sEngine(opts.inst_config,program=False)
    fConf = seng.fConf
    sConf = seng.sConf
    print '########################################'

    # For the purposes of calculating zenith direction, a
    # assume all antennas have the same lat as the reference
    array_lat, array_lon = array.get_ref_loc()

    zenith = np.deg2rad(array_lat)
    if opts.dec.startswith('z'):
        point_dec = zenith
    else:
        point_dec = ephem.degrees(opts.dec)
    pointing_rotation = zenith-point_dec
    point_zen_dist = abs(pointing_rotation)
    print 'Zenith is at %.2f degrees' %np.rad2deg(zenith)
    print 'Pointing declination is %.2f degrees' %np.rad2deg(point_dec)
    print 'Pointing zenith distance is %.2f degrees' %np.rad2deg(point_zen_dist)

    array_proj_factor = np.cos(point_zen_dist)
    print 'Array projection factor at observing altitude is %.2f' %array_proj_factor

    grid_x = sConf.grid.x_dim
    grid_y = sConf.grid.y_dim

    #But because of zero padding, there are twice this number of beams
    beams_x = 2*grid_x
    beams_y = 2*grid_y

    print 'Array has dimensions %d x %d' %(grid_x,grid_y)

    # Beam centres are at k.d.sin(theta) = n.2pi/2N  n=[0,1,2,...,N-1]
    # Here we ignore the fact that different frequency channels have different
    # beam centres.
    c = 3e8
    k = 2*np.pi #*array.receiver.center_freq*1e6/c #we measure d in wavelengths, so k is normalized to 2pi
    dx = array.grid.x_spacing
    dy = array.grid.y_spacing*array_proj_factor #The grid must be projected to the relevant dec

    x_spacing = 2*np.pi/k/dx/float(beams_x)
    y_spacing = 2*np.pi/k/dy/float(beams_y)

    # Calculate the centres of the beams in sin(theta) space
    x_centres = np.arange(beams_x,dtype=float)*2*np.pi/k/dx/float(beams_x)
    y_centres = np.arange(beams_y,dtype=float)*2*np.pi/k/dy/float(beams_y)

    # Calculate the positions relative to point centre, with equal numbers of beams
    # each side of the middle
    x_centres_pc = np.zeros(beams_x+1)
    y_centres_pc = np.zeros(beams_y+1)
    x_centres_pc[0:beams_x//2 + 1] = x_centres[0:beams_x//2 + 1]
    x_centres_pc[beams_x//2 + 1 :] = -x_centres[beams_x//2:0:-1]
    y_centres_pc[0:beams_y//2 + 1] = y_centres[0:beams_y//2 + 1]
    y_centres_pc[beams_y//2 + 1 :] = -y_centres[beams_y//2:0:-1]

    # The indices of this array can no longer be used as beam ids (since there is one more index than beam
    # because we allow a the edge beam to be valid on both sides of the sky.
    # re-map the N+1 pointing directions above to the N beams
    beam_remap_x = np.zeros(beams_x+1, dtype=int)
    beam_remap_y = np.zeros(beams_y+1, dtype=int)
    beam_remap_x[0:beams_x//2 + 1] = np.arange(beams_x//2 + 1)
    beam_remap_x[beams_x//2 + 1 :] = np.arange(beams_x//2, beams_x)
    beam_remap_y[0:beams_y//2 + 1] = np.arange(beams_y//2 + 1)
    beam_remap_y[beams_y//2 + 1 :] = np.arange(beams_y//2, beams_y)

    pylab.hold(True)
    pylab.ion()
    plot_centres(x_centres_pc,y_centres_pc,0,0)
    pylab.draw()

    if opts.verbose:
        print 'X pointing centres (relative to pointing centre)'
        for xc in x_centres_pc:
            print np.rad2deg(xc)
        print 'Y pointing centres (relative to pointing centre)'
        for yc in y_centres_pc:
            print np.rad2deg(yc)
        print 'X beam index map:'
        print beam_remap_x
        print 'Y beam index map:'
        print beam_remap_y


    # Now we have the beam centres, all we need to do is keep checking where the source is
    # And assign the nearest beam to watch it

    # To calculate the relative position of observatory and source,
    # set up the observatory as an ephem observer
    
    obs = ephem.Observer()
    obs.lat = ephem.degrees(str(array_lat))
    obs.long = ephem.degrees(str(array_lon))

    if opts.verbose:
        print 'Source info:'
        for src in srcs:
            src.compute(obs)
            print src.name, src.ra, src.dec

    history_len = 1024
    source_history = np.zeros([history_len,2])
    history_timestamps = np.zeros(history_len)
    history_index = 0
    history_initialised = 0
    while(True):
        try:
            for sn,src in enumerate(srcs): 
                
                obs.date = juldate2ephem(ephem.julian_date())

                if opts.verbose:
                    print 'Local Sidereal Time:', obs.sidereal_time()
                
                lst = obs.sidereal_time()
                src.compute(obs) 

                src_alt_offset = point_zen_dist - (np.pi/2 - src.alt)
                az = src.az
                az_offset = az

                # convert alt-az to x,y,z coordinates, where z is the zenith, x points east, and y north
                z = np.cos(np.pi/2 - src.alt)
                y = np.sin(np.pi/2 - src.alt)*np.sin(np.pi/2 - src.az)
                x = np.sin(np.pi/2 - src.alt)*np.cos(np.pi/2 - src.az)

                if opts.verbose:
                    print 'x,y,z in zenith-based co-ordinates: %.3f, %.3f, %.3f'%(np.rad2deg(x),np.rad2deg(y),np.rad2deg(z))

                # rotate these co-ordinates into the system where z is the pointing direction,
                # i.e. a rotation of theta_point about the x-axis
                x_rot, y_rot, z_rot = rotate_about_x(-pointing_rotation,[x,y,z])

                x_rot = -x_rot # X-axis points East, but beam offsets increase westwards
                y_rot = -y_rot # Y-axis points towards increasing dec, but beam offsets increment in negative dec direction

                # record position for plotting
                if history_initialised == 0:
                    history_timestamps[:] = lst
                    source_history[:] = [x_rot,y_rot]
                    history_initialised = 1

                source_history[history_index] = [x_rot,y_rot]
                history_timestamps[history_index] = lst


                if opts.verbose:
                    print "%s: Altitude: %.3f\tN/S offset from pointing centre %.3f"%(src.name,np.rad2deg(src.alt),np.rad2deg(src_alt_offset))
                    print "%s: Az: %.3f\tE/W offset from pointing centre %.3f"%(src.name,np.rad2deg(az),np.rad2deg(az_offset))

                if opts.verbose:
                    print '%s: x,y distance from point centre is %.3f, %.3f' %(src.name, np.rad2deg(x_rot),np.rad2deg(y_rot))

                
                nearest_x_beam = np.argmin(np.abs(x_centres_pc-x_rot))
                nearest_y_beam = np.argmin(np.abs(y_centres_pc-y_rot))

                nearest_x_beam_remap = beam_remap_x[nearest_x_beam]
                nearest_y_beam_remap = beam_remap_y[nearest_y_beam]

                pylab.cla() #clear plot
                pylab.title('History Start: %s Current LST: %s'%(ephem.hours(history_timestamps[(history_index+1)%history_len]),obs.sidereal_time()))
                plot_src(source_history, src.name)
                #pylab.annotate('%s'%src.name, (np.rad2deg(x_rot),np.rad2deg(y_rot)))
                pylab.legend()
                plot_centres(x_centres_pc,y_centres_pc,nearest_x_beam,nearest_y_beam)
                pylab.draw()

                history_index= (history_index+1)%history_len

                if (nearest_x_beam_remap != src_beams[sn,0]) or (nearest_y_beam_remap != src_beams[sn,1]):
                    print "Updating beam %d (%s) from (%d,%d) to (%d,%d)"%(sn,src.name,src_beams[sn,0], src_beams[sn,1], nearest_x_beam_remap, nearest_y_beam_remap)
                    seng.set_beam(sn,nearest_x_beam_remap, nearest_y_beam_remap)
                    src_beams[sn,0] = nearest_x_beam_remap
                    src_beams[sn,1] = nearest_y_beam_remap

            time.sleep(opts.sleep_time)

        except KeyboardInterrupt:
               print "Keyboard Interrupt! Exiting."
               exit()

