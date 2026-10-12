from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from sc_linac_physics.utils import archiver, archiver_store
from sc_linac_physics.utils.archiver import PVNotArchivedError
from sc_linac_physics.utils.archiver_store import ArchiverStore

UTC = timezone.utc
JAN = datetime(2024, 1, 1, tzinfo=UTC)
FEB = datetime(2024, 2, 1, tzinfo=UTC)
MAR = datetime(2024, 3, 1, tzinfo=UTC)


def _secs(moment: datetime) -> int:
    return int(moment.timestamp())


class FakeArchiver:
    """Serves iter_range_chunks from a list of (time, value) per PV.

    Like the archiver, each window starts with the last sample before it.
    """

    def __init__(self, samples, fail_after=None):
        self.samples = samples
        self.calls = []
        self.fail_after = fail_after

    def __call__(self, pv, start, end, timeout=None):
        self.calls.append((pv, start, end))
        if pv not in self.samples:
            raise PVNotArchivedError([pv])
        rows = sorted(self.samples[pv])
        earlier = [r for r in rows if r[0] < start][-1:]
        inside = [r for r in rows if start <= r[0] <= end]
        for i, (moment, value) in enumerate(earlier + inside):
            if self.fail_after is not None and i >= self.fail_after:
                raise archiver.ArchiverTimeoutError("no answer")
            yield archiver._to_frame([{"secs": _secs(moment), "val": value}])


@pytest.fixture
def store(tmp_path):
    return ArchiverStore(tmp_path)


def _values(frame):
    return list(frame["value"])


def _serve(samples, **kwargs):
    fake = FakeArchiver(samples, **kwargs)
    return fake, patch.object(archiver, "iter_range_chunks", side_effect=fake)


def test_read_across_months_keeps_each_sample_once(store):
    fake, served = _serve(
        {
            "A:PV": [
                (JAN + timedelta(days=3), 1.0),
                (JAN + timedelta(days=20), 2.0),
                (FEB + timedelta(days=2), 3.0),
            ]
        }
    )
    with served:
        frame = store.read("A:PV", JAN + timedelta(days=1), MAR)

    assert _values(frame) == [1.0, 2.0, 3.0]
    assert list(frame.columns) == archiver.COLUMNS


def test_read_starts_with_the_sample_before_start(store):
    fake, served = _serve(
        {
            "A:PV": [
                (JAN + timedelta(days=2), 1.0),
                (JAN + timedelta(days=9), 2.0),
                (JAN + timedelta(days=20), 3.0),
            ]
        }
    )
    with served:
        frame = store.read(
            "A:PV", JAN + timedelta(days=5), JAN + timedelta(days=10)
        )

    assert _values(frame) == [1.0, 2.0]


def test_settled_month_is_fetched_once(store):
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=3), 1.0)]})
    with served:
        store.read("A:PV", JAN, FEB)
        frame = store.read("A:PV", JAN, FEB)

    assert len(fake.calls) == 1
    assert _values(frame) == [1.0]
    assert store.path("A:PV", JAN).exists()


def test_recent_month_is_fetched_fresh_and_not_written(store):
    now = datetime.now(UTC)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fake, served = _serve({"A:PV": [(month, 1.0)]})
    with served:
        store.read("A:PV", month, now)
        store.read("A:PV", month, now)

    assert len(fake.calls) == 2
    assert not store.path("A:PV", month).exists()


def test_recent_month_is_fetched_only_where_asked(store):
    now = datetime.now(UTC)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fake, served = _serve({"A:PV": []})
    start = max(month, now - timedelta(hours=2))
    with served:
        store.read("A:PV", start, now)

    assert [(c[1], c[2]) for c in fake.calls] == [(start, now)]


def test_unwritable_cache_still_returns_data(tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("")  # a file where the cache directory should go
    store = ArchiverStore(blocker)
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=1), 1.0)]})
    with served, patch.object(archiver, "get_logger") as get_logger:
        frame = store.read("A:PV", JAN, FEB)

    assert _values(frame) == [1.0]
    warning = get_logger.return_value.warning.call_args
    assert "cannot write" in warning.args[0]


