# "test_runner.py"
"""Comprehensive tests for cavity fault monitoring runner."""

import signal
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from sc_linac_physics.utils.epics import (
    PVConnectionError,
    PVGetError,
    PVPutError,
)


def create_mock_cavities(count=5):
    """Helper to create mock cavities."""
    mock_cavities = []
    for i in range(count):
        cavity = MagicMock()
        cavity.__str__ = Mock(return_value=f"TestCavity{i}")
        cavity.faults = [MagicMock() for _ in range(2)]
        cavity.run_through_faults = MagicMock(return_value=None)
        mock_cavities.append(cavity)
    return mock_cavities


@pytest.fixture
def runner():
    """Create a runner instance with mocked backend and PVs."""
    with patch(
        "sc_linac_physics.displays.cavity_display.backend.runner.BackendMachine"
    ) as mock_machine:
        mock_cavities = create_mock_cavities(5)
        mock_machine.return_value.all_iterator = iter(mock_cavities)

        from sc_linac_physics.displays.cavity_display.backend.runner import (
            Runner,
        )

        runner = Runner(lazy_fault_pvs=True)

        # Create a properly configured mock PV
        mock_pv = MagicMock()
        mock_pv.get = MagicMock(return_value=100)
        mock_pv.put = MagicMock(return_value=None)
        runner._watcher_pv_obj = mock_pv

        yield runner


class TestBasicFunctionality:
    """Test core runner functionality."""

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.sleep")
    def test_check_faults(self, mock_sleep, runner):
        """Test basic fault checking."""
        assert len(runner.backend_cavities) == 5
        assert isinstance(runner.backend_cavities[0], MagicMock)

        runner.check_faults()

        for cavity in runner.backend_cavities:
            cavity.run_through_faults.assert_called()
        runner._watcher_pv_obj.put.assert_called()

    def test_watcher_pv_obj(self, runner):
        """Test watcher PV object access."""
        assert runner.watcher_pv_obj == runner._watcher_pv_obj

    def test_initialization(self):
        """Test runner initialization."""
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.runner.BackendMachine"
        ) as mock_machine:
            from sc_linac_physics.displays.cavity_display.backend.runner import (
                Runner,
            )

            mock_cavities = create_mock_cavities(3)
            mock_machine.return_value.all_iterator = iter(mock_cavities)

            runner = Runner(lazy_fault_pvs=True)

            assert len(runner.backend_cavities) == 3
            assert (
                runner.watcher_pv_name == "PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"
            )
            assert runner._running is False
            assert runner._heartbeat_failures == 0
            assert runner._first_check is True

    def test_initialization_failure(self):
        """Test handling of initialization failures."""
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.runner.BackendMachine"
        ) as mock_machine:
            from sc_linac_physics.displays.cavity_display.backend.runner import (
                Runner,
            )

            mock_machine.side_effect = RuntimeError("Init failed")

            with pytest.raises(RuntimeError):
                Runner(lazy_fault_pvs=True)


class TestFaultChecking:
    """Test fault checking scenarios."""

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.sleep")
    def test_cavity_errors_dont_stop_checking(self, mock_sleep, runner):
        """Test that cavity errors don't stop the check cycle."""
        runner.backend_cavities[0].run_through_faults.side_effect = (
            RuntimeError("Error 1")
        )
        runner.backend_cavities[2].run_through_faults.side_effect = ValueError(
            "Error 2"
        )

        runner.check_faults()

        for cavity in runner.backend_cavities:
            cavity.run_through_faults.assert_called_once()
        runner._watcher_pv_obj.put.assert_called()

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.sleep")
    def test_first_check_flag_updates(self, mock_sleep, runner):
        """Test that first_check flag is properly managed."""
        assert runner._first_check is True
        runner.check_faults()
        assert runner._first_check is False

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.sleep")
    def test_slow_cavity_tracking(self, mock_sleep, runner):
        """Test tracking of slow cavities."""

        def slow_cavity(*args, **kwargs):
            time.sleep(0.15)

        runner.backend_cavities[1].run_through_faults = slow_cavity
        runner.check_faults()

    @patch(
        "sc_linac_physics.displays.cavity_display.backend.runner.BACKEND_SLEEP_TIME",
        0.5,
    )
    @patch(
        "sc_linac_physics.displays.cavity_display.backend.runner.DEBUG", True
    )
    def test_debug_mode_sleep(self, runner):
        """Test that debug mode maintains cycle time."""
        start = time.time()
        runner.check_faults()
        duration = time.time() - start
        assert duration >= 0.5

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.sleep")
    def test_all_cavities_checked_in_order(self, mock_sleep, runner):
        """Test that all cavities are checked in order."""
        call_order = []

        def track_call(cavity_id):
            def _track(*args, **kwargs):
                call_order.append(cavity_id)

            return _track

        for i, cavity in enumerate(runner.backend_cavities):
            cavity.run_through_faults = track_call(i)

        runner.check_faults()

        assert call_order == list(range(len(runner.backend_cavities)))


