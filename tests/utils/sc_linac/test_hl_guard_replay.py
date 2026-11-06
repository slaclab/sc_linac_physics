"""Replay Cavity._auto_tune on each packaged H1/H2 response curve.

The fake tuner here moves along a cavity's curve: N commanded microsteps move
the cavity N / factor microsteps along it. factor 1.0 is a tuner that matches
its curve; 1.1 takes 10% more steps than the curve says, as some archived runs
on H2 cav 5 and 7 did (Lisa Zacarias, "Stepper SCALE on the harmonic
linearizers", 2026-11-02).

With the curve sizing moves and a 1.3x floor on the runaway guard, a one-call
tune from -400 kHz must pass at 1.0x and 1.1x and trip at 1.5x. These are the
settings the FREQ_OFFSET automation will pass to _auto_tune.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sc_linac_physics.utils.epics import EPICS_NO_ALARM_VAL, make_mock_pv
from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    RF_MODE_CHIRP,
    DetuneError,
)
from sc_linac_physics.utils.sc_linac.tuner_response import TunerResponse
from tests.mock_utils import mock_func

HL_PREFIXES = [f"ACCL:L1B:H{cm}{cav}0:" for cm in (1, 2) for cav in range(1, 9)]
START_HZ = -400_000
TOLERANCE_HZ = 500
# The configured STEP:SCALE on every HL cavity. Only its sign matters here.
HL_SCALE = 0.0715


@pytest.fixture
def cavity(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)
    with patch("sc_linac_physics.utils.sc_linac.cavity.custom_logger"):
        rack = MagicMock()
        rack.cryomodule.is_harmonic_linearizer = True
        rack.freq_offset = 0
        cav = Cavity(cavity_num=1, rack_object=rack)
        cav._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        cav._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_NO_ALARM_VAL)
        cav._tune_config_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        cav._status_msg_pv_obj = make_mock_pv()
        cav.stepper_tuner.hz_per_microstep = HL_SCALE
        yield cav


def _replay(cavity, response, factor, use_curve=True):
    """Tune from START_HZ to 0. Returns the total microsteps commanded."""
    state = {"real_hz": START_HZ, "commanded": 0}

    def move(steps, max_steps=None, speed=None):
        # With SCALE positive, _auto_tune expects a move of `steps` to lower
        # delta_hz by steps / microsteps_per_hz, so negative steps raise the
        # detune here.
        position = response.position(state["real_hz"]) - steps / factor
        state["real_hz"] = float(
            np.interp(position, response.usteps_from_cold, response.detune_hz)
        )
        state["commanded"] += abs(steps)

    cavity.stepper_tuner.move = move
    kwargs = {}
    if use_curve:
        kwargs = dict(
            expected_steps=int(abs(response.steps_between(START_HZ, 0))),
            step_estimator=lambda d: response.steps_between(
                state["real_hz"], state["real_hz"] - d
            ),
            min_tol_factor=1.3,
        )
    cavity._auto_tune(
        delta_hz_func=lambda: state["real_hz"],
        tolerance=TOLERANCE_HZ,
        **kwargs,
    )
    return state


@pytest.mark.parametrize("prefix", HL_PREFIXES)
@pytest.mark.parametrize("factor", [1.0, 1.1])
def test_curve_guard_passes(cavity, prefix, factor):
    response = TunerResponse.for_cavity(prefix)
    state = _replay(cavity, response, factor)
    assert abs(state["real_hz"]) <= TOLERANCE_HZ


@pytest.mark.parametrize("prefix", HL_PREFIXES)
def test_curve_guard_trips_on_a_runaway(cavity, prefix):
    response = TunerResponse.for_cavity(prefix)
    with pytest.raises(DetuneError, match="more steps than expected"):
        _replay(cavity, response, factor=1.5)


def test_one_near_resonance_scale_trips_across_the_flat_zone(cavity):
    """Why the curve is needed: H2 cav 5 spends ~40% of its tune in the
    -300 to -200 kHz band. With SCALE set to its near-resonance slope, the
    default guard stops a -400 kHz tune partway."""
    response = TunerResponse.for_cavity("ACCL:L1B:H250:")
    cavity.stepper_tuner.hz_per_microstep = response.hz_per_microstep(0)
    with pytest.raises(DetuneError, match="more steps than expected"):
        _replay(cavity, response, factor=1.0, use_curve=False)
