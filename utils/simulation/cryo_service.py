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

    @mode.putter
    async def mode(self, instance, value):
        if value == 1:
            await self.trigger_heater_sequencer()

    @readback.putter
    async def readback(self, instance, value):
        await self.jt_group.trigger_jt_man_feedback()


class JTPVGroup(PVGroup):
    def __init__(self, prefix, ll_group, heater_group):
        super().__init__(prefix)
        self.ll_group: LiquidLevelPVGroup = ll_group
        self.heater_group: HeaterPVGroup = heater_group

    readback = pvproperty(name="ORBV", value=30.0)
    ds_setpoint = pvproperty(
        name="SP_RQST", value=30.0
    )  # I'm actually a little confused about this PV.
    # Is this the actual liquid level setpoint or the jt position for that liquid level?
    manual = pvproperty(name="MANUAL", value=0)
    auto = pvproperty(name="AUTO", value=0)
    mode = pvproperty(name="MODE", value=0)
    man_pos = pvproperty(name="MANPOS_RQST", value=40.0)
    mode_string: PvpropertyString = pvproperty(name="MODE_STRING", value="AUTO")

    async def trigger_jt_auto_feedback(self):
        while self.ll_group.downstream.value != self.ds_setpoint.value:
            print("Waiting for liquid level to reach downstream setpoint")
            if self.ll_group.downstream.value > self.ds_setpoint.value:
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.value - 0.2
                )
            elif self.ll_group.downstream.value < self.ds_setpoint.value:
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.value + 0.2
                )
            await sleep(1)
        print(f"Downstream level is at {self.ll_group.downstream.value}")

    # for this function, I'm using the assumption that 48W is the stability point
    # the cryoplant wants to see from RF + heater
    async def trigger_jt_man_feedback(self):
        net_heat_load = (
            10  # The ten is just a placeholder. I think net_heat_load here is
        )
        # Pdiss that I'll calculate using the cavity's Q0
        current_total_heat_load = net_heat_load + self.heater_group.readback.value
        stable_heat_load = 48
        current_jt_pos = self.readback.value
        stable_jt_pos = (
            40  # this is a number I got from calibration files, jt valve seems to be
            # in the range of 35 - 40 when total heat load is 48 W
        )

        # I know there should probably be some sort of looping behavior for the following if-else blocks
        # I'm still thinking through what would make sense for the loop conditions
        if (
            current_total_heat_load != stable_heat_load
            and current_jt_pos == stable_jt_pos
        ):
            ll_slope = (
                8.174374050765241e-05 * net_heat_load
            )  # I'm using net_heat_load here because from my understanding, the calibration curve
            # is a relationship between rate of change in liquid level and the rf heat load for that cavity
            # and not between dll/dt and
            # total heat load as seen by the cryoplant
            if (
                current_total_heat_load < stable_heat_load
            ):  # if total heat load is less than stability point then
                # decrease rate of change of liquid helium supply
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.value - ll_slope
                )
                await sleep(1)

            elif (
                current_total_heat_load > stable_heat_load
            ):  # if total heat load is greater than stability point then
                # increase rate of change of liquid helium supply
                await self.ll_group.downstream.write(
                    self.ll_group.downstream.value + ll_slope
                )
                await sleep(1)

        elif (
            current_total_heat_load == stable_heat_load
            and current_jt_pos != stable_jt_pos
        ):
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
            await self.trigger_jt_auto_feedback()

    @readback.putter
    async def readback(self, instance, value):
        await self.trigger_jt_man_feedback()

    @ds_setpoint.putter
    async def ds_setpoint(self, instance, value):
        if self.auto != 1:
            await self.readback.write(value)


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
