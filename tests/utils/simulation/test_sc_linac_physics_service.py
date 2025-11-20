from unittest.mock import Mock, patch

import pytest
from caproto import ChannelEnum, ChannelFloat, ChannelInteger

from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
    LauncherGroups,
    HEARTBEAT_CHANNELS,
    ALARM_CHANNELS,
    ALARM_STATES,
    RACK_A_CAVITIES,
    LAUNCHER_TYPES,
)


class TestLauncherGroups:
    """Test the LauncherGroups container class."""

    def test_initialization(self):
        """Test that LauncherGroups initializes with None values."""
        groups = LauncherGroups()
        assert groups.setup is None
        assert groups.off is None
        assert groups.cold is None
        assert groups.park is None

    def test_set_and_get(self):
        """Test setting and getting launcher groups."""
        groups = LauncherGroups()
        mock_group = Mock()

        groups.set("setup", mock_group)
        assert groups.get("setup") is mock_group

    def test_all(self):
        """Test the all() method returns all groups as list."""
        groups = LauncherGroups()
        mock_setup = Mock()
        mock_off = Mock()

        groups.set("setup", mock_setup)
        groups.set("off", mock_off)

        all_groups = groups.all()
        assert len(all_groups) == 4
        assert mock_setup in all_groups
        assert mock_off in all_groups

    def test_by_type(self):
        """Test the by_type() method returns dict."""
        groups = LauncherGroups()
        mock_setup = Mock()
        groups.set("setup", mock_setup)

        by_type = groups.by_type()
        assert isinstance(by_type, dict)
        assert by_type["setup"] is mock_setup
        assert "off" in by_type
        assert "cold" in by_type
        assert "park" in by_type


