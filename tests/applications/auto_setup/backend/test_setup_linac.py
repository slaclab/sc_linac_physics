"""Unit tests for SetupLinac class."""

from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics.utils.sc_linac.linac import Linac


@pytest.fixture
def setup_linac(monkeypatch):
    """Create a SetupLinac instance for testing."""
    from sc_linac_physics.applications.auto_setup.backend.setup_linac import (
        SetupLinac,
    )

    # Mock LauncherLinacObject since it's in the inheritance chain
    launcher_mock = MagicMock()
    monkeypatch.setattr(
        "sc_linac_physics.utils.sc_linac.linac_utils.LauncherLinacObject",
        launcher_mock,
    )

    # Create a proper mock machine
    machine = MagicMock()
    machine.cryomodule_class = MagicMock()
    machine.cavity_class = MagicMock()
    machine.rack_class = MagicMock()
    machine.magnet_class = MagicMock()
    machine.ssa_class = MagicMock()
    machine.stepper_class = MagicMock()
    machine.piezo_class = MagicMock()

    # Create the SetupLinac instance with required parameters
    # According to LINAC_CM_MAP in linac_utils, L0B is index 0
    linac = SetupLinac(
        linac_section=0,  # L0B is index 0
        beamline_vacuum_infixes=["BV01"],
        insulating_vacuum_cryomodules=["CM01"],
        machine=machine,
    )

    # Mock the PVs required by SetupLinacObject
    linac._start_pv_obj = MagicMock()
    linac._stop_pv_obj = MagicMock()
    linac._abort_pv_obj = MagicMock()
    linac._shutoff_pv_obj = MagicMock()
    linac._ssa_cal_requested_pv_obj = MagicMock()
    linac._auto_tune_requested_pv_obj = MagicMock()
    linac._cav_char_requested_pv_obj = MagicMock()
    linac._rf_ramp_requested_pv_obj = MagicMock()

    return linac


class TestSetupLinacInitialization:
    """Tests for SetupLinac initialization and inheritance."""

    def test_inheritance(self, setup_linac):
        """Test that SetupLinac has required functionality from parent classes."""
        # Test Linac functionality
        assert isinstance(setup_linac, Linac)
        assert hasattr(setup_linac, "cryomodules")
        assert hasattr(setup_linac, "name")

        # Test SetupLinac functionality
        assert hasattr(setup_linac, "ssa_cal_requested")
        assert hasattr(setup_linac, "auto_tune_requested")
        assert hasattr(setup_linac, "pv_prefix")

        # Test base functionality
        assert hasattr(setup_linac, "pv_addr")
        assert hasattr(setup_linac, "auto_pv_addr")

    def test_initialization(self, setup_linac):
        """Test that initialization sets up all required attributes."""
        assert setup_linac.name == "L0B"
        assert hasattr(setup_linac, "cryomodules")
        assert hasattr(setup_linac, "pv_prefix")
        assert hasattr(setup_linac, "start_pv_obj")


class TestSetupLinacOperations:
    """Tests for SetupLinac operations."""

    def test_pv_prefix(self, setup_linac):
        """Test that PV prefix is correctly formatted."""
        assert setup_linac.pv_prefix == "ACCL:L0B:1:"

    def test_clear_abort(self, setup_linac):
        """Test that clear_abort is called on all cryomodules."""
        # Mock all cryomodules
        for cm in setup_linac.cryomodules.values():
            cm.clear_abort = MagicMock()

        setup_linac.clear_abort()

        # Verify each cryomodule's clear_abort was called exactly once
        for cm in setup_linac.cryomodules.values():
            cm.clear_abort.assert_called_once()

    def test_clear_abort_with_no_cryomodules(self, setup_linac):
        """Test clear_abort behavior when there are no cryomodules."""
        with patch.object(setup_linac, "cryomodules", {}):
            # Should not raise any errors
            setup_linac.clear_abort()

    def test_clear_abort_handles_errors(self, setup_linac):
        """Test that clear_abort properly handles errors from cryomodules."""
        # Create a cryomodule that raises an error
        error_cm = MagicMock()
        error_cm.clear_abort.side_effect = RuntimeError("Mock error")

        setup_linac.cryomodules = {"CM01": error_cm}

        # The error should be propagated
        with pytest.raises(RuntimeError, match="Mock error"):
            setup_linac.clear_abort()


class TestSetupLinacProperties:
    """Tests for SetupLinac property getters and setters."""

    def test_ssa_cal_requested_property(self, setup_linac):
        """Test that ssa_cal_requested property updates the PV."""
        # Mock the PV object
        setup_linac._ssa_cal_requested_pv_obj = MagicMock()
        setup_linac._ssa_cal_requested_pv_obj.get.return_value = True

        # Test getter gets from PV
        assert setup_linac.ssa_cal_requested is True
        setup_linac._ssa_cal_requested_pv_obj.get.assert_called_once()

        # Test setter updates PV
        setup_linac.ssa_cal_requested = False
        setup_linac._ssa_cal_requested_pv_obj.put.assert_called_once_with(False)

    def test_auto_tune_requested_property(self, setup_linac):
        """Test that auto_tune_requested property updates the PV."""
        # Mock the PV object
        setup_linac._auto_tune_requested_pv_obj = MagicMock()
        setup_linac._auto_tune_requested_pv_obj.get.return_value = True

        # Test getter gets from PV
        assert setup_linac.auto_tune_requested is True
        setup_linac._auto_tune_requested_pv_obj.get.assert_called_once()

        # Test setter updates PV
        setup_linac.auto_tune_requested = False
        setup_linac._auto_tune_requested_pv_obj.put.assert_called_once_with(
            False
        )
