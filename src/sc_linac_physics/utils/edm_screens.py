"""Catalog of EDM screens, and the ``edm`` command that opens each one.

The paths and macros here are the ones the fault buttons use
(``displays/cavity_display/utils/faults.csv``, "Button Path" and "Button
Macros") and the ones hardcoded in the tuning and auto-setup GUIs. Cavity
screens get their macros from ``Cavity.edm_macro_string``, the same property
the buttons use, so a screen opened here gets the same macros as from a button.

``sc-edm`` (``cli/edm_commands.py``) is the command-line front end. Nothing
here writes a PV. It only builds and starts an ``edm`` process.
"""

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from sc_linac_physics.utils.sc_linac.linac import MACHINE


class ScreenLevel(Enum):
    """What a screen needs to know to open: nothing, a CM, a rack or a cavity."""

    GLOBAL = "global"
    CRYOMODULE = "cryomodule"
    RACK = "rack"
    CAVITY = "cavity"


@dataclass(frozen=True)
class EdmScreen:
    """One EDM screen.

    ``path`` may contain ``$EDM`` and these placeholders:
    ``{cm_or_hl}`` ("cm" or "hl", for the SSA screen) and ``{rack}``
    ("A" or "B").
    ``extra_macros`` are added after the cavity or cryo macros.
    """

    name: str
    description: str
    level: ScreenLevel
    path: str
    extra_macros: str = ""
    # Cryo screens take CM=,AREA= (Cavity.cryo_edm_macro_string) instead
    # of the LLRF cavity macros.
    cryo_macros: bool = False
    # Only the cavity main screen has tabs chosen with SELTAB.
    has_tabs: bool = False


# SELCHAR picks the sub-tab inside the Characterization tab of
# rf_srf_cavity_main.edl. 3 is the Cavity sub-tab, the value most fault
# buttons pass. Other tabs ignore it.
CAVITY_MAIN_SELCHAR = 3

# Names for the rf_srf_cavity_main.edl tabs (SELTAB) and Characterization
# sub-tabs (SELCHAR), so `--tab` and `--char` can take a name. Numbers always
# work. Both count left to right from 0, as the tabs appear on the screen.
CAVITY_TABS: Dict[str, int] = {
    "overview": 0,
    "characterization": 1,
    "detune": 2,
    "tuners": 3,
    "interlocks": 4,
    "rf-controller": 5,
    "diag": 6,
    "pulsed": 7,
    "hardware": 8,
    "calib": 9,
    "hwmode": 10,
}
CHARACTERIZATION_TABS: Dict[str, int] = {
    "piezo-pre-rf": 0,
    "ssa": 1,
    "frequency-tune": 2,
    "cavity": 3,
    "piezo-with-rf": 4,
}

SCREENS: Dict[str, EdmScreen] = {
    screen.name: screen
    for screen in [
        EdmScreen(
            name="cavity",
            description="LLRF cavity main screen",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_cavity_main.edl",
            has_tabs=True,
        ),
        EdmScreen(
            name="ssa",
            description="SSA screen (CM or HL version)",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_ssa_{cm_or_hl}.edl",
        ),
        EdmScreen(
            name="intlk",
            description="Cavity cryo interlocks",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_intlk_cryo.edl",
        ),
        EdmScreen(
            name="prl",
            description="PRL screen for the cryomodule",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_prl_cm.edl",
            extra_macros="SELTAB=8,SELCHAR=3",
        ),
        EdmScreen(
            name="waveform",
            description="Waveform acquisition",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_wf_acq_cm.edl",
            extra_macros="SELTAB=0,SELCHAR=3",
        ),
        EdmScreen(
            name="fault-waveform",
            description="Fault waveform overview",
            level=ScreenLevel.CAVITY,
            path="$EDM/llrf/rf_srf_wf_fault_overview.edl",
        ),
        EdmScreen(
            name="prl-rack",
            description="PRL waveforms for a rack",
            level=ScreenLevel.RACK,
            path="$EDM/llrf/rf_srf_wf_prl_rack.edl",
            extra_macros=(
                "SELTAB=8,SELCHAR=3,FWD=FWD,REV=REV,"
                "PRLDESC=PRL Readout,ACQFILE=rf_srf_wf_prl_acq_cm"
            ),
        ),
        EdmScreen(
            name="freqscan",
            description="Frequency scan for a rack",
            level=ScreenLevel.RACK,
            # tuning_gui.py hardcodes /usr/local/lcls/tools/edm/display/llrf/
            # for this screen. The $EDM path opened the same screen on
            # lcls-srv01 (checked 2026-10-19).
            path="$EDM/llrf/rf_srf_freq_scan_rack{rack}.edl",
        ),
        EdmScreen(
            name="cryo",
            description="Cryomodule cryo screen",
            level=ScreenLevel.CRYOMODULE,
            path="$EDM/cryo/cryo_cryomodule.edl",
            cryo_macros=True,
        ),
        EdmScreen(
            name="cryo-all",
            description="Cryo system overview",
            level=ScreenLevel.GLOBAL,
            path="$EDM/cryo/cryo_system_all.edl",
        ),
        EdmScreen(
            name="unit-tests",
            description="All CM unit tests",
            level=ScreenLevel.GLOBAL,
            path="$EDM/llrf/rf_srf_cavity_unit_all.edl",
        ),
    ]
}


