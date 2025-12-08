# "test_tune_stepper.py"
from random import randint, uniform
from unittest.mock import MagicMock, patch

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.tuning.tune_stepper import TuneStepper
from sc_linac_physics.utils.sc_linac.linac_utils import MAX_STEPPER_SPEED


@pytest.fixture
def mock_cavity():
    """Create a mock cavity with necessary attributes."""
    cavity = MagicMock()
    cavity.park_detune = 10000
    cavity.set_status_message = MagicMock()
    return cavity


@pytest.fixture
def stepper(mock_cavity):
    """Create TuneStepper instance with mocked cavity."""
    with patch.object(TuneStepper, "__init__", lambda self, cavity: None):
        stepper_instance = TuneStepper.__new__(TuneStepper)
        stepper_instance.cavity = mock_cavity
        stepper_instance._steps_cold_landing_pv_obj = None
        stepper_instance._nsteps_park_pv_obj = None
        stepper_instance._nsteps_cold_pv_obj = None
        stepper_instance._step_signed_pv_obj = None
        stepper_instance._park_steps = None
        # Mock the hz_per_microstep PV object with a default value
        stepper_instance._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)
        yield stepper_instance


class TestPropertyLazyLoading:
    """Test lazy loading of PV objects."""

    def test_steps_cold_landing_pv_obj_lazy_load(self, stepper):
        """Test that steps_cold_landing_pv_obj is created on first access."""
        with patch(
            "sc_linac_physics.applications.tuning.tune_stepper.PV"
        ) as mock_pv:
            mock_pv_instance = make_mock_pv()
            mock_pv.return_value = mock_pv_instance
            stepper.steps_cold_landing_pv = "TEST:STEPS:COLD"
            stepper._steps_cold_landing_pv_obj = (
                None  # Reset to test lazy loading
            )

            result = stepper.steps_cold_landing_pv_obj

            mock_pv.assert_called_once_with("TEST:STEPS:COLD")
            assert result == mock_pv_instance

    def test_steps_cold_landing_pv_obj_cached(self, stepper):
        """Test that subsequent accesses use cached PV object."""
        mock_pv = make_mock_pv()
        stepper._steps_cold_landing_pv_obj = mock_pv

        result1 = stepper.steps_cold_landing_pv_obj
        result2 = stepper.steps_cold_landing_pv_obj

        assert result1 is result2
        assert result1 == mock_pv

    def test_nsteps_cold_pv_obj_lazy_load(self, stepper):
        """Test that nsteps_cold_pv_obj is created on first access."""
        with patch(
            "sc_linac_physics.applications.tuning.tune_stepper.PV"
        ) as mock_pv:
            mock_pv_instance = make_mock_pv()
            mock_pv.return_value = mock_pv_instance
            stepper.nsteps_cold_pv = "TEST:NSTEPS:COLD"
            stepper._nsteps_cold_pv_obj = None  # Reset to test lazy loading

            result = stepper.nsteps_cold_pv_obj

            mock_pv.assert_called_once_with("TEST:NSTEPS:COLD")
            assert result == mock_pv_instance

    def test_nsteps_cold_pv_obj_cached(self, stepper):
        """Test that nsteps_cold_pv_obj is cached."""
        mock_pv = make_mock_pv()
        stepper._nsteps_cold_pv_obj = mock_pv

        result1 = stepper.nsteps_cold_pv_obj
        result2 = stepper.nsteps_cold_pv_obj

        assert result1 is result2

    def test_step_signed_pv_obj_lazy_load(self, stepper):
        """Test that step_signed_pv_obj is created on first access."""
        with patch(
            "sc_linac_physics.applications.tuning.tune_stepper.PV"
        ) as mock_pv:
            mock_pv_instance = make_mock_pv()
            mock_pv.return_value = mock_pv_instance
            stepper.step_signed_pv = "TEST:STEP:SIGNED"
            stepper._step_signed_pv_obj = None  # Reset to test lazy loading

            result = stepper.step_signed_pv_obj

            mock_pv.assert_called_once_with("TEST:STEP:SIGNED")
            assert result == mock_pv_instance

    def test_step_signed_pv_obj_cached(self, stepper):
        """Test that step_signed_pv_obj is cached."""
        mock_pv = make_mock_pv()
        stepper._step_signed_pv_obj = mock_pv

        result1 = stepper.step_signed_pv_obj
        result2 = stepper.step_signed_pv_obj

        assert result1 is result2


class TestParkSteps:
    """Test park_steps calculation."""

    def test_park_steps_calculation(self, stepper):
        """Test that park_steps is calculated correctly."""
        stepper.cavity.park_detune = 10000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)

        assert stepper.park_steps == 100.0  # 10000 / 100

    def test_park_steps_cached(self, stepper):
        """Test that park_steps is cached after first calculation."""
        stepper.cavity.park_detune = 10000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)
        stepper._park_steps = None  # Ensure it starts as None

        # First call calculates and caches
        result1 = stepper.park_steps
        assert result1 == 100.0
        assert stepper._park_steps == 100.0  # Verify it was cached

        # Change the underlying values
        stepper.cavity.park_detune = 20000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=50.0)

        # Should still return cached value
        result2 = stepper.park_steps
        assert result2 == 100.0  # Still the cached value

        # Reset cache to None to force recalculation
        stepper._park_steps = None
        result3 = stepper.park_steps
        assert result3 == 400.0  # New calculation: 20000 / 50

    def test_park_steps_negative_detune(self, stepper):
        """Test park_steps with negative detune."""
        stepper.cavity.park_detune = -5000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=50.0)

        assert stepper.park_steps == -100.0


