from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.applications.field_emission import run_cache
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
    run_path,
)

HEADER = (
    "Cryomodule,Start Date,Start Time,End Date,End Time,Decarad #,"
    "Link to Measurement,Notes,Recharacterization,Multipacting,Commissioning\n"
)


def _write_list(tmp_path, rows):
    path = tmp_path / "runs.csv"
    path.write_text(HEADER + "".join(row + "\n" for row in rows))
    return path


def _frames():
    columns = ["ACCL:L1B:0310:AACTMEAN"] + [
        f"RADM:SYS0:100:{h:02d}:GAMMAAVE" for h in range(1, 11)
    ]
    return {
        (cav, readout): pd.DataFrame(
            np.arange(22, dtype=float).reshape(2, 11) + cav, columns=columns
        )
        for cav in (1, 2)
        for readout in ("average", "instant")
    }


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


def test_run_path_names_cm_and_start(tmp_path):
    assert run_path(RUN, tmp_path) == tmp_path / "cm03_2023-10-02_0913.h5"


class TestLoadRun:
    def test_fetches_once_then_reads_cache(self, tmp_path):
        with patch.object(
            run_cache, "fetch_run", return_value=_frames()
        ) as fetch:
            first = load_run(RUN, tmp_path)
            second = load_run(RUN, tmp_path)

        fetch.assert_called_once_with("03", RUN.start, RUN.end, RUN.decarad)
        assert is_cached(RUN, tmp_path)
        assert first.keys() == second.keys() == _frames().keys()

    def test_round_trip_keeps_values_and_columns(self, tmp_path):
        frames = _frames()
        with patch.object(run_cache, "fetch_run", return_value=frames):
            data = load_run(RUN, tmp_path)

        values, columns = data[2, "instant"]
        np.testing.assert_array_equal(values, frames[2, "instant"].to_numpy())
        assert columns == list(frames[2, "instant"].columns)

    def test_failed_fetch_leaves_nothing(self, tmp_path):
        with patch.object(
            run_cache, "fetch_run", side_effect=RuntimeError("archiver down")
        ):
            with pytest.raises(RuntimeError):
                load_run(RUN, tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_failed_write_leaves_no_temp_file(self, tmp_path):
        bad = {(1, "average"): object()}  # no to_numpy: write fails
        with patch.object(run_cache, "fetch_run", return_value=bad):
            with pytest.raises(AttributeError):
                load_run(RUN, tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_creates_cache_dir(self, tmp_path):
        cache = tmp_path / "srf" / "field_emission" / "runs"
        with patch.object(run_cache, "fetch_run", return_value=_frames()):
            load_run(RUN, cache)
        assert is_cached(RUN, cache)


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

    def test_fetches_only_missing_runs_with_progress(self, tmp_path):
        runs = self._runs()
        with patch.object(run_cache, "fetch_run", return_value=_frames()):
            load_run(runs[0], tmp_path)
            calls = []
            with patch.object(
                run_cache, "load_run", wraps=run_cache.load_run
            ) as load:
                fetched = run_cache.fill_cache(
                    runs, lambda *a: calls.append(a), tmp_path
                )
        assert fetched == 1
        load.assert_called_once_with(runs[1], tmp_path)
        assert calls == [(0, 1, runs[1])]

    def test_stops_at_first_failure(self, tmp_path):
        with patch.object(
            run_cache, "fetch_run", side_effect=ConnectionError("down")
        ) as fetch:
            with pytest.raises(ConnectionError):
                run_cache.fill_cache(self._runs(), cache_dir=tmp_path)
        assert fetch.call_count == 1
