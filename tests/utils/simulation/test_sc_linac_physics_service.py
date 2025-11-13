from unittest.mock import patch, MagicMock

import pytest
from caproto import ChannelEnum, ChannelFloat, ChannelInteger

from sc_linac_physics.utils.sc_linac.linac_utils import (
    LINAC_TUPLES,
)
from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
    SCLinacPhysicsService,
    main,
)


# Create a fixture that mocks all the expensive PVGroup imports
@pytest.fixture(autouse=True)
def mock_all_pvgroups():
    """Mock all PVGroup classes to speed up tests"""
    with patch.multiple(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service",
        CavityPVGroup=MagicMock(return_value=MagicMock()),
        SSAPVGroup=MagicMock(return_value=MagicMock()),
        PiezoPVGroup=MagicMock(return_value=MagicMock()),
        StepperPVGroup=MagicMock(return_value=MagicMock()),
        CavFaultPVGroup=MagicMock(return_value=MagicMock()),
        HeaterPVGroup=MagicMock(return_value=MagicMock()),
        JTPVGroup=MagicMock(return_value=MagicMock()),
        LiquidLevelPVGroup=MagicMock(return_value=MagicMock()),
        CryoPVGroup=MagicMock(return_value=MagicMock()),
        CryomodulePVGroup=MagicMock(return_value=MagicMock()),
        HOMPVGroup=MagicMock(return_value=MagicMock()),
        DecaradPVGroup=MagicMock(return_value=MagicMock()),
        DecaradHeadPVGroup=MagicMock(return_value=MagicMock()),
        PPSPVGroup=MagicMock(return_value=MagicMock()),
        BSOICPVGroup=MagicMock(return_value=MagicMock()),
        BeamlineVacuumPVGroup=MagicMock(return_value=MagicMock()),
        CouplerVacuumPVGroup=MagicMock(return_value=MagicMock()),
        SetupGlobalPVGroup=MagicMock(return_value=MagicMock()),
        OffGlobalPVGroup=MagicMock(return_value=MagicMock()),
        SetupLinacPVGroup=MagicMock(return_value=MagicMock()),
        OffLinacPVGroup=MagicMock(return_value=MagicMock()),
        SetupCMPVGroup=MagicMock(return_value=MagicMock()),
        OffCMPVGroup=MagicMock(return_value=MagicMock()),
        SetupCavityPVGroup=MagicMock(return_value=MagicMock()),
        OffCavityPVGroup=MagicMock(return_value=MagicMock()),
        MAGNETPVGroup=MagicMock(return_value=MagicMock()),
        RACKPVGroup=MagicMock(return_value=MagicMock()),
        RFStationPVGroup=MagicMock(return_value=MagicMock()),
        Decarad=MagicMock(
            return_value=MagicMock(
                pv_prefix="DCRH:SYS0:1:",
                heads={1: MagicMock(pv_prefix="DCRH:SYS0:1:1:")},
            )
        ),
    ):
        yield


class TestSCLinacPhysicsServiceInitialization:
    """Test that the service initializes correctly"""

    def test_service_can_be_instantiated(self):
        """Test that SCLinacPhysicsService can be created"""
        service = SCLinacPhysicsService()
        assert service is not None

    def test_service_is_service_subclass(self):
        """Test that SCLinacPhysicsService inherits from Service"""
        from sc_linac_physics.utils.simulation.service import Service

        assert issubclass(SCLinacPhysicsService, Service)


class TestHeartbeatPVs:
    """Test heartbeat PV creation"""

    def test_heartbeat_pvs_created(self):
        """Test that all heartbeat PVs are created"""
        service = SCLinacPhysicsService()

        assert "PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT" in service
        assert "PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT" in service
        assert "PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT" in service

    def test_heartbeat_pvs_are_integers(self):
        """Test that heartbeat PVs are ChannelIntegers"""
        service = SCLinacPhysicsService()

        assert isinstance(
            service["PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT"], ChannelInteger
        )
        assert isinstance(
            service["PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT"], ChannelInteger
        )
        assert isinstance(
            service["PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"], ChannelInteger
        )

    def test_heartbeat_pvs_default_to_zero(self):
        """Test that heartbeat PVs default to 0"""
        service = SCLinacPhysicsService()

        assert service["PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT"].value == 0
        assert service["PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT"].value == 0
        assert service["PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"].value == 0


