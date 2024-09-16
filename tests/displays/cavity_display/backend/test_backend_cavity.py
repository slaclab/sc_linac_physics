from unittest import TestCase, mock

from lcls_tools.superconducting.sc_linac import Machine

builtin_open = open  # save the unpatched version

csv_keys = [
    "Three Letter Code",
    "Short Description",
    "Long Description",
    "Recommended Corrective Actions",
    "Level",
    "CM Type",
    "Button Type",
    "Button Path",
    "Button Macros",
    "Rack",
    "PV Prefix",
    "PV Suffix",
    "OK If Equal To",
    "Faulted If Equal To",
    "Severity",
    "Generic Short Description for Decoder",
]
csv_cav_row = [
    "   ",
    "Offline",
    "Cavity not usable or not intended to be used for extended period",
    "No further action required",
    "CAV",
    "",
    "EDM",
    "$EDM/llrf/rf_srf_cavity_main.edl",
    '"SELTAB=10',
    'SELCHAR=3"',
    "",
    "ACCL:{LINAC}:{CRYOMODULE}{CAVITY}0:",
    "HWMODE",
    "",
    "2",
    "5",
    "Offline",
    "",
]

csv_all_row = [
    "BSO",
    "BSOIC Tripped Chain A",
    "BSOIC tripped",
    "Communicate the fault to the EOIC and await resolution",
    "ALL",
    "",
    "EDM",
    "$EDM/pps/pps_sysw.edl",
    "",
    "",
    "BSOC:SYSW:2:",
    "SumyA",
    "1",
    "",
    "2",
    "BSOIC Tripped",
    "",
]

csv_rack_row = [
    "BLV",
    "Beamline Vacuum",
    "Beamline Vacuum too high",
    "Contact on call SRF person",
    "RACK",
    "",
    "EDM",
    "$EDM/llrf/rf_srf_cavity_main.edl",
    '"SELTAB=4',
    'SELCHAR=3"',
    "A",
    "ACCL:{LINAC}:{CRYOMODULE}00:",
    "BMLNVACA_LTCH",
    "0",
    "",
    "2",
    "",
    "",
]

csv_ssa_row = [
    "SSA",
    "SSA Faulted",
    "SSA not on",
    "Run auto setup",
    "SSA",
    "",
    "EDM",
    "$EDM/llrf/rf_srf_ssa_{cm_OR_hl}.edl",
    "",
    "",
    "ACCL:{LINAC}:{CRYOMODULE}{CAVITY}0:SSA:",
    "FaultSummary.SEVR",
    "",
    "2",
    "2",
    "SSA Faulted",
    "",
]

csv_cryo_row = [
    "USL",
    "Upstream liquid level out of tolerance Alarm",
    "Cryomodule liquid level out of tolerance",
    "Call on shift cryo operator",
    "CRYO",
    "",
    "EDM",
    "$EDM/cryo/cryo_system_all.edl",
    "",
    "",
    "CLL:CM{CRYOMODULE}:2601:US:",
    "LVL.SEVR",
    "",
    "2",
    "2",
    "",
    "",
]

csv_cm_row = [
    "BCS",
    "BCS LLRF Drive Fault",
    "BCS fault is interrupting LLRF drive (only affects CM01 in practice)",
    "Communicate the fault to the EOIC and await resolution",
    "CM",
    "ALL",
    "EDM",
    "$EDM/bcs/ops_lcls2_bcs_main.edl",
    "",
    "",
    "ACCL:{LINAC}:{CRYOMODULE}00:",
    "BCSDRVSUM",
    "0",
    "",
    "2",
    "BCS LLRF Drive Fault",
    "",
]


def mock_open(*args, **kwargs):
    data = [",".join(csv_keys), ",".join(csv_rack_row)]
    # mocked open for path "foo"
    return mock.mock_open(read_data="\n".join(data))(*args, **kwargs)


# These import states try to read from faults.csv which causes an error
with mock.patch("builtins.open", mock_open):
    from displays.cavity_display.backend.backend_cavity import BackendCavity

    DISPLAY_MACHINE = Machine(
        cavity_class=BackendCavity,
    )


class TestBackendCavity(TestCase):
    def test_create_faults_rack(self):
        cm01 = DISPLAY_MACHINE.cryomodules["01"]
        cavity1: BackendCavity = cm01.cavities[1]
        cavity5: BackendCavity = cm01.cavities[5]

        self.assertEqual(len(cavity1.faults.values()), 1)
        self.assertEqual(
            len(cavity5.faults.values()), 0, msg="Rack B cavity created Rack A fault"
        )

    def test_get_fault_counts(self):
        self.skipTest("not yet implemented")

    def test_run_through_faults(self):
        self.skipTest("not yet implemented")
