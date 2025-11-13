from caproto import ChannelEnum, ChannelFloat, ChannelInteger
from caproto.server import ioc_arg_parser, run

from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac_utils import (
    L1BHL,
    LINAC_CM_DICT,
    LINAC_TUPLES,
)
from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.cryo_service import (
    CryoPVGroup,
    HeaterPVGroup,
    JTPVGroup,
    LiquidLevelPVGroup,
)
from sc_linac_physics.utils.simulation.cryomodule_service import (
    CryomodulePVGroup,
    HOMPVGroup,
)
from sc_linac_physics.utils.simulation.decarad_service import (
    DecaradHeadPVGroup,
    DecaradPVGroup,
)
from sc_linac_physics.utils.simulation.fault_service import (
    BeamlineVacuumPVGroup,
    BSOICPVGroup,
    CavFaultPVGroup,
    CouplerVacuumPVGroup,
    PPSPVGroup,
)
from sc_linac_physics.utils.simulation.launcher_service import (
    OffCavityPVGroup,
    OffCMPVGroup,
    OffGlobalPVGroup,
    OffLinacPVGroup,
    SetupCavityPVGroup,
    SetupCMPVGroup,
    SetupGlobalPVGroup,
    SetupLinacPVGroup,
)
from sc_linac_physics.utils.simulation.magnet_service import MAGNETPVGroup
from sc_linac_physics.utils.simulation.rack_service import RACKPVGroup
from sc_linac_physics.utils.simulation.rfs_service import RFStationPVGroup
from sc_linac_physics.utils.simulation.service import Service
from sc_linac_physics.utils.simulation.ssa_service import SSAPVGroup
from sc_linac_physics.utils.simulation.tuner_service import (
    PiezoPVGroup,
    StepperPVGroup,
)

# Constants
HEARTBEAT_CHANNELS = [
    "SC_SEL_PHAS_OPT_HEARTBEAT",
    "SC_CAV_QNCH_RESET_HEARTBEAT",
    "SC_CAV_FAULT_HEARTBEAT",
]

ALARM_CHANNELS = [
    "SC_CAV_FAULT",
    "SC_SEL_PHAS_OPT",
    "SC_CAV_QNCH_RESET",
]

ALARM_STATES = ("RUNNING", "NOT_RUNNING", "INVALID")
RACK_A_CAVITIES = range(1, 5)


