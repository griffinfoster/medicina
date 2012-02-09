import aipy as a, numpy as n

prms = {
    'loc': ('44:31:24.88',  '11:38:45.56'), # Medicina, Italy
    'order': [3,2,1,0,7,6,5,4,11,10,9,8,15,14,13,12,19,18,17,16,23,22,21,20,27,26,25,24,31,30,29,28],
    'antpos':
      [[ -11.69,  -85.50,   11.89],  #3
       [ -11.69,  -65.90,   11.89],  #2
       [ -11.69,  -46.29,   11.89],  #1
       [ -11.69,  -26.68,   11.89],  #0
       [ -35.08,  -85.50,   35.67],  #7
       [ -35.08,  -65.90,   35.67],  #6
       [ -35.08,  -46.29,   35.67],  #5
       [ -35.08,  -26.68,   35.67],  #4
       [ -58.47,  -85.50,   59.45],  #11
       [ -58.47,  -65.90,   59.45],  #10
       [ -58.47,  -46.29,   59.45],  #9
       [ -58.47,  -26.68,   59.45],  #8
       [ -81.86,  -85.50,   83.23],  #15
       [ -81.86,  -65.90,   83.23],  #14
       [ -81.86,  -46.29,   83.23],  #13
       [ -81.86,  -26.68,   83.23],  #12
       [-105.25,  -85.50,  107.01],  #19
       [-105.25,  -65.90,  107.01],  #18
       [-105.25,  -46.29,  107.01],  #17
       [-105.25,  -26.68,  107.01],  #16
       [-128.64,  -85.50,  130.80],  #23
       [-128.64,  -65.90,  130.80],  #22
       [-128.64,  -46.29,  130.80],  #21
       [-128.64,  -26.68,  130.80],  #20
       [-152.03,  -85.50,  154.58],  #27
       [-152.03,  -65.90,  154.58],  #26
       [-152.03,  -46.29,  154.58],  #25
       [-152.03,  -26.68,  154.58],  #24
       [-175.42,  -85.50,  178.36],  #31
       [-175.42,  -65.90,  178.36],  #30
       [-175.42,  -46.29,  178.36],  #29
       [-175.42,  -26.68,  178.36]], #28
    'amps':[
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00,
    ],
    'delays':[  #nanoseconds
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
        0.00, 0.00, 0.00, 0.00,
    ],
    'bp_r': n.array([[1.]] * 32),
    'bp_i': n.array([[1.]] * 32),
    'beam': a.fit.Beam2DGaussian,
    'bm_prms': {'xwidth':0.1151, 'ywidth':0.0994},
    'dec': 2.*n.pi*(40.76/360.),
}

class AntennaArray(a.fit.AntennaArray):
    """Include functions to necessary for the pointing of the Medicina BEST-2 array"""
    def dec_pointing(self, dec):
        self.dec_pointing = dec
    def get_baseline(self, i, j, src='z'):
        """Return the baseline corresponding to i,j in various coordinate 
        projections: src='e' for current equatorial, 'z' for zenith 
        topocentric, 'r' for unrotated equatorial, or a RadioBody for
        projection toward that source."""
        bl = self[j] - self[i]
        if type(src) == str:
            if src == 'e': return n.dot(self._eq2now, bl)
            elif src == 'z': return n.dot(self._eq2zen, bl)
            elif src == 'r': return bl
            else: raise ValueError('Unrecognized source:' + src)
        try:
            if src.alt < 0:
                raise a.phs.PointingError('%s below horizon' % src.src_name)
            m = src.map
        except(AttributeError):
            ra,dec = a.coord.eq2radec(src)
            m = a.coord.eq2top_m(self.sidereal_time() - ra, dec)
        return n.dot(m, bl).transpose()

def get_aa(freqs):
    '''Return the AntennaArray to be used fro simulation.'''
    location = prms['loc']
    antennas = []
    nants = len(prms['antpos'])
    for i in range(len(prms['antpos'])):
        beam = prms['beam'](freqs)
        try: beam.set_params(prms['bm_prms'])
        except(AttributeError): pass
        pos = prms['antpos'][i]
        bp_r = prms['bp_r'][i]
        bp_i = prms['bp_i'][i]
        antennas.append(
            a.fit.Antenna(pos[0],pos[1],pos[2], beam,
                bp_r=bp_r, bp_i=bp_i)
        )
    aa = AntennaArray(prms['loc'], antennas)
    aa.dec_pointing(prms['dec'])
    return aa

src_prms = {
}
