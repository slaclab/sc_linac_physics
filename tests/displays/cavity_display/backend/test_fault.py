from random import randint
from unittest import TestCase

from displays.cavity_display.backend.fault import FaultCounter


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

    def test_ratio_ok(self):
        self.skipTest("Not yet implemented")

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


class TestFault(TestCase):
    def test_is_currently_faulted(self):

        self.fail()

    def test_is_faulted(self):

        self.fail()

    def test_was_faulted(self):

        self.fail()

    def test_get_fault_count_over_time_range(self):

        self.fail()
