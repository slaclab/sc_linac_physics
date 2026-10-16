# Not test_add_run_dialogs.py: tests/conftest.py mocks open() for any path
# containing "log", which would hide this file from collection.

from unittest.mock import patch

from sc_linac_physics.applications.field_emission import add_run_dialogs
from sc_linac_physics.applications.field_emission.add_run_dialogs import (
    MultiInputDialog,
    SingleInputDialog,
    UpdateButtons,
)

ELOG = (
    "https://mccelog.slac.stanford.edu/elog/wbin/elog_item.php?elog_id=1253142"
)
GOOD = ("6", "2/2/24", "13:05", "", "13:20", "2", ELOG, "", "Y", "N", "N")


def test_single_dialog_returns_fields_in_run_list_order(qtbot):
    dialog = SingleInputDialog()
    qtbot.addWidget(dialog)
    for (label, _), value in zip(SingleInputDialog.FIELDS, GOOD):
        dialog.lines[label].setText(value)
    assert dialog.get_inputs() == GOOD


def test_multi_dialog_returns_path(qtbot):
    dialog = MultiInputDialog()
    qtbot.addWidget(dialog)
    dialog.line_csv.setText("/tmp/runs.csv")
    assert dialog.get_input() == "/tmp/runs.csv"


def test_invalid_single_input_warns_and_starts_nothing(qtbot):
    buttons = UpdateButtons()
    qtbot.addWidget(buttons)
    bad = ("99",) + GOOD[1:]
    with (
        patch.object(add_run_dialogs, "SingleInputDialog") as dialog,
        patch.object(add_run_dialogs.QMessageBox, "warning") as warning,
        patch.object(buttons, "_do_background_task") as start,
    ):
        dialog.return_value.exec.return_value = True
        dialog.return_value.get_inputs.return_value = bad
        buttons.update_in_single_mode()
    assert "Invalid cryomodule" in warning.call_args.args[2]
    start.assert_not_called()


def test_valid_single_input_runs_worker_in_background(qtbot):
    buttons = UpdateButtons()
    qtbot.addWidget(buttons)
    started = []
    buttons._run_in_background = started.append
    with patch.object(add_run_dialogs, "SingleInputDialog") as dialog:
        dialog.return_value.exec.return_value = True
        dialog.return_value.get_inputs.return_value = GOOD
        buttons.update_in_single_mode()
    assert started == [buttons.worker.run]
    assert buttons.worker.mode == "single"
    buttons.progress_dialog.close()


def test_worker_finish_closes_progress_and_accepts(qtbot):
    buttons = UpdateButtons()
    qtbot.addWidget(buttons)
    buttons._run_in_background = lambda target: None
    with patch.object(add_run_dialogs, "MultiInputDialog") as dialog:
        dialog.return_value.exec.return_value = True
        dialog.return_value.get_input.return_value = "/tmp/runs.csv"
        buttons.update_in_multi_mode()
    with patch.object(add_run_dialogs.QMessageBox, "information") as info:
        buttons.worker.finished.emit(
            "1 run(s) added, 1 fetched from the archiver."
        )
    info.assert_called_once()
    assert buttons.result() == UpdateButtons.Accepted


def test_worker_error_warns(qtbot):
    buttons = UpdateButtons()
    qtbot.addWidget(buttons)
    buttons._run_in_background = lambda target: None
    with patch.object(add_run_dialogs, "MultiInputDialog") as dialog:
        dialog.return_value.exec.return_value = True
        dialog.return_value.get_input.return_value = "/tmp/runs.csv"
        buttons.update_in_multi_mode()
    with patch.object(add_run_dialogs.QMessageBox, "warning") as warning:
        buttons.worker.error.emit("Bad run list row")
    assert warning.call_args.args[2] == "Bad run list row"
