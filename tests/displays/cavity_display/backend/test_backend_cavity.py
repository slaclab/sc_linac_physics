from collections import OrderedDict
from datetime import timedelta, datetime
from random import randint, choice
from typing import DefaultDict
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.backend.fault import (
    FaultCounter,
    Fault,
)
from tests.displays.cavity_display.test_utils.utils import mock_parse


@pytest.fixture
def cavity():
    cav_num = randint(1, 8)
    rack = MagicMock()
    rack.rack_name = "A" if cav_num <= 4 else "B"

    rack.cryomodule.linac.machine.lazy_fault_pvs = True
    with patch(
        "sc_linac_physics.displays.cavity_display.utils.utils.parse_csv",
        mock_parse,
    ):
        cavity = BackendCavity(cavity_num=cav_num, rack_object=rack)
        cavity._status_pv_obj = make_mock_pv()
        cavity._severity_pv_obj = make_mock_pv()
        cavity._description_pv_obj = make_mock_pv()
        for fault in cavity.faults.values():
            fault.is_currently_faulted = MagicMock(return_value=False)

        yield cavity


def test_create_faults(cavity):
    cavity.create_faults()

    # mock rack fault is for rack A
    if cavity.number <= 4:
        assert len(cavity.faults.items()) == 6
    else:
        assert len(cavity.faults.items()) == 5


@pytest.mark.skip(reason="this tests the old version of the function")
def test_get_fault_counts(cavity):
    # Making Mock fault objects w/ values
    mock_fault_counter_1 = FaultCounter(
        alarm_count=5, ok_count=3, invalid_count=0
    )
    mock_fault_counter_2 = FaultCounter(
        alarm_count=3, ok_count=5, invalid_count=1
    )
    mock_fault_counter_3 = FaultCounter(
        alarm_count=1, ok_count=8, invalid_count=2
    )
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
    cavity.faults = OrderedDict(
        (i, fault) for i, fault in enumerate(mock_faults)
    )

    # Test
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=1)

    # Calling function we are testing w/ our time range.
    result: DefaultDict[str, FaultCounter] = cavity.get_fault_counts(
        start_time, end_time
    )

    # Our assertions
    # 1. results needs to be an instance of dict
    assert isinstance(result, dict)
    assert len(result) == 2

    # 3. Making sure FaultCounter obj with the highest sum of
    #    fault_count+invalid_count is in the result for its associated TLC
    assert result["OFF"] == mock_fault_counter_1
    assert result["MGT"] == mock_fault_counter_2

    # Edge Case for Empty Fault
    cavity.faults = OrderedDict()
    empty_result: DefaultDict[str, FaultCounter] = cavity.get_fault_counts(
        start_time, end_time
    )
    assert len(empty_result) == 0

    # 4. Need to verify get_fault_count_over_time_range was called for each fault
    for fault in mock_faults:
        fault.get_fault_count_over_time_range.assert_called_once_with(
            start_time=start_time, end_time=end_time
        )


def test_run_through_faults_not_faulted(cavity):
    """1st part we're testing is: No faults"""

    # Calling method
    cavity.run_through_faults()

    cavity._status_pv_obj.put.assert_called_with(str(cavity.number))
    cavity._severity_pv_obj.put.assert_called_with(0)
    cavity._description_pv_obj.put.assert_called_with(" ")


def test_run_through_faults_faulted(cavity):
    """Test that faulted cavity updates status correctly."""
    from unittest.mock import patch

    faulted_fault: Fault = choice(list(cavity.faults.values()))
    print(f"Fault mocked as faulted: {faulted_fault.pv}")
    faulted_fault.is_currently_faulted = MagicMock(return_value=True)

    # Force batch read to fail so it uses sequential fallback
    with patch(
        "sc_linac_physics.utils.epics.batch.PVBatch.get_values",
        side_effect=Exception("Mocked failure"),
    ):
        cavity.run_through_faults()

    cavity._status_pv_obj.put.assert_called_with(faulted_fault.tlc)
    cavity._severity_pv_obj.put.assert_called_with(faulted_fault.severity)
    cavity._description_pv_obj.put.assert_called_with(
        faulted_fault.short_description
    )


def _make_handler(samples):
    """Build an ArchiveDataHandler-like mock from (value, timestamp) pairs."""
    handler = MagicMock()
    handler.values = [value for value, _ in samples]
    handler.timestamps = [ts for _, ts in samples]
    return handler


class TestProcessFaultHistory:
    def test_counts_and_events_match_severities(self, cavity):
        """Statuses pick up the severity in effect at their timestamp."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        statuses = _make_handler(
            [
                ("SSA", base + timedelta(seconds=10)),
                (str(cavity.number), base + timedelta(seconds=20)),
                ("QCH", base + timedelta(seconds=30)),
            ]
        )
        severities = _make_handler(
            [
                (2, base + timedelta(seconds=10)),  # alarm during SSA
                (0, base + timedelta(seconds=20)),
                (1, base + timedelta(seconds=30)),  # warning during QCH
            ]
        )

        counts, events = cavity.process_fault_history(statuses, severities)

        assert counts["SSA"].alarm_count == 1
        assert counts["QCH"].warning_count == 1
        # All three transitions recorded, including the OK one
        assert len(events) == 3
        assert events[0].severity == 2
        assert events[1].severity == 0  # the OK clear
        assert events[2].severity == 1
        assert events[0].timestamp < events[1].timestamp < events[2].timestamp

    def test_severity_matching_equivalent_to_per_sample_scan(self, cavity):
        """The merge pass must match severity_of_fault's per-sample scan."""
        from sc_linac_physics.displays.cavity_display.utils.utils import (
            severity_of_fault,
        )

        base = datetime(2025, 6, 2, 12, 0, 0)
        # offset timestamps so the matching isn't trivial
        severities = _make_handler(
            [(i % 4, base + timedelta(seconds=5 * i)) for i in range(40)]
        )
        statuses = _make_handler(
            [("SSA", base + timedelta(seconds=3 + 7 * i)) for i in range(25)]
        )

        _, events = cavity.process_fault_history(statuses, severities)

        for event in events:
            ts = cavity._round_to_10ms(event.timestamp)
            assert event.severity == severity_of_fault(ts, severities)

    def test_status_before_any_severity_counts_invalid(self, cavity):
        """A status sample with no severity yet has severity None."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        statuses = _make_handler([("SSA", base)])
        severities = _make_handler([(2, base + timedelta(seconds=10))])

        counts, events = cavity.process_fault_history(statuses, severities)

        assert counts["SSA"].invalid_count == 1
        assert events[0].severity is None
