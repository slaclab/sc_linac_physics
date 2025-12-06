# "test_srf_rack_cold_launcher.py"
from unittest.mock import MagicMock, patch, Mock

import pytest

from sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher import (
    detune_cavity,
    detune_rack,
    get_rack,
    parse_args,
    main,
    DEFAULT_SLEEP_INTERVAL,
)
from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError


@pytest.fixture
def mock_cavity():
    """Create a mock TuneCavity object."""
    cavity = MagicMock()
    cavity.script_is_running = False
    cavity.__str__.return_value = "01-Cavity-1"
    return cavity


@pytest.fixture
def mock_rack():
    """Create a mock TuneRack with 8 cavities."""
    rack = MagicMock()
    rack.cavities = {
        f"cav{i}": MagicMock(__str__=Mock(return_value=f"Cavity-{i}"))
        for i in range(1, 9)
    }
    for cav in rack.cavities.values():
        cav.script_is_running = False
    rack.__str__.return_value = "01-Rack-A"
    return rack


@pytest.fixture
def mock_cryomodule():
    """Create a mock Cryomodule object."""
    cm = MagicMock()
    cm.rack_a = MagicMock(__str__=Mock(return_value="Rack-A"))
    cm.rack_b = MagicMock(__str__=Mock(return_value="Rack-B"))
    return cm


class TestDetuneCavity:
    """Tests for detune_cavity function."""

    def test_success(self, mock_cavity):
        """Test successful cavity detuning."""
        assert detune_cavity(mock_cavity) is True
        mock_cavity.trigger_start.assert_called_once()

    def test_already_running(self, mock_cavity):
        """Test when script is already running."""
        mock_cavity.script_is_running = True
        assert detune_cavity(mock_cavity) is False
        mock_cavity.trigger_start.assert_not_called()

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.logger"
    )
    def test_cavity_abort_error(self, mock_logger, mock_cavity):
        """Test handling of CavityAbortError."""
        mock_cavity.trigger_start.side_effect = CavityAbortError("Abort")
        detune_cavity(mock_cavity)
        mock_logger.error.assert_called_once()

    def test_generic_exception(self, mock_cavity):
        """Test handling of generic exceptions."""
        mock_cavity.trigger_start.side_effect = RuntimeError("Error")
        assert detune_cavity(mock_cavity) is False


class TestDetuneRack:
    """Tests for detune_rack function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_cavity"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.sleep"
    )
    def test_all_successful(self, mock_sleep, mock_detune, mock_rack):
        """Test all cavities detune successfully."""
        mock_detune.return_value = True

        successful, failed = detune_rack(mock_rack)

        assert successful == 8
        assert failed == 0
        assert mock_detune.call_count == 8
        assert mock_sleep.call_count == 8

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_cavity"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.sleep"
    )
    def test_mixed_results(self, mock_sleep, mock_detune, mock_rack):
        """Test with some successes and failures."""
        mock_detune.side_effect = [
            True,
            False,
            True,
            False,
            True,
            False,
            True,
            False,
        ]

        successful, failed = detune_rack(mock_rack)

        assert successful == 4
        assert failed == 4

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_cavity"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.sleep"
    )
    def test_custom_sleep_interval(self, mock_sleep, mock_detune, mock_rack):
        """Test custom sleep interval is used."""
        mock_detune.return_value = True

        detune_rack(mock_rack, sleep_interval=0.5)

        for call_args in mock_sleep.call_args_list:
            assert call_args[0][0] == 0.5

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_cavity"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.sleep"
    )
    def test_empty_rack(self, mock_sleep, mock_detune):
        """Test with empty rack."""
        rack = MagicMock()
        rack.cavities = {}
        rack.__str__.return_value = "Empty-Rack"

        successful, failed = detune_rack(rack)

        assert successful == 0
        assert failed == 0
        mock_detune.assert_not_called()


class TestGetRack:
    """Tests for get_rack function."""

    def test_get_rack_a(self, mock_cryomodule):
        """Test getting rack A."""
        assert get_rack(mock_cryomodule, "A") == mock_cryomodule.rack_a

    def test_get_rack_b(self, mock_cryomodule):
        """Test getting rack B."""
        assert get_rack(mock_cryomodule, "B") == mock_cryomodule.rack_b


class TestParseArgs:
    """Tests for parse_args function."""

    def test_minimal_args(self):
        """Test parsing minimal required arguments."""
        args = parse_args(["--cryomodule", "01", "--rack", "A"])

        assert args.cryomodule == "01"
        assert args.rack == "A"
        assert args.sleep_interval == DEFAULT_SLEEP_INTERVAL

    def test_with_custom_sleep(self):
        """Test with custom sleep interval."""
        args = parse_args(["-cm", "02", "-r", "B", "-s", "0.5"])

        assert args.cryomodule == "02"
        assert args.rack == "B"
        assert args.sleep_interval == 0.5

    def test_missing_required_args(self):
        """Test that missing required args raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--cryomodule", "01"])

    def test_invalid_rack(self):
        """Test invalid rack choice."""
        with pytest.raises(SystemExit):
            parse_args(["--cryomodule", "01", "--rack", "C"])


