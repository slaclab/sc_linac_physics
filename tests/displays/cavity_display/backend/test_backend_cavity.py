from collections import OrderedDict
from datetime import timedelta, datetime
from typing import DefaultDict
from unittest import TestCase, mock

from displays.cavity_display.backend.backend_cavity import BackendCavity
from displays.cavity_display.backend.fault import FaultCounter
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.linac import Machine

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
    data = [
        ",".join(csv_keys),
        ",".join(csv_rack_row),
        ",".join(csv_all_row),
        ",".join(csv_ssa_row),
        ",".join(csv_cryo_row),
        ",".join(csv_cm_row),
    ]
    # mocked open for path "foo"
    return mock.mock_open(read_data="\n".join(data))(*args, **kwargs)


# Comment
class TestBackendCavity(TestCase):
    @classmethod
    def setUpClass(cls):
        # We are setting up the mock for the test class. (Replacing the open func)
        cls.mock_open_patcher = mock.patch("builtins.open", mock_open)
        cls.mock_open_patcher.start()
        # Create display Machine
        cls.DISPLAY_MACHINE = Machine(cavity_class=BackendCavity)

    @classmethod
    def tearDownClass(cls):
        # Stops patcher when we finish all tests
        cls.mock_open_patcher.stop()

    def setUp(self):
        self.cm01: Cryomodule = self.DISPLAY_MACHINE.cryomodules["01"]
        self.cavity1: BackendCavity = self.cm01.cavities[1]
        self.cavity5: BackendCavity = self.cm01.cavities[5]
        self.cavity1.rack.rack_name = "A"

        # Need additonal setup for running through fault tests
        self.cavity1.create_faults = mock.Mock()
        self.cavity1.number = 1
        self.cavity1.status_pv = "STATUS_PV"
        self.cavity1.severity_pv = "SEVERITY_PV"
        self.cavity1.description_pv = "DESCRIPTION_PV"

    def test_create_faults_rack(self):
        cm01: Cryomodule = self.DISPLAY_MACHINE.cryomodules["01"]
        cavity1: BackendCavity = cm01.cavities[1]
        cavity5: BackendCavity = cm01.cavities[5]

        # Asserting cav1 only has 5 fault.
        self.assertEqual(len(cavity1.faults.values()), 5)
        # Asserting cav5 only has 4 fault.
        self.assertEqual(len(cavity5.faults.values()), 4)

        # Maybe an assertion to confirm cav5 has no rack faults?

        # WIP

    def test_create_faults(self):
        self.skipTest("not yet implemented")

    def test_get_fault_counts(self):
        # Setup
        cavity1: BackendCavity = self.cm01.cavities[1]

        # Making Mock fault objects w/ values
        mock_fault_counter_1 = FaultCounter(fault_count=5, ok_count=3, invalid_count=0)
        mock_fault_counter_2 = FaultCounter(fault_count=3, ok_count=5, invalid_count=1)
        mock_fault_counter_3 = FaultCounter(fault_count=1, ok_count=8, invalid_count=2)
        mock_faults = [
            mock.Mock(
                tlc="OFF",
                pv="PV1",
                get_fault_count_over_time_range=mock.Mock(
                    return_value=mock_fault_counter_1
                ),
            ),
            mock.Mock(
                tlc="MGT",
                pv="PV2",
                get_fault_count_over_time_range=mock.Mock(
                    return_value=mock_fault_counter_2
                ),
            ),
            mock.Mock(
                tlc="MGT",
                pv="PV3",
                get_fault_count_over_time_range=mock.Mock(
                    return_value=mock_fault_counter_3
                ),
            ),
        ]
        # Now need to replace cavity1.faults w/ our mock faults.
        cavity1.faults = OrderedDict((i, fault) for i, fault in enumerate(mock_faults))

        # Test
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=1)

        # Calling function we are testing w/ our time range.
        result: DefaultDict[str, FaultCounter] = cavity1.get_fault_counts(
            start_time, end_time
        )

        # Our assertions
        # 1. results needs to be an instance of dict
        self.assertIsInstance(result, dict)

        # 2. Need to verify the result has 2 entries (OFF and MGT)
        self.assertEqual(len(result), 2)

        # 3. Making sure FaultCounter obj with the highest sum of
        #    fault_count+invalid_count is in the result for its associated TLC
        self.assertEqual(result["OFF"], mock_fault_counter_1)
        self.assertEqual(result["MGT"], mock_fault_counter_2)

        # Edge Case for Empty Fault
        cavity1.faults = OrderedDict()
        empty_result: DefaultDict[str, FaultCounter] = cavity1.get_fault_counts(
            start_time, end_time
        )
        self.assertEqual(len(empty_result), 0)

        # 4. Need to verify get_fault_count_over_time_range was called for each fault
        for fault in mock_faults:
            fault.get_fault_count_over_time_range.assert_called_once_with(
                start_time=start_time, end_time=end_time
            )

    @mock.patch("displays.cavity_display.backend.backend_cavity.caput")
    def test_run_through_faults(self, mock_caput):
        # 1st part we're testing is: No faults
        self.cavity1.faults = OrderedDict()

        # Calling method
        self.cavity1.run_through_faults()

        mock_caput.assert_any_call("STATUS_PV", "1")
        mock_caput.assert_any_call("SEVERITY_PV", 0)
        mock_caput.assert_any_call("DESCRIPTION_PV", " ")

        # 2nd part im thinking testing: We have 1 fault

        # 3rd part im thinking testing: Invalid PV

        # WIP
