from asyncio import sleep

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyInteger,
    PvpropertyBoolEnum,
    PvpropertyEnum,
    PvpropertyFloat,
)

from sc_linac_physics.utils.sc_linac.linac_utils import (
    ESTIMATED_MICROSTEPS_PER_HZ,
    PIEZO_HZ_PER_VOLT,
)
from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class StepperPVGroup(PVGroup):
    move_pos = pvproperty(name="MOV_REQ_POS")
    move_neg = pvproperty(name="MOV_REQ_NEG")
    abort = pvproperty(name="ABORT_REQ")
    step_des: PvpropertyInteger = pvproperty(value=0, name="NSTEPS")
    max_steps = pvproperty(name="NSTEPS.DRVH")
    speed: PvpropertyInteger = pvproperty(value=20000, name="VELO")
    step_tot: PvpropertyInteger = pvproperty(value=0, name="REG_TOTABS")
    step_signed: PvpropertyInteger = pvproperty(value=0, name="REG_TOTSGN")
    reset_tot = pvproperty(name="TOTABS_RESET")
    reset_signed = pvproperty(name="TOTSGN_RESET")
    steps_cold_landing = pvproperty(name="NSTEPS_COLD")
    nsteps_park = pvproperty(name="NSTEPS_PARK", value=5000000)
    push_signed_cold = pvproperty(name="PUSH_NSTEPS_COLD.PROC")
    push_signed_park = pvproperty(name="PUSH_NSTEPS_PARK.PROC")
    motor_moving: PvpropertyBoolEnum = pvproperty(
        value=0,
        name="STAT_MOV",
        enum_strings=("Not Moving", "Moving"),
        dtype=ChannelType.ENUM,
    )
    motor_done: PvpropertyBoolEnum = pvproperty(
        value=1,
        name="STAT_DONE",
        enum_strings=("Not Done", "Done"),
        dtype=ChannelType.ENUM,
    )
    hardware_sum = pvproperty(
        value=0,
        name="HWSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("", "", "Fault"),
    )
    limit_switch_a = pvproperty(
        value=0,
        name="STAT_LIMA",
        dtype=ChannelType.ENUM,
        enum_strings=("not at limit", "at limit"),
    )
    limit_switch_b = pvproperty(
        value=0,
        name="STAT_LIMB",
        dtype=ChannelType.ENUM,
        enum_strings=("not at limit", "at limit"),
    )
    hz_per_microstep = pvproperty(
        value=1 / ESTIMATED_MICROSTEPS_PER_HZ,
        name="SCALE",
        dtype=ChannelType.FLOAT,
    )

    def __init__(self, prefix, cavity_group, piezo_group):
        super().__init__(prefix)
        self.cavity_group: CavityPVGroup = cavity_group
        self.piezo_group: PiezoPVGroup = piezo_group
        if not self.cavity_group.is_hl:
            self.steps_per_hertz = 256 / 1.4
        else:
            self.steps_per_hertz = 256 / 18.3

    async def move(self, move_sign_des: int):
        print("Motor moving")
        await self.motor_moving.write("Moving")
        steps = 0
        step_change = move_sign_des * self.speed.value
        freq_move_sign = (
            move_sign_des if self.cavity_group.is_hl else -move_sign_des
        )
        starting_detune = self.cavity_group.detune.value

        while (
            self.step_des.value - steps >= self.speed.value
            and self.abort.value != 1
        ):
            await self.step_tot.write(self.step_tot.value + self.speed.value)
            await self.step_signed.write(self.step_signed.value + step_change)

            steps += self.speed.value
            delta = self.speed.value // self.steps_per_hertz
            new_detune = self.cavity_group.detune.value + (
                freq_move_sign * delta
            )

            await self.cavity_group.detune.write(new_detune)
            await self.cavity_group.detune_rfs.write(new_detune)
            await self.cavity_group.detune_chirp.write(new_detune)
            await sleep(1)

        if self.abort.value == 1:
            await self.motor_moving.write("Not Moving")
            await self.abort.write(0)
            return

        remainder = self.step_des.value - steps
        await self.step_tot.write(self.step_tot.value + remainder)
        step_change = move_sign_des * remainder
        await self.step_signed.write(self.step_signed.value + step_change)

        delta = remainder // self.steps_per_hertz
        new_detune = self.cavity_group.detune.value + (freq_move_sign * delta)

        print(
            f"Piezo feedback status: {self.piezo_group.feedback_mode_stat.value}"
        )
        if (
            self.piezo_group.enable_stat.value == 1
            and self.piezo_group.feedback_mode_stat.value == "Feedback"
        ):
            freq_change = new_detune - starting_detune
            voltage_change = freq_change * (1 / PIEZO_HZ_PER_VOLT)
            print(f"Changing piezo voltage by {voltage_change} V")
            await self.piezo_group.voltage.write(
                self.piezo_group.voltage.value + voltage_change
            )
        await self.cavity_group.detune.write(new_detune)
        await self.cavity_group.detune_rfs.write(new_detune)
        await self.cavity_group.detune_chirp.write(new_detune)

        await self.motor_moving.write("Not Moving")
        await self.motor_done.write("Done")

    @move_neg.putter
    async def move_neg(self, instance, value):
        await self.move(-1)
        return value

    @move_pos.putter
    async def move_pos(self, instance, value):
        await self.move(1)
        return value