class SCLinacPhysicsService(Service):
    def __init__(self):
        super().__init__()
        self._setup_system_pvs()
        self._setup_decarad_pvs()
        self._setup_linac_pvs()

    def _setup_system_pvs(self):
        """Set up system-level PVs for heartbeats and alarms."""
        # Heartbeat channels
        for channel in HEARTBEAT_CHANNELS:
            self[f"PHYS:SYS0:1:{channel}"] = ChannelInteger(value=0)

        # Alarm channels
        for channel in ALARM_CHANNELS:
            self[f"ALRM:SYS0:{channel}:ALHBERR"] = ChannelEnum(
                enum_strings=ALARM_STATES, value=0
            )

        # System-level groups
        self.add_pvs(BSOICPVGroup(prefix="BSOC:SYSW:2:"))
        self.add_pvs(PPSPVGroup(prefix="PPS:SYSW:1:"))

    def _setup_decarad_pvs(self):
        """Set up Decarad-related PVs."""
        for i in [1, 2]:
            decarad = Decarad(i)
            self.add_pvs(DecaradPVGroup(decarad.pv_prefix))
            for head in decarad.heads.values():
                self.add_pvs(DecaradHeadPVGroup(head.pv_prefix))

    def _setup_linac_pvs(self):
        """Set up all linac-related PVs."""
        setup_linac_groups = []
        off_linac_groups = []

        for linac_idx, (linac_name, cm_list) in enumerate(LINAC_TUPLES):
            setup_linac, off_linac = self._setup_single_linac(
                linac_idx, linac_name, cm_list
            )
            setup_linac_groups.append(setup_linac)
            off_linac_groups.append(off_linac)

        # Add global setup/off groups with references to linac groups
        self.add_pvs(
            SetupGlobalPVGroup(
                prefix="ACCL:SYS0:SC:", linac_groups=setup_linac_groups
            )
        )
        self.add_pvs(
            OffGlobalPVGroup(
                prefix="ACCL:SYS0:SC:", linac_groups=off_linac_groups
            )
        )

    def _setup_single_linac(self, linac_idx, linac_name, cm_list):
        """Set up PVs for a single linac.

        Returns:
            tuple: (SetupLinacPVGroup, OffLinacPVGroup)
        """
        linac_prefix = f"ACCL:{linac_name}:1:"

        # Linac-level channels
        self[f"{linac_prefix}AACTMEANSUM"] = ChannelFloat(
            value=len(LINAC_CM_DICT[linac_idx]) * 8 * 16.6
        )
        self[f"{linac_prefix}ADES_MAX"] = ChannelFloat(value=2800.0)

        # Handle L1B high-level cavities
        if linac_name == "L1B":
            cm_list = cm_list + L1BHL
            self[f"{linac_prefix}HL_AACTMEANSUM"] = ChannelFloat(value=0.0)

        # Set up cryomodules and collect setup groups
        setup_cm_groups = []
        off_cm_groups = []

        for cm_name in cm_list:
            setup_cm, off_cm = self._setup_cryomodule(linac_name, cm_name)
            setup_cm_groups.append(setup_cm)
            off_cm_groups.append(off_cm)

        # Create linac-level groups with references to CM groups
        setup_linac = SetupLinacPVGroup(
            prefix=linac_prefix,
            linac_idx=linac_idx,
            cm_groups=setup_cm_groups,
        )
        off_linac = OffLinacPVGroup(
            prefix=linac_prefix,
            linac_idx=linac_idx,
            cm_groups=off_cm_groups,
        )

        self.add_pvs(setup_linac)
        self.add_pvs(off_linac)

        return setup_linac, off_linac

    def _setup_cryomodule(self, linac_name, cm_name):
        """Set up PVs for a single cryomodule.

        Returns:
            tuple: (SetupCMPVGroup, OffCMPVGroup)
        """
        is_hl = cm_name in L1BHL
        cm_prefix = f"ACCL:{linac_name}:{cm_name}"

        # Cryomodule-level channels
        self.add_pvs(HeaterPVGroup(prefix=f"CPIC:CM{cm_name}:0000:EHCV:"))
        self[f"CRYO:CM{cm_name}:0:CAS_ACCESS"] = ChannelEnum(
            enum_strings=("Close", "Open"), value=1
        )
        self[f"{cm_prefix}00:ADES_MAX"] = ChannelFloat(value=168.0)

        # Magnet groups
        magnet_infix = f"{linac_name}:{cm_name}85:"
        for magnet_type in ["XCOR", "YCOR", "QUAD"]:
            self.add_pvs(MAGNETPVGroup(prefix=f"{magnet_type}:{magnet_infix}"))

        # Cryomodule-level groups
        self.add_pvs(CryoPVGroup(prefix=f"CLL:CM{cm_name}:2601:US:"))
        self.add_pvs(BeamlineVacuumPVGroup(prefix=f"{cm_prefix}00:"))
        self.add_pvs(CouplerVacuumPVGroup(prefix=f"{cm_prefix}10:"))
        self.add_pvs(CryomodulePVGroup(prefix=f"{cm_prefix}00:"))

        # Set up cavities and collect setup groups
        setup_cavity_groups = []
        off_cavity_groups = []

        for cav_num in range(1, 9):
            setup_cav, off_cav = self._setup_cavity(
                linac_name, cm_name, cav_num, cm_prefix, is_hl
            )
            setup_cavity_groups.append(setup_cav)
            off_cavity_groups.append(off_cav)

        # Create CM-level groups with references to cavity groups
        setup_cm = SetupCMPVGroup(
            prefix=f"{cm_prefix}00:",
            cm_name=cm_name,
            cavity_groups=setup_cavity_groups,
        )
        off_cm = OffCMPVGroup(
            prefix=f"{cm_prefix}00:",
            cm_name=cm_name,
            cavity_groups=off_cavity_groups,
        )

        self.add_pvs(setup_cm)
        self.add_pvs(off_cm)

        return setup_cm, off_cm

    def _setup_cavity(self, linac_name, cm_name, cav_num, cm_prefix, is_hl):
        """Set up PVs for a single cavity.

        Returns:
            tuple: (SetupCavityPVGroup, OffCavityPVGroup)
        """
        cav_prefix = f"{cm_prefix}{cav_num}0:"

        # Cavity group
        cavity_group = CavityPVGroup(prefix=cav_prefix, isHL=is_hl)
        self.add_pvs(cavity_group)

        # Tuner groups
        piezo_group = PiezoPVGroup(
            prefix=f"{cav_prefix}PZT:", cavity_group=cavity_group
        )
        self.add_pvs(piezo_group)
        self.add_pvs(
            StepperPVGroup(
                prefix=f"{cav_prefix}STEP:",
                cavity_group=cavity_group,
                piezo_group=piezo_group,
            )
        )

        # Other cavity-related groups
        self.add_pvs(
            SSAPVGroup(prefix=f"{cav_prefix}SSA:", cavityGroup=cavity_group)
        )
        self.add_pvs(CavFaultPVGroup(prefix=cav_prefix))
        self.add_pvs(JTPVGroup(prefix=f"CLIC:CM{cm_name}:3001:PVJT:"))
        self.add_pvs(LiquidLevelPVGroup(prefix=f"CLL:CM{cm_name}:"))
        self.add_pvs(HOMPVGroup(prefix=f"CTE:CM{cm_name}:1{cav_num}"))

        # Rack-specific setup
        self._setup_rack_and_rfs(cav_num, cm_prefix)

        # Create cavity-level setup/off groups
        setup_cavity = SetupCavityPVGroup(
            prefix=cav_prefix,
            cm_name=cm_name,
            cav_num=cav_num,
        )
        off_cavity = OffCavityPVGroup(
            prefix=cav_prefix,
            cm_name=cm_name,
            cav_num=cav_num,
        )

        self.add_pvs(setup_cavity)
        self.add_pvs(off_cavity)

        return setup_cavity, off_cavity

    def _setup_rack_and_rfs(self, cav_num, cm_prefix):
        """Set up rack and RFS PVs based on cavity number."""
        if cav_num in RACK_A_CAVITIES:
            rack_suffix = "RACKA:"
            rfs_infix = "A:"
        else:
            rack_suffix = "RACKB:"
            rfs_infix = "B:"

        self.add_pvs(RACKPVGroup(prefix=f"{cm_prefix}00:{rack_suffix}"))

        for rfs_num in [1, 2]:
            self.add_pvs(
                RFStationPVGroup(
                    prefix=f"{cm_prefix}00:RFS{rfs_num}{rfs_infix}"
                )
            )


def main():
    service = SCLinacPhysicsService()
    _, run_options = ioc_arg_parser(
        default_prefix="", desc="Simulated CM Cavity Service"
    )
    run(service, **run_options)


if __name__ == "__main__":
    main()
