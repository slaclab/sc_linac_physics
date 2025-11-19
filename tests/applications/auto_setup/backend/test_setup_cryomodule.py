from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import SCLinacObject


@pytest.fixture
def setup_cryomodule() -> SetupCryomodule:
    """Create a SetupCryomodule with mocked PVs and cavities."""
    with (
        patch(
            "sc_linac_physics.utils.sc_linac.cavity.custom_logger"
        ) as mock_cavity_logger,
        patch(
            "sc_linac_physics.applications.auto_setup.backend.setup_cavity.custom_logger"
        ) as mock_setup_logger,
    ):

        mock_cavity_logger.return_value = MagicMock()
        mock_setup_logger.return_value = MagicMock()

        linac_mock = MagicMock()
        # Just pass the CM number, prefix will be added by parent class
        cryo = SetupCryomodule(cryo_name="01", linac_object=linac_mock)

        # Mock PVs from SetupLinacObject
        cryo._start_pv_obj = MagicMock()
        cryo._stop_pv_obj = MagicMock()
        cryo._abort_pv_obj = MagicMock()
        cryo._shutoff_pv_obj = MagicMock()
        cryo._ssa_cal_requested_pv_obj = MagicMock()
        cryo._auto_tune_requested_pv_obj = MagicMock()
        cryo._cav_char_requested_pv_obj = MagicMock()
        cryo._rf_ramp_requested_pv_obj = MagicMock()

        return cryo


class TestSetupCryomoduleInitialization:
    def test_inheritance(self):
        """Test that SetupCryomodule properly inherits from both parent classes."""
        cryo = SetupCryomodule(cryo_name="01", linac_object=MagicMock())
        # Test inheritance tree - we only need to check the immediate parents
        assert isinstance(cryo, SetupCryomodule)  # First our actual class
        assert isinstance(cryo, Cryomodule)  # First parent
        assert isinstance(
            cryo, SCLinacObject
        )  # Base class both parents inherit from

    def test_initialization(self, setup_cryomodule):
        """Test that initialization sets up all required attributes."""
        assert (
            setup_cryomodule.cryo_name == "CM01"
        )  # Just the CM prefix + number
        assert hasattr(setup_cryomodule, "cavities")
        assert hasattr(setup_cryomodule, "start_pv_obj")
        assert hasattr(setup_cryomodule, "ssa_cal_requested_pv_obj")


class TestSetupCryomoduleOperations:
    def test_clear_abort(self, setup_cryomodule):
        """Test that clear_abort is called on all cavities."""
        for cavity in setup_cryomodule.cavities.values():
            cavity.clear_abort = MagicMock()

        setup_cryomodule.clear_abort()

        for cavity in setup_cryomodule.cavities.values():
            cavity.clear_abort.assert_called_once()

    def test_clear_abort_with_no_cavities(self):
        """Test clear_abort behavior when there are no cavities."""
        cryo = SetupCryomodule(cryo_name="01", linac_object=MagicMock())
        with patch.object(cryo, "cavities", {}):
            # Should not raise any errors
            cryo.clear_abort()

    def test_clear_abort_handles_errors(self, setup_cryomodule):
        """Test that clear_abort handles errors in individual cavities."""
        # Create a mock cavity with a failing clear_abort
        cavity = MagicMock()
        cavity.clear_abort.side_effect = RuntimeError("Mock error")
        setup_cryomodule.cavities = {"1": cavity}

        # The error should be propagated
        with pytest.raises(RuntimeError, match="Mock error"):
            setup_cryomodule.clear_abort()


class TestSetupCryomoduleProperties:
    def test_ssa_cal_requested_property(self, setup_cryomodule):
        """Test the ssa_cal_requested property."""
        test_value = True
        setup_cryomodule.ssa_cal_requested = test_value
        setup_cryomodule._ssa_cal_requested_pv_obj.put.assert_called_with(
            test_value
        )

        setup_cryomodule._ssa_cal_requested_pv_obj.get.return_value = test_value
        assert setup_cryomodule.ssa_cal_requested == test_value

    def test_auto_tune_requested_property(self, setup_cryomodule):
        """Test the auto_tune_requested property."""
        test_value = True
        setup_cryomodule.auto_tune_requested = test_value
        setup_cryomodule._auto_tune_requested_pv_obj.put.assert_called_with(
            test_value
        )

        setup_cryomodule._auto_tune_requested_pv_obj.get.return_value = (
            test_value
        )
        assert setup_cryomodule.auto_tune_requested == test_value
