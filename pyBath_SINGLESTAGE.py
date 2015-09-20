# standard library
import sys
import os
import time
import logging
# third party
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
# local library
import gr # TESTING shell
import qtgr
from qtgr.backend import QtCore, QtGui
from qtgr.events import GUIConnector, MouseEvent, PickEvent, LegendEvent
from gr.pygr import Plot, PlotAxes, PlotCurve, ErrorBar



class MainWindow(QtGui.QMainWindow):

    def __init__(self, *args, **kwargs):
        while not shared_memory['data_fresh']:
            pass
        super(MainWindow, self).__init__(*args, **kwargs)
        uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                "second.ui"), self) 
        self.monitor_mode = False
        self.state = 'Connecting...'
        self.prev_time = time.time()

        self._heat_capacity_spin.valueChanged.connect(self.updateHeatCapacity)
        self._heat_capacity_spin.setDecimals(4)
        self._heat_capacity_spin.setMaximum(15.00) # Will we ever heat hydrogen?
        self._heat_capacity_spin.setSingleStep(0.0001)

        self._mass_spin.valueChanged.connect(self.updateMass)
        self._mass_spin.setDecimals(4)
        self._mass_spin.setMaximum(1000.00) 
        self._mass_spin.setSingleStep(0.0001)

        self._emissivity_spin.valueChanged.connect(self.updateEmissivity)
        self._emissivity_spin.setDecimals(4)
        self._emissivity_spin.setMaximum(1.00)
        self._emissivity_spin.setSingleStep(0.0001)

        self._area_spin.valueChanged.connect(self.updateArea)
        self._area_spin.setDecimals(4)
        self._area_spin.setMaximum(1000.00) 
        self._area_spin.setSingleStep(0.0001)

        self._resistance_spin.valueChanged.connect(self.updateResistance)
        self._resistance_spin.setDecimals(1)
        self._resistance_spin.setMaximum(1000.0) 
        self._resistance_spin.setSingleStep(0.1)

        self._voltage_spin.valueChanged.connect(self.updateVoltage)
        self._voltage_spin.setDecimals(2)
        self._voltage_spin.setMaximum(1000.00) 
        self._voltage_spin.setSingleStep(0.01)

        self._p_spin.valueChanged.connect(self.updateP)
        self._p_spin.setDecimals(4)
        self._p_spin.setMaximum(2.00) 
        self._p_spin.setSingleStep(0.0001)

        self._i_spin.valueChanged.connect(self.updateI)
        self._i_spin.setDecimals(4)
        self._i_spin.setMaximum(2.00) 
        self._i_spin.setSingleStep(0.0001)

        self._d_spin.valueChanged.connect(self.updateD)
        self._d_spin.setDecimals(4)
        self._d_spin.setMaximum(2.00) 
        self._d_spin.setSingleStep(0.0001)

        self._target_spin.valueChanged.connect(self.updateTarget)
        self._target_spin.setDecimals(2)
        self._target_spin.setMaximum(500.00) 
        self._target_spin.setSingleStep(0.01)

 
        self._monitor_check.stateChanged.connect(self.updateMonitor)
        self._btn_start.clicked.connect(self.startProcess)
        self._btn_stop.clicked.connect(self.stopProcess)
        self._state_out_label.setText(self.state)

        try:
          self._heat_capacity_spin.setValue(shared_memory['heatCapacity'])
          self._mass_spin.setValue(shared_memory['mass'])
          self._emissivity_spin.setValue(shared_memory['emissivity'])
          self._area_spin.setValue(shared_memory['area'])
          self._resistance_spin.setValue(shared_memory['resistance'])
          self._voltage_spin.setValue(shared_memory['voltage'])
          self._p_spin.setValue(shared_memory['p'])
          self._i_spin.setValue(shared_memory['i'])
          self._d_spin.setValue(shared_memory['d'])
        except:
           pass

        # palette = self._ambient_lcd.palette()
        # # foreground color
        # palette.setColor(palette.WindowText, QtGui.QColor(0, 0, 0))
        # # background color
        # palette.setColor(palette.Background, QtGui.QColor(0, 0, 0))
        # # "light" border
        # # palette.setColor(palette.Light, QtGui.QColor(255, 0, 0))
        # # "dark" border
        # palette.setColor(palette.Dark, QtGui.QColor(0, 0, 0))
        # # set the palette
        # self._ambient_lcd.setPalette(palette)
        # self._bath_lcd.setPalette(palette)
        # self._ambient_lcd.display(0.0)
        # self._bath_lcd.display(0.0)

        x = [1.0]
        y = [shared_memory['bath_temp']]
        xe = [1.0]
        ye = [shared_memory['env_temp']]

        viewport = [0.1, 0.95, 0.1, 0.95]

        self.env_curve = PlotCurve(xe, ye, legend = "Environment")
        self.env_curve.linetype = gr.LINETYPE_DASHED
        self.env_curve.linecolor = 7

        self.bath_curve = PlotCurve(x, y, legend = "Bath Medium")

        axes = PlotAxes(viewport)
        # axes.addCurves(self.env_curve)
        axes.addCurves(self.bath_curve)
        self._plot = Plot(viewport).addAxes(axes)
        self._plot.title = "System Temperatures"
        #self._plot.subTitle = "live data"
        self._plot.xlabel = "Seconds"
        self._plot.ylabel = "Celsius"
        self._plot.setLegend(True)
        self._plot.autoscale = PlotAxes.SCALE_X | PlotAxes.SCALE_Y
        self._stage.addPlot(self._plot)

        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateData)
        timer.start(5000)

    def _reset_curves(self):
        self.bath_curve.x = [0.0]
        self.env_curve.x  = [0.0]
        self.bath_curve.y = [shared_memory['bath_temp']]
        self.env_curve.y  = [shared_memory['env_temp']]

    def updateData(self):
        
        if shared_memory['data_fresh']:
            t = time.time()
            if self.state != 'Connected!':
                self.state = 'Connected!'
                self._state_out_label.setText(self.state)
            self._env_label.setText(str(shared_memory['env_temp']))
            self._bath_label_2.setText(str(shared_memory['bath_temp']))

            if self.monitor_mode or shared_memory['start']:
                self.env_curve.x.append(t - self.prev_time)#self.env_curve.x[-1]+5)
                self.bath_curve.x.append(t - self.prev_time)#self.bath_curve.x[-1]+5)
                self.env_curve.y.append(shared_memory['env_temp'])
                self.bath_curve.y.append(shared_memory['bath_temp'])
        else:
            self.state = 'Connecting...'
            self._state_out_label.setText(self.state)
            self._env_label.setText('0.0')
            self._bath_label_2.setText('0.0')

        self.update() 


    def updateHeatCapacity(self):
      shared_memory['heatCapacity'] = float(self._heat_capacity_spin.cleanText())

    def updateMass(self):
      shared_memory['mass'] = float(self._mass_spin.cleanText())

    def updateEmissivity(self):
      shared_memory['emissivity'] = float(self._emissivity_spin.cleanText())

    def updateArea(self):
      shared_memory['area'] = float(self._area_spin.cleanText())

    def updateResistance(self):
      shared_memory['resistance'] = float(self._resistance_spin.cleanText())

    def updateVoltage(self):
      shared_memory['voltage'] = float(self._voltage_spin.cleanText())

    def updateP(self):
      shared_memory['p'] = float(self._p_spin.cleanText())

    def updateI(self):
      shared_memory['i'] = float(self._i_spin.cleanText())

    def updateD(self):
      shared_memory['d'] = float(self._d_spin.cleanText())

    def updateMonitor(self):
      if not self.monitor_mode:
        self._reset_curves()
        self._stage.update()
        self.monitor_mode = True
      else:
        self.monitor_mode = False

    def updateTarget(self):
      shared_memory['target'] = float(self._target_spin.cleanText())

    def startProcess(self):
      if shared_memory['target'] is not None:
          self._monitor_check.setCheckState(False)
          self._monitor_check.setEnabled(False)
          self._heat_capacity_spin.setEnabled(False)
          self._mass_spin.setEnabled(False)
          self._emissivity_spin.setEnabled(False)
          self._area_spin.setEnabled(False)
          self._resistance_spin.setEnabled(False)
          self._voltage_spin.setEnabled(False)
          self._p_spin.setEnabled(False)
          self._i_spin.setEnabled(False)
          self._d_spin.setEnabled(False)
          self._target_spin.setEnabled(False)
          self._btn_start.setEnabled(False)
          self._reset_curves()
          self._stage.update()
          shared_memory['start'] = True

    def stopProcess(self):
      self._monitor_check.setEnabled(True)
      self._heat_capacity_spin.setEnabled(True)
      self._mass_spin.setEnabled(True)
      self._emissivity_spin.setEnabled(True)
      self._area_spin.setEnabled(True)
      self._resistance_spin.setEnabled(True)
      self._voltage_spin.setEnabled(True)
      self._p_spin.setEnabled(True)
      self._i_spin.setEnabled(True)
      self._d_spin.setEnabled(True)
      self._target_spin.setEnabled(True)
      self._btn_start.setEnabled(True)
      shared_memory['start'] = False    














