"""Tests for the SetupCavity class and its functionality."""

from random import randint
from unittest.mock import MagicMock, call

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import SetupCavity
from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    RF_MODE_SELA,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    HW_MODE_READY_VALUE,
    HW_MODE_ONLINE_VALUE,
)
from sc_linac_physics.utils.sc_linac.rfstation import RFStation
from sc_linac_physics.utils.sc_linac.ssa import SSA


@pytest.fixture
def cavity_number():
    """Generate a random cavity number for testing."""
    return randint(1, 8)


@pytest.fixture
def mock_rack(cavity_number):
    """Create a mock rack with appropriate configuration."""
    rack = MagicMock()
    rack.rack_name = "A" if cavity_number <= 4 else "B"
    rack.rfs1 = RFStation(num=1, rack_object=rack)
    rack.rfs2 = RFStation(num=2, rack_object=rack)
    return rack


@pytest.fixture
def cavity(cavity_number, mock_rack):
    """Create a SetupCavity instance with mocked dependencies.

    Returns:
        SetupCavity: A cavity instance with:
        - Mocked PVs
        - Configured SSA
        - Attached to mock rack
        - Basic monitoring PVs set up
    """
    cavity = SetupCavity(cavity_num=cavity_number, rack_object=mock_rack)
    cavity.ssa = SSA(cavity)

    # Set up common PVs that most tests need
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
    cavity._progress_pv_obj = make_mock_pv(get_val=0)
    cavity._status_msg_pv_obj = make_mock_pv(get_val="")
    cavity._abort_pv_obj = make_mock_pv(get_val=False)

    yield cavity


@pytest.fixture
def online_cavity(cavity):
    """Create a cavity that's in online mode."""
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    return cavity


@pytest.fixture
def running_cavity(cavity):
    """Create a cavity that's in running state."""
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)
    return cavity


