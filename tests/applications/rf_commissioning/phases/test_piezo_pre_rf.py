"""
Tests for Piezo Pre-RF Phase
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.data_models import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_pre_rf import (
    PiezoPreRFPhase,
    PiezoTestLimits,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    PIEZO_PRE_RF_CHECKOUT_PASS_VALUE,
    PIEZO_SCRIPT_RUNNING_VALUE,
)


@pytest.fixture
def mock_cavity():
    """Create a mock cavity with CommissioningPiezo."""
    cavity = Mock()
    cavity.piezo = Mock(spec=CommissioningPiezo)
    cavity.__str__ = Mock(return_value="CM02_CAV1")
    return cavity


@pytest.fixture
def mock_piezo_pvs(mock_cavity):
    """Setup mock PV objects for piezo testing."""
    piezo = mock_cavity.piezo

    # Initial state PVs
    piezo.prerf_test_status_pv_obj = Mock()
    piezo.prerf_cha_status_pv_obj = Mock()
    piezo.prerf_chb_status_pv_obj = Mock()

    # Test control PVs
    piezo.prerf_test_start_pv_obj = Mock()

    # Result PVs
    piezo.prerf_cha_testmsg_pv_obj = Mock()
    piezo.prerf_chb_testmsg_pv_obj = Mock()
    piezo.capacitance_a_pv_obj = Mock()
    piezo.capacitance_b_pv_obj = Mock()

    return piezo


@pytest.fixture
def commissioning_record(mock_cavity):
    """Create a commissioning record."""
    return CommissioningRecord(
        cavity_name=str(mock_cavity),
        cryomodule="CM02",
    )


@pytest.fixture
def context(mock_cavity, commissioning_record):
    """Create phase context."""
    return PhaseContext(
        record=commissioning_record,
        operator="test_operator",
        dry_run=False,
        parameters={"cavity": mock_cavity},
    )


@pytest.fixture
def phase(context):
    """Create phase with short timeout for testing."""
    return PiezoPreRFPhase(
        context=context,
        limits=PiezoTestLimits(
            test_timeout=5.0,
            poll_interval=0.1,
        ),
    )


class TestPiezoPreRFPhase:
    """Test suite for PiezoPreRFPhase."""

    def test_phase_type(self, phase):
        """Test that phase type is correct."""
        assert phase.phase_type == CommissioningPhase.PIEZO_PRE_RF

    def test_prerequisite_validation_success(self, phase, mock_cavity):
        """Test successful prerequisite validation."""
        is_valid, message = phase.validate_prerequisites()

        assert is_valid
        assert "validated" in message.lower()
        assert phase.cavity is mock_cavity

    def test_prerequisite_validation_no_cavity(self, context):
        """Test prerequisite validation fails when no cavity."""
        context.parameters.pop("cavity")
        phase = PiezoPreRFPhase(context)

        is_valid, message = phase.validate_prerequisites()

        assert not is_valid
        assert "no cavity" in message.lower()

    def test_prerequisite_validation_wrong_piezo_type(self, context):
        """Test prerequisite validation fails with wrong piezo type."""
        # Replace with non-CommissioningPiezo
        context.parameters["cavity"].piezo = Mock()
        phase = PiezoPreRFPhase(context)

        is_valid, message = phase.validate_prerequisites()

        assert not is_valid
        assert "CommissioningPiezo" in message

    def test_get_phase_steps(self, phase):
        """Test that phase steps are returned in correct order."""
        steps = phase.get_phase_steps()

        assert len(steps) == 4
        assert steps[0] == "verify_initial_state"
        assert steps[1] == "trigger_prerf_test"
        assert steps[2] == "wait_for_completion"
        assert steps[3] == "validate_results"

    def test_successful_run(self, phase, mock_piezo_pvs):
        """Test successful complete phase run."""
        # Setup successful test scenario
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
            0,  # Initial: not running
            PIEZO_SCRIPT_RUNNING_VALUE,  # After start: running
            PIEZO_SCRIPT_RUNNING_VALUE,  # Still running
            0,  # Completed
        ]

        # Both channels pass
        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )

        # Messages
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"

        # Capacitance values
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # Run phase
        success = phase.run()

        # Verify results
        assert success
        assert (
            phase.context.record.phase_status[CommissioningPhase.PIEZO_PRE_RF]
            == PhaseStatus.COMPLETE
        )

        # Verify test was triggered
        mock_piezo_pvs.prerf_test_start_pv_obj.put.assert_called_once_with(1)

        # Verify data was saved
        assert phase.context.record.piezo_pre_rf is not None
        assert phase.context.record.piezo_pre_rf.channel_a_passed
        assert phase.context.record.piezo_pre_rf.channel_b_passed

    def test_verify_initial_state_success(self, phase, mock_piezo_pvs):
        """Test verify_initial_state step success."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = 0
        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = 0
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = 0

        result = phase.execute_step("verify_initial_state")

        assert result.result == PhaseResult.SUCCESS
        assert "ready" in result.message.lower()

    def test_verify_initial_state_already_running(self, phase, mock_piezo_pvs):
        """Test verify_initial_state fails when test already running."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = (
            PIEZO_SCRIPT_RUNNING_VALUE
        )

        result = phase.execute_step("verify_initial_state")

        assert result.result == PhaseResult.FAILED
        assert "already in progress" in result.message.lower()

    def test_trigger_prerf_test_success(self, phase, mock_piezo_pvs):
        """Test trigger_prerf_test step success."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = (
            PIEZO_SCRIPT_RUNNING_VALUE
        )

        result = phase.execute_step("trigger_prerf_test")

        assert result.result == PhaseResult.SUCCESS
        assert "started successfully" in result.message.lower()
        mock_piezo_pvs.prerf_test_start_pv_obj.put.assert_called_once_with(1)

    def test_trigger_prerf_test_dry_run(self, phase, mock_piezo_pvs):
        """Test trigger_prerf_test in dry run mode."""
        phase.context.dry_run = True
        phase.validate_prerequisites()

        result = phase.execute_step("trigger_prerf_test")

        assert result.result == PhaseResult.SUCCESS
        assert "DRY RUN" in result.message
        mock_piezo_pvs.prerf_test_start_pv_obj.put.assert_not_called()

    def test_trigger_prerf_test_fails_to_start(self, phase, mock_piezo_pvs):
        """Test trigger_prerf_test fails when test doesn't start."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = (
            0  # Still not running
        )

        result = phase.execute_step("trigger_prerf_test")

        assert result.result == PhaseResult.FAILED
        assert "failed to start" in result.message.lower()

    def test_wait_for_completion_success(self, phase, mock_piezo_pvs):
        """Test wait_for_completion step success."""
        phase.validate_prerequisites()

        # Simulate test running then completing
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
            PIEZO_SCRIPT_RUNNING_VALUE,
            PIEZO_SCRIPT_RUNNING_VALUE,
            0,  # Completed
        ]

        result = phase.execute_step("wait_for_completion")

        assert result.result == PhaseResult.SUCCESS
        assert "completed" in result.message.lower()
        assert "elapsed_time" in result.data

    def test_wait_for_completion_timeout(self, phase, mock_piezo_pvs):
        """Test wait_for_completion timeout."""
        phase.validate_prerequisites()

        # Test never completes
        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = (
            PIEZO_SCRIPT_RUNNING_VALUE
        )

        result = phase.execute_step("wait_for_completion")

        assert result.result == PhaseResult.FAILED
        assert "timeout" in result.message.lower()

    def test_wait_for_completion_abort(self, phase, mock_piezo_pvs):
        """Test wait_for_completion handles abort request."""
        phase.validate_prerequisites()

        # Request abort
        phase.context.request_abort()

        mock_piezo_pvs.prerf_test_status_pv_obj.get.return_value = (
            PIEZO_SCRIPT_RUNNING_VALUE
        )

        result = phase.execute_step("wait_for_completion")

        assert result.result == PhaseResult.FAILED
        assert "aborted" in result.message.lower()

    def test_validate_results_success(self, phase, mock_piezo_pvs):
        """Test validate_results step with passing results."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        result = phase.execute_step("validate_results")

        assert result.result == PhaseResult.SUCCESS
        assert "passed" in result.message.lower()
        assert (
            result.data["channel_a_status"] == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        assert (
            result.data["channel_b_status"] == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        assert result.data["capacitance_a_nf"] == 25.3
        assert result.data["capacitance_b_nf"] == 24.8

    def test_validate_results_channel_a_fails(self, phase, mock_piezo_pvs):
        """Test validate_results with Channel A failure."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = 1  # Not pass
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = (
            "Low capacitance"
        )
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 5.2
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        result = phase.execute_step("validate_results")

        assert result.result == PhaseResult.FAILED
        assert "Channel A failed" in result.message
        assert "Low capacitance" in result.message

    def test_validate_results_channel_b_fails(self, phase, mock_piezo_pvs):
        """Test validate_results with Channel B failure."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = 2  # Not pass
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = (
            "Connection error"
        )
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 0.0

        result = phase.execute_step("validate_results")

        assert result.result == PhaseResult.FAILED
        assert "Channel B failed" in result.message
        assert "Connection error" in result.message

    def test_validate_results_both_channels_fail(self, phase, mock_piezo_pvs):
        """Test validate_results with both channels failing."""
        phase.validate_prerequisites()

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = 1
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = 2
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "Error A"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "Error B"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 0.0
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 0.0

        result = phase.execute_step("validate_results")

        assert result.result == PhaseResult.FAILED
        assert "Channel A failed" in result.message
        assert "Channel B failed" in result.message

    def test_execute_step_unknown_step(self, phase):
        """Test execute_step with unknown step name."""
        phase.validate_prerequisites()

        result = phase.execute_step("unknown_step")

        assert result.result == PhaseResult.FAILED
        assert "Unknown step" in result.message

    def test_execute_step_without_prerequisite_validation(self, context):
        """Test execute_step fails without prerequisite validation."""
        phase = PiezoPreRFPhase(context)

        with pytest.raises(Exception):  # PhaseExecutionError
            phase.execute_step("verify_initial_state")

    def test_finalize_phase(self, phase, mock_piezo_pvs):
        """Test finalize_phase saves data correctly."""
        phase.validate_prerequisites()

        # Setup validation data
        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # Execute validation step to create checkpoint
        result = phase.execute_step("validate_results")

        # Create checkpoint manually (normally done by run())
        from sc_linac_physics.applications.rf_commissioning.data_models import (
            PhaseCheckpoint,
        )

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.PIEZO_PRE_RF,
            timestamp=datetime.now(),
            operator="test_operator",
            step_name="validate_results",
            success=True,
            measurements=result.data,
        )
        phase.context.record.phase_history.append(checkpoint)

        # Finalize phase
        phase.finalize_phase()

        # Verify data was saved
        assert phase.context.record.piezo_pre_rf is not None
        piezo_result = phase.context.record.piezo_pre_rf

        assert piezo_result.channel_a_passed
        assert piezo_result.channel_b_passed
        assert (
            abs(piezo_result.capacitance_a - 25.3e-9) < 1e-12
        )  # Check nF to F conversion
        assert abs(piezo_result.capacitance_b - 24.8e-9) < 1e-12

    def test_custom_limits(self, context):
        """Test phase with custom test limits."""
        custom_limits = PiezoTestLimits(
            test_timeout=60.0,
            poll_interval=1.0,
        )
        phase = PiezoPreRFPhase(context=context, limits=custom_limits)

        assert phase.limits.test_timeout == 60.0
        assert phase.limits.poll_interval == 1.0

    def test_default_limits(self, context):
        """Test phase with default limits."""
        phase = PiezoPreRFPhase(context=context)

        assert phase.limits.test_timeout == 30.0
        assert phase.limits.poll_interval == 0.5

    def test_phase_name(self, phase):
        """Test human-readable phase name."""
        assert phase.phase_name == "Piezo Pre Rf"

    def test_full_run_creates_checkpoints(self, phase, mock_piezo_pvs):
        """Test that full run creates appropriate checkpoints."""
        # Setup successful test scenario
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
            0,  # Initial: not running
            PIEZO_SCRIPT_RUNNING_VALUE,  # After start: running
            PIEZO_SCRIPT_RUNNING_VALUE,  # Still running
            0,  # Completed
        ]

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # Run phase
        success = phase.run()

        assert success

        # Check checkpoints were created
        checkpoints = phase.context.record.phase_history
        assert len(checkpoints) > 0

        # Find specific checkpoints
        checkpoint_names = [cp.step_name for cp in checkpoints]
        assert "phase_start" in checkpoint_names
        assert "verify_initial_state" in checkpoint_names
        assert "trigger_prerf_test" in checkpoint_names
        assert "wait_for_completion" in checkpoint_names
        assert "validate_results" in checkpoint_names
        assert "phase_complete" in checkpoint_names

        # Verify all successful
        for cp in checkpoints:
            assert cp.success

    def test_failed_run_marks_phase_failed(self, phase, mock_piezo_pvs):
        """Test that failed run marks phase as failed."""
        # Setup failure scenario - channel A fails
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
            0,  # Initial
            PIEZO_SCRIPT_RUNNING_VALUE,  # Running
            0,  # Completed
        ]

        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = 1  # Failed
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "Error"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 0.0
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # Run phase
        success = phase.run()

        assert not success
        assert (
            phase.context.record.phase_status[CommissioningPhase.PIEZO_PRE_RF]
            == PhaseStatus.FAILED
        )

    def test_pv_read_error_handling(self, phase, mock_piezo_pvs):
        """Test handling of PV read errors."""
        phase.validate_prerequisites()

        # Simulate PV error
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = Exception(
            "PV timeout"
        )

        result = phase.execute_step("verify_initial_state")

        assert result.result == PhaseResult.FAILED
        assert "Failed to verify" in result.message

    def test_multiple_runs_with_fresh_context(
        self, mock_cavity, mock_piezo_pvs
    ):
        """Test that phase can be run multiple times with fresh contexts."""

        # Setup successful scenario
        def setup_success():
            mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
                0,  # Initial
                PIEZO_SCRIPT_RUNNING_VALUE,  # Running
                PIEZO_SCRIPT_RUNNING_VALUE,
                0,  # Complete
            ]
            mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
                PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
            )
            mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
                PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
            )
            mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
            mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
            mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
            mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # First run with first record
        setup_success()
        record1 = CommissioningRecord(
            cavity_name="CM02_CAV1", cryomodule="CM02"
        )
        context1 = PhaseContext(
            record=record1,
            operator="test_operator",
            dry_run=False,
            parameters={"cavity": mock_cavity},
        )
        phase1 = PiezoPreRFPhase(
            context=context1,
            limits=PiezoTestLimits(test_timeout=5.0, poll_interval=0.1),
        )
        success1 = phase1.run()
        assert success1
        assert record1.piezo_pre_rf is not None

        # Second run with second record (simulating different cavity)
        setup_success()
        record2 = CommissioningRecord(
            cavity_name="CM02_CAV2", cryomodule="CM02"
        )
        context2 = PhaseContext(
            record=record2,
            operator="test_operator",
            dry_run=False,
            parameters={"cavity": mock_cavity},
        )
        phase2 = PiezoPreRFPhase(
            context=context2,
            limits=PiezoTestLimits(test_timeout=5.0, poll_interval=0.1),
        )
        success2 = phase2.run()
        assert success2
        assert record2.piezo_pre_rf is not None

        # Both should have triggered the test
        assert mock_piezo_pvs.prerf_test_start_pv_obj.put.call_count == 2

    def test_integration_with_commissioning_record(self, phase, mock_piezo_pvs):
        """Test full integration with commissioning record tracking."""
        # Setup successful scenario
        mock_piezo_pvs.prerf_test_status_pv_obj.get.side_effect = [
            0,
            PIEZO_SCRIPT_RUNNING_VALUE,
            PIEZO_SCRIPT_RUNNING_VALUE,
            0,
        ]
        mock_piezo_pvs.prerf_cha_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_chb_status_pv_obj.get.return_value = (
            PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
        )
        mock_piezo_pvs.prerf_cha_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.prerf_chb_testmsg_pv_obj.get.return_value = "OK"
        mock_piezo_pvs.capacitance_a_pv_obj.get.return_value = 25.3
        mock_piezo_pvs.capacitance_b_pv_obj.get.return_value = 24.8

        # Verify initial state
        record = phase.context.record
        assert record.piezo_pre_rf is None
        assert (
            record.phase_status[CommissioningPhase.PIEZO_PRE_RF]
            == PhaseStatus.NOT_STARTED
        )

        # Run phase
        success = phase.run()
        assert success

        # Verify final state
        assert record.piezo_pre_rf is not None
        assert record.piezo_pre_rf.passed
        assert (
            record.phase_status[CommissioningPhase.PIEZO_PRE_RF]
            == PhaseStatus.COMPLETE
        )
        assert record.current_phase == CommissioningPhase.PIEZO_PRE_RF

        # Verify checkpoint history
        piezo_checkpoints = [
            cp
            for cp in record.phase_history
            if cp.phase == CommissioningPhase.PIEZO_PRE_RF
        ]
        assert len(piezo_checkpoints) > 0

        # Verify can serialize record
        record_dict = record.to_dict()
        assert "piezo_pre_rf" in record_dict
        assert record_dict["piezo_pre_rf"]["passed"]