class TestMoveToColdLanding:
    """Test move_to_cold_landing functionality."""

    def test_move_to_cold_landing_positive_steps(self, stepper):
        """Test moving to cold landing with positive steps."""
        expected_steps = randint(1000, 50000)
        stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=expected_steps)
        stepper.move = MagicMock()

        stepper.move_to_cold_landing()

        stepper.move.assert_called_once_with(
            num_steps=expected_steps,
            max_steps=abs(expected_steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )

    def test_move_to_cold_landing_negative_steps(self, stepper):
        """Test moving to cold landing with negative steps."""
        expected_steps = randint(-50000, -1000)
        stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=expected_steps)
        stepper.move = MagicMock()

        stepper.move_to_cold_landing()

        stepper.move.assert_called_once_with(
            num_steps=expected_steps,
            max_steps=abs(expected_steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )

    def test_move_to_cold_landing_with_check_detune(self, stepper):
        """Test that check_detune parameter is passed correctly."""
        expected_steps = 5000
        stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=expected_steps)
        stepper.move = MagicMock()

        stepper.move_to_cold_landing(check_detune=True)

        stepper.move.assert_called_once_with(
            num_steps=expected_steps,
            max_steps=abs(expected_steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=True,
        )

    def test_move_to_cold_landing_logs_status(self, stepper, mock_cavity):
        """Test that status message is logged."""
        expected_steps = 5000
        stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=expected_steps)
        stepper.move = MagicMock()

        stepper.move_to_cold_landing(check_detune=True)

        mock_cavity.set_status_message.assert_called_once()
        args = mock_cavity.set_status_message.call_args
        assert "Moving stepper to cold landing" in args[0][0]
        assert args[1]["extra_data"]["steps"] == expected_steps
        assert args[1]["extra_data"]["check_detune"] is True


class TestPark:
    """Test park functionality."""

    def test_park_positive_steps(self, stepper):
        """Test parking with positive steps."""
        stepper.cavity.park_detune = 10000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)
        stepper.move = MagicMock()

        stepper.park()

        stepper.move.assert_called_once_with(
            num_steps=100.0,
            max_steps=100.0,
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )

    def test_park_negative_steps(self, stepper):
        """Test parking with negative steps."""
        stepper.cavity.park_detune = -10000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)
        stepper.move = MagicMock()

        stepper.park()

        stepper.move.assert_called_once_with(
            num_steps=-100.0,
            max_steps=100.0,  # abs() is used for max_steps
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )

    def test_park_with_check_detune(self, stepper):
        """Test that check_detune parameter is passed correctly."""
        stepper.cavity.park_detune = 5000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=50.0)
        stepper.move = MagicMock()

        stepper.park(check_detune=True)

        stepper.move.assert_called_once_with(
            num_steps=100.0,
            max_steps=100.0,
            speed=MAX_STEPPER_SPEED,
            check_detune=True,
        )

    def test_park_logs_status(self, stepper, mock_cavity):
        """Test that status message is logged."""
        stepper.cavity.park_detune = 5000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=50.0)
        stepper.move = MagicMock()

        stepper.park(check_detune=True)

        mock_cavity.set_status_message.assert_called_once()
        args = mock_cavity.set_status_message.call_args
        assert "Moving tuner to park position" in args[0][0]
        assert args[1]["extra_data"]["target_steps"] == 100.0
        assert args[1]["extra_data"]["check_detune"] is True

    def test_park_with_small_hz_per_microstep(self, stepper):
        """Test parking with very small hz_per_microstep values."""
        stepper.cavity.park_detune = 10000
        hz_value = uniform(0.001, 0.01)
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=hz_value)
        stepper.move = MagicMock()

        stepper.park()

        expected_steps = 10000 / hz_value
        stepper.move.assert_called_once()
        call_args = stepper.move.call_args[1]
        assert abs(call_args["num_steps"] - expected_steps) < 0.01


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_park_with_zero_hz_per_microstep(self, stepper):
        """Test that park raises error with zero hz_per_microstep."""
        stepper.cavity.park_detune = 10000
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=0)

        with pytest.raises(ZeroDivisionError):
            _ = stepper.park_steps

    def test_move_to_cold_landing_with_zero_steps(self, stepper):
        """Test moving to cold landing with zero steps."""
        stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=0)
        stepper.move = MagicMock()

        stepper.move_to_cold_landing()

        stepper.move.assert_called_once_with(
            num_steps=0,
            max_steps=0,
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )

    def test_park_with_zero_detune(self, stepper):
        """Test parking with zero detune."""
        stepper.cavity.park_detune = 0
        stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=100.0)
        stepper.move = MagicMock()

        stepper.park()

        stepper.move.assert_called_once_with(
            num_steps=0.0,
            max_steps=0.0,
            speed=MAX_STEPPER_SPEED,
            check_detune=False,
        )
