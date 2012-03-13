#!/usr/bin/env python

# encoding: utf-8
"""
gen_fits_idi.py
=====================

Generates a FITS IDI files based on a corrected HDF5 SPEAD files
An XML file is used to generate the table headers, and the table
data is either generated from functions within this file, or from
a HDF5 file (i.e. the raw output of a correlator).

Created by Danny Price on 2011-04-21.
Copyright (c) 2011 The University of Oxford. All rights reserved.

"""

import sys, os, datetime, time
import pyfits as pf
import numpy as np
import h5py
import ephem
import poxy

# FITS IDI python module imports
from pyfitsidi import *

def computeUVW(xyz,H,d):
    """ Converts X-Y-Z coordinates into U-V-W
    
    Uses the transform from Thompson Moran Swenson (4.1, pg86)
    
    Parameters
    ----------
    xyz: should be a numpy array [x,y,z]
    H: float (degrees)
        is the hour angle of the phase reference position
    d: float (degrees)
        is the declination
    """
    sin = np.sin
    cos = np.cos
    
    xyz = np.matrix(xyz) # Cast into a matrix
    
    trans= np.matrix([
        [sin(H),         cos(H),        0],
        [-sin(d)*cos(H), sin(d)*sin(H), cos(d)],
        [cos(d)*cos(H), -cos(d)*sin(H), sin(H)]
        ])
    
    uvw = trans * xyz.T
    uvw = np.array(uvw)
    return uvw[:,0]

def update_hdr(kv, tbl):
    """ Update/Add keys/values to the table header

    Parameters
    ----------
    kv: dict of keys/values to be updated/added
    tbl: pyfits.hdu table to be updated
    """
    for key in kv: tbl.header.update(key, kv[key])
    return tbl

def config_antenna(tbl):
    """ Configures the antenna table.
    
    Parameters
    ----------
    tbl: pyfits.hdu
        table to be configured
    """
  
    antenna = tbl.data
    for i in range(0,tbl.data.size):
        antenna[i]['ANNAME']      = 'ANT_%i'%i
        antenna[i]['ANTENNA_NO']  = i
        antenna[i]['ARRAY']       = 1
        antenna[i]['FREQID']      = 1
        antenna[i]['NO_LEVELS']   = 12
        antenna[i]['POLTYA']      = 'R'
        antenna[i]['POLTYB']      = 'L'
        antenna[i]['POLAA']       = 0
        antenna[i]['POLAB']       = 0
        #antenna[i]['POLCALA']     = 0
        #antenna[i]['POLCALB']     = 0
        antenna[i]['NOPOL']       = 2
    tbl.data = antenna
    return tbl

def config_source(tbl, source):
    """  Configures the source table.
    
    Parameters
    ----------
    tbl: pyfits.hdu
      table to be configured
    source: ephem.fixedBody
      source to be phased to (use makeSource())
    """
    # Stupidly using source as a variable name twice
    source_ra   = np.rad2deg(source._ra)
    source_dec  = np.rad2deg(source._dec)
    source_name = source.name
    
    #print('Source is: %s'%source.name)
    source = tbl.data[0]
    
    source['SOURCE_ID'] = 1
    source['SOURCE']    = source_name
    source['QUAL']      = 1
    source['VELDEF']    = 'RADIO'
    source['VELTYP']    = 'GEOCENTR'
    source['FREQID']    = 1
    source['RAEPO']     = source_ra
    source['DECEPO']    = source_dec
    source['EQUINOX']   = 'J2000'
    
    # Things I'm just making up
    source['IFLUX']    = 0
    source['QFLUX']    = 0
    source['UFLUX']    = 0
    source['VFLUX']    = 0
    source['ALPHA']    = 0
    source['FREQOFF']  = 0
    
    tbl.data[0] = source
    return tbl

def config_frequency(tbl,bw,nchan):
    """
    Configures the frequency table.
    
    Parameters
    ----------
    tbl: pyfits.hdu
      table to be configured
    bw: bandwidth in Hz
    nchan: number of channels
    """
    frequency = tbl.data[0]
  
    frequency['FREQID']         = 1
    frequency['BANDFREQ']       = 0         # This is offset from REF_FREQ, so zero!
    frequency['CH_WIDTH']       = bw/nchan
    frequency['TOTAL_BANDWIDTH']= bw
    frequency['SIDEBAND']       = 1
    frequency['BB_CHAN']        = 1
    
    tbl.data[0] = frequency
    return tbl  