class TestCavityStatus:
    """Tests for cavity status monitoring and basic state operations."""

    @pytest.mark.parametrize("status", [STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
    def test_status(self, cavity, status):
        """Test that cavity status is correctly reported."""
        cavity._status_pv_obj = make_mock_pv(get_val=status)
        assert cavity.status == status

    @pytest.mark.parametrize(
        "status,expected", [(STATUS_RUNNING_VALUE, True), (STATUS_READY_VALUE, False), (STATUS_ERROR_VALUE, False)]
    )
    def test_script_running_status(self, cavity, status, expected):
        """Test script_is_running property for different status values."""
        cavity._status_pv_obj = make_mock_pv(get_val=status)
        assert cavity.script_is_running == expected

    def test_capture_acon(self, cavity):
        """Test that ACON value is captured from ADES."""
        cavity._acon_pv_obj = make_mock_pv()
        ades = 16.6
        cavity._ades_pv_obj = make_mock_pv(get_val=ades)

        cavity.capture_acon()

        cavity._ades_pv_obj.get.assert_called_once()
        cavity._acon_pv_obj.put.assert_called_once_with(ades)

    def test_progress_reporting(self, cavity):
        """Test progress value reporting."""
        expected_progress = randint(0, 100)
        cavity._progress_pv_obj = make_mock_pv(get_val=expected_progress)

        assert cavity.progress == expected_progress

    def test_status_message(self, cavity):
        """Test status message reporting."""
        expected_message = "test status message"
        cavity._status_msg_pv_obj = make_mock_pv(get_val=expected_message)

        assert cavity.status_message == expected_message

    @pytest.mark.parametrize("initial_status", [STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
    def test_status_transitions(self, cavity, initial_status):
        """Test that status can transition between states."""
        cavity._status_pv_obj = make_mock_pv(get_val=initial_status)
        new_status = STATUS_ERROR_VALUE if initial_status != STATUS_ERROR_VALUE else STATUS_READY_VALUE

        cavity._status_pv_obj.put(new_status)
        cavity._status_pv_obj.get.return_value = new_status

        assert cavity.status == new_status


def test_progress(cavity):
    val = randint(0, 100)
    cavity._progress_pv_obj = make_mock_pv(get_val=val)
    assert val == cavity.progress


def test_status_message(cavity):
    tst_str = "this is a fake status"
    cavity._status_msg_pv_obj = make_mock_pv(get_val=tst_str)
    assert tst_str == cavity.status_message


class TestCavityAbortAndShutdown:
    """Tests for cavity abort and shutdown functionality."""

    def test_clear_abort(self, cavity):
        """Test that abort flag can be cleared."""
        cavity._abort_pv_obj = make_mock_pv()

        cavity.clear_abort()

        cavity._abort_pv_obj.put.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "status,should_abort", [(STATUS_READY_VALUE, False), (STATUS_RUNNING_VALUE, True), (STATUS_ERROR_VALUE, False)]
    )
    def test_request_abort(self, cavity, status, should_abort):
        """Test abort request handling in different states."""
        cavity._status_pv_obj = make_mock_pv(get_val=status)
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity._abort_pv_obj = make_mock_pv()

        cavity.trigger_abort()

        if should_abort:
            cavity._abort_pv_obj.put.assert_called_once()
        else:
            cavity._abort_pv_obj.put.assert_not_called()

        cavity._status_msg_pv_obj.put.assert_called_once()

    def test_check_abort_when_aborted(self, cavity):
        """Test that check_abort raises exception when abort is set."""
        cavity._abort_pv_obj = make_mock_pv(get_val=True)
        cavity.clear_abort = MagicMock()

        with pytest.raises(CavityAbortError):
            cavity.check_abort()

        cavity.clear_abort.assert_called_once()

    def test_check_abort_when_not_aborted(self, cavity):
        """Test that check_abort proceeds normally when no abort is set."""
        cavity._abort_pv_obj = make_mock_pv(get_val=False)
        cavity.clear_abort = MagicMock()

        cavity.check_abort()  # Should not raise
        cavity.clear_abort.assert_not_called()

    def test_shut_down_sequence(self, cavity):
        """Test the complete shutdown sequence."""
        # Setup
        cavity.clear_abort = MagicMock()
        cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity._progress_pv_obj = make_mock_pv()
        cavity.turn_off = MagicMock()
        cavity.ssa.turn_off = MagicMock()

        # Execute
        cavity.shut_down()

        # Verify all steps executed in correct order
        cavity._status_pv_obj.put.assert_has_calls([call(STATUS_RUNNING_VALUE), call(STATUS_READY_VALUE)])
        cavity._progress_pv_obj.put.assert_has_calls([call(0), call(50), call(100)])
        cavity.turn_off.assert_called_once()
        cavity.ssa.turn_off.assert_called_once()

    def test_shut_down_with_running_status(self, running_cavity):
        """Test shutdown behavior when cavity is running."""
        running_cavity.turn_off = MagicMock()
        running_cavity.ssa.turn_off = MagicMock()
        running_cavity._status_msg_pv_obj = make_mock_pv()

        running_cavity.shut_down()

        # Should not proceed with shutdown when script is running
        running_cavity.turn_off.assert_not_called()
        running_cavity.ssa.turn_off.assert_not_called()
        running_cavity._status_msg_pv_obj.put.assert_called_with(f"{running_cavity} script already running")


class TestSSACalibration:
    """Tests for SSA calibration functionality."""

    @pytest.fixture
    def setup_ssa_mocks(self, cavity):
        """Set up common mocks for SSA calibration tests."""
        cavity._progress_pv_obj = make_mock_pv()
        cavity.check_abort = MagicMock()
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity.turn_off = MagicMock()
        cavity.ssa.calibrate = MagicMock()
        cavity.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=100.0)
        cavity.rack.rfs1._dac_amp_pv_obj = make_mock_pv()
        cavity.rack.rfs2._dac_amp_pv_obj = make_mock_pv()
        return cavity

    def test_request_ssa_cal_when_not_requested(self, setup_ssa_mocks):
        """Test SSA calibration when not requested."""
        cavity = setup_ssa_mocks
        cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=False)

        cavity.request_ssa_cal()

        # Verify no calibration actions were taken
        cavity._ssa_cal_requested_pv_obj.get.assert_called_once()
        cavity.turn_off.assert_not_called()
        cavity.ssa.calibrate.assert_not_called()

        # Verify progress and abort checks still happen
        cavity._progress_pv_obj.put.assert_called_once()
        cavity.check_abort.assert_called_once()

    def test_request_ssa_cal_when_requested(self, setup_ssa_mocks):
        """Test full SSA calibration sequence."""
        cavity = setup_ssa_mocks
        cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=True)

        cavity.request_ssa_cal()

        # Verify calibration sequence
        cavity._ssa_cal_requested_pv_obj.get.assert_called_once()
        cavity.turn_off.assert_called_once()
        cavity.ssa.calibrate.assert_called_once()
        cavity.ssa._saved_drive_max_pv_obj.get.assert_called_once()

        # Verify RF station DAC updates
        cavity.rack.rfs2._dac_amp_pv_obj.put.assert_called_once()
        cavity.rack.rfs1._dac_amp_pv_obj.put.assert_called_once()

        # Verify progress updates and status
        assert cavity._status_msg_pv_obj.put.call_count >= 1
        assert cavity._progress_pv_obj.put.call_count >= 1
        cavity.check_abort.assert_called_once()

    def test_ssa_cal_with_abort(self, setup_ssa_mocks):
        """Test SSA calibration handling when abort is triggered."""
        cavity = setup_ssa_mocks
        cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=True)
        cavity.check_abort.side_effect = CavityAbortError("Test abort")

        with pytest.raises(CavityAbortError):
            cavity.request_ssa_cal()

        # Verify the expected error message was set last
        cavity._status_msg_pv_obj.put.assert_called_with("Test abort")

    @pytest.mark.parametrize("drive_max", [0.0, 50.0, 100.0])
    def test_ssa_cal_with_different_drive_levels(self, setup_ssa_mocks, drive_max):
        """Test SSA calibration with different drive maximum values."""
        cavity = setup_ssa_mocks
        cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=True)
        cavity.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=drive_max)

        cavity.request_ssa_cal()

        # DAC amp should be set to 0 during calibration
        cavity.rack.rfs1._dac_amp_pv_obj.put.assert_called_once_with(0)
        cavity.rack.rfs2._dac_amp_pv_obj.put.assert_called_once_with(0)


