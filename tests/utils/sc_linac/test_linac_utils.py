from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import (
    SCLinacObject,
    stepper_tol_factor,
    PulseError,
    StepperError,
    SSACalibrationError,
    SSACalibrationToleranceError,
    CavityQLoadedCalibrationError,
    CavityCharacterizationError,
    CavityScaleFactorCalibrationError,
    SSAPowerError,
    SSAFaultError,
    DetuneError,
    QuenchError,
    StepperAbortError,
    CavityAbortError,
    CavityFaultError,
    CavityHWModeError,
    L0B,
    L1B,
    L1BHL,
    L2B,
    L3B,
    ALL_CRYOMODULES,
    ALL_CRYOMODULES_NO_HL,
    LINAC_TUPLES,
    LINAC_CM_DICT,
    LINAC_CM_MAP,
    SSA_STATUS_ON_VALUE,
    SSA_STATUS_FAULTED_VALUE,
    LOADED_Q_LOWER_LIMIT,
    LOADED_Q_UPPER_LIMIT,
    CAVITY_SCALE_UPPER_LIMIT,
    CAVITY_SCALE_LOWER_LIMIT,
    RF_MODE_SELAP,
    RF_MODE_PULSE,
    STEPPER_TEMP_LIMIT,
    HZ_PER_STEP,
    HL_HZ_PER_STEP,
    MICROSTEPS_PER_STEP,
    ESTIMATED_MICROSTEPS_PER_HZ,
    CRYO_NAME_MAP,
    HL_SSA_MAP,
    BEAMLINE_VACUUM_INFIXES,
    INSULATING_VACUUM_CRYOMODULES,
    PARK_DETUNE,
    STATUS_RUNNING_VALUE,
    STATUS_READY_VALUE,
    STATUS_ERROR_VALUE,
    ESTIMATED_MICROSTEPS_PER_HZ_HL,
    L4B,
)


class TestConstants:
    """Test module constants and data structures"""

    def test_linac_structure_constants(self):
        """Test that linac structure constants are properly defined"""
        assert L0B == ["01"]
        assert L1B == ["02", "03"]
        assert L1BHL == ["H1", "H2"]
        assert len(L2B) == 12
        assert len(L3B) == 20
        assert L2B[0] == "04"
        assert L2B[-1] == "15"
        assert L3B[0] == "16"
        assert L3B[-1] == "35"

    def test_all_cryomodules_composition(self):
        """Test that ALL_CRYOMODULES contains all expected modules"""
        expected_total = (
            len(L0B) + len(L1B) + len(L1BHL) + len(L2B) + len(L3B) + len(L4B)
        )
        assert len(ALL_CRYOMODULES) == expected_total

        # Check that all individual lists are represented
        for cm in L0B + L1B + L1BHL + L2B + L3B:
            assert cm in ALL_CRYOMODULES

    def test_all_cryomodules_no_hl_composition(self):
        """Test that ALL_CRYOMODULES_NO_HL excludes HL modules"""
        expected_total = len(L0B) + len(L1B) + len(L2B) + len(L3B) + len(L4B)
        assert len(ALL_CRYOMODULES_NO_HL) == expected_total

        # Check that HL modules are not included
        for hl_module in L1BHL:
            assert hl_module not in ALL_CRYOMODULES_NO_HL

    def test_linac_tuples_structure(self):
        """Test LINAC_TUPLES structure"""
        assert len(LINAC_TUPLES) == 5
        names = [name for name, _ in LINAC_TUPLES]
        assert names == ["L0B", "L1B", "L2B", "L3B", "L4B"]

    def test_linac_cm_dict_structure(self):
        """Test LINAC_CM_DICT mapping"""
        assert LINAC_CM_DICT[0] == L0B
        assert LINAC_CM_DICT[1] == L1B + L1BHL
        assert LINAC_CM_DICT[2] == L2B
        assert LINAC_CM_DICT[3] == L3B
        assert LINAC_CM_DICT[4] == L4B

    def test_linac_cm_map_structure(self):
        """Test LINAC_CM_MAP includes HL modules"""
        assert LINAC_CM_MAP[0] == L0B
        assert LINAC_CM_MAP[1] == L1B + L1BHL
        assert LINAC_CM_MAP[2] == L2B
        assert LINAC_CM_MAP[3] == L3B

    def test_status_values(self):
        """Test status value constants"""
        assert STATUS_READY_VALUE == 0
        assert STATUS_RUNNING_VALUE == 1
        assert STATUS_ERROR_VALUE == 2
        assert isinstance(STATUS_RUNNING_VALUE, int)

    def test_ssa_status_values(self):
        """Test SSA status constants"""
        assert SSA_STATUS_ON_VALUE == 3
        assert SSA_STATUS_FAULTED_VALUE == 1
        assert isinstance(SSA_STATUS_ON_VALUE, int)
        assert isinstance(SSA_STATUS_FAULTED_VALUE, int)

    def test_cavity_limits(self):
        """Test cavity parameter limits"""
        assert LOADED_Q_LOWER_LIMIT == int(2.5e7)
        assert LOADED_Q_UPPER_LIMIT == int(5.1e7)
        assert LOADED_Q_LOWER_LIMIT < LOADED_Q_UPPER_LIMIT

        assert CAVITY_SCALE_LOWER_LIMIT == 10
        assert CAVITY_SCALE_UPPER_LIMIT == 125
        assert CAVITY_SCALE_LOWER_LIMIT < CAVITY_SCALE_UPPER_LIMIT

    def test_rf_mode_values(self):
        """Test RF mode constants"""
        assert RF_MODE_SELAP == 0
        assert RF_MODE_PULSE == 4
        assert isinstance(RF_MODE_SELAP, int)
        assert isinstance(RF_MODE_PULSE, int)

    def test_cryo_name_map(self):
        """Test cryogenic name mapping"""
        assert CRYO_NAME_MAP["H1"] == "HL01"
        assert CRYO_NAME_MAP["H2"] == "HL02"
        assert len(CRYO_NAME_MAP) == 2

    def test_hl_ssa_map(self):
        """Test high-level SSA mapping"""
        expected_mapping = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3, 8: 4}
        assert HL_SSA_MAP == expected_mapping

    def test_vacuum_structures(self):
        """Test vacuum-related data structures"""
        assert len(BEAMLINE_VACUUM_INFIXES) == 5
        assert len(INSULATING_VACUUM_CRYOMODULES) == 5

        # Check that each beamline has corresponding vacuum info
        for i, beamline_vacuums in enumerate(BEAMLINE_VACUUM_INFIXES):
            assert isinstance(beamline_vacuums, list)
            if i < 4:
                assert len(beamline_vacuums) > 0

    def test_park_detune_constant(self):
        """Test PARK_DETUNE constant"""
        assert PARK_DETUNE == 10000
        assert isinstance(PARK_DETUNE, int)


