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


def test_chunks_across_fall_back_skip_no_hour(session):
    session.request.return_value = _response(payload=[])
    first_0130 = datetime(2024, 11, 3, 1, 30, tzinfo=archiver.LOCAL_TZ)

    get_values_over_time_range(["A:PV"], first_0130, datetime(2024, 11, 4))

    first, second = session.request.call_args_list[:2]
    assert first.kwargs["params"]["to"] == "2024-11-03T09:30:00.000000Z"
    assert second.kwargs["params"]["from"] == "2024-11-03T09:30:00.000000Z"


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


class TestChunkedRange:
    """Long windows are fetched in chunks and stitched back together."""

    LONG_END = START + 3 * archiver.FIRST_CHUNK

    @pytest.fixture(autouse=True)
    def fixed_span(self):
        with patch.object(
            archiver, "_next_span", side_effect=lambda span, samples: span
        ):
            yield

    @staticmethod
    def _windows(session):
        return [
            (c.kwargs["params"]["from"], c.kwargs["params"]["to"])
            for c in session.request.call_args_list
        ]

    def test_short_window_is_one_request(self, session):
        session.request.return_value = _response(payload=[{"data": []}])

        get_values_over_time_range(["A:PV"], START, END)

        assert session.request.call_count == 1

    def test_chunks_cover_the_window_end_to_end(self, session):
        session.request.return_value = _response(payload=[{"data": []}])

        get_values_over_time_range(["A:PV"], START, self.LONG_END)

        windows = self._windows(session)
        assert len(windows) == 3
        assert windows[0][0] == archiver._to_utc_iso(START)
        assert windows[-1][1] == archiver._to_utc_iso(self.LONG_END)
        for (_, to), (frm, _) in zip(windows, windows[1:]):
            assert to == frm

    def test_samples_repeated_across_a_boundary_are_kept_once(self, session):
        # Each window repeats the sample before its start; the one on the
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

    def test_empty_first_chunk_keeps_timestamp_dtype(self, session):
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

    def test_404_on_a_later_chunk_names_the_pv(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": [_datum(100, 1.0)]}]),
            _response(status=404),
        ]

        with pytest.raises(PVNotArchivedError) as excinfo:
            get_values_over_time_range(["A:PV"], START, self.LONG_END)

        assert "A:PV" in str(excinfo.value)


class TestNextSpan:
    HOUR = timedelta(hours=1)

    def test_scales_toward_chunk_bytes(self):
        nbytes = archiver.CHUNK_BYTES * 4  # 4x too big: quarter the span
        assert archiver._next_span(self.HOUR, nbytes) == self.HOUR / 4

    def test_quiet_pv_grows_to_max_chunk(self):
        assert archiver._next_span(self.HOUR, 100) == archiver.MAX_CHUNK
        assert archiver._next_span(self.HOUR, 0) == archiver.MAX_CHUNK

    def test_very_fast_pv_stops_at_min_chunk(self):
        nbytes = archiver.CHUNK_BYTES * 10_000
        assert archiver._next_span(self.HOUR, nbytes) == archiver.MIN_CHUNK

    def test_long_window_uses_bytes_from_each_response(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": []}], nbytes=archiver.CHUNK_BYTES * 4),
            _response(payload=[{"data": []}]),
        ]
        end = START + archiver.FIRST_CHUNK + archiver.FIRST_CHUNK / 4

        get_values_over_time_range(["A:PV"], START, end)

        assert session.request.call_count == 2
