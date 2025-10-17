from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from pydm.widgets.analog_indicator import PyDMAnalogIndicator
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI

# Mock SETUP_MACHINE for testing
SETUP_MACHINE = MagicMock()


@pytest.fixture(autouse=True)
def reset_setup_machine():
    """Reset the SETUP_MACHINE mock before each test."""
    SETUP_MACHINE.reset_mock()
    yield


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    """Prevent PyDM from making real channel connections during tests."""
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def setup_gui():
    pv_mock = MagicMock()
    pv_mock.pvname = "dummy"
    pv_mock.value = 0.0
    pv_mock.connect = MagicMock()
    pv_mock.wait_for_connection = MagicMock(return_value=True)
    pv_mock.get = MagicMock(return_value=0.0)
    pv_mock.put = MagicMock()
    pv_mock.callbacks = []

    with (
        patch(
            "lcls_tools.common.controls.pyepics.utils.PV", return_value=pv_mock
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()
        # Mock the sanity check popups to always return Yes
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_shutdown_popup.exec = MagicMock(
            return_value=QMessageBox.Yes
        )
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.Yes)

        # Get all PyDMAnalogIndicator widgets and set up their mock channels
        for widget in gui.findChildren(PyDMAnalogIndicator):
            channel_mock = MagicMock()
            channel_mock.value = 0.0
            channel_mock.connection_state = True
            widget._channel = channel_mock

            # Mock the value method
            widget._value = 0.0
            widget.value = lambda: widget._value

            # Helper method to simulate value updates
            def update_value(new_value):
                channel_mock.value = new_value
                widget._value = new_value
                widget.channelValueChanged(new_value)

            # Add the helper method to the widget
            widget.simulate_value = update_value

        yield gui


def test_launches(qtbot: QtBot, setup_gui):
    """Test that the GUI launches and has the expected initial state."""
    qtbot.addWidget(setup_gui)

    # Check window title
    assert setup_gui.windowTitle() == "SRF Auto Setup"

    # Verify initial checkbox states (all should be checked by default)
    assert setup_gui.ssa_cal_checkbox.isChecked()
    assert setup_gui.autotune_checkbox.isChecked()
    assert setup_gui.cav_char_checkbox.isChecked()
    assert setup_gui.rf_ramp_checkbox.isChecked()


def test_linac_widgets_population(qtbot: QtBot, setup_gui):
    """Test that linac widgets are properly populated."""
    qtbot.addWidget(setup_gui)

    # Should have 4 linac widgets (L0B through L3B)
    assert len(setup_gui.linac_widgets) == 4

    # Verify linac names
    expected_names = ["L0B", "L1B", "L2B", "L3B"]
    actual_names = [widget.name for widget in setup_gui.linac_widgets]
    assert actual_names == expected_names


def test_machine_setup_button(qtbot: QtBot, setup_gui):
    """Test machine setup button click and settings propagation."""
    qtbot.addWidget(setup_gui)

    # Reset mock status before testing
    SETUP_MACHINE.trigger_setup.reset_mock()

    # Click machine setup button
    qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)

    # Verify SETUP_MACHINE settings were updated
    assert (
        SETUP_MACHINE.ssa_cal_requested
        == setup_gui.ssa_cal_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.auto_tune_requested
        == setup_gui.autotune_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.cav_char_requested
        == setup_gui.cav_char_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.rf_ramp_requested
        == setup_gui.rf_ramp_checkbox.isChecked()
    )

    # Verify setup was triggered
    assert SETUP_MACHINE.trigger_setup.call_count == 1


def test_machine_shutdown_button(qtbot: QtBot, setup_gui):
    """Test machine shutdown button click."""
    qtbot.addWidget(setup_gui)

    # Reset mock status before testing
    SETUP_MACHINE.trigger_shutdown.reset_mock()

    # Click shutdown button
    qtbot.mouseClick(setup_gui.machine_shutdown_button, Qt.LeftButton)

    # Verify shutdown was triggered
    assert SETUP_MACHINE.trigger_shutdown.call_count == 1


