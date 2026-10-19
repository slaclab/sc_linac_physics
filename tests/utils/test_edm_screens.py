"""Tests for the EDM screen catalog and command builder."""

from unittest.mock import patch

import pytest

from sc_linac_physics.utils.edm_screens import (
    CHARACTERIZATION_TABS,
    SCREENS,
    ScreenLevel,
    edm_command,
    open_screen,
    resolve_tab,
    screen_path_and_macros,
)
from sc_linac_physics.utils.sc_linac.linac import MACHINE


def test_cavity_screen_uses_cavity_macros_and_tab():
    path, macros = screen_path_and_macros(
        SCREENS["cavity"], cryomodule="02", cavity=3, tab=4
    )
    cavity = MACHINE.cryomodules["02"].cavities[3]
    assert path == "$EDM/llrf/rf_srf_cavity_main.edl"
    assert macros == f"{cavity.edm_macro_string},SELTAB=4,SELCHAR=3"


def test_cavity_screen_sets_characterization_sub_tab():
    _, macros = screen_path_and_macros(
        SCREENS["cavity"], cryomodule="02", cavity=3, tab=1, char=2
    )
    assert macros.endswith(",SELTAB=1,SELCHAR=2")


def test_cavity_screen_defaults_to_tab_0():
    _, macros = screen_path_and_macros(
        SCREENS["cavity"], cryomodule="02", cavity=3
    )
    assert macros.endswith(",SELTAB=0,SELCHAR=3")


@pytest.mark.parametrize("cm, expected", [("02", "cm"), ("H1", "hl")])
def test_ssa_screen_picks_cm_or_hl_file(cm, expected):
    path, _ = screen_path_and_macros(SCREENS["ssa"], cryomodule=cm, cavity=1)
    assert path == f"$EDM/llrf/rf_srf_ssa_{expected}.edl"


@pytest.mark.parametrize("rack, first_cavity", [("A", 1), ("B", 5)])
def test_rack_screen_uses_first_cavity_in_rack(rack, first_cavity):
    path, macros = screen_path_and_macros(
        SCREENS["freqscan"], cryomodule="02", rack=rack
    )
    cavity = MACHINE.cryomodules["02"].cavities[first_cavity]
    assert path == f"$EDM/llrf/rf_srf_freq_scan_rack{rack}.edl"
    assert macros == cavity.edm_macro_string


def test_cryo_screen_uses_cryo_macros():
    _, macros = screen_path_and_macros(SCREENS["cryo"], cryomodule="02")
    assert macros == "CM=02,AREA=L1B"


def test_global_screen_needs_no_location():
    path, macros = screen_path_and_macros(SCREENS["cryo-all"])
    assert path == "$EDM/cryo/cryo_system_all.edl"
    assert macros == ""


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("cavity", {}),
        ("cavity", {"cryomodule": "02"}),
        ("freqscan", {"cryomodule": "02"}),
    ],
)
def test_missing_location_raises(name, kwargs):
    with pytest.raises(ValueError):
        screen_path_and_macros(SCREENS[name], **kwargs)


def test_every_screen_resolves_for_a_cm_and_an_hl():
    for screen in SCREENS.values():
        for cm in ("02", "H2"):
            path, _ = screen_path_and_macros(
                screen, cryomodule=cm, rack="B", cavity=8
            )
            assert path.endswith(".edl")
            assert "{" not in path


def test_resolve_tab():
    assert resolve_tab("5") == 5
    assert resolve_tab("RF-Controller") == 5
    assert resolve_tab("hwmode") == 10
    assert resolve_tab("frequency-tune", CHARACTERIZATION_TABS) == 2
    with pytest.raises(ValueError):
        resolve_tab("not-a-tab")
    with pytest.raises(ValueError):
        # Sub-tab names are not tab names.
        resolve_tab("frequency-tune")


def test_edm_command_expands_edm_variable(monkeypatch):
    monkeypatch.setenv("EDM", "/edm/display")
    assert edm_command("$EDM/a.edl", "C=1") == [
        "edm",
        "-x",
        "-eolc",
        "-m",
        "C=1",
        "/edm/display/a.edl",
    ]


def test_edm_command_without_macros(monkeypatch):
    monkeypatch.setenv("EDM", "/edm/display")
    assert edm_command("$EDM/a.edl", "") == [
        "edm",
        "-x",
        "-eolc",
        "/edm/display/a.edl",
    ]


def test_open_screen_detaches():
    with patch("sc_linac_physics.utils.edm_screens.subprocess.Popen") as popen:
        open_screen(["edm", "x.edl"])
    popen.assert_called_once_with(["edm", "x.edl"], start_new_session=True)


def test_levels_cover_every_screen():
    assert {s.level for s in SCREENS.values()} == set(ScreenLevel)
