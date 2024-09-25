from unittest import TestCase, mock
from unittest.mock import MagicMock, patch
from lcls_tools.common.controls.pyepics.utils import (
    make_mock_pv,
    EPICS_INVALID_VAL,
    PVInvalidError,
)
from lcls_tools.common.data.archiver import ArchiverValue, ArchiveDataHandler

archiver_value = ArchiverValue()
get_data_at_time_mock = MagicMock(return_value={"PV": archiver_value})
get_values_over_time_range_mock = MagicMock(return_value={"PV": ArchiveDataHandler([archiver_value])})

@patch.multiple('lcls_tools.common.data.archiver',
                get_data_at_time=get_data_at_time_mock,
                get_values_over_time_range=get_values_over_time_range_mock)

class TestFault(TestCase):
    def setUp(self):
        from displays.cavity_display.backend.fault import Fault, FaultCounter
        self.fault = Fault(severity=0)

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
        pv: MagicMock = make_mock_pv()
        self.fault.ok_value = 5
        pv.val = 5
        self.assertFalse(self.fault.is_faulted(pv))

        self.fault.ok_value = 3
        self.assertTrue(self.fault.is_faulted(pv))

    def test_is_faulted(self):
        pv: MagicMock = make_mock_pv()
        self.fault.fault_value = 5
        pv.val = 5
        self.assertTrue(self.fault.is_faulted(pv))

        self.fault.fault_value = 3
        self.assertFalse(self.fault.is_faulted(pv))

    def test_is_faulted_exception(self):
        pv: MagicMock = make_mock_pv()
        self.assertRaises(Exception, self.fault.is_faulted, pv)

    # def test_was_faulted(self):
    #     self.fault.pv = "PV"
    #     self.fault.is_faulted = MagicMock()
    #     self.fault.was_faulted(datetime.now())
    #     self.fault.is_faulted.assert_called_with(archiver_value)

    def test_get_fault_count_over_time_range(self):

        self.skipTest("Not yet implemented")
    # Double checking that the patch.multiple is working.
    def test_mocks_are_applied(self):
        from lcls_tools.common.data.archiver import get_data_at_time, get_values_over_time_range
        self.assertEqual(get_data_at_time, get_data_at_time_mock)
        self.assertEqual(get_values_over_time_range, get_values_over_time_range_mock)