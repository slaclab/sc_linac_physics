from asyncio import sleep

from caproto import ChannelType
from caproto.server import PVGroup, pvproperty, PvpropertyDouble

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp

_FSCAN_STAT_SEARCH = 3
_FSCAN_STAT_DONE = 5


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
    fscan_freq_start = pvproperty(value=0, name="FSCAN:FREQ_START")
    fscan_freq_stop = pvproperty(value=0, name="FSCAN:FREQ_STOP")
    fscan_thresh = pvproperty(value=0, name="FSCAN:RMS_THRESH")
    fscan_overlap = pvproperty(value=0, name="FSCAN:MODE_OVERLAP")
    fscan_start = pvproperty(value=0, name="FSCAN:START")
    fscan_stat = pvproperty(
        value=0,
        name="FSCAN:STAT",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "Await request",
            "No cav selected",
            "Bad range",
            "Search in progress",
            "Shift mode",
            "Scan done",
            "Scan aborted",
            "Freq restore fail",
        ),
    )
    prl = SeverityProp(value=0, name="PRLSUM")
    pjt: PvpropertyDouble = pvproperty(
        value=0, name="PRLJITSUM", dtype=ChannelType.DOUBLE
    )

    @fscan_start.putter
    async def fscan_start(self, instance, value):
        if value:
            await self.fscan_stat.write(_FSCAN_STAT_SEARCH)
            await sleep(3)
            await self.fscan_stat.write(_FSCAN_STAT_DONE)
        return value
