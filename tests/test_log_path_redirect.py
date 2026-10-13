"""Tests for the log-file redirection in tests/conftest.py.

conftest replaces `open` and `Path.open` with versions that hand back a mock
file for log paths. The match used to be the substring "log" anywhere in the
path, so a test file named `test_add_run_dialogs.py` was read as "" and
collected 0 tests with no error. These tests pin the narrower match: real log
locations stay redirected, everything else is opened for real.
"""

from pathlib import Path

import pytest

from tests import conftest


@pytest.mark.parametrize(
    "name",
    ["test_add_run_dialogs.py", "catalog.csv", "blog.txt", "logic.py"],
)
def test_names_containing_log_are_opened_for_real(tmp_path, name):
    path = tmp_path / name
    path.write_text("real contents")

    assert not conftest._is_log_path(str(path))
    with open(path) as f:
        assert f.read() == "real contents"
    with path.open() as f:
        assert f.read() == "real contents"


def test_directory_containing_log_is_created_for_real(tmp_path):
    path = tmp_path / "dialogs"
    path.mkdir()

    assert path.is_dir()


@pytest.mark.parametrize(
    "path",
    [
        "/home/physics/srf/logfiles/tuning/tuning_gui.txt",
        str(Path.home() / ".sc_linac_physics" / "logfiles" / "x" / "y"),
        "/somewhere/cavity_1.log",
        "/somewhere/cavity_1.jsonl",
        "/somewhere/cavity_1.log.3",
    ],
)
def test_log_paths_are_still_redirected(path):
    assert conftest._is_log_path(path)
    with open(path, "w") as f:
        f.write("never reaches disk")
    assert not Path(path).exists()
