"""Tests for the sc-edm command."""

from unittest.mock import patch

import pytest

from sc_linac_physics.cli.edm_commands import main


def test_help_lists_screens(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "cavity" in out
    assert "freqscan" in out


def test_print_does_not_start_edm(capsys, monkeypatch):
    monkeypatch.setenv("EDM", "/edm/display")
    with patch("sc_linac_physics.cli.edm_commands.open_screen") as opener:
        assert main(["cavity", "02", "3", "--tab", "4", "--print"]) == 0
    opener.assert_not_called()
    out = capsys.readouterr().out
    assert out.startswith("edm -x -eolc -m C=3,")
    assert "SELTAB=4" in out
    assert "/edm/display/llrf/rf_srf_cavity_main.edl" in out


def test_tab_and_char_names(capsys):
    argv = ["cavity", "02", "3", "--tab", "characterization"]
    assert main(argv + ["--char", "frequency-tune", "--print"]) == 0
    assert "SELTAB=1,SELCHAR=2" in capsys.readouterr().out


def test_opens_screen(monkeypatch):
    monkeypatch.setenv("EDM", "/edm/display")
    with patch("sc_linac_physics.cli.edm_commands.open_screen") as opener:
        assert main(["freqscan", "02", "b"]) == 0
    command = opener.call_args.args[0]
    assert command[-1] == "/edm/display/llrf/rf_srf_freq_scan_rackB.edl"


def test_unset_edm_variable_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv("EDM", raising=False)
    with patch("sc_linac_physics.cli.edm_commands.open_screen") as opener:
        assert main(["cryo", "02"]) == 1
    opener.assert_not_called()
    assert "$EDM is not set" in capsys.readouterr().err


def test_missing_edm_binary_is_an_error(monkeypatch, capsys):
    monkeypatch.setenv("EDM", "/edm/display")
    with patch(
        "sc_linac_physics.cli.edm_commands.open_screen",
        side_effect=FileNotFoundError,
    ):
        assert main(["cryo-all"]) == 1
    assert "not on PATH" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["cavity", "02"],
        ["cavity", "02", "9"],
        ["cavity", "CM02", "1"],
        ["cavity", "02", "1", "--tab", "nope"],
        ["cavity", "02", "1", "--char", "nope"],
        ["freqscan", "02", "C"],
    ],
)
def test_bad_arguments_exit_with_usage(argv):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2
