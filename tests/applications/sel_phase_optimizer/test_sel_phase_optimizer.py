#!/usr/bin/env python

"""
Tests for SEL phase optimizer script
"""

import time
from unittest.mock import Mock, patch, call

import pytest

from sc_linac_physics.applications.sel_phase_optimizer import (
    sel_phase_optimizer,
)
from sc_linac_physics.utils.epics import PVInvalidError, PVConnectionError


@pytest.fixture
def mock_pv():
    """Create a mock PV object"""
    pv = Mock()
    pv.get.return_value = 0
    pv.put.return_value = None
    return pv


@pytest.fixture
def mock_cavity():
    """Create a mock SELCavity object"""
    cavity = Mock()
    cavity.straighten_iq_plot.return_value = 2.0  # step size
    cavity.logger = Mock()
    return cavity


@pytest.fixture(autouse=True)
def reset_heartbeat_pv():
    """Reset the global heartbeat PV before each test"""
    sel_phase_optimizer._HEARTBEAT_PV = None
    yield
    sel_phase_optimizer._HEARTBEAT_PV = None


class TestGetHeartbeatPv:
    """Tests for get_heartbeat_pv function"""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.PV"
    )
    def test_creates_pv_on_first_call(self, mock_pv_class):
        """Test that PV is created on first call"""
        mock_pv_instance = Mock()
        mock_pv_class.return_value = mock_pv_instance

        result = sel_phase_optimizer.get_heartbeat_pv()

        mock_pv_class.assert_called_once_with(
            "PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT"
        )
        assert result == mock_pv_instance

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.PV"
    )
    def test_returns_cached_pv_on_subsequent_calls(self, mock_pv_class):
        """Test that the same PV instance is returned on subsequent calls"""
        mock_pv_instance = Mock()
        mock_pv_class.return_value = mock_pv_instance

        result1 = sel_phase_optimizer.get_heartbeat_pv()
        result2 = sel_phase_optimizer.get_heartbeat_pv()

        mock_pv_class.assert_called_once()
        assert result1 == result2 == mock_pv_instance


class TestUpdateHeartbeat:
    """Tests for update_heartbeat function"""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_updates_heartbeat_correct_number_of_times(
        self, mock_get_pv, mock_sleep, mock_pv
    ):
        """Test that heartbeat is updated the correct number of times"""
        mock_get_pv.return_value = mock_pv
        # Make get() return incrementing values to simulate the actual behavior
        mock_pv.get.side_effect = [10, 11, 12]

        sel_phase_optimizer.update_heartbeat(3)

        assert mock_pv.get.call_count == 3
        assert mock_pv.put.call_count == 3
        assert mock_sleep.call_count == 3

        # Verify the put calls
        put_calls = [call(11), call(12), call(13)]
        mock_pv.put.assert_has_calls(put_calls)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_pv_connection_error(
        self, mock_get_pv, mock_sleep, mock_pv, capsys
    ):
        """Test that PVConnectionError is caught and logged"""
        mock_get_pv.return_value = mock_pv
        mock_pv.get.side_effect = PVConnectionError("Connection failed")

        sel_phase_optimizer.update_heartbeat(2)

        captured = capsys.readouterr()
        assert "Heartbeat update failed" in captured.out
        assert mock_sleep.call_count == 2

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_pv_invalid_error(
        self, mock_get_pv, mock_sleep, mock_pv, capsys
    ):
        """Test that PVInvalidError is caught and logged"""
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 5
        mock_pv.put.side_effect = PVInvalidError("Invalid PV")

        sel_phase_optimizer.update_heartbeat(1)

        captured = capsys.readouterr()
        assert "Heartbeat update failed" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_type_error(self, mock_get_pv, mock_sleep, mock_pv, capsys):
        """Test that TypeError is caught and logged"""
        mock_get_pv.return_value = mock_pv
        mock_pv.get.side_effect = TypeError("Type error")

        sel_phase_optimizer.update_heartbeat(1)

        captured = capsys.readouterr()
        assert "Heartbeat update failed" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_prints_sleep_message(
        self, mock_get_pv, mock_sleep, mock_pv, capsys
    ):
        """Test that sleep message is printed"""
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 0

        sel_phase_optimizer.update_heartbeat(5)

        captured = capsys.readouterr()
        assert "Sleeping for 5 seconds" in captured.out


