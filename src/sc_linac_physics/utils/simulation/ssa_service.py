import asyncio
from asyncio import sleep
from random import uniform, random

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyInteger,
    pvproperty,
)

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
    saved_slope: PvpropertyFloat = pvproperty(
        value=0.0, name="SLOPE_SAVE", dtype=ChannelType.FLOAT
    )
    # Enum index read by SSA.rated_power_kw, per
    # linac_utils.SSA_TYPE_RATED_POWER_KW: 0 the 7 kW HE SSA, 2 a standard
    # LCLS-II SSA, 3 the 3.9 GHz HL SSA. The sim picks by cryomodule: HL,
    # then high energy (L4B, Cryomodule.is_high_energy), then standard. The
    # real machine has 191 index-0 SSAs to L4B's 184, plus 4 index-1 HE
    # prototypes, so this is close but not exact.
    ssa_type: PvpropertyInteger = pvproperty(
        value=2, name="Type", dtype=ChannelType.INT
    )

    @ssa_type.startup
    async def ssa_type(self, instance, async_lib):
        if self.cavityGroup.is_hl:
            await instance.write(3)
        elif self.is_high_energy:
            await instance.write(0)

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
    ps_volt_setpt1: PvpropertyFloat = pvproperty(
        name="PSVoltSetpt1", value=2500.0, dtype=ChannelType.FLOAT
    )
    ps_volt_setpt2: PvpropertyFloat = pvproperty(
        name="PSVoltSetpt2", value=2500.0, dtype=ChannelType.FLOAT
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
        SLOPE_NEW, DRV_MAX_NEW and CALSTAT. CALSTAT is Crash with
        CALIBRATION_BAD_RESULT_PROBABILITY, which the model reports as a bad
        result (SSA.calibration_result_good). CALSTS itself always ends at
        Complete.
        """
        await sleep(self.CALIBRATION_DURATION_S)
        await self.slope_new.write(uniform(0.5, 1.5))
        await self.drive_max_new.write(self.drive_max.value)
        if random() < self.CALIBRATION_BAD_RESULT_PROBABILITY:
            await self.cal_stat.write("Crash")
            self.log.warning(f"{self.prefix} SSA calibration result: Crash")
        else:
            await self.cal_stat.write("Success")
        await self.cal_status.write("Complete")
        self.log.info(f"{self.prefix} SSA calibration complete")

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