class TestAutoTuning:
    """Tests for cavity auto-tuning functionality."""

    @pytest.fixture
    def setup_tuning_mocks(self, cavity):
        """Set up common mocks for auto-tuning tests."""
        cavity.move_to_resonance = MagicMock()
        cavity._progress_pv_obj = make_mock_pv()
        cavity.check_abort = MagicMock()
        cavity._status_msg_pv_obj = make_mock_pv()
        return cavity

    def test_request_auto_tune_when_not_requested(self, setup_tuning_mocks):
        """Test auto-tuning behavior when not requested."""
        cavity = setup_tuning_mocks
        cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=False)

        cavity.request_auto_tune()

        # Verify no tuning was attempted
        cavity._auto_tune_requested_pv_obj.get.assert_called_once()
        cavity.move_to_resonance.assert_not_called()

        # Verify progress updates still happen
        cavity._progress_pv_obj.put.assert_called_once()
        cavity.check_abort.assert_called_once()

    def test_request_auto_tune_when_requested(self, setup_tuning_mocks):
        """Test auto-tuning sequence when requested."""
        cavity = setup_tuning_mocks
        cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)

        cavity.request_auto_tune()

        # Verify tuning sequence
        cavity._auto_tune_requested_pv_obj.get.assert_called_once()
        cavity.move_to_resonance.assert_called_once_with(use_sela=False)

        # Verify status updates and progress
        assert cavity._status_msg_pv_obj.put.call_count >= 1  # At least one status message
        cavity._progress_pv_obj.put.assert_called_once_with(50)  # Progress is set to 50
        cavity.check_abort.assert_called_once()

    def test_auto_tune_with_abort(self, setup_tuning_mocks):
        """Test auto-tuning handling when abort is triggered."""
        cavity = setup_tuning_mocks
        cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)
        cavity.check_abort.side_effect = CavityAbortError("Test abort")

        with pytest.raises(CavityAbortError):
            cavity.request_auto_tune()

        # Verify check_abort was called
        cavity.check_abort.assert_called_with()
        cavity.move_to_resonance.assert_not_called()

    @pytest.mark.parametrize("mode", [True, False])
    def test_auto_tune_sela_modes(self, setup_tuning_mocks, mode):
        """Test auto-tuning in different SELA modes."""
        cavity = setup_tuning_mocks
        cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)
        cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA if mode else 0)

        cavity.request_auto_tune()

        # Verify correct mode is used
        cavity.move_to_resonance.assert_called_once_with(use_sela=False)

    def test_auto_tune_progress_reporting(self, setup_tuning_mocks):
        """Test progress reporting during auto-tuning."""
        cavity = setup_tuning_mocks
        cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)

        cavity.request_auto_tune()

        # In auto_tune, only one progress update to 50 is expected
        cavity._progress_pv_obj.put.assert_called_once_with(50)


