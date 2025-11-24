from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from pydm.widgets.analog_indicator import PyDMAnalogIndicator
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI
from sc_linac_physics.utils.epics import make_mock_pv

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
    mock_pv = make_mock_pv(pv_name="TEST:PV", get_val=0.0, connected=True)

    with (
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.PV",
            return_value=mock_pv,
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()

        # Mock all popups to return Yes by default
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_shutdown_popup.exec = MagicMock(
            return_value=QMessageBox.Yes
        )
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.Yes)

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
    assert SETUP_MACHINE.trigger_start.call_count == 1


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
    mock_pv = make_mock_pv(pv_name="TEST:PV", get_val=0.0, connected=True)

    with (
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.PV",
            return_value=mock_pv,
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()

        # Mock all popups to return No
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_shutdown_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.No)

        yield gui


def test_dialog_cancellation(qtbot: QtBot, setup_gui_with_no_dialogs):
    """Test that clicking 'No' in confirmation dialogs prevents actions."""
    qtbot.addWidget(setup_gui_with_no_dialogs)

    # Reset mocks before testing
    SETUP_MACHINE.reset_mock()
    # Don't need to reset exec since it's recreated in the fixture

    # Test setup button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_setup_button, Qt.LeftButton
    )
    assert SETUP_MACHINE.trigger_start.call_count == 0

    # Test shutdown button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_shutdown_button, Qt.LeftButton
    )
    assert SETUP_MACHINE.trigger_shutdown.call_count == 0

    # Test abort button with No response
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_abort_button, Qt.LeftButton
    )
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
        "sc_linac_physics.utils.epics.PV",
        side_effect=Exception("PV Connection Error"),
    ):
        # Creating a new GUI should handle PV creation errors gracefully
        gui = SetupGUI()
        assert gui is not None  # GUI should still be created

    # Test rapid button clicks
    for _ in range(5):
        qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)
    assert SETUP_MACHINE.trigger_start.call_count == 5

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
    """Test PyDMAnalogIndicator widgets exist and are properly configured."""
    qtbot.addWidget(setup_gui)

    # Find all analog indicators in the GUI
    indicators = setup_gui.findChildren(PyDMAnalogIndicator)

    # Verify we have the expected number of indicators
    assert len(indicators) > 0, "No analog indicators found"

    # Test each indicator has required properties
    for indicator in indicators:
        # Check that channel is set (it's a string PV name)
        assert isinstance(indicator.channel, str), "Channel should be a string"
        assert len(indicator.channel) > 0, "Channel should not be empty"

        # Test basic value update (without channel)
        test_value = 42.5
        indicator.channelValueChanged(test_value)
        assert (
            indicator.value == test_value
        ), f"Indicator value should be {test_value}"