def test_writing_a_month_is_logged(store):
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=1), 1.0)]})
    with served, patch.object(archiver, "get_logger") as get_logger:
        store.read("A:PV", JAN, FEB)
        store.read("A:PV", JAN, FEB)

    log = get_logger.return_value
    lines = [c.args[0] % c.args[1:] for c in log.info.call_args_list]
    assert lines[0].startswith("cache: wrote A:PV 2024-01")
    assert "0 of 1 month(s) from disk" in lines[1]
    assert "1 samples, 1 of 1 month(s) from disk" in lines[2]


def test_empty_settled_month_is_recorded(store):
    fake, served = _serve({"A:PV": []})
    with served:
        first = store.read("A:PV", JAN, FEB)
        store.read("A:PV", JAN, FEB)

    assert first.empty
    assert len(fake.calls) == 1


def test_failed_fetch_leaves_no_file(store):
    samples = {"A:PV": [(JAN + timedelta(days=d), float(d)) for d in (1, 2, 3)]}
    fake, served = _serve(samples, fail_after=1)
    with served, pytest.raises(archiver.ArchiverTimeoutError):
        store.read("A:PV", JAN, FEB)

    assert list(store.root.rglob("*")) == [store.path("A:PV", JAN).parent]


def test_unknown_pv_raises_and_writes_nothing(store):
    fake, served = _serve({})
    with served, pytest.raises(PVNotArchivedError):
        store.read("A:PV", JAN, FEB)

    assert not store.path("A:PV", JAN).exists()


def test_string_values_round_trip(store):
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=1), "FLT")]})
    with served:
        store.read("A:PV", JAN, FEB)
        frame = store.read("A:PV", JAN, FEB)

    assert _values(frame) == ["FLT"]


def test_iter_months_yields_a_frame_per_month_with_samples(store):
    fake, served = _serve(
        {
            "A:PV": [
                (JAN + timedelta(days=3), 1.0),
                (FEB + timedelta(days=3), 2.0),
            ]
        }
    )
    with served:
        frames = list(store.iter_months("A:PV", JAN + timedelta(days=1), MAR))

    assert [_values(f) for f in frames] == [[1.0], [2.0]]


def test_naive_times_are_pacific(store):
    fake, served = _serve({"A:PV": []})
    with served:
        store.read("A:PV", datetime(2024, 1, 31, 20), datetime(2024, 2, 1))

    # 20:00 PST on Jan 31 is 04:00 UTC on Feb 1: only February is asked for.
    assert [c[1] for c in fake.calls] == [FEB]


def test_fill_writes_settled_months_and_names_unknown_pvs(store):
    now = datetime.now(UTC)
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=1), 1.0)]})
    with served, pytest.raises(PVNotArchivedError) as excinfo:
        store.fill(["A:PV", "B:PV"], JAN, now)

    assert excinfo.value.pvs == ["B:PV"]
    assert store.path("A:PV", JAN).exists()
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    assert not store.path("A:PV", this_month).exists()


def test_progress_names_each_month_and_where_it_comes_from(store):
    fake, served = _serve({"A:PV": [(JAN + timedelta(days=1), 1.0)]})
    messages = []
    with served:
        store.read("A:PV", JAN, FEB)
        store.read("A:PV", JAN, MAR, progress=messages.append)

    assert messages == [
        "Jan 2024 (1 of 2): from disk",
        "Feb 2024 (2 of 2): fetching from the archiver",
    ]


def test_pv_names_are_safe_directory_names(store):
    path = store.path("A:B/C D", JAN)

    assert path.parent.name == "A:B%2FC%20D"
    assert path.name == "2024-01.parquet"


def test_default_root_is_under_the_srf_base_dir():
    with patch.object(
        archiver_store,
        "get_srf_base_dir",
        return_value=archiver_store.Path("/x"),
    ):
        assert ArchiverStore().root == archiver_store.Path("/x/archiver_cache")


def test_months_cover_the_window():
    months = archiver_store._months(JAN + timedelta(days=30), MAR)

    assert months == [(JAN, FEB), (FEB, MAR)]


def test_cached_month_reads_back_identical_frame(store):
    fake, served = _serve(
        {"A:PV": [(JAN + timedelta(hours=h), h * 0.5) for h in range(48)]}
    )
    with served:
        fetched = store.read("A:PV", JAN, FEB)
        cached = store.read("A:PV", JAN, FEB)

    pd.testing.assert_frame_equal(fetched, cached)
