"""sc-sim starts each cavity at its production values.

Values come from data/production_cavities.csv, read on lcls-srv01 on
2026-10-28, except the L4B ADES_MAX limits, which are set to 26 MV (see
_load_production_cavities). ADES_MAX is 0 for an Offline cavity and the
lowest of the five limits otherwise.
"""

from unittest.mock import Mock

import numpy as np
import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    build_cavity_pv_base,
    get_linac_for_cryomodule,
)
from sc_linac_physics.utils.simulation.cavity_service import (
    CavityPVGroup,
    _load_production_cavities,
)
from sc_linac_physics.utils.simulation.fault_service import CavFaultPVGroup


def make_cavity(prefix, is_hl=False):
    return CavityPVGroup(prefix, isHL=is_hl, cm_group=Mock())


def limits_of(cavity):
    return (
        cavity.adesMaxSRF.value,
        cavity.adesMaxOPS.value,
        cavity.adesMaxRF.value,
        cavity.adesMaxCRYO.value,
        cavity.adesMaxADMIN.value,
    )


def test_file_has_every_cavity_once():
    expected = {
        build_cavity_pv_base(get_linac_for_cryomodule(cm), cm, cav)
        for cm in ALL_CRYOMODULES
        for cav in range(1, 9)
    }
    assert set(_load_production_cavities()) == expected
    assert len(expected) == 480


@pytest.mark.parametrize(
    "prefix, is_hl, limits, ades_max",
    [
        # SRF is the lowest
        ("ACCL:L0B:0130:", False, (9.1, 21.798, 16.6, 21.8, 18.2), 9.1),
        # RF is the lowest
        ("ACCL:L1B:0210:", False, (18.7, 21.798, 17, 21.8, 18.68), 17),
        # CRYO is the lowest
        ("ACCL:L3B:2640:", False, (15.8, 21.798, 16.6, 6, 18.68), 6),
        # HL cavity
        ("ACCL:L1B:H110:", True, (4.3, 7.265, 7.265, 31, 6.227), 4.3),
        # Offline: 0 although the lowest limit is 17
        ("ACCL:L2B:0510:", False, (17.7, 21.798, 17, 21.8, 18.68), 0),
        # L4B: 26 everywhere but CRYO
        ("ACCL:L4B:3710:", False, (26, 26, 26, 31, 26), 26),
        ("ACCL:L4B:5980:", False, (26, 26, 26, 31, 26), 26),
    ],
)
def test_cavity_starts_at_its_limits(prefix, is_hl, limits, ades_max):
    cavity = make_cavity(prefix, is_hl)
    assert limits_of(cavity) == pytest.approx(limits)
    assert cavity.adesMax.value == pytest.approx(ades_max)


@pytest.mark.parametrize(
    "prefix, hw_mode, acon, ades",
    [
        ("ACCL:L0B:0110:", 0, 5.7, 5.7),
        ("ACCL:L2B:0510:", 2, 17, 0),  # Offline, ACON kept
        ("ACCL:L1B:H230:", 1, 5, 5),  # Maintenance
        ("ACCL:L4B:3710:", 0, 0, 0),
    ],
)
def test_cavity_starts_at_its_amplitude_and_hwmode(prefix, hw_mode, acon, ades):
    cavity = make_cavity(prefix, is_hl="H" in prefix)
    assert cavity.hw_mode == hw_mode
    assert cavity.acon.value == pytest.approx(acon)
    for channel in (cavity.ades, cavity.aact, cavity.amean):
        assert channel.value == pytest.approx(ades)
    for channel in (cavity.gdes, cavity.gact):
        assert channel.value == pytest.approx(ades / cavity.length)


async def test_startup_uses_production_q_scale_and_df_cold():
    cavity = make_cavity("ACCL:L1B:0210:")
    await CavityPVGroup.qloaded_new.pvspec.startup(
        cavity, cavity.qloaded_new, None
    )
    await CavityPVGroup.detune.pvspec.startup(cavity, cavity.detune, None)
    for channel in (cavity.qloaded, cavity.qloaded_new):
        assert channel.value == pytest.approx(4.47746e7)
    for channel in (cavity.current_cav_scale, cavity.scale_new):
        assert channel.value == pytest.approx(28.8468)
    assert cavity.df_cold.value == 226472