def get_temp( send=False, on_time=0 ):
    if send: controller.set_element_time(on_time)
    # If there is a problem with packet
    t = controller.get_temperatures()
    if t is None or t[0] == 0.0 or t[1] == 0.0:
        shared_memory['data_fresh'] = False
        return
    shared_memory['env_temp']   = t[0]
    shared_memory['bath_temp']  = t[1]
    shared_memory['data_fresh'] = True

def window_main(*args):
    app = QtGui.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())




if __name__ == "__main__":

    import PID
    from BathController import BathController
    from multiprocessing import Process, Manager, Lock
    from ConfigParser import SafeConfigParser

    def resistance_to_watts(resistance, voltage):
        """ Calculate element wattage from resitance and voltage """
        return (voltage**2)/resistance

    def joules_to_watt_seconds(joules, element_wattage):
        """ Calculate element time from energy in joules """
        return float(joules/element_wattage)

    def temperature_to_joules(temp_obj, temp_amb, mass_kg, heat_capacity):
        """ Calculate energy contained within the bath medium """
        # 4.184 is cal -> joule, specific heat is cal/g/c, we want joule/g/k
        return float((heat_capacity * (mass_kg*1000) * (temp_obj - temp_amb))/4.184)

    def boltzmann_loss(emissivity, area, temp_obj, temp_amb):
        """ Calculate the energy radiated at a given temperature """
        temp_amb += 273.15
        temp_obj += 273.15
        boltzmann_const = 5.670373e-8# W * m^-2 * K^-4
        a = area*((temp_obj**4) - (temp_amb**4))# A(T^4 - Tc^4)
        return emissivity*boltzmann_const*a



    manager = Manager()
    config = SafeConfigParser()
    config.read('config.conf')
    shared_memory = manager.dict({
                                  'env_temp':None,
                                  'bath_temp':None,
                                  'heatCapacity':float(config.get('Tuning', 'Heat_Capacity')),
                                  'mass':float(config.get('Tuning', 'Mass')),
                                  'emissivity':float(config.get('Tuning', 'Emissivity')),
                                  'area':float(config.get('Tuning', 'Area')),
                                  'resistance':float(config.get('Tuning', 'Resistance')),
                                  'voltage':float(config.get('Tuning', 'Voltage')),
                                  'p':float(config.get('Tuning', 'P')), 
                                  'i':float(config.get('Tuning', 'I')), 
                                  'd':float(config.get('Tuning', 'D')),
                                  'target':None,
                                  'start':False,
                                  'data_fresh':False
                                  })

    controller = BathController(config.get('Connection', 'Port'), 
                                config.get('Connection', 'Baud'))
    time.sleep(3)
    print "\rLift off!"
    get_temp()
    # Start main window thread
    window_thread = Process(target = window_main, args = (sys.argv, shared_memory))
    window_thread.daemon = True
    window_thread.start()
    # Initialise PID object
    pid = PID.control(shared_memory['p']/10000.0, shared_memory['i']/10000.0, shared_memory['d']/10000.0)
    # Whilst the UI is open 
    while window_thread.is_alive():
        # Kick over 
        get_temp()
        #get_temp()
        if shared_memory['start'] and shared_memory['data_fresh']:
            cycleStart = time.time()
            dist = None
            target_reached = False
            while shared_memory['start'] and window_thread.is_alive():
                cycleStart = time.time()
                To = shared_memory['target']
                Ta = shared_memory['env_temp']
                Tb = shared_memory['bath_temp']
                m  = shared_memory['mass']
                h  = shared_memory['heatCapacity']
                e  = shared_memory['emissivity']
                a  = shared_memory['area']
                w  = resistance_to_watts(shared_memory['resistance'], shared_memory['voltage'])
                if Tb >= To: target_reached = True
                # Calculate desired energy within medium
                set_point  = temperature_to_joules(To, Ta, m, h) 
                # print "Set point is {0} Joules".format(set_point)
                # Add boltzmann radiated loss for that moment
                #set_point += boltzmann_loss(e, a, To, Ta)
                # Assess the current energy within medium
                current_energy = temperature_to_joules(Tb, Ta, m, h)
                print "\nCurrent stored energy is {0} Joules".format(current_energy)
                bltz = boltzmann_loss(e,a, Tb, Ta)
                # Add boltzamn
                energy_deficit = set_point - current_energy #+ bltz
                # First loop? save total error for adaptive tuning
                if dist is None: dist = energy_deficit
                print "Energy deficit is {0} Joules".format(set_point - current_energy)#+ bltz)
                if energy_deficit > 0:
                    # Adaptive tuning
                    # Below 33% and more than 20Kj, agressive tuning
                    # if energy_deficit >= (dist/3)*2 and energy_deficit >= 20000:
                    #     print 'Mode: Agrressive '
                    #     pid.setKp(shared_memory['p'] / 100.00)   
                    #     pid.setKi(shared_memory['i'] / 100.00)  
                    #     pid.setKd(shared_memory['d'] / 100.00)
                    # Within 25%, use a more conservative tuning
                    # if energy_deficit <= (dist/10):
                    #     print 'Mode: Conservative '
                    #     pid.setKp(shared_memory['p'] / 20000.00)   
                    #     pid.setKi(shared_memory['i'] / 20000.00)  
                    #     pid.setKd(shared_memory['d'] / 20000.00)
                    # # Within 25%, use a more conservative tuning
                    # elif energy_deficit <= (dist/4):
                    #     print 'Mode: Conservative '
                    #     pid.setKp(shared_memory['p'] / 10000.00)   
                    #     pid.setKi(shared_memory['i'] / 10000.00)  
                    #     pid.setKd(shared_memory['d'] / 10000.00)
                    # # Else normal tuning       
                    # else:
                    print 'Mode: SINGLE STAGE '
                    pid.setKp(shared_memory['p'] / 1000.00)   
                    pid.setKi(shared_memory['i'] / 1000.00)  
                    pid.setKd(shared_memory['d'] / 1000.00)
                    # send the PID controller set_energy - stored energy (error)
                    energy_output = pid.genOut(set_point - current_energy)
                    # pid returns energy to put in, convert to watt seconds
                    element_time = joules_to_watt_seconds(energy_output, w)
                    print "PID wants {0} Joules".format(energy_output)
                    if element_time > 0.0 and element_time < 10.0: 
                        print 'Element time   = ', element_time
                        get_temp(send=True, on_time=int(element_time*1000))
                    elif element_time > 10.0:
                        print 'Element time   = 10.0 [CLAMPED]'
                        get_temp(send=True, on_time=10000)
                # Update temps
                get_temp()
                # dt
                time.sleep(10 - (time.time()-cycleStart))
        else:
            time.sleep(5)
