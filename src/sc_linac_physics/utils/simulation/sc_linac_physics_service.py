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
    SetupCavityPVGroup,
    SetupCMPVGroup,
    SetupGlobalPVGroup,
    SetupLinacPVGroup,
    OffCavityPVGroup,
    OffCMPVGroup,
    OffGlobalPVGroup,
    OffLinacPVGroup,
    ColdCavityPVGroup,
    ColdCMPVGroup,
    ColdGlobalPVGroup,
    ColdLinacPVGroup,
    ParkCavityPVGroup,
    ParkCMPVGroup,
    ParkGlobalPVGroup,
    ParkLinacPVGroup,
    ColdRackPVGroup,
    ParkRackPVGroup,
    SetupRackPVGroup,
    OffRackPVGroup,
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

# Launcher type configuration
# Launcher type configuration
LAUNCHER_TYPES = {
    "setup": {
        "cavity": SetupCavityPVGroup,
        "cm": SetupCMPVGroup,
        "linac": SetupLinacPVGroup,
        "global": SetupGlobalPVGroup,
        "rack": SetupRackPVGroup,
    },
    "off": {
        "cavity": OffCavityPVGroup,
        "cm": OffCMPVGroup,
        "linac": OffLinacPVGroup,
        "global": OffGlobalPVGroup,
        "rack": OffRackPVGroup,
    },
    "cold": {
        "cavity": ColdCavityPVGroup,
        "cm": ColdCMPVGroup,
        "linac": ColdLinacPVGroup,
        "global": ColdGlobalPVGroup,
        "rack": ColdRackPVGroup,
    },
    "park": {
        "cavity": ParkCavityPVGroup,
        "cm": ParkCMPVGroup,
        "linac": ParkLinacPVGroup,
        "global": ParkGlobalPVGroup,
        "rack": ParkRackPVGroup,
    },
}


