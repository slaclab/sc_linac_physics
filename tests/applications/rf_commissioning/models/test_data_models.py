"""Tests for RF commissioning data models."""

from datetime import datetime, timedelta

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    ColdLandingData,
    CommissioningPhase,
    CommissioningRecord,
    HighPowerRampData,
    PHASE_REGISTRY,
    PhaseCheckpoint,
    PhaseStatus,
    PiezoPreRFCheck,
    PiezoWithRFTest,
    PiModeMeasurement,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    deserialize_model,
    get_phase_display_specs,
    serialize_model,
)


class TestCommissioningPhase:
    """Tests for phase ordering and navigation helpers."""

    def test_get_phase_order_matches_expected_sequence(self):
        expected_order = [
            CommissioningPhase.PIEZO_PRE_RF,
            CommissioningPhase.SSA_CHAR,
            CommissioningPhase.COLD_LANDING,
            CommissioningPhase.PI_MODE,
            CommissioningPhase.CAVITY_CHAR,
            CommissioningPhase.PIEZO_WITH_RF,
            CommissioningPhase.HIGH_POWER,
            CommissioningPhase.COMPLETE,
        ]

        assert CommissioningPhase.get_phase_order() == expected_order

    def test_next_and_previous_phase_navigation(self):
        assert (
            CommissioningPhase.PIEZO_PRE_RF.get_next_phase()
            == CommissioningPhase.SSA_CHAR
        )
        assert (
            CommissioningPhase.SSA_CHAR.get_previous_phase()
            == CommissioningPhase.PIEZO_PRE_RF
        )
        assert CommissioningPhase.PIEZO_PRE_RF.get_previous_phase() is None
        assert CommissioningPhase.COMPLETE.get_next_phase() is None


class TestPhaseModels:
    """Tests for phase dataclasses and computed properties."""

    def test_piezo_pre_rf_conversions_and_status(self):
        model = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

        assert model.capacitance_a_nf == pytest.approx(1.5)
        assert model.capacitance_b_nf == pytest.approx(1.6)
        assert model.passed is True
        assert "PASS" in model.status_description

    def test_cold_landing_computed_properties(self):
        model = ColdLandingData(
            initial_detune_hz=12_500.0,
            steps_to_resonance=44,
            final_detune_hz=300.0,
        )

        assert model.initial_detune_khz == pytest.approx(12.5)
        assert model.final_detune_khz == pytest.approx(0.3)
        assert model.is_complete is True

    def test_ssa_characterization_computed_properties(self):
        model = SSACharacterization(
            max_drive=0.60,
            initial_drive=0.80,
            num_attempts=1,
        )

        assert model.max_drive_percent == pytest.approx(60.0)
        assert model.initial_drive_percent == pytest.approx(80.0)
        assert model.drive_reduction == pytest.approx(0.20)
        assert model.succeeded_first_try is True
        assert model.is_complete is True

    def test_pi_mode_measurement_completion(self):
        incomplete = PiModeMeasurement(mode_8pi_9_frequency=1.0e6)
        complete = PiModeMeasurement(
            mode_8pi_9_frequency=1.0e6,
            mode_7pi_9_frequency=0.99e6,
        )

        assert incomplete.is_complete is False
        assert complete.is_complete is True

    def test_other_phase_completion_flags(self):
        cavity = CavityCharacterization(loaded_q=3.0e7, scale_factor=2.5)
        piezo_rf = PiezoWithRFTest(
            amplifier_gain_a=1.1,
            amplifier_gain_b=1.2,
            detune_gain=0.9,
        )
        high_power = HighPowerRampData(
            final_amplitude=16.0,
            one_hour_complete=True,
        )

        assert cavity.is_complete is True
        assert piezo_rf.is_complete is True
        assert high_power.is_complete is True


