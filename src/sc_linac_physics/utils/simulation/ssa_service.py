from asyncio import sleep
from random import uniform, random

from caproto import ChannelType
from caproto.server import PVGroup, PvpropertyEnum, pvproperty, PvpropertyFloat

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class SSAPVGroup(PVGroup):
    on: PvpropertyEnum = pvproperty(
        value=1,
        name="PowerOn",
        dtype=ChannelType.ENUM,
        enum_strings=("False", "True"),
    )
    off: PvpropertyEnum = pvproperty(
        value=0,
        name="PowerOff",
        dtype=ChannelType.ENUM,
        enum_strings=("False", "True"),
    )
    reset: PvpropertyEnum = pvproperty(
        value=0,
        name="FaultReset",
        dtype=ChannelType.ENUM,
        enum_strings=("Standby", "Resetting..."),
    )
    alarm_sum: PvpropertyEnum = pvproperty(
        value=0,
        name="AlarmSummary",
        dtype=ChannelType.ENUM,
        enum_strings=("NO_ALARM", "MINOR", "MAJOR", "INVALID"),
    )
    status_msg: PvpropertyEnum = pvproperty(
        value=3,
        name="StatusMsg",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "Unknown",
            "Faulted",
            "SSA Off",
            "SSA On",
            "Resetting Faults...",
            "Powering ON...",
            "Powering Off...",
            "Fault Reset Failed...",
            "Power On Failed...",
            "Power Off Failed...",
            "Rebooting SSA...",
            "Rebooting X-Port...",
            "Resetting Processor...",
        ),
    )

    status_480: PvpropertyEnum = pvproperty(
        name="480VACStat",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Enabled", "Disabled"),
    )

    cal_start: PvpropertyEnum = pvproperty(
        value=0,
        name="CALSTRT",
        dtype=ChannelType.ENUM,
        enum_strings=("Start", "Start"),
    )
    cal_status: PvpropertyEnum = pvproperty(
        value=1,
        name="CALSTS",
        dtype=ChannelType.ENUM,
        enum_strings=("Crash", "Complete", "Running"),
    )
    cal_stat: PvpropertyEnum = pvproperty(
        value=0,
        dtype=ChannelType.ENUM,
        name="CALSTAT",
        enum_strings=("Success", "Crash"),
    )
    slope_old: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE", dtype=ChannelType.FLOAT
    )
    slope_new: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE_NEW", dtype=ChannelType.FLOAT
    )
    drive_max: PvpropertyFloat = pvproperty(
        name="DRV_MAX_REQ", value=0.8, dtype=ChannelType.FLOAT
    )
    drive_max_save: PvpropertyFloat = pvproperty(
        name="DRV_MAX_SAVE", value=0.8, dtype=ChannelType.FLOAT
    )
    power: PvpropertyFloat = pvproperty(
        name="CALPWR", value=4000, dtype=ChannelType.FLOAT
    )

    nirp: PvpropertyEnum = pvproperty(
        value=1,
        name="NRP_PRMT",
        dtype=ChannelType.ENUM,
        enum_strings=("FAULT", "OK"),
    )
    fault_sum: PvpropertyEnum = SeverityProp(
        value=0,
        name="FaultSummary",
    )

    def __init__(self, prefix, cavityGroup: CavityPVGroup):
        super().__init__(prefix)
        self.cavityGroup: CavityPVGroup = cavityGroup

    @cal_start.putter
    async def cal_start(self, instance, value):
        """
        Trying to simulate SSA Calibration with 20% chance of failing. Needs
        some work to make the PV enums are actually right
        """
        await self.cal_status.write("Running")
        print("Calibration Status: ", self.cal_status.value)
        await sleep(5)
        await self.cal_status.write("Complete")
        print("Calibration Status: ", self.cal_status.value)
        await self.slope_new.write(uniform(0.5, 1.5))
        print("New Slope: ", self.slope_new.value)
        if random() < 0.2:
            await self.cal_stat.write("Crash")
            print("Calibration Crashed")
        else:
            await self.cal_stat.write("Success")
            print("Calibration Successful")

    @on.putter
    async def on(self, instance, value):
        if value == "True" and self.status_msg.value != "SSA On":
            print("Turning SSA on")
            await self.status_msg.write("Resetting Faults...")
            await self.status_msg.write("Powering ON...")
            await self.status_msg.write("SSA On")
            print(self.status_msg.value)
            await self.off.write("False")
            if self.cavityGroup.rf_state_des.value == "On":
                await self.cavityGroup.power_on()

    @off.putter
    async def off(self, instance, value):
        if value == "True" and self.status_msg.value != "SSA Off":
            print("Turning SSA off")
            await self.status_msg.write("Powering Off...")
            await self.status_msg.write("SSA Off")
            print(self.status_msg.value)
            await self.on.write("False")
            await self.cavityGroup.power_off()
