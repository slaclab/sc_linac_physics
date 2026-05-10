# tests/applications/tuning/conftest.py
"""Fixtures specific to tuning GUI tests."""

from unittest.mock import Mock, patch

import pytest
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QWidget, QLabel


# Create proper Qt widget mocks that Qt will accept
class MockPyDMWidget(QWidget):
    """Mock PyDM widget that is actually a QWidget."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.init_channel = kwargs.get("init_channel", "")


class MockPyDMEnumComboBox(QWidget):
    """Mock PyDMEnumComboBox."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.init_channel = kwargs.get("init_channel", "")


class MockPyDMLabel(QLabel):
    """Mock PyDMLabel."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.init_channel = kwargs.get("init_channel", "")
        self.displayFormat = None
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False


class MockPyDMSpinbox(QWidget):
    """Mock PyDMSpinbox."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.init_channel = kwargs.get("init_channel", "")
        self.showStepExponent = False


class MockPyDMEDMDisplayButton(QWidget):
    """Mock PyDMEDMDisplayButton."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.filename = kwargs.get("filename", "")
        self.macros = ""

    def setText(self, text):
        pass


class MockEmbeddableArchiverPlot(QWidget):
    """Mock EmbeddableArchiverPlot."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.title = kwargs.get("title", "")
        self.time_span = kwargs.get("time_span", 3600)
        self.add_pv = Mock()


class MockCollapsibleGroupBox(QWidget):
    """Mock CollapsibleGroupBox."""

    def __init__(self, *args, **kwargs):
        super().__init__()


@pytest.fixture
def mock_cavity():
    """Create a mock TuneCavity object for tuning GUI tests."""
    cavity = Mock()
    cavity.number = 1
    cavity.tune_config_pv = "TEST:TUNE:CONFIG"
    cavity.status_msg_pv = "TEST:STATUS:MSG"
    cavity.use_rf = 0
    cavity.chirp_freq_start = 0
    cavity.chirp_freq_stop = 0

    # Stepper tuner
    cavity.stepper_tuner = Mock()
    cavity.stepper_tuner.speed_pv = "TEST:SPEED"
    cavity.stepper_tuner.max_steps_pv = "TEST:MAX_STEPS"

    # PVs
    cavity.detune_best_pv = "TEST:DETUNE"
    cavity.df_cold_pv = "TEST:DF_COLD"
    cavity.edm_macro_string = "CAV=1"

    # Methods
    cavity.__str__ = Mock(return_value="Cavity 1")
    cavity.trigger_abort = Mock()
    cavity.trigger_start = Mock()

    return cavity


@pytest.fixture
def mock_cavity_2():
    """Create a second mock cavity for multi-cavity tests."""
    cavity = Mock()
    cavity.number = 2
    cavity.detune_best_pv = "TEST:CAV2:DETUNE"
    cavity.df_cold_pv = "TEST:CAV2:DF_COLD"
    cavity.edm_macro_string = "CAV=2"
    cavity.tune_config_pv = "TEST:CAV2:TUNE"
    cavity.status_msg_pv = "TEST:CAV2:STATUS"

    cavity.stepper_tuner = Mock()
    cavity.stepper_tuner.speed_pv = "TEST:CAV2:SPEED"
    cavity.stepper_tuner.max_steps_pv = "TEST:CAV2:STEPS"

    cavity.trigger_abort = Mock()
    cavity.trigger_start = Mock()

    return cavity


@pytest.fixture
def mock_rack(mock_cavity, mock_cavity_2):
    """Create a mock TuneRack object."""
    rack = Mock()
    rack.rack_name = "A"
    rack.__str__ = Mock(return_value="Rack A")
    rack.use_rf = 0
    rack.trigger_start = Mock()
    rack.trigger_abort = Mock()
    rack.cavities = {1: mock_cavity, 2: mock_cavity_2}

    return rack


@pytest.fixture
def mock_rack_b():
    """Create a second mock rack (Rack B) with minimal setup."""
    rack = Mock()
    rack.rack_name = "B"
    rack.__str__ = Mock(return_value="Rack B")
    rack.use_rf = 0
    rack.trigger_start = Mock()
    rack.trigger_abort = Mock()
    rack.cavities = {}

    return rack


@pytest.fixture
def mock_machine(mock_rack, mock_rack_b):
    """Create a mock Machine object with cryomodules."""
    machine = Mock()

    cm = Mock()
    cm.rack_a = mock_rack
    cm.rack_b = mock_rack_b
    cm.use_rf = 0
    cm.trigger_start = Mock()
    cm.trigger_abort = Mock()

    machine.cryomodules = {"CM01": cm}

    return machine


@pytest.fixture
def mock_parent(qapp_global):
    """Mock parent widget with RF state for tuning GUI."""
    # Create an actual QObject for parent to avoid Qt type checking issues
    parent = QObject()
    parent.get_use_rf_state = Mock(return_value=True)
    return parent


@pytest.fixture
def pydm_patches():
    """Common patches for PyDM widgets."""
    with (
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMEnumComboBox",
            MockPyDMEnumComboBox,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMLabel",
            MockPyDMLabel,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMSpinbox",
            MockPyDMSpinbox,
        ),
    ):
        yield


@pytest.fixture
def cavity_section_patches():
    """Patches needed for CavitySection tests."""
    with (
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMEnumComboBox",
            MockPyDMEnumComboBox,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMLabel",
            MockPyDMLabel,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.CollapsibleGroupBox",
            MockCollapsibleGroupBox,
        ),
    ):
        yield


@pytest.fixture
def rack_screen_patches():
    """Patches needed for RackScreen tests."""
    mock_plot_class = Mock(return_value=MockEmbeddableArchiverPlot())

    with (
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.EmbeddableArchiverPlot",
            mock_plot_class,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.PyDMEDMDisplayButton",
            MockPyDMEDMDisplayButton,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.CavitySection"
        ) as mock_cav_section,
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.make_rainbow",
            return_value=[[255, 0, 0, 255], [0, 255, 0, 255]],
        ),
    ):

        # Make CavitySection return a mock with a groupbox
        def create_cavity_section(*args, **kwargs):
            section = Mock()
            section.groupbox = QWidget()
            return section

        mock_cav_section.side_effect = create_cavity_section
        yield mock_plot_class


@pytest.fixture
def tuner_patches(mock_machine):
    """Comprehensive patches for Tuner display tests."""

    def create_rack_screen(*args, **kwargs):
        """Create a mock RackScreen with a real QWidget groupbox."""
        screen = Mock()
        screen.groupbox = QWidget()
        screen.rack = (
            kwargs.get("rack")
            if "rack" in kwargs
            else args[0] if args else Mock()
        )
        return screen

    mock_rack_screen = Mock(side_effect=create_rack_screen)

    # Create a mock Machine class that returns our mock immediately
    def mock_machine_init(*args, **kwargs):
        return mock_machine

    with (
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Machine"
        ) as mock_machine_cls,
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.ALL_CRYOMODULES",
            [],
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.RackScreen",
            mock_rack_screen,
        ),
        patch(
            "sc_linac_physics.applications.tuning.tuning_gui.TUNE_MACHINE",
            mock_machine,
        ),
    ):

        # Make Machine() constructor return our mock immediately
        mock_machine_cls.return_value = mock_machine
        yield mock_rack_screen