class TestAlarmPVs:
    """Test alarm PV creation"""

    def test_alarm_pvs_created(self):
        """Test that all alarm PVs are created"""
        service = SCLinacPhysicsService()

        assert "ALRM:SYS0:SC_CAV_FAULT:ALHBERR" in service
        assert "ALRM:SYS0:SC_SEL_PHAS_OPT:ALHBERR" in service
        assert "ALRM:SYS0:SC_CAV_QNCH_RESET:ALHBERR" in service

    def test_alarm_pvs_are_enums(self):
        """Test that alarm PVs are ChannelEnums"""
        service = SCLinacPhysicsService()

        assert isinstance(
            service["ALRM:SYS0:SC_CAV_FAULT:ALHBERR"], ChannelEnum
        )

    def test_alarm_pvs_have_correct_enum_strings(self):
        """Test that alarm PVs have correct enum strings"""
        service = SCLinacPhysicsService()

        expected_strings = ("RUNNING", "NOT_RUNNING", "INVALID")
        pv = service["ALRM:SYS0:SC_CAV_FAULT:ALHBERR"]
        assert pv.enum_strings == expected_strings

    def test_alarm_pvs_default_to_running(self):
        """Test that alarm PVs default to RUNNING (0)"""
        service = SCLinacPhysicsService()

        assert service["ALRM:SYS0:SC_CAV_FAULT:ALHBERR"].value == 0


class TestGlobalLaunchers:
    """Test global launcher PV groups"""

    def test_global_launchers_created(self, mock_all_pvgroups):
        """Test that global launchers are created"""
        # Access the mocked classes
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        # Check that SetupGlobalPVGroup was called with prefix and linac_groups
        call_args = sc_linac_physics_service.SetupGlobalPVGroup.call_args
        assert call_args.kwargs["prefix"] == "ACCL:SYS0:SC:"
        assert "linac_groups" in call_args.kwargs
        assert isinstance(call_args.kwargs["linac_groups"], list)
        assert len(call_args.kwargs["linac_groups"]) == 4  # Number of linacs

        # Similarly for OffGlobalPVGroup
        call_args = sc_linac_physics_service.OffGlobalPVGroup.call_args
        assert call_args.kwargs["prefix"] == "ACCL:SYS0:SC:"
        assert "linac_groups" in call_args.kwargs
        assert isinstance(call_args.kwargs["linac_groups"], list)
        assert len(call_args.kwargs["linac_groups"]) == 4  # Number of linacs


class TestLinacPVGroups:
    """Test linac-level PV creation"""

    def test_linac_aactmeansum_created(self):
        """Test that AACTMEANSUM PV is created for each linac"""
        service = SCLinacPhysicsService()

        for linac_idx, (linac_name, _) in enumerate(LINAC_TUPLES):
            pv_name = f"ACCL:{linac_name}:1:AACTMEANSUM"
            assert pv_name in service
            assert isinstance(service[pv_name], ChannelFloat)

    def test_linac_aactmeansum_value(self):
        """Test that AACTMEANSUM values are reasonable"""
        service = SCLinacPhysicsService()

        for linac_idx, (linac_name, cm_list) in enumerate(LINAC_TUPLES):
            pv_name = f"ACCL:{linac_name}:1:AACTMEANSUM"
            actual_value = service[pv_name].value

            # Just verify it's a positive, reasonable value
            assert actual_value > 0, f"{pv_name} should be positive"
            assert actual_value < 5000, f"{pv_name} should be < 5000"
            assert isinstance(
                actual_value, float
            ), f"{pv_name} should be a float"

    def test_linac_ades_max_created(self):
        """Test that ADES_MAX PV is created for each linac"""
        service = SCLinacPhysicsService()

        for _, (linac_name, _) in enumerate(LINAC_TUPLES):
            pv_name = f"ACCL:{linac_name}:1:ADES_MAX"
            assert pv_name in service
            assert service[pv_name].value == 2800.0

    def test_l1b_hl_aactmeansum_created(self):
        """Test that L1B gets HL_AACTMEANSUM PV"""
        service = SCLinacPhysicsService()

        assert "ACCL:L1B:1:HL_AACTMEANSUM" in service
        assert service["ACCL:L1B:1:HL_AACTMEANSUM"].value == 0.0

    def test_linac_launchers_created(self, mock_all_pvgroups):
        """Test that linac launchers are created for each linac"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        # Should be called once per linac
        assert sc_linac_physics_service.SetupLinacPVGroup.call_count == len(
            LINAC_TUPLES
        )
        assert sc_linac_physics_service.OffLinacPVGroup.call_count == len(
            LINAC_TUPLES
        )


class TestCryomodulePVGroups:
    """Test cryomodule-level PV creation"""

    def test_cryo_cas_access_created(self):
        """Test that CAS_ACCESS PV is created for known CMs"""
        service = SCLinacPhysicsService()

        # Just test a few known CMs
        test_cms = ["01", "02", "H1", "04", "16"]

        for cm_name in test_cms:
            pv_name = f"CRYO:CM{cm_name}:0:CAS_ACCESS"
            assert pv_name in service, f"Missing {pv_name}"
            assert isinstance(service[pv_name], ChannelEnum)
            assert service[pv_name].enum_strings == ("Close", "Open")
            assert service[pv_name].value == 1  # Open

    def test_cm_ades_max_created(self):
        """Test that CM-level ADES_MAX is created"""
        service = SCLinacPhysicsService()

        # Test for L0B CM01
        pv_name = "ACCL:L0B:0100:ADES_MAX"
        assert pv_name in service
        assert service[pv_name].value == 168.0

    def test_cm_launchers_created(self, mock_all_pvgroups):
        """Test that CM launchers are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        # Verify they're called the same number of times
        assert (
            sc_linac_physics_service.SetupCMPVGroup.call_count
            == sc_linac_physics_service.OffCMPVGroup.call_count
        )

        # Verify it's a reasonable number
        assert sc_linac_physics_service.SetupCMPVGroup.call_count > 30


class TestCavityPVGroups:
    """Test cavity-level PV creation"""

    def test_cavity_groups_created(self, mock_all_pvgroups):
        """Test that cavity PV groups are created (8 per CM)"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert sc_linac_physics_service.CavityPVGroup.call_count >= 200
        assert sc_linac_physics_service.CavityPVGroup.call_count % 8 == 0

    def test_cavity_launchers_created(self, mock_all_pvgroups):
        """Test that cavity launchers are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert (
            sc_linac_physics_service.SetupCavityPVGroup.call_count
            == sc_linac_physics_service.OffCavityPVGroup.call_count
        )
        assert sc_linac_physics_service.SetupCavityPVGroup.call_count >= 200

    def test_ssa_groups_created(self, mock_all_pvgroups):
        """Test that SSA PV groups are created for each cavity"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert sc_linac_physics_service.SSAPVGroup.call_count >= 200

    def test_ssa_matches_cavity_count(self, mock_all_pvgroups):
        """Test that SSA count matches cavity count"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert (
            sc_linac_physics_service.SSAPVGroup.call_count
            == sc_linac_physics_service.CavityPVGroup.call_count
        )


class TestRackPVGroups:
    """Test rack PV group creation"""

    def test_rack_groups_created(self, mock_all_pvgroups):
        """Test that rack PV groups are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert sc_linac_physics_service.RACKPVGroup.call_count >= 200

    def test_rack_a_and_b_distribution(self, mock_all_pvgroups):
        """Test that cavities 1-4 go to RACKA, 5-8 go to RACKB"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        rack_a_calls = 0
        rack_b_calls = 0

        for call in sc_linac_physics_service.RACKPVGroup.call_args_list:
            prefix = call.kwargs.get(
                "prefix", call.args[0] if call.args else ""
            )
            if "RACKA" in prefix:
                rack_a_calls += 1
            elif "RACKB" in prefix:
                rack_b_calls += 1

        assert rack_a_calls == rack_b_calls
        assert rack_a_calls > 0


class TestRFStationPVGroups:
    """Test RF station PV group creation"""

    def test_rf_station_groups_created(self, mock_all_pvgroups):
        """Test that RF station PV groups are created (2 per cavity)"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert sc_linac_physics_service.RFStationPVGroup.call_count >= 400
        assert sc_linac_physics_service.RFStationPVGroup.call_count % 2 == 0

    def test_rf_station_count_is_double_cavity_count(self, mock_all_pvgroups):
        """Test that there are 2 RF stations per cavity"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert (
            sc_linac_physics_service.RFStationPVGroup.call_count
            == sc_linac_physics_service.CavityPVGroup.call_count * 2
        )

    def test_rf_station_naming(self, mock_all_pvgroups):
        """Test that RF stations are named RFS1A, RFS2A, RFS1B, RFS2B"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        rfs1a_count = 0
        rfs2a_count = 0
        rfs1b_count = 0
        rfs2b_count = 0

        for call in sc_linac_physics_service.RFStationPVGroup.call_args_list:
            prefix = call.kwargs.get(
                "prefix", call.args[0] if call.args else ""
            )
            if "RFS1A" in prefix:
                rfs1a_count += 1
            elif "RFS2A" in prefix:
                rfs2a_count += 1
            elif "RFS1B" in prefix:
                rfs1b_count += 1
            elif "RFS2B" in prefix:
                rfs2b_count += 1

        assert rfs1a_count == rfs2a_count == rfs1b_count == rfs2b_count
        assert rfs1a_count > 0


class TestMagnetPVGroups:
    """Test magnet PV group creation"""

    def test_magnet_groups_created(self, mock_all_pvgroups):
        """Test that magnet PV groups are created (XCOR, YCOR, QUAD per CM)"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert sc_linac_physics_service.MAGNETPVGroup.call_count >= 90
        assert sc_linac_physics_service.MAGNETPVGroup.call_count % 3 == 0

    def test_magnet_types_created(self, mock_all_pvgroups):
        """Test that all three magnet types are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        xcor_count = 0
        ycor_count = 0
        quad_count = 0

        for call in sc_linac_physics_service.MAGNETPVGroup.call_args_list:
            prefix = call.kwargs.get(
                "prefix", call.args[0] if call.args else ""
            )
            if prefix.startswith("XCOR:"):
                xcor_count += 1
            elif prefix.startswith("YCOR:"):
                ycor_count += 1
            elif prefix.startswith("QUAD:"):
                quad_count += 1

        assert xcor_count == ycor_count == quad_count
        assert xcor_count > 0


class TestTunerPVGroups:
    """Test tuner PV group creation"""

    def test_tuner_groups_created(self, mock_all_pvgroups):
        """Test that piezo and stepper groups are created for each cavity"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert (
            sc_linac_physics_service.PiezoPVGroup.call_count
            == sc_linac_physics_service.StepperPVGroup.call_count
        )
        assert sc_linac_physics_service.PiezoPVGroup.call_count >= 200


