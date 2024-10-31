from unittest import TestCase
from unittest.mock import MagicMock, patch
from random import randint
from datetime import datetime

from displays.cavity_display.backend.fault import FaultCounter

from lcls_tools.common.controls.pyepics.utils import (
    make_mock_pv,
    EPICS_INVALID_VAL,
    PVInvalidError,
)
from lcls_tools.common.data.archiver import ArchiverValue, ArchiveDataHandler

archiver_value = ArchiverValue()
get_data_at_time_mock = MagicMock(return_value={"PV": archiver_value})
get_values_over_time_range_mock = MagicMock(
    return_value={"PV": ArchiveDataHandler([archiver_value])}
)


@patch.multiple(
    'lcls_tools.common.data.archiver',
    get_data_at_time=get_data_at_time_mock,
    get_values_over_time_range=get_values_over_time_range_mock
)
class TestFault(TestCase):
    def setUp(self):
        from displays.cavity_display.backend.fault import Fault
        self.fault = Fault(
            severity=0,
            tlc="test_tlc",
            pv="test_pv",
            ok_value=None,  # Changed from 1 to None
            fault_value=None,  # Start with None, will be set in specific tests
            long_description="Test long description",
            short_description="Test short description",
            button_level=1,
            button_command="test_command",
            macros={},
            button_text="Test Button",
            button_macro={},
            action=None
        )

    def test_pv_obj(self):
        self.fault._pv_obj = MagicMock()
        self.assertEqual(self.fault.pv_obj, self.fault._pv_obj)

    def test_is_currently_faulted(self):
        self.fault.is_faulted = MagicMock()
        self.fault._pv_obj = make_mock_pv()
        self.fault.is_currently_faulted()
        self.fault.is_faulted.assert_called_with(self.fault._pv_obj)

    def test_is_faulted_invalid(self):
        pv = make_mock_pv(severity=EPICS_INVALID_VAL)
        self.assertRaises(PVInvalidError, self.fault.is_faulted, pv)

    def test_is_faulted_ok(self):
        pv = make_mock_pv()
        pv.val = 5
        # Test with ok_value
        self.fault.ok_value = 5
        self.fault.fault_value = None
        self.assertFalse(self.fault.is_faulted(pv))

        self.fault.ok_value = 3
        self.assertTrue(self.fault.is_faulted(pv))

    def test_is_faulted(self):
        pv = make_mock_pv()
        pv.val = 5
        # Test with fault_value
        self.fault.ok_value = None  # Make sure ok_value is None
        self.fault.fault_value = 5
        self.assertTrue(self.fault.is_faulted(pv))

        self.fault.fault_value = 3
        self.assertFalse(self.fault.is_faulted(pv))

    def test_is_faulted_exception(self):
        pv = make_mock_pv()
        # Set both values to None to trigger the exception
        self.fault.ok_value = None
        self.fault.fault_value = None
        self.assertRaises(Exception, self.fault.is_faulted, pv)

    @patch('displays.cavity_display.backend.fault.get_data_at_time', get_data_at_time_mock)
    def test_was_faulted(self):
        self.fault.pv = "PV"
        self.fault.is_faulted = MagicMock()
        self.fault.was_faulted(datetime.now())
        self.fault.is_faulted.assert_called_with(archiver_value)

    def test_get_fault_count_over_time_range(self):
        self.skipTest("Not yet implemented")

    # Double checking that the patch.multiple is working.
    def test_mocks_are_applied(self):
        from lcls_tools.common.data.archiver import get_data_at_time, get_values_over_time_range
        self.assertEqual(get_data_at_time, get_data_at_time_mock)
        self.assertEqual(get_values_over_time_range, get_values_over_time_range_mock)


class TestFaultCounter(TestCase):
    def setUp(self):
        max_rand_count = 1
        self.ok_count = randint(0, max_rand_count)
        self.fault_count = randint(0, max_rand_count)
        self.invalid_count = randint(0, max_rand_count)

        self.fault_counter = FaultCounter(
            ok_count=self.ok_count,
            fault_count=self.fault_count,
            invalid_count=self.invalid_count,
        )

        self.ok_count2 = randint(0, max_rand_count)
        self.fault_count2 = randint(0, max_rand_count)
        self.invalid_count2 = randint(0, max_rand_count)

        self.fault_counter2 = FaultCounter(
            ok_count=self.ok_count2,
            fault_count=self.fault_count2,
            invalid_count=self.invalid_count2,
        )

    def test_sum_fault_count(self):
        self.assertEqual(
            self.fault_count + self.invalid_count, self.fault_counter.sum_fault_count
        )

    def test_gt(self):
        if self.fault_counter.sum_fault_count > self.fault_counter2.sum_fault_count:
            self.assertTrue(self.fault_counter > self.fault_counter2)
        else:
            self.assertFalse(self.fault_counter > self.fault_counter2)

    def test_eq(self):
        if self.fault_counter.sum_fault_count == self.fault_counter2.sum_fault_count:
            self.assertTrue(self.fault_counter == self.fault_counter2)
        else:
            self.assertFalse(self.fault_counter == self.fault_counter2)
