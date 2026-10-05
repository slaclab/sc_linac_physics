from datetime import datetime
from unittest.mock import patch

from sc_linac_physics.applications.field_emission import gui_updater
from sc_linac_physics.applications.field_emission.gui_updater import (
    UpdateWorker,
)

MOD = "sc_linac_physics.applications.field_emission.gui_updater"

RUN_A = ("01", datetime(2023, 10, 2, 9, 13), datetime(2023, 10, 2, 10), "1", "")
RUN_B = ("02", datetime(2024, 1, 5, 8, 0), datetime(2024, 1, 5, 9), "2", "")


def _run_sync(missing):
    worker = UpdateWorker("sync", "runs.csv")
    with (
        patch(f"{MOD}.read_from_csv", return_value=iter([RUN_A, RUN_B])),
        patch(f"{MOD}.find_missing_runs", return_value=missing) as find,
        patch(f"{MOD}.generate_amp_vs_rad_csvs") as generate,
        patch(f"{MOD}.parse_csv", return_value={"k": "row"}) as parse,
        patch(f"{MOD}.convert_to_h5") as convert,
    ):
        worker.run()
    return find, generate, parse, convert


def test_sync_fetches_only_missing_runs():
    find, generate, parse, convert = _run_sync([RUN_B])

    find.assert_called_once_with([RUN_A, RUN_B])
    generate.assert_called_once_with(*RUN_B[:4])
    parse.assert_called_once_with("runs.csv")
    convert.assert_called_once_with({"k": "row"})


def test_sync_with_nothing_missing_does_not_touch_h5():
    _, generate, _, convert = _run_sync([])

    generate.assert_not_called()
    convert.assert_not_called()


def test_sync_reports_archiver_failure_as_error():
    worker = UpdateWorker("sync", "runs.csv")
    errors = []
    worker.error.connect(errors.append)
    with (
        patch(f"{MOD}.read_from_csv", return_value=iter([RUN_A])),
        patch(f"{MOD}.find_missing_runs", return_value=[RUN_A]),
        patch(
            f"{MOD}.generate_amp_vs_rad_csvs",
            side_effect=TimeoutError("archiver timeout"),
        ),
    ):
        worker.run()

    assert errors == ["archiver timeout"]


def test_run_list_parses_with_read_from_csv():
    """the committed run list must stay readable by the update path"""
    from sc_linac_physics.applications.field_emission.constants import (
        RUN_LIST_PATH,
    )

    runs = list(gui_updater.read_from_csv(RUN_LIST_PATH))

    assert len(runs) == 80
    assert all(start < end for _, start, end, _, _ in runs)