class LauncherGroups:
    """Container for launcher groups at a specific level"""

    def __init__(self):
        self.setup = None
        self.off = None
        self.cold = None
        self.park = None

    def set(self, launcher_type, group):
        """Set a launcher group by type name"""
        setattr(self, launcher_type, group)

    def get(self, launcher_type):
        """Get a launcher group by type name"""
        return getattr(self, launcher_type)

    def all(self):
        """Return all launcher groups as a list"""
        return [self.setup, self.off, self.cold, self.park]

    def by_type(self):
        """Return dict of launcher type -> group"""
        return {
            "setup": self.setup,
            "off": self.off,
            "cold": self.cold,
            "park": self.park,
        }


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
        linac_launchers = LauncherGroups()

        for linac_idx, (linac_name, cm_list) in enumerate(LINAC_TUPLES):
            single_linac_launchers = self._setup_single_linac(
                linac_idx, linac_name, cm_list
            )

            # Collect launcher groups by type
            for launcher_type in LAUNCHER_TYPES.keys():
                if linac_launchers.get(launcher_type) is None:
                    linac_launchers.set(launcher_type, [])
                linac_launchers.get(launcher_type).append(
                    single_linac_launchers.get(launcher_type)
                )

        # Add global launcher groups
        for launcher_type, classes in LAUNCHER_TYPES.items():
            global_launcher = classes["global"](
                prefix="ACCL:SYS0:SC:",
                linac_groups=linac_launchers.get(launcher_type),
            )
            self.add_pvs(global_launcher)

    def _setup_single_linac(self, linac_idx, linac_name, cm_list):
        """Set up PVs for a single linac.

        Returns:
            LauncherGroups: Container with all launcher types
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

        # Set up cryomodules and collect launcher groups
        cm_launchers = LauncherGroups()

        for cm_name in cm_list:
            single_cm_launchers = self._setup_cryomodule(linac_name, cm_name)

            for launcher_type in LAUNCHER_TYPES.keys():
                if cm_launchers.get(launcher_type) is None:
                    cm_launchers.set(launcher_type, [])
                cm_launchers.get(launcher_type).append(
                    single_cm_launchers.get(launcher_type)
                )

        # Create linac-level launcher groups
        linac_launchers = LauncherGroups()
        for launcher_type, classes in LAUNCHER_TYPES.items():
            launcher = classes["linac"](
                prefix=linac_prefix,
                linac_idx=linac_idx,
                cm_groups=cm_launchers.get(launcher_type),
            )
            self.add_pvs(launcher)
            linac_launchers.set(launcher_type, launcher)

        return linac_launchers

    def _setup_cryomodule(self, linac_name, cm_name):
        """Set up PVs for a single cryomodule.

        Returns:
            LauncherGroups: Container with all launcher types
        """
        is_hl = cm_name in L1BHL
        cm_prefix = f"ACCL:{linac_name}:{cm_name}"

        # Set up cryomodule-level PVs
        self._setup_cryomodule_level_pvs(cm_name, cm_prefix, linac_name)

        # Set up cavities and collect launcher groups organized by cavity and rack
        cavity_launchers, rack_launchers = self._setup_cavities_and_racks(
            linac_name, cm_name, cm_prefix, is_hl
        )

        # Set up rack-level launcher groups
        self._setup_rack_launchers(cm_prefix, cm_name, rack_launchers)

        # Set up RFS groups
        self._setup_rfs_groups(cm_prefix)

        # Create and return CM-level launcher groups
        return self._create_cm_launcher_groups(
            cm_prefix, cm_name, cavity_launchers
        )

    def _setup_cryomodule_level_pvs(self, cm_name, cm_prefix, linac_name):
        """Set up PVs at the cryomodule level."""
        # Cryomodule-level channels
        cm_group = CryomodulePVGroup(prefix=f"{cm_prefix}00:")

        # Store cm_group for cavity registration
        if not hasattr(self, "_cm_group"):
            self._cm_group = {}
        self._cm_group[cm_name] = cm_group

        # liquid level group
        liquid_level_prefix = f"CLL:CM{cm_name}:"
        ll_group = LiquidLevelPVGroup(prefix=liquid_level_prefix)
        self.add_pvs(ll_group)
        if cm_group:
            cm_group.ll_group = ll_group

        # heater group
        heater_prefix = f"CPIC:CM{cm_name}:0000:EHCV:"
        heater_group = HeaterPVGroup(prefix=heater_prefix, cm_group=cm_group)
        self.add_pvs(heater_group)

        # Register heater with its cryomodule
        if cm_group:
            cm_group.heater = heater_group

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
        self.add_pvs(cm_group)

    def _setup_cavities_and_racks(self, linac_name, cm_name, cm_prefix, is_hl):
        """Set up all cavities and organize launcher groups by cavity and rack.

        Returns:
            tuple: (cavity_launchers, rack_launchers) where rack_launchers is a dict
                   with keys 'A' and 'B'
        """
        cavity_launchers = LauncherGroups()
        rack_launchers = {"A": LauncherGroups(), "B": LauncherGroups()}

        for cav_num in range(1, 9):
            single_cavity_launchers = self._setup_cavity(
                linac_name, cm_name, cav_num, cm_prefix, is_hl
            )

            # Determine which rack this cavity belongs to
            rack_key = "A" if cav_num in RACK_A_CAVITIES else "B"

            # Collect launcher groups
            for launcher_type in LAUNCHER_TYPES.keys():
                # Initialize if needed
                if cavity_launchers.get(launcher_type) is None:
                    cavity_launchers.set(launcher_type, [])
                if rack_launchers[rack_key].get(launcher_type) is None:
                    rack_launchers[rack_key].set(launcher_type, [])

                # Append to both cavity and rack collections
                launcher = single_cavity_launchers.get(launcher_type)
                cavity_launchers.get(launcher_type).append(launcher)
                rack_launchers[rack_key].get(launcher_type).append(launcher)

        return cavity_launchers, rack_launchers

    def _setup_rack_launchers(self, cm_prefix, cm_name, rack_launchers):
        """Set up rack-level PVs and launcher groups.

        Args:
            cm_prefix: Cryomodule prefix string
            cm_name: Cryomodule name
            rack_launchers: Dict with keys 'A' and 'B' containing LauncherGroups
        """
        rack_config = [
            ("RACKA:", "A"),
            ("RACKB:", "B"),
        ]

        for rack_suffix, rack_letter in rack_config:
            rack_prefix = f"{cm_prefix}00:{rack_suffix}"
            self.add_pvs(RACKPVGroup(prefix=rack_prefix))

            # Create rack launcher groups for each launcher type
            for launcher_type, classes in LAUNCHER_TYPES.items():
                launcher = classes["rack"](
                    prefix=rack_prefix,
                    cm_name=cm_name,
                    rack_name=rack_letter,
                    rack_groups=rack_launchers[rack_letter].get(launcher_type),
                )
                self.add_pvs(launcher)

    def _setup_rfs_groups(self, cm_prefix):
        """Set up RF Station groups for the cryomodule."""
        for rfs_infix in ["A:", "B:"]:
            for rfs_num in [1, 2]:
                self.add_pvs(
                    RFStationPVGroup(
                        prefix=f"{cm_prefix}00:RFS{rfs_num}{rfs_infix}"
                    )
                )

    def _create_cm_launcher_groups(self, cm_prefix, cm_name, cavity_launchers):
        """Create and add CM-level launcher groups.

        Returns:
            LauncherGroups: Container with all launcher types at CM level
        """
        cm_launchers = LauncherGroups()
        for launcher_type, classes in LAUNCHER_TYPES.items():
            launcher = classes["cm"](
                prefix=f"{cm_prefix}00:",
                cm_name=cm_name,
                cavity_groups=cavity_launchers.get(launcher_type),
            )
            self.add_pvs(launcher)
            cm_launchers.set(launcher_type, launcher)

        return cm_launchers

    def _setup_cavity(self, linac_name, cm_name, cav_num, cm_prefix, is_hl):
        """Set up PVs for a single cavity.

        Returns:
            LauncherGroups: Container with all launcher types
        """
        cav_prefix = f"{cm_prefix}{cav_num}0:"
        # Get the cryomodule group
        cm_group = self._cm_group.get(cm_name)

        # Cavity group
        cavity_group = CavityPVGroup(
            prefix=cav_prefix, isHL=is_hl, cm_group=cm_group
        )
        self.add_pvs(cavity_group)

        # Register cavity with its cryomodule
        if cm_group:
            cm_group.cavities[cav_num] = cavity_group

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
        jt_prefix = f"CLIC:CM{cm_name}:3001:PVJT:"
        jt_group = JTPVGroup(prefix=jt_prefix, cm_group=cm_group)
        self.add_pvs(jt_group)
        self.add_pvs(HOMPVGroup(prefix=f"CTE:CM{cm_name}:1{cav_num}"))

        # Note: Rack and RFS setup moved to CM level

        # Create cavity-level launcher groups
        cavity_launchers = LauncherGroups()
        for launcher_type, classes in LAUNCHER_TYPES.items():
            launcher = classes["cavity"](
                prefix=cav_prefix,
                cm_name=cm_name,
                cav_num=cav_num,
            )
            self.add_pvs(launcher)
            cavity_launchers.set(launcher_type, launcher)

        return cavity_launchers


def main():
    service = SCLinacPhysicsService()
    _, run_options = ioc_arg_parser(
        default_prefix="", desc="Simulated CM Cavity Service"
    )
    run(service, **run_options)


if __name__ == "__main__":
    main()
