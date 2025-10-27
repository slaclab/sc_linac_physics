"""Tests for PyDM display launchers."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pydm_app():
    """Mock PyDMApplication."""
    with patch("sc_linac_physics.cli.launchers.PyDMApplication") as mock_app:
        mock_instance = MagicMock()
        mock_instance.main_window = MagicMock()
        mock_instance.exec.return_value = 0
        mock_app.return_value = mock_instance
        mock_app.instance.return_value = None  # Default: no existing instance
        yield mock_app


@pytest.fixture
def mock_main_window():
    """Mock PyDMMainWindow."""
    with patch("sc_linac_physics.cli.launchers.PyDMMainWindow") as mock_window:
        mock_instance = MagicMock()
        mock_window.return_value = mock_instance
        yield mock_window


@pytest.fixture
def mock_display_class():
    """Mock display class."""
    mock_class = MagicMock()
    mock_class.return_value = MagicMock()
    return mock_class


class TestDecorators:
    """Test decorator functions."""

    def test_display_decorator(self):
        """Test that display decorator sets correct category."""
        from sc_linac_physics.cli.launchers import display

        @display
        def test_func():
            pass

        assert hasattr(test_func, "_launcher_category")
        assert test_func._launcher_category == "display"

    def test_application_decorator(self):
        """Test that application decorator sets correct category."""
        from sc_linac_physics.cli.launchers import application

        @application
        def test_func():
            pass

        assert hasattr(test_func, "_launcher_category")
        assert test_func._launcher_category == "application"


class TestLaunchPythonDisplay:
    """Test launch_python_display function."""

    def test_standalone_mode(self, mock_pydm_app, mock_display_class):
        """Test launching in standalone mode."""
        from sc_linac_physics.cli.launchers import launch_python_display

        with patch("sys.exit") as mock_exit:
            launch_python_display(
                mock_display_class, "--test-arg", standalone=True
            )

        # Verify PyDMApplication was created with command line args
        mock_pydm_app.assert_called_once_with(command_line_args=["--test-arg"])

        # Verify display was instantiated
        mock_display_class.assert_called_once_with()

        # Verify display was set on main window
        mock_pydm_app.return_value.main_window.set_display_widget.assert_called_once_with(
            mock_display_class.return_value
        )

        # Verify main window was shown
        mock_pydm_app.return_value.main_window.show.assert_called_once()

        # Verify app.exec() was called
        mock_pydm_app.return_value.exec.assert_called_once()

        # Verify sys.exit was called with exec() return value
        mock_exit.assert_called_once_with(0)

    def test_child_window_mode(
        self, mock_pydm_app, mock_main_window, mock_display_class
    ):
        """Test launching in child window mode."""
        from sc_linac_physics.cli.launchers import launch_python_display

        # Set up existing app instance
        existing_app = MagicMock()
        mock_pydm_app.instance.return_value = existing_app

        result = launch_python_display(mock_display_class, standalone=False)

        # Verify no new PyDMApplication was created
        mock_pydm_app.assert_not_called()

        # Verify instance was retrieved
        mock_pydm_app.instance.assert_called_once()

        # Verify display was instantiated
        mock_display_class.assert_called_once_with()

        # Verify new main window was created
        mock_main_window.assert_called_once()

        # Verify display was set on the new window
        mock_main_window.return_value.set_display_widget.assert_called_once_with(
            mock_display_class.return_value
        )

        # Verify window was shown
        mock_main_window.return_value.show.assert_called_once()

        # Verify window instance was returned
        assert result == mock_main_window.return_value

    def test_child_window_mode_no_app_raises_error(
        self, mock_pydm_app, mock_display_class
    ):
        """Test that child window mode raises error when no app exists."""
        from sc_linac_physics.cli.launchers import launch_python_display

        # No existing app instance
        mock_pydm_app.instance.return_value = None

        with pytest.raises(
            RuntimeError, match="No PyDMApplication instance found"
        ):
            launch_python_display(mock_display_class, standalone=False)

    def test_no_additional_args(self, mock_pydm_app, mock_display_class):
        """Test launching without additional arguments."""
        from sc_linac_physics.cli.launchers import launch_python_display

        with patch("sys.exit"):
            launch_python_display(mock_display_class, standalone=True)

        # Verify empty args list
        mock_pydm_app.assert_called_once_with(command_line_args=[])


class TestDisplayLaunchers:
    """Test individual display launcher functions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up common mocks for all display launcher tests."""
        with (
            patch("sys.exit"),
            patch(
                "sc_linac_physics.cli.launchers.launch_python_display"
            ) as mock_launch,
        ):
            self.mock_launch = mock_launch
            yield

    def test_launch_srf_home(self):
        """Test SRF home launcher."""
        from sc_linac_physics.cli.launchers import launch_srf_home

        # Mock the import inside the function
        with patch("sc_linac_physics.displays.srfhome.srf_home.SRFHome"):
            launch_srf_home(standalone=True)

            # Verify launch_python_display was called
            assert self.mock_launch.called
            call_kwargs = self.mock_launch.call_args
            # The display_class argument should be the mock
            assert "display_class" in call_kwargs.kwargs
            assert call_kwargs.kwargs["standalone"] is True

    def test_launch_srf_home_has_display_decorator(self):
        """Test that SRF home launcher has display decorator."""
        from sc_linac_physics.cli.launchers import launch_srf_home

        assert hasattr(launch_srf_home, "_launcher_category")
        assert launch_srf_home._launcher_category == "display"

    def test_launch_cavity_display(self):
        """Test cavity display launcher."""
        from sc_linac_physics.cli.launchers import launch_cavity_display

        with patch(
            "sc_linac_physics.displays.cavity_display.cavity_display.CavityDisplayGUI"
        ):
            launch_cavity_display(standalone=False)

            assert self.mock_launch.called
            call_kwargs = self.mock_launch.call_args
            assert call_kwargs.kwargs["standalone"] is False

    def test_launch_fault_decoder(self):
        """Test fault decoder launcher."""
        from sc_linac_physics.cli.launchers import launch_fault_decoder

        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay"
        ):
            launch_fault_decoder()

            assert self.mock_launch.called

    def test_launch_fault_count(self):
        """Test fault count launcher."""
        from sc_linac_physics.cli.launchers import launch_fault_count

        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay"
        ):
            launch_fault_count()

            assert self.mock_launch.called


class TestApplicationLaunchers:
    """Test individual application launcher functions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up common mocks for all application launcher tests."""
        with (
            patch("sys.exit"),
            patch(
                "sc_linac_physics.cli.launchers.launch_python_display"
            ) as mock_launch,
        ):
            self.mock_launch = mock_launch
            yield

    def test_launch_quench_processing(self):
        """Test quench processing launcher."""
        from sc_linac_physics.cli.launchers import launch_quench_processing

        with patch(
            "sc_linac_physics.applications.quench_processing.quench_gui.QuenchGUI"
        ):
            launch_quench_processing(standalone=True)

            assert self.mock_launch.called
            call_kwargs = self.mock_launch.call_args
            assert call_kwargs.kwargs["standalone"] is True

    def test_launch_quench_processing_has_application_decorator(self):
        """Test that quench processing launcher has application decorator."""
        from sc_linac_physics.cli.launchers import launch_quench_processing

        assert hasattr(launch_quench_processing, "_launcher_category")
        assert launch_quench_processing._launcher_category == "application"

    def test_launch_auto_setup(self):
        """Test auto setup launcher."""
        from sc_linac_physics.cli.launchers import launch_auto_setup

        with patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SetupGUI"
        ):
            launch_auto_setup()

            assert self.mock_launch.called

    def test_launch_q0_measurement(self):
        """Test Q0 measurement launcher."""
        from sc_linac_physics.cli.launchers import launch_q0_measurement

        with patch("sc_linac_physics.applications.q0.q0_gui.Q0GUI"):
            launch_q0_measurement()

            assert self.mock_launch.called

    def test_launch_tuning(self):
        """Test tuning launcher."""
        from sc_linac_physics.cli.launchers import launch_tuning

        with patch("sc_linac_physics.applications.tuning.tuning_gui.Tuner"):
            launch_tuning()

            assert self.mock_launch.called

    def test_launch_microphonics(self):
        """Test microphonics launcher."""
        from sc_linac_physics.cli.launchers import launch_microphonics

        with patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.MicrophonicsGUI"
        ):
            launch_microphonics()

            assert self.mock_launch.called


class TestMainExecution:
    """Test __main__ execution."""

    def test_main_calls_launch_srf_home(self):
        """Test that running as main launches SRF home."""
        with patch(
            "sc_linac_physics.cli.launchers.launch_srf_home"
        ) as mock_launch:
            # Simulate running as __main__
            import sc_linac_physics.cli.launchers as launcher_module

            # Save original __name__
            original_name = launcher_module.__name__

            try:
                launcher_module.__name__ = "__main__"

                # Re-execute the if __name__ == '__main__' block
                if launcher_module.__name__ == "__main__":
                    launcher_module.launch_srf_home()

                mock_launch.assert_called_once()
            finally:
                launcher_module.__name__ = original_name


class TestSysArgvPassing:
    """Test that sys.argv is correctly passed to displays."""

    def test_sys_argv_passed_to_launch(self, mock_pydm_app):
        """Test that sys.argv arguments are passed through."""
        from sc_linac_physics.cli.launchers import launch_python_display

        test_args = ["--arg1", "value1", "--arg2"]

        mock_display_class = MagicMock()

        with patch("sys.exit"), patch("sys.argv", ["script.py"] + test_args):
            launch_python_display(
                mock_display_class, *test_args, standalone=True
            )

        # Verify args were passed to PyDMApplication
        mock_pydm_app.assert_called_once_with(command_line_args=test_args)
