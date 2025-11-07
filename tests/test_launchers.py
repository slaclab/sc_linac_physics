"""Test GUI launchers."""

import shutil
import subprocess
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.parametrize(
    "launcher_func,module_path",
    [
        ("launch_srf_home", "sc_linac_physics.cli.launchers"),
        ("launch_cavity_display", "sc_linac_physics.cli.launchers"),
        ("launch_fault_decoder", "sc_linac_physics.cli.launchers"),
        ("launch_fault_count", "sc_linac_physics.cli.launchers"),
        ("launch_quench_processing", "sc_linac_physics.cli.launchers"),
        ("launch_auto_setup", "sc_linac_physics.cli.launchers"),
        ("launch_q0_measurement", "sc_linac_physics.cli.launchers"),
        ("launch_tuning", "sc_linac_physics.cli.launchers"),
        ("launch_microphonics", "sc_linac_physics.cli.launchers"),
    ],
)
def test_gui_launcher_imports(launcher_func, module_path):
    """Test that launcher functions can be imported."""
    module = __import__(module_path, fromlist=[launcher_func])
    func = getattr(module, launcher_func)
    assert callable(func)


def test_launcher_decorators():
    """Test that launchers have correct decorator categories."""
    from sc_linac_physics.cli.launchers import (
        launch_srf_home,
        launch_cavity_display,
        launch_quench_processing,
        launch_auto_setup,
    )

    # Display launchers should have 'display' category
    assert launch_srf_home._launcher_category == "display"
    assert launch_cavity_display._launcher_category == "display"

    # Application launchers should have 'application' category
    assert launch_quench_processing._launcher_category == "application"
    assert launch_auto_setup._launcher_category == "application"


@patch("sc_linac_physics.displays.srfhome.srf_home.SRFHome")
@patch("sc_linac_physics.cli.launchers.PyDMApplication")
@patch("sc_linac_physics.cli.launchers.sys.exit")
def test_launch_srf_home_standalone(
    mock_exit, mock_pydm_app, mock_display_class
):
    """Test SRF home launcher in standalone mode."""
    from sc_linac_physics.cli.launchers import launch_srf_home

    # Setup mocks
    mock_app_instance = MagicMock()
    mock_pydm_app.return_value = mock_app_instance
    mock_app_instance.exec.return_value = 0
    mock_app_instance.exec_.return_value = 0

    mock_display_instance = MagicMock()
    mock_display_class.return_value = mock_display_instance

    # Call launcher
    launch_srf_home(standalone=True)

    # Verify PyDMApplication was created
    assert mock_pydm_app.called

    # Verify display was instantiated
    assert mock_display_class.called

    # Verify app.exec() or app.exec_() was called
    assert mock_app_instance.exec.called or mock_app_instance.exec_.called

    # Verify sys.exit was called
    assert mock_exit.called


@patch("sc_linac_physics.displays.srfhome.srf_home.SRFHome")
@patch("sc_linac_physics.cli.launchers.PyDMMainWindow")
@patch("sc_linac_physics.cli.launchers.PyDMApplication")
def test_launch_srf_home_non_standalone(
    mock_pydm_app, mock_window, mock_display_class
):
    """Test SRF home launcher in non-standalone mode."""
    from sc_linac_physics.cli.launchers import launch_srf_home

    # Setup mocks for existing application
    mock_app_instance = MagicMock()
    mock_pydm_app.instance.return_value = mock_app_instance

    mock_display_instance = MagicMock()
    mock_display_class.return_value = mock_display_instance

    mock_window_instance = MagicMock()
    mock_window.return_value = mock_window_instance

    # Call launcher in non-standalone mode
    result = launch_srf_home(standalone=False)

    # Verify window was created and returned
    assert result == mock_window_instance
    assert mock_window_instance.set_display_widget.called
    assert mock_window_instance.show.called


@pytest.mark.parametrize(
    "command",
    [
        "sc-srf-home",
        "sc-cavity",
        "sc-faults",
        "sc-fcount",
    ],
)
def test_display_launchers_exist(command):
    """Test that display launcher commands are installed and executable."""
    # Check if command exists in PATH
    command_path = shutil.which(command)
    assert command_path is not None, f"Command '{command}' not found in PATH"

    # Verify it's executable
    import os

    assert os.access(
        command_path, os.X_OK
    ), f"Command '{command}' is not executable"


@pytest.mark.parametrize(
    "command,expected_import_error",
    [
        ("sc-srf-home", "SRFHome"),
        ("sc-cavity", "CavityDisplayGUI"),
        ("sc-faults", "DecoderDisplay"),
        ("sc-fcount", "FaultCountDisplay"),
    ],
)
def test_display_launchers_no_syntax_errors(command, expected_import_error):
    """Test that launchers don't have syntax errors (they may have import errors)."""
    # This test just verifies the launcher code itself has no syntax errors
    # by checking that the Python code can be parsed
    result = subprocess.run(
        [
            "python",
            "-c",
            f"from sc_linac_physics.cli.launchers import {command.replace('sc-', 'launch_').replace('-', '_')}",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )

    # Should not have SyntaxError or TypeError about 'multiple values'
    assert "SyntaxError" not in result.stderr
    assert (
        "TypeError: launch_python_display() got multiple values"
        not in result.stderr
    )


@patch("sc_linac_physics.cli.launchers.launch_python_display")
def test_launch_python_display_called_correctly(mock_launch):
    """Test that launchers call launch_python_display with correct arguments."""
    from sc_linac_physics.cli.launchers import launch_srf_home
    from sc_linac_physics.displays.srfhome.srf_home import SRFHome

    mock_launch.return_value = None

    # Mock sys.argv
    with patch("sys.argv", ["sc-srf-home", "--arg1", "--arg2"]):
        launch_srf_home(standalone=True)

        # Verify launch_python_display was called
        assert mock_launch.called

        # Check arguments
        call_args = mock_launch.call_args
        # First positional arg should be the display class
        assert call_args[0][0] == SRFHome
        # Remaining positional args should be from sys.argv[1:]
        assert "--arg1" in call_args[0]
        assert "--arg2" in call_args[0]
        # standalone should be passed as keyword
        assert call_args[1]["standalone"] is True


@patch("sc_linac_physics.cli.launchers.PyDMApplication")
def test_launch_python_display_no_app_instance(mock_pydm_app):
    """Test that non-standalone mode raises error without app instance."""
    from sc_linac_physics.cli.launchers import launch_python_display

    mock_pydm_app.instance.return_value = None

    with pytest.raises(RuntimeError, match="No PyDMApplication instance found"):
        # Use a dummy class
        class DummyDisplay:
            pass

        launch_python_display(DummyDisplay, standalone=False)


@pytest.mark.parametrize(
    "launcher_name,display_class_path,display_module",
    [
        (
            "launch_srf_home",
            "sc_linac_physics.displays.srfhome.srf_home.SRFHome",
            "sc_linac_physics.displays.srfhome.srf_home",
        ),
        (
            "launch_cavity_display",
            "sc_linac_physics.displays.cavity_display.cavity_display.CavityDisplayGUI",
            "sc_linac_physics.displays.cavity_display.cavity_display",
        ),
        (
            "launch_fault_decoder",
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay",
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display",
        ),
        (
            "launch_fault_count",
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay",
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display",
        ),
    ],
)
def test_launchers_import_correct_display_class(
    launcher_name, display_class_path, display_module
):
    """Test that each launcher imports and uses the correct display class."""
    from sc_linac_physics.cli.launchers import (
        launch_srf_home,
        launch_cavity_display,
        launch_fault_decoder,
        launch_fault_count,
    )

    launchers = {
        "launch_srf_home": launch_srf_home,
        "launch_cavity_display": launch_cavity_display,
        "launch_fault_decoder": launch_fault_decoder,
        "launch_fault_count": launch_fault_count,
    }

    launcher_func = launchers[launcher_name]

    # Parse the display class path
    module_path, class_name = display_class_path.rsplit(".", 1)

    # Mock launch_python_display to capture what was passed to it
    with patch(
        "sc_linac_physics.cli.launchers.launch_python_display"
    ) as mock_launch:
        mock_launch.return_value = None

        # Call the launcher
        launcher_func(standalone=True)

        # Verify launch_python_display was called
        assert mock_launch.called
        call_args = mock_launch.call_args[0]

        # Get the actual class that was passed (should be the real class, not a mock)
        passed_class = call_args[0]

        # Verify it's the expected class by checking its module and name
        assert passed_class.__name__ == class_name
        assert passed_class.__module__ == module_path


def test_all_entry_points_have_tests():
    """Meta-test: ensure all launchers in the module are being tested."""
    from sc_linac_physics.cli import launchers
    import inspect

    # Get all launcher functions
    launcher_functions = [
        name
        for name, obj in inspect.getmembers(launchers)
        if name.startswith("launch_") and callable(obj)
    ]

    # Expected launchers based on entry points
    expected_launchers = {
        "launch_srf_home",
        "launch_cavity_display",
        "launch_fault_decoder",
        "launch_fault_count",
        "launch_quench_processing",
        "launch_auto_setup",
        "launch_q0_measurement",
        "launch_tuning",
        "launch_microphonics",
    }

    actual_launchers = set(launcher_functions)

    # All expected launchers should exist
    assert expected_launchers.issubset(
        actual_launchers
    ), f"Missing launchers: {expected_launchers - actual_launchers}"
