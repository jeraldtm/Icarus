import logging
import os
from time import sleep
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Procedure
from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjField, senis3AxHallProbe

from pymeasure.display.windows import ManagedImageWindow
from pymeasure.experiment import Results, unique_filename
import sys
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi


class icarusCalibCheckProcedure(Procedure):
    """
    Procedure for making a raser image of the field components of Daedalus
    """

    # control parameters
    calib_name = Parameter("Calibration Name", default='')
    mag_field = FloatParameter("Magnetic field strength", units="T", default=0.1)
    num_averages = IntegerParameter("Number of Averages", default=1)
    delay = FloatParameter("Delay between averages", units="s", default=.1)
    center_calib_name = Parameter("Center Calibration File")

    phi_start = FloatParameter("Phi Start Position", units="mm", default=10.)
    phi_end = FloatParameter("Phi End Position", units="mm", default=13.)
    phi_step = FloatParameter("Phi Scan Step Size", units="mm", default=0.1)
    theta_start = FloatParameter("Theta Start Position", units="mm", default=10.)
    theta_end = FloatParameter("Theta End Position", units="mm", default=13.)
    theta_step = FloatParameter("Theta Scan Step Size", units="mm", default=0.1)

    DATA_COLUMNS = ["phi","theta","X", "Y", "Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std",
                    "Yfield_std","Zfield_std"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        
        log.info("Setting magnet field to %.2f T"%self.mag_field)
        log.info("Setting magnet position to Phi: {0}, Theta: {1}".format(phi_start, theta_start))
        self.magnet.set_vector_field(self.mag_field, self.phi_start, self.theta_start)
        while self.magnet.in_motion:
            sleep(0.05)
        sleep(.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

    def get_Bz(self):
        return -1*self.hall_probe.z_field

    def execute(self):
        phis = np.arange(self.phi_start, self.phi_end + self.phi_step, self.phi_step)
        thetas = np.arange(self.theta_start, self.theta_end + self.theta_step, self.theta_step)

        num_progress = float(phis.size * thetas.size) * self.num_averages
        progress_iterator = 0
        self.emit('progress',int(100*progress_iterator/num_progress))

        for theta in thetas:
            for phi in phis:
                log.info("moving magnet to Phi: %g deg, Theta: %g deg"%(phi, theta))
                self.magnet.set_vector_field()
                # wait for all motion to finish
                while self.magnet.in_motion:
                    sleep(0.05)
                errors = self.magnet.errors
                for err in errors:
                    log.warning('%s'%err)

                x = self.magnet.motion_inst.x.position
                y = self.magnet.motion_inst.y.position

                xfields = np.array([])
                yfields = np.array([])
                zfields = np.array([])
                for j in range(self.num_averages):
                    sleep(self.delay)
                    log.info("Recording average %d of %d"%(j+1,self.num_averages))
                    progress_iterator += 1
                    self.emit('progress',int(100*progress_iterator/num_progress))
                    xfields = np.append(xfields,self.hall_probe.x_field)
                    yfields = np.append(yfields,self.hall_probe.y_field)
                    zfields = np.append(zfields,self.get_Bz())
                self.emit("results", {
                "Phi": phi,
                "Theta": theta,
                "X":x,
                "Y":y,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields)
                })
                if self.should_stop():
                    log.warning("Caught stop flag in procedure")
                    break # out of x steps
            else: # to catch nested loops
                continue
            break # out of y steps


    def shutdown(self):
        log.info("Done with image scan. Shutting down instruments")
        self.magnet.voltage = 0.

class icarusCalibCheckGUI(ManagedImageWindow):
        def __init__(self):
            super().__init__(
                procedure_class=icarusCalibCheckProcedure,
                displays=[
                    'mag_field',
                    'num_averages',
                    'phi_start',
                    'phi_end',
                    'theta_start',
                    'theta_end'
                    ],
                x_axis='Phi',
                y_axis='Theta',
                z_axis='Xfield_avg'
            )
            self.setWindowTitle('Icarus Calib Check GUI')

        def _setup_ui(self):
            """
            Loads custom QT UI
            """
            super()._setup_ui()
            self.inputs.hide()
            self.run_directory = os.path.dirname(os.path.realpath(__file__))
            self.inputs = fromUi(os.path.join(self.run_directory,'calibrationCheck_gui.ui'))

        def make_procedure(self):
            procedure = icarusCalibCheckProcedure()

            procedure.name = self.inputs.name.text()

            procedure.mag_field = self.inputs.mag_field.value()
            procedure.num_averages = self.inputs.num_averages.value()
            procedure.delay = self.inputs.delay.value()
            procedure.phi = self.inputs.phi.value()

            procedure.phi_start = self.inputs.phi_start.value()
            procedure.phi_end = self.inputs.phi_end.value()
            procedure.phi_step = self.inputs.phi_step.value()
            procedure.theta_start = self.inputs.theta_start.value()
            procedure.theta_end = self.inputs.theta_end.value()
            procedure.theta_step = self.inputs.theta_step.value()

            return procedure

        def queue(self):
            fname = unique_filename(
                self.inputs.save_dir.text(),
                dated_folder=True,
                prefix=self.inputs.name.text() + '_calibrationCheck_',
                suffix=''
            )
            procedure = self.make_procedure()
            results = Results(procedure, fname)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = icarusCalibCheckGUI()
    window.show()
    sys.exit(app.exec_())
