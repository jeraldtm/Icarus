from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjField, Keithley220
import PyDAQmx as daqmx
from daedalus.custom_instruments import senis3AxHallProbe
import time

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

time.sleep(5)

task = daqmx.Task()
task.CreateAIVoltageChan(read_str.encode(),"",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
task.StartTask()
        # write field
read_volts = daqmx.float64()
task.ReadAnalogScalarF64(10.0,read_volts,None) # args: timeout, ctypes thing result is read to, "reserved" (always None)
task.StopTask()
task.ClearTask()
print(read_volts.value)

hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
print('x: %1.7f' % hall_probe.x_field)
print('y: %1.7f' % hall_probe.y_field)
print('z: %1.7f' % hall_probe.z_field)