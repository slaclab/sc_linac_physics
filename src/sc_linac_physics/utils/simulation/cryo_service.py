import asyncio
import random
from asyncio import sleep

from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyBoolEnum,
    PvpropertyString,
)

from sc_linac_physics.utils.simulation.cryomodule_service import (
    CryomodulePVGroup,
)
from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class HeaterPVGroup(PVGroup):
    def __init__(self, prefix, cm_group):
        super().__init__(prefix)
        self.cm_group: "CryomodulePVGroup" = cm_group
        self.ll_group: "LiquidLevelPVGroup" = cm_group.ll_group
        self._manual_task = None
        self.async_lib = None

    setpoint = pvproperty(name="MANPOS_RQST", value=0.0, precision=2)
    readback = pvproperty(name="ORBV", value=0.0, precision=2)
    mode = pvproperty(name="MODE", value=2)  # 0=MANUAL, 2=SEQUENCER
    mode_string: PvpropertyString = pvproperty(
        name="MODE_STRING", value="SEQUENCER"
    )
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL", value=0)
    sequencer: PvpropertyBoolEnum = pvproperty(name="SEQUENCER", value=1)

    stable_heat = 48.0  # Watts - baseline heat load

    @property
    def total_heat(self):
        """Total heat = cavity RF power + heater power"""
        return self.cm_group.total_power + self.readback.value

    @property
    def net_heat(self):
        """Net heat relative to stable baseline"""
        if self.mode.value == 2:  # SEQUENCER mode
            return 0.0  # Perfect feedback - no net heat
        else:  # MANUAL mode
            return self.total_heat - self.stable_heat

    @property
    def ll_delta(self):
        """Liquid level change per second based on calibration curve"""
        dll_dt = -8.174374050765241e-05 * self.net_heat  # %/sec
        dt = 1  # seconds
        return dll_dt * dt

    @setpoint.startup
    async def setpoint(self, instance, async_lib):
        self.async_lib = async_lib

    @setpoint.putter
    async def setpoint(self, instance, value):
        if self.mode.value == 0:  # MANUAL mode
            await asyncio.sleep(0.2)
            await self.readback.write(value)
            if self._manual_task:
                self._manual_task.cancel()

            # Start as background task
            self._manual_task = self.async_lib.library.create_task(
                self.manual_mode_start()
            )

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            print("Heater feedback status: Manual")
            await self.sequencer.write(0)
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

    @sequencer.putter
    async def sequencer(self, instance, value):
        if value == 1:
            print("Heater feedback status: Sequencer")
            await self.manual.write(0)
            await self.mode.write(2)
            await self.mode_string.write("SEQUENCER")

    async def manual_mode_start(self):
        """
        Continuously update liquid level based on heat load changes
        Runs while in manual mode and within valid liquid level bounds
        """
        while True:
            # Exit conditions
            if (
                self.ll_group.downstream.value <= self.ll_group.min_ll
                or self.ll_group.downstream.value >= self.ll_group.max_ll
                or self.mode.value != 0  # Not in MANUAL mode
            ):
                break

            # Update liquid level based on net heat
            new_ll = self.ll_group.downstream.value + self.ll_delta
            await self.ll_group.downstream.write(new_ll)

            await sleep(1)