class TestMain:
    """Tests for main function."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_rack"
    )
    def test_success(self, mock_detune_rack, mock_machine, mock_cryomodule):
        """Test successful execution."""
        mock_machine.cryomodules = {"01": mock_cryomodule}
        mock_detune_rack.return_value = (8, 0)

        exit_code = main(["--cryomodule", "01", "--rack", "A"])

        assert exit_code == 0
        mock_detune_rack.assert_called_once()

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_rack"
    )
    def test_with_failures(
        self, mock_detune_rack, mock_machine, mock_cryomodule
    ):
        """Test execution with some failures."""
        mock_machine.cryomodules = {"01": mock_cryomodule}
        mock_detune_rack.return_value = (6, 2)

        exit_code = main(["--cryomodule", "01", "--rack", "B"])

        assert exit_code == 1

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.TUNE_MACHINE"
    )
    def test_cryomodule_not_found(self, mock_machine):
        """Test when cryomodule doesn't exist."""
        mock_machine.cryomodules = {}

        exit_code = main(["--cryomodule", "35", "--rack", "A"])

        assert exit_code == 1

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.detune_rack"
    )
    def test_custom_sleep_passed_through(
        self, mock_detune_rack, mock_machine, mock_cryomodule
    ):
        """Test that custom sleep interval is passed to detune_rack."""
        mock_machine.cryomodules = {"01": mock_cryomodule}
        mock_detune_rack.return_value = (8, 0)

        main(["--cryomodule", "01", "--rack", "A", "--sleep-interval", "2.0"])

        # detune_rack is called with positional args: detune_rack(rack_obj, sleep_interval)
        call_args = mock_detune_rack.call_args[0]
        assert call_args[1] == 2.0


class TestIntegration:
    """Integration tests."""

    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.TUNE_MACHINE"
    )
    @patch(
        "sc_linac_physics.applications.tuning.launcher.srf_rack_cold_launcher.sleep"
    )
    def test_full_workflow(self, mock_sleep, mock_machine):
        """Test complete workflow from main to cavity detuning."""
        # Setup
        mock_cm = MagicMock()
        mock_rack_a = MagicMock()
        cavities = {}
        for i in range(1, 5):
            cav = MagicMock()
            cav.script_is_running = False
            cav.__str__.return_value = f"Cavity-{i}"
            cavities[f"cav{i}"] = cav

        mock_rack_a.cavities = cavities
        mock_cm.rack_a = mock_rack_a
        mock_cm.rack_b = MagicMock()
        mock_machine.cryomodules = {"01": mock_cm}

        # Execute
        exit_code = main(["--cryomodule", "01", "--rack", "A"])

        # Verify
        assert exit_code == 0
        for cav in cavities.values():
            cav.trigger_start.assert_called_once()
