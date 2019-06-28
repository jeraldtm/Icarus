from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjField, Keithley220
import PyDAQmx as daqmx
from daedalus.custom_instruments import senis3AxHallProbe

daq = DAQmxAdapter('Dev2', ['ao0', 'ai1'])

write_str = '/' + daq.resource_name + '/' + daq.channels[0]
read_str = '/' + daq.resource_name + '/' + daq.channels[1]

volts = 0.0

task = daqmx.Task()
task.CreateAOVoltageChan(write_str.encode(),"",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
task.StartTask()
task.WriteAnalogScalarF64(1,10.0,volts,None)
task.StopTask()
task.ClearTask()

hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
print('x: %1.7f' % hall_probe.x_field)
print('y: %1.7f' % hall_probe.y_field)
print('z: %1.7f' % hall_probe.z_field)