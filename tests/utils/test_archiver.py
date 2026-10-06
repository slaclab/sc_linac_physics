from datetime import datetime, timezone
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


def _response(status=200, payload=None):
    response = MagicMock()
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