class JTPVGroup(PVGroup):
    """JT Valve control with auto/manual modes"""

    def __init__(self, prefix, cm_group):
        super().__init__(prefix)
        self.cm_group: "CryomodulePVGroup" = cm_group
        self.heater_group: "HeaterPVGroup" = cm_group.heater
        self.ll_group: "LiquidLevelPVGroup" = cm_group.ll_group
        self._auto_task = None
        self._manual_task = None
        self.async_lib = None

    readback = pvproperty(name="ORBV", value=30.0, precision=2)
    ds_setpoint = pvproperty(name="SP_RQST", value=93.0, precision=2)
    manual_pos = pvproperty(name="MANPOS_RQST", value=40.0, precision=2)
    manual: PvpropertyBoolEnum = pvproperty(name="MANUAL", value=0)
    auto: PvpropertyBoolEnum = pvproperty(name="AUTO", value=1)
    mode = pvproperty(name="MODE", value=1, read_only=True)
    mode_string: PvpropertyString = pvproperty(
        name="MODE_STRING", value="AUTO", read_only=True
    )

    stable_jt_pos = 40.0

    @auto.startup
    async def auto(self, instance, async_lib):
        """Initialize auto feedback on startup"""
        self.async_lib = async_lib
        if self.auto.value == 1:
            self._auto_task = async_lib.library.create_task(
                self.auto_feedback_start()
            )

    @manual.putter
    async def manual(self, instance, value):
        if value == 1:
            print("JT valve status: Manual")
            # Update mode
            await self.auto.write(0)
            await self.mode.write(0)
            await self.mode_string.write("MANUAL")

            # Cancel auto feedback
            if self._auto_task:
                self._auto_task.cancel()
                self._auto_task = None

    @auto.putter
    async def auto(self, instance, value):
        if value == 1:
            print("JT valve status: Auto")
            # Update mode
            await self.manual.write(0)
            await self.mode.write(1)
            await self.mode_string.write("AUTO")

            # Cancel any manual tasks
            if self._manual_task:
                self._manual_task.cancel()
                self._manual_task = None

            # Start auto feedback as background task
            if self._auto_task:
                self._auto_task.cancel()
            self._auto_task = self.async_lib.library.create_task(
                self.auto_feedback_start()
            )

    @manual_pos.putter
    async def manual_pos(self, instance, value):
        """When JT position changes in manual mode"""
        if self.mode.value == 0:  # MANUAL mode
            await self.readback.write(value)
            # Start manual mode liquid level updates
            if self._manual_task:
                self._manual_task.cancel()
            self._manual_task = self.async_lib.library.create_task(
                self.manual_mode_start()
            )

    @ds_setpoint.putter
    async def ds_setpoint(self, instance, value):
        """Setpoint change in AUTO mode triggers feedback"""
        if self.mode.value == 1:  # AUTO mode
            # Restart feedback to new setpoint
            if self._auto_task:
                self._auto_task.cancel()
            self._auto_task = self.async_lib.library.create_task(
                self.auto_feedback_start()
            )

    async def auto_feedback_start(self):
        """
        AUTO mode: Walk liquid level to setpoint
        Rate: ~0.2%/sec (randomized between 0.15-0.25)
        """
        while self.mode.value == 1:  # AUTO mode
            target = self.ds_setpoint.value
            actual = self.ll_group.downstream.value
            delta = target - actual

            # Check if we're close enough
            if abs(delta) < 0.2:
                await self.ll_group.downstream.write(target)
                await sleep(1)
                continue

            # Random walk rate between 0.15 and 0.25 %/sec
            rate = random.uniform(0.15, 0.25)
            direction = rate if delta > 0 else -rate

            new_ll = actual + direction

            # Clamp to valid range
            new_ll = max(
                self.ll_group.min_ll, min(self.ll_group.max_ll, new_ll)
            )

            await self.ll_group.downstream.write(new_ll)
            await sleep(1)

    async def manual_mode_start(self):
        """
        MANUAL mode: Update liquid level based on JT position and heat load
        """
        try:
            while True:
                # Exit conditions
                if (
                    self.ll_group.downstream.value <= self.ll_group.min_ll
                    or self.ll_group.downstream.value >= self.ll_group.max_ll
                    or self.mode.value != 0  # Not in MANUAL mode
                ):
                    break

                current_ll = self.ll_group.downstream.value
                current_jt_pos = self.readback.value

                # Check if JT and heat are at stable points
                jt_at_stable = abs(current_jt_pos - self.stable_jt_pos) < 0.1
                heat_at_stable = abs(self.heater_group.net_heat) < 0.1

                ll_change = 0.0

                # Case 1: BOTH heat and JT are stable -> no change
                if jt_at_stable and heat_at_stable:
                    ll_change = 0.0

                # Case 2: Heat is different, JT is stable -> use calibration curve
                elif not heat_at_stable and jt_at_stable:
                    ll_change = self.heater_group.ll_delta

                # Case 3: Heat is stable, JT is different -> random rate based on direction
                elif heat_at_stable and not jt_at_stable:
                    rate = random.uniform(0.1, 0.3)

                    if current_jt_pos < self.stable_jt_pos:
                        # Less helium supply -> level falls
                        ll_change = -rate
                    else:
                        # More helium supply -> level rises
                        ll_change = rate

                # Case 4: Both are different -> combined effect
                else:
                    # Heat contribution
                    heat_contribution = self.heater_group.ll_delta

                    # JT contribution
                    jt_delta = current_jt_pos - self.stable_jt_pos
                    rate = random.uniform(0.1, 0.3)
                    if jt_delta < 0:
                        jt_contribution = -rate  # Less helium
                    else:
                        jt_contribution = rate  # More helium

                    ll_change = heat_contribution + jt_contribution

                # Apply change
                new_ll = current_ll + ll_change
                new_ll = max(
                    self.ll_group.min_ll, min(self.ll_group.max_ll, new_ll)
                )

                await self.ll_group.downstream.write(new_ll)
                await sleep(1)
        except asyncio.CancelledError:
            raise


class LiquidLevelPVGroup(PVGroup):
    upstream = pvproperty(name="2601:US:LVL", value=75.0)
    downstream = pvproperty(name="2301:DS:LVL", value=93.0)

    max_ll = 100
    min_ll = 0


class CryoPVGroup(PVGroup):
    uhl = SeverityProp(name="LVL", value=0)