def test_unknown_prefix_keeps_the_old_defaults():
    cavity = make_cavity("TEST:CAV:")
    assert limits_of(cavity) == (21, 21, 21, 21, 21)
    assert cavity.adesMax.value == 21
    assert cavity.ades.value == 16.6
    assert cavity.hw_mode == 0


@pytest.mark.parametrize(
    "attr", ["adesMaxSRF", "adesMaxOPS", "adesMaxRF", "adesMaxADMIN"]
)
async def test_lowering_a_limit_lowers_ades_max(attr):
    cavity = make_cavity("ACCL:L4B:3710:")
    await getattr(cavity, attr).write(12.5)
    assert cavity.adesMax.value == pytest.approx(12.5)


async def test_raising_the_lowest_limit_moves_ades_max_to_the_next():
    cavity = make_cavity("ACCL:L1B:0210:")  # RF 17 is lowest, ADMIN 18.68 next
    await cavity.adesMaxRF.write(25)
    assert cavity.adesMax.value == pytest.approx(18.68)


async def test_raising_a_limit_on_an_offline_cavity_keeps_ades_max_at_0():
    cavity = make_cavity("ACCL:L2B:0510:")
    await cavity.adesMaxRF.write(25)
    assert cavity.adesMax.value == 0


def test_hwmode_starts_at_the_cavity_value():
    cavity = make_cavity("ACCL:L2B:0510:")
    faults = CavFaultPVGroup("ACCL:L2B:0510:", cavity_group=cavity)
    assert faults.offline.value == 2


async def test_writing_hwmode_recomputes_ades_max():
    cavity = make_cavity("ACCL:L2B:0510:")
    faults = CavFaultPVGroup("ACCL:L2B:0510:", cavity_group=cavity)

    await faults.offline.write("Online")
    assert cavity.hw_mode == 0
    assert cavity.adesMax.value == pytest.approx(17)

    await faults.offline.write("Offline")
    assert cavity.hw_mode == 2
    assert cavity.adesMax.value == 0


@pytest.mark.parametrize(
    "prefix, points, dt, pre",
    [
        ("ACCL:L1B:0210:", 16384, 7.001e-7, 0),
        ("ACCL:L1B:H110:", 16384, 1.785e-4, 1024),
        ("ACCL:L1B:H130:", 16384, 6.999e-7, 1024),
        ("ACCL:L1B:H140:", 16384, 5.6e-6, 1024),
        ("ACCL:L4B:3710:", 2048, 1.785e-4, 2048),
        ("ACCL:L4B:3950:", 1638, 1.785e-4, 1639),
        ("ACCL:L4B:4410:", 16384, 1.785e-4, 2048),
    ],
)
def test_fault_time_axis_matches_production(prefix, points, dt, pre):
    cavity = make_cavity(prefix, is_hl="H" in prefix)
    t = cavity._fault_time_axis()
    assert len(t) == points
    assert np.diff(t) == pytest.approx(dt, rel=1e-3)
    assert np.count_nonzero(t < 0) == min(pre, points)


def test_unknown_prefix_keeps_the_old_fault_time_axis():
    t = make_cavity("TEST:CAV:")._fault_time_axis()
    assert len(t) == 16384
    assert t[0] == pytest.approx(-500e-6)
    assert t[-1] == pytest.approx(1500e-6)
    assert np.count_nonzero(t < 0) == 4096


def test_decay_is_written_on_the_production_axis():
    cavity = make_cavity("ACCL:L1B:H110:", is_hl=True)
    t, a = cavity._generate_decay_waveform(5.0, 1e7)
    assert len(t) == len(a) == 16384
    assert a[:1024].mean() == pytest.approx(5.0, rel=0.01)  # flat before
    assert a[1024] == pytest.approx(5.0, rel=0.01)  # t = 0
    assert a[-1] < 0.01  # decayed by the end


def test_l4b_buffer_has_no_decay():
    cavity = make_cavity("ACCL:L4B:3710:")
    t, a = cavity._generate_decay_waveform(16.0, 4e7)
    assert len(a) == 2048
    assert (t < 0).all()
    assert a.mean() == pytest.approx(16.0, rel=0.01)
