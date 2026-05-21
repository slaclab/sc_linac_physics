from pathlib import Path

from sc_linac_physics.utils.platform_paths import (
    get_database_dir,
    get_json_dir,
    get_log_base_dir,
    get_srf_base_dir,
    get_ssa_cal_base_dir,
    is_linux,
    is_macos,
)


def test_platform_paths_linux():
    home = Path("/Users/tester")

    assert get_srf_base_dir(system_name="Linux", home_dir=home) == Path(
        "/home/physics/srf"
    )
    assert get_database_dir(system_name="Linux", home_dir=home) == Path(
        "/home/physics/srf/databases"
    )
    assert get_json_dir(system_name="Linux", home_dir=home) == Path(
        "/home/physics/srf/json"
    )
    assert get_log_base_dir(system_name="Linux", home_dir=home) == Path(
        "/home/physics/srf/logfiles"
    )


def test_platform_paths_macos_like():
    home = Path("/Users/tester")
    base = home / ".sc_linac_physics"

    assert get_srf_base_dir(system_name="Darwin", home_dir=home) == base
    assert (
        get_database_dir(system_name="Darwin", home_dir=home)
        == base / "databases"
    )
    assert get_json_dir(system_name="Darwin", home_dir=home) == base / "json"
    assert (
        get_log_base_dir(system_name="Darwin", home_dir=home)
        == base / "logfiles"
    )


def test_ssa_cal_base_dir_linux():
    home = Path("/Users/tester")
    assert get_ssa_cal_base_dir(system_name="Linux", home_dir=home) == Path(
        "/u1/lcls/physics/rf_lcls2/ssa_cal"
    )


def test_ssa_cal_base_dir_macos_like():
    home = Path("/Users/tester")
    base = home / ".sc_linac_physics"
    assert (
        get_ssa_cal_base_dir(system_name="Darwin", home_dir=home)
        == base / "ssa_cal"
    )


def test_platform_predicates():
    assert is_linux(system_name="Linux") is True
    assert is_linux(system_name="Darwin") is False
    assert is_macos(system_name="Darwin") is True
    assert is_macos(system_name="Linux") is False