class TestStepperTolFactor:
    """Test the stepper tolerance factor function"""

    def test_small_steps_tolerance(self):
        """Test tolerance for small step counts"""
        # Steps <= 10000 should return 5
        assert stepper_tol_factor(5000) == 5
        assert stepper_tol_factor(10000) == 5
        assert stepper_tol_factor(-5000) == 5  # Should handle negative steps

    def test_large_steps_tolerance(self):
        """Test tolerance for very large step counts"""
        # Steps >= 50M should return 1.01
        result = stepper_tol_factor(50000000)
        assert abs(result - 1.01) < 0.001

        result = stepper_tol_factor(100000000)
        assert abs(result - 1.01) < 0.001

    def test_intermediate_steps_tolerance(self):
        """Test tolerance for intermediate step counts"""
        # Test a few points in the linear interpolation ranges
        result_100k = stepper_tol_factor(100000)
        result_1m = stepper_tol_factor(1000000)
        result_5m = stepper_tol_factor(5000000)

        # Should be decreasing as steps increase
        assert result_100k > result_1m > result_5m

        # Should be within reasonable bounds
        assert 1.0 < result_5m < 2.0
        assert 1.0 < result_1m < 3.0
        assert 1.0 < result_100k < 6.0

    def test_negative_steps_handling(self):
        """Test that negative steps are handled correctly"""
        positive_result = stepper_tol_factor(50000)
        negative_result = stepper_tol_factor(-50000)
        assert positive_result == negative_result

    def test_zero_steps(self):
        """Test edge case of zero steps"""
        result = stepper_tol_factor(0)
        assert result == 5  # Should default to small steps behavior


class TestExceptions:
    """Test custom exception classes"""

    def test_exception_inheritance(self):
        """Test that all custom exceptions inherit from Exception"""
        exceptions = [
            PulseError,
            StepperError,
            SSACalibrationError,
            SSACalibrationToleranceError,
            CavityQLoadedCalibrationError,
            CavityCharacterizationError,
            CavityScaleFactorCalibrationError,
            SSAPowerError,
            SSAFaultError,
            DetuneError,
            QuenchError,
            StepperAbortError,
            CavityAbortError,
            CavityFaultError,
            CavityHWModeError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, Exception)

    def test_exception_instantiation(self):
        """Test that exceptions can be instantiated and raised"""
        test_message = "Test error message"

        with pytest.raises(SSACalibrationError):
            raise SSACalibrationError(test_message)

        with pytest.raises(QuenchError):
            raise QuenchError(test_message)

        with pytest.raises(StepperAbortError):
            raise StepperAbortError(test_message)


class ConcreteSCLinacObject(SCLinacObject):
    """Concrete implementation for testing abstract base class"""

    def __init__(self, prefix):
        self._pv_prefix = prefix

    @property
    def pv_prefix(self):
        return self._pv_prefix