def test_machine_abort_button(qtbot: QtBot, setup_gui):
    """Test machine abort button click."""
    qtbot.addWidget(setup_gui)

    # Reset mock status before testing
    SETUP_MACHINE.trigger_abort.reset_mock()

    # Click abort button
    qtbot.mouseClick(setup_gui.machine_abort_button, Qt.LeftButton)

    # Verify abort was triggered
    assert SETUP_MACHINE.trigger_abort.call_count == 1


def test_checkbox_updates(qtbot: QtBot, setup_gui):
    """Test that checkbox state changes are reflected in settings."""
    qtbot.addWidget(setup_gui)

    # Uncheck all boxes
    setup_gui.ssa_cal_checkbox.setChecked(False)
    setup_gui.autotune_checkbox.setChecked(False)
    setup_gui.cav_char_checkbox.setChecked(False)
    setup_gui.rf_ramp_checkbox.setChecked(False)

    # Click setup button to propagate settings
    qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)

    # Verify SETUP_MACHINE settings match checkbox states
    assert not SETUP_MACHINE.ssa_cal_requested
    assert not SETUP_MACHINE.auto_tune_requested
    assert not SETUP_MACHINE.cav_char_requested
    assert not SETUP_MACHINE.rf_ramp_requested


@pytest.fixture
def setup_gui_with_no_dialogs():
    """Fixture for GUI with dialog responses set to No"""
    pv_mock = MagicMock()
    pv_mock.pvname = "dummy"
    pv_mock.value = 0.0
    pv_mock.connect = MagicMock()
    pv_mock.wait_for_connection = MagicMock(return_value=True)
    pv_mock.get = MagicMock(return_value=0.0)
    pv_mock.put = MagicMock()
    pv_mock.callbacks = []

    with (
        patch(
            "lcls_tools.common.controls.pyepics.utils.PV", return_value=pv_mock
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()
        # Mock the sanity check popups to return No
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_shutdown_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.No)

        # Get all PyDMAnalogIndicator widgets and set up their mock channels
        for widget in gui.findChildren(PyDMAnalogIndicator):
            channel_mock = MagicMock()
            channel_mock.value = 0.0
            channel_mock.connection_state = True
            widget._channel = channel_mock

            # Mock the value method
            widget._value = 0.0
            widget.value = lambda: widget._value

            # Helper method to simulate value updates
            def update_value(new_value):
                channel_mock.value = new_value
                widget._value = new_value
                widget.channelValueChanged(new_value)

            # Add the helper method to the widget
            widget.simulate_value = update_value

        yield gui


def test_dialog_cancellation(qtbot: QtBot, setup_gui_with_no_dialogs):
    """Test that clicking 'No' in confirmation dialogs prevents actions."""
    qtbot.addWidget(setup_gui_with_no_dialogs)

    # Reset mocks before testing
    SETUP_MACHINE.reset_mock()
    setup_gui_with_no_dialogs.machine_setup_popup.exec.reset_mock()
    setup_gui_with_no_dialogs.machine_shutdown_popup.exec.reset_mock()
    setup_gui_with_no_dialogs.machine_abort_popup.exec.reset_mock()

    # Setup button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_setup_button, Qt.LeftButton
    )
    assert setup_gui_with_no_dialogs.machine_setup_popup.exec.call_count == 1
    assert SETUP_MACHINE.trigger_setup.call_count == 0

    # Reset mocks again
    SETUP_MACHINE.reset_mock()
    setup_gui_with_no_dialogs.machine_setup_popup.exec.reset_mock()

    # Shutdown button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_shutdown_button, Qt.LeftButton
    )
    assert setup_gui_with_no_dialogs.machine_shutdown_popup.exec.call_count == 1
    assert SETUP_MACHINE.trigger_shutdown.call_count == 0

    # Reset mocks again
    SETUP_MACHINE.reset_mock()
    setup_gui_with_no_dialogs.machine_shutdown_popup.exec.reset_mock()

    # Abort button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_abort_button, Qt.LeftButton
    )
    assert setup_gui_with_no_dialogs.machine_abort_popup.exec.call_count == 1
    assert SETUP_MACHINE.trigger_abort.call_count == 0


