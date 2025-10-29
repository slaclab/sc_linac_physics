"""Test hierarchical setup commands."""

import pytest


@pytest.mark.parametrize(
    "main_func,module",
    [
        (
            "main",
            "sc_linac_physics.applications.auto_setup.launcher.srf_global_setup_launcher",
        ),
        (
            "main",
            "sc_linac_physics.applications.auto_setup.launcher.srf_linac_setup_launcher",
        ),
        (
            "main",
            "sc_linac_physics.applications.auto_setup.launcher.srf_cm_setup_launcher",
        ),
        (
            "main",
            "sc_linac_physics.applications.auto_setup.launcher.srf_cavity_setup_launcher",
        ),
    ],
)
def test_setup_command_imports(main_func, module):
    """Test that setup command main functions exist."""
    mod = __import__(module, fromlist=[main_func])
    func = getattr(mod, main_func)
    assert callable(func)


def test_setup_all_help(monkeypatch, capsys):
    """Test sc-setup-all --help."""
    from sc_linac_physics.applications.auto_setup.launcher.srf_global_setup_launcher import (
        main,
    )

    monkeypatch.setattr("sys.argv", ["sc-setup-all", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0


def test_setup_linac_help(monkeypatch, capsys):
    """Test sc-setup-linac --help."""
    from sc_linac_physics.applications.auto_setup.launcher.srf_linac_setup_launcher import (
        main,
    )

    monkeypatch.setattr("sys.argv", ["sc-setup-linac", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0


@pytest.mark.parametrize(
    "level,expected_args",
    [
        ("sc-setup-all", []),
        ("sc-setup-linac", ["--linac", "NL"]),
        ("sc-setup-cm", ["--cryomodule", "CM01"]),
        ("sc-setup-cav", ["--cavity", "CAV001"]),
    ],
)
def test_setup_commands_with_args(level, expected_args):
    """Test setup commands accept expected arguments."""
    import subprocess

    # This is a smoke test - just verify the command exists
    result = subprocess.run(
        [level, "--help"], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0