class TestHeartbeat:
    """Test heartbeat functionality."""

    def test_heartbeat_success(self, runner):
        """Test successful heartbeat update."""
        runner._watcher_pv_obj.get.return_value = 100
        runner._update_heartbeat()

        runner._watcher_pv_obj.get.assert_called_once_with(timeout=2.0)
        runner._watcher_pv_obj.put.assert_called_once_with(101, timeout=2.0)
        assert runner._heartbeat_failures == 0

    def test_heartbeat_recovery(self, runner):
        """Test recovery after failures."""
        runner._heartbeat_failures = 3
        runner._watcher_pv_obj.get.return_value = 100
        runner._update_heartbeat()
        assert runner._heartbeat_failures == 0

    @pytest.mark.parametrize(
        "error_class", [PVConnectionError, PVGetError, PVPutError]
    )
    def test_heartbeat_errors(self, runner, error_class):
        """Test handling of various heartbeat errors."""
        runner._watcher_pv_obj.get.side_effect = error_class("Error")
        runner._update_heartbeat()
        assert runner._heartbeat_failures == 1

    def test_heartbeat_max_failures_stops_runner(self, runner):
        """Test stopping after max failures."""
        runner._running = True
        runner._heartbeat_failures = 9
        runner._watcher_pv_obj.get.side_effect = PVConnectionError("Lost")

        runner._update_heartbeat()

        assert runner._heartbeat_failures == 10
        assert runner._running is False

    def test_heartbeat_unexpected_error(self, runner):
        """Test unexpected error handling."""
        runner._running = True
        runner._heartbeat_failures = 9
        runner._watcher_pv_obj.get.side_effect = Exception("Unexpected")

        runner._update_heartbeat()

        assert runner._heartbeat_failures == 10
        assert runner._running is False


class TestWatcherPV:
    """Test watcher PV lazy initialization."""

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.PV")
    def test_lazy_pv_creation(self, mock_pv_class):
        """Test lazy creation and caching of watcher PV."""
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.runner.BackendMachine"
        ) as mock_machine:
            from sc_linac_physics.displays.cavity_display.backend.runner import (
                Runner,
            )

            mock_machine.return_value.all_iterator = iter([])
            mock_pv = MagicMock()
            mock_pv_class.return_value = mock_pv

            runner = Runner(lazy_fault_pvs=True)
            runner._watcher_pv_obj = None

            result1 = runner.watcher_pv_obj
            result2 = runner.watcher_pv_obj

            mock_pv_class.assert_called_once()
            assert result1 == result2 == mock_pv

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.PV")
    def test_pv_connection_failure(self, mock_pv_class):
        """Test handling of PV connection failure."""
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.runner.BackendMachine"
        ) as mock_machine:
            from sc_linac_physics.displays.cavity_display.backend.runner import (
                Runner,
            )

            mock_machine.return_value.all_iterator = iter([])
            mock_pv_class.side_effect = PVConnectionError("Failed")

            runner = Runner(lazy_fault_pvs=True)
            runner._watcher_pv_obj = None

            with pytest.raises(PVConnectionError):
                _ = runner.watcher_pv_obj


