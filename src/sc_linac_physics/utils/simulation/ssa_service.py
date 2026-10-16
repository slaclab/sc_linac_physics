import asyncio
from asyncio import sleep
from random import uniform, random

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyDouble,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyInteger,
    pvproperty,
)

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class SSAPVGroup(PVGroup):
    # PowerOn/PowerOff are momentary commands: the sim idles at Standby, and
    # StatusMsg carries the SSA state. (Index 1 reads "Powering On..." on
    # lcls-srv01, 2026-10-14.)
    on: PvpropertyEnum = pvproperty(
        value=0,
        name="PowerOn",
        dtype=ChannelType.ENUM,
        enum_strings=("Standby", "Powering On..."),
    )
    off: PvpropertyEnum = pvproperty(
        value=0,
        name="PowerOff",
        dtype=ChannelType.ENUM,
        enum_strings=("Standby", "Powering Off..."),
    )
    reset: PvpropertyEnum = pvproperty(
        value=0,
        name="FaultReset",
        dtype=ChannelType.ENUM,
        enum_strings=("Standby", "Resetting..."),
    )
    alarm_sum: PvpropertyDouble = pvproperty(
        value=0.0, name="AlarmSummary", dtype=ChannelType.DOUBLE
    )
    status_msg: PvpropertyEnum = pvproperty(
        value=3,
        name="StatusMsg",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "Unknown",
            "SSA Faulted",
            "SSA Off",
            "SSA On",
            "Resetting Faults...",
            "Powering On...",
            "Powering Off...",
            "Fault Reset Failed...",
            "Power On Failed...",
            "Power Off Failed...",
            "Rebooting SSA...",
            "Rebooting X-Port...",
            "Resetting Processor...",
            "SSA Offline",
        ),
    )

    status_480: PvpropertyInteger = pvproperty(
        name="480VACStat", value=0, dtype=ChannelType.LONG
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
        enum_strings=("Good", "Warning", "Error"),
    )
    slope_old: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE", dtype=ChannelType.FLOAT
    )
    slope_new: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE_NEW", dtype=ChannelType.FLOAT
    )
    saved_slope: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE_SAVE", dtype=ChannelType.FLOAT
    )
    # Read by SSA.rated_power_kw, in kW. The sim picks by cryomodule: HL
    # 1 kW, then high energy (L4B, Cryomodule.is_high_energy) 7 kW, then
    # standard 3.8 kW. The real machine also has 7 kW SSAs outside L4B and
    # 4 HE prototypes at 4.6 kW, so this is close but not exact.
    pwr_rating: PvpropertyFloat = pvproperty(
        value=3.8, name="PwrRating", dtype=ChannelType.FLOAT, units="kW"
    )

    @pwr_rating.startup
    async def pwr_rating(self, instance, async_lib):
        if self.cavityGroup.is_hl:
            await instance.write(1.0)
        elif self.is_high_energy:
            await instance.write(7.0)

    drive_max: PvpropertyFloat = pvproperty(
        name="DRV_MAX_REQ", value=0.8, dtype=ChannelType.FLOAT
    )
    drive_max_new: PvpropertyFloat = pvproperty(
        name="DRV_MAX_NEW", value=0.8, dtype=ChannelType.FLOAT
    )
    drive_max_current: PvpropertyFloat = pvproperty(
        name="DRV_MAX", value=0.8, dtype=ChannelType.FLOAT
    )
    drive_max_save: PvpropertyFloat = pvproperty(
        name="DRV_MAX_SAVE", value=0.8, dtype=ChannelType.FLOAT
    )
    power: PvpropertyFloat = pvproperty(
        name="CALPWR", value=4000, dtype=ChannelType.FLOAT
    )
    ps_volt_setpt1: PvpropertyInteger = pvproperty(
        name="PSVoltSetpt1", value=2500, dtype=ChannelType.LONG
    )
    ps_volt_setpt2: PvpropertyInteger = pvproperty(
        name="PSVoltSetpt2", value=2500, dtype=ChannelType.LONG
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

    def __init__(
        self,
        prefix,
        cavityGroup: CavityPVGroup,
        is_high_energy: bool = False,
    ):
        super().__init__(prefix)
        self.cavityGroup: CavityPVGroup = cavityGroup
        self.is_high_energy = is_high_energy
        self._calibration_task: asyncio.Task | None = None
        # Held from the running check until the task exists. The status write
        # in between yields, so without it two starts could both pass.
        self._calibration_start_lock = asyncio.Lock()

    CALIBRATION_DURATION_S = 5
    CALIBRATION_BAD_RESULT_PROBABILITY = 0.2

    @cal_start.putter
    async def cal_start(self, instance, value):
        """Start a simulated SSA calibration; the put returns at once.

        Sets CALSTS to Running here and finishes the run in a task, so the
        client can poll CALSTS meanwhile. A start while one is running is
        ignored. Returns 0, the same CALSTRT readback as PROBECALSTRT.
        """
        async with self._calibration_start_lock:
            if (
                self._calibration_task is not None
                and not self._calibration_task.done()
            ):
                self.log.warning(
                    f"{self.prefix} SSA calibration already running; "
                    "start ignored"
                )
                return 0
            self.log.info(f"{self.prefix} SSA calibration started")
            await self.cal_status.write("Running")
            self._calibration_task = asyncio.get_running_loop().create_task(
                self._finish_calibration()
            )
        return 0

    async def _finish_calibration(self):
        """Write the results, then CALSTS Complete.

        Results come first so a client that sees Complete reads this run's
        SLOPE_NEW, DRV_MAX_NEW and CALSTAT. CALSTAT is Error with
        CALIBRATION_BAD_RESULT_PROBABILITY, which the model reports as a bad
        result (SSA.calibration_result_good). CALSTS itself always ends at
        Complete.
        """
        await sleep(self.CALIBRATION_DURATION_S)
        await self.slope_new.write(uniform(0.5, 1.5))
        await self.drive_max_new.write(self.drive_max.value)
        if random() < self.CALIBRATION_BAD_RESULT_PROBABILITY:
            await self.cal_stat.write("Error")
            self.log.warning(f"{self.prefix} SSA calibration result: Error")
        else:
            await self.cal_stat.write("Good")
        await self.cal_status.write("Complete")
        self.log.info(f"{self.prefix} SSA calibration complete")

    @on.putter
    async def on(self, instance, value):
        if value == "Powering On..." and self.status_msg.value != "SSA On":
            print("Turning SSA on")
            await self.status_msg.write("Resetting Faults...")
            await self.status_msg.write("Powering On...")
            await self.status_msg.write("SSA On")
            print(self.status_msg.value)
            await self.off.write("Standby")
            if self.cavityGroup.rf_state_des.value == "On":
                await self.cavityGroup.power_on()
        # Momentary command: PowerOn reads back Standby once handled.
        return 0

    @off.putter
    async def off(self, instance, value):
        if value == "Powering Off..." and self.status_msg.value != "SSA Off":
            print("Turning SSA off")
            await self.status_msg.write("Powering Off...")
            await self.status_msg.write("SSA Off")
            print(self.status_msg.value)
            await self.on.write("Standby")
            await self.cavityGroup.power_off()
        return 0
