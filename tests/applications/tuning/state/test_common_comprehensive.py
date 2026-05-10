"""Tests for tuning state common utilities."""

from pathlib import Path

import pytest

from sc_linac_physics.applications.tuning.state import common
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR


def test_platform_default_paths_linux():
    """Test platform default paths on Linux."""
    base_dir, db_path, json_path = common._platform_default_paths(
        "Linux",
        Path("/Users/tester"),
    )

    assert base_dir == Path("/home/physics/srf")
    assert db_path == Path("/home/physics/srf/databases/tune_status.sqlite")
    assert json_path == Path("/home/physics/srf/json/tune_status.json")


def test_platform_default_paths_macos_like():
    """Test platform default paths on macOS."""
    base_dir, db_path, json_path = common._platform_default_paths(
        "Darwin",
        Path("/Users/tester"),
    )

    assert base_dir == Path("/Users/tester")
    assert db_path == Path("/Users/tester/databases/tune_status.sqlite")
    assert json_path == Path("/Users/tester/json/tune_status.json")


def test_resolve_paths_use_platform_defaults_for_default_base_dir():
    """Test resolve_poll_paths uses defaults when base_dir is default."""
    db_path, json_path, log_path = common.resolve_poll_paths(
        common.DEFAULT_BASE_DIR
    )

    assert db_path == common.DEFAULT_DB_PATH
    assert json_path == common.DEFAULT_JSON_PATH
    assert log_path == common.DEFAULT_LOG_PATH


def test_resolve_paths_use_base_dir_for_non_default_base_dir(tmp_path):
    """Test resolve_poll_paths uses custom base_dir."""
    db_path, json_path, log_path = common.resolve_poll_paths(tmp_path)

    assert db_path == tmp_path / common.DEFAULT_DB_FILENAME
    assert json_path == tmp_path / "json" / common.DEFAULT_JSON_FILENAME
    assert log_path == common.DEFAULT_LOG_PATH


def test_resolve_paths_respects_explicit_overrides(tmp_path):
    """Test resolve_poll_paths respects explicit path overrides."""
    custom_db = tmp_path / "custom.db"
    custom_json = tmp_path / "custom.json"
    custom_log = tmp_path / "custom.log"

    db_path, json_path, log_path = common.resolve_poll_paths(
        tmp_path,
        db_path=custom_db,
        json_path=custom_json,
        log_path=custom_log,
    )

    assert db_path == custom_db
    assert json_path == custom_json
    assert log_path == custom_log


def test_default_log_path_comes_from_tune_log_dir():
    """Test DEFAULT_LOG_PATH is properly set from TUNE_LOG_DIR."""
    assert common.DEFAULT_LOG_PATH == TUNE_LOG_DIR / common.DEFAULT_LOG_FILENAME


def test_resolve_db_path_uses_override_if_provided(tmp_path):
    """Test resolve_db_path uses override when provided."""
    custom_path = tmp_path / "custom.sqlite"
    result = common.resolve_db_path(tmp_path, db_path=custom_path)
    assert result == custom_path


def test_resolve_db_path_uses_default_in_base_dir(tmp_path):
    """Test resolve_db_path uses default filename in base_dir."""
    result = common.resolve_db_path(tmp_path)
    assert result == tmp_path / common.DEFAULT_DB_FILENAME


def test_batched_chunks_sequences():
    """Test batched() chunks sequences correctly."""
    items = [1, 2, 3, 4, 5]
    batches = list(common.batched(items, 2))
    assert batches == [[1, 2], [3, 4], [5]]


def test_batched_exact_chunks():
    """Test batched() with evenly divisible sequence."""
    items = [1, 2, 3, 4]
    batches = list(common.batched(items, 2))
    assert batches == [[1, 2], [3, 4]]


def test_batched_single_batch():
    """Test batched() with batch size larger than sequence."""
    items = [1, 2, 3]
    batches = list(common.batched(items, 10))
    assert batches == [[1, 2, 3]]


def test_batched_empty_sequence():
    """Test batched() with empty sequence."""
    items = []
    batches = list(common.batched(items, 2))
    assert batches == []


def test_batched_invalid_batch_size():
    """Test batched() raises error with invalid batch size."""
    items = [1, 2, 3]
    with pytest.raises(ValueError):
        list(common.batched(items, 0))

    with pytest.raises(ValueError):
        list(common.batched(items, -1))


def test_connect_db_creates_database(tmp_path):
    """Test connect_db creates database file."""
    db_path = tmp_path / "test.db"
    conn = common.connect_db(db_path)
    try:
        assert db_path.exists()
        assert conn is not None
    finally:
        conn.close()


def test_connect_db_creates_parent_directories(tmp_path):
    """Test connect_db creates parent directories."""
    db_path = tmp_path / "nested" / "dir" / "test.db"
    conn = common.connect_db(db_path)
    try:
        assert db_path.exists()
        assert db_path.parent.exists()
    finally:
        conn.close()


def test_connect_db_with_row_factory(tmp_path):
    """Test connect_db sets row factory when provided."""
    import sqlite3

    db_path = tmp_path / "test.db"
    conn = common.connect_db(db_path, row_factory=sqlite3.Row)
    try:
        assert conn.row_factory == sqlite3.Row
    finally:
        conn.close()


def test_now_utc_iso_returns_iso_format():
    """Test now_utc_iso returns valid ISO-8601 format."""
    iso_str = common.now_utc_iso()
    # Should be able to parse as ISO 8601
    from datetime import datetime

    dt = datetime.fromisoformat(iso_str)
    assert dt is not None
