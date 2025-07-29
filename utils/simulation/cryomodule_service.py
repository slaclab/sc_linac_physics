from caproto import ChannelType
from caproto.server import PVGroup, pvproperty
from typing import List

from utils.simulation.cavity_service import CavityPVGroup
from utils.simulation.severity_prop import SeverityProp


class CryomodulePVGroup(PVGroup):
    nrp = pvproperty(
        value=0, name="NRP:STATSUMY", dtype=ChannelType.DOUBLE, record="ai"
    )
    aact_mean_sum = pvproperty(value=0, name="AACTMEANSUM")
    # TODO - find this and see what type pv it is on bcs/ops_lcls2_bcs_main.edl
    bcs = pvproperty(value=0, name="BCSDRVSUM", dtype=ChannelType.DOUBLE)

    def __init__(self, prefix):
        super().__init__(prefix=prefix)
        self.cavities: List[CavityPVGroup] = []

    def add_cavity(self, cavity: CavityPVGroup):
        self.cavities.append(cavity)

    @property
    def total_power(self) -> float:
        return sum(cav.power.value for cav in self.cavities)


class HOMPVGroup(PVGroup):
    upstreamHOM = SeverityProp(value=0, name="18:UH:TEMP")
    downstreamHOM = SeverityProp(value=0, name="20:DH:TEMP")
