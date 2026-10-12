import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from sc_linac_physics.utils import archiver
from sc_linac_physics.utils.archiver import (
    ArchiverConnectionError,
    ArchiverError,
    ArchiverTimeoutError,
    PVNotArchivedError,
    get_values_at_time,
    get_values_over_time_range,
)

START = datetime(2023, 10, 2, 9, 13)  # naive: read as Pacific (PDT, -07:00)
END = datetime(2023, 10, 2, 10, 0)


def _response(status=200, payload=None, nbytes=0):
    response = MagicMock()
    response.content = b"x" * nbytes
    response.status_code = status
    response.ok = status < 400
    response.json.return_value = payload
    return response


def _datum(secs, val, severity=0, nanos=0):
    return {"secs": secs, "val": val, "nanos": nanos, "severity": severity}


@pytest.fixture
def session():
    s = MagicMock()
    with (
        patch.object(archiver, "_session", return_value=s),
        patch.object(archiver, "sleep") as _,
    ):
        yield s


class TestRange:
    def test_one_request_per_pv(self, session):
        session.request.return_value = _response(
            payload=[{"meta": {}, "data": [_datum(1696263180, 1.5)]}]
        )

        frames = get_values_over_time_range(["A:PV", "B:PV"], START, END)

        assert set(frames) == {"A:PV", "B:PV"}
        sent = sorted(
            c.kwargs["params"]["pv"] for c in session.request.call_args_list
        )
        assert sent == ["A:PV", "B:PV"]

    def test_naive_times_are_sent_as_pacific_in_utc(self, session):
        session.request.return_value = _response(payload=[])

        get_values_over_time_range(["A:PV"], START, END)

        params = session.request.call_args.kwargs["params"]
        assert params["from"] == "2023-10-02T16:13:00.000000Z"
        assert params["to"] == "2023-10-02T17:00:00.000000Z"

    def test_standard_time_offset_in_winter(self, session):
        session.request.return_value = _response(payload=[])

        get_values_over_time_range(
            ["A:PV"], datetime(2024, 1, 5, 8, 0), datetime(2024, 1, 5, 9, 0)
        )

        assert (
            session.request.call_args.kwargs["params"]["from"]
            == "2024-01-05T16:00:00.000000Z"
        )

    def test_aware_times_are_converted(self, session):
        session.request.return_value = _response(payload=[])
        utc_start = datetime(2023, 10, 2, 16, 13, tzinfo=timezone.utc)

        get_values_over_time_range(["A:PV"], utc_start, END)

        assert (
            session.request.call_args.kwargs["params"]["from"]
            == "2023-10-02T16:13:00.000000Z"
        )

    def test_frame_columns_values_and_validity(self, session):
        session.request.return_value = _response(
            payload=[
                {
                    "meta": {},
                    "data": [
                        _datum(1696263180, 1.5, nanos=500_000_000),
                        _datum(1696263181, 2.5, severity=3),  # INVALID
                    ],
                }
            ]
        )

        frame = get_values_over_time_range(["A:PV"], START, END)["A:PV"]

        assert list(frame.columns) == archiver.COLUMNS
        assert frame["value"].tolist() == [1.5, 2.5]
        assert frame["valid"].tolist() == [True, False]
        first = frame["timestamp"].iloc[0]
        assert first.tzinfo is not None
        assert first == datetime(
            2023, 10, 2, 16, 13, 0, 500_000, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("payload", [[], [{"meta": {}, "data": []}]])
    def test_no_samples_gives_empty_frame(self, session, payload):
        session.request.return_value = _response(payload=payload)

        frame = get_values_over_time_range(["A:PV"], START, END)["A:PV"]

        assert frame.empty
        assert list(frame.columns) == archiver.COLUMNS

    def test_unknown_pvs_are_all_named_once_every_request_ends(self, session):
        def respond(method, url, timeout, params):
            if params["pv"] == "GOOD:PV":
                return _response(payload=[])
            return _response(status=404)

        session.request.side_effect = respond

        with pytest.raises(PVNotArchivedError) as err:
            get_values_over_time_range(
                ["BAD:A", "GOOD:PV", "BAD:B"], START, END
            )

        assert err.value.pvs == ["BAD:A", "BAD:B"]
        assert session.request.call_count == 3


class TestRetries:
    def test_timeout_retried_then_succeeds(self, session):
        session.request.side_effect = [
            requests.exceptions.Timeout(),
            _response(payload=[]),
        ]

        frames = get_values_over_time_range(["A:PV"], START, END)

        assert frames["A:PV"].empty
        assert session.request.call_count == 2

    def test_timeout_on_every_attempt_raises(self, session):
        session.request.side_effect = requests.exceptions.Timeout()

        with pytest.raises(ArchiverTimeoutError):
            get_values_over_time_range(["A:PV"], START, END)

        assert session.request.call_count == archiver.MAX_RETRIES

    def test_connection_error_raises_after_retries(self, session):
        session.request.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(ArchiverConnectionError):
            get_values_over_time_range(["A:PV"], START, END)

    def test_server_error_is_retried(self, session):
        session.request.side_effect = [_response(503), _response(payload=[])]

        get_values_over_time_range(["A:PV"], START, END)

        assert session.request.call_count == 2

    def test_client_error_raises_without_retry(self, session):
        session.request.return_value = _response(400)

        with pytest.raises(ArchiverError, match="HTTP 400"):
            get_values_over_time_range(["A:PV"], START, END)

        assert session.request.call_count == 1


class TestAtTime:
    def test_one_post_for_all_pvs(self, session):
        session.request.return_value = _response(
            payload={
                "A:PV": _datum(1696264199, 0.5),
                "B:PV": _datum(1696264199, 0.0),
            }
        )

        samples = get_values_at_time(
            ["A:PV", "B:PV"], datetime(2023, 10, 2, 9, 30)
        )

        method, url = session.request.call_args.args
        assert method == "POST" and url.endswith("/getDataAtTime")
        assert session.request.call_args.kwargs["json"] == ["A:PV", "B:PV"]
        assert session.request.call_args.kwargs["params"]["at"] == (
            "2023-10-02T16:30:00.000000Z"
        )
        assert samples["A:PV"].value == 0.5
        assert samples["A:PV"].valid

    def test_pv_without_value_is_left_out(self, session):
        session.request.return_value = _response(
            payload={"A:PV": _datum(1, 1.0)}
        )

        samples = get_values_at_time(
            ["A:PV", "NOT:A:PV"], datetime(2023, 10, 2)
        )

        assert list(samples) == ["A:PV"]

    def test_invalid_severity(self, session):
        session.request.return_value = _response(
            payload={"A:PV": _datum(1, 1.0, severity=3)}
        )

        assert not get_values_at_time(["A:PV"], datetime(2023, 10, 2))[
            "A:PV"
        ].valid

    def test_http_error_raises_instead_of_returning_empty(self, session):
        session.request.return_value = _response(400)

        with pytest.raises(ArchiverError):
            get_values_at_time(["A:PV"], datetime(2023, 10, 2))


def test_at_time_404_returns_empty(session):
    session.request.return_value = _response(404)

    assert get_values_at_time(["NOT:A:PV"], datetime(2023, 10, 2)) == {}


def test_each_thread_gets_its_own_session():
    import threading

    sessions = []
    thread = threading.Thread(
        target=lambda: sessions.append(archiver._session())
    )
    thread.start()
    thread.join()

    assert archiver._session() is archiver._session()
    assert sessions[0] is not archiver._session()


# ---------------------------------------------------------------------------
# get_series / pair_by_time
# ---------------------------------------------------------------------------
def test_get_series_keeps_valid_samples_indexed_by_time(session):
    session.request.return_value = _response(
        payload=[
            {
                "meta": {},
                "data": [
                    _datum(1696263180, 1.5),
                    _datum(1696263181, 9.9, severity=3),  # INVALID, dropped
                    _datum(1696263182, 2.5),
                ],
            }
        ]
    )

    series = archiver.get_series(["A:PV"], START, END)["A:PV"]

    assert series.name == "A:PV"
    assert series.tolist() == [1.5, 2.5]
    assert series.index[0] == datetime(2023, 10, 2, 16, 13, tzinfo=timezone.utc)


def _series(name, secs_vals):
    import pandas as pd

    return pd.Series(
        [v for _, v in secs_vals],
        index=pd.DatetimeIndex(
            [archiver._timestamp(s, 0) for s, _ in secs_vals]
        ),
        name=name,
    )


def test_pair_by_time_takes_last_y_at_or_before_each_x():
    x = _series("AMP", [(10, 1.0), (20, 2.0), (30, 3.0)])
    y = _series("RAD", [(5, 0.1), (20, 0.2), (25, 0.3)])

    paired = archiver.pair_by_time(x, y)

    assert paired.columns.tolist() == ["AMP", "RAD"]
    assert paired["RAD"].tolist() == [0.1, 0.2, 0.3]


def test_pair_by_time_drops_x_before_first_y():
    x = _series("AMP", [(1, 1.0), (10, 2.0)])
    y = _series("RAD", [(5, 0.1)])

    assert archiver.pair_by_time(x, y)["AMP"].tolist() == [2.0]


# ---------------------------------------------------------------------------
# Review fixes
# ---------------------------------------------------------------------------
def test_range_error_names_the_pv(session):
    session.request.side_effect = requests.exceptions.Timeout()

    with pytest.raises(ArchiverTimeoutError, match="^A:PV: "):
        get_values_over_time_range(["A:PV"], START, END)


@pytest.mark.parametrize(
    "naive",
    [
        datetime(2024, 11, 3, 1, 30),  # fall back: 01:30 happens twice
        datetime(2024, 3, 10, 2, 30),  # spring forward: 02:30 never happens
    ],
)
def test_naive_time_during_dst_change_is_refused(session, naive):
    with pytest.raises(ValueError, match="daylight saving"):
        get_values_over_time_range(["A:PV"], naive, END)

    session.request.assert_not_called()


def test_aware_time_during_dst_change_is_accepted(session):
    session.request.return_value = _response(payload=[])
    pdt = archiver.LOCAL_TZ
    first_0130 = datetime(2024, 11, 3, 1, 30, tzinfo=pdt, fold=0)

    get_values_over_time_range(["A:PV"], first_0130, datetime(2024, 11, 4))

    assert (
        session.request.call_args_list[0].kwargs["params"]["from"]
        == "2024-11-03T08:30:00.000000Z"
    )


def test_pair_by_time_sorts_unsorted_input():
    x = _series("AMP", [(30, 3.0), (10, 1.0), (20, 2.0)])
    y = _series("RAD", [(25, 0.3), (5, 0.1)])

    paired = archiver.pair_by_time(x, y)

    assert paired["AMP"].tolist() == [1.0, 2.0, 3.0]
    assert paired["RAD"].tolist() == [0.1, 0.1, 0.3]


def test_timestamp_keeps_exact_microseconds():
    # secs + nanos / 1e9 as one float gives 999999 here.
    stamp = archiver._timestamp(1727049601, 999_998_500)
    assert stamp.microsecond == 999998


def test_timestamp_in_fall_back_hour_keeps_pst():
    # 09:30 UTC on 2024-11-03 is the second 01:30, in PST.
    secs = int(datetime(2024, 11, 3, 9, 30, tzinfo=timezone.utc).timestamp())

    stamp = archiver._timestamp(secs, 500_000)

    assert stamp.utcoffset() == timedelta(hours=-8)
    assert stamp.timestamp() == secs + 0.0005


# ---------------------------------------------------------------------------
# Daemon threads
# ---------------------------------------------------------------------------
# A request that never answers. The fetch runs on a daemon thread, as the
# displays run it; the main thread then returns, so the interpreter should exit.
_STUCK_FETCH = """
import threading
from datetime import datetime
from unittest.mock import MagicMock, patch

from sc_linac_physics.utils import archiver

started = threading.Event()


def stuck(*args, **kwargs):
    started.set()
    threading.Event().wait()


session = MagicMock()
session.request.side_effect = stuck
with patch.object(archiver, "_session", return_value=session):
    threading.Thread(
        target=archiver.get_values_over_time_range,
        args=(["A:PV"], datetime(2023, 10, 2, 9), datetime(2023, 10, 2, 10)),
        daemon=True,
    ).start()
    assert started.wait(10)
"""


def test_stuck_request_does_not_block_exit():
    src = Path(archiver.__file__).parents[2]
    env = {**os.environ, "PYTHONPATH": str(src)}

    # Import time is most of this; the old pool hung here until killed.
    result = subprocess.run(
        [sys.executable, "-c", _STUCK_FETCH],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_errors_raise_in_pv_order_after_every_request(session):
    def respond(method, url, timeout, params):
        if params["pv"] == "GOOD:PV":
            return _response(payload=[])
        raise requests.exceptions.ConnectionError()

    session.request.side_effect = respond

    with pytest.raises(ArchiverConnectionError, match="^BAD:A: "):
        get_values_over_time_range(["BAD:A", "GOOD:PV", "BAD:B"], START, END)

    assert session.request.call_count == 1 + 2 * archiver.MAX_RETRIES


def test_results_keep_pv_order(session):
    pvs = [f"PV:{i}" for i in range(20)]
    session.request.return_value = _response(payload=[])

    frames = get_values_over_time_range(pvs, START, END, max_workers=3)

    assert list(frames) == pvs


def test_no_workers_is_refused(session):
    with pytest.raises(ValueError):
        get_values_over_time_range(["A:PV"], START, END, max_workers=0)


HOUR = timedelta(hours=1)
UTC_START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _counts(*per_hour, start=UTC_START):
    """count_3600 bins, timestamped at each hour's midpoint like the archiver."""
    base = int(start.timestamp())
    return [_datum(base + 3600 * i + 1800, n) for i, n in enumerate(per_hour)]


class TestChunkedRange:
    """Long windows are fetched in planned chunks and stitched back together."""

    LONG_END = START + 3 * HOUR

    @pytest.fixture
    def three_chunks(self):
        bounds = [START + i * HOUR for i in range(4)]
        with patch.object(archiver, "_plan_chunks", return_value=bounds):
            yield

    @staticmethod
    def _sent_pvs(session):
        return [
            c.kwargs["params"]["pv"] for c in session.request.call_args_list
        ]

    def test_short_window_is_one_request_without_counting(self, session):
        session.request.return_value = _response(payload=[{"data": []}])

        get_values_over_time_range(["A:PV"], START, START + HOUR)

        assert self._sent_pvs(session) == ["A:PV"]

    def test_long_window_counts_first(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": _counts(5, 5, 5)}]),
            _response(payload=[{"data": [_datum(100, 1.0)]}]),
        ]

        get_values_over_time_range(["A:PV"], START, self.LONG_END)

        assert self._sent_pvs(session) == ["count_3600(A:PV)", "A:PV"]

    def test_counts_are_asked_for_a_window_at_a_time(self, session):
        session.request.return_value = _response(payload=[{"data": _counts(1)}])
        end = START + 2 * archiver.COUNT_WINDOW + HOUR

        get_values_over_time_range(["A:PV"], START, end)

        counted = [p for p in self._sent_pvs(session) if p.startswith("count")]
        assert len(counted) == 3

    def test_quiet_string_pv_is_one_request_after_its_total(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(payload=[{"data": [_datum(0, 3)]}]),
            _response(payload=[{"data": [_datum(100, "1")]}]),
        ]

        frame = get_values_over_time_range(["A:PV"], START, self.LONG_END)[
            "A:PV"
        ]

        assert self._sent_pvs(session) == [
            "count_3600(A:PV)",
            "ncount(A:PV)",
            "A:PV",
        ]
        assert list(frame["value"]) == ["1"]

    def test_busy_string_pv_is_halved_until_each_part_fits(self, session):
        limit = archiver.CHUNK_SAMPLES
        totals = {  # (from, to) -> ncount: the first half is still too big
            (START, self.LONG_END): 3 * limit,
            (START, START + 1.5 * HOUR): 2 * limit,
            (START + 1.5 * HOUR, self.LONG_END): limit,
            (START, START + 0.75 * HOUR): limit,
            (START + 0.75 * HOUR, START + 1.5 * HOUR): limit,
        }
        by_window = {
            (archiver._to_utc_iso(a), archiver._to_utc_iso(b)): n
            for (a, b), n in totals.items()
        }

        def reply(method, url, timeout, params):
            pv, window = params["pv"], (params["from"], params["to"])
            if pv.startswith("ncount"):
                return _response(
                    payload=[{"data": [_datum(0, by_window[window])]}]
                )
            return _response(payload=[{"data": []}])

        session.request.side_effect = reply

        get_values_over_time_range(["A:PV"], START, self.LONG_END)

        data = [
            c.kwargs["params"]["from"]
            for c in session.request.call_args_list
            if c.kwargs["params"]["pv"] == "A:PV"
        ]
        assert data == [
            archiver._to_utc_iso(t)
            for t in (START, START + 0.75 * HOUR, START + 1.5 * HOUR)
        ]

    def test_counts_found_only_in_a_later_window_still_plan_chunks(
        self, session
    ):
        later = START + archiver.COUNT_WINDOW
        busy = [archiver.CHUNK_SAMPLES] * 2
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(payload=[{"data": [_datum(0, 0)]}]),  # its ncount
            _response(payload=[{"data": _counts(*busy, start=later)}]),
        ] + [_response(payload=[{"data": []}])] * 4
        end = later + 2 * HOUR

        get_values_over_time_range(["A:PV"], START, end)

        data = [p for p in self._sent_pvs(session) if p == "A:PV"]
        assert len(data) > 1

    def test_404_while_halving_is_not_archived(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(
                payload=[{"data": [_datum(0, 2 * archiver.CHUNK_SAMPLES)]}]
            ),
            _response(status=404),
        ]

        with pytest.raises(PVNotArchivedError):
            get_values_over_time_range(["A:PV"], START, self.LONG_END)

    def test_404_on_the_second_half_is_not_archived(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(
                payload=[{"data": [_datum(0, 2 * archiver.CHUNK_SAMPLES)]}]
            ),
            _response(payload=[{"data": [_datum(0, 1)]}]),
            _response(status=404),
        ]

        with pytest.raises(PVNotArchivedError):
            get_values_over_time_range(["A:PV"], START, self.LONG_END)

    def test_pv_unknown_when_counting_is_not_archived(self, session):
        session.request.return_value = _response(status=404)

        with pytest.raises(PVNotArchivedError):
            get_values_over_time_range(["A:PV"], START, self.LONG_END)

        assert session.request.call_count == 1

    def test_samples_repeated_across_a_boundary_are_kept_once(
        self, session, three_chunks
    ):
        # Each window can repeat the sample before its start; the one on the
        # boundary (secs=200) comes back in both windows around it.
        chunks = [
            [_datum(50, 0.0), _datum(100, 1.0), _datum(200, 2.0)],
            [_datum(200, 2.0), _datum(300, 3.0)],
            [_datum(300, 3.0), _datum(400, 4.0, nanos=5)],
        ]
        session.request.side_effect = [
            _response(payload=[{"data": c}]) for c in chunks
        ]

        frame = get_values_over_time_range(["A:PV"], START, self.LONG_END)[
            "A:PV"
        ]

        assert list(frame["value"]) == [0.0, 1.0, 2.0, 3.0, 4.0]

    def test_empty_first_chunk_keeps_timestamp_dtype(
        self, session, three_chunks
    ):
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(payload=[{"data": [_datum(100, 1.0)]}]),
            _response(payload=[{"data": [_datum(200, 2.0)]}]),
        ]

        frame = get_values_over_time_range(["A:PV"], START, self.LONG_END)[
            "A:PV"
        ]

        assert str(frame["timestamp"].dtype).startswith("datetime64")
        assert list(frame["value"]) == [1.0, 2.0]

    def test_404_on_a_later_chunk_names_the_pv(self, session, three_chunks):
        session.request.side_effect = [
            _response(payload=[{"data": [_datum(100, 1.0)]}]),
            _response(status=404),
        ]

        with pytest.raises(PVNotArchivedError) as excinfo:
            get_values_over_time_range(["A:PV"], START, self.LONG_END)

        assert "A:PV" in str(excinfo.value)


