import sys
from random import choice
from unittest import TestCase
from unittest.mock import MagicMock, call

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from applications.quench_processing.quench_gui import QuenchGUI
from applications.quench_processing.quench_linac import QUENCH_MACHINE
from applications.quench_processing.quench_worker import QuenchWorker
from utils.qt import make_rainbow
from utils.sc_linac.decarad import Decarad

if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()


class TestQuenchGUI(TestCase):
    @classmethod
    def setUpClass(cls):
        print("Testing Quench GUI")
        cls.test_num = 0
        cls.non_hl_iterator = QUENCH_MACHINE.non_hl_iterator

    def setUp(self):
        self.gui = QuenchGUI()
        self.test_num += 1
        self.gui.status_label.setStyleSheet = MagicMock()
        self.gui.status_label.setText = MagicMock()
        self.gui.start_button.setEnabled = MagicMock()

        self.cavity = next(self.non_hl_iterator)
        self.gui.current_cav = self.cavity
        self.gui.current_cm = self.cavity.cryomodule
        self.gui.cm_combobox.setCurrentText(self.cavity.cryomodule.name)
        self.gui.cav_combobox.setCurrentText(str(self.cavity.number))
        msg = f"Testing {self.gui.current_cav}"
        print(msg)
        self.msg = msg

    def tearDown(self) -> None:
        app.closeAllWindows()

    @classmethod
    def tearDownClass(cls):
        print("Done testing quench gui")

    def test_handle_status(self):
        self.gui.handle_status(self.msg)
        self.gui.status_label.setStyleSheet.assert_called_with("color: blue;")
        self.gui.status_label.setText.assert_called_with(self.msg)

    def test_handle_error(self):
        self.gui.handle_error(self.msg)
        self.gui.status_label.setStyleSheet.assert_called_with("color: red;")
        self.gui.status_label.setText.assert_called_with(self.msg)
        self.gui.start_button.setEnabled.assert_called_with(True)

    def test_handle_finished(self):
        self.gui.handle_finished(self.msg)
        self.gui.status_label.setStyleSheet.assert_called_with("color: green;")
        self.gui.status_label.setText.assert_called_with(self.msg)
        self.gui.start_button.setEnabled.assert_called_with(True)

    def test_process(self):
        self.gui.current_decarad = Decarad(choice([1, 2]))
        self.gui.make_quench_worker = MagicMock()
        self.gui.quench_worker = MagicMock()
        self.gui.process()
        self.gui.start_button.setEnabled.assert_called_with(False)
        self.assertEqual(self.gui.current_cav.decarad, self.gui.current_decarad)
        self.gui.make_quench_worker.assert_called()
        self.gui.quench_worker.start.assert_called()

    def test_make_quench_worker(self):
        self.gui.quench_worker = None
        self.gui.make_quench_worker()
        self.assertIsInstance(self.gui.quench_worker, QuenchWorker)

    def test_clear_connections(self):
        signal = MagicMock()
        self.gui.clear_connections(signal)
        signal.disconnect.assert_called()

    def test_clear_all_connections(self):
        self.gui.rf_controls = MagicMock()
        self.gui.clear_connections = MagicMock()
        self.gui.clear_all_connections()
        self.gui.clear_connections.assert_called_with(
            self.gui.decarad_off_button.clicked
        )

    def test_update_timeplot(self):
        self.gui.amp_rad_timeplot = MagicMock()
        decarad = choice([1, 2])
        self.gui.decarad_combobox.setCurrentText(str(decarad))
        self.gui.update_timeplot()
        self.gui.amp_rad_timeplot.clearCurves.assert_called()
        self.gui.amp_rad_timeplot.addYChannel.assert_called()

        colors = make_rainbow(num_colors=11)
        channels = [self.cavity.aact_pv] + [
            head.raw_dose_rate_pv for head in Decarad(decarad).heads.values()
        ]
        axes = ["Amplitude"] + ["Radiation" for _ in range(10)]
        calls = []
        for channel, (r, g, b, a), axis in zip(channels, colors, axes):
            calls.append(
                call(
                    y_channel=channel,
                    useArchiveData=True,
                    color=QColor(r, g, b, a),
                    yAxisName=axis,
                )
            )
        self.gui.amp_rad_timeplot.addYChannel.assert_has_calls(calls, any_order=True)

    def test_update_decarad(self):
        decarad_num = choice([1, 2])
        self.gui.decarad_combobox.setCurrentText(str(decarad_num))
        self.gui.update_timeplot = MagicMock()
        self.gui.clear_connections = MagicMock()
        self.gui.decarad_on_button.clicked = MagicMock()
        self.gui.decarad_off_button.clicked = MagicMock()

        self.gui.update_decarad()

        self.assertEqual(self.gui.current_decarad, Decarad(decarad_num))
        self.gui.update_timeplot.assert_called()
        self.gui.clear_connections.assert_called()
        self.gui.decarad_on_button.clicked.connect.assert_called_with(
            self.gui.current_decarad.turn_on
        )
        self.gui.decarad_off_button.clicked.connect.assert_called_with(
            self.gui.current_decarad.turn_off
        )
        self.assertEqual(
            self.gui.current_decarad.power_status_pv,
            self.gui.decarad_status_readback.channel,
        )
        self.assertEqual(
            self.gui.current_decarad.voltage_readback_pv,
            self.gui.decarad_voltage_readback.channel,
        )

    def test_update_cm(self):
        self.gui.clear_all_connections = MagicMock()
        self.gui.update_timeplot = MagicMock()
        self.gui.waveform_updater.updatePlot = MagicMock()
        self.gui.rf_controls.ssa_on_button = MagicMock()
        self.gui.rf_controls.ssa_off_button = MagicMock()
        self.gui.rf_controls.rf_on_button = MagicMock()
        self.gui.rf_controls.rf_off_button = MagicMock()
        self.gui.start_button = MagicMock()
        self.gui.abort_button = MagicMock()

        self.gui.update_cm()
        self.gui.clear_all_connections.assert_called()
        self.gui.update_timeplot.assert_called()
        self.gui.waveform_updater.updatePlot.assert_called()
        self.gui.rf_controls.ssa_on_button.clicked.connect.assert_called_with(
            self.cavity.ssa.turn_on
        )
        self.gui.rf_controls.ssa_off_button.clicked.connect.assert_called_with(
            self.cavity.ssa.turn_off
        )
        self.assertEqual(
            self.gui.rf_controls.ssa_readback_label.channel, self.cavity.ssa.status_pv
        )

        self.assertEqual(
            self.gui.rf_controls.rf_mode_combobox.channel, self.cavity.rf_mode_ctrl_pv
        )
        self.assertEqual(
            self.gui.rf_controls.rf_mode_readback_label.channel, self.cavity.rf_mode_pv
        )
        self.gui.rf_controls.rf_on_button.clicked.connect.assert_called_with(
            self.cavity.turn_on
        )
        self.gui.rf_controls.rf_off_button.clicked.connect.assert_called_with(
            self.cavity.turn_off
        )
        self.assertEqual(
            self.gui.rf_controls.rf_status_readback_label.channel,
            self.cavity.rf_state_pv,
        )

        self.assertEqual(self.gui.rf_controls.ades_spinbox.channel, self.cavity.ades_pv)
        self.assertEqual(
            self.gui.rf_controls.aact_readback_label.channel, self.cavity.aact_pv
        )
        self.assertEqual(
            self.gui.rf_controls.srf_max_spinbox.channel, self.cavity.srf_max_pv
        )
        self.assertEqual(
            self.gui.rf_controls.srf_max_readback_label.channel, self.cavity.srf_max_pv
        )

        self.gui.start_button.clicked.connect.assert_called_with(self.gui.process)
        self.gui.abort_button.clicked.connect.assert_called_with(
            self.cavity.request_abort
        )
