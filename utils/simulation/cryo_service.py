import time
from asyncio import sleep

from caproto.server import PVGroup, pvproperty, PvpropertyString, PvpropertyBoolEnum

from utils.simulation.cavity_service import CavityPVGroup
from utils.simulation.severity_prop import SeverityProp


class HeaterPVGroup(PVGroup):
    def __init__(self, prefix, jt_group, cavity_group):
        super().__init__(prefix)
        self.jt_group: JTPVGroup = jt_group
        self.cavity_group: CavityPVGroup = cavity_group

    setpoint = pvproperty(name="MANPOS_RQST", value=24.0)
    readback = pvproperty(name="ORBV", value=24.0)
    mode = pvproperty(name="MODE", value=1)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="SEQUENCER")
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL")
    sequencer: PvpropertyBoolEnum = pvproperty(name="SEQUENCER")

    @property
    def pdiss(self):
        amplitude = self.cavity_group.amean.value
        q0 = 2.7e10  # will be actual Q0 PV
        pdiss = (amplitude * amplitude) / (1012 * q0)
        return pdiss

    async def trigger_heater_sequencer(self):
        heat = self.pdiss
        heater_power = 48 - heat
        await self.setpoint.write(heater_power)

    @setpoint.putter
    async def setpoint(self, instance, value):
        if self.sequencer != 1:
            self.readback.value = value
            await self.jt_group.trigger_jt_manual_mode()

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

    @sequencer.putter
    async def sequencer(self, instance, value):
        if value == 1:
            await self.mode.write(1)
            await self.mode_string.write("SEQUENCER")

    @mode.putter
    async def mode(self, instance, value):
        if value == 1:
            await self.trigger_heater_sequencer()


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

    @property
    def max_ll(self):
        max_ll = 100
        return max_ll

    @property
    def min_ll(self):
        min_ll = 0
        return min_ll

    @property
    def total_heat(self):
        total_heat = self.heater_group.pdiss + self.heater_group.readback.value
        return total_heat

    @property
    def stable_heat(self):
        stable_heat = 48
        return stable_heat

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

    @property
    def ll_diff(self):
        current = self.ll_group.downstream.value
        target = self.ds_setpoint.value
        ll_diff = current - target
        return ll_diff

    def is_at_setpoint(self):
        current = self.ll_group.downstream.value
        target = self.ds_setpoint.value
        return current == target

    def is_at_max_fill(self):
        current = self.ll_group.downstream.value
        return current >= self.max_ll

    def is_empty(self):
        current = self.ll_group.downstream.value
        return current <= self.min_ll

    # logic behind direction determination
    # Case 1: current > target
    # ll_diff = positive number
    # min(-ll_diff, +ll_delta) ==> returns -ll_diff
    # max(-ll_diff, -ll_delta) ==> returns -ll_diff if |ll_delta| > |ll_diff|, -ll_delta otherwise
    # direction = -some_number
    #############################
    #############################
    # Case 2: current < target
    # ll_diff = negative number
    # min(-ll_diff, +ll_delta) ==> returns +ll_diff if |ll_delta| > |ll_diff|, +ll_delta otherwise
    # max(+ll_diff, -ll_delta) ==> returns +ll_diff if |ll_delta| > |ll_diff|, +ll_delta otherwise
    # direction = +some_number
    #############################
    #############################
    # Case 3: current == target
    # ll_diff = 0
    # min(-ll_diff, +ll_delta) ==> returns 0
    # max(ll_diff, -ll_delta) ==> returns 0
    # direction = 0
    #############################
    #############################
    def get_step_direction(self, ll_delta):
        direction = max(min(-self.ll_diff, ll_delta), -ll_delta)
        return direction

    def get_jt_direction(self):
        current_jt_pos = self.readback.value
        stable_jt_pos = 40
        if current_jt_pos < stable_jt_pos:
            direction = -0.2

        elif current_jt_pos > stable_jt_pos:
            direction = 0.2
        return direction

    def get_net_step(self):
        net_step = self.ll_delta + self.get_jt_direction()
        return net_step

    async def trigger_jt_auto_feedback(self):
        ll_delta = 0.2

        while True:
            current = self.ll_group.downstream.value

            if (
                not self.is_at_setpoint()
                or current == self.max_ll
                or current == self.min_ll
            ):
                break

            direction = self.get_step_direction(ll_delta)
            await self.ll_group.downstream.write(current + direction)
            await sleep(1)

    # I'm using the assumption that 48W is the stability point
    # the cryoplant wants to see in total from RF + heater
    async def trigger_jt_manual_mode(self):
        current_jt_pos = self.readback.value
        stable_jt_pos = 40
        start = time.time()

        while (
            not self.is_at_setpoint
            and not self.is_at_max_fill()
            and not self.is_empty()
            and time.time() - start < 10  # 10s timeout
        ):
            if self.total_heat != self.stable_heat and current_jt_pos == stable_jt_pos:
                direction = self.ll_delta

            elif (
                self.total_heat == self.stable_heat and current_jt_pos != stable_jt_pos
            ):
                direction = self.get_jt_direction()

            elif (
                self.total_heat != self.stable_heat and current_jt_pos != stable_jt_pos
            ):
                direction = self.get_net_step()

            await self.ll_group.downstream.write(
                self.ll_group.downstream.value + direction
            )

            await sleep(1)

    @man_pos.putter
    async def man_pos(self, instance, value):
        if self.auto != 1:
            self.readback.value = value
            await self.trigger_jt_manual_mode()

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

    @mode.putter
    async def mode(self, instance, value):
        if value == 1:
            await self.trigger_jt_auto_feedback()

    @ds_setpoint.putter
    async def ds_setpoint(self, instance, value):
        if self.auto != 1:
            await self.trigger_jt_manual_mode()


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
