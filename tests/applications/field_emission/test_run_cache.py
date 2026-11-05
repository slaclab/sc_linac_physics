from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from sc_linac_physics.applications.field_emission import run_cache
from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    fetch_run,
    run_pvs,
)
from sc_linac_physics.applications.field_emission.constants import (
    RUN_LIST_PATH,
)
from sc_linac_physics.applications.field_emission.run_cache import (
    Run,
    add_runs,
    find_run,
    is_cached,
    load_run,
    read_run_list,
)
from sc_linac_physics.utils import archiver
from sc_linac_physics.utils.archiver_store import ArchiverStore

HEADER = (
    "Cryomodule,Start Date,Start Time,End Date,End Time,Decarad #,"
    "Link to Measurement,Notes,Recharacterization,Multipacting,Commissioning\n"
)


def _write_list(tmp_path, rows):
    path = tmp_path / "runs.csv"
    path.write_text(HEADER + "".join(row + "\n" for row in rows))
    return path


RUN = Run(
    cm="03",
    start=datetime(2023, 10, 2, 9, 13),
    end=datetime(2023, 10, 2, 10, 0),
    decarad="1",
    elog="http://elog.example",
    notes="",
    start_text="9:13",
    end_text="10:00",
)


class TestReadRunList:
    def test_parses_a_row(self, tmp_path):
        path = _write_list(
            tmp_path, ["CM03,10/2/23,9:13,,10:00,1,http://elog.example,,Y,N,N"]
        )
        assert read_run_list(path, tmp_path / "none.csv") == [RUN]

    def test_end_date_used_when_given(self, tmp_path):
        path = _write_list(
            tmp_path, ["CM03,10/2/23,23:00,10/3/23,1:00,1,,overnight,Y,N,N"]
        )
        run = read_run_list(path, tmp_path / "none.csv")[0]
        assert run.end == datetime(2023, 10, 3, 1, 0)
        assert run.notes == "overnight"

    def test_letter_cryomodule(self, tmp_path):
        path = _write_list(tmp_path, ["CMH1,10/2/23,9:13,,10:00,2,,,Y,N,N"])
        assert read_run_list(path, tmp_path / "none.csv")[0].cm == "H1"

    def test_skips_commented_and_malformed_rows(self, tmp_path):
        path = _write_list(
            tmp_path,
            [
                "#CM03,10/2/23,9:13,,10:00,1,,,Y,N,N",
                "CM03,not a date,9:13,,10:00,1,,,Y,N,N",
                "CM04,10/2/23,9:13,,10:00,1,,,Y,N,N",
            ],
        )
        assert [
            run.cm for run in read_run_list(path, tmp_path / "none.csv")
        ] == ["04"]

    def test_sorted_oldest_first(self, tmp_path):
        path = _write_list(
            tmp_path,
            [
                "CM05,1/5/24,9:00,,10:00,1,,,Y,N,N",
                "CM04,1/4/24,9:00,,10:00,1,,,Y,N,N",
            ],
        )
        assert [
            run.cm for run in read_run_list(path, tmp_path / "none.csv")
        ] == ["04", "05"]

    def test_committed_run_list_parses(self, tmp_path):
        runs = read_run_list(RUN_LIST_PATH, tmp_path / "none.csv")
        assert len(runs) == 80
        assert len({(run.cm, run.start) for run in runs}) == 80


def test_find_run():
    assert find_run("03", RUN.start, [RUN]) is RUN
    assert find_run("04", RUN.start, [RUN]) is None


def _samples(pv, start, end, timeout=None):
    """A fake archiver: two valid samples per PV inside the window."""
    value = float(sum(map(ord, pv)) % 97)
    yield archiver._to_frame(
        [
            {"secs": int(start.timestamp()) + 60, "val": value},
            {"secs": int(start.timestamp()) + 120, "val": value + 1},
        ]
    )


@pytest.fixture
def served():
    with patch.object(
        archiver, "iter_range_chunks", side_effect=_samples
    ) as fetch:
        yield fetch


def test_run_pvs_are_every_amplitude_and_decarad_head_once():
    pvs = run_pvs(RUN.cm, RUN.decarad)
    assert len(pvs) == len(set(pvs)) == 8 + 10 * 2


