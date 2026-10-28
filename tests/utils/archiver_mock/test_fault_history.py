from datetime import datetime, timedelta

import pandas as pd

from sc_linac_physics.displays.cavity_display.backend.fault import (
    SeverityLevel,
)
from sc_linac_physics.displays.cavity_display.utils.utils import parse_csv
from sc_linac_physics.utils import archiver
from sc_linac_physics.utils.archiver_mock import mock_values_over_time_range
from sc_linac_physics.utils.archiver_mock.fault_history import (
    MAX_FAULTS_PER_WINDOW,
    cavity_number,
)

START = datetime(2025, 6, 2, tzinfo=archiver.LOCAL_TZ)
END = START + timedelta(days=7)
PREFIX = "ACCL:L1B:0230"
# Some codes appear on several rows with different severities
PAIRS = {
    (row["Three Letter Code"], int(row["Severity"])) for row in parse_csv()
}


def _both(prefix=PREFIX, start=START, end=END):
    status, sevr = f"{prefix}:CUDSTATUS", f"{prefix}:CUDSEVR"
    frames = mock_values_over_time_range([status, sevr], start, end)
    return frames[status], frames[sevr]


def _busy_prefixes(n=40):
    """Cavity prefixes across several cryomodules."""
    return [
        f"ACCL:L1B:{cm:02d}{cav}0"
        for cm in (2, 3, 4, 5, 6)
        for cav in range(1, 9)
    ][:n]


def test_status_and_severity_share_timestamps():
    status, sevr = _both()
    pd.testing.assert_series_equal(status["timestamp"], sevr["timestamp"])
    assert list(status.columns) == archiver.COLUMNS
    assert status["valid"].all()


def test_opens_ok_at_window_start():
    status, sevr = _both()
    assert status["timestamp"].iloc[0] == START
    assert status["value"].iloc[0] == "3"  # cavity 3's own number
    assert sevr["value"].iloc[0] == SeverityLevel.NO_ALARM


def test_values_are_what_the_runner_writes():
    for prefix in _busy_prefixes():
        status, sevr = _both(prefix)
        ok = cavity_number(prefix)
        for code, severity in zip(status["value"], sevr["value"]):
            if code == ok:
                assert severity == SeverityLevel.NO_ALARM
            else:
                assert (code, severity) in PAIRS  # a faults.csv row


def test_events_in_time_order_and_faults_clear():
    for prefix in _busy_prefixes():
        status, _ = _both(prefix)
        assert status["timestamp"].is_monotonic_increasing
        assert status["timestamp"].is_unique
    # A fault can follow another before it clears, as when the runner sees
    # a different fault first; but faults do clear back to OK
    prefix = _busy_prefixes()[0]
    status, _ = _both(prefix)
    assert (status["value"] == cavity_number(prefix)).sum() > 1


def test_rates_vary_across_cavities():
    counts = [
        int((_both(p)[0]["value"] != cavity_number(p)).sum())
        for p in _busy_prefixes()
    ]
    assert min(counts) < max(counts)
    assert max(counts) > 0


def test_same_timeline_whichever_pv_is_fetched_first():
    status_alone = mock_values_over_time_range(
        [f"{PREFIX}:CUDSTATUS"], START, END
    )[f"{PREFIX}:CUDSTATUS"]
    status, _ = _both()
    pd.testing.assert_frame_equal(status_alone, status)


def test_process_fault_history_reads_it():
    from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
        BackendMachine,
    )

    cavity = BackendMachine(lazy_fault_pvs=True).cryomodules["02"].cavities[3]
    status, sevr = _both(cavity.pv_prefix.rstrip(":"))
    counts, events = cavity.process_fault_history(status, sevr)
    n_faults = int((status["value"] != str(cavity.number)).sum())
    counted = sum(
        c.alarm_count + c.warning_count + c.invalid_count + c.ok_count
        for c in counts.values()
    )
    assert counted == n_faults  # every fault event counted once
    assert len(events) == len(status)


def test_cavity_number():
    assert cavity_number("ACCL:L1B:0210") == "1"
    assert cavity_number("ACCL:L1B:H180") == "8"


def test_fault_count_is_capped():
    status, _ = _both(start=START, end=START + timedelta(days=3650))
    assert len(status) <= 2 * MAX_FAULTS_PER_WINDOW + 1


def test_empty_window():
    status, _ = _both(start=END, end=START)
    assert status.empty
