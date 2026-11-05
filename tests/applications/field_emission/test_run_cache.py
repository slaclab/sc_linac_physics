from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    fetch_run,
    run_pvs,
)
from sc_linac_physics.applications.field_emission.constants import (
    RUN_LIST_PATH,
)
from sc_linac_physics.applications.field_emission.run_cache import (
    Run,
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
        assert read_run_list(path) == [RUN]

    def test_end_date_used_when_given(self, tmp_path):
        path = _write_list(
            tmp_path, ["CM03,10/2/23,23:00,10/3/23,1:00,1,,overnight,Y,N,N"]
        )
        run = read_run_list(path)[0]
        assert run.end == datetime(2023, 10, 3, 1, 0)
        assert run.notes == "overnight"

    def test_letter_cryomodule(self, tmp_path):
        path = _write_list(tmp_path, ["CMH1,10/2/23,9:13,,10:00,2,,,Y,N,N"])
        assert read_run_list(path)[0].cm == "H1"

    def test_skips_commented_and_malformed_rows(self, tmp_path):
        path = _write_list(
            tmp_path,
            [
                "#CM03,10/2/23,9:13,,10:00,1,,,Y,N,N",
                "CM03,not a date,9:13,,10:00,1,,,Y,N,N",
                "CM04,10/2/23,9:13,,10:00,1,,,Y,N,N",
            ],
        )
        assert [run.cm for run in read_run_list(path)] == ["04"]

    def test_sorted_oldest_first(self, tmp_path):
        path = _write_list(
            tmp_path,
            [
                "CM05,1/5/24,9:00,,10:00,1,,,Y,N,N",
                "CM04,1/4/24,9:00,,10:00,1,,,Y,N,N",
            ],
        )
        assert [run.cm for run in read_run_list(path)] == ["04", "05"]

    def test_committed_run_list_parses(self):
        runs = read_run_list(RUN_LIST_PATH)
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