class TestCryoPVGroups:
    """Test cryo system PV groups"""

    def test_cryo_groups_created(self, mock_all_pvgroups):
        """Test that cryo-related PV groups are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        # Heater and cryo: one per CM
        # JT: one per cavity
        assert (
            sc_linac_physics_service.HeaterPVGroup.call_count
            == sc_linac_physics_service.CryoPVGroup.call_count
        )
        assert (
            sc_linac_physics_service.JTPVGroup.call_count
            == sc_linac_physics_service.CavityPVGroup.call_count
        )
        assert sc_linac_physics_service.HeaterPVGroup.call_count > 30


class TestVacuumPVGroups:
    """Test vacuum PV groups"""

    def test_vacuum_groups_created(self, mock_all_pvgroups):
        """Test that vacuum PV groups are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        assert (
            sc_linac_physics_service.BeamlineVacuumPVGroup.call_count
            == sc_linac_physics_service.CouplerVacuumPVGroup.call_count
        )
        assert sc_linac_physics_service.BeamlineVacuumPVGroup.call_count > 30


class TestFaultPVGroups:
    """Test fault-related PV groups"""

    def test_fault_groups_created(self, mock_all_pvgroups):
        """Test that fault PV groups are created"""
        from sc_linac_physics.utils.simulation import sc_linac_physics_service

        SCLinacPhysicsService()

        # One PPS and BSOIC group total
        sc_linac_physics_service.PPSPVGroup.assert_called_once_with(
            prefix="PPS:SYSW:1:"
        )
        sc_linac_physics_service.BSOICPVGroup.assert_called_once_with(
            prefix="BSOC:SYSW:2:"
        )

        # One cavity fault group per cavity
        assert (
            sc_linac_physics_service.CavFaultPVGroup.call_count
            == sc_linac_physics_service.CavityPVGroup.call_count
        )


class TestMainFunction:
    """Test the main() function"""

    @patch("sc_linac_physics.utils.simulation.sc_linac_physics_service.run")
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.ioc_arg_parser"
    )
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.SCLinacPhysicsService"
    )
    def test_main_creates_service(
        self, mock_service_cls, mock_parser, mock_run
    ):
        """Test that main() creates the service"""
        mock_parser.return_value = (None, {})

        main()

        mock_service_cls.assert_called_once()

    @patch("sc_linac_physics.utils.simulation.sc_linac_physics_service.run")
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.ioc_arg_parser"
    )
    def test_main_calls_run(self, mock_parser, mock_run, mock_all_pvgroups):
        """Test that main() calls run()"""
        mock_parser.return_value = (None, {"some": "options"})

        main()

        mock_run.assert_called_once()

    @patch("sc_linac_physics.utils.simulation.sc_linac_physics_service.run")
    @patch(
        "sc_linac_physics.utils.simulation.sc_linac_physics_service.ioc_arg_parser"
    )
    def test_main_uses_ioc_arg_parser(self, mock_parser, mock_run):
        """Test that main() uses ioc_arg_parser correctly"""
        mock_parser.return_value = (None, {})

        main()

        mock_parser.assert_called_once_with(
            default_prefix="", desc="Simulated CM Cavity Service"
        )
