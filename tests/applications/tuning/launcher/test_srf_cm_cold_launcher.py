from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher import (
    detune_cavity,
    detune_cryomodule,
    parse_args,
    main,
    DEFAULT_SLEEP_INTERVAL,
)


class TestDetuneCavity:
    """Tests for detune_cavity function."""

    def test_detune_cavity_success(self, capsys):
        """Test successful cavity detuning."""
        cavity = Mock()
        cavity.script_is_running = False
        cavity.__str__ = Mock(return_value="Cavity1")

        result = detune_cavity(cavity)

        assert result is True
        cavity.trigger_start.assert_called_once()

        captured = capsys.readouterr()
        assert "Triggered detuning for Cavity1" in captured.out

    def test_detune_cavity_already_running(self, capsys):
        """Test detuning when script is already running."""
        cavity = Mock()
        cavity.script_is_running = True
        cavity.__str__ = Mock(return_value="Cavity1")

        result = detune_cavity(cavity)

        assert result is False
        cavity.trigger_start.assert_not_called()

        captured = capsys.readouterr()
        assert "Warning: Cavity1 script already running" in captured.err

    def test_detune_cavity_exception(self, capsys):
        """Test handling of exception during trigger_start."""
        cavity = Mock()
        cavity.script_is_running = False
        cavity.__str__ = Mock(return_value="Cavity1")
        cavity.trigger_start.side_effect = Exception("Test error")

        result = detune_cavity(cavity)

        assert result is False

        captured = capsys.readouterr()
        assert "Error triggering Cavity1: Test error" in captured.err


class TestDetuneCryomodule:
    """Tests for detune_cryomodule function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_all_success(self, mock_detune, mock_sleep):
        """Test detuning all cavities successfully."""
        mock_detune.return_value = True

        cryomodule = Mock()
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

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_mixed_results(self, mock_detune, mock_sleep):
        """Test detuning with some successes and failures."""
        mock_detune.side_effect = [True, False, True, False]

        cryomodule = Mock()
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
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.sleep"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cavity"
    )
    def test_detune_cryomodule_empty(self, mock_detune, mock_sleep):
        """Test detuning cryomodule with no cavities."""
        cryomodule = Mock()
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
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.detune_cryomodule"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02"],
    )
    def test_main_success(self, mock_detune_cm, mock_tune_machine, capsys):
        """Test successful main execution."""
        mock_detune_cm.return_value = (8, 0)  # All successful

        mock_cm = Mock()
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 0
        mock_detune_cm.assert_called_once_with(mock_cm)

        captured = capsys.readouterr()
        assert "Detuning cryomodule CM01" in captured.out
        assert "Completed: 8 successful, 0 failed" in captured.out

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
        self, mock_detune_cm, mock_tune_machine, capsys
    ):
        """Test main execution with some failures."""
        mock_detune_cm.return_value = (6, 2)  # Some failures

        mock_cm = Mock()
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Completed: 6 successful, 2 failed" in captured.out

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01", "CM02"],
    )
    def test_main_cryomodule_not_found(self, mock_tune_machine, capsys):
        """Test main when cryomodule is not found."""
        mock_tune_machine.cryomodules = {}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Error: Could not find cryomodule CM01" in captured.err

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_cm_cold_launcher.ALL_CRYOMODULES",
        ["CM01"],
    )
    def test_main_keyerror_handling(self, mock_tune_machine, capsys):
        """Test main handling of KeyError."""
        mock_tune_machine.cryomodules = {"CM02": Mock()}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Error: Could not find cryomodule" in captured.err


class TestIntegration:
    """Integration tests combining multiple components."""

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
    def test_full_flow_success(self, mock_sleep, mock_tune_machine, capsys):
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
        mock_cm.cavities = {"cav1": cavity1, "cav2": cavity2}
        mock_tune_machine.cryomodules = {"CM01": mock_cm}

        exit_code = main(["--cryomodule", "CM01"])

        assert exit_code == 0
        cavity1.trigger_start.assert_called_once()
        cavity2.trigger_start.assert_called_once()

        captured = capsys.readouterr()
        assert "Triggered detuning for Cavity1" in captured.out
        assert "Triggered detuning for Cavity2" in captured.out
        assert "Completed: 2 successful, 0 failed" in captured.out