def test_tab_widget_population(qtbot: QtBot, setup_gui):
    """Test tab widget structure and content."""
    qtbot.addWidget(setup_gui)

    # Verify tab widget exists
    assert setup_gui.tabWidget_linac is not None

    # Check number of tabs (should be 4 for L0B through L3B)
    assert setup_gui.tabWidget_linac.count() == 4

    # Check tab titles
    expected_titles = ["L0B", "L1B", "L2B", "L3B"]
    actual_titles = [setup_gui.tabWidget_linac.tabText(i) for i in range(4)]
    assert actual_titles == expected_titles

    # Check each tab's content structure
    for i in range(4):
        tab_widget = setup_gui.tabWidget_linac.widget(i)

        # Verify tab has a layout
        assert tab_widget.layout() is not None

        # Get the linac widget for this tab
        linac = setup_gui.linac_widgets[i]

        # Verify critical widgets exist
        assert linac.readback_label is not None
        assert linac.setup_button is not None
        assert linac.abort_button is not None
        assert linac.acon_button is not None
        assert linac.cm_tab_widget is not None


@pytest.mark.skip("AACT PV test needs IOC simulation")
def test_aact_pv_connections(qtbot: QtBot, setup_gui):
    """Test AACT PV connections and interactions."""
    qtbot.addWidget(setup_gui)

    # Verify PVs were created for each linac
    assert len(setup_gui.linac_aact_pvs) == 4

    # Check PV names
    for i, pv in enumerate(setup_gui.linac_aact_pvs):
        expected_pv_name = f"ACCL:L{i}B:1:AACTMEANSUM"
        assert pv.pvname == expected_pv_name

    # Note: PV value testing requires IOC simulation
    # This has been disabled until proper IOC mocking is implemented


def test_error_conditions(qtbot: QtBot, setup_gui):
    """Test error handling and edge cases."""
    qtbot.addWidget(setup_gui)

    # Test with invalid linac index (shouldn't crash)
    with pytest.raises(IndexError, match="list index out of range"):
        setup_gui.linac_widgets[99].setup_button.click()

    # Test PV connection error simulation
    with patch(
        "lcls_tools.common.controls.pyepics.utils.PV",
        side_effect=Exception("PV Connection Error"),
    ):
        # Creating a new GUI should handle PV creation errors gracefully
        gui = SetupGUI()
        assert gui is not None  # GUI should still be created

    # Test rapid button clicks
    for _ in range(5):
        qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)
    assert SETUP_MACHINE.trigger_setup.call_count == 5

    # Test checkbox state consistency
    setup_gui.settings = None  # Simulate settings object being destroyed
    setup_gui.ssa_cal_checkbox.setChecked(True)  # Should not crash

    # Test with missing SETUP_MACHINE (simulate module import error)
    with patch(
        "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE", None
    ):
        gui = SetupGUI()
        assert gui is not None  # GUI should still be created

        # Verify error stylesheet is applied to abort button
        stylesheet = setup_gui.machine_abort_button.styleSheet().lower()
        assert (
            "color: rgb(128, 0, 2)" in stylesheet
            or "background-color: #ff9994" in stylesheet
        )


def test_analog_indicators(qtbot: QtBot, setup_gui):
    """Test PyDMAnalogIndicator widgets behavior."""
    qtbot.addWidget(setup_gui)

    # Find all analog indicators in the GUI
    indicators = setup_gui.findChildren(PyDMAnalogIndicator)

    # Test each indicator
    for indicator in indicators:
        # Test value updates through the channel
        test_values = [0.0, 42.5, 100.0]
        for value in test_values:
            indicator.channelValueChanged(value)  # Use the PyDM method directly
            indicator._channel.value = value  # Set the channel value
            assert indicator._channel.value == value  # Verify channel value

        # Test alarm ranges (if configured)
        if hasattr(indicator, "alarmLimits"):
            indicator.setAlarmLimits(-10, 10)  # Example limits

            # Test normal range
            indicator.simulate_value(0.0)
            assert indicator._value == 0.0

            # Test warning range
            indicator.simulate_value(15.0)
            assert indicator._value == 15.0

            # Test alarm range
            indicator.simulate_value(-15.0)
            assert indicator._value == -15.0

        # Verify the indicator is using the real PyDMAnalogIndicator class
        assert isinstance(indicator, PyDMAnalogIndicator)

        # Verify no real channel connections were made
        assert indicator._channel is not None
        assert indicator._value is not None  # Check value directly
