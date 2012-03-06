#! /usr/bin/env python

# PyQt Stuff
import PyQt4 as Qt
import PyQt4.Qt as qt
import PyQt4.QtGui as gui
import PyQt4.QtCore as core
import PyQt4.uic as uic

# Matplotlib stuff
import matplotlib
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

# Other stuff
import numpy as np
import struct
import sys, os

# Application specific stuff
"""
Plot FFT spectra before and after amplitude equalization,
phase equalization and quantization to 4 bits
"""
import time, sys,struct
import numpy as np
from poxy import katcp_wrapper, medInstrument, log_handlers 
import pylab, math
from poxy import plot_tools

# ------------------------ MATPLOTLIB CLASS ---------------------------

class MatplotlibPlot:
    """ Class encapsulating a matplotlib plot"""
    def __init__(self, parent = None, dpi = 100, size = (5,5)):
        """ Class initialiser """

        self.dpi = dpi
        self.figure = Figure(size, dpi = self.dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(parent)

        # Create the navigation toolbar, tied to the canvas
        self.toolbar = NavigationToolbar(self.canvas, parent)
        self.canvas.show()
        self.toolbar.show()

        # Reset the plot landscape
        self.figure.clear()
        self.nSubplot=0

    def resetSubplots(self):
        self.nSubplot=0

    def plotCurve(self, data, xAxisRange = None, yAxisRange = None, xLabel = "", yLabel = "", title="", label="", plotLog=False, nSubplots=1, hold=False):
        """ Plot the data as a curve"""

        if len(data) != 0:
            # Plan what dimensions the grid will have if there are to be subplots
            # Attempt to be roughly square but give preference to vertical stacking
            nSubplots_v = np.ceil(np.sqrt(nSubplots))
            nSubplots_h = np.ceil(float(nSubplots)/nSubplots_v)

            yAxisRange=np.array(yAxisRange)
            if yAxisRange is not None:
                auto_scale_y = False
                if plotLog:
                    data[data==0] = 1
                    yAxisRange[yAxisRange==0] = 1
                    data= 10*np.log(data)
                    yAxisRange = 10*np.log(yAxisRange)
            else:
                auto_scale_y = True

            # draw the new plot
            if self.nSubplot < nSubplots:
                self.axes = self.figure.add_subplot(nSubplots_v, nSubplots_h, self.nSubplot+1, label=label, title=title, ylim=yAxisRange) #subplots start from 1        
                self.axes.grid(True)
            #if plotLog:
            #    self.axes.semilogy(range(np.size(data)), data, scaley=auto_scale_y)
            #else:
            #    self.axes.plot(range(np.size(data)), data, scaley=auto_scale_y)
            self.axes.plot(range(np.size(data)), data, scaley=auto_scale_y)

            #if xAxisRange is not None:        
            #    self.xAxisRange = xAxisRange
            #    self.axes.xaxis.set_major_formatter(ticker.FuncFormatter(
            #               lambda x, pos=None: '%.2f' % self.xAxisRange[x] if 0 <= x < len(xAxisRange) else ''))
            #    for tick in self.axes.xaxis.get_ticklabels():
            #          tick.set_rotation(15)

            #if yAxisRange is not None:        
            #    self.yAxisRange = yAxisRange
            #    self.axes.xaxis.set_major_formatter(ticker.FuncFormatter(
            #               lambda x, pos=None: '%.1f' % self.yAxisRange[y] if 0 <= y < len(yAxisRange) else ''))
            #    for tick in self.axes.yaxis.get_ticklabels():
            #          tick.set_rotation(15)

            self.axes.xaxis.set_label_text(xLabel)
            self.axes.yaxis.set_label_text(yLabel)

            # Increment the subplot number ready for the plot method to be called again.
            # Count modulo number of subplots so that nSubplots=1 is the same as having a
            # single shared axis.
            # Skip this step if hold is set, in which case the next plot will be overlaid with the current one
            if not hold:
                self.nSubplot = (self.nSubplot + 1)

    def plotNewCurve(self, data, xAxisRange=None, yAxisRange=None, xLabel="", yLabel="", plotLog=False):
        # Clear the plot
        self.figure.clear()
        # Start from a new set of subplots
        self.nSubplot = 0
        self.plotCurve(self, data, xAxisRange=xAxisRange, yAxisRange=yAxisRange, xLabel=xLabel, yLabel=yLabel, plotLog=plotLog)

    def updatePlot(self):
        self.canvas.draw()

class NicePlotter(gui.QMainWindow):
    """ Main UI Window class """

    def __init__(self, uiFile):
        """ Initialise main window """
        super(NicePlotter, self).__init__()

        # Load window file
        self.mainWidget = uic.loadUi(uiFile)
        self.setCentralWidget(self.mainWidget)
        self.setWindowTitle("Nice Plotter")
        self.resize(880,740)

        # Create matplotlib Figure and FigCanvas objects
        self.matlabPlot = MatplotlibPlot(self.mainWidget.plotFrame, 100, (6,6))
        layout = gui.QGridLayout()
        self.mainWidget.plotFrame.setLayout(layout)
        layout.addWidget(self.matlabPlot.canvas)
        # initialise subplot
        self.subplots = False
        
        # Connect signals and slots
        # Plot selection lists
        core.QObject.connect(self.mainWidget.antennaList, core.SIGNAL('itemSelectionChanged()'), self.plotSignalFilter)
        core.QObject.connect(self.mainWidget.fpgaList, core.SIGNAL('itemSelectionChanged()'), self.plotSignalFilter)
        core.QObject.connect(self.mainWidget.plotTypeList, core.SIGNAL('currentRowChanged(int)'), self.plotSignalFilter)
        self.plotFilter=False
        # Data update button
        core.QObject.connect(self.mainWidget.updatePlot, core.SIGNAL('clicked()'), self.get_roach_data)
        # log plot button
        core.QObject.connect(self.mainWidget.plotLog, core.SIGNAL('stateChanged(int)'), self.setLog)
        # X/Y plot buttons
        core.QObject.connect(self.mainWidget.plotX, core.SIGNAL('stateChanged(int)'), self.plotX)
        core.QObject.connect(self.mainWidget.plotY, core.SIGNAL('stateChanged(int)'), self.plotY)
        # select / de-select all
        core.QObject.connect(self.mainWidget.selectAll, core.SIGNAL('clicked()'), self.selectAll)
        core.QObject.connect(self.mainWidget.deselectAll, core.SIGNAL('clicked()'), self.deselectAll)
        # single / multiple plot controls
        core.QObject.connect(self.mainWidget.plotSingle, core.SIGNAL('released()'), self.setPlotStyle)
        core.QObject.connect(self.mainWidget.plotMultiple, core.SIGNAL('released()'), self.setPlotStyle)
        core.QObject.connect(self.mainWidget.plotSubplots, core.SIGNAL('released()'), self.setPlotStyle)

        
        # Connect to ROACHs / parse config file
        self.initialise_Roaches()

        # Set log plotting as default option
        self.setLog(1)
        self.mainWidget.plotLog.setChecked(True)

        # Initialise progress bar
        self.setPlotProgress(0)

        # Set default plotting strategy. Multiple, single plot axis
        self.mainWidget.plotMultiple.click()

        # Get data (do this before setting the default plots lists,
        # otherwise there is no data for the intial plot
        self.get_roach_data()

        # Set default list selections
        self.plotX(1)
        self.plotY(1)
        self.mainWidget.antennaList.setCurrentRow(0)
        self.mainWidget.fpgaList.setCurrentRow(0)
        self.mainWidget.plotTypeList.setCurrentRow(0)
        self.mainWidget.plotX.setChecked(True)
        self.mainWidget.plotY.setChecked(True)

        self.show()

    def setPlotStyle(self):
        """ Set the plotting style controls (Multiple, single,subplots) """
        if self.mainWidget.plotSingle.isChecked():
            print 'Single plot mode!'
            curr_selected_ant = self.mainWidget.antennaList.selectedItems()
            curr_selected_fpga= self.mainWidget.fpgaList.selectedItems()
            self.mainWidget.antennaList.setSelectionMode(gui.QAbstractItemView.SingleSelection)
            self.mainWidget.fpgaList.setSelectionMode(gui.QAbstractItemView.SingleSelection)
            self.subplots=False
            # If more than one selection was made before entering single selection mode,
            # then highlight the first entry of the current selection
            if len(curr_selected_ant) > 1: 
                self.mainWidget.antennaList.setCurrentItem(curr_selected_ant[0])
            if len(curr_selected_fpga) > 1:
                self.mainWidget.fpgaList.setCurrentItem(curr_selected_fpga[0])
        else:
            print 'Multiple plot mode!'
            self.mainWidget.antennaList.setSelectionMode(gui.QAbstractItemView.MultiSelection)
            self.mainWidget.fpgaList.setSelectionMode(gui.QAbstractItemView.MultiSelection)
            if self.mainWidget.plotMultiple.isChecked():
                print 'No subplots!'
                self.subplots=False
            else:
                print 'Subplots!'
                self.subplots=True
        # plot with the new settings
        self.plot()

    def plotX(self,val):
        print 'plot X:', bool(val)
        self.plotX = bool(val)
        self.plot()

    def plotY(self,val):
        if not self.is_dual_pol:
            val=0 #Don't try to plot Y pols
        print 'plot Y:', bool(val)
        self.plotY = bool(val)
        self.plot()

    def plotSignalFilter(self):
        if not self.plotFilter:
            self.plot()
        else:
            pass

    def selectAll(self):
        """ Select all antennas for plotting """
        print "selecting all!!"
        self.plotFilter=True
        for item in self.antListItems:
            item.setSelected(True)
        self.plotFilter=False
        self.plot()

    def deselectAll(self):
        """ Deselect all antennas in the plotting list """
        print "deselecting all!!"
        self.plotFilter=True
        for item in self.antListItems:
            item.setSelected(False)
        self.plotFilter=False
        self.plot()

    def setPlotProgress(self,progress):
        self.mainWidget.plotProgress.setValue(progress)

    def add_plot_types(self):
        for plot_type in self.plot_types:
            self.mainWidget.plotTypeList.addItem(plot_type)

    def setLog(self, val):
        self.plotLog = bool(val)
        self.plot()

    def plot(self):
        """ Plot required plot """
        # Clear the existing plots
        self.matlabPlot.figure.clear()
        self.matlabPlot.resetSubplots()
        ants = self.mainWidget.antennaList.selectedItems()
        fpgas = self.mainWidget.fpgaList.selectedItems()
        plot_type = self.plot_types[self.mainWidget.plotTypeList.currentRow()]
        Nplots=len(fpgas)*len(ants)
        ant_indices = []
        for ant in ants:
            ant_indices.append(ant.ant_index)

        if Nplots != 0:
            if self.plotX:
                ymax = np.max(np.array(self.power_spec_x[plot_type])[:,ant_indices,0])
                ymin = np.min(np.array(self.power_spec_x[plot_type])[:,ant_indices,0])
                if self.plotY:
                    ymax = np.max([ymax, np.max(self.power_spec_y[plot_type][:,ant_indices,0])])
                    ymin = np.min([ymax, np.min(self.power_spec_y[plot_type][:,ant_indices,0])])
            elif self.plotY:
                ymax = np.max(self.power_spec_y[plot_type][:,ant_indices,0])
                ymin = np.min(self.power_spec_y[plot_type][:,ant_indices,0])


        if ((not self.plotX) and (not self.plotY)):
            # detect the case where antennas are selected but neither the plotX or plotY options are set
            Nplots=0
        nSubplots = Nplots if self.subplots else 1
        if Nplots==0:
            # No plots are selected. Put something blank on the plot
            self.matlabPlot.plotCurve([],plotLog=self.plotLog)
            self.setPlotProgress(100)
        else:
            # Work out what percentage of the total plot a single plot
            # makes up. Use this to update the progress bar.
            single_plot_progress = 100./Nplots
            print "Plot type:", plot_type
            plot_number = 1
            for fpga in fpgas:
                #print "Selected FPGA %d" %fpga.fpga_index
                for ant_n, ant in enumerate(ants):
                    #print "Selected antenna %d" % ant.ant_index
                    if self.plotX:
                        # plot the X pol and hold the subplot if a Ypol plot will follow
                        self.matlabPlot.plotCurve(self.power_spec_x[plot_type][fpga.fpga_index][ant.ant_index][0],plotLog=self.plotLog,nSubplots=nSubplots, hold=self.plotY, title='ant%d'%ant.ant_index, yAxisRange=(0.9*ymin,1.1*ymax))
                    if self.plotY:
                        self.matlabPlot.plotCurve(self.power_spec_y[plot_type][fpga.fpga_index][ant.ant_index][0],plotLog=self.plotLog,nSubplots=nSubplots, yAxisRange=(0.9*ymin,1.1*ymax))
                    self.setPlotProgress(np.round(plot_number*single_plot_progress))
                    plot_number += 1
            self.matlabPlot.updatePlot()

    def exit_fail(self):
        print 'FAILURE DETECTED. Log entries:\n', self.lh.printMessages()
        print "Unexpected error:", sys.exc_info()
        try:
            self.im.disconnect_all()
        except: pass
        raise
        exit()

    def initialise_Roaches(self):
        """ Read the configuration info from the config file, and initialise connections """

        args = sys.argv[1:]
        if args==[]:
            print 'Please specify a configuration file! \nExiting.'
            exit()

        lh=log_handlers.DebugLogHandler()
            
        # Parse the config file and connect to the ROACHs
        print 'Loading configuration file and connecting...',
        self.im = medInstrument.fEngine(args[0],lh,program=False)
        print 'done'
            
        self.Nchans = self.im.config.fengine.n_chan
        self.Nants_real = self.im.config.fengine.n_ants_sp
        self.is_dual_pol = (self.im.config.fengine.pols_per_ant==2)
        self.Nants = self.Nants_real
        self.int_len = self.im.config.xengine.xeng_acc_len

        # Populate listview
        self.fpgaListItems=[]
        self.antListItems=[]
        for fn, fpga in enumerate(self.im.fpgas):
            x = gui.QListWidgetItem()
            x.setText("FPGA %d" %(fn))
            x.fpga_index = fn
            self.fpgaListItems.append(x)
            self.mainWidget.fpgaList.addItem(x)
        for i in range(self.Nants_real):
            x = gui.QListWidgetItem()
            x.setText("Antenna %d" % i)
            x.ant_index = i
            self.antListItems.append(x)
            self.mainWidget.antennaList.addItem(x)
        self.plot_types = ['fft','amp EQ', 'phase EQ', 'quantised (seng)', 'quantised (xeng)']
        self.add_plot_types()

    def get_roach_data(self):
        """ Grab data from the ROACH to be plotted  """

        x_ss = 'x_snap'
        ctrl_reg = 'snap_ctrl'
        snap_sel_ss = 'snap_sel_reg'
        sync_sel_ss = 'sync_sel_reg'

        self.spec_x = {}
        self.power_spec_x = {}

        # Grab the data for the different plot types
        for snap_type in self.plot_types:
            if snap_type == 'fft':
                print ' Configuring software to snap FFT spectra'
                sync_index = 0
                snap_class = 'Spectras18'
            elif snap_type == 'amp EQ':
                print ' Configuring software to snap amplitude equalized spectra'
                sync_index = 1
                snap_class = 'Spectras18'
            elif snap_type == 'phase EQ':
                print ' Configuring software to snap amplitude + phase equalized spectra'
                sync_index = 2
                snap_class = 'Spectras18'
            elif snap_type == 'quantised (seng)':
                print ' Configuring software to snap 4 bit quantized spectra'
                sync_index = 3
                data_index = 12
                snap_class = 'SpectrasQuant'
            elif snap_type == 'quantised (xeng)':
                print ' Configuring software to snap 4 bit quantized spectra'
                sync_index = 4
                data_index = 13
                snap_class = 'SpectrasQuant'
            elif snap_type == 'transpose':
                sync_index = 5
                snap_class = 'SpectrasTranspose'
            else:
                'Requested snap of unknown quantity.'
                exit()

            print 'Snap Class is', snap_class
            if snap_class == 'Spectras18':
                snap_x = plot_tools.Spectras18(self.im.fpgas, ram_path=x_ss+'_snap_bram', ctrl_path=ctrl_reg,
                                               addr_path=x_ss+'_snap_addr', input_sel=x_ss+'_'+snap_sel_ss,
                                               sync_sel=x_ss+'_'+sync_sel_ss,sync_index=sync_index, n_ants=self.Nants,
                                               n_chans=self.Nchans)
            elif snap_class == 'SpectrasQuant':
                snap_x = plot_tools.SpectrasQuant(self.im.fpgas, ram_path=x_ss+'_snap_bram', ctrl_path=ctrl_reg,
                                               addr_path=x_ss+'_snap_addr', input_sel=x_ss+'_'+snap_sel_ss,
                                               sync_sel=x_ss+'_'+sync_sel_ss,sync_index=sync_index, n_ants=self.Nants,
                                               n_chans=self.Nchans,data_index=data_index)
            elif snap_class == 'SpectrasTranspose':
                snap_x = plot_tools.SpectrasTranspose(self.im.fpgas, ram_path=x_ss+'_snap_bram', ctrl_path=ctrl_reg,
                                                      addr_path=x_ss+'_snap_addr', input_sel=x_ss+'_'+snap_sel_ss,
                                                      sync_sel=x_ss+'_'+sync_sel_ss,sync_index=sync_index, n_ants=self.Nants,
                                                      n_chans=16, int_len=256)

            print snap_type
            self.spec_x[snap_type] = snap_x.get_spectras()
            self.power_spec_x[snap_type] = self.spec_x[snap_type].real**2 + self.spec_x[snap_type].imag**2
        self.plot()


if __name__ == "__main__":
    app = gui.QApplication(sys.argv)
    app.setApplicationName("feng_plotter")
    window = NicePlotter("/usr/local/bin/feng_plotter.ui")
    sys.exit(app.exec_())
