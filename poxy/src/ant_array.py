#! /usr/bin/env python
"""
Software for parsing array configuration file and dealing with physical array parameters, eg. antenna positions, etc.
"""

import xmlParser
import numpy as n

class Array:
    def __init__(self, config_file):
        self.config = xmlParser.xmlObject(config_file).xmlobj #python object containing all the information from the xml file
        self.config_file = config_file

        self.n_ants=len(self.config.antennas.ant)
        self.ants=self.config.antennas.ant
        self.ref_ant=self.config.antennas.reference
        self.receiver = self.config.receiver
        self.grid = self.config.grid

    def loc(self,ant_index):
        '''Return the location of an antenna element in list format'''
        pos = self.ants[ant_index].position
        return [pos.x, pos.y, pos.z]

    def get_grid_position(self,ant_index):
        pos = self.ants[ant_index].position
        return [pos.grid['x'],pos.grid['y']]

    def get_input_num(self,ant_index):
        '''Return the ADC input channel number of an antenna'''
        if self.ants[ant_index].pols == 1:
            return {'x':int(self.ants[ant_index].adc_chan.data)}
        #elif self.ants[ant_index].pols == 2:
        #    if self.ants[ant_index].adc_chan[0].pol=='x':
        #        return {'x':int(self.ants.[ant_index].adc_chan[0].data),
        #                'y':int(self.ants.[ant_index].adc_chan[1].data)}
        #    else:
        #        return {'x':int(self.ants.[ant_index].adc_chan[0].data),
        #                'y':int(self.ants.[ant_index].adc_chan[1].data)}
        else:
            raise IndexError('Only 1 or 2 polarisations supported')

    def get_ref_loc(self):
        '''Return the lat and long of the reference point in degrees'''
        lat = self.ref_ant.position.lat
        lon = self.ref_ant.position.long
        if lat[-1]=='N':
            mult=1
            lat=lat.rstrip('N')
        elif lat[-1]=='S':
            mult=-1
            lat=lat.rstrip('S')
        else:
            mult=1
        lat = lat.split(':')
        lat_degs=0.0
        for vn,val in enumerate(lat):
            lat_degs += ((float(val)/(60**vn)))
        if lon[-1]=='E':
            mult=1
            lon=lon.rstrip('E')
        elif lon[-1]=='W':
            mult=-1
            lon=lon.rstrip('W')
        else:
            mult=1
        lon = lon.split(':')
        lon_degs=0.0
        for vn,val in enumerate(lon):
            lon_degs += ((float(val)/(60**vn)))
        return [lat_degs,lon_degs]
