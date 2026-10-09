from datetime import timedelta, datetime, timezone
from random import randint, choice
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.backend.fault import Fault
from sc_linac_physics.utils.archiver import LOCAL_TZ
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


def _make_frame(samples):
    """A frame like utils.archiver returns, from (value, naive time) pairs.

    Times are read as Pacific, as the archiver client returns them.
    """
    return pd.DataFrame(
        {
            "timestamp": [ts.replace(tzinfo=LOCAL_TZ) for _, ts in samples],
            "value": [value for value, _ in samples],
        }
    )


def _severity_at(timestamp, severity_samples):
    """Reference scan: the last severity at or before timestamp.

    Copied from utils.severity_of_fault, removed from src as unused, so the
    merge pass in process_fault_history still has something to match.
    """
    sevr = None
    for severity, severity_timestamp in severity_samples:
        try:
            rounded_ts = severity_timestamp.replace(
                microsecond=round(severity_timestamp.microsecond / 10000)
                * 10000
            )
        except ValueError:
            rounded_ts = severity_timestamp + timedelta(seconds=1)
        if (timestamp - rounded_ts).total_seconds() >= 0:
            sevr = severity
        else:
            break
    return sevr


class TestProcessFaultHistory:
    def test_counts_and_events_match_severities(self, cavity):
        """Statuses pick up the severity in effect at their timestamp."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        statuses = _make_frame(
            [
                ("SSA", base + timedelta(seconds=10)),
                (str(cavity.number), base + timedelta(seconds=20)),
                ("QCH", base + timedelta(seconds=30)),
            ]
        )
        severities = _make_frame(
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
        """The merge pass must match a per-sample scan of the severities."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        # offset timestamps so the matching isn't trivial
        severity_samples = [
            (i % 4, base + timedelta(seconds=5 * i)) for i in range(40)
        ]
        severities = _make_frame(severity_samples)
        statuses = _make_frame(
            [("SSA", base + timedelta(seconds=3 + 7 * i)) for i in range(25)]
        )

        _, events = cavity.process_fault_history(statuses, severities)

        for event in events:
            ts = cavity._round_to_10ms(event.timestamp)
            assert event.severity == _severity_at(ts, severity_samples)

    def test_status_before_any_severity_counts_invalid(self, cavity):
        """A status sample with no severity yet has severity None."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        statuses = _make_frame([("SSA", base)])
        severities = _make_frame([(2, base + timedelta(seconds=10))])

        counts, events = cavity.process_fault_history(statuses, severities)

        assert counts["SSA"].invalid_count == 1
        assert events[0].severity is None

    def test_event_times_are_naive_pacific(self, cavity):
        """The heatmap compares event times with naive Qt times."""
        base = datetime(2025, 6, 2, 12, 0, 0)
        statuses = _make_frame([("SSA", base)])
        severities = _make_frame([(2, base)])

        _, events = cavity.process_fault_history(statuses, severities)

        assert events[0].timestamp == base
        assert events[0].timestamp.tzinfo is None

    def test_fall_back_hour_keeps_archiver_order(self, cavity):
        """Both 01:30s on 2024-11-03 become naive 01:30, still in order."""
        pdt = datetime(2024, 11, 3, 8, 30, tzinfo=timezone.utc)
        pst = datetime(2024, 11, 3, 9, 30, tzinfo=timezone.utc)
        statuses = pd.DataFrame(
            {"timestamp": [pdt, pst], "value": ["SSA", "QCH"]}
        )
        severities = pd.DataFrame({"timestamp": [pdt], "value": [2]})

        _, events = cavity.process_fault_history(statuses, severities)

        assert [e.status for e in events] == ["SSA", "QCH"]
        assert [e.timestamp for e in events] == [
            datetime(2024, 11, 3, 1, 30)
        ] * 2


class TestGetFaultHistory:
    def test_fetches_status_and_severity_pvs(self, cavity):
        start = datetime(2025, 6, 2, 12, 0)
        end = datetime(2025, 6, 2, 13, 0)
        status_pv = cavity.pv_addr("CUDSTATUS")
        sevr_pv = cavity.pv_addr("CUDSEVR")
        frames = {
            status_pv: _make_frame([("SSA", start)]),
            sevr_pv: _make_frame([(2, start)]),
        }
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.backend_cavity"
            ".get_values_over_time_range",
            return_value=frames,
        ) as fetch:
            counts, events = cavity.get_fault_history(start, end)

        fetch.assert_called_once_with([status_pv, sevr_pv], start, end)
        assert counts["SSA"].alarm_count == 1
        assert events[0].timestamp == start

    def test_archiver_error_returns_empty(self, cavity):
        with patch(
            "sc_linac_physics.displays.cavity_display.backend.backend_cavity"
            ".get_values_over_time_range",
            side_effect=RuntimeError("archiver down"),
        ):
            counts, events = cavity.get_fault_history(
                datetime(2025, 6, 2, 12, 0), datetime(2025, 6, 2, 13, 0)
            )

        assert len(counts) == 0
        assert events == []
