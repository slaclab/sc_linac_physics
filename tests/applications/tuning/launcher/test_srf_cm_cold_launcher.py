from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher import (
    detune_cavity,
    detune_cryomodule,
    parse_args,
    main,
    DEFAULT_SLEEP_INTERVAL,
)
from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError


class TestDetuneCavity:
    """Tests for detune_cavity function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    def test_detune_cavity_success(self, mock_logger):
        """Test successful cavity detuning."""
        cavity = Mock()
        cavity.script_is_running = False
        cavity.__str__ = Mock(return_value="Cavity1")

        result = detune_cavity(cavity)

        assert result is True
        cavity.trigger_start.assert_called_once()
        mock_logger.info.assert_called_once()

        # Verify log message content
        call_args = mock_logger.info.call_args
        assert "Triggered cavity detuning" in call_args[0][0]

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    def test_detune_cavity_already_running(self, mock_logger):
        """Test detuning when script is already running."""
        cavity = Mock()
        cavity.script_is_running = True
        cavity.__str__ = Mock(return_value="Cavity1")

        result = detune_cavity(cavity)

        assert result is False
        cavity.trigger_start.assert_not_called()
        mock_logger.warning.assert_called_once()

        # Verify warning was logged
        call_args = mock_logger.warning.call_args
        assert "Script already running" in call_args[0][0]

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    def test_detune_cavity_generic_exception(self, mock_logger):
        """Test handling of generic exception during trigger_start."""
        cavity = Mock()
        cavity.script_is_running = False
        cavity.__str__ = Mock(return_value="Cavity1")
        cavity.trigger_start.side_effect = Exception("Test error")

        result = detune_cavity(cavity)

        assert result is False
        mock_logger.exception.assert_called_once()

        # Verify exception was logged
        call_args = mock_logger.exception.call_args
        assert "Error triggering" in call_args[0][0]

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    def test_detune_cavity_abort_error(self, mock_logger):
        """Test handling of CavityAbortError."""
        cavity = Mock()
        cavity.script_is_running = False
        cavity.__str__ = Mock(return_value="Cavity1")
        cavity.trigger_start.side_effect = CavityAbortError("Cavity aborted")

        result = detune_cavity(cavity)

        assert result is False
        mock_logger.error.assert_called_once()

        # Verify error message
        call_args = mock_logger.error.call_args
        assert "Cavity aborted" in call_args[0][0]


class TestDetuneCryomodule:
    """Tests for detune_cryomodule function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_all_success(
        self, mock_detune, mock_sleep, mock_logger
    ):
        """Test detuning all cavities successfully."""
        mock_detune.return_value = True

        cryomodule = Mock()
        cryomodule.__str__ = Mock(return_value="CM01")
        cavity1, cavity2, cavity3 = Mock(), Mock(), Mock()
        cryomodule.cavities = {
            "cav1": cavity1,
            "cav2": cavity2,
            "cav3": cavity3,
        }

        successful, failed = detune_cryomodule(cryomodule)

        assert successful == 3
        assert failed == 0
        assert mock_detune.call_count == 3
        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(DEFAULT_SLEEP_INTERVAL)

        # Verify logging calls
        assert mock_logger.debug.called
        assert mock_logger.info.called

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_mixed_results(
        self, mock_detune, mock_sleep, mock_logger
    ):
        """Test detuning with some successes and failures."""
        mock_detune.side_effect = [True, False, True, False]

        cryomodule = Mock()
        cryomodule.__str__ = Mock(return_value="CM01")
        cryomodule.cavities = {
            "cav1": Mock(),
            "cav2": Mock(),
            "cav3": Mock(),
            "cav4": Mock(),
        }

        successful, failed = detune_cryomodule(cryomodule)

        assert successful == 2
        assert failed == 2
        assert mock_detune.call_count == 4
        assert mock_sleep.call_count == 4

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_empty(
        self, mock_detune, mock_sleep, mock_logger
    ):
        """Test detuning cryomodule with no cavities."""
        cryomodule = Mock()
        cryomodule.__str__ = Mock(return_value="CM01")
        cryomodule.cavities = {}

        successful, failed = detune_cryomodule(cryomodule)

        assert successful == 0
        assert failed == 0
        mock_detune.assert_not_called()
        mock_sleep.assert_not_called()


