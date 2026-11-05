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


class TestErrorContract:
    """Every failure is an ArchiverError, as the module promises."""

    def _not_json(self):
        response = _response()
        response.json.side_effect = requests.exceptions.JSONDecodeError(
            "Expecting value", "<html>login</html>", 0
        )
        return response

    def test_range_non_json_body_raises_archiver_error_naming_pv(self, session):
        session.request.return_value = self._not_json()
        with pytest.raises(ArchiverError, match="TEST:PV1.*not JSON"):
            archiver.get_values_over_time_range(
                ["TEST:PV1"], datetime(2025, 6, 2, 12), datetime(2025, 6, 2, 13)
            )

    def test_range_unexpected_shape_raises_archiver_error(self, session):
        session.request.return_value = _response(payload=[{"meta": {}}])
        with pytest.raises(ArchiverError, match="TEST:PV1.*unexpected"):
            archiver.get_values_over_time_range(
                ["TEST:PV1"], datetime(2025, 6, 2, 12), datetime(2025, 6, 2, 13)
            )

    def test_long_window_bad_counts_raise_archiver_error(self, session):
        # count_3600 bins without "secs"/"val": planning, not fetching, fails.
        session.request.return_value = _response(payload=[{"data": [{}]}])
        with pytest.raises(ArchiverError, match="TEST:PV1.*unexpected"):
            archiver.get_values_over_time_range(
                ["TEST:PV1"], datetime(2025, 6, 2, 12), datetime(2025, 6, 2, 16)
            )

    def test_long_window_non_json_counts_raise_archiver_error(self, session):
        session.request.return_value = self._not_json()
        with pytest.raises(ArchiverError, match="TEST:PV1.*not JSON"):
            archiver.get_values_over_time_range(
                ["TEST:PV1"], datetime(2025, 6, 2, 12), datetime(2025, 6, 2, 16)
            )

    def test_at_time_non_json_body_raises_archiver_error(self, session):
        session.request.return_value = self._not_json()
        with pytest.raises(ArchiverError, match="not JSON"):
            archiver.get_values_at_time(["TEST:PV1"], datetime(2025, 6, 2, 12))

    def test_at_time_with_no_pvs_sends_nothing(self, session):
        assert archiver.get_values_at_time([], datetime(2025, 6, 2, 12)) == {}
        session.request.assert_not_called()

    def test_500_is_not_retried(self, session):
        session.request.return_value = _response(500)
        with pytest.raises(ArchiverError, match="HTTP 500"):
            archiver.get_values_at_time(["TEST:PV1"], datetime(2025, 6, 2, 12))
        assert session.request.call_count == 1

    @pytest.mark.parametrize("status", [502, 503, 504])
    def test_gateway_errors_are_retried(self, session, status):
        session.request.side_effect = [_response(status), _response(payload={})]
        archiver.get_values_at_time(["TEST:PV1"], datetime(2025, 6, 2, 12))
        assert session.request.call_count == 2


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


