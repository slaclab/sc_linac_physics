"""Test watcher management commands."""

import pytest


def test_watcher_main_import():
    """Test watcher command can be imported."""
    from sc_linac_physics.cli.watcher_commands import main

    assert callable(main)


def test_watcher_help(monkeypatch, capsys):
    """Test sc-watcher --help."""
    from sc_linac_physics.cli.watcher_commands import main

    monkeypatch.setattr("sys.argv", ["sc-watcher", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    capsys.readouterr()
    # Adjust based on your actual help output


@pytest.mark.parametrize("subcommand", ["start", "stop", "status", "restart"])
def test_watcher_subcommands(subcommand, monkeypatch):
    """Test watcher subcommands exist."""
    from sc_linac_physics.cli.watcher_commands import main

    monkeypatch.setattr("sys.argv", ["sc-watcher", subcommand, "--help"])

    with pytest.raises(SystemExit):
        main()