class TestLoadRun:
    def test_first_load_fetches_each_pv_then_reads_disk(self, tmp_path, served):
        store = ArchiverStore(tmp_path)
        assert not is_cached(RUN, store)

        first = load_run(RUN, store)
        fetched = served.call_count
        second = load_run(RUN, store)

        assert fetched == 28 and served.call_count == 28
        assert is_cached(RUN, store)
        assert first.keys() == second.keys()
        for key in first:
            np.testing.assert_array_equal(first[key][0], second[key][0])

    def test_data_is_fetch_runs_alignment_of_the_cached_samples(
        self, tmp_path, served
    ):
        data = load_run(RUN, ArchiverStore(tmp_path))

        def series(pvs, start, end):
            return archiver.series_from_frames(
                {pv: next(_samples(pv, start, end)) for pv in pvs}
            )

        expected = fetch_run(RUN.cm, RUN.start, RUN.end, RUN.decarad, series)
        assert data.keys() == expected.keys()
        for key, frame in expected.items():
            values, columns = data[key]
            np.testing.assert_array_equal(values, frame.to_numpy("float64"))
            assert columns == [str(c) for c in frame.columns]

    def test_failed_fetch_caches_nothing(self, tmp_path):
        store = ArchiverStore(tmp_path)
        with patch.object(
            archiver,
            "iter_range_chunks",
            side_effect=archiver.ArchiverTimeoutError("down"),
        ):
            with pytest.raises(archiver.ArchiverTimeoutError):
                load_run(RUN, store)
        assert not is_cached(RUN, store)
        assert not list(tmp_path.rglob("*.parquet"))


class TestAddedRuns:
    ROW = ["CM04", "1/4/24", "9:00", "", "10:00", "1", "", "", "Y", "N", "N"]

    def test_read_merges_committed_and_added(self, tmp_path):
        committed = _write_list(tmp_path, ["CM05,1/5/24,9:00,,10:00,1,,,Y,N,N"])
        added = tmp_path / "added.csv"
        add_runs([self.ROW], committed, added)
        assert [r.cm for r in read_run_list(committed, added)] == ["04", "05"]

    def test_missing_added_list_is_fine(self, tmp_path):
        committed = _write_list(tmp_path, ["CM05,1/5/24,9:00,,10:00,1,,,Y,N,N"])
        assert len(read_run_list(committed, tmp_path / "nope.csv")) == 1

    def test_add_writes_header_once(self, tmp_path):
        committed = _write_list(tmp_path, [])
        added = tmp_path / "sub" / "added.csv"
        add_runs([self.ROW], committed, added)
        second = ["CM06", *self.ROW[1:]]
        assert [r.cm for r in add_runs([second], committed, added)] == ["06"]
        lines = added.read_text().splitlines()
        assert lines[0].startswith("Cryomodule,")
        assert len(lines) == 3

    def test_add_skips_runs_already_listed(self, tmp_path):
        committed = _write_list(tmp_path, ["CM04,1/4/24,9:00,,10:00,1,,,Y,N,N"])
        added = tmp_path / "added.csv"
        assert add_runs([self.ROW, self.ROW], committed, added) == []
        assert not added.exists()

    def test_bad_row_writes_nothing(self, tmp_path):
        committed = _write_list(tmp_path, [])
        added = tmp_path / "added.csv"
        bad = ["CM06", "not a date", *self.ROW[2:]]
        with pytest.raises(ValueError, match="Bad run list row"):
            add_runs([self.ROW, bad], committed, added)
        assert not added.exists()


class TestFillCache:
    def _runs(self):
        return [
            RUN,
            Run(**{**vars(RUN), "cm": "04"}),
        ]

    def test_fetches_only_missing_runs_with_progress(self, tmp_path, served):
        store = ArchiverStore(tmp_path)
        runs = self._runs()
        load_run(runs[0], store)
        calls = []
        with patch.object(
            run_cache, "load_run", wraps=run_cache.load_run
        ) as load:
            fetched = run_cache.fill_cache(
                runs, lambda *a: calls.append(a), store
            )
        assert fetched == 1
        load.assert_called_once_with(runs[1], store)
        assert calls == [(0, 1, runs[1])]
        assert all(is_cached(run, store) for run in runs)

    def test_stops_at_first_failure(self, tmp_path):
        with patch.object(
            archiver,
            "iter_range_chunks",
            side_effect=archiver.ArchiverTimeoutError("down"),
        ) as fetch:
            with pytest.raises(archiver.ArchiverTimeoutError):
                run_cache.fill_cache(
                    self._runs(), store=ArchiverStore(tmp_path)
                )
        # The first run's PVs are all tried (in parallel); the second run's
        # are never asked for.
        asked = {c.args[0] for c in fetch.call_args_list}
        assert asked == set(run_pvs(RUN.cm, RUN.decarad))