class TestBinnedValues:
    STEP = 3600
    # A UTC hour boundary, so bins line up with whole hours here.
    T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _bins(step, *pairs, start):
        """Archiver-style bins: timestamped at each bin's middle."""
        base = int(start.timestamp())
        return [
            _datum(base + i * step + step // 2, v) for i, v in enumerate(pairs)
        ]

    def _reply(self, values, counts):
        def reply(method, url, timeout, params):
            pv = params["pv"]
            if pv.startswith("count_") and "planning" not in reply.__dict__:
                reply.planning = True  # the planner's count comes first
                return _response(payload=[{"data": []}])
            if pv.startswith("ncount"):
                return _response(payload=[{"data": [_datum(0, 1)]}])
            data = counts if pv.startswith("count_") else values
            return _response(payload=[{"data": data}])

        return reply

    def test_bins_without_samples_and_before_the_window_are_dropped(
        self, session
    ):
        start = self.T0 + timedelta(hours=1)
        end = start + timedelta(hours=3)
        before = start - timedelta(hours=1)
        # Hour before the window, then three hours; the last one is empty and
        # the archiver repeats the previous bin's value in it.
        values = self._bins(self.STEP, 9.0, 1.0, 2.0, 2.0, start=before)
        counts = self._bins(self.STEP, 1, 10, 20, 0, start=before)
        session.request.side_effect = self._reply(values, counts)

        frame = archiver.get_binned_values(
            ["A:PV"], start, end, timedelta(hours=1)
        )["A:PV"]

        assert list(frame["value"]) == [1.0, 2.0]
        assert list(frame["count"]) == [10, 20]
        assert list(frame["timestamp"]) == [
            start.astimezone(archiver.LOCAL_TZ),
            (start + timedelta(hours=1)).astimezone(archiver.LOCAL_TZ),
        ]

    def test_statistic_and_bin_size_are_in_the_operator(self, session):
        session.request.return_value = _response(payload=[{"data": []}])

        archiver.get_binned_values(
            ["A:PV"],
            self.T0,
            self.T0 + timedelta(minutes=30),
            timedelta(minutes=10),
            "max",
        )

        sent = [
            c.kwargs["params"]["pv"] for c in session.request.call_args_list
        ]
        assert sent == ["max_600(A:PV)", "count_600(A:PV)"]

    def test_chunk_edges_are_moved_to_bin_edges(self, session):
        step = timedelta(hours=1)
        bounds = [
            self.T0,
            self.T0 + timedelta(minutes=90),  # mid-bin: moved to 1:00
            self.T0 + timedelta(hours=3),
        ]
        session.request.return_value = _response(payload=[{"data": []}])
        with patch.object(archiver, "_plan_chunks", return_value=bounds):
            archiver.get_binned_values(["A:PV"], self.T0, bounds[-1], step)

        starts = sorted(
            {c.kwargs["params"]["from"] for c in session.request.call_args_list}
        )
        assert starts == [
            archiver._to_utc_iso(self.T0),
            archiver._to_utc_iso(self.T0 + step),
        ]

    def _value_windows(self, session, prefix):
        """(from, to) of each value request sent, in order."""
        return [
            (c.kwargs["params"]["from"], c.kwargs["params"]["to"])
            for c in session.request.call_args_list
            if c.kwargs["params"]["pv"].startswith(prefix)
        ]

    def test_requests_are_capped_by_bins_too(self, session, monkeypatch):
        monkeypatch.setattr(archiver, "BINNED_CHUNK_BINS", 3)
        session.request.side_effect = self._reply([], [])

        archiver.get_binned_values(
            ["A:PV"], self.T0, self.T0 + timedelta(hours=7), timedelta(hours=1)
        )

        windows = self._value_windows(session, "mean_")
        assert len(windows) == 3  # 3 + 3 + 1 bins
        assert windows[0][1] == "2024-01-01T03:00:00.000000Z"

    def test_bin_holding_two_planned_chunks_is_refused(self):
        t0 = self.T0
        planned = [t0, t0 + timedelta(minutes=10), t0 + timedelta(minutes=20)]
        planned.append(t0 + timedelta(hours=1))

        with pytest.raises(ValueError, match="A:PV.*smaller bin_size"):
            archiver._binned_bounds(
                "A:PV", planned, t0, t0 + timedelta(hours=1), self.STEP
            )

    def test_count_statistic_sends_one_request_per_chunk(self, session):
        values = self._bins(self.STEP, 4, 5, start=self.T0)
        session.request.side_effect = self._reply(values, values)

        frame = archiver.get_binned_values(
            ["A:PV"],
            self.T0,
            self.T0 + timedelta(hours=2),
            timedelta(hours=1),
            "count",
        )["A:PV"]

        # the planner's count_3600, then one count_3600 for the one chunk
        sent = [
            c.kwargs["params"]["pv"] for c in session.request.call_args_list
        ]
        assert sent.count("count_3600(A:PV)") == 2
        assert list(frame["value"]) == [4, 5]

    def test_bin_on_a_chunk_edge_is_counted_once(self, session, monkeypatch):
        monkeypatch.setattr(archiver, "BINNED_CHUNK_BINS", 1)
        # Both requests send back both bins, as when a sample sits exactly on
        # the edge between them
        values = self._bins(self.STEP, 1.0, 2.0, start=self.T0)
        counts = self._bins(self.STEP, 10, 20, start=self.T0)
        session.request.side_effect = self._reply(values, counts)

        frame = archiver.get_binned_values(
            ["A:PV"], self.T0, self.T0 + timedelta(hours=2), timedelta(hours=1)
        )["A:PV"]

        assert len(self._value_windows(session, "mean_")) == 2
        assert list(frame["value"]) == [1.0, 2.0]
        assert frame["timestamp"].is_unique

    def test_long_window_is_planned_with_the_binned_limit(self, session):
        session.request.return_value = _response(payload=[{"data": []}])
        with patch.object(
            archiver, "_plan_chunks", return_value=[self.T0, self.T0]
        ) as plan:
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(days=2),
                timedelta(hours=1),
            )

        assert plan.call_args.args[-1] == archiver.BINNED_CHUNK_SAMPLES

    @pytest.mark.parametrize(
        "statistic, bin_size",
        [
            ("median", timedelta(hours=1)),
            ("mean", timedelta(0)),
            ("mean", timedelta(seconds=1.5)),
        ],
    )
    def test_bad_arguments_are_refused(self, session, statistic, bin_size):
        with pytest.raises(ValueError):
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(hours=1),
                bin_size,
                statistic,
            )

    def test_unknown_pv_is_named(self, session):
        session.request.return_value = _response(status=404)

        with pytest.raises(PVNotArchivedError) as excinfo:
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(hours=1),
                timedelta(minutes=10),
            )

        assert excinfo.value.pvs == ["A:PV"]

    def test_unknown_pv_found_while_planning_is_named(self, session):
        session.request.return_value = _response(status=404)

        with pytest.raises(PVNotArchivedError):
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(days=2),
                timedelta(hours=1),
            )

        assert session.request.call_count == 1

    def test_404_on_the_count_names_the_pv(self, session):
        session.request.side_effect = [
            _response(payload=[{"data": []}]),
            _response(status=404),
        ]

        with pytest.raises(PVNotArchivedError):
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(minutes=30),
                timedelta(minutes=10),
            )

    def test_other_errors_name_the_pv(self, session):
        session.request.return_value = _response(status=400)

        with pytest.raises(ArchiverError, match="A:PV"):
            archiver.get_binned_values(
                ["A:PV"],
                self.T0,
                self.T0 + timedelta(minutes=30),
                timedelta(minutes=10),
            )
