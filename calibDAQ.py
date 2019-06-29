from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjField, Keithley220
import PyDAQmx as daqmx
from daedalus.custom_instruments import senis3AxHallProbe
import time
import numpy as np

daq = DAQmxAdapter('Dev2', ['ao0', 'ai1'])

write_str = '/' + daq.resource_name + '/' + daq.channels[0]
read_str = '/' + daq.resource_name + '/' + daq.channels[1]

voltValues = np.arange(-10.0, 10.0, 1)

offsetList = []

for volts in voltValues:
	task = daqmx.Task()
	task.CreateAOVoltageChan(write_str.encode(),"",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
	task.StartTask()
	task.WriteAnalogScalarF64(1,10.0,volts,None)
	task.StopTask()
	task.ClearTask()

	time.sleep(1)

	task = daqmx.Task()
	task.CreateAIVoltageChan(read_str.encode(),"",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
	task.StartTask()
	        # write field
	read_volts = daqmx.float64()
	task.ReadAnalogScalarF64(10.0,read_volts,None) # args: timeout, ctypes thing result is read to, "reserved" (always None)
	task.StopTask()
	task.ClearTask()
	offset = read_volts-volts
	print(offset)
	offsetList.append(offset)

print(np.array(offsetList).mean())