# test_q0_measurement_widget.py
import sys
from unittest.mock import patch

import pytest
from PyQt5.QtWidgets import QApplication, QWidget, QGroupBox, QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QComboBox


# Create mock PyDM widgets that inherit from QWidget so they can be added to layouts
class MockPyDMWidget(QWidget):
    """Base mock PyDM widget that behaves like a real QWidget."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Add common PyDM properties
        self.channel = None

    def setProperty(self, name, value):
        """Mock setProperty method."""
        setattr(self, name, value)


class MockPyDMSpinbox(MockPyDMWidget):
    """Mock PyDMSpinbox that behaves like a real spinbox."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._value = 0.0
        self._minimum = 0.0
        self._maximum = 100.0
        self._singleStep = 1.0

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value

    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        self._minimum = value

    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        self._maximum = value

    def singleStep(self):
        return self._singleStep

    def setSingleStep(self, value):
        self._singleStep = value


class MockPyDMLabel(MockPyDMWidget):
    """Mock PyDMLabel that behaves like a real label."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._text = ""

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class MockPyDMPushButton(MockPyDMWidget):
    """Mock PyDMPushButton that behaves like a real button."""

    def __init__(self, text="", *args, **kwargs):
        super().__init__()
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class MockPyDMByteIndicator(MockPyDMWidget):
    """Mock PyDMByteIndicator."""

    def __init__(self, *args, **kwargs):
        super().__init__()


@pytest.fixture
def qapp():
    """Create QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    if app:
        app.quit()


# Create a fixture that handles all the mocking
@pytest.fixture
def mock_pydm():
    """Mock all PyDM imports comprehensively."""
    patches = []

    # List of all possible import patterns we need to patch
    patch_targets = [
        # Direct widget imports (from pydm.widgets import ...)
        "pydm.widgets.PyDMSpinbox",
        "pydm.widgets.PyDMLabel",
        "pydm.widgets.PyDMPushButton",
        "pydm.widgets.PyDMByteIndicator",
        # Module-level imports in target file
        "sc_linac_physics.applications.q0.q0_measurement_widget.PyDMSpinbox",
        "sc_linac_physics.applications.q0.q0_measurement_widget.PyDMLabel",
        "sc_linac_physics.applications.q0.q0_measurement_widget.PyDMPushButton",
        "sc_linac_physics.applications.q0.q0_measurement_widget.PyDMByteIndicator",
    ]

    # Create patches for all possible import patterns
    for target in patch_targets:
        if "PyDMSpinbox" in target:
            patches.append(patch(target, MockPyDMSpinbox))
        elif "PyDMLabel" in target:
            patches.append(patch(target, MockPyDMLabel))
        elif "PyDMPushButton" in target:
            patches.append(patch(target, MockPyDMPushButton))
        elif "PyDMByteIndicator" in target:
            patches.append(patch(target, MockPyDMByteIndicator))

    # Start all patches
    for p in patches:
        p.start()

    # Clean up the import cache to force re-import with mocks
    if "sc_linac_physics.applications.q0.q0_measurement_widget" in sys.modules:
        del sys.modules["sc_linac_physics.applications.q0.q0_measurement_widget"]

    yield

    # Stop all patches
    for p in patches:
        p.stop()


class TestQ0MeasurementWidgetInitialization:
    """Test widget initialization and structure."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_widget_creation(self, widget):
        """Test that widget is created successfully."""
        assert isinstance(widget, QWidget)
        assert widget.layout() is not None

    def test_cryomodule_selection_widgets(self, widget):
        """Test cryomodule selection widgets are created."""
        assert hasattr(widget, "cm_combobox")
        assert isinstance(widget.cm_combobox, QComboBox)

        assert hasattr(widget, "perm_byte")
        assert isinstance(widget.perm_byte, MockPyDMByteIndicator)

        assert hasattr(widget, "perm_label")
        assert isinstance(widget.perm_label, MockPyDMLabel)

    def test_cryo_controls_group(self, widget):
        """Test cryo controls group and its widgets."""
        assert hasattr(widget, "groupBox_3")
        assert isinstance(widget.groupBox_3, QGroupBox)
        assert widget.groupBox_3.title() == "Cryo Controls"

        # JT Controls
        assert hasattr(widget, "jt_man_button")
        assert isinstance(widget.jt_man_button, MockPyDMPushButton)
        assert hasattr(widget, "jt_auto_button")
        assert isinstance(widget.jt_auto_button, MockPyDMPushButton)
        assert hasattr(widget, "jt_mode_label")
        assert isinstance(widget.jt_mode_label, MockPyDMLabel)
        assert hasattr(widget, "jt_setpoint_spinbox")
        assert isinstance(widget.jt_setpoint_spinbox, MockPyDMSpinbox)
        assert hasattr(widget, "jt_setpoint_readback")
        assert isinstance(widget.jt_setpoint_readback, MockPyDMLabel)

        # Heater Controls
        assert hasattr(widget, "heater_man_button")
        assert isinstance(widget.heater_man_button, MockPyDMPushButton)
        assert hasattr(widget, "heater_seq_button")
        assert isinstance(widget.heater_seq_button, MockPyDMPushButton)
        assert hasattr(widget, "heater_mode_label")
        assert isinstance(widget.heater_mode_label, MockPyDMLabel)
        assert hasattr(widget, "heater_setpoint_spinbox")
        assert isinstance(widget.heater_setpoint_spinbox, MockPyDMSpinbox)
        assert hasattr(widget, "heater_readback_label")
        assert isinstance(widget.heater_readback_label, MockPyDMLabel)

        # Restore button
        assert hasattr(widget, "restore_cryo_button")
        assert isinstance(widget.restore_cryo_button, QPushButton)

    def test_measurement_settings_group(self, widget):
        """Test measurement settings group and its widgets."""
        assert hasattr(widget, "groupBox")
        assert isinstance(widget.groupBox, QGroupBox)
        assert widget.groupBox.title() == "Measurement Settings"

        assert hasattr(widget, "ll_start_spinbox")
        assert isinstance(widget.ll_start_spinbox, QDoubleSpinBox)

        assert hasattr(widget, "ll_drop_spinbox")
        assert isinstance(widget.ll_drop_spinbox, QDoubleSpinBox)

        assert hasattr(widget, "ll_avg_spinbox")
        assert isinstance(widget.ll_avg_spinbox, QSpinBox)

    def test_calibration_group(self, widget):
        """Test calibration group and its widgets."""
        assert hasattr(widget, "groupBox_2")
        assert isinstance(widget.groupBox_2, QGroupBox)
        assert widget.groupBox_2.title() == "Calibration"

        # Reference parameters sub-group
        assert hasattr(widget, "manual_cryo_groupbox")
        assert isinstance(widget.manual_cryo_groupbox, QGroupBox)
        assert widget.manual_cryo_groupbox.title() == "Reference Parameters"

        assert hasattr(widget, "setup_param_button")
        assert isinstance(widget.setup_param_button, QPushButton)
        assert hasattr(widget, "jt_pos_spinbox")
        assert isinstance(widget.jt_pos_spinbox, QDoubleSpinBox)
        assert hasattr(widget, "ref_heat_spinbox")
        assert isinstance(widget.ref_heat_spinbox, QDoubleSpinBox)

        # Settings spinboxes
        assert hasattr(widget, "start_heat_spinbox")
        assert isinstance(widget.start_heat_spinbox, QDoubleSpinBox)
        assert hasattr(widget, "end_heat_spinbox")
        assert isinstance(widget.end_heat_spinbox, QDoubleSpinBox)
        assert hasattr(widget, "num_cal_points_spinbox")
        assert isinstance(widget.num_cal_points_spinbox, QSpinBox)

        # Calibration buttons
        assert hasattr(widget, "load_cal_button")
        assert isinstance(widget.load_cal_button, QPushButton)
        assert hasattr(widget, "new_cal_button")
        assert isinstance(widget.new_cal_button, QPushButton)
        assert hasattr(widget, "show_cal_data_button")
        assert isinstance(widget.show_cal_data_button, QPushButton)
        assert hasattr(widget, "abort_cal_button")
        assert isinstance(widget.abort_cal_button, QPushButton)

        # Status label
        assert hasattr(widget, "cal_status_label")
        assert isinstance(widget.cal_status_label, QLabel)

    def test_rf_measurement_group(self, widget):
        """Test RF measurement group and its widgets."""
        assert hasattr(widget, "rf_groupbox")
        assert isinstance(widget.rf_groupbox, QGroupBox)
        assert widget.rf_groupbox.title() == "RF Measurement"

        # Should be disabled by default
        assert not widget.rf_groupbox.isEnabled()

        assert hasattr(widget, "cavity_layout")
        assert hasattr(widget, "rf_cal_spinbox")
        assert isinstance(widget.rf_cal_spinbox, QDoubleSpinBox)
        assert hasattr(widget, "load_rf_button")
        assert isinstance(widget.load_rf_button, QPushButton)
        assert hasattr(widget, "new_rf_button")
        assert isinstance(widget.new_rf_button, QPushButton)
        assert hasattr(widget, "show_rf_button")
        assert isinstance(widget.show_rf_button, QPushButton)
        assert hasattr(widget, "abort_rf_button")
        assert isinstance(widget.abort_rf_button, QPushButton)
        assert hasattr(widget, "rf_status_label")
        assert isinstance(widget.rf_status_label, QLabel)


class TestQ0MeasurementWidgetDefaults:
    """Test default values and properties of widgets."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_measurement_settings_defaults(self, widget):
        """Test default values for measurement settings."""
        assert widget.ll_start_spinbox.value() == 93.0
        assert widget.ll_start_spinbox.minimum() == 90.0
        assert widget.ll_start_spinbox.maximum() == 93.0

        assert widget.ll_drop_spinbox.value() == 3.0
        assert widget.ll_drop_spinbox.minimum() == 1.0
        assert widget.ll_drop_spinbox.maximum() == 3.0

        assert widget.ll_avg_spinbox.value() == 10

    def test_jt_setpoint_defaults(self, widget):
        """Test JT setpoint spinbox defaults."""
        assert widget.jt_setpoint_spinbox.minimum() == 5.0
        assert widget.jt_setpoint_spinbox.maximum() == 70.0

    def test_heater_setpoint_defaults(self, widget):
        """Test heater setpoint spinbox defaults."""
        assert widget.heater_setpoint_spinbox.maximum() == 160.0
        assert widget.heater_setpoint_spinbox.singleStep() == 10.0

    def test_calibration_spinbox_defaults(self, widget):
        """Test calibration spinbox defaults."""
        assert widget.jt_pos_spinbox.value() == 40.0
        assert widget.ref_heat_spinbox.value() == 48.0

        assert widget.start_heat_spinbox.minimum() == 75.0
        assert widget.start_heat_spinbox.maximum() == 130.0
        assert widget.start_heat_spinbox.value() == 130.0

        assert widget.end_heat_spinbox.minimum() == 130.0
        assert widget.end_heat_spinbox.maximum() == 160.0
        assert widget.end_heat_spinbox.value() == 160.0

        assert widget.num_cal_points_spinbox.maximum() == 20
        assert widget.num_cal_points_spinbox.value() == 5

    def test_rf_measurement_defaults(self, widget):
        """Test RF measurement defaults."""
        assert not widget.rf_groupbox.isEnabled()
        assert not widget.show_cal_data_button.isEnabled()
        assert not widget.rf_cal_spinbox.isEnabled()

        assert widget.rf_cal_spinbox.minimum() == 24.0
        assert widget.rf_cal_spinbox.maximum() == 112.0
        assert widget.rf_cal_spinbox.value() == 80.0


class TestQ0MeasurementWidgetStyling:
    """Test widget styling and appearance."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0Measurement Widget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_group_box_fonts(self, widget):
        """Test that group boxes have bold fonts."""
        group_boxes = [widget.groupBox_3, widget.groupBox, widget.groupBox_2, widget.rf_groupbox]

        for groupbox in group_boxes:
            font = groupbox.font()
            assert font.bold()

    def test_cryomodule_combobox_font(self, widget):
        """Test cryomodule combobox has bold font."""
        font = widget.cm_combobox.font()
        assert font.bold()

    def test_abort_button_styling(self, widget):
        """Test abort buttons have red styling."""
        abort_buttons = [widget.abort_cal_button, widget.abort_rf_button]

        for button in abort_buttons:
            style = button.styleSheet()
            assert "rgb(252, 33, 37)" in style

    def test_pydm_button_text(self, widget):
        """Test PyDM button text is set correctly."""
        assert widget.jt_man_button.text() == "Manual"
        assert widget.jt_auto_button.text() == "Auto"
        assert widget.heater_man_button.text() == "Manual"
        assert widget.heater_seq_button.text() == "Sequencer"


class TestQ0MeasurementWidgetTooltips:
    """Test tooltips and help text."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_setup_param_button_tooltip(self, widget):
        """Test setup parameter button has tooltip."""
        tooltip = widget.setup_param_button.toolTip()
        assert "Sets the heater to manual at 48" in tooltip
        assert "JT can settle" in tooltip