def config_array_geometry(tbl, antenna_array):
    """  Configures the array_geometry table with Medicina values
  
    Parameters
    ----------
    tbl: pyfits.hdu
      table to be configured
    antenna_array: numpy.array
      an array of xyz coordinates of the antenna locations (offsets) in METERS
      from the array centre (this is a keyword in the header unit)
      e.g. 
    """
    geometry = tbl.data
  
    # X-Y-Z in metres
    xyz_m = antenna_array * 1e-9 * ephem.c
    for i in range(0,tbl.data.size):
        geometry[i]['ANNAME']  = 'MED_%i'%i
        geometry[i]['STABXYZ'] = xyz_m[i]
        geometry[i]['DERXYZ']  =  0
        #geometry[i]['ORBPARM'] = 0
        geometry[i]['NOSTA']   = i
        geometry[i]['MNTSTA']  = 1 
        # NOTE: Aperture arrays are given code 6, but not supported by CASA
        geometry[i]['STAXOF']  = np.array([0,0,0])
        geometry[i]['DIAMETER'] = 0
    
    tbl.data = geometry
    return tbl

def config_system_temperature(tbl):
    """
    Configures the system_temperature table with values for Medicina.
    Casa currently doesn't support this table in any way.
    """
    system_temp = tbl.data
    
    for i in range(0, tbl.data.size): 
        system_temp[i]['TIME'] = 0
        system_temp[i]['TIME_INTERVAL'] = 365 
        system_temp[i]['SOURCE_ID']  = 1 
        system_temp[i]['ANTENNA_NO'] = i 
        system_temp[i]['ARRAY'] = 1
        system_temp[i]['FREQID'] = 1
        system_temp[i]['TSYS_1'] = 87 
        system_temp[i]['TANT_1'] = 47

    tbl.data = system_temp
    return tbl 