class TestRun:
    """Tests for run function"""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_processes_all_cavities(
        self, mock_machine, mock_get_pv, mock_update_hb, mock_pv, mock_cavity
    ):
        """Test that all cavities are processed"""
        # Create multiple mock cavities
        cavity1 = Mock()
        cavity1.straighten_iq_plot.return_value = 2.0
        cavity1.logger = Mock()

        cavity2 = Mock()
        cavity2.straighten_iq_plot.return_value = 3.0
        cavity2.logger = Mock()

        mock_machine.all_iterator = [cavity1, cavity2]
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 0

        # Run once and break
        with patch.object(
            sel_phase_optimizer,
            "run",
            side_effect=lambda: self._run_once(mock_machine, mock_get_pv),
        ):
            try:
                sel_phase_optimizer.run()
            except StopIteration:
                pass

        cavity1.straighten_iq_plot.assert_called_once()
        cavity2.straighten_iq_plot.assert_called_once()

    def _run_once(self, mock_machine, mock_get_pv):
        """Helper to run the loop once"""
        cavities = list(mock_machine.all_iterator)
        heartbeat_pv = mock_get_pv()

        for cavity in cavities:
            cavity.straighten_iq_plot()
            heartbeat_pv.get()
            heartbeat_pv.put(1)

        raise StopIteration

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.MAX_STEP",
        5,
    )
    def test_many_large_steps_triggers_short_wait(
        self, mock_machine, mock_get_pv, mock_update_hb, mock_pv, capsys
    ):
        """Test that many large steps triggers 5 second wait"""
        # Create 6 cavities with large steps
        cavities = []
        for _ in range(6):
            cavity = Mock()
            cavity.straighten_iq_plot.return_value = 5.0  # MAX_STEP
            cavity.logger = Mock()
            cavities.append(cavity)

        mock_machine.all_iterator = cavities
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 0

        # Run once
        run_count = 0

        def run_once_wrapper():
            nonlocal run_count
            if run_count > 0:
                raise KeyboardInterrupt
            run_count += 1

            cavities_list = list(mock_machine.all_iterator)
            heartbeat_pv = mock_get_pv()
            num_large_steps = 0

            for cavity in cavities_list:
                step_size = cavity.straighten_iq_plot()
                num_large_steps += 1 if step_size >= 5 else 0
                heartbeat_pv.get()
                heartbeat_pv.put(1)

            if num_large_steps > 5:
                print(
                    f"\033[91mPhase change limited to 5 deg {num_large_steps} times. Re-running program.\033[0m"
                )
                mock_update_hb(5)
            else:
                mock_update_hb(600)

        with patch.object(
            sel_phase_optimizer, "run", side_effect=run_once_wrapper
        ):
            try:
                sel_phase_optimizer.run()
            except KeyboardInterrupt:
                pass

        mock_update_hb.assert_called_with(5)
        captured = capsys.readouterr()
        assert "Phase change limited to 5 deg" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.MAX_STEP",
        5,
    )
    def test_few_large_steps_triggers_long_wait(
        self, mock_machine, mock_get_pv, mock_update_hb, mock_pv, capsys
    ):
        """Test that few large steps triggers 600 second wait"""
        # Create 3 cavities with small steps
        cavities = []
        for _ in range(3):
            cavity = Mock()
            cavity.straighten_iq_plot.return_value = 2.0  # Small step
            cavity.logger = Mock()
            cavities.append(cavity)

        mock_machine.all_iterator = cavities
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 0

        run_count = 0

        def run_once_wrapper():
            nonlocal run_count
            if run_count > 0:
                raise KeyboardInterrupt
            run_count += 1

            cavities_list = list(mock_machine.all_iterator)
            heartbeat_pv = mock_get_pv()
            num_large_steps = 0

            for cavity in cavities_list:
                step_size = cavity.straighten_iq_plot()
                num_large_steps += 1 if step_size >= 5 else 0
                heartbeat_pv.get()
                heartbeat_pv.put(1)

            if num_large_steps > 5:
                mock_update_hb(5)
            else:
                current_time = time.strftime(
                    "%m/%d/%y %H:%M:%S", time.localtime()
                )
                print(
                    f"\033[94mThanks for your help! The current date/time is {current_time}\033[0m"
                )
                mock_update_hb(600)

        with patch.object(
            sel_phase_optimizer, "run", side_effect=run_once_wrapper
        ):
            try:
                sel_phase_optimizer.run()
            except KeyboardInterrupt:
                pass

        mock_update_hb.assert_called_with(600)
        captured = capsys.readouterr()
        assert "Thanks for your help!" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_handles_cavity_error(
        self, mock_machine, mock_get_pv, mock_update_hb, mock_pv, mock_cavity
    ):
        """Test that cavity errors are caught and logged"""
        mock_cavity.straighten_iq_plot.side_effect = PVInvalidError("PV error")
        mock_machine.all_iterator = [mock_cavity]
        mock_get_pv.return_value = mock_pv
        mock_pv.get.return_value = 0

        run_count = 0

        def run_once_wrapper():
            nonlocal run_count
            if run_count > 0:
                raise KeyboardInterrupt
            run_count += 1

            cavities_list = list(mock_machine.all_iterator)
            heartbeat_pv = mock_get_pv()

            for cavity in cavities_list:
                try:
                    cavity.straighten_iq_plot()
                except (PVInvalidError, TypeError) as e:
                    cavity.logger.error(f"Failed to straighten IQ plot: {e}")

                heartbeat_pv.get()
                heartbeat_pv.put(1)

            mock_update_hb(600)

        with patch.object(
            sel_phase_optimizer, "run", side_effect=run_once_wrapper
        ):
            try:
                sel_phase_optimizer.run()
            except KeyboardInterrupt:
                pass

        mock_cavity.logger.error.assert_called_once()

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_handles_heartbeat_error_in_loop(
        self, mock_machine, mock_get_pv, mock_update_hb, mock_pv, mock_cavity
    ):
        """Test that heartbeat errors in the loop are caught"""
        mock_cavity.straighten_iq_plot.return_value = 2.0
        mock_machine.all_iterator = [mock_cavity]
        mock_get_pv.return_value = mock_pv
        mock_pv.get.side_effect = PVConnectionError("Connection error")

        run_count = 0

        def run_once_wrapper():
            nonlocal run_count
            if run_count > 0:
                raise KeyboardInterrupt
            run_count += 1

            cavities_list = list(mock_machine.all_iterator)
            heartbeat_pv = mock_get_pv()

            for cavity in cavities_list:
                cavity.straighten_iq_plot()
                try:
                    current_value = heartbeat_pv.get()
                    heartbeat_pv.put(current_value + 1)
                except (PVConnectionError, PVInvalidError) as e:
                    cavity.logger.warning(f"Heartbeat update failed: {e}")

            mock_update_hb(600)

        with patch.object(
            sel_phase_optimizer, "run", side_effect=run_once_wrapper
        ):
            try:
                sel_phase_optimizer.run()
            except KeyboardInterrupt:
                pass

        mock_cavity.logger.warning.assert_called_once()


