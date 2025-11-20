from unittest.mock import Mock, patch, call

import pytest
from lcls_tools.common.controls.pyepics.utils import PVInvalidError

from sc_linac_physics.applications.sel_phase_optimizer.sel_phase_linac import (
    MAX_STEP,
)
from sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer import (
    update_heartbeat,
    run,
    main,
    HEARTBEAT_PV,
)


class TestUpdateHeartbeat:
    """Tests for update_heartbeat function."""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    def test_update_heartbeat_normal(self, mock_heartbeat_pv, mock_sleep):
        """Test update_heartbeat increments PV and sleeps correctly."""
        # Make get() return incrementing values: 10, 11, 12
        mock_heartbeat_pv.get.side_effect = [10, 11, 12]

        update_heartbeat(3)

        # Should increment 3 times
        assert mock_heartbeat_pv.put.call_count == 3
        assert mock_sleep.call_count == 3

        # Verify increments: 10->11, 11->12, 12->13
        expected_calls = [call(11), call(12), call(13)]
        mock_heartbeat_pv.put.assert_has_calls(expected_calls)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    def test_update_heartbeat_handles_type_error(
        self, mock_heartbeat_pv, mock_sleep, capsys
    ):
        """Test update_heartbeat handles TypeError gracefully."""
        mock_heartbeat_pv.get.side_effect = TypeError("Test error")

        update_heartbeat(2)

        # Should still sleep even if PV operations fail
        assert mock_sleep.call_count == 2

        # Should print the error
        captured = capsys.readouterr()
        assert "Test error" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    def test_update_heartbeat_zero_wait(self, mock_heartbeat_pv, mock_sleep):
        """Test update_heartbeat with zero wait time."""
        update_heartbeat(0)

        # Should not increment or sleep
        mock_heartbeat_pv.put.assert_not_called()
        mock_sleep.assert_not_called()

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    def test_update_heartbeat_prints_message(
        self, mock_heartbeat_pv, mock_sleep, capsys
    ):
        """Test update_heartbeat prints sleep message."""
        mock_heartbeat_pv.get.return_value = 0

        update_heartbeat(5)

        captured = capsys.readouterr()
        assert "Sleeping for 5 seconds" in captured.out


