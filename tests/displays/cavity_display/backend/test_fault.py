from datetime import datetime
from random import randint
from unittest import TestCase
from unittest.mock import MagicMock, patch

from lcls_tools.common.data.archiver import ArchiverValue, ArchiveDataHandler

from sc_linac_physics.displays.cavity_display.backend.fault import (
    Fault,
    FaultCounter,
)
from sc_linac_physics.utils.epics import (
    make_mock_pv,
    EPICS_INVALID_VAL,
    PVInvalidError,
)

archiver_value = ArchiverValue()
get_data_at_time_mock = MagicMock(return_value={"PV": archiver_value})
get_values_over_time_range_mock = MagicMock(
    return_value={"PV": ArchiveDataHandler([archiver_value])}
)


@patch.multiple(
    "lcls_tools.common.data.archiver",
    get_data_at_time=get_data_at_time_mock,
    get_values_over_time_range=get_values_over_time_range_mock,
)
class TestFault(TestCase):
    def setUp(self):
        self.fault = Fault(severity=0, lazy_pv=True)

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
        pv.val = 5
        # Test with ok_value
        self.fault.ok_value = 5
        self.assertFalse(self.fault.is_faulted(pv))

        self.fault.ok_value = 3
        self.assertTrue(self.fault.is_faulted(pv))

    def test_is_faulted(self):
        pv: MagicMock = make_mock_pv()
        pv.val = 5
        # Test with fault_value
        self.fault.fault_value = 5
        self.assertTrue(self.fault.is_faulted(pv))

        self.fault.fault_value = 3
        self.assertFalse(self.fault.is_faulted(pv))

    def test_is_faulted_exception(self):
        pv: MagicMock = make_mock_pv()
        self.assertRaises(Exception, self.fault.is_faulted, pv)

    @patch(
        "sc_linac_physics.displays.cavity_display.backend.fault.get_data_at_time",
        get_data_at_time_mock,
    )
    def test_was_faulted(self):
        self.fault.pv = "PV"
        self.fault.is_faulted = MagicMock()
        self.fault.was_faulted(datetime.now())
        self.fault.is_faulted.assert_called_with(archiver_value)

    def test_get_fault_count_over_time_range(self):
        self.skipTest("Not yet implemented")

    # Double checking that the patch.multiple is working.
    def test_mocks_are_applied(self):
        from lcls_tools.common.data.archiver import (
            get_data_at_time,
            get_values_over_time_range,
        )

        self.assertEqual(get_data_at_time, get_data_at_time_mock)
        self.assertEqual(
            get_values_over_time_range, get_values_over_time_range_mock
        )


class TestFaultCounter(TestCase):
    def setUp(self):
        max_rand_count = 1
        self.ok_count = randint(0, max_rand_count)
        self.fault_count = randint(0, max_rand_count)
        self.invalid_count = randint(0, max_rand_count)

        self.fault_counter = FaultCounter(
            ok_count=self.ok_count,
            alarm_count=self.fault_count,
            invalid_count=self.invalid_count,
        )

        self.ok_count2 = randint(0, max_rand_count)
        self.fault_count2 = randint(0, max_rand_count)
        self.invalid_count2 = randint(0, max_rand_count)

        self.fault_counter2 = FaultCounter(
            ok_count=self.ok_count2,
            alarm_count=self.fault_count2,
            invalid_count=self.invalid_count2,
        )

    def test_sum_fault_count(self):
        self.assertEqual(
            self.fault_count + self.invalid_count,
            self.fault_counter.sum_fault_count,
        )

    def test_ratio_ok(self):
        self.skipTest("Not yet implemented")

    def test_gt(self):
        if (
            self.fault_counter.sum_fault_count
            > self.fault_counter2.sum_fault_count
        ):
            self.assertTrue(self.fault_counter > self.fault_counter2)
        else:
            self.assertFalse(self.fault_counter > self.fault_counter2)

    def test_eq(self):
        if (
            self.fault_counter.sum_fault_count
            == self.fault_counter2.sum_fault_count
        ):
            self.assertTrue(self.fault_counter == self.fault_counter2)
        else:
            self.assertFalse(self.fault_counter == self.fault_counter2)