class TestIterRangeChunks:
    @pytest.fixture(autouse=True)
    def three_chunks(self):
        bounds = [START + i * HOUR for i in range(4)]
        with patch.object(archiver, "_plan_chunks", return_value=bounds):
            yield

    def test_yields_one_frame_per_nonempty_chunk_lazily(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": [_datum(100, 1.0)]}]),
            _response(payload=[{"data": []}]),
            _response(payload=[{"data": [_datum(300, 3.0)]}]),
        ]

        chunks = archiver.iter_range_chunks("A:PV", START, START + 3 * HOUR)
        first = next(chunks)

        assert session.request.call_count == 1
        assert list(first["value"]) == [1.0]
        assert [list(c["value"]) for c in chunks] == [[3.0]]

    def test_not_archived_raises_naming_the_pv(self, session):
        session.request.return_value = _response(status=404)

        with pytest.raises(PVNotArchivedError) as excinfo:
            list(archiver.iter_range_chunks("A:PV", START, START + 3 * HOUR))

        assert excinfo.value.pvs == ["A:PV"]

    def test_other_errors_name_the_pv(self, session):
        session.request.return_value = _response(status=400)

        with pytest.raises(ArchiverError, match="A:PV"):
            list(archiver.iter_range_chunks("A:PV", START, START + 3 * HOUR))


