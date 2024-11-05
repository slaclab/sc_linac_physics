from collections import OrderedDict
from datetime import timedelta, datetime
from typing import DefaultDict
from unittest import TestCase, mock

from displays.cavity_display.backend.backend_cavity import BackendCavity
from displays.cavity_display.backend.backend_machine import BackendMachine
from displays.cavity_display.backend.fault import FaultCounter
from tests.displays.cavity_display.utils.utils import mock_open
from utils.sc_linac.cryomodule import Cryomodule

builtin_open = open  # save the unpatched version


class TestBackendCavity(TestCase):
    @classmethod
    def setUpClass(cls):
        # We are setting up the mock for the test class. (Replacing the open func)
        cls.mock_open_patcher = mock.patch("builtins.open", mock_open)
        cls.mock_open_patcher.start()
        # Create display Machine
        cls.DISPLAY_MACHINE = BackendMachine(lazy_fault_pvs=True)

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
