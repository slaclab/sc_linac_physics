from caproto import ChannelType
from caproto.server import PVGroup, pvproperty, PvpropertyDouble

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class RACKPVGroup(PVGroup):
    hwi = pvproperty(
        value=0,
        name="HWINITSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "HW Init running", "LLRF chassis problem"),
        record="mbbi",
    )
    fro = pvproperty(
        value=0,
        name="FREQSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Still OK", "Faulted"),
    )
    fscan_start = pvproperty(value=0, name="FSCAN:FREQ_START")
    fscan_stop = pvproperty(value=0, name="FSCAN:FREQ_STOP")
    fscan_thresh = pvproperty(value=0, name="FSCAN:RMS_THRESH")
    fscan_overlap = pvproperty(value=0, name="FSCAN:MODE_OVERLAP")
    prl = SeverityProp(value=0, name="PRLSUM")
    pjt: PvpropertyDouble = pvproperty(
        value=0, name="PRLJITSUM", dtype=ChannelType.DOUBLE
    )