class TestLogging:
    @pytest.fixture
    def log(self):
        with patch.object(archiver, "get_logger") as get_logger:
            yield get_logger.return_value

    def test_one_info_line_per_pv_with_its_sample_count(self, session, log):
        session.request.return_value = _response(
            payload=[{"data": [_datum(1696263180, 1.5)]}]
        )

        get_values_over_time_range(["A:PV"], START, END)

        line = log.info.call_args.args[0] % log.info.call_args.args[1:]
        assert line.startswith("A:PV 2023-10-02 09:13..2023-10-02 10:00")
        assert "1 samples in 1 chunk(s)" in line

    def test_each_request_is_a_debug_line(self, session, log):
        session.request.return_value = _response(
            payload=[{"data": []}], nbytes=2_000_000
        )

        get_values_over_time_range(["A:PV"], START, END)

        line = log.debug.call_args.args[0] % log.debug.call_args.args[1:]
        assert line.startswith("GET A:PV") and "2.0 MB" in line

    def test_retries_are_warnings(self, session, log):
        session.request.side_effect = [
            requests.exceptions.Timeout("slow"),
            _response(payload=[{"data": []}]),
        ]

        get_values_over_time_range(["A:PV"], START, END)

        assert "attempt 1 of 4" in (
            log.warning.call_args.args[0] % log.warning.call_args.args[1:]
        )

    def test_value_at_time_is_one_info_line(self, session, log):
        session.request.return_value = _response(
            payload={"A:PV": {"secs": 1, "val": 1.0, "nanos": 0}}
        )

        get_values_at_time(["A:PV", "B:PV"], START)

        line = log.info.call_args.args[0] % log.info.call_args.args[1:]
        assert "1 of 2 PVs" in line


