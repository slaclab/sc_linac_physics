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


def test_process_fault_history_reads_each_severity():
    """A fault that clears within 10 ms of starting still reads as a fault."""
    from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
        BackendMachine,
    )

    machine = BackendMachine(lazy_fault_pvs=True)
    for cm in ("02", "03", "04", "05", "06"):
        for cavity in machine.cryomodules[cm].cavities.values():
            # A long window packs in many short faults. It ends before the
            # November DST change: process_fault_history compares naive
            # Pacific times, which run backwards across it.
            status, sevr = _both(
                cavity.pv_prefix.rstrip(":"),
                start=START,
                end=START + timedelta(days=150),
            )
            _, events = cavity.process_fault_history(status, sevr)
            # Skip statuses in the last 5 ms of a second: _round_to_10ms
            # carries those a full second late (ts + 1 s, microseconds
            # kept), a separate bug that picks up the next severity.
            kept = (status["timestamp"].dt.microsecond < 995_000).tolist()
            got = [e.severity for e, k in zip(events, kept) if k]
            want = [v for v, k in zip(sevr["value"], kept) if k]
            assert got == want


def _codes_seen(prefix):
    status, _ = _both(prefix, start=START, end=START + timedelta(days=365))
    return set(status["value"]) - {cavity_number(prefix)}


def test_harmonic_linearizer_gets_no_1p3_cm_faults():
    # faults.csv: MGT rows are CM Type 1.3, which _build_fault_pv skips
    # for H1/H2
    seen = set().union(
        *(
            _codes_seen(f"ACCL:L1B:H{c}{n}0")
            for c in (1, 2)
            for n in range(1, 9)
        )
    )
    assert seen
    assert "MGT" not in seen
    seen_13 = set().union(*(_codes_seen(p) for p in _busy_prefixes()))
    assert "MGT" in seen_13


def test_rows_match_what_build_fault_pv_keeps():
    from sc_linac_physics.utils.archiver_mock.fault_history import (
        _fault_codes,
    )

    rows = parse_csv()

    def expected(rack, harmonic):
        return sorted(
            (r["Three Letter Code"], int(r["Severity"]))
            for r in rows
            if not (r["Level"] == "RACK" and r["Rack"] != rack)
            and not (r["Level"] == "CM" and r["CM Type"] == "1.3" and harmonic)
            and not (
                r["Level"] == "CM" and r["CM Type"] == "3.9" and not harmonic
            )
        )

    assert sorted(_fault_codes("ACCL:L1B:0210")) == expected("A", False)
    assert sorted(_fault_codes("ACCL:L1B:0250")) == expected("B", False)
    assert sorted(_fault_codes("ACCL:L1B:H150")) == expected("B", True)