class TestCavityCharacterization:
    """Tests for cavity characterization functionality."""

    @pytest.fixture
    def setup_char_mocks(self, cavity):
        """Set up common mocks for characterization tests."""
        cavity._progress_pv_obj = make_mock_pv()
        cavity._abort_pv_obj = make_mock_pv()
        cavity.characterize = MagicMock()
        cavity._calc_probe_q_pv_obj = make_mock_pv()
        cavity._status_msg_pv_obj = make_mock_pv()

        # Mock check_abort but make it call through to real implementation
        real_check_abort = cavity.check_abort
        mock_check_abort = MagicMock(side_effect=real_check_abort)
        cavity.check_abort = mock_check_abort
        return cavity

    def test_request_characterization_when_not_requested(self, setup_char_mocks):
        """Test characterization behavior when not requested."""
        cavity = setup_char_mocks
        cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=False)

        cavity.request_characterization()

        # Verify no characterization was attempted
        assert cavity._cav_char_requested_pv_obj.get.call_count == 1
        cavity.characterize.assert_not_called()
        cavity._calc_probe_q_pv_obj.put.assert_not_called()

        # Verify progress updates still happen
        cavity._progress_pv_obj.put.assert_called_once()
        cavity.check_abort.assert_called_once()

    def test_request_characterization_when_requested(self, setup_char_mocks):
        """Test full characterization sequence when requested."""
        cavity = setup_char_mocks
        cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)

        cavity.request_characterization()

        # Verify characterization sequence
        cavity._cav_char_requested_pv_obj.get.assert_called()
        cavity.characterize.assert_called_once()
        cavity._calc_probe_q_pv_obj.put.assert_called_once()

        # Verify status updates
        assert cavity._status_msg_pv_obj.put.call_count >= 1
        assert cavity._progress_pv_obj.put.call_count >= 1
        cavity.check_abort.assert_called_once()

    def test_characterization_with_abort(self, setup_char_mocks):
        """Test characterization handling when abort is triggered."""
        cavity = setup_char_mocks
        cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)
        cavity._abort_pv_obj = make_mock_pv()
        cavity._abort_pv_obj.get.return_value = True  # Ensure abort_requested returns True

        with pytest.raises(CavityAbortError) as exc:
            cavity.request_characterization()

        assert str(exc.value) == f"Abort requested for {cavity}"
        cavity._status_msg_pv_obj.put.assert_called_with(f"Abort requested for {cavity}")
        cavity._abort_pv_obj.put.assert_called_once_with(0)  # Verify clear_abort was called
        cavity.characterize.assert_not_called()

    def test_characterization_error_handling(self, setup_char_mocks):
        """Test characterization error handling."""
        cavity = setup_char_mocks
        cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)
        test_error = Exception("Test error")
        cavity.characterize.side_effect = test_error

        with pytest.raises(Exception) as exc:
            cavity.request_characterization()

        # Verify that we got the same error
        assert exc.value == test_error

        # Verify error handling - only the first status message is set
        cavity._status_msg_pv_obj.put.assert_has_calls([call(f"Running {cavity} Cavity Characterization")])

    def test_probe_q_calculation(self, setup_char_mocks):
        """Test probe Q calculation during characterization."""
        cavity = setup_char_mocks
        cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)

        # Mock characterization to return Q values
        cavity.characterize.return_value = {"probe_q": 1e9}

        cavity.request_characterization()

        # Verify Q value flag is set
        cavity._calc_probe_q_pv_obj.put.assert_called_once_with(1)