def resolve_tab(tab: str, names: Optional[Dict[str, int]] = None) -> int:
    """Turn a ``--tab`` or ``--char`` value (a number, or a name in
    ``names``) into a number. ``names`` defaults to CAVITY_TABS.
    Raises ValueError for anything else."""
    if names is None:
        names = CAVITY_TABS
    if tab.isdigit():
        return int(tab)
    try:
        return names[tab.lower()]
    except KeyError:
        known = ", ".join(names) or "none yet"
        raise ValueError(
            f"Unknown tab {tab!r}. Use a number or one of: {known}"
        ) from None


def screen_path_and_macros(
    screen: EdmScreen,
    cryomodule: Optional[str] = None,
    rack: Optional[str] = None,
    cavity: Optional[int] = None,
    tab: Optional[int] = None,
    char: Optional[int] = None,
) -> tuple[str, str]:
    """Return the ``.edl`` path (``$EDM`` not yet expanded) and the macro
    string for one screen.

    ``cryomodule`` is a name like "02" or "H1", ``rack`` is "A" or "B",
    ``cavity`` is 1-8. Which of them are needed depends on
    ``screen.level``. Raises ValueError if one is missing. ``tab`` and
    ``char`` are the SELTAB and SELCHAR numbers, used only by screens with
    tabs (default 0 and CAVITY_MAIN_SELCHAR).
    """
    if screen.level is ScreenLevel.GLOBAL:
        return screen.path, screen.extra_macros

    if cryomodule is None:
        raise ValueError(f"'{screen.name}' needs a cryomodule")
    cm_obj = MACHINE.cryomodules[cryomodule]

    if screen.level is ScreenLevel.CRYOMODULE:
        # Any cavity works for the cryo macros: they only use the CM name
        # and linac name.
        cav_obj = cm_obj.cavities[1]
    elif screen.level is ScreenLevel.RACK:
        if rack is None:
            raise ValueError(f"'{screen.name}' needs a rack (A or B)")
        rack_obj = cm_obj.rack_a if rack == "A" else cm_obj.rack_b
        # Rack screens take one cavity's macros, the same as the tuning
        # GUI's rack EDM button (first cavity in the rack).
        cav_obj = list(rack_obj.cavities.values())[0]
    else:
        if cavity is None:
            raise ValueError(f"'{screen.name}' needs a cavity (1-8)")
        cav_obj = cm_obj.cavities[cavity]

    path = screen.path.format(
        cm_or_hl="hl" if cm_obj.is_harmonic_linearizer else "cm",
        rack=cav_obj.rack.rack_name,
    )

    macros = (
        cav_obj.cryo_edm_macro_string
        if screen.cryo_macros
        else cav_obj.edm_macro_string
    )
    extra = screen.extra_macros
    if screen.has_tabs:
        seltab = 0 if tab is None else tab
        selchar = CAVITY_MAIN_SELCHAR if char is None else char
        extra = f"SELTAB={seltab},SELCHAR={selchar}"
    if extra:
        macros = f"{macros},{extra}"
    return path, macros


def edm_command(path: str, macros: str) -> List[str]:
    """Build the ``edm`` command line.

    ``-x`` opens the screen in execute mode, as the buttons do. ``-eolc``
    makes the edm process exit when its last window closes, so closing the
    screen ends the process. The buttons instead share one ``edm -server``
    process; a standalone command has no server to share.
    """
    # edmbutton passes "$EDM/..." to edm unexpanded. Expanding it here means
    # the command does not depend on whether edm expands it itself.
    command = ["edm", "-x", "-eolc"]
    if macros:
        command += ["-m", macros]
    command.append(os.path.expandvars(path))
    return command


def open_screen(command: List[str]) -> subprocess.Popen:
    """Start ``edm`` in its own session, so it keeps running after the
    terminal that started it closes."""
    return subprocess.Popen(command, start_new_session=True)
