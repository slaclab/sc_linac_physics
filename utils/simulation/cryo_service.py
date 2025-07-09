from caproto.server import PVGroup, pvproperty, PvpropertyString, PvpropertyBoolEnum

from applications.q0 import q0_utils
from utils.simulation.severity_prop import SeverityProp


class HeaterPVGroup(PVGroup):
    setpoint = pvproperty(name="MANPOS_RQST", value=24.0)
    readback = pvproperty(name="ORBV", value=24.0)
    mode = pvproperty(name="MODE", value=1)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="SEQUENCER")
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL")
    sequencer: PvpropertyBoolEnum = pvproperty(name="SEQUENCER")

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


class JTPVGroup(PVGroup):
    def __init__(self, prefix, ll_group):
        super().__init__(prefix)
        self.ll_group: LiquidLevelPVGroup = ll_group

    readback = pvproperty(name="ORBV", value=30.0)
    ds_setpoint = pvproperty(name="SP_RQST", value=30.0)
    manual = pvproperty(name="MANUAL", value=0)
    auto = pvproperty(name="AUTO", value=0)
    mode = pvproperty(name="MODE", value=0)
    man_pos = pvproperty(name="MANPOS_RQST", value=40.0)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="AUTO")

    async def trigger_jt_feedback_script(self):
        starting_ll = self.ll_group.downstream.value
        if starting_ll != q0_utils.MAX_DS_LL:
            target_ll_diff = q0_utils.MAX_DS_LL - self.ll_group.downstream.value
            print("Waiting for downstream liquid level to reach 93")
            await self.ll_group.downstream.write(starting_ll + target_ll_diff)
            print(f"Liquid level is at {self.ll_group.downstream.value}")

    @man_pos.putter
    async def man_pos(self, instance, value):
        await self.readback.write(value)

    @auto.putter
    async def auto(self, instance, value):
        if value == 1:
            await self.mode.write(1)
            await self.mode_string.write("AUTO")

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

    @mode.putter
    async def mode(self, instance, value):
        if value == 1:
            await self.trigger_jt_feedback_script()


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