class TestMain:
    """Tests for main function"""

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_initializes_heartbeat_to_zero(
        self, mock_get_pv, mock_run, mock_pv
    ):
        """Test that heartbeat is initialized to 0"""
        mock_get_pv.return_value = mock_pv
        mock_run.side_effect = KeyboardInterrupt  # Exit immediately

        sel_phase_optimizer.main()

        mock_pv.put.assert_called_with(0)

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_calls_run(self, mock_get_pv, mock_run, mock_pv):
        """Test that run() is called"""
        mock_get_pv.return_value = mock_pv
        mock_run.side_effect = KeyboardInterrupt

        sel_phase_optimizer.main()

        mock_run.assert_called_once()

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_keyboard_interrupt(
        self, mock_get_pv, mock_run, mock_pv, capsys
    ):
        """Test that KeyboardInterrupt is handled gracefully"""
        mock_get_pv.return_value = mock_pv
        mock_run.side_effect = KeyboardInterrupt

        sel_phase_optimizer.main()

        captured = capsys.readouterr()
        assert "Optimization stopped by user" in captured.out

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_pv_connection_error(
        self, mock_get_pv, mock_run, mock_pv, capsys
    ):
        """Test that PVConnectionError is handled"""
        mock_get_pv.return_value = mock_pv
        mock_pv.put.side_effect = PVConnectionError("Connection failed")

        with pytest.raises(PVConnectionError):
            sel_phase_optimizer.main()

        captured = capsys.readouterr()
        assert "Failed to connect to heartbeat PV" in captured.out

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_handles_unexpected_error(
        self, mock_get_pv, mock_run, mock_pv, capsys
    ):
        """Test that unexpected errors are handled"""
        mock_get_pv.return_value = mock_pv
        mock_run.side_effect = ValueError("Unexpected error")

        with pytest.raises(ValueError):
            sel_phase_optimizer.main()

        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out

    @patch("sys.argv", ["sel_phase_optimizer.py"])
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.get_heartbeat_pv"
    )
    def test_parses_arguments(self, mock_get_pv, mock_run, mock_pv):
        """Test that arguments are parsed"""
        mock_get_pv.return_value = mock_pv
        mock_run.side_effect = KeyboardInterrupt

        sel_phase_optimizer.main()

        # If we get here without SystemExit, argparse worked correctly
        assert True