class TestParseArgs:
    """Tests for parse_args function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02", "CM03"],
    )
    def test_parse_args_valid_cryomodule(self):
        """Test parsing valid cryomodule argument."""
        args = parse_args(["--cryomodule", "CM01"])
        assert args.cryomodule == "CM01"

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02", "CM03"],
    )
    def test_parse_args_short_flag(self):
        """Test parsing with short flag."""
        args = parse_args(["-cm", "CM02"])
        assert args.cryomodule == "CM02"

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02", "CM03"],
    )
    def test_parse_args_missing_required(self):
        """Test that missing required argument raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args([])

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02", "CM03"],
    )
    def test_parse_args_invalid_choice(self):
        """Test that invalid cryomodule choice raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--cryomodule", "INVALID"])


class TestMain:
    """Tests for main function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cryomodule"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02"],
    )
    def test_main_success(self, mock_detune_cm, mock_tune_machine, mock_logger):
        """Test successful main execution."""
        mock_detune_cm.return_value = (8, 0)  # All successful

        mock_cm = Mock()
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 0
        mock_detune_cm.assert_called_once_with(mock_cm)

        # Verify logging
        assert mock_logger.info.called
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any(
            "Starting cryomodule detune script" in msg for msg in info_calls
        )
        assert any(
            "Detune cryomodule script completed" in msg for msg in info_calls
        )

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cryomodule"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02"],
    )
    def test_main_with_failures(
        self, mock_detune_cm, mock_tune_machine, mock_logger
    ):
        """Test main execution with some failures."""
        mock_detune_cm.return_value = (6, 2)  # Some failures

        mock_cm = Mock()
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        # Verify completion logging with failure count
        info_calls = mock_logger.info.call_args_list
        completion_call = info_calls[-1]

        # Verify the message
        assert "Detune cryomodule script completed" in completion_call[0][0]

        # The 'extra' parameter is passed as a kwarg to logger.info()
        # It contains a dict with 'extra_data' key
        assert "extra" in completion_call[1]
        extra_data = completion_call[1]["extra"]["extra_data"]
        assert extra_data["failed"] == 2
        assert extra_data["successful"] == 6
        assert extra_data["total"] == 8
        assert extra_data["cryomodule"] == "CM01"

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02"],
    )
    def test_main_cryomodule_not_found(self, mock_tune_machine, mock_logger):
        """Test main when cryomodule is not found."""
        mock_tune_machine.cryomodules = {}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "Could not find cryomodule" in error_call[0][0]

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01"],
    )
    def test_main_keyerror_handling(self, mock_tune_machine, mock_logger):
        """Test main handling of KeyError."""
        mock_tune_machine.cryomodules = {"CM02": Mock()}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        # Verify error was logged
        mock_logger.error.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01"],
    )
    def test_full_flow_success(
        self, mock_sleep, mock_tune_machine, mock_logger
    ):
        """Test full flow from main to cavity detuning."""
        # Setup cavities
        cavity1 = Mock()
        cavity1.script_is_running = False
        cavity1.__str__ = Mock(return_value="Cavity1")

        cavity2 = Mock()
        cavity2.script_is_running = False
        cavity2.__str__ = Mock(return_value="Cavity2")

        # Setup cryomodule
        mock_cm = Mock()
        mock_cm.__str__ = Mock(return_value="CM01")
        mock_cm.cavities = {"cav1": cavity1, "cav2": cavity2}
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 0
        cavity1.trigger_start.assert_called_once()
        cavity2.trigger_start.assert_called_once()

        # Verify appropriate logging occurred
        assert mock_logger.info.call_count >= 3  # start, 2 cavities, completion

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.logger"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01"],
    )
    def test_full_flow_with_running_cavity(
        self, mock_sleep, mock_tune_machine, mock_logger
    ):
        """Test full flow when one cavity is already running."""
        cavity1 = Mock()
        cavity1.script_is_running = True  # Already running
        cavity1.__str__ = Mock(return_value="Cavity1")

        cavity2 = Mock()
        cavity2.script_is_running = False
        cavity2.__str__ = Mock(return_value="Cavity2")

        mock_cm = Mock()
        mock_cm.__str__ = Mock(return_value="CM01")
        mock_cm.cavities = {"cav1": cavity1, "cav2": cavity2}
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1  # Should fail because one cavity didn't detune
        cavity1.trigger_start.assert_not_called()  # Shouldn't try if running
        cavity2.trigger_start.assert_called_once()

        # Should have warning for already running
        assert mock_logger.warning.calledv