class TestRunLoop:
    """Test the main run loop."""

    def test_run_initialization(self, runner):
        """Test run loop setup and execution."""
        with patch.object(runner, "check_faults") as mock_check:

            def stop_after_first(*args, **kwargs):
                runner.stop()

            mock_check.side_effect = stop_after_first

            runner.run()

            mock_check.assert_called_once()
            assert any(
                call[0] == (0,)
                for call in runner._watcher_pv_obj.put.call_args_list
            )

    def test_run_keyboard_interrupt(self, runner):
        """Test keyboard interrupt handling."""
        with patch.object(runner, "check_faults") as mock_check:
            mock_check.side_effect = KeyboardInterrupt()
            runner.run()
            assert runner._running is False

    def test_run_unexpected_error(self, runner):
        """Test unexpected error propagation."""
        with patch.object(runner, "check_faults") as mock_check:
            mock_check.side_effect = RuntimeError("Error")
            with pytest.raises(RuntimeError):
                runner.run()

    def test_run_heartbeat_init_failure(self, runner):
        """Test handling of heartbeat init failure."""
        runner._watcher_pv_obj.put.side_effect = [
            PVConnectionError("Failed"),
            None,
        ]

        with patch.object(runner, "check_faults") as mock_check:

            def stop_after_first(*args, **kwargs):
                runner.stop()

            mock_check.side_effect = stop_after_first
            runner.run()


class TestSignalHandling:
    """Test signal handling."""

    def test_signal_handler_stops_runner(self, runner):
        """Test signal handler stops the runner."""
        runner._running = True
        runner._signal_handler(signal.SIGTERM, None)
        assert runner._running is False

    def test_signal_handler_during_init(self):
        """Test signal handling during initialization."""
        from sc_linac_physics.displays.cavity_display.backend.runner import (
            _signal_handler_during_init,
        )
        import sc_linac_physics.displays.cavity_display.backend.runner as runner_module

        runner_module._initialization_in_progress = True
        with pytest.raises(SystemExit):
            _signal_handler_during_init(signal.SIGINT, None)
        runner_module._initialization_in_progress = False

        runner_module._initialization_in_progress = False
        with pytest.raises(KeyboardInterrupt):
            _signal_handler_during_init(signal.SIGINT, None)


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_normal(self, runner):
        """Test normal context manager usage."""
        with runner as r:
            assert r is runner
        assert runner._running is False

    def test_context_manager_with_exception(self, runner):
        """Test exception handling in context manager."""
        with pytest.raises(ValueError):
            with runner:
                raise ValueError("Error")
        assert runner._running is False

    def test_context_manager_keyboard_interrupt(self, runner):
        """Test KeyboardInterrupt is suppressed."""
        with runner:
            raise KeyboardInterrupt()
        assert runner._running is False


class TestMainFunction:
    """Test main entry point."""

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.Runner")
    @patch("sc_linac_physics.displays.cavity_display.backend.runner.signal")
    def test_main_success(self, mock_signal, mock_runner_class):
        """Test successful main execution."""
        from sc_linac_physics.displays.cavity_display.backend.runner import main

        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner
        mock_runner.__enter__ = Mock(return_value=mock_runner)
        mock_runner.__exit__ = Mock(return_value=False)
        mock_runner.run.side_effect = lambda: None

        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.Runner")
    def test_main_init_keyboard_interrupt(self, mock_runner_class):
        """Test keyboard interrupt during init."""
        from sc_linac_physics.displays.cavity_display.backend.runner import main

        mock_runner_class.side_effect = KeyboardInterrupt()

        with patch("sys.exit") as mock_exit:
            main()
            exit_calls = [call[0][0] for call in mock_exit.call_args_list]
            assert 0 in exit_calls

    @patch("sc_linac_physics.displays.cavity_display.backend.runner.Runner")
    def test_main_fatal_error(self, mock_runner_class):
        """Test fatal error handling."""
        from sc_linac_physics.displays.cavity_display.backend.runner import main

        mock_runner_class.side_effect = RuntimeError("Fatal")

        with patch("sys.exit") as mock_exit:
            main()
            exit_calls = [call[0][0] for call in mock_exit.call_args_list]
            assert 1 in exit_calls


class TestUtilities:
    """Test utility functions."""

    def test_track_cavity_init(self):
        """Test cavity initialization tracking."""
        from sc_linac_physics.displays.cavity_display.backend.runner import (
            track_cavity_init,
        )
        import sc_linac_physics.displays.cavity_display.backend.runner as runner_module

        runner_module._cavity_init_count = 9
        runner_module._last_progress_time = time.time()

        with patch("builtins.print"):
            track_cavity_init()

        assert runner_module._cavity_init_count == 10

    def test_stop_method(self, runner):
        """Test stop method."""
        runner._running = True
        runner.stop()
        assert runner._running is False

        # Test idempotency
        runner.stop()
        assert runner._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=runner", "--cov-report=term-missing"])
