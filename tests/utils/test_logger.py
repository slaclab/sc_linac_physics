import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from sc_linac_physics.utils.logger import ColoredFormatter, JSONFormatter


def _record(extra_data):
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "msg", None, None
    )
    record.extra_data = extra_data
    return record


def test_json_formatter_serializes_non_json_extra_data():
    """Path / numpy / nested values must not drop the record."""
    extra = {
        "path": Path("/tmp/x"),
        "amp": np.float64(16.6),
        "nested": {"p": Path("/tmp/y")},
    }

    out = json.loads(JSONFormatter().format(_record(extra)))

    assert out["extra"]["path"] == "/tmp/x"
    assert out["extra"]["nested"]["p"] == "/tmp/y"


def test_text_formatter_serializes_nested_non_json_values():
    formatter = ColoredFormatter("%(message)s")

    out = formatter.format(_record({"nested": {"p": Path("/tmp/y")}}))

    assert "/tmp/y" in out


class TestFileHandlers:
    """custom_logger opens .log and .jsonl once; on failure, console only.

    conftest disables logging and points file handlers at /dev/null, so these
    check the handlers custom_logger adds rather than files on disk.
    """

    @pytest.fixture
    def creators(self):
        from sc_linac_physics.utils import logger as logger_module

        text, json_ = Mock(name="text"), Mock(name="json")
        with (
            patch.object(
                logger_module, "_create_text_file_handler", return_value=text
            ) as make_text,
            patch.object(
                logger_module, "_create_json_file_handler", return_value=json_
            ) as make_json,
        ):
            yield make_text, make_json

    def test_adds_log_and_jsonl_handlers(self, tmp_path, creators):
        from sc_linac_physics.utils.logger import custom_logger

        make_text, make_json = creators
        logger = custom_logger("t.ok", "ops", log_dir=tmp_path / "sub")

        for make in creators:
            make.assert_called_once_with(
                tmp_path / "sub", "ops", logging.DEBUG, 10 * 1024 * 1024, 5
            )
            assert make.return_value in logger.handlers
        assert (tmp_path / "sub").is_dir()

    def test_unwritable_dir_is_console_only_with_one_warning(
        self, tmp_path, creators, capsys
    ):
        from sc_linac_physics.utils.logger import custom_logger

        make_text, _ = creators
        make_text.side_effect = PermissionError("denied")
        logging.disable(logging.NOTSET)  # conftest turns logging off

        logger = custom_logger("t.ro", "ops", log_dir=tmp_path)
        logger.info("still logs")
        logger.info("and again")

        out = capsys.readouterr().out
        assert out.count("File logging unavailable") == 1
        assert "still logs" in out
        # Nothing tries to reopen the files later.
        make_text.assert_called_once()

    def test_half_made_handlers_are_closed(self, tmp_path, creators):
        from sc_linac_physics.utils.logger import custom_logger

        make_text, make_json = creators
        make_json.side_effect = OSError("disk full")

        logger = custom_logger("t.half", "ops", log_dir=tmp_path)

        make_text.return_value.close.assert_called_once_with()
        assert make_text.return_value not in logger.handlers

    def test_no_chmod(self, tmp_path):
        from sc_linac_physics.utils.logger import custom_logger

        with patch("os.chmod") as chmod:
            custom_logger("t.perm", "ops", log_dir=tmp_path / "sub")

        chmod.assert_not_called()

    def test_old_retry_arguments_warn_and_are_ignored(self, tmp_path, creators):
        from sc_linac_physics.utils.logger import custom_logger

        with pytest.warns(DeprecationWarning, match="retry_interval"):
            custom_logger("t.dep", "ops", log_dir=tmp_path, retry_interval=5)

    def test_unknown_argument_still_raises(self, tmp_path):
        from sc_linac_physics.utils.logger import custom_logger

        with pytest.raises(TypeError, match="bogus"):
            custom_logger("t.bad", "ops", log_dir=tmp_path, bogus=1)
