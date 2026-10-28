"""PV wiring helpers for Piezo Pre-RF controller."""

from __future__ import annotations


from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    get_linac_for_cryomodule,
)


def cryomodule_key(cryomodule) -> str:
    """Return the Machine.cryomodules key for a cryomodule selection.

    Numbered cryomodules are zero-padded ("2" -> "02"); the harmonic
    linearizers keep their names ("H1", "H2"). Raises ValueError for
    anything else.
    """
    name = str(cryomodule).strip()
    key = f"{int(name):02d}" if name.isdigit() else name
    if key not in ALL_CRYOMODULES:
        raise ValueError(f"unknown cryomodule {cryomodule!r}")
    return key


def resolve_cavity_selection(
    view,
    cryomodule: str | None,
    cavity_number: str | None,
) -> tuple[str | None, str | None]:
    """Resolve cavity selection from explicit args or parent dropdowns."""
    if cryomodule is not None and cavity_number is not None:
        return cryomodule, cavity_number

    parent = view.parent()
    while parent:
        if hasattr(parent, "cryomodule_combo") and hasattr(
            parent, "cavity_combo"
        ):
            selected_cm = parent.cryomodule_combo.currentText()
            selected_cavity = parent.cavity_combo.currentText()
            if selected_cm == "..." or selected_cavity == "...":
                return None, None
            return selected_cm, selected_cavity
        parent = parent.parent()

    return None, None


def cavity_number_from_short_name(short_name) -> int:
    """Return the cavity number from a CommissioningRecord.short_cavity_name.

    short_cavity_name is "{cryomodule}-{cavity_number}": "02-3" -> 3,
    "H1-3" -> 3. Raises ValueError for anything else rather than guessing a
    cavity, since the caller runs the phase on the cavity this returns.
    """
    _, sep, cavity = str(short_name).rpartition("-")
    if not sep:
        raise ValueError(f"not a short cavity name: {short_name!r}")
    return int(cavity)


def get_piezo_from_selection(
    machine: Machine | None,
    cryomodule: str,
    cavity_number: str,
) -> tuple[CommissioningPiezo, str, int, Machine]:
    """Return piezo object, cryomodule key, cavity number, and machine."""
    cav = int(cavity_number)
    cm = cryomodule_key(cryomodule)

    active_machine = machine or Machine(piezo_class=CommissioningPiezo)
    cavity = active_machine.cryomodules[cm].cavities[cav]
    return cavity.piezo, cm, cav, active_machine


def build_pv_mapping(view, piezo: CommissioningPiezo) -> dict:
    """Build widget-to-PV mapping for Piezo Pre-RF display."""
    pv_mapping = {
        view.pv_overall: piezo.prerf_test_status_pv,
        view.pv_cha_status: piezo.prerf_cha_status_pv,
        view.pv_chb_status: piezo.prerf_chb_status_pv,
        view.pv_cha_cap: piezo.capacitance_a_pv,
        view.pv_chb_cap: piezo.capacitance_b_pv,
    }

    optional_mappings = [
        ("pydm_enable_ctrl", piezo.enable_pv),
        ("pydm_enable_stat", piezo.enable_stat_pv),
        ("pydm_mode_ctrl", piezo.feedback_control_pv),
        ("pydm_mode_stat", piezo.feedback_stat_pv),
    ]
    for widget_name, pv_addr in optional_mappings:
        if hasattr(view, widget_name):
            pv_mapping[getattr(view, widget_name)] = pv_addr

    return pv_mapping


def apply_pv_mapping(pv_mapping: dict) -> None:
    """Apply EPICS channel addresses to mapped widgets."""
    for widget, pv_addr in pv_mapping.items():
        widget.channel = f"ca://{pv_addr}"


def format_pv_update_message(
    cryomodule: str,
    cavity_number: str,
    cm: str,
    cav: int,
) -> str:
    """Format user-facing message describing active PV source.

    cm is a cryomodule key from cryomodule_key(): "02", "H1".
    """
    linac = get_linac_for_cryomodule(cryomodule)
    cavity_display_name = (
        f"{linac}_CM{cryomodule}_CAV{cavity_number}"
        if linac
        else f"CM{cryomodule}_CAV{cavity_number}"
    )
    return f"PVs updated for {cavity_display_name} (CM{cm} Cav{cav})"
