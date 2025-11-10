from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import (
    SCLinacObject,
    AutoLinacObject,
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
        expected_total = len(L0B) + len(L1B) + len(L1BHL) + len(L2B) + len(L3B)
        assert len(ALL_CRYOMODULES) == expected_total

        # Check that all individual lists are represented
        for cm in L0B + L1B + L1BHL + L2B + L3B:
            assert cm in ALL_CRYOMODULES

    def test_all_cryomodules_no_hl_composition(self):
        """Test that ALL_CRYOMODULES_NO_HL excludes HL modules"""
        expected_total = len(L0B) + len(L1B) + len(L2B) + len(L3B)
        assert len(ALL_CRYOMODULES_NO_HL) == expected_total

        # Check that HL modules are not included
        for hl_module in L1BHL:
            assert hl_module not in ALL_CRYOMODULES_NO_HL

    def test_linac_tuples_structure(self):
        """Test LINAC_TUPLES structure"""
        assert len(LINAC_TUPLES) == 4
        names = [name for name, _ in LINAC_TUPLES]
        assert names == ["L0B", "L1B", "L2B", "L3B"]

    def test_linac_cm_dict_structure(self):
        """Test LINAC_CM_DICT mapping"""
        assert LINAC_CM_DICT[0] == L0B
        assert LINAC_CM_DICT[1] == L1B
        assert LINAC_CM_DICT[2] == L2B
        assert LINAC_CM_DICT[3] == L3B

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
        assert len(BEAMLINE_VACUUM_INFIXES) == 4
        assert len(INSULATING_VACUUM_CRYOMODULES) == 4

        # Check that each beamline has corresponding vacuum info
        for i, beamline_vacuums in enumerate(BEAMLINE_VACUUM_INFIXES):
            assert isinstance(beamline_vacuums, list)
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


class TestAutoLinacObject:
    """Test the AutoLinacObject class"""

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_initialization(self, mock_pv_class):
        """Test AutoLinacObject initialization"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        # Test PV address construction
        assert obj.abort_pv == "TEST:AUTO:AUTO:ABORT"
        assert obj.start_pv == "TEST:AUTO:AUTO:SETUPSTRT"
        assert obj.stop_pv == "TEST:AUTO:AUTO:fSETUPSTOP"  # Note the 'f' prefix
        assert obj.progress_pv == "TEST:AUTO:AUTO:PROG"
        assert obj.status_pv == "TEST:AUTO:AUTO:STATUS"
        assert obj.status_msg_pv == "TEST:AUTO:AUTO:MSG"
        assert obj.note_pv == "TEST:AUTO:AUTO:NOTE"

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_pv_object_creation(self, mock_pv_class):
        """Test that PV objects are created lazily"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        # Initially, PV objects should be None
        assert obj._abort_pv_obj is None
        assert obj._status_pv_obj is None
        assert obj._progress_pv_obj is None

        # Accessing properties should create PV objects
        mock_pv_instance = Mock()
        mock_pv_class.return_value = mock_pv_instance

        abort_pv_obj = obj.abort_pv_obj
        assert mock_pv_class.called
        assert abort_pv_obj == mock_pv_instance

        # Second access should return the same object
        abort_pv_obj_2 = obj.abort_pv_obj
        assert abort_pv_obj == abort_pv_obj_2

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_status_property(self, mock_pv_class):
        """Test status property getter and setter"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_pv_instance = Mock()
        mock_pv_instance.get.return_value = 1
        mock_pv_class.return_value = mock_pv_instance

        # Test getter
        status = obj.status
        assert status == 1
        mock_pv_instance.get.assert_called_once()

        # Test setter
        obj.status = 3
        mock_pv_instance.put.assert_called_once_with(3)

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_script_is_running(self, mock_pv_class):
        """Test script_is_running property"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_pv_instance = Mock()
        mock_pv_class.return_value = mock_pv_instance

        # Test when status equals STATUS_RUNNING_VALUE (1)
        mock_pv_instance.get.return_value = STATUS_RUNNING_VALUE  # Should be 1
        assert obj.script_is_running is True

        # Test when status doesn't equal STATUS_RUNNING_VALUE
        mock_pv_instance.get.return_value = STATUS_READY_VALUE  # Should be 0
        assert obj.script_is_running is False

        # Test with another different value
        mock_pv_instance.get.return_value = STATUS_ERROR_VALUE  # Should be 2
        assert obj.script_is_running is False

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_progress_property(self, mock_pv_class):
        """Test progress property getter and setter"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_pv_instance = Mock()
        mock_pv_instance.get.return_value = 45.5
        mock_pv_class.return_value = mock_pv_instance

        # Test getter
        progress = obj.progress
        assert progress == 45.5

        # Test setter
        obj.progress = 67.8
        mock_pv_instance.put.assert_called_with(67.8)

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    @patch("builtins.print")
    def test_status_message_property(self, mock_print, mock_pv_class):
        """Test status_message property getter and setter"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_pv_instance = Mock()
        mock_pv_instance.get.return_value = "Test message"
        mock_pv_class.return_value = mock_pv_instance

        # Test getter
        message = obj.status_message
        assert message == "Test message"

        # Test setter (should also print)
        obj.status_message = "New status"
        mock_pv_instance.put.assert_called_with("New status")
        mock_print.assert_called_with("New status")

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_abort_functionality(self, mock_pv_class):
        """Test abort-related functionality"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_pv_instance = Mock()
        mock_pv_class.return_value = mock_pv_instance

        # Test abort_requested when abort is False
        mock_pv_instance.get.return_value = 0
        assert obj.abort_requested is False

        # Test abort_requested when abort is True
        mock_pv_instance.get.return_value = 1
        assert obj.abort_requested is True

        # Test trigger_abort
        obj.trigger_abort()
        mock_pv_instance.put.assert_called_with(1)

    @patch("sc_linac_physics.utils.sc_linac.linac_utils.PV")
    def test_start_and_stop_triggers(self, mock_pv_class):
        """Test start and stop trigger functionality"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        mock_start_pv = Mock()
        mock_stop_pv = Mock()

        def pv_side_effect(addr):
            if "STRT" in addr:
                return mock_start_pv
            elif "STOP" in addr:
                return mock_stop_pv
            return Mock()

        mock_pv_class.side_effect = pv_side_effect

        # Test trigger_start
        obj.trigger_start()
        mock_start_pv.put.assert_called_with(1)

        # Test trigger_stop
        obj.trigger_stop()
        mock_stop_pv.put.assert_called_with(1)

    def test_clear_abort_not_implemented(self):
        """Test that clear_abort raises NotImplementedError"""

        class ConcreteAutoLinacObject(AutoLinacObject):
            @property
            def pv_prefix(self):
                return "TEST:AUTO:"

        obj = ConcreteAutoLinacObject("SETUP")

        with pytest.raises(NotImplementedError):
            obj.clear_abort()


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


@pytest.fixture
def concrete_auto_linac_object():
    """Fixture providing a concrete AutoLinacObject for testing"""

    class TestAutoLinacObject(AutoLinacObject):
        @property
        def pv_prefix(self):
            return "TEST:LINAC:"

    return TestAutoLinacObject("SETUP")


class TestIntegration:
    """Integration tests using fixtures"""

    def test_auto_linac_object_full_workflow(
        self, mock_pv, concrete_auto_linac_object
    ):
        """Test a complete workflow with AutoLinacObject"""
        obj = concrete_auto_linac_object

        # Test initial state
        mock_pv.get.return_value = 0
        assert not obj.abort_requested

        # Test starting a process
        obj.trigger_start()
        mock_pv.put.assert_called_with(1)

        # Test setting status
        mock_pv.reset_mock()  # Clear previous calls
        obj.status = STATUS_RUNNING_VALUE
        mock_pv.put.assert_called_with(STATUS_RUNNING_VALUE)

        # Test setting progress
        mock_pv.reset_mock()  # Clear previous calls
        obj.progress = 50.0
        mock_pv.put.assert_called_with(50.0)

        # Test aborting
        mock_pv.reset_mock()  # Clear previous calls
        obj.trigger_abort()
        mock_pv.put.assert_called_with(1)

    def test_auto_linac_object_status_workflow(
        self, mock_pv, concrete_auto_linac_object
    ):
        """Test status-related workflow"""
        obj = concrete_auto_linac_object

        # Test status message
        mock_pv.get.return_value = "Initial message"
        assert obj.status_message == "Initial message"

        # Test setting new status message
        with patch("builtins.print") as mock_print:
            obj.status_message = "New status message"
            mock_pv.put.assert_called_with("New status message")
            mock_print.assert_called_with("New status message")


class TestDataStructureIntegrity:
    """Test the integrity and consistency of data structures"""

    def test_linac_cm_dict_completeness(self):
        """Test that LINAC_CM_DICT covers all expected linacs"""
        expected_keys = [0, 1, 2, 3]  # L0B, L1B, L2B, L3B
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
        assert len(BEAMLINE_VACUUM_INFIXES) == 4  # L0B, L1B, L2B, L3B

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