class TestGroupBins:
    LIMIT = archiver.CHUNK_SAMPLES

    @staticmethod
    def _plan(hours, *per_hour, start=UTC_START):
        counts = {
            archiver._bin_start(d["secs"]): d["val"]
            for d in _counts(*per_hour, start=start)
        }
        return archiver._group_bins(start, start + hours * HOUR, counts)

    def test_quiet_window_is_one_chunk(self):
        assert self._plan(24 * 365, 3, 0, 1) == [
            UTC_START,
            UTC_START + 24 * 365 * HOUR,
        ]

    def test_chunks_cut_at_hour_edges_under_the_limit(self):
        half = self.LIMIT // 2
        bounds = self._plan(4, half, half, half, half)

        assert bounds == [UTC_START, UTC_START + 2 * HOUR, UTC_START + 4 * HOUR]

    def test_hour_over_the_limit_is_split_evenly(self):
        bounds = self._plan(1, 3 * self.LIMIT)

        assert bounds == [UTC_START + i * HOUR / 3 for i in range(4)]

    def test_window_starting_mid_hour_starts_at_start(self):
        start = UTC_START + HOUR / 2
        counts = {archiver._bin_start(start.timestamp()): 2 * self.LIMIT}

        bounds = archiver._group_bins(start, start + HOUR / 2, counts)

        assert bounds[0] == start
        assert bounds[-1] == start + HOUR / 2

    def test_bounds_across_fall_back_are_an_hour_apart(self, session):
        # A Pacific datetime plus a timedelta is wall-clock time; chunking in
        # UTC keeps every planned hour exactly an hour long.
        first_0130 = datetime(2024, 11, 3, 1, 30, tzinfo=archiver.LOCAL_TZ)
        start = first_0130.astimezone(timezone.utc)
        counts = {
            archiver._bin_start(start.timestamp()) + 3600 * i: self.LIMIT
            for i in range(4)
        }

        bounds = archiver._group_bins(start, start + 3 * HOUR, counts)

        assert all(b - a <= HOUR for a, b in zip(bounds, bounds[1:]))
        assert bounds[-1] - bounds[0] == 3 * HOUR
