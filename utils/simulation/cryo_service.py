from asyncio import sleep

from caproto.server import PVGroup, pvproperty, PvpropertyString, PvpropertyBoolEnum

from utils.simulation.cryomodule_service import CryomodulePVGroup
from utils.simulation.severity_prop import SeverityProp


class HeaterPVGroup(PVGroup):
    def __init__(self, prefix, cm_group, ll_group):
        super().__init__(prefix)
        self.cm_group: CryomodulePVGroup = cm_group
        self.ll_group: LiquidLevelPVGroup = ll_group

    setpoint = pvproperty(name="MANPOS_RQST", value=24.0)
    readback = pvproperty(name="ORBV", value=24.0)
    mode = pvproperty(name="MODE", value=2)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="SEQUENCER")
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL", value=0)
    sequencer: PvpropertyBoolEnum = pvproperty(name="SEQUENCER", value=0)

    stable_heat = 48

    @property
    def total_heat(self):
        total_heat = self.cm_group.total_power + self.readback.value
        return total_heat

    @property
    def net_heat(self):
        net_heat = self.total_heat - self.stable_heat
        return net_heat

    @property
    def ll_delta(self):
        dll_dt = -8.174374050765241e-05 * self.net_heat
        dt = 1  # seconds
        ll_delta = dll_dt * dt
        return ll_delta

    @setpoint.putter
    async def setpoint(self, instance, value):
        if self.sequencer != 1:
            self.readback.value = value
            await self.manual_mode_start()

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

    @sequencer.putter
    async def sequencer(self, instance, value):
        if value == 1:
            await self.mode.write(2)
            await self.mode_string.write("SEQUENCER")

    async def manual_mode_start(self):
        while True:
            if (
                self.ll_group.downstream.value <= self.ll_group.min_ll
                or self.ll_group.downstream.value >= self.ll_group.max_ll
                or self.mode_string.value == "SEQUENCER"
            ):
                break
            await self.ll_group.downstream.write(
                self.ll_group.downstream.value + self.ll_delta
            )
            await sleep(1)


class JTPVGroup(PVGroup):
    def __init__(self, prefix, ll_group, heater_group):
        super().__init__(prefix)
        self.ll_group: LiquidLevelPVGroup = ll_group
        self.heater_group: HeaterPVGroup = heater_group

    readback = pvproperty(name="ORBV", value=30.0)
    ds_setpoint = pvproperty(name="SP_RQST", value=92.0)
    manual = pvproperty(name="MANUAL", value=0)
    auto = pvproperty(name="AUTO", value=0)
    mode = pvproperty(name="MODE", value=0)
    man_pos = pvproperty(name="MANPOS_RQST", value=40.0)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="AUTO")

    async def feedback_start(self):
        delta = 0.2
        target = self.ds_setpoint.value
        actual = self.ll_group.downstream.value
        while abs(target - actual) > delta:
            direction = -0.2 if target - actual > 0 else 0.2
            await self.ll_group.downstream.write(actual + direction)
            await sleep(1)
        await self.ll_group.downstream.write(target)

    async def manual_mode_start(self):
        current_jt_pos = self.readback.value
        stable_jt_pos = 40

        while True:
            if (
                self.ll_group.downstream.value <= self.ll_group.min_ll
                or self.ll_group.downstream.value >= self.ll_group.max_ll
                or self.mode_string.value == "AUTO"
            ):
                break

        def get_jt_direction():
            return -0.2 if current_jt_pos < stable_jt_pos else 0.2

        def get_net_step():
            return self.heater_group.ll_delta + get_jt_direction()

        direction = 0.0  # Default fallback

        if (
            self.heater_group.total_heat != self.heater_group.stable_heat
            and current_jt_pos == stable_jt_pos
        ):
            direction = self.heater_group.ll_delta

        elif (
            self.heater_group.total_heat == self.heater_group.stable_heat
            and current_jt_pos != stable_jt_pos
        ):
            direction = get_jt_direction()

        elif (
            self.heater_group.total_heat != self.heater_group.stable_heat
            and current_jt_pos != stable_jt_pos
        ):
            direction = get_net_step()

        await self.ll_group.downstream.write(self.ll_group.downstream.value + direction)
        await sleep(1)

    @man_pos.putter
    async def man_pos(self, instance, value):
        if self.auto != 1:
            self.readback.value = value
            await self.manual_mode_start()

    @auto.putter
    async def auto(self, instance, value):
        if value == 1:
            await self.manual.write(0)
            await self.mode.write(1)
            await self.mode_string.write("AUTO")

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            await self.auto.write(0)
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

    @ds_setpoint.putter
    async def ds_setpoint(self, instance, value):
        if self.mode_string.value == "AUTO":
            await self.ll_group.downstream.write(value)
            await self.manual_mode_start()
        await self.feedback_start()


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)

    max_ll = 100
    min_ll = 0


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