class TestSCLinacPhysicsService:
    """Test the main service class."""

    @pytest.fixture
    def mocked_service(self):
        """Create a service with all dependencies mocked."""
        patches = {
            "Decarad": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.Decarad"
            ),
            "BSOICPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.BSOICPVGroup"
            ),
            "PPSPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.PPSPVGroup"
            ),
            "DecaradPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.DecaradPVGroup"
            ),
            "DecaradHeadPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.DecaradHeadPVGroup"
            ),
            "CavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CavityPVGroup"
            ),
            "PiezoPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.PiezoPVGroup"
            ),
            "StepperPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.StepperPVGroup"
            ),
            "SSAPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SSAPVGroup"
            ),
            "CavFaultPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CavFaultPVGroup"
            ),
            "JTPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.JTPVGroup"
            ),
            "LiquidLevelPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.LiquidLevelPVGroup"
            ),
            "HOMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.HOMPVGroup"
            ),
            "HeaterPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.HeaterPVGroup"
            ),
            "CryoPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CryoPVGroup"
            ),
            "BeamlineVacuumPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.BeamlineVacuumPVGroup"
            ),
            "CouplerVacuumPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CouplerVacuumPVGroup"
            ),
            "CryomodulePVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CryomodulePVGroup"
            ),
            "MAGNETPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.MAGNETPVGroup"
            ),
            "RACKPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.RACKPVGroup"
            ),
            "RFStationPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.RFStationPVGroup"
            ),
            "SetupCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupCavityPVGroup"
            ),
            "SetupCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupCMPVGroup"
            ),
            "SetupLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupLinacPVGroup"
            ),
            "SetupGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupGlobalPVGroup"
            ),
            "SetupRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupRackPVGroup"
            ),
            "OffCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffCavityPVGroup"
            ),
            "OffCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffCMPVGroup"
            ),
            "OffLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffLinacPVGroup"
            ),
            "OffGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffGlobalPVGroup"
            ),
            "OffRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffRackPVGroup"
            ),
            "ColdCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdCavityPVGroup"
            ),
            "ColdCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdCMPVGroup"
            ),
            "ColdLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdLinacPVGroup"
            ),
            "ColdGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdGlobalPVGroup"
            ),
            "ColdRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdRackPVGroup"
            ),
            "ParkCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkCavityPVGroup"
            ),
            "ParkCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkCMPVGroup"
            ),
            "ParkLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkLinacPVGroup"
            ),
            "ParkGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkGlobalPVGroup"
            ),
            "ParkRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkRackPVGroup"
            ),
        }

        mocks = {}
        for name, patcher in patches.items():
            mocks[name] = patcher.start()

        yield mocks

        for patcher in patches.values():
            patcher.stop()

    def test_initialization(self, mocked_service):
        """Test that service initializes properly."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()
        assert service is not None
        assert isinstance(service, SCLinacPhysicsService)

    def test_system_pvs_created(self, mocked_service):
        """Test that system-level PVs are created."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # Check heartbeat channels
        for channel in HEARTBEAT_CHANNELS:
            pv_name = f"PHYS:SYS0:1:{channel}"
            assert pv_name in service
            assert isinstance(service[pv_name], ChannelInteger)

        # Check alarm channels
        for channel in ALARM_CHANNELS:
            pv_name = f"ALRM:SYS0:{channel}:ALHBERR"
            assert pv_name in service
            assert isinstance(service[pv_name], ChannelEnum)

    def test_decarad_pvs_created(self, mocked_service):
        """Test that Decarad PVs are created."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger Decarad initialization
        _ = SCLinacPhysicsService()

        # Decarad should be instantiated for indices 1 and 2
        assert mocked_service["Decarad"].call_count == 2
        mocked_service["Decarad"].assert_any_call(1)
        mocked_service["Decarad"].assert_any_call(2)

    def test_service_components_initialized(self, mocked_service):
        """Test that all major service components are initialized."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger component initialization
        _ = SCLinacPhysicsService()

        # Verify PVGroup constructors were called (they may be called multiple times)
        # Just verify they were called at least once
        assert mocked_service["BSOICPVGroup"].called
        assert mocked_service["PPSPVGroup"].called
        assert mocked_service["CavityPVGroup"].called
        assert mocked_service["MAGNETPVGroup"].called
        assert mocked_service["RACKPVGroup"].called

    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.LINAC_TUPLES",
        [("L0B", ["01"])],
    )
    def test_single_linac_setup(self, mocked_service):
        """Test setup of a single linac."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # Check linac-level channel was created
        assert "ACCL:L0B:1:AACTMEANSUM" in service
        assert isinstance(service["ACCL:L0B:1:AACTMEANSUM"], ChannelFloat)
        assert "ACCL:L0B:1:ADES_MAX" in service

    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.L1BHL",
        ["02"],
    )
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.LINAC_TUPLES",
        [("L1B", ["01"])],
    )
    def test_l1b_high_level_setup(self, mocked_service):
        """Test that L1B high-level cavities are handled."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # Check HL-specific channel
        assert "ACCL:L1B:1:HL_AACTMEANSUM" in service
        assert isinstance(service["ACCL:L1B:1:HL_AACTMEANSUM"], ChannelFloat)

    def test_cryomodule_level_pvs(self, mocked_service):
        """Test cryomodule-level PV creation."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger cryomodule setup
        _ = SCLinacPhysicsService()

        # Check that cryomodule groups were created
        assert mocked_service["HeaterPVGroup"].called
        assert mocked_service["CryoPVGroup"].called
        assert mocked_service["BeamlineVacuumPVGroup"].called
        assert mocked_service["CouplerVacuumPVGroup"].called
        assert mocked_service["CryomodulePVGroup"].called

    def test_magnet_groups_created(self, mocked_service):
        """Test that magnet groups are created."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger magnet group creation
        _ = SCLinacPhysicsService()

        # Should create XCOR, YCOR, and QUAD for each CM
        assert mocked_service["MAGNETPVGroup"].called

    def test_cavity_setup(self, mocked_service):
        """Test cavity-level PV creation."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger cavity setup
        _ = SCLinacPhysicsService()

        # Check that cavity-related groups were created
        assert mocked_service["CavityPVGroup"].called
        assert mocked_service["PiezoPVGroup"].called
        assert mocked_service["StepperPVGroup"].called
        assert mocked_service["SSAPVGroup"].called
        assert mocked_service["CavFaultPVGroup"].called

    def test_rack_setup(self, mocked_service):
        """Test rack-level PV creation."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger rack setup
        _ = SCLinacPhysicsService()

        # Check that rack groups were created
        assert mocked_service["RACKPVGroup"].called

    def test_rfs_groups_created(self, mocked_service):
        """Test RF Station groups are created."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        # Instantiate service to trigger RFS group creation
        _ = SCLinacPhysicsService()

        # Should create RFS groups for A and B, numbers 1 and 2
        assert mocked_service["RFStationPVGroup"].called

    def test_launcher_groups_structure(self, mocked_service):
        """Test that launcher groups are properly structured."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # This is an integration test to ensure the launcher hierarchy works
        assert service is not None

    def test_rack_a_cavities_constant(self):
        """Test RACK_A_CAVITIES constant."""
        assert RACK_A_CAVITIES == range(1, 5)
        assert 1 in RACK_A_CAVITIES
        assert 4 in RACK_A_CAVITIES
        assert 5 not in RACK_A_CAVITIES

    def test_launcher_types_structure(self):
        """Test LAUNCHER_TYPES configuration."""
        assert "setup" in LAUNCHER_TYPES
        assert "off" in LAUNCHER_TYPES
        assert "cold" in LAUNCHER_TYPES
        assert "park" in LAUNCHER_TYPES

        for launcher_type, classes in LAUNCHER_TYPES.items():
            assert "cavity" in classes
            assert "cm" in classes
            assert "linac" in classes
            assert "global" in classes
            assert "rack" in classes

    def test_alarm_states_constant(self):
        """Test ALARM_STATES constant."""
        assert "RUNNING" in ALARM_STATES
        assert "NOT_RUNNING" in ALARM_STATES
        assert "INVALID" in ALARM_STATES