class TestRun:
    """Tests for run function."""

    @pytest.fixture
    def mock_cavities(self):
        """Create mock cavities."""
        cavities = []
        for i in range(3):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = 0.5  # Small step
            cavity.logger = Mock()
            cavities.append(cavity)
        return cavities

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.localtime"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.strftime"
    )
    def test_run_normal_operation_one_iteration(
        self,
        mock_strftime,
        mock_localtime,
        mock_sel_machine,
        mock_heartbeat_pv,
        mock_update_heartbeat,
        mock_cavities,
    ):
        """Test run with normal operation (one iteration)."""
        # Setup
        mock_sel_machine.all_iterator = iter(mock_cavities)
        mock_heartbeat_pv.get.return_value = 0
        mock_strftime.return_value = "01/01/24 12:00:00"

        # Mock the while loop to run only once
        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        # Verify all cavities were processed
        for cavity in mock_cavities:
            cavity.straighten_iq_plot.assert_called_once()

        # Should update heartbeat after each cavity
        assert mock_heartbeat_pv.put.call_count == len(mock_cavities)

        # Should sleep for 600 seconds (normal operation)
        mock_update_heartbeat.assert_called_with(600)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_run_with_large_steps(
        self,
        mock_sel_machine,
        mock_heartbeat_pv,
        mock_update_heartbeat,
        mock_cavities,
    ):
        """Test run when many large steps are detected."""
        # Make 6 cavities return large steps
        for i in range(6):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = MAX_STEP + 1  # Large step
            cavity.logger = Mock()
            mock_cavities.append(cavity)

        mock_sel_machine.all_iterator = iter(mock_cavities)
        mock_heartbeat_pv.get.return_value = 0

        # Mock to run only once
        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        # Should sleep for only 5 seconds (re-run condition)
        mock_update_heartbeat.assert_called_with(5)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_run_handles_pv_invalid_error(
        self, mock_sel_machine, mock_heartbeat_pv, mock_update_heartbeat
    ):
        """Test run handles PVInvalidError gracefully."""
        cavity = Mock(spec=["straighten_iq_plot", "logger"])
        cavity.straighten_iq_plot.side_effect = PVInvalidError("Invalid PV")
        cavity.logger = Mock()

        mock_sel_machine.all_iterator = iter([cavity])
        mock_heartbeat_pv.get.return_value = 0

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run - should not crash
        with pytest.raises(KeyboardInterrupt):
            run()

        # Error should be logged
        cavity.logger.error.assert_called_once()

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_run_handles_type_error(
        self, mock_sel_machine, mock_heartbeat_pv, mock_update_heartbeat
    ):
        """Test run handles TypeError gracefully."""
        cavity = Mock(spec=["straighten_iq_plot", "logger"])
        cavity.straighten_iq_plot.side_effect = TypeError("Type error")
        cavity.logger = Mock()

        mock_sel_machine.all_iterator = iter([cavity])
        mock_heartbeat_pv.get.return_value = 0

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run - should not crash
        with pytest.raises(KeyboardInterrupt):
            run()

        # Error should be logged
        cavity.logger.error.assert_called_once()

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_run_mixed_step_sizes(
        self, mock_sel_machine, mock_heartbeat_pv, mock_update_heartbeat
    ):
        """Test run with mix of small and large steps."""
        cavities = []

        # 3 small steps
        for i in range(3):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = 1.0  # Small step
            cavity.logger = Mock()
            cavities.append(cavity)

        # 5 large steps (exactly at threshold)
        for i in range(5):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = (
                MAX_STEP + 0.1
            )  # Large step
            cavity.logger = Mock()
            cavities.append(cavity)

        mock_sel_machine.all_iterator = iter(cavities)
        mock_heartbeat_pv.get.return_value = 0

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        # Exactly 5 large steps - should use normal wait time
        mock_update_heartbeat.assert_called_with(600)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_run_prints_warning_for_large_steps(
        self, mock_sel_machine, mock_heartbeat_pv, mock_update_heartbeat, capsys
    ):
        """Test run prints warning message for large steps."""
        cavities = []

        # 6 large steps
        for i in range(6):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = MAX_STEP + 1
            cavity.logger = Mock()
            cavities.append(cavity)

        mock_sel_machine.all_iterator = iter(cavities)
        mock_heartbeat_pv.get.return_value = 0

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        captured = capsys.readouterr()
        assert "Phase change limited to 5 deg" in captured.out
        assert "Re-running program" in captured.out

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.localtime"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.strftime"
    )
    def test_run_prints_success_message(
        self,
        mock_strftime,
        mock_localtime,
        mock_sel_machine,
        mock_heartbeat_pv,
        mock_update_heartbeat,
        mock_cavities,
        capsys,
    ):
        """Test run prints success message with timestamp."""
        mock_sel_machine.all_iterator = iter(mock_cavities)
        mock_heartbeat_pv.get.return_value = 0
        mock_strftime.return_value = "12/25/24 14:30:00"

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        captured = capsys.readouterr()
        assert "Thanks for your help!" in captured.out
        assert "12/25/24 14:30:00" in captured.out


