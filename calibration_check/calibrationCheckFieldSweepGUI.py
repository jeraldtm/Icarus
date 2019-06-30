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
from itertools import product


class icarusCalibCheckProcedure(Procedure):
    """
    Procedure for making a raser image of the field components of Daedalus
    """

    # control parameters
    calib_name = Parameter("Calibration Name", default='')
    mag_field = FloatParameter("Magnetic field strength", units="T", default=0.1)
    num_averages = IntegerParameter("Number of Averages", default=1)
    delay = FloatParameter("Delay between averages", units="s", default=.1)

    mag_calib_name = Parameter("Magnet Calibration Filename", default='./calibrations/icarus')

    phi_start = FloatParameter("Phi Start Position", units="mm", default=10.)
    phi_end = FloatParameter("Phi End Position", units="mm", default=13.)
    phi_step = FloatParameter("Phi Scan Step Size", units="mm", default=0.1)
    theta_start = FloatParameter("Theta Start Position", units="mm", default=10.)
    theta_end = FloatParameter("Theta End Position", units="mm", default=13.)
    theta_step = FloatParameter("Theta Scan Step Size", units="mm", default=0.1)

    first = True
    last = True

    DATA_COLUMNS = ["phi","theta","X", "Y", "act_phi", "act_theta", "Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std",
                    "Yfield_std","Zfield_std", "Bmag", "V", "act_V"  ]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
        	log.warning('%s' % err)
        self.magnet.load_calibration_params(self.mag_calib_name)

        log.info("Setting magnet field to %.2f T"%self.mag_field)
        log.info("Setting magnet position to Phi: {0}, Theta: {1}".format(self.phi_start, self.theta_start))
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
                self.magnet.set_vector_field(self.mag_field, phi, theta)
                # wait for all motion to finish
                while self.magnet.in_motion:
                    sleep(0.05)
                errors = self.magnet.errors
                for err in errors:
                    log.warning('%s'%err)

                x = self.magnet.motion_inst.x.position
                y = self.magnet.motion_inst.y.position
                v = self.magnet.getVolts()

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
                "phi": phi,
                "theta": theta,
                "X":x,
                "Y":y,
                "act_phi": np.arctan(np.mean(xfields)/np.mean(yfields))*180/np.pi,
                "act_theta": np.arctan(np.mean(zfields)/np.sqrt(np.mean(yfields)**2 + np.mean(xfields)**2))*180/np.pi,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields),
                "Bmag": np.sqrt(np.mean(xfields)**2 + np.mean(yfields)**2 + np.mean(zfields)**2),
                "V" : self.magnet.volts,  
                "act_V" : v
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

        SWEEP_PARAM_NAMES = ['field']
        NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

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
                x_axis='phi',
                y_axis='theta',
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
            self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/calibrationCheckFieldSweep_gui.ui'))

        def make_procedure(self):
            procedure = icarusCalibCheckProcedure()

            procedure.name = self.inputs.name.text()
            procedure.mag_calib_name = os.path.join(self.run_directory,'calibrations/icarus')
            procedure.mag_field = self.inputs.mag_field.value()
            procedure.num_averages = self.inputs.num_averages.value()
            procedure.delay = self.inputs.delay.value()

            procedure.phi_start = self.inputs.phi_start.value()
            procedure.phi_end = self.inputs.phi_end.value()
            procedure.phi_step = self.inputs.phi_step.value()
            procedure.theta_start = self.inputs.theta_start.value()
            procedure.theta_end = self.inputs.theta_end.value()
            procedure.theta_step = self.inputs.theta_step.value()

            return procedure

        def make_field_sweep(self, fields):
                """
                Makes a series of procedures varying fields
                """
                procedures = []
                for field in fields:
                    procedure = self.make_procedure()
                    procedure.mag_field = field
                    procedure.first = False
                    procedure.last = False
                    procedures.append(procedure)
                return procedures

        def make_procedures(self):
                """
                Constructs a series of procedures based on gui options
                """
                procedures = []

                # Number of parameters which can vary. Change this if more are added!
                self.NUM_SWEEP_PARAMS = 1

                # make arrays of all of the possible parameter values we want
                fields = np.arange(self.inputs.mag_field.value(), self.inputs.field_end.value(), self.inputs.field_step.value())
                if self.inputs.field_end.value() not in fields: # ensure we capture the endpoint
                    fields = np.append(fields,self.inputs.field_end.value())
            
                # make lists of them where the index of the list is the index of the
                # combobox or tab which corresponds to them
                sweep_values = [fields]
                # Need separate start values in case we're not sweeping and start
                # is larger than stop in UI
                start_values = [self.inputs.mag_field.value()]

                used_pnames = []
                used_pvals = []
                sweep_param_indices = {}
                for gui_item in dir(self.inputs):
                    if gui_item.startswith('sweep_param_'):
                        item_number = int(gui_item.split('_')[-1])
                        sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex() # TODO: does this work?
                if self.inputs.do_sweeps.isChecked():
                    used_indices = [] # keeping track of which parameters swept so no repeats
                    for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep parameter values
                        param_index = sweep_param_indices[param_number]
                        if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
                            used_indices.append(param_index)
                            used_pnames.append(self.SWEEP_PARAM_NAMES[param_index])
                            used_pvals.append(sweep_values[param_index])
                    # add on any that weren't swept
                    for i in range(self.NUM_SWEEP_PARAMS):
                        if i not in used_indices:
                            used_pvals.append([start_values[i]])
                            used_pnames.append(self.SWEEP_PARAM_NAMES[i])
                    # Reverse order so that product gives us what we want
                    used_pvals = used_pvals[::-1]
                    used_pnames = used_pnames[::-1]
                else:
                    for i in range(self.NUM_SWEEP_PARAMS):
                        used_pnames.append(self.SWEEP_PARAM_NAMES[i])
                        used_pvals.append([start_values[i]])

                # make a cartesian product of all of the swept values
                pvals = product(*used_pvals)
                for val_combo in pvals:
                    # for each parameter combination, create a procedure and set the
                    # appropriate parameter values
                    procedure = self.make_procedure()
                    for i, val in enumerate(val_combo):
                        setattr(procedure, used_pnames[i], val_combo[i])
                    procedures.append(procedure)

                # Set first and last procedures to make sweeps faster and have less
                # voltage, field and angle oscillations.
                procedures[0].first = True
                procedures[-1].last = True

                return procedures

        def start_series(self):
            """
            Creates the header and filename of the series file for these scans.
            """
            # ensure we have some sample name
            pre = '_2Vcalibcheck_'
            suf = ''
            series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                           suffix=suf,dated_folder=True,ext='txt')

            field_section = '# Initial Field: %g T\n'%self.inputs.mag_field.value()
            field_section += '# Final Field: %g T\n'%self.inputs.field_end.value()
            field_section += '# Field Step: %g T\n'%self.inputs.field_step.value()

            series_header = '# swept procedure column: field_strength\n'
            sweep_sections = [field_section, None]
            used_sections = []
            sweep_param_indices = {}

            # adding sections pertaining to sweeps
            for gui_item in dir(self.inputs):
                if gui_item.startswith('sweep_param_'):
                    item_number = int(gui_item.split('_')[-1])
                    sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex() # TODO: does this work?
            if self.inputs.do_sweeps.isChecked():
                used_indices = [] # keeping track of which parameters swept so no repeats
                for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep sections
                    param_index = sweep_param_indices[param_number]
                    if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
                        series_header += '# swept series parameter: %s\n'%self.SWEEP_PARAM_NAMES[param_index]
                        used_sections.append(sweep_sections[param_index])
                series_header += '# Parameters:\n#\n'
                for section in used_sections:
                    series_header += section
            else:
                for i in range(self.NUM_SWEEP_PARAMS):
                    used_pnames.append(self.SWEEP_PARAM_NAMES[i])
                    used_pvals.append([start_values[i]])
            series_header += '#\n# Files in Series:\n#\n'
            return series_fname, series_header


        def queue(self):
                direc = self.inputs.save_dir.text()
                # create list of procedures to run
                procedures = self.make_procedures()
                do_sweep = self.inputs.do_sweeps.isChecked()
                if do_sweep:
                    series_fname, series_header = self.start_series()
                    self.last_series_fname = series_fname
                    series_file = open(series_fname,'w')
                    series_file.write(series_header)

                for procedure in procedures:
                    # ensure *some* sample name exists so Results.load() works

                    # create files
                    pre = '_2VcalibCheck_F{field:05.1f}'.format(
                        field=procedure.mag_field,
                    )
                    suf = ''
                    filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                               prefix=pre)

                    if do_sweep:
                        series_file.write(os.path.split(filename)[-1] + '\n')

                    # Queue experiment
                    results = Results(procedure,filename)
                    experiment = self.new_experiment(results)
                    self.manager.queue(experiment)
                if do_sweep:
                    series_file.close()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = icarusCalibCheckGUI()
    window.show()
    sys.exit(app.exec_())
