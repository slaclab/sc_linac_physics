import json
import logging
from pathlib import Path

import numpy as np

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