class TestMain:
    """Tests for main function."""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch("sys.argv", ["sel_phase_optimizer.py"])
    def test_main_initializes_and_runs(self, mock_heartbeat_pv, mock_run):
        """Test main initializes heartbeat and calls run."""
        mock_run.side_effect = KeyboardInterrupt("Stop test")

        with pytest.raises(KeyboardInterrupt):
            main()

        # Should reset heartbeat to 0
        mock_heartbeat_pv.put.assert_called_once_with(0)

        # Should call run
        mock_run.assert_called_once()

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.run"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch("sys.argv", ["sel_phase_optimizer.py", "--help"])
    def test_main_handles_help_argument(self, mock_heartbeat_pv, mock_run):
        """Test main handles --help argument."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        # argparse exits with code 0 for --help
        assert exc_info.value.code == 0

        # Should not call run
        mock_run.assert_not_called()


class TestHeartbeatPV:
    """Tests for HEARTBEAT_PV constant."""

    def test_heartbeat_pv_address(self):
        """Test that HEARTBEAT_PV has correct address."""
        assert HEARTBEAT_PV.pvname == "PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT"


class TestIntegration:
    """Integration tests."""

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.time.sleep"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_full_iteration_cycle(
        self, mock_sel_machine, mock_heartbeat_pv, mock_sleep
    ):
        """Test a complete iteration of the optimization loop."""
        # Setup cavities
        cavities = []
        for i in range(5):
            cavity = Mock(spec=["straighten_iq_plot", "logger"])
            cavity.straighten_iq_plot.return_value = 2.0  # Small step
            cavity.logger = Mock()
            cavities.append(cavity)

        mock_sel_machine.all_iterator = iter(cavities)
        mock_heartbeat_pv.get.return_value = 100

        # Run one iteration
        iteration_count = [0]

        def limited_sleep(duration):
            if duration == 1:  # Only count the sleep in update_heartbeat
                iteration_count[0] += 1
                if iteration_count[0] >= 600:  # After full wait cycle
                    raise KeyboardInterrupt("Stop test")

        mock_sleep.side_effect = limited_sleep

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        # All cavities should have been processed
        for cavity in cavities:
            cavity.straighten_iq_plot.assert_called_once()

        # Heartbeat should have been incremented for each cavity
        assert mock_heartbeat_pv.put.call_count >= len(cavities)

    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.update_heartbeat"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.HEARTBEAT_PV"
    )
    @patch(
        "sc_linac_physics.applications.sel_phase_optimizer.sel_phase_optimizer.SEL_MACHINE"
    )
    def test_recovery_from_errors(
        self, mock_sel_machine, mock_heartbeat_pv, mock_update_heartbeat
    ):
        """Test that the loop continues after errors."""
        # Mix of successful and failing cavities
        cavities = []

        # Good cavity
        good_cavity = Mock(spec=["straighten_iq_plot", "logger"])
        good_cavity.straighten_iq_plot.return_value = 1.0
        good_cavity.logger = Mock()
        cavities.append(good_cavity)

        # Bad cavity (PVInvalidError)
        bad_cavity1 = Mock(spec=["straighten_iq_plot", "logger"])
        bad_cavity1.straighten_iq_plot.side_effect = PVInvalidError("Error")
        bad_cavity1.logger = Mock()
        cavities.append(bad_cavity1)

        # Another good cavity
        good_cavity2 = Mock(spec=["straighten_iq_plot", "logger"])
        good_cavity2.straighten_iq_plot.return_value = 1.5
        good_cavity2.logger = Mock()
        cavities.append(good_cavity2)

        mock_sel_machine.all_iterator = iter(cavities)
        mock_heartbeat_pv.get.return_value = 0

        iteration_count = [0]

        def limited_update_heartbeat(wait_time):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                raise KeyboardInterrupt("Stop test")

        mock_update_heartbeat.side_effect = limited_update_heartbeat

        # Run
        with pytest.raises(KeyboardInterrupt):
            run()

        # Good cavities should have been called
        good_cavity.straighten_iq_plot.assert_called_once()
        good_cavity2.straighten_iq_plot.assert_called_once()

        # Error should have been logged
        bad_cavity1.logger.error.assert_called_once()

        # Should still complete the iteration
        mock_update_heartbeat.assert_called_once()
