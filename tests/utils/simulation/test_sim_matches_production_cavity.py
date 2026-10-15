"""sc-sim serves the production type and enum states for cavity and tuner PVs.

Production values were read from lcls-srv01 on 2026-10-14 (L1B CM02). The app
code compares enums by index, so the point is that a client reading a PV
through the sim sees the same type, states and waveform length as on the
machine. These pin a few of each kind of fix; the sim-serves-model test
covers the names.
"""

import pytest
from caproto import ChannelType

from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
    SCLinacPhysicsService,
)

CAV = "ACCL:L1B:0210:"
BLANK = ("", "")


@pytest.fixture(scope="module")
def service():
    return SCLinacPhysicsService()


@pytest.mark.parametrize(
    "pv, data_type",
    [
        (f"{CAV}DFBEST", ChannelType.DOUBLE),
        (f"{CAV}PZT:V", ChannelType.DOUBLE),
        (f"{CAV}PZT:HWSTATSUM", ChannelType.DOUBLE),
        (f"{CAV}ACQ_DECIM_SEL.A", ChannelType.DOUBLE),
        (f"{CAV}CAV:CAL_SCALEB_NEW", ChannelType.DOUBLE),
        (f"{CAV}DF_COLD", ChannelType.LONG),
    ],
)
def test_numeric_type(service, pv, data_type):
    assert service[pv].data_type == data_type


@pytest.mark.parametrize(
    "pv, states",
    [
        (f"{CAV}PZT:CHA_TESTSTAT", ("Pass", "Warning", "Fail")),
        (f"{CAV}PZT:RFTESTSTS", ("Crash", "Complete", "Running")),
        (f"{CAV}PZT:MODESTAT", ("Manual", "Feedback", "Chirp", "Unknown")),
        (f"{CAV}PZT:ENABLESTAT", ("Not enabled", "Enabled")),
        (f"{CAV}STEP:STAT_DONE", ("Not done", "Done")),
        (f"{CAV}STEP:STAT_LIMA", ("Not at limit", "At limit")),
        (f"{CAV}RFREADYFORBEAM", ("Not ready", "Ready")),
    ],
)
def test_enum_states(service, pv, states):
    chan = service[pv]
    assert chan.data_type == ChannelType.ENUM
    assert tuple(chan.enum_strings) == states


def test_rfmode_has_sixteen_states(service):
    states = tuple(service[f"{CAV}RFMODE"].enum_strings)
    assert len(states) == 16
    assert states[:7] == (
        "SELAP",
        "SELA",
        "SEL",
        "SEL Raw",
        "Pulse",
        "Chirp",
        "Tone",
    )
    assert states[7:15] == ("",) * 8
    assert states[15] == "Unknown"


@pytest.mark.parametrize(
    "pv",
    [
        f"{CAV}STEP:MOV_REQ_POS",
        f"{CAV}STEP:ABORT_REQ",
        f"{CAV}PROBECALSTRT",
        f"{CAV}PZT:TESTSTRT",
    ],
)
def test_command_pvs_are_blank_two_state_enums(service, pv):
    chan = service[pv]
    assert chan.data_type == ChannelType.ENUM
    assert tuple(chan.enum_strings) == BLANK


def test_fresh_sim_rftests_idles_at_complete_not_crash(service):
    """Production index 0 is Crash, so the idle default must be Complete."""
    assert service[f"{CAV}PZT:RFTESTSTS"].value in (1, "Complete")


@pytest.mark.parametrize(
    "suffix",
    ["CAV:AWF", "CAV:FLTAWF", "CAV:FLTTWF", "FWD:AWF", "REV:AWF"],
)
def test_waveforms_are_16384_points(service, suffix):
    assert len(service[f"{CAV}{suffix}"].value) == 16384
