"""Shared platform-aware path helpers."""

import platform
from pathlib import Path


def _current_system(system_name: str | None = None) -> str:
    return system_name or platform.system()


def _current_home(home_dir: Path | None = None) -> Path:
    return home_dir or Path.home()


def is_macos(*, system_name: str | None = None) -> bool:
    """Return True when running on macOS."""
    return _current_system(system_name) == "Darwin"


def is_linux(*, system_name: str | None = None) -> bool:
    """Return True when running on Linux."""
    return _current_system(system_name) == "Linux"


def get_srf_base_dir(
    *,
    system_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Return the SRF base directory for the current platform."""
    if is_linux(system_name=system_name):
        return Path("/home/physics/srf")
    return _current_home(home_dir) / ".sc_linac_physics"


def get_database_dir(
    *,
    system_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Return the default databases directory for the current platform."""
    return (
        get_srf_base_dir(system_name=system_name, home_dir=home_dir)
        / "databases"
    )


def get_json_dir(
    *,
    system_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Return the default JSON directory for the current platform."""
    return get_srf_base_dir(system_name=system_name, home_dir=home_dir) / "json"


def get_log_base_dir(
    *,
    system_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Return the default logfiles directory for the current platform."""
    return (
        get_srf_base_dir(system_name=system_name, home_dir=home_dir)
        / "logfiles"
    )


def get_ssa_cal_base_dir(
    *,
    system_name: str | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Return the root directory where SSA calibration plots are stored."""
    if is_linux(system_name=system_name):
        return Path("/u1/lcls/physics/rf_lcls2/ssa_cal")
    return (
        get_srf_base_dir(system_name=system_name, home_dir=home_dir) / "ssa_cal"
    )
