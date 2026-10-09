from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.field_emission import gui_updater
from sc_linac_physics.applications.field_emission.gui_updater import (
    UpdateWorker,
)
from sc_linac_physics.applications.field_emission.run_cache import Run

ELOG = (
    "https://mccelog.slac.stanford.edu/elog/wbin/elog_item.php?elog_id=1253142"
)
INPUT_ROW = ("4", "1/4/24", "9:00", "", "10:00", "1", "", "", "Y", "N", "N")
RUN = Run(
    cm="04",
    start=datetime(2024, 1, 4, 9, 0),
    end=datetime(2024, 1, 4, 10, 0),
    decarad="1",
    elog="",
    notes="",
    start_text="9:00",
    end_text="10:00",
)


def _run_worker(worker):
    finished, error = Mock(), Mock()
    worker.finished.connect(finished)
    worker.error.connect(error)
    worker.run()
    return finished, error


def test_single_adds_the_row_and_fetches_it():
    worker = UpdateWorker("single", {"cryomodule": "04"}, INPUT_ROW)
    with (
        patch.object(gui_updater, "add_runs", return_value=[RUN]) as add,
        patch.object(gui_updater, "read_run_list", return_value=[RUN]),
        patch.object(gui_updater, "fill_cache", return_value=1) as fill,
    ):
        finished, error = _run_worker(worker)

    add.assert_called_once_with([["CM04", *INPUT_ROW[1:]]])
    assert fill.call_args.args[0] == [RUN]
    finished.assert_called_once_with(
        "1 run(s) added, 1 fetched from the archiver."
    )
    error.assert_not_called()


def test_multi_reads_the_csv(tmp_path):
    csv_path = tmp_path / "runs.csv"
    csv_path.write_text(
        "Cryomodule,Start Date,Start Time,End Date,End Time,Decarad #\n"
        f"#CM03,1/3/24,9:00,,10:00,1,{ELOG},,Y,N,N\n"
        f"CM04,1/4/24,9:00,,10:00,1,{ELOG},,Y,N,N\n"
    )
    worker = UpdateWorker("multi", str(csv_path))
    with (
        patch.object(gui_updater, "add_runs", return_value=[]) as add,
        patch.object(gui_updater, "read_run_list", return_value=[RUN]),
        patch.object(gui_updater, "fill_cache", return_value=0),
    ):
        finished, _ = _run_worker(worker)

    rows = add.call_args.args[0]
    assert [row[0] for row in rows] == ["CM04"]
    finished.assert_called_once_with(
        "0 run(s) added, 0 fetched from the archiver."
    )


@pytest.mark.parametrize(
    "bad_row",
    [
        f"CM99,1/5/24,9:00,,10:00,1,{ELOG},,Y,N,N",  # unknown cryomodule
        f"CM05,1/5/24,9:00,,10:00,3,{ELOG},,Y,N,N",  # decarad 3
        "CM05,1/5/24,9:00,,10:00,1,http://example.com,,Y,N,N",  # bad elog
        "CM05,1/5/24,9:00",  # short row
    ],
)
def test_multi_rejects_a_bad_row_before_writing_any(tmp_path, bad_row):
    csv_path = tmp_path / "runs.csv"
    csv_path.write_text(
        "Cryomodule,Start Date,Start Time,End Date,End Time,Decarad #\n"
        f"CM04,1/4/24,9:00,,10:00,1,{ELOG},,Y,N,N\n"
        f"{bad_row}\n"
    )
    worker = UpdateWorker("multi", str(csv_path))
    with patch.object(gui_updater, "add_runs") as add:
        finished, error = _run_worker(worker)

    add.assert_not_called()
    assert "line 3" in error.call_args.args[0]
    finished.assert_not_called()


def test_progress_names_each_run():
    worker = UpdateWorker("single", {"cryomodule": "04"}, INPUT_ROW)
    progress = Mock()
    worker.progress.connect(progress)
    worker._report(0, 2, RUN)
    progress.assert_called_once_with("Fetching 1/2: CM04 01/04/24 09:00")


def test_failure_emits_error():
    worker = UpdateWorker("single", {"cryomodule": "04"}, INPUT_ROW)
    with patch.object(
        gui_updater, "add_runs", side_effect=ValueError("Bad run list row")
    ):
        finished, error = _run_worker(worker)
    error.assert_called_once_with("Bad run list row")
    finished.assert_not_called()


GOOD = ("6", "2/2/24", "13:05", "", "13:20", "2", ELOG, "", "y", "N", "N")


def _with(**changes):
    names = [
        "cm",
        "ds",
        "ts",
        "de",
        "te",
        "dec",
        "elog",
        "notes",
        "r",
        "m",
        "c",
    ]
    row = dict(zip(names, GOOD))
    row.update(changes)
    return tuple(row[name] for name in names)


class TestValidateEmissionData:
    def test_valid_row(self):
        valid = gui_updater.validate_emission_data(GOOD)
        assert valid == {
            "cryomodule": "06",
            "start": datetime(2024, 2, 2, 13, 5),
            "end": datetime(2024, 2, 2, 13, 20),
            "decarad": "2",
            "elog": ELOG,
            "filters": ["Y", "N", "N"],
        }

    def test_cm_prefix_accepted(self):
        valid = gui_updater.validate_emission_data(_with(cm="CM06"))
        assert valid["cryomodule"] == "06"

    def test_empty_elog_only_when_not_required(self):
        with pytest.raises(ValueError, match="eLog link"):
            gui_updater.validate_emission_data(_with(elog=""))
        valid = gui_updater.validate_emission_data(
            _with(elog=""), require_elog=False
        )
        assert valid["elog"] == ""

    def test_end_date_given(self):
        valid = gui_updater.validate_emission_data(
            _with(ts="23:00", de="2/3/24", te="1:00")
        )
        assert valid["end"] == datetime(2024, 2, 3, 1, 0)

    @pytest.mark.parametrize(
        "changes, message",
        [
            ({"cm": "99"}, "Invalid cryomodule"),
            ({"ds": "2024-02-02"}, "Start time does not match"),
            ({"te": "25:00"}, "End time does not match"),
            ({"te": "13:00"}, "End date is before start date"),
            ({"dec": "3"}, "Invalid decarad"),
            ({"elog": "http://example.com"}, "eLog link"),
            ({"m": "maybe"}, "Invalid filter"),
        ],
    )
    def test_rejects(self, changes, message):
        with pytest.raises(ValueError, match=message):
            gui_updater.validate_emission_data(_with(**changes))