class TestQ0MeasurementWidgetLayout:
    """Test widget layout and structure."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_main_layout_exists(self, widget):
        """Test main layout is properly set."""
        layout = widget.layout()
        assert layout is not None
        assert layout.spacing() == 10

    def test_widgets_are_added_to_layout(self, widget):
        """Test that major widgets are properly added to layout."""
        layout = widget.layout()

        # Check that layout has the expected number of items
        # The exact count depends on implementation, but should be > 0
        assert layout.count() > 0

    def test_subgroup_layouts(self, widget):
        """Test that sub-groups have proper layouts."""
        # Cryo controls should have sub-groups
        cryo_layout = widget.groupBox_3.layout()
        assert cryo_layout is not None

        # Calibration should have sub-groups
        cal_layout = widget.groupBox_2.layout()
        assert cal_layout is not None

        # RF measurement should have cavity layout
        rf_layout = widget.rf_groupbox.layout()
        assert rf_layout is not None


class TestQ0MeasurementWidgetFunctionality:
    """Test functional aspects of the widget."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_spinbox_value_changes(self, widget):
        """Test that spinbox values can be changed."""
        # Test a few key spinboxes
        widget.ll_start_spinbox.setValue(92.0)
        assert widget.ll_start_spinbox.value() == 92.0

        widget.ref_heat_spinbox.setValue(50.0)
        assert widget.ref_heat_spinbox.value() == 50.0

        widget.num_cal_points_spinbox.setValue(8)
        assert widget.num_cal_points_spinbox.value() == 8

    def test_pydm_spinbox_functionality(self, widget):
        """Test PyDM spinbox functionality."""
        # Test PyDM spinboxes
        widget.jt_setpoint_spinbox.setValue(25.0)
        assert widget.jt_setpoint_spinbox.value() == 25.0

        widget.heater_setpoint_spinbox.setValue(75.0)
        assert widget.heater_setpoint_spinbox.value() == 75.0

    def test_enable_disable_functionality(self, widget):
        """Test enabling/disabling of widgets."""
        # RF group should start disabled
        assert not widget.rf_groupbox.isEnabled()

        # Should be able to enable it
        widget.rf_groupbox.setEnabled(True)
        assert widget.rf_groupbox.isEnabled()

        # Test other widgets
        widget.show_cal_data_button.setEnabled(True)
        assert widget.show_cal_data_button.isEnabled()


class TestQ0MeasurementWidgetEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_spinbox_boundaries(self, widget):
        """Test spinbox boundary values."""
        # Test minimum values
        widget.ll_start_spinbox.setValue(89.0)  # Below minimum
        assert widget.ll_start_spinbox.value() == 90.0  # Should clamp to minimum

        widget.ll_start_spinbox.setValue(94.0)  # Above maximum
        assert widget.ll_start_spinbox.value() == 93.0  # Should clamp to maximum

    def test_invalid_parent(self, mock_pydm):
        """Test widget creation with invalid parent."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        # Should not raise exception
        widget = Q0MeasurementWidget(parent=None)
        assert isinstance(widget, QWidget)

    def test_widget_deletion(self, widget):
        """Test widget can be properly deleted."""
        # Store reference to test deletion
        widget_ref = widget

        # This shouldn't raise an exception
        try:
            widget_ref.deleteLater()
        except Exception as e:
            pytest.fail(f"Widget deletion raised exception: {e}")


class TestQ0MeasurementWidgetIntegration:
    """Test integration aspects of the widget."""

    @pytest.fixture
    def widget(self, qapp, mock_pydm):
        """Create Q0MeasurementWidget instance for testing."""
        from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget

        return Q0MeasurementWidget()

    def test_all_expected_attributes_exist(self, widget):
        """Test that all expected attributes exist for GUI integration."""
        expected_attributes = [
            "cm_combobox",
            "ll_avg_spinbox",
            "new_cal_button",
            "load_cal_button",
            "show_cal_data_button",
            "new_rf_button",
            "load_rf_button",
            "show_rf_button",
            "setup_param_button",
            "abort_rf_button",
            "abort_cal_button",
            "restore_cryo_button",
            "ref_heat_spinbox",
            "jt_pos_spinbox",
            "ll_start_spinbox",
            "start_heat_spinbox",
            "end_heat_spinbox",
            "num_cal_points_spinbox",
            "ll_drop_spinbox",
            "rf_cal_spinbox",
            "perm_byte",
            "perm_label",
            "jt_man_button",
            "jt_auto_button",
            "jt_mode_label",
            "jt_setpoint_spinbox",
            "jt_setpoint_readback",
            "heater_man_button",
            "heater_seq_button",
            "heater_mode_label",
            "heater_setpoint_spinbox",
            "heater_readback_label",
            "cal_status_label",
            "rf_status_label",
            "rf_groupbox",
            "cavity_layout",
        ]

        for attr in expected_attributes:
            assert hasattr(widget, attr), f"Missing expected attribute: {attr}"

    def test_widget_can_be_shown(self, widget):
        """Test that widget can be shown without errors."""
        try:
            widget.show()
            # Note: In a headless environment, this might not actually display
        except Exception as e:
            pytest.fail(f"Showing widget raised exception: {e}")

    def test_widget_size_hints(self, widget):
        """Test that widget provides reasonable size hints."""
        size_hint = widget.sizeHint()
        assert size_hint.width() > 0
        assert size_hint.height() > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
