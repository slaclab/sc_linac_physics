"""sc-sim serves the production type and enum states for SSA, rack, cryo,
launcher and system PVs.

Production values were read from lcls-srv01 on 2026-10-14 (L1B CM02, H1). The
app code compares enums by index, so the point is that a client reading a PV
through the sim sees the same type and states as on the machine. These pin a
few of each kind of fix; the sim-serves-model test covers the names.
"""

import pytest
from caproto import ChannelType

from sc_linac_physics.utils.simulation.sc_linac_physics_service import (
    SCLinacPhysicsService,
)

CAV = "ACCL:L1B:0210:"
CM = "ACCL:L1B:0200:"
BLANK = ("", "")


@pytest.fixture(scope="module")
def service():
    return SCLinacPhysicsService()


@pytest.mark.parametrize(
    "pv, data_type",
    [
        (f"{CAV}CKPSUM", ChannelType.DOUBLE),
        (f"{CM}AACTMEANSUM", ChannelType.DOUBLE),
        (f"{CM}RACKA:FREQSUM", ChannelType.DOUBLE),
        (f"{CM}RACKA:FSCAN:RMS_THRESH", ChannelType.DOUBLE),
        (f"{CAV}SSA:AlarmSummary", ChannelType.DOUBLE),
        (f"{CM}RFS1A:DAC_AMPLITUDE", ChannelType.LONG),
        (f"{CAV}SSA:480VACStat", ChannelType.LONG),
        ("PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT", ChannelType.DOUBLE),
        ("CLIC:HL01:3001:PVJT:MODE", ChannelType.DOUBLE),
    ],
)
def test_numeric_type(service, pv, data_type):
    assert service[pv].data_type == data_type


@pytest.mark.parametrize(
    "pv, states",
    [
        (f"{CAV}SSA:CALSTAT", ("Good", "Warning", "Error")),
        (f"{CAV}SSA:PowerOn", ("Standby", "Powering On...")),
        (f"{CAV}SSA:PowerOff", ("Standby", "Powering Off...")),
        (f"{CAV}CPLRTEMP2_LTCH", ("Ok", "Fault")),
        (f"{CM}AUTO:SETUP_SSAREQ", ("No request", "Request")),
        (f"{CM}AUTO:SETUPSTS", ("Crash", "Complete", "Running")),
        ("CRYO:HL01:0:CAS_ACCESS", ("Disable", "Enable")),
        ("BSOC:SYSW:2:SumyA", ("FAULT", "Ok")),
        ("QUAD:L1B:0285:STATMSG", None),
    ],
)
def test_enum_states(service, pv, states):
    chan = service[pv]
    assert chan.data_type == ChannelType.ENUM
    if states is not None:
        assert tuple(chan.enum_strings) == states


def test_ssa_status_msg_indices(service):
    states = service[f"{CAV}SSA:StatusMsg"].enum_strings
    assert states[1] == "SSA Faulted"
    assert states[5] == "Powering On..."
    assert states[13] == "SSA Offline"


def test_magnet_statmsg_index_13(service):
    assert service["QUAD:L1B:0285:STATMSG"].enum_strings[13] == "BAD Ripple"


def test_command_pv_is_blank_two_state_enum(service):
    chan = service[f"{CM}RACKA:FSCAN:START"]
    assert chan.data_type == ChannelType.ENUM
    assert tuple(chan.enum_strings) == BLANK


def test_fresh_launcher_status_idles_at_complete_not_crash(service):
    """Production index 0 is Crash, so the idle default must be Complete."""
    assert service[f"{CM}AUTO:SETUPSTS"].value in (1, "Complete")


def test_cas_access_names_follow_cryo_name(service):
    """q0_cryomodule names it through cryo_name: HL01/HL02 for H1/H2."""
    assert "CRYO:HL01:0:CAS_ACCESS" in service
    assert "CRYO:HL02:0:CAS_ACCESS" in service
    assert "CRYO:CM02:0:CAS_ACCESS" in service
    assert "CRYO:CMH1:0:CAS_ACCESS" not in service
    assert "CRYO:CMH2:0:CAS_ACCESS" not in service
