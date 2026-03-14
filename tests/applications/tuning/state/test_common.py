from pathlib import Path

from sc_linac_physics.applications.tuning.state import common
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR


def test_platform_default_paths_linux():
    base_dir, db_path, json_path = common._platform_default_paths(
        "Linux",
        Path("/Users/tester"),
    )

    assert base_dir == Path("/home/physics/srf")
    assert db_path == Path("/home/physics/srf/databases/tune_status.sqlite")
    assert json_path == Path("/home/physics/srf/tune_status.json")


def test_platform_default_paths_macos_like():
    base_dir, db_path, json_path = common._platform_default_paths(
        "Darwin",
        Path("/Users/tester"),
    )

    assert base_dir == Path("/Users/tester")
    assert db_path == Path("/Users/tester/databases/tune_status.sqlite")
    assert json_path == Path("/Users/tester/tune_status.json")


def test_resolve_paths_use_platform_defaults_for_default_base_dir():
    db_path, json_path, log_path = common.resolve_poll_paths(
        common.DEFAULT_BASE_DIR
    )

    assert db_path == common.DEFAULT_DB_PATH
    assert json_path == common.DEFAULT_JSON_PATH
    assert log_path == common.DEFAULT_LOG_PATH


def test_resolve_paths_use_base_dir_for_non_default_base_dir(tmp_path):
    db_path, json_path, log_path = common.resolve_poll_paths(tmp_path)

    assert db_path == tmp_path / common.DEFAULT_DB_FILENAME
    assert json_path == tmp_path / common.DEFAULT_JSON_FILENAME
    assert log_path == common.DEFAULT_LOG_PATH


def test_default_log_path_comes_from_tune_log_dir():
    assert common.DEFAULT_LOG_PATH == TUNE_LOG_DIR / common.DEFAULT_LOG_FILENAME
