"""Rack FREQ_OFFSET and the chirp window in the simulator.

On the machine, CHIRP:DF reads real detune minus the rack FREQ_OFFSET, and
production code treats an INVALID CHIRP:DF as "no detune in the chirp window".
These tests pin both down in the sim, so tuning code that steps the offset can
be exercised against sc-sim.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from caproto import AlarmSeverity

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.rack_service import RACKPVGroup

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def cm_group():
    group = Mock()
    group.total_power = 0.0
    group.heater = Mock()
    group.heater.mode.value = 2
    group.heater.setpoint = Mock()
    group.heater.setpoint.value = 0.0
    group.heater.setpoint.write = AsyncMock()
    return group


@pytest.fixture
def rack(cm_group):
    """An HL rack with two cavities wired the way the service wires them."""
    cavities = [
        CavityPVGroup(f"TEST:H1{num}0:", isHL=True, cm_group=cm_group)
        for num in (1, 2)
    ]
    rack = RACKPVGroup("TEST:H100:RACKA:", cavity_groups=cavities)
    for cavity in cavities:
        cavity.rack_group = rack
    return rack


def _chirp_invalid(cavity) -> bool:
    return cavity.detune_chirp.alarm.severity == AlarmSeverity.INVALID_ALARM


class TestWriteDetune:
    @pytest.mark.asyncio
    async def test_chirp_reads_relative_to_rack_offset(self, rack):
        cavity = rack.cavity_groups[0]
        await rack.freq_offset.write(-600_000)

        await cavity.write_detune(-650_000)

        assert cavity.detune.value == -650_000
        assert cavity.detune_rfs.value == -650_000
        assert cavity.detune_chirp.value == -50_000

    @pytest.mark.asyncio
    async def test_no_rack_means_zero_offset(self, cm_group):
        cavity = CavityPVGroup("TEST:CAV:", isHL=False, cm_group=cm_group)

        await cavity.write_detune(1_234)

        assert cavity.detune_chirp.value == 1_234


class TestRackOffsetPutter:
    @pytest.mark.asyncio
    async def test_offset_write_moves_chirp_not_real_detune(self, rack):
        for cavity in rack.cavity_groups:
            await cavity.write_detune(-650_000)

        await rack.freq_offset.write(-400_000)

        for cavity in rack.cavity_groups:
            assert cavity.detune.value == -650_000
            assert cavity.detune_chirp.value == -250_000

    @pytest.mark.asyncio
    async def test_offset_defaults_to_zero(self, rack):
        assert rack.freq_offset.value == 0.0


class TestChirpWindow:
    @pytest.mark.asyncio
    async def test_outside_window_is_invalid(self, rack):
        cavity = rack.cavity_groups[0]
        await cavity.chirp_start.write(-200_000)
        await cavity.chirp_stop.write(200_000)

        await cavity.write_detune(-650_000)

        assert _chirp_invalid(cavity)

    @pytest.mark.asyncio
    async def test_offset_brings_cavity_into_window(self, rack):
        cavity = rack.cavity_groups[0]
        await cavity.write_detune(-650_000)
        assert _chirp_invalid(cavity)

        await rack.freq_offset.write(-600_000)

        assert not _chirp_invalid(cavity)

    @pytest.mark.asyncio
    async def test_widening_window_clears_invalid(self, rack):
        # What Cavity.find_chirp_range does: widen until CHIRP:DF is valid.
        cavity = rack.cavity_groups[0]
        await cavity.write_detune(-300_000)
        assert _chirp_invalid(cavity)

        await cavity.chirp_start.write(-350_000)

        assert not _chirp_invalid(cavity)

    @pytest.mark.asyncio
    async def test_narrowing_window_sets_invalid(self, rack):
        cavity = rack.cavity_groups[0]
        await cavity.write_detune(-150_000)
        assert not _chirp_invalid(cavity)

        await cavity.chirp_start.write(-100_000)

        assert _chirp_invalid(cavity)

    @pytest.mark.asyncio
    async def test_invalid_chirp_leaves_other_cavity_pvs_alone(self, rack):
        # pvproperties without an alarm_group share one alarm per group.
        cavity = rack.cavity_groups[0]

        await cavity.write_detune(-650_000)

        assert _chirp_invalid(cavity)
        assert cavity.ades.alarm.severity != AlarmSeverity.INVALID_ALARM
        assert cavity.detune.alarm.severity != AlarmSeverity.INVALID_ALARM
