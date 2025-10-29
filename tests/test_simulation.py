"""Test simulation service."""

import pytest


def test_simulation_main_import():
    """Test simulation main can be imported."""
    from sc_linac_physics.utils.simulation.sc_linac_physics_service import main

    assert callable(main)


def test_simulation_help(monkeypatch, capsys):
    """Test sc-sim --help."""
    from sc_linac_physics.utils.simulation.sc_linac_physics_service import main

    monkeypatch.setattr("sys.argv", ["sc-sim", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