class TestSCLinacObject:
    """Test the abstract SCLinacObject base class"""

    def test_cannot_instantiate_abstract_class(self):
        """Test that SCLinacObject cannot be instantiated directly"""
        with pytest.raises(TypeError):
            SCLinacObject()

    def test_concrete_implementation(self):
        """Test concrete implementation of SCLinacObject"""
        prefix = "ACCL:L1B:0110:"
        obj = ConcreteSCLinacObject(prefix)

        assert obj.pv_prefix == prefix
        assert obj.pv_addr("ADES") == "ACCL:L1B:0110:ADES"
        assert obj.pv_addr("PHASE") == "ACCL:L1B:0110:PHASE"

    def test_pv_addr_method(self):
        """Test PV address construction"""
        obj = ConcreteSCLinacObject("TEST:PREFIX:")

        assert obj.pv_addr("SUFFIX") == "TEST:PREFIX:SUFFIX"
        assert obj.pv_addr("") == "TEST:PREFIX:"
        assert obj.pv_addr("LONG:SUFFIX:HERE") == "TEST:PREFIX:LONG:SUFFIX:HERE"


class TestCalculatedConstants:
    """Test calculated constants and derived values"""

    def test_microsteps_calculations(self):
        """Test microsteps per Hz calculations"""
        expected_normal = MICROSTEPS_PER_STEP / HZ_PER_STEP
        expected_hl = MICROSTEPS_PER_STEP / HL_HZ_PER_STEP

        assert abs(ESTIMATED_MICROSTEPS_PER_HZ - expected_normal) < 0.001
        assert abs(ESTIMATED_MICROSTEPS_PER_HZ_HL - expected_hl) < 0.001

        # Sanity check the values
        assert ESTIMATED_MICROSTEPS_PER_HZ > 0
        assert ESTIMATED_MICROSTEPS_PER_HZ_HL > 0
        assert ESTIMATED_MICROSTEPS_PER_HZ > ESTIMATED_MICROSTEPS_PER_HZ_HL


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_stepper_tol_factor_boundary_values(self):
        """Test stepper tolerance factor at boundary values"""
        # Test exactly at boundaries
        assert stepper_tol_factor(10000) == 5
        assert (
            stepper_tol_factor(10001) != 5
        )  # Should be in interpolation range

        # Test just above and below key thresholds
        result_just_below_10k = stepper_tol_factor(9999)
        result_just_above_10k = stepper_tol_factor(10001)

        assert result_just_below_10k == 5
        assert result_just_above_10k < 5

    def test_empty_string_pv_suffix(self):
        """Test PV address construction with empty suffix"""
        obj = ConcreteSCLinacObject("PREFIX:")
        assert obj.pv_addr("") == "PREFIX:"

    def test_constants_are_immutable_types(self):
        """Test that important constants are immutable types"""
        # These should be immutable to prevent accidental modification
        assert isinstance(SSA_STATUS_ON_VALUE, int)
        assert isinstance(LOADED_Q_LOWER_LIMIT, int)
        assert isinstance(HZ_PER_STEP, (int, float))
        assert isinstance(STEPPER_TEMP_LIMIT, (int, float))


# Fixtures for integration tests
@pytest.fixture
def mock_pv():
    """Fixture providing a mock PV object"""
    with patch("sc_linac_physics.utils.sc_linac.linac_utils.PV") as mock:
        pv_instance = Mock()
        mock.return_value = pv_instance
        yield pv_instance


class TestDataStructureIntegrity:
    """Test the integrity and consistency of data structures"""

    def test_linac_cm_dict_completeness(self):
        """Test that LINAC_CM_DICT covers all expected linacs"""
        expected_keys = [0, 1, 2, 3, 4]  # L0B, L1B, L2B, L3B, L4B
        assert set(LINAC_CM_DICT.keys()) == set(expected_keys)

    def test_linac_cm_map_consistency(self):
        """Test that LINAC_CM_MAP is consistent with individual lists"""
        assert LINAC_CM_MAP[0] == L0B
        assert LINAC_CM_MAP[2] == L2B
        assert LINAC_CM_MAP[3] == L3B
        # L1B includes HL modules
        assert set(LINAC_CM_MAP[1]) == set(L1B + L1BHL)

    def test_vacuum_structure_consistency(self):
        """Test consistency between vacuum structures"""
        # Should have same number of beamlines
        assert len(BEAMLINE_VACUUM_INFIXES) == len(
            INSULATING_VACUUM_CRYOMODULES
        )
        assert len(BEAMLINE_VACUUM_INFIXES) == 5  # L0B, L1B, L2B, L3B, L4B

    def test_cryo_name_map_validity(self):
        """Test that CRYO_NAME_MAP keys exist in HL modules"""
        for hl_name in CRYO_NAME_MAP.keys():
            assert hl_name in L1BHL


# Configuration for pytest
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