def config_uv_data(h5fh, tbl_uv_data, antpos, obs, src, ti, verbose=False):
    
    if verbose:
        print('\nGenerating file metadata')
        print('--------------------------')
  
    # Data is stored in multidimensional array called xeng_raw0
    # time, channels, baselines, polarisation, then data=(real, imaginary) 
    (t_len, chan_len, bl_len, pol_len, ri_len) = h5fh['xeng_raw0'].shape
    int_time = h5fh.attrs['int_time']
    h5data = h5fh['xeng_raw0'][ti]
    
    timestamps = []
    baselines = []
    #weights = [1  in range(0,chan_len*2)]
    
    if verbose: print('Retrieving timestamps...')
    timestamps = h5fh['timestamp0'][ti]
  
    # Date and time
    # Date is julian date at midnight that day
    # The time is DAYS since midnight
    firststamp = timestamps[0]
    julian = ephem.julian_date(time.gmtime(firststamp)[:6])
    midnight = int(firststamp)
    
    # Ephem returns julian date at NOON, we need at MIDNIGHT
    julian_midnight = int(julian)+1
  
    elapsed = []
    for timestamp in timestamps:
        elapsed.append((ephem.julian_date(time.gmtime(timestamp)[:6]) - julian_midnight))
 
    if verbose: print('Creating baseline IDs...')
    bl_order = h5fh['bl_order'].value
    #WARNING: hardcore the antenna position frequency (GHz)
    cfreq=.408
    for bl in range(0,bl_len):
        # Baseline is in stupid 256*baseline1 + baseline2 format
        ant1, ant2 = bl_order[bl][0], bl_order[bl][1] 
        bl_id = 256*ant1 + ant2
        
        # Generate the XYZ vectors too
        # From CASA measurement set definition
        # uvw coordinates for the baseline from ANTENNE2 to ANTENNA1, 
        # i.e. the baseline is equal to the difference POSITION2 - POSITION1. 
        bl_vector = (antpos[ant2] - antpos[ant1])*cfreq
        #print bl_vector, antpos[ant2], antpos[ant1]
        baselines.append((bl_id,bl_vector))  
      
    if verbose: print('Computing UVW coordinates...\n')
    # Extract the timestamps and use these to make source our phase centre
    uvws = []
    for timestamp in timestamps:
        t = datetime.datetime.utcfromtimestamp(timestamp)
        if verbose: print t
        obs.date=t
        src.compute(obs)
        
        for baseline in baselines:
            vector = baseline[1]
            H, d = (obs.sidereal_time() - src._ra, src._dec)
            uvws.append(computeUVW(vector,H,d))
  
    # This array has shape t_len, num_ants, 3
    # and units of SECONDS
    uvws = np.array(uvws)
    uvws = uvws.reshape(uvws.size/bl_len/3,bl_len,3) / ephem.c
  
    if verbose:
        print('\nReformatting HDF5 format -> FITS IDI UV_DATA')
        print('--------------------------------------------')
     
    # The actual data matrix is stored per row as a multidimensional matrix
    # with the following mandatory axes:
    # COMPLEX     Real, imaginary, (weight)
    # STOKES      Stokes parameter
    # FREQ        Frequency (spectral channel)
    # RA          Right ascension of the phase center
    # DEC         Declination of the phase center 
    flux = np.ndarray(shape=(chan_len,1,ri_len))
     
    # This step takes ages.
    # I imagine there is some way to massage the hdf5 array
    # to do this a lot quicker than iterating over the indexes 
    if verbose: print('\nCreating multidimensional UV matrix...')
    for t in range(0,len(ti)):
        if verbose: print('processing time sample set %i/%i'%(t+1,len(ti)))
        # The time is seconds since midnight
        tbl_uv_data.data['TIME'][t*bl_len:(t+1)*bl_len] = np.ones(bl_len)*elapsed[t]
        tbl_uv_data.data['DATE'][t*bl_len:(t+1)*bl_len] = julian_midnight
        tbl_uv_data.data['INTTIM'][t*bl_len:(t+1)*bl_len] = np.ones(bl_len)*int_time
        #tbl_uv_data.data['SOURCE'][t*bl_len:(t+1)*bl_len]= np.ones(bl_len,dtype=np.int32)*1
        tbl_uv_data.data['SOURCE_ID'][t*bl_len:(t+1)*bl_len]= np.ones(bl_len,dtype=np.int32)*1
        tbl_uv_data.data['FREQID'][t*bl_len:(t+1)*bl_len]   = np.ones(bl_len,dtype=np.int32)*1
        tbl_uv_data.data['UU'][t*bl_len:(t+1)*bl_len] = uvws[t,:,0]
        tbl_uv_data.data['VV'][t*bl_len:(t+1)*bl_len] = uvws[t,:,1]
        tbl_uv_data.data['WW'][t*bl_len:(t+1)*bl_len] = uvws[t,:,2]
        for bl in range(0,bl_len):
            # Create a 1D index for the uv_data table
            i = t*bl_len + bl
            
            # Swap real and imaginary
            flux[:,0,0] = h5data[t,:,bl,0,1]
            flux[:,0,1] = h5data[t,:,bl,0,0]
            
            tbl_uv_data.data[i]['FLUX']     = flux.ravel()
            tbl_uv_data.data[i]['BASELINE'] = baselines[bl][0]
    
    if verbose:
        print('\nData reformatting complete')
        print('DONE.')
    return tbl_uv_data  

def convert_arg_range(arg):
    """Split apart command-line lists/ranges into a list of numbers."""
    arg = arg.split(',')
    init = [map(int, option.split('_')) for option in arg]
    rv = []
    for i in init:
        if len(i) == 1:
            rv.append(i[0])
        elif len(i) == 2:
            rv.extend(range(i[0],i[1]+1))
    return rv

if __name__ == '__main__':
    from optparse import OptionParser
    p = OptionParser()
    p.set_usage('%prog [options] HDF5_FILE(S)')
    p.set_description(__doc__)
    p.add_option('-c', '--config', dest='config',
        help='pyFITS-IDI XML config file, this is required, there is no default.')
    p.add_option('-a', '--ant', dest='ant_config',
        help='Antenna config file, this is required, there is no default.')
    p.add_option('-o', '--out', dest='outfile',
        help='Ouput file name, defaults to input filename with a \'.fits\' extension.')
    p.add_option('-s', '--source', dest='src',
        help='Source config XML file, this is required, there is no default.')
    p.add_option('-t', '--time', dest='time_index', default='all',
        help='Time index range, takes in two values: the starting time index and the index range, i.e. 24,10 will use 10 time samples startong at index 24, default is all times.')
    p.add_option('-A', '--append', dest='append', action='store_true', default=False,
        help='Append all input files into a single output file, the time index range covers all inputs files as if it was a single file.')
    p.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False,
        help='Verbose mode.')
    opts, args = p.parse_args(sys.argv[1:])
    if args==[]:
        print 'Please specify the HDF5 files. \nExiting.'
        exit()
    elif opts.config == None:
        print 'Please specifiy the pyFITSIDI config file. \nExiting.'
        exit()
    elif opts.ant_config == None:
        print 'Please specifiy the Antenna config file. \nExiting.'
        exit()
    elif opts.src == None:
        print 'Please specifiy the Source. \nExiting.'
        exit()
   
    #import the antenna config file, parameter dictionary ant_config.prms
    ant_config_key = opts.ant_config.split('.')[0]
    exec('import %s as ant_config' % ant_config_key)

    if opts.verbose:
        print('\nInput and output filenames')
        print('--------------------------------')
        print 'Config XML:', opts.config
        print 'Antenna Config:', opts.ant_config
        print 'Source:', opts.src
        if opts.append:
            for f in args: print 'In:',f
            print 'Out:',args[0]+'.fits'
        else:
            for f in args: print "In: %s \tOut: %s"%(f, f+'.fits')
    ofile_prefix = opts.outfile

    #gather attributes from first hdf5 file
    fh=h5py.File(args[0])
    bandwidth=fh.attrs['bandwidth']
    telescope=fh.attrs['telescope'].upper()
    center_freq=fh.attrs['center_freq']
    n_chans=fh.attrs['n_chans']
    int_time=fh.attrs['int_time']
    first_ts=fh['timestamp0'][0]
    fh.flush()
    fh.close()

    #common header values
    cmn = {}
    #cmn['OBSCODE']=telescope
    #header values do not like non-ASCII characters
    cmn['OBSCODE']=telescope
    rdate=time.gmtime(first_ts)[:3]
    #pad dates with zero if necessary
    if rdate[1] < 10: month_str='0%i'%rdate[1]
    else: month_str=str(rdate[1])
    if rdate[2] < 10: day_str='0%i'%rdate[2]
    else: day_str=str(rdate[2])
    cmn['RDATE']='%i-%s-%s'%(rdate[0],month_str,day_str)
    
    cmn['NO_CHAN']=n_chans
    cmn['REF_FREQ']=center_freq - (bandwidth/2.)
    cmn['CHAN_BW']=bandwidth

    if opts.verbose:
        print('\nConfiguring Array geography')
        print('--------------------------')
    
    if len(ant_config.prms['loc']) == 2:
        (lat, lng) = ant_config.prms['loc']
        elev=0.
    else: (lat, lng, elev) = ant_config.prms['loc']
    antpos = np.array(ant_config.prms['antpos'])
    antpos = antpos[ant_config.prms['order']]
    obs = ephem.Observer()
    obs.lat=lat
    obs.long=lng
    obs.elevation=elev
    obs.date=ephem.now()

    # The source is our phase centre for UVW coordinates
    src_xml=poxy.xmlParser.xmlObject(opts.src).xmlobj
    src=ephem.readdb('%s,f,%s,%s,%s,%d'%(src_xml.name,src_xml.ra,src_xml.dec,1,ephem.J2000))
    src.compute(obs)

    if opts.verbose:
        print('\nConfiguring phase source')
        print('--------------------------')
        print "Name: %s \nRA: %s \nDEC: %s"%(src_xml.name,src._ra,src._dec)
   
    # Make a new blank FITS HDU
    hdu = make_primary(config=opts.config)
    hdu = update_hdr(cmn, hdu)
    if opts.verbose:
        print('\nCreating PRIMARY HDU')
        print('------------------------------------')
        print hdu.header.ascardlist()
    
    # Go through and generate required tables
    tbl_array_geometry = make_array_geometry(config=opts.config, num_rows=antpos.shape[0])
    tbl_array_geometry = config_array_geometry(tbl_array_geometry,antpos)
    g_cmn = cmn
    g_cmn['FREQ']=center_freq
    tbl_array_geometry = update_hdr(g_cmn, tbl_array_geometry)
    if opts.verbose:
        print('\nCreating ARRAY_GEOMETRY')
        print('------------------------------------')
        print tbl_array_geometry.header.ascardlist()
    
    tbl_frequency = make_frequency(config=opts.config, num_rows=1)
    tbl_frequency = config_frequency(tbl_frequency,bandwidth,n_chans)
    tbl_frequency = update_hdr(cmn, tbl_frequency)
    if opts.verbose:
        print('\nCreating FREQUENCY')
        print('------------------------------------')
        print tbl_frequency.header.ascardlist()
    
    tbl_source = make_source(config=opts.config, num_rows=1)
    tbl_source = config_source(tbl_source, src)
    tbl_source = update_hdr(cmn, tbl_source)
    if opts.verbose:
        print('\nCreating SOURCE')
        print('------------------------------------')
        print tbl_source.header.ascardlist()
    
    tbl_antenna = make_antenna(config=opts.config, num_rows=antpos.shape[0])
    tbl_antenna = config_antenna(tbl_antenna)
    tbl_antenna = update_hdr(cmn, tbl_antenna)
    if opts.verbose:
        print('\nCreating ANTENNA')
        print('------------------------------------')
        print tbl_antenna.header.ascardlist()
    
    if opts.verbose:
        print('\nCreating UV_DATA')
        print('------------------------------------')
    
    for fid,f in enumerate(args):
        # Open hdf5 table
        print('Opening HDF5 table %s'%f)
        h5fh = h5py.File(f)
    
        # Data is stored in multidimensional array called xeng_raw0
        # time, channels, baselines, polarisation, then data=(real, imaginary) 
        (t_len, chan_len, bl_len, pol_len, ri_len) = h5fh['xeng_raw0'].shape
        if opts.verbose:
            print('Data dimensions: %i dumps, %i chans, %i baselines, %i pols, %i data (real/imag)'%(t_len, chan_len, bl_len, pol_len, ri_len))
            print('Generating blank UV_DATA rows...')
        
        if opts.time_index == 'all':
            time_index=range(h5fh['timestamp0'].len())
        else: time_index = convert_arg_range(opts.time_index)
        tbl_uv_data = make_uv_data(config=opts.config, num_rows=len(time_index)*bl_len, n_chans=n_chans)
        uv_cmn = cmn
        uv_cmn['DATE-OBS']=cmn['RDATE']
        uv_cmn['TELESCOP']=telescope
        #sort currently set to '*', should it be something else?
        #uv_cmn['SORT']=???
        #<CTYPE1>    'COMPLEX'   </CTYPE1>
        uv_cmn['CDELT1']=1.0
        uv_cmn['CRPIX1']=1.0
        uv_cmn['CRVAL1']=1.0
        #<CTYPE2>    'STOKES'    </CTYPE2> 
        #uv_cmn['CDELT2']=1.0    #this could be -1.0???
        uv_cmn['CDELT2']=-1.0
        uv_cmn['CRPIX2']=1.0
        uv_cmn['CRVAL2']=tbl_uv_data.header['STK_1']
        #<CTYPE3>    'FREQ'      </CTYPE3>
        uv_cmn['MAXIS3']=n_chans
        uv_cmn['CDELT3']=bandwidth/n_chans
        uv_cmn['CRPIX3']=tbl_uv_data.header['REF_PIXL']
        uv_cmn['CRVAL3']=center_freq - (bandwidth/2.)
        #<CTYPE4>    'BAND'      </CTYPE4>
        #<CTYPE5>    'RA'        </CTYPE5>
        uv_cmn['CRVAL5']=float(src._ra)*180./ephem.pi
        #<CTYPE6>    'DEC'       </CTYPE6>
        uv_cmn['CRVAL6']=float(src._dec)*180./ephem.pi
        
        tbl_uv_data = update_hdr(uv_cmn, tbl_uv_data)

        if opts.verbose: print('Now filling FITS file with data from HDF file...')
        tbl_uv_data = config_uv_data(h5fh,tbl_uv_data, antpos, obs, src, time_index, verbose=opts.verbose)

        #tbl_flag = make_flag(config=opts.config)
        #tbl_flag = config_flag(h5fh, tbl_flag)
        #tbl_flag = update_hdr(cmn, tbl_flag)

        h5fh.flush()
        h5fh.close()

        if opts.verbose: print tbl_uv_data.header.ascardlist()
    
        hdulist = pf.HDUList(
            [hdu, 
            tbl_array_geometry,
            tbl_frequency,
            tbl_antenna,
            tbl_source, 
            tbl_uv_data])
    
        if opts.verbose: print('Verifying integrity...')            
        hdulist.verify()
   
        if ofile_prefix is None: ofile=f+'.fits'
        else: ofile = ofile_prefix + str(fid) + '.fits'
        if opts.verbose: print('Writing to file...')
        hdulist.writeto(ofile)
  
    if opts.verbose: print('Done.')