class TestCommissioningRecord:
    """Tests for commissioning record workflow behavior."""

    def test_linac_accepts_integer(self):
        record = CommissioningRecord(
            linac=2,
            cryomodule="02",
            cavity_number=3,
        )

        assert record.linac == 2
        assert record.full_cavity_name == "L2B_CM02_CAV3"

    def test_linac_rejects_out_of_range_integer(self):
        with pytest.raises(ValueError, match="range 0..4"):
            CommissioningRecord(
                linac=9,
                cryomodule="02",
                cavity_number=3,
            )

    def test_default_phase_status_initialization(self):
        record = CommissioningRecord(
            linac=1,
            cryomodule="02",
            cavity_number=3,
        )

        assert record.current_phase == CommissioningPhase.PIEZO_PRE_RF
        assert (
            record.get_phase_status(CommissioningPhase.PIEZO_PRE_RF)
            == PhaseStatus.IN_PROGRESS
        )
        assert (
            record.get_phase_status(CommissioningPhase.SSA_CHAR)
            == PhaseStatus.NOT_STARTED
        )

    def test_can_start_phase_honors_previous_phase_completion(self):
        record = CommissioningRecord(
            linac=1,
            cryomodule="02",
            cavity_number=3,
        )

        allowed, reason = record.can_start_phase(
            CommissioningPhase.COLD_LANDING
        )
        assert allowed is False
        assert "must complete first" in reason

        record.set_phase_status(
            CommissioningPhase.SSA_CHAR, PhaseStatus.COMPLETE
        )
        allowed, reason = record.can_start_phase(
            CommissioningPhase.COLD_LANDING
        )
        assert allowed is True
        assert "Prerequisites met" in reason

    def test_advance_to_next_phase_requires_current_complete(self):
        record = CommissioningRecord(
            linac=1,
            cryomodule="02",
            cavity_number=3,
        )

        success, message = record.advance_to_next_phase()
        assert success is False
        assert "is not complete" in message

        record.set_phase_status(
            CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE
        )
        success, message = record.advance_to_next_phase()
        assert success is True
        assert record.current_phase == CommissioningPhase.SSA_CHAR
        assert "Advanced to ssa_char" == message

    def test_checkpoint_helpers(self):
        record = CommissioningRecord(
            linac=1,
            cryomodule="02",
            cavity_number=3,
        )

        cp1 = PhaseCheckpoint(
            phase=CommissioningPhase.SSA_CHAR,
            timestamp=datetime(2026, 3, 20, 10, 0, 0),
            operator="op1",
            step_name="run_ssa",
            success=True,
        )
        cp2 = PhaseCheckpoint(
            phase=CommissioningPhase.SSA_CHAR,
            timestamp=datetime(2026, 3, 20, 10, 5, 0),
            operator="op1",
            step_name="verify_ssa",
            success=True,
        )

        record.add_checkpoint(cp1)
        record.add_checkpoint(cp2)

        checkpoints = record.get_checkpoints(CommissioningPhase.SSA_CHAR)
        assert len(checkpoints) == 2
        assert record.get_latest_checkpoint(CommissioningPhase.SSA_CHAR) == cp2

    def test_record_formatting_and_serialization(self):
        start = datetime.now() - timedelta(hours=2)
        record = CommissioningRecord(
            linac=1,
            cryomodule="02",
            cavity_number=3,
            start_time=start,
        )
        record.end_time = start + timedelta(hours=1, minutes=30)
        record.phase_status[CommissioningPhase.PIEZO_PRE_RF] = (
            PhaseStatus.COMPLETE
        )

        payload = record.to_dict()

        assert record.full_cavity_name == "L1B_CM02_CAV3"
        assert record.short_cavity_name == "02_CAV3"
        assert payload["phase_status"]["piezo_pre_rf"] == "complete"
        assert payload["elapsed_time_hours"] == pytest.approx(1.5)


class TestSerializationAndRegistry:
    """Tests for serialization helper integration and phase registry."""

    def test_serialize_deserialize_round_trip_for_phase_model(self):
        original = SSACharacterization(
            max_drive=0.65,
            initial_drive=0.85,
            num_attempts=2,
            timestamp=datetime(2026, 3, 21, 9, 0, 0),
            notes="round trip",
        )

        serialized = serialize_model(
            original,
            computed_fields=(
                "max_drive_percent",
                "initial_drive_percent",
                "drive_reduction",
                "succeeded_first_try",
                "is_complete",
            ),
        )

        restored = deserialize_model(SSACharacterization, serialized)

        assert serialized["max_drive_percent"] == pytest.approx(65.0)
        assert serialized["is_complete"] is True
        assert restored == original

    def test_display_specs_are_available_for_phase_models(self):
        cold_specs = get_phase_display_specs(ColdLandingData)

        assert [spec.widget_name for spec in cold_specs] == [
            "cold_initial_detune",
            "cold_steps_to_resonance",
            "cold_final_detune",
        ]

    def test_phase_registry_contains_all_phases(self):
        assert set(PHASE_REGISTRY) == set(CommissioningPhase)
        assert PHASE_REGISTRY[CommissioningPhase.COMPLETE].record_attr is None
        assert PHASE_REGISTRY[CommissioningPhase.COMPLETE].data_model is None
