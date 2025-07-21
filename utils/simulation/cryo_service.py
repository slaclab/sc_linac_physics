from asyncio import sleep

from caproto.server import PVGroup, pvproperty, PvpropertyString, PvpropertyBoolEnum

from utils.simulation.severity_prop import SeverityProp


class HeaterPVGroup(PVGroup):
    def __init__(self, prefix, jt_group):
        super().__init__(prefix)
        self.jt_group: JTPVGroup = jt_group

    setpoint = pvproperty(name="MANPOS_RQST", value=24.0)
    readback = pvproperty(name="ORBV", value=24.0)
    mode = pvproperty(name="MODE", value=1)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="SEQUENCER")
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL")
    sequencer: PvpropertyBoolEnum = pvproperty(name="SEQUENCER")

    async def trigger_heater_sequencer(self):
        heat = 10  # this will be Pdiss calculated using Q0
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

    def calculate_ll_diff(self, current, target):
        return current - target

    # logic behind direction determination
    # Case 1: current > target
    # ll_diff = positive number
    # min(-ll_diff, +ll_delta) ==> returns -ll_diff
    # max(-ll_diff, -ll_delta) ==> returns -ll_diff if |ll_delta| > |ll_diff|, -ll_delta otherwise
    # direction = -some_number
    # Case 2: current < target
    # ll_diff = negative number
    # min(-ll_diff, +ll_delta) ==> returns +ll_diff if |ll_delta| > |ll_diff|, +ll_delta otherwise
    # max(+ll_diff, -ll_delta) ==> returns +ll_diff if |ll_delta| > |ll_diff|, +ll_delta otherwise
    # direction = +some_number
    # Case 3: current == target
    # ll_diff = 0
    # min(-ll_diff, +ll_delta) ==> returns 0
    # max(-ll_diff, -ll_delta) ==> returns 0
    # direction = 0
    def calculate_direction(self, ll_diff, ll_delta, current, target):
        direction = max(min(-ll_diff, ll_delta), -ll_delta)

        return direction

    async def trigger_jt_auto_feedback(self):
        ll_delta = 0.2
        tolerance = 1
        while True:
            current = self.ll_group.downstream.value
            target = self.ds_setpoint.value

            ll_diff = self.calculate_ll_diff(current, target)

            if abs(ll_diff) < tolerance:
                break

            direction = self.calculate_direction(ll_diff, ll_delta, current, target)
            await self.ll_group.downstream.write(current + direction)
            await sleep(1)

    # I'm using the assumption that 48W is the stability point
    # the cryoplant wants to see in total from RF + heater
    async def trigger_jt_manual_mode(self):
        total_heat_load = 10 + self.heater_group.readback.value
        stable_heat_load = 48

        current_jt_pos = self.readback.value
        stable_jt_pos = 40

        tolerance = 0.05

        if total_heat_load != stable_heat_load and current_jt_pos == stable_jt_pos:
            while True:
                net_heat_load = total_heat_load - stable_heat_load
                dll_dt = -8.174374050765241e-05 * net_heat_load
                dt = 1  # seconds
                delta_ll = dll_dt * dt

                if abs(net_heat_load) <= tolerance:
                    break

                await self.ll_group.downstream.write(
                    self.ll_group.downstream.value + delta_ll
                )
                await sleep(dt)

        elif total_heat_load == stable_heat_load and current_jt_pos != stable_jt_pos:
            if current_jt_pos < stable_jt_pos:
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.write - 0.2
                )
                await sleep(1)

            elif current_jt_pos > stable_jt_pos:
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.write + 0.2
                )
                await sleep(1)

    @man_pos.putter
    async def man_pos(self, instance, value):
        if self.auto != 1:
            self.readback.value = value

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
