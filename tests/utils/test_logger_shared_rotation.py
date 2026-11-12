"""SharedRotatingFileHandler: several processes writing one log file.

These write real files under tmp_path. mock_log_files is overridden below,
so logging.FileHandler and open() are the real ones.
"""

import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from sc_linac_physics.utils import logger as logger_module
from sc_linac_physics.utils.logger import SharedRotatingFileHandler

pytestmark = pytest.mark.skipif(
    logger_module.fcntl is None, reason="needs fcntl.flock"
)

SRC = str(Path(logger_module.__file__).parents[2])


@pytest.fixture(autouse=True)
def mock_log_files():
    """Override conftest's: these tests need real files.

    conftest also replaces builtins.open, which FileHandler opens through.
    """
    from tests import conftest

    with patch("builtins.open", conftest._original_open):
        yield


def _lines(directory, name="ops.log"):
    lines = []
    for path in directory.glob(f"{name}*"):
        if path.name.endswith(".lock"):
            continue
        with open(path, encoding="utf-8") as f:
            lines.extend(f.read().splitlines())
    return lines


def _record(msg):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)


def test_processes_rotating_one_file_lose_no_lines(tmp_path):
    """4 processes x 300 lines, rotating at 2 kB, keep all 1200."""
    script = textwrap.dedent("""
        import logging, sys
        from sc_linac_physics.utils.logger import SharedRotatingFileHandler
        h = SharedRotatingFileHandler(
            sys.argv[1], maxBytes=2000, backupCount=10000
        )
        h.setFormatter(logging.Formatter("%(message)s"))
        for i in range(300):
            h.emit(logging.LogRecord(
                "t", logging.INFO, "", 0, f"{sys.argv[2]}-{i}", None, None
            ))
        h.close()
        """)
    env = {**os.environ, "PYTHONPATH": SRC}
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path / "ops.log"), str(n)],
            env=env,
        )
        for n in range(4)
    ]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0, 0]

    lines = _lines(tmp_path)
    assert len(lines) == 1200
    assert len(set(lines)) == 1200
    assert (tmp_path / "ops.log.3").exists()  # it did rotate


def test_follows_a_rotation_by_another_process(tmp_path):
    path = tmp_path / "ops.log"
    handler = SharedRotatingFileHandler(path)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.emit(_record("before"))

    os.rename(path, tmp_path / "ops.log.1")  # what the other process does
    handler.emit(_record("after"))
    handler.close()

    with open(path, encoding="utf-8") as f:
        assert f.read() == "after\n"


def test_writes_unlocked_when_the_lock_is_held(tmp_path):
    import fcntl

    path = tmp_path / "ops.log"
    handler = SharedRotatingFileHandler(path)
    handler.setFormatter(logging.Formatter("%(message)s"))
    holder = os.open(handler.lock_path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        with patch.object(logger_module, "LOG_LOCK_TIMEOUT_S", 0.05):
            handler.emit(_record("not lost"))
    finally:
        os.close(holder)
        handler.close()

    assert _lines(tmp_path) == ["not lost"]


def test_writes_unlocked_when_the_lock_file_cannot_be_opened(tmp_path):
    path = tmp_path / "ops.log"
    handler = SharedRotatingFileHandler(path)
    handler.setFormatter(logging.Formatter("%(message)s"))
    os.mkdir(handler.lock_path)  # opening it read-write fails

    handler.emit(_record("not lost"))
    handler.close()

    assert _lines(tmp_path) == ["not lost"]


def test_new_lock_file_is_group_writable(tmp_path):
    handler = SharedRotatingFileHandler(tmp_path / "ops.log")
    handler.emit(_record("x"))
    handler.close()

    assert os.stat(handler.lock_path).st_mode & 0o777 == 0o664


def test_custom_logger_uses_it_for_both_files(tmp_path):
    with patch.object(logger_module, "SharedRotatingFileHandler") as cls:
        logger_module.custom_logger("t.shared", "ops", log_dir=tmp_path)

    names = sorted(Path(c.args[0]).name for c in cls.call_args_list)
    assert names == ["ops.jsonl", "ops.log"]


def test_file_made_by_rollover_is_group_writable(tmp_path):
    path = tmp_path / "ops.log"
    handler = SharedRotatingFileHandler(path, maxBytes=10, backupCount=2)
    handler.setFormatter(logging.Formatter("%(message)s"))
    old = os.umask(0o022)
    try:
        handler.emit(_record("first line, past 10 bytes"))
        handler.emit(_record("rotates before this one"))
    finally:
        os.umask(old)
        handler.close()

    assert (tmp_path / "ops.log.1").exists()
    assert os.stat(path).st_mode & 0o777 == 0o664


def test_reopen_leaves_existing_permissions_alone(tmp_path):
    path = tmp_path / "ops.log"
    path.touch()
    os.chmod(path, 0o640)
    handler = SharedRotatingFileHandler(path)
    handler.emit(_record("x"))
    handler.close()

    assert os.stat(path).st_mode & 0o777 == 0o640


def test_failed_reopen_after_rotation_does_not_raise(tmp_path):
    path = tmp_path / "ops.log"
    handler = SharedRotatingFileHandler(path)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.emit(_record("before"))
    os.rename(path, tmp_path / "ops.log.1")

    real_open = handler._open
    with (
        patch.object(handler, "_open", side_effect=PermissionError),
        patch.object(handler, "handleError") as handle_error,
    ):
        handler.emit(_record("dropped"))  # must not raise
    handle_error.assert_called_once()

    handler._open = real_open
    handler.emit(_record("after"))  # writes once the file opens again
    handler.close()

    with open(path, encoding="utf-8") as f:
        assert f.read() == "after\n"
