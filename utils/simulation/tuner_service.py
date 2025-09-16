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
from lcls_tools.superconducting.sc_linac_utils import (
    ESTIMATED_MICROSTEPS_PER_HZ,
    PIEZO_HZ_PER_VOLT,
)

from utils.simulation.cavity_service import CavityPVGroup
from utils.simulation.severity_prop import SeverityProp


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
        value=1 / ESTIMATED_MICROSTEPS_PER_HZ, name="SCALE", dtype=ChannelType.FLOAT
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
        freq_move_sign = move_sign_des if self.cavity_group.is_hl else -move_sign_des
        starting_detune = self.cavity_group.detune.value

        while self.step_des.value - steps >= self.speed.value and self.abort.value != 1:
            await self.step_tot.write(self.step_tot.value + self.speed.value)
            await self.step_signed.write(self.step_signed.value + step_change)

            steps += self.speed.value
            delta = self.speed.value // self.steps_per_hertz
            new_detune = self.cavity_group.detune.value + (freq_move_sign * delta)

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

        print(f"Piezo feedback status: {self.piezo_group.feedback_mode_stat.value}")
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

    @move_pos.putter
    async def move_pos(self, instance, value):
        await self.move(1)


class PiezoPVGroup(PVGroup):
    enable: PvpropertyEnum = pvproperty(name="ENABLE")
    enable_stat = pvproperty(
        name="ENABLESTAT",
        dtype=ChannelType.ENUM,
        value=1,
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
    dc_setpoint = pvproperty(name="DAC_SP")
    bias_voltage = pvproperty(name="BIAS")
    prerf_test_start = pvproperty(name="TESTSTRT")
    prerf_cha_status = pvproperty(name="CHA_TESTSTAT")
    prerf_chb_status = pvproperty(name="CHB_TESTSTAT")
    prerf_cha_testmsg = pvproperty(name="CHA_TESTMSG1")
    prerf_chb_testmsg = pvproperty(name="CHA_TESTMSG2")
    capacitance_a = pvproperty(name="CHA_C")
    capacitance_b = pvproperty(name="CHB_C")
    prerf_test_status: PvpropertyEnum = pvproperty(
        name="TESTSTS",
        dtype=ChannelType.ENUM,
        value=0,
        enum_strings=("", "Complete", "Running"),
    )
    withrf_run_check = pvproperty(name="RFTESTSTRT")
    withrf_check_status: PvpropertyEnum = pvproperty(
        name="RFTESTSTS",
        dtype=ChannelType.ENUM,
        value=1,
        enum_strings=("", "Complete", "Running"),
    )
    withrf_status = pvproperty(name="RFSTESTSTAT")
    amplifiergain_a = pvproperty(name="CHA_AMPGAIN")
    amplifiergain_b = pvproperty(name="CHB_AMPGAIN")
    withrf_push_dfgain = pvproperty(name="PUSH_DFGAIN.PROC")
    withrf_save_dfgain = pvproperty(name="SAVE_DFGAIN.PROC")
    detunegain_new = pvproperty(name="DFGAIN_NEW")
    hardware_sum = pvproperty(
        value=0,
        name="HWSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("", "Minor Fault", "Fault"),
    )
    feedback_sum = pvproperty(
        value=0,
        name="FBSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("", "Minor Fault", "Fault"),
    )
    integrator_sp: PvpropertyFloat = pvproperty(
        name="INTEG_SP", value=0, dtype=ChannelType.FLOAT
    )
    integrator_lim_status = SeverityProp(name="INTEG_AT_LIM", value=0)

    voltage: PvpropertyInteger = pvproperty(name="V", value=17, dtype=ChannelType.INT)
    scale: PvpropertyInteger = pvproperty(name="SCALE", value=20, dtype=ChannelType.INT)

    def __init__(self, prefix, cavity_group):
        super().__init__(prefix)
        self.cavity_group: CavityPVGroup = cavity_group

    @prerf_test_start.putter
    async def prerf_test_start(self, instance, value):
        await self.prerf_test_status.write("Running")
        await sleep(5)
        await self.prerf_test_status.write("Complete")

    @feedback_mode.putter
    async def feedback_mode(self, instance, value):
        await self.feedback_mode_stat.write(value)
