"""PV wiring helpers for Piezo Pre-RF controller."""

from __future__ import annotations

from typing import Optional

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import get_linac_for_cryomodule


def resolve_cavity_selection(
    view,
    cryomodule: Optional[str],
    cavity_number: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
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
            if (
                selected_cm == "Select CM..."
                or selected_cavity == "Select Cav..."
            ):
                return None, None
            return selected_cm, selected_cavity
        parent = parent.parent()

    return None, None


def get_piezo_from_selection(
    machine: Optional[Machine],
    cryomodule: str,
    cavity_number: str,
) -> tuple[CommissioningPiezo, int, int, Machine]:
    """Return piezo object, parsed CM/CAV values, and resolved machine."""
    cav = int(cavity_number)
    cm = int(cryomodule)

    active_machine = machine or Machine(piezo_class=CommissioningPiezo)
    cm_str = f"{cm:02d}"
    cryomodule_obj = active_machine.cryomodules[cm_str]
    cavity = cryomodule_obj.cavities[cav]
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
    cm: int,
    cav: int,
) -> str:
    """Format user-facing message describing active PV source."""
    linac = get_linac_for_cryomodule(cryomodule)
    cavity_display_name = (
        f"{linac}_CM{cryomodule}_CAV{cavity_number}"
        if linac
        else f"CM{cryomodule}_CAV{cavity_number}"
    )
    return f"PVs updated for {cavity_display_name} (CM{cm:02d} Cav{cav})"
