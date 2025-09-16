from caproto import ChannelEnum, ChannelFloat, ChannelInteger
from caproto.server import (
    ioc_arg_parser,
    run,
)

from utils.sc_linac.decarad import Decarad
from utils.sc_linac.linac_utils import LINAC_TUPLES, LINAC_CM_DICT, L1BHL
from utils.simulation.auto_setup_service import (
    AutoSetupCMPVGroup,
    AutoSetupLinacPVGroup,
    AutoSetupGlobalPVGroup,
    AutoSetupCavityPVGroup,
)
from utils.simulation.cavity_service import CavityPVGroup
from utils.simulation.cryo_service import (
    HeaterPVGroup,
    JTPVGroup,
    LiquidLevelPVGroup,
    CryoPVGroup,
)
from utils.simulation.cryomodule_service import CryomodulePVGroup, HOMPVGroup
from utils.simulation.decarad_service import DecaradPVGroup, DecaradHeadPVGroup
from utils.simulation.fault_service import (
    CavFaultPVGroup,
    PPSPVGroup,
    BSOICPVGroup,
    BeamlineVacuumPVGroup,
    CouplerVacuumPVGroup,
)
from utils.simulation.magnet_service import MAGNETPVGroup
from utils.simulation.rack_service import RACKPVGroup
from utils.simulation.rfs_service import RFStationPVGroup
from utils.simulation.service import Service
from utils.simulation.ssa_service import SSAPVGroup
from utils.simulation.tuner_service import StepperPVGroup, PiezoPVGroup


class SCLinacPhysicsService(Service):
    def __init__(self):
        super().__init__()
        self["PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT"] = ChannelInteger(value=0)
        self["PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT"] = ChannelInteger(value=0)
        self["PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"] = ChannelInteger(value=0)

        self["ALRM:SYS0:SC_CAV_FAULT:ALHBERR"] = ChannelEnum(
            enum_strings=("RUNNING", "NOT_RUNNING", "INVALID"), value=0
        )
        self["ALRM:SYS0:SC_SEL_PHAS_OPT:ALHBERR"] = ChannelEnum(
            enum_strings=("RUNNING", "NOT_RUNNING", "INVALID"), value=0
        )
        self["ALRM:SYS0:SC_CAV_QNCH_RESET:ALHBERR"] = ChannelEnum(
            enum_strings=("RUNNING", "NOT_RUNNING", "INVALID"), value=0
        )
        self.add_pvs(BSOICPVGroup(prefix="BSOC:SYSW:2:"))

        rackA = range(1, 5)
        self.add_pvs(PPSPVGroup(prefix="PPS:SYSW:1:"))
        self.add_pvs(AutoSetupGlobalPVGroup(prefix="ACCL:SYS0:SC:"))

        for i in [1, 2]:
            decarad = Decarad(i)
            self.add_pvs(DecaradPVGroup(decarad.pv_prefix))
            for head in decarad.heads.values():
                self.add_pvs(DecaradHeadPVGroup(head.pv_prefix))

        for linac_idx, (linac_name, cm_list) in enumerate(LINAC_TUPLES):
            linac_prefix = f"ACCL:{linac_name}:1:"
            self[f"{linac_prefix}AACTMEANSUM"] = ChannelFloat(
                value=len(LINAC_CM_DICT[linac_idx]) * 8 * 16.6
            )
            self[f"{linac_prefix}ADES_MAX"] = ChannelFloat(value=2800.0)
            if linac_name == "L1B":
                cm_list += L1BHL
                self[f"{linac_prefix}HL_AACTMEANSUM"] = ChannelFloat(value=0.0)

            self.add_pvs(
                AutoSetupLinacPVGroup(prefix=linac_prefix, linac_idx=linac_idx)
            )
            for cm_name in cm_list:
                is_hl = cm_name in L1BHL
                heater_prefix = f"CPIC:CM{cm_name}:0000:EHCV:"
                self.add_pvs(HeaterPVGroup(prefix=heater_prefix))

                self[f"CRYO:CM{cm_name}:0:CAS_ACCESS"] = ChannelEnum(
                    enum_strings=("Close", "Open"), value=1
                )
                self[f"ACCL:{linac_name}:{cm_name}00:ADES_MAX"] = ChannelFloat(
                    value=168.0
                )

                cryo_prefix = f"CLL:CM{cm_name}:2601:US:"
                cm_prefix = f"ACCL:{linac_name}:{cm_name}"
                rfs_prefix = cm_prefix + "00:"

                magnet_infix = f"{linac_name}:{cm_name}85:"

                self.add_pvs(MAGNETPVGroup(prefix=f"XCOR:{magnet_infix}"))
                self.add_pvs(MAGNETPVGroup(prefix=f"YCOR:{magnet_infix}"))
                self.add_pvs(MAGNETPVGroup(prefix=f"QUAD:{magnet_infix}"))

                self.add_pvs(
                    AutoSetupCMPVGroup(prefix=cm_prefix + "00:", cm_name=cm_name)
                )

                for cav_num in range(1, 9):
                    cav_prefix = cm_prefix + f"{cav_num}0:"

                    jt_prefix = f"CLIC:CM{cm_name}:3001:PVJT:"
                    liquid_level_prefix = f"CLL:CM{cm_name}:"

                    HOM_prefix = f"CTE:CM{cm_name}:1{cav_num}"

                    cavityGroup = CavityPVGroup(prefix=cav_prefix, isHL=is_hl)
                    self.add_pvs(cavityGroup)
                    self.add_pvs(
                        SSAPVGroup(prefix=cav_prefix + "SSA:", cavityGroup=cavityGroup)
                    )

                    piezo_group = PiezoPVGroup(
                        prefix=cav_prefix + "PZT:", cavity_group=cavityGroup
                    )
                    self.add_pvs(piezo_group)
                    self.add_pvs(
                        StepperPVGroup(
                            prefix=cav_prefix + "STEP:",
                            cavity_group=cavityGroup,
                            piezo_group=piezo_group,
                        )
                    )
                    self.add_pvs(CavFaultPVGroup(prefix=cav_prefix))

                    self.add_pvs(JTPVGroup(prefix=jt_prefix))
                    self.add_pvs(LiquidLevelPVGroup(prefix=liquid_level_prefix))

                    # Rack PVs are stupidly inconsistent
                    if cav_num in rackA:
                        hwi_prefix = cm_prefix + "00:RACKA:"
                        rfs_infix = "A:"
                    else:
                        hwi_prefix = cm_prefix + "00:RACKB:"
                        rfs_infix = "B:"

                    self.add_pvs(RACKPVGroup(prefix=hwi_prefix))
                    self.add_pvs(HOMPVGroup(prefix=HOM_prefix))
                    self.add_pvs(
                        AutoSetupCavityPVGroup(
                            prefix=cav_prefix,
                            cm_name=cm_name,
                            cav_num=cav_num,
                        )
                    )
                    self.add_pvs(RFStationPVGroup(prefix=rfs_prefix + f"RFS1{rfs_infix}"))
                    self.add_pvs(RFStationPVGroup(prefix=rfs_prefix + f"RFS2{rfs_infix}"))

                self.add_pvs(CryoPVGroup(prefix=cryo_prefix))
                self.add_pvs(BeamlineVacuumPVGroup(prefix=cm_prefix + "00:"))
                self.add_pvs(CouplerVacuumPVGroup(prefix=cm_prefix + "10:"))
                self.add_pvs(CryomodulePVGroup(prefix=cm_prefix + "00:"))


def main():
    service = SCLinacPhysicsService()
    _, run_options = ioc_arg_parser(
        default_prefix="", desc="Simulated CM Cavity Service"
    )
    run(service, **run_options)


if __name__ == "__main__":
    main()
