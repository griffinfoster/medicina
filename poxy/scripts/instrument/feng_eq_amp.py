#! /usr/bin/env python
"""
Read/Write the Amplitude equalization coefficents for the F Engine on the Medicina Correlator/Spatial FFT
"""
import time, sys, struct, numpy
import katcp_wrapper, medInstrument, xmlParser, log_handlers, equalization

def exit_fail():
    print 'FAILURE DETECTED. Log entries:\n',lh.printMessages()
    print "Unexpected error:", sys.exc_info()
    try:
        inst.disconnect_all()
    except: pass
    raise
    exit()

def exit_clean():
    try:
        inst.disconnect_all()
    except: pass
    exit()

if __name__ == '__main__':
    from optparse import OptionParser

    o = OptionParser()
    o.set_usage('feng_eq_amp.py CONFIG_FILE')
    o.set_description(__doc__)
    o.add_option('-a', '--ant', dest='ants', default='all',
        help='Select which antennas to process, default=all')
    o.add_option('-p', '--pol', dest='pols', default='all',
        help='Select which polarizations to process (x,y,all), default=all')
    o.add_option('-r', '--read', dest='read', action='store_true', default=False,
        help='Read the the BRAM coefficents for selected antennas')
    o.add_option('--const', dest='const', default=-1,
        help='Multiply the current coefficents by a constant')
    o.add_option('-w', '--write', dest='write', default=None,
        help='Write coefficents based on an EQ pickle file, if left blank will load XML config file.')
    o.add_option('-v', '--verbose', dest='verbose',action='store_true', default=False, 
        help='Be verbose about errors.')

    opts, args = o.parse_args(sys.argv[1:])

    if args==[]:
        print 'Please specify a configuration file! \nExiting.'
        exit()

lh=log_handlers.DebugLogHandler()
name='xengine'
mode='amp'
save=False
pol_map={'x':0,'y':1}

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

print 'Connecting...',
feng=medInstrument.fEngine(args[0],lh)
print 'done'

if opts.ants.startswith('all'): ants = range(feng.n_ants)
else: ants = convert_arg_range(opts.ants)

if opts.pols.startswith('all'): pols = feng.pols
else: pols = opts.pols.split(',')

#Load EQ class from XML or pickle
if opts.write is None:
    #load EQs from XML config
    feng.eq_amp=feng.eq_load(name,mode)
else:
    #load EQs from pkl file
    feng.eq_amp=equalization.EQ()
    feng.eq_amp.read_pkl(opts.write)

#Apply constant factor to selected antpols
if float(opts.const)>0.:
    print "Apply a constant(%f) to the current EQ coefficents..."%float(opts.const),
    for a in ants:
        for p in pols:
            feng.eq_amp.apply_constant(a,pol_map[p],float(opts.const))
    feng.eq_write_amp_all(feng.eq_amp)
    feng.spead_eq_amp_meta_issue()
    save=True
    print "done"

#Read slected antpol BRAMs
if opts.read:
    for a in ants:
        for p in pols:
            print "ant: %i pol: %s"%(a,p)
            print feng.eq_read_amp(feng.eq_amp,a,pol=p)

#save eq_amp to pkl
if save:
    print "Saving new EQs to file...",
    feng.eq_save(name,mode,feng.eq_amp)
    print "done"

"""
try:
    print 'Connecting...',
    feng=medInstrument.fEngine(args[0],lh)
    print 'done'

    
except KeyboardInterrupt:
        exit_clean()
except: 
        exit_fail()

exit_clean()
"""