class TestRFRamp:
    """Tests for RF ramping functionality."""

    @pytest.fixture
    def setup_ramp_mocks(self, cavity):
        """Set up common mocks for RF ramping tests."""
        cavity.piezo.enable_feedback = MagicMock()
        cavity._ades_pv_obj = make_mock_pv()
        cavity.turn_on = MagicMock()
        cavity.set_sela_mode = MagicMock()
        cavity.walk_amp = MagicMock()
        cavity.move_to_resonance = MagicMock()
        cavity.set_selap_mode = MagicMock()
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity._progress_pv_obj = make_mock_pv()
        cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
        cavity.check_abort = MagicMock()
        cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
        return cavity

    def test_request_ramp_when_not_requested(self, setup_ramp_mocks):
        """Test RF ramp behavior when not requested."""
        cavity = setup_ramp_mocks
        cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=False)

        cavity.request_ramp()

        # Verify no ramp operations occurred
        cavity._rf_ramp_requested_pv_obj.get.assert_called_once()
        cavity.piezo.enable_feedback.assert_not_called()
        cavity._ades_pv_obj.put.assert_not_called()
        cavity.turn_on.assert_not_called()
        cavity.set_sela_mode.assert_not_called()
        cavity.walk_amp.assert_not_called()
        cavity.move_to_resonance.assert_not_called()
        cavity.set_selap_mode.assert_not_called()

    @pytest.mark.parametrize("acon", [5.0, 13.0, 21.0])
    def test_request_ramp_when_requested(self, setup_ramp_mocks, acon):
        """Test full RF ramp sequence with different ACON values."""
        cavity = setup_ramp_mocks
        cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=True)
        cavity._acon_pv_obj = make_mock_pv(get_val=acon)

        # Replace get() with a side_effect to track real calls
        mock_get = MagicMock(return_value=acon)
        cavity._acon_pv_obj.get = mock_get

        cavity.request_ramp()

        # Verify ramp sequence
        assert cavity._rf_ramp_requested_pv_obj.get.call_count == 1
        cavity.piezo.enable_feedback.assert_called_once()
        cavity.turn_on.assert_called_once()
        cavity.set_sela_mode.assert_called_once()
        cavity.walk_amp.assert_called_once_with(acon, 0.1)
        cavity.move_to_resonance.assert_called_once_with(use_sela=True)
        cavity.set_selap_mode.assert_called_once()

    def test_ramp_with_abort(self, setup_ramp_mocks):
        """Test RF ramp handling when abort is triggered."""
        cavity = setup_ramp_mocks
        cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=True)
        cavity._acon_pv_obj = make_mock_pv(get_val=10.0)
        err_msg = f"Abort requested for {cavity}"
        cavity.check_abort.side_effect = CavityAbortError(err_msg)

        with pytest.raises(CavityAbortError) as exc:
            cavity.request_ramp()

        assert str(exc.value) == err_msg
        cavity._status_msg_pv_obj.put.assert_called_with(err_msg)


class TestCavitySetup:
    """Tests for the complete cavity setup sequence."""

    @pytest.fixture
    def setup_sequence_mocks(self, cavity):
        """Set up common mocks for setup sequence tests."""
        cavity.request_ssa_cal = MagicMock()
        cavity.request_auto_tune = MagicMock()
        cavity.request_characterization = MagicMock()
        cavity.request_ramp = MagicMock()
        cavity.clear_abort = MagicMock()
        cavity.turn_off = MagicMock()
        cavity.ssa.turn_on = MagicMock()
        cavity.reset_interlocks = MagicMock()
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity._progress_pv_obj = make_mock_pv()
        return cavity

    def test_setup_when_already_running(self, setup_sequence_mocks):
        """Test setup behavior when cavity is already running."""
        cavity = setup_sequence_mocks
        cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)

        cavity.setup()

        # Verify no setup operations occurred
        cavity.request_ssa_cal.assert_not_called()
        cavity.request_auto_tune.assert_not_called()
        cavity.request_characterization.assert_not_called()
        cavity.request_ramp.assert_not_called()

    @pytest.mark.parametrize(
        "hw_mode", [HW_MODE_MAINTENANCE_VALUE, HW_MODE_OFFLINE_VALUE, HW_MODE_MAIN_DONE_VALUE, HW_MODE_READY_VALUE]
    )
    def test_setup_in_invalid_mode(self, setup_sequence_mocks, hw_mode):
        """Test setup behavior in various invalid hardware modes."""
        cavity = setup_sequence_mocks
        cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        cavity._hw_mode_pv_obj = make_mock_pv(get_val=hw_mode)

        cavity.setup()

        # Verify error state is set
        cavity._status_pv_obj.put.assert_called_with(STATUS_ERROR_VALUE)
        cavity.request_ssa_cal.assert_not_called()

    def test_complete_setup_sequence(self, setup_sequence_mocks):
        """Test complete successful setup sequence."""
        cavity = setup_sequence_mocks
        cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)

        cavity.setup()

        # Verify initialization
        cavity.clear_abort.assert_called_once()
        cavity.turn_off.assert_called_once()
        cavity.ssa.turn_on.assert_called_once()
        cavity.reset_interlocks.assert_called_once()

        # Verify setup sequence
        cavity.request_ssa_cal.assert_called_once()
        cavity.request_auto_tune.assert_called_once()
        cavity.request_characterization.assert_called_once()
        cavity.request_ramp.assert_called_once()

        # Verify completion
        cavity._status_pv_obj.put.assert_called_with(STATUS_READY_VALUE)
        cavity._progress_pv_obj.put.assert_called_with(100)

    def test_setup_with_error(self, setup_sequence_mocks):
        """Test setup error handling."""
        cavity = setup_sequence_mocks
        cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        cavity.request_ssa_cal.side_effect = Exception("Test error")

        cavity.setup()

        # Verify error handling
        cavity._status_pv_obj.put.assert_called_with(STATUS_ERROR_VALUE)
        cavity._status_msg_pv_obj.put.assert_called_with("Test error")
