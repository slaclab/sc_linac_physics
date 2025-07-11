from caproto.server import PVGroup, pvproperty, PvpropertyString, PvpropertyBoolEnum

from applications.q0 import q0_utils
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

    @setpoint.putter
    async def setpoint(self, instance, value):
        await self.readback.write(value)

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

    @readback.putter
    async def readback(self, instance, value):
        await self.jt_group.adjust_liquid_level()


class JTPVGroup(PVGroup):
    def __init__(self, prefix, ll_group, heater_group):
        super().__init__(prefix)
        self.ll_group: LiquidLevelPVGroup = ll_group
        self.heater_group: HeaterPVGroup = heater_group

    readback = pvproperty(name="ORBV", value=30.0)
    ds_setpoint = pvproperty(name="SP_RQST", value=30.0)
    manual = pvproperty(name="MANUAL", value=0)
    auto = pvproperty(name="AUTO", value=0)
    mode = pvproperty(name="MODE", value=0)
    man_pos = pvproperty(name="MANPOS_RQST", value=40.0)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="AUTO")

    async def trigger_jt_feedback(self):
        starting_ll = self.ll_group.downstream.value
        if starting_ll != q0_utils.MAX_DS_LL:
            target_ll_diff = q0_utils.MAX_DS_LL - self.ll_group.downstream.value
            print("Waiting for downstream liquid level to reach 93")
            await self.ll_group.downstream.write(starting_ll + target_ll_diff)
            print(f"Liquid level is at {self.ll_group.downstream.value}")

    async def adjust_liquid_level(self):
        if self.auto == 0:
            jt_steady_state = 40  # baseline JT valve position
            current_pos = self.readback.value
            delta_pos = current_pos - jt_steady_state

            ll_slope = 8.174374050765241e-05 * 10  # assuming Q0 of 2.7e10, we expect heat load of 10W

            # 5 steps of valve movement = 1 unit of liquid level rate of change
            expected_delta = 5 * ll_slope

            if abs(expected_delta) != abs(delta_pos):
                if delta_pos < 0:  # heater is turned down, RF heat load increased. Increase liquid helium level
                    self.man_pos.write(jt_steady_state + expected_delta)
                self.man_pos.write(jt_steady_state - expected_delta)

    @man_pos.putter
    async def man_pos(self, instance, value):
        await self.readback.write(value)

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
            await self.trigger_jt_feedback()

    @readback.putter
    async def readback(self, instance, value):
        await self.adjust_liquid_level()


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