class PiezoPVGroup(PVGroup):
    simulate_failure = pvproperty(
        name="SIM_FAIL",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=(
            "No Failure",
            "Channel A Fail (Low Cap)",
            "Channel B Fail (Low Cap)",
            "Both Fail (No Connection)",
            "Channel A Fail (High Cap)",
            "Timeout",
        ),
    )
    enable: PvpropertyEnum = pvproperty(
        name="ENABLE",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Disable", "Enable"),
    )
    enable_stat = pvproperty(
        name="ENABLESTAT",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=("Disabled", "Enabled"),
    )
    feedback_mode = pvproperty(
        value=1,
        name="MODECTRL",
        dtype=ChannelType.ENUM,
        enum_strings=("Manual", "Feedback"),
    )
    feedback_mode_stat = pvproperty(
        name="MODESTAT",
        value=1,
        dtype=ChannelType.ENUM,
        enum_strings=("Manual", "Feedback"),
    )
    dc_setpoint = pvproperty(name="DAC_SP", value=0.0, dtype=ChannelType.FLOAT)
    bias_voltage = pvproperty(name="BIAS", value=0.0, dtype=ChannelType.FLOAT)

    # Pre-RF Test PVs
    prerf_test_start = pvproperty(name="TESTSTRT", value=0)
    prerf_cha_status = pvproperty(
        name="CHA_TESTSTAT",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=(
            "Pass",
            "Fail",
            "Not Tested",
        ),
    )

    prerf_chb_status = pvproperty(
        name="CHB_TESTSTAT",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=("Pass", "Fail", "Not Tested"),
    )
    prerf_cha_testmsg = pvproperty(
        name="CHA_TESTMSG1", value="", dtype=ChannelType.STRING
    )
    prerf_chb_testmsg = pvproperty(
        name="CHA_TESTMSG2",
        value="",
        dtype=ChannelType.STRING,
    )
    capacitance_a: PvpropertyFloat = pvproperty(
        name="CHA_C", value=0.0, dtype=ChannelType.FLOAT
    )
    capacitance_b: PvpropertyFloat = pvproperty(
        name="CHB_C", value=0.0, dtype=ChannelType.FLOAT
    )
    prerf_test_status: PvpropertyEnum = pvproperty(
        name="TESTSTS",
        dtype=ChannelType.ENUM,
        value=1,
        enum_strings=("Crash", "Complete", "Running"),
    )

    # With-RF Test PVs
    withrf_run_check = pvproperty(name="RFTESTSTRT", value=0)
    withrf_check_status: PvpropertyEnum = pvproperty(
        name="RFTESTSTS",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=("Idle", "Complete", "Running"),
    )
    withrf_status = pvproperty(
        name="RFSTESTSTAT",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=("Not Tested", "Pass", "Fail"),
    )
    amplifiergain_a = pvproperty(
        name="CHA_AMPGAIN", value=0.0, dtype=ChannelType.FLOAT
    )
    amplifiergain_b = pvproperty(
        name="CHB_AMPGAIN", value=0.0, dtype=ChannelType.FLOAT
    )
    withrf_push_dfgain = pvproperty(name="PUSH_DFGAIN.PROC", value=0)
    withrf_save_dfgain = pvproperty(name="SAVE_DFGAIN.PROC", value=0)
    detunegain_new = pvproperty(
        name="DFGAIN_NEW", value=0.0, dtype=ChannelType.FLOAT
    )

    # Status PVs
    hardware_sum = pvproperty(
        value=0,
        name="HWSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Minor Fault", "Fault"),
    )
    feedback_sum = pvproperty(
        value=0,
        name="FBSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Minor Fault", "Fault"),
    )

    integrator_sp: PvpropertyFloat = pvproperty(
        name="INTEG_SP", value=0, dtype=ChannelType.FLOAT
    )
    integrator_lim_status = SeverityProp(name="INTEG_AT_LIM", value=0)

    voltage: PvpropertyInteger = pvproperty(
        name="V", value=17, dtype=ChannelType.INT
    )
    scale: PvpropertyInteger = pvproperty(
        name="SCALE", value=20, dtype=ChannelType.INT
    )

    def __init__(self, prefix, cavity_group):
        super().__init__(prefix)
        self.cavity_group: CavityPVGroup = cavity_group

    @enable.putter
    async def enable(self, instance, value):
        """Update enable status when enable command is issued."""
        if isinstance(value, str):
            is_enabled = value in ("Enable", "Enabled")
        else:
            is_enabled = int(value) == 1

        await self.enable_stat.write(1 if is_enabled else 0)
        if not is_enabled:  # Disabled
            # Optionally reset feedback mode to manual
            await self.feedback_mode_stat.write(0)
        return value

    @prerf_test_start.putter
    async def prerf_test_start(self, instance, value):
        """Simulate pre-RF test execution."""
        if value == 0:
            return value

        print("Starting Pre-RF test simulation...")

        # Set test status to Running (index 2)
        await self.prerf_test_status.write(2)  # Running

        # Reset previous test results to "Not Tested" (index 2)
        await self.prerf_cha_status.write(2)  # Not Tested
        await self.prerf_chb_status.write(2)  # Not Tested
        await self.capacitance_a.write(0.0)
        await self.capacitance_b.write(0.0)
        await self.prerf_cha_testmsg.write("Testing...")
        await self.prerf_chb_testmsg.write("Testing...")

        await sleep(1)

        # Get failure mode - it's already an integer!
        fail_mode = self.simulate_failure.value  # Already 0, 1, 2, 3, 4, or 5

        if fail_mode == 0:  # No failure
            await self.prerf_cha_status.write(0)  # Pass
            await self.prerf_chb_status.write(0)  # Pass
            await self.capacitance_a.write(25.3)
            await self.capacitance_b.write(24.8)
            await self.prerf_cha_testmsg.write("Test passed")
            await self.prerf_chb_testmsg.write("Test passed")

        elif fail_mode == 1:  # Channel A fails
            await self.prerf_cha_status.write(1)  # Fail
            await self.prerf_chb_status.write(0)  # Pass
            await self.capacitance_a.write(10.5)
            await self.capacitance_b.write(24.8)
            await self.prerf_cha_testmsg.write("Low capacitance detected")
            await self.prerf_chb_testmsg.write("Test passed")

        elif fail_mode == 2:  # Channel B fails
            await self.prerf_cha_status.write(0)
            await self.prerf_chb_status.write(1)
            await self.capacitance_a.write(25.3)
            await self.capacitance_b.write(5.2)
            await self.prerf_cha_testmsg.write("Test passed")
            await self.prerf_chb_testmsg.write("Low capacitance detected")

        elif fail_mode == 3:  # Both channels fail
            await self.prerf_cha_status.write(1)
            await self.prerf_chb_status.write(1)
            await self.capacitance_a.write(0.1)
            await self.capacitance_b.write(0.2)
            await self.prerf_cha_testmsg.write("No connection detected")
            await self.prerf_chb_testmsg.write("No connection detected")

        elif fail_mode == 4:  # High capacitance
            await self.prerf_cha_status.write(1)
            await self.prerf_chb_status.write(0)
            await self.capacitance_a.write(45.7)
            await self.capacitance_b.write(24.8)
            await self.prerf_cha_testmsg.write("High capacitance detected")
            await self.prerf_chb_testmsg.write("Test passed")

        elif fail_mode == 5:  # Timeout
            await self.prerf_cha_status.write(1)
            await self.prerf_chb_status.write(1)
            await self.capacitance_a.write(0.0)
            await self.capacitance_b.write(0.0)
            await self.prerf_cha_testmsg.write("Test timeout")
            await self.prerf_chb_testmsg.write("Test timeout")

        else:  # Unknown
            await self.prerf_cha_status.write(1)
            await self.prerf_chb_status.write(1)
            await self.prerf_cha_testmsg.write("Unknown failure mode")
            await self.prerf_chb_testmsg.write("Unknown failure mode")

        # Set test status to Complete
        await self.prerf_test_status.write(1)  # Complete

        # Determine overall result - compare to strings!
        overall_pass = (
            self.prerf_cha_status.value == "Pass"
            and self.prerf_chb_status.value == "Pass"
        )

        if overall_pass:
            print("Pre-RF test complete: PASS")
        else:
            print("Pre-RF test complete: FAIL")

        return value

    @feedback_mode.putter
    async def feedback_mode(self, instance, value):
        """Update feedback mode status."""
        if self.enable_stat.value == 0:
            print("Warning: Cannot change feedback mode while disabled")
            return instance.value  # Don't change if disabled
        await self.feedback_mode_stat.write(value)
        return value

    @withrf_run_check.putter
    async def withrf_run_check(self, instance, value):
        """Simulate with-RF test execution."""
        if value == 0:
            return value

        print("Starting With-RF test simulation...")
        await self.withrf_check_status.write(2)  # Running
        await self.withrf_status.write(0)  # Reset status

        await sleep(3)

        # Simulate successful with-RF test
        await self.withrf_status.write(1)  # Pass
        await self.amplifiergain_a.write(1.05)
        await self.amplifiergain_b.write(0.98)

        await self.withrf_check_status.write(1)  # Complete
        print("With-RF test complete: PASS")
        return value