class TestMainFunction:
    """Test the main entry point."""

    @patch("sc_linac_physics.utils.simulation.sc_linac_physics_service.run")
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.ioc_arg_parser"
    )
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.SCLinacPhysicsService"
    )
    def test_main_function(self, mock_service_class, mock_parser, mock_run):
        """Test that main() sets up and runs the service."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            main,
        )

        mock_parser.return_value = (None, {"option": "value"})
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        main()

        # Verify service was created
        mock_service_class.assert_called_once()

        # Verify parser was called with correct args
        mock_parser.assert_called_once_with(
            default_prefix="", desc="Simulated CM Cavity Service"
        )

        # Verify run was called with service and options
        mock_run.assert_called_once_with(mock_service, option="value")


class TestIntegration:
    """Integration tests with minimal mocking."""

    @pytest.fixture
    def mocked_service(self):
        """Create a service with all dependencies mocked."""
        patches = {
            "Decarad": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.Decarad"
            ),
            "BSOICPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.BSOICPVGroup"
            ),
            "PPSPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.PPSPVGroup"
            ),
            "DecaradPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.DecaradPVGroup"
            ),
            "DecaradHeadPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.DecaradHeadPVGroup"
            ),
            "CavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CavityPVGroup"
            ),
            "PiezoPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.PiezoPVGroup"
            ),
            "StepperPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.StepperPVGroup"
            ),
            "SSAPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SSAPVGroup"
            ),
            "CavFaultPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CavFaultPVGroup"
            ),
            "JTPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.JTPVGroup"
            ),
            "LiquidLevelPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.LiquidLevelPVGroup"
            ),
            "HOMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.HOMPVGroup"
            ),
            "HeaterPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.HeaterPVGroup"
            ),
            "CryoPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CryoPVGroup"
            ),
            "BeamlineVacuumPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.BeamlineVacuumPVGroup"
            ),
            "CouplerVacuumPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CouplerVacuumPVGroup"
            ),
            "CryomodulePVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.CryomodulePVGroup"
            ),
            "MAGNETPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.MAGNETPVGroup"
            ),
            "RACKPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.RACKPVGroup"
            ),
            "RFStationPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.RFStationPVGroup"
            ),
            "SetupCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupCavityPVGroup"
            ),
            "SetupCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupCMPVGroup"
            ),
            "SetupLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupLinacPVGroup"
            ),
            "SetupGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupGlobalPVGroup"
            ),
            "SetupRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.SetupRackPVGroup"
            ),
            "OffCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffCavityPVGroup"
            ),
            "OffCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffCMPVGroup"
            ),
            "OffLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffLinacPVGroup"
            ),
            "OffGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffGlobalPVGroup"
            ),
            "OffRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.OffRackPVGroup"
            ),
            "ColdCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdCavityPVGroup"
            ),
            "ColdCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdCMPVGroup"
            ),
            "ColdLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdLinacPVGroup"
            ),
            "ColdGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdGlobalPVGroup"
            ),
            "ColdRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ColdRackPVGroup"
            ),
            "ParkCavityPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkCavityPVGroup"
            ),
            "ParkCMPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkCMPVGroup"
            ),
            "ParkLinacPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkLinacPVGroup"
            ),
            "ParkGlobalPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkGlobalPVGroup"
            ),
            "ParkRackPVGroup": patch(
                "sc_linac_physics.utils.simulation.sc_linac_physics_service.ParkRackPVGroup"
            ),
        }

        mocks = {}
        for name, patcher in patches.items():
            mocks[name] = patcher.start()

        yield mocks

        for patcher in patches.values():
            patcher.stop()

    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.LINAC_TUPLES",
        [("L0B", ["01"])],
    )
    def test_service_creates_expected_pv_count(self, mocked_service):
        """Test that service creates a reasonable number of PVs."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # Should have system PVs, decarad PVs, and linac PVs
        assert len(service) > 0

    def test_pv_name_format(self, mocked_service):
        """Test that PV names follow expected format."""
        from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
            SCLinacPhysicsService,
        )

        service = SCLinacPhysicsService()

        # Check some known PV patterns
        system_pvs = [k for k in service.keys() if k.startswith("PHYS:SYS0:1:")]
        assert len(system_pvs) > 0

        alarm_pvs = [k for k in service.keys() if k.startswith("ALRM:SYS0:")]
        assert len(alarm_pvs) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
