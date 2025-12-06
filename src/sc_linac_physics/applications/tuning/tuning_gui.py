from typing import List

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QComboBox, QCheckBox
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from edmbutton import PyDMEDMDisplayButton
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMTimePlot, PyDMSpinbox, PyDMEnumComboBox, PyDMLabel
from pydm.widgets.display_format import DisplayFormat
from pydm.widgets.timeplot import updateMode
from qtpy import QtCore

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_rack import TuneRack
from sc_linac_physics.applications.tuning.tune_stepper import TuneStepper
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.qt import CollapsibleGroupBox, make_rainbow
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES
from sc_linac_physics.utils.sc_linac.rack import Rack

logger = custom_logger(
    "tuning_gui", log_filename="tuning_gui", log_dir=TUNE_LOG_DIR
)

# Constants
CHIRP_FREQUENCY_OFFSET_HZ = 400e3
DEFAULT_TIME_SPAN_SECONDS = 3600
GRID_COLUMNS = 2
TUNE_MACHINE = Machine(
    cavity_class=TuneCavity, rack_class=TuneRack, stepper_class=TuneStepper
)


class LabeledSpinbox:
    """A labeled spinbox widget combining a PyDMSpinbox with a descriptive label.

    Attributes:
        spinbox: The PyDMSpinbox widget for numerical input
        label: QLabel showing the channel name
        layout: Horizontal layout containing the label and spinbox
    """

    def __init__(self, init_channel: str) -> None:
        """Initialize a new labeled spinbox.

        Args:
            init_channel: The PV channel to connect to
        """
        self.spinbox: PyDMSpinbox = PyDMSpinbox(init_channel=init_channel)
        self.spinbox.showStepExponent = False
        self.label: QLabel = QLabel(init_channel.split(":")[-1])
        self.layout: QHBoxLayout = QHBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.spinbox)


class CavitySection(QObject):
    """GUI section for controlling and monitoring a single cavity."""

    def __init__(
        self,
        cavity: TuneCavity,
        parent: QObject | None = None,
        compact: bool = False,
    ) -> None:
        """Initialize a new cavity control section.

        Args:
            cavity: The cavity to control
            parent: Parent QObject for Qt ownership
            compact: Whether to use compact layout (default: False)
        """
        super().__init__(parent)
        self.parent_obj: QObject = parent
        self.cavity: TuneCavity = cavity
        self.compact: bool = compact

        self.tune_state: PyDMEnumComboBox = PyDMEnumComboBox(
            init_channel=cavity.tune_config_pv
        )

        self.groupbox = QGroupBox(
            f"Cav {cavity.number}" if compact else f"Cavity {cavity.number}"
        )
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)

        if compact:
            layout.setSpacing(2)
            layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self.tune_state)

        # Status label
        self.status_label = PyDMLabel(init_channel=cavity.status_msg_pv)
        self.status_label.displayFormat = DisplayFormat.String
        layout.addWidget(self.status_label)

        # Cold landing button and abort
        button_layout = QHBoxLayout()
        if compact:
            button_layout.setSpacing(2)

        self.cold_button: QPushButton = QPushButton(
            "Cold" if compact else "Move to Cold Landing"
        )
        self.cold_button.clicked.connect(self.on_cold_button_clicked)
        self.cold_button.setToolTip("Move to Cold Landing")
        button_layout.addWidget(self.cold_button)

        self.abort_button: QPushButton = QPushButton(
            "X" if compact else "Abort"
        )
        self.abort_button.clicked.connect(self.cavity.trigger_abort)
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.setToolTip("Abort current operation")
        if compact:
            self.abort_button.setMaximumWidth(30)
        button_layout.addWidget(self.abort_button)

        layout.addLayout(button_layout)

        # Expert options
        if not compact:
            # Full expert options section
            expert_layout = self._create_expert_controls()
            expert_options = CollapsibleGroupBox(
                f"Show {cavity} expert options", expert_layout
            )
            layout.addWidget(expert_options)
        else:
            # Compact mode: just add an expert button
            expert_button = QPushButton("⚙")
            expert_button.setMaximumWidth(30)
            expert_button.setToolTip("Expert options")
            expert_button.clicked.connect(self.show_expert_dialog)
            button_layout.addWidget(expert_button)

    def on_cold_button_clicked(self):
        """Handle cold landing button click - set RF state then trigger start."""
        # Get the RF state from the parent Tuner display
        use_rf = (
            self.parent_obj.get_use_rf_state() if self.parent_obj else False
        )

        logger.info(f"Cold landing {self.cavity} with use_rf={use_rf}")

        # Set the RF usage state
        self.cavity.use_rf = 1 if use_rf else 0

        # Trigger the cold landing
        self.cavity.trigger_start()

    def _create_expert_controls(self) -> QGridLayout:
        """Create expert control layout."""
        self.motor_speed: LabeledSpinbox = LabeledSpinbox(
            init_channel=self.cavity.stepper_tuner.speed_pv
        )
        self.max_steps: LabeledSpinbox = LabeledSpinbox(
            init_channel=self.cavity.stepper_tuner.max_steps_pv
        )
        self.chirp_button: QPushButton = QPushButton("Set Chirp ±400kHz")
        self.chirp_button.clicked.connect(self.set_chirp_range)

        expert_layout = QGridLayout()
        expert_layout.addLayout(self.motor_speed.layout, 0, 0)
        expert_layout.addLayout(self.max_steps.layout, 0, 1)
        expert_layout.addWidget(self.chirp_button, 1, 0, 1, 2)

        return expert_layout

    def set_chirp_range(self):
        """Set chirp frequency range to ±400kHz."""
        logger.info(f"Setting chirp range for {self.cavity}")
        try:
            self.cavity.chirp_freq_start = -CHIRP_FREQUENCY_OFFSET_HZ
            self.cavity.chirp_freq_stop = CHIRP_FREQUENCY_OFFSET_HZ
        except Exception as e:
            logger.error(f"Error setting chirp range: {e}")

    def show_expert_dialog(self):
        """Show expert options in a separate dialog (for compact mode)."""
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self.groupbox)
        dialog.setWindowTitle(f"Expert Options - Cavity {self.cavity.number}")
        dialog.resize(400, 200)
        dialog_layout = QVBoxLayout()
        dialog.setLayout(dialog_layout)

        # Create expert controls
        expert_layout = self._create_expert_controls()

        dialog_layout.addLayout(expert_layout)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.close)
        dialog_layout.addWidget(button_box)

        dialog.exec_()


class RackScreen(QObject):
    def __init__(self, rack: Rack, parent=None):
        super().__init__(parent)
        self.rack: TuneRack = rack
        self._parent = parent

        # Create plot
        self.detune_plot: PyDMTimePlot = PyDMTimePlot()
        self.detune_plot.setTimeSpan(DEFAULT_TIME_SPAN_SECONDS)
        self.detune_plot.updateMode = updateMode.AtFixedRate
        self.detune_plot.setPlotTitle(f"{rack} Detunes")
        self.detune_plot.showLegend = True

        # Main container
        self.groupbox = QGroupBox(f"{rack}")
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(4, 4, 4, 4)
        self.groupbox.setLayout(main_layout)

        # Use splitter for adjustability
        from PyQt5.QtWidgets import QSplitter

        splitter = QSplitter(QtCore.Qt.Horizontal)

        # PLOT - takes most space
        splitter.addWidget(self.detune_plot)

        # CONTROLS - compact side panel
        control_panel = self._create_compact_control_panel()
        splitter.addWidget(control_panel)

        # Initial sizes: 80% plot, 20% controls
        splitter.setSizes([800, 200])
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # Populate plot AFTER creating UI
        self.populate_detune_plot()

    def on_rack_cold_button_clicked(self):
        """Handle rack cold landing button click - set RF state then trigger start."""
        # Get the RF state from the parent Tuner display
        use_rf = self._parent.get_use_rf_state() if self._parent else False

        logger.info(f"Cold landing {self.rack} with use_rf={use_rf}")

        # Set the RF usage state for the rack
        self.rack.use_rf = 1 if use_rf else 0

        # Trigger the cold landing
        self.rack.trigger_start()

    def _create_compact_control_panel(self) -> QWidget:
        """Create space-efficient control panel."""
        from PyQt5.QtWidgets import QScrollArea, QFrame

        panel = QWidget()
        panel.setMaximumWidth(350)
        panel_layout = QVBoxLayout()
        panel_layout.setSpacing(4)
        panel_layout.setContentsMargins(4, 4, 4, 4)
        panel.setLayout(panel_layout)

        # Rack controls
        rack_file = f"/usr/local/lcls/tools/edm/display/llrf/rf_srf_freq_scan_rack{self.rack.rack_name}.edl"
        self.edm_screen = PyDMEDMDisplayButton(filename=rack_file)
        self.edm_screen.setText("EDM")
        self.edm_screen.macros = list(self.rack.cavities.values())[
            0
        ].edm_macro_string

        rack_controls = QHBoxLayout()
        rack_controls.addWidget(self.edm_screen)

        self.cold_button = QPushButton("All → Cold")
        self.cold_button.clicked.connect(self.on_rack_cold_button_clicked)
        rack_controls.addWidget(self.cold_button)

        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.rack.trigger_abort)
        rack_controls.addWidget(self.abort_button)

        panel_layout.addLayout(rack_controls)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        panel_layout.addWidget(line)

        # Scrollable cavity sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        cavity_container = QWidget()
        cavity_layout = QVBoxLayout()
        cavity_layout.setSpacing(4)
        cavity_container.setLayout(cavity_layout)

        self.cav_sections: List[CavitySection] = []
        for cavity in self.rack.cavities.values():
            cav_section = CavitySection(
                cavity, parent=self._parent, compact=True
            )
            self.cav_sections.append(cav_section)
            cavity_layout.addWidget(cav_section.groupbox)

        cavity_layout.addStretch()
        scroll.setWidget(cavity_container)
        panel_layout.addWidget(scroll)

        return panel

    def populate_detune_plot(self):
        """Populate the detune plot with cavity data."""
        detune_pvs = []
        cold_pvs = []
        for cavity in self.rack.cavities.values():
            detune_pvs.append(cavity.detune_best_pv)
            cold_pvs.append(cavity.df_cold_pv)

        colors = make_rainbow(len(detune_pvs))

        for idx, (detune_pv, cold_pv) in enumerate(zip(detune_pvs, cold_pvs)):
            r, g, b, a = colors[idx]
            solid_color = QColor(r, g, b, a)
            dashed_color = QColor(r, g, b, 127)

            self.detune_plot.addYChannel(
                y_channel=detune_pv,
                useArchiveData=True,
                color=solid_color,
                yAxisName="Detune (Hz)",
            )
            self.detune_plot.addYChannel(
                y_channel=cold_pv,
                useArchiveData=True,
                color=dashed_color,
                yAxisName="Detune (Hz)",
                lineStyle=QtCore.Qt.DashLine,
            )


class Tuner(Display):
    """Main display for the SRF Tuner application.

    This is the top-level window that allows selection of a cryomodule
    and displays its associated cavity tuning controls.

    Attributes:
        cm_selector: Combobox for selecting active cryomodule
        use_rf_checkbox: Global checkbox for RF usage
        machine: The machine instance containing all cavities
        rack_screen_cache: Cache of created rack screens
        current_rack_screens: Currently displayed rack screens
    """

    def __init__(self) -> None:
        """Initialize the tuner display."""
        super().__init__()
        self.setWindowTitle("SRF Tuner")

        main_layout: QVBoxLayout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create top control bar
        control_bar_layout = QHBoxLayout()

        # Cryomodule selector
        selector_label = QLabel("Cryomodule:")
        selector_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.cm_selector = QComboBox()
        self.cm_selector.addItems(ALL_CRYOMODULES)
        self.cm_selector.currentTextChanged.connect(self.on_cryomodule_changed)
        self.cm_selector.setMinimumWidth(150)

        control_bar_layout.addWidget(selector_label)
        control_bar_layout.addWidget(self.cm_selector)
        control_bar_layout.addSpacing(20)

        # Global RF usage checkbox
        use_rf_label = QLabel("Use RF:")
        use_rf_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.use_rf_checkbox = QCheckBox()
        self.use_rf_checkbox.setChecked(True)  # Default to using RF
        self.use_rf_checkbox.setToolTip(
            "Enable RF usage for cold landing operations (Feature coming soon)"
        )
        self.use_rf_checkbox.setEnabled(
            False
        )  # Keep disabled until feature is ready
        # Connect to confirmation handler (will be active when enabled)
        self.use_rf_checkbox.stateChanged.connect(self._on_use_rf_changed)

        control_bar_layout.addWidget(use_rf_label)
        control_bar_layout.addWidget(self.use_rf_checkbox)
        control_bar_layout.addSpacing(20)

        # Cryomodule-level controls
        self.cm_cold_button = QPushButton("Move CM to Cold Landing")
        self.cm_cold_button.clicked.connect(self.on_cm_cold_button_clicked)
        self.cm_cold_button.setToolTip(
            "Move all cavities in cryomodule to cold landing"
        )
        control_bar_layout.addWidget(self.cm_cold_button)

        self.cm_abort_button = QPushButton("Abort CM")
        self.cm_abort_button.clicked.connect(self.on_cm_abort_button_clicked)
        self.cm_abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.cm_abort_button.setToolTip("Abort all operations in cryomodule")
        control_bar_layout.addWidget(self.cm_abort_button)

        control_bar_layout.addStretch()

        main_layout.addLayout(control_bar_layout)

        # Container for rack displays
        self.rack_container = QWidget()
        self.rack_layout = QHBoxLayout()
        self.rack_layout.setContentsMargins(0, 0, 0, 0)
        self.rack_container.setLayout(self.rack_layout)
        main_layout.addWidget(self.rack_container)

        self.machine: Machine = Machine(
            cavity_class=TuneCavity,
            stepper_class=TuneStepper,
            rack_class=TuneRack,
        )

        # Cache for created rack screens
        self.rack_screen_cache: dict[str, tuple[RackScreen, RackScreen]] = {}
        self.current_rack_screens: tuple[RackScreen, RackScreen] | None = None
        self.current_cryomodule = None

        # Load first cryomodule
        if ALL_CRYOMODULES:
            self.on_cryomodule_changed(ALL_CRYOMODULES[0])

    def _on_use_rf_changed(self, state):
        """Handle RF usage checkbox state change with confirmation.

        Args:
            state: Qt.CheckState value (0=unchecked, 2=checked)
        """
        from PyQt5.QtWidgets import QMessageBox
        from PyQt5.QtCore import Qt

        # If unchecking (disabling RF), ask for confirmation
        if state == Qt.Unchecked:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Confirm Disable RF")
            msg_box.setText("Are you sure you want to disable RF usage?")
            msg_box.setInformativeText(
                "Disabling RF will affect all subsequent cold landing operations:\n\n"
                "• Cavity tuning may be less accurate\n"
                "• Cold landing operations will proceed without RF feedback\n"
                "• This applies to all cavities in all cryomodules\n\n"
                "Continue with disabling RF?"
            )
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)

            # Make the warning more visible
            msg_box.button(QMessageBox.Yes).setStyleSheet(
                "background-color: #ffaa00; font-weight: bold;"
            )

            reply = msg_box.exec_()

            if reply == QMessageBox.No:
                # User cancelled - re-enable the checkbox
                self.use_rf_checkbox.blockSignals(True)
                self.use_rf_checkbox.setChecked(True)
                self.use_rf_checkbox.blockSignals(False)
                logger.info("User cancelled disabling RF")
            else:
                logger.warning("RF usage disabled by user")
        else:
            # Enabling RF - no confirmation needed
            logger.info("RF usage enabled")

    def get_use_rf_state(self) -> bool:
        """Get the current state of the global RF usage checkbox.

        Returns:
            True if RF should be used, False otherwise
        """
        return self.use_rf_checkbox.isChecked()

    def on_cm_cold_button_clicked(self):
        """Handle cryomodule cold landing button click."""
        if not self.current_cryomodule:
            logger.warning("No cryomodule selected")
            return

        use_rf = self.get_use_rf_state()
        logger.info(
            f"Cold landing {self.current_cryomodule} with use_rf={use_rf}"
        )

        # Set RF usage for the cryomodule
        self.current_cryomodule.use_rf = 1 if use_rf else 0

        # Trigger cold landing for the cryomodule
        self.current_cryomodule.trigger_start()

    def on_cm_abort_button_clicked(self):
        """Handle cryomodule abort button click."""
        if not self.current_cryomodule:
            logger.warning("No cryomodule selected")
            return

        logger.info(f"Aborting operations for {self.current_cryomodule}")
        self.current_cryomodule.trigger_abort()

    def on_cryomodule_changed(self, cm_name: str) -> None:
        """Handle cryomodule selection change.

        Args:
            cm_name: Name of the selected cryomodule
        """
        if not cm_name:  # Handle empty selection
            return

        logger.info(f"Switching to cryomodule: {cm_name}")

        # Update current cryomodule
        self.current_cryomodule = self.machine.cryomodules[cm_name]

        # Clear current displays
        self._clear_rack_displays()

        # Check cache first
        if cm_name in self.rack_screen_cache:
            logger.debug(f"Loading {cm_name} from cache")
            rack_a_screen, rack_b_screen = self.rack_screen_cache[cm_name]
        else:
            # Create new rack screens
            logger.debug(f"Creating new screens for {cm_name}")
            cm = self.current_cryomodule
            rack_a_screen = RackScreen(cm.rack_a, parent=self)
            rack_b_screen = RackScreen(cm.rack_b, parent=self)

            # Cache for future use
            self.rack_screen_cache[cm_name] = (rack_a_screen, rack_b_screen)

        # Add to layout
        self.rack_layout.addWidget(rack_a_screen.groupbox)
        self.rack_layout.addWidget(rack_b_screen.groupbox)
        self.current_rack_screens = (rack_a_screen, rack_b_screen)

        # Update window title
        self.setWindowTitle(f"SRF Tuner - {cm_name}")

    def _clear_rack_displays(self) -> None:
        """Remove current rack displays from layout."""
        if self.current_rack_screens:
            for rack_screen in self.current_rack_screens:
                self.rack_layout.removeWidget(rack_screen.groupbox)
                rack_screen.groupbox.setParent(
                    None
                )  # Hide but don't delete (for caching)
            self.current_rack_screens = None
