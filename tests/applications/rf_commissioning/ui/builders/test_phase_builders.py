"""Tests for RF commissioning phase-specific UI builders."""

from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.ui.builders.phase_builders import (
    CavityCharUI,
    FrequencyTuningUI,
    GenericPhaseUI,
    HighPowerUI,
    PiezoPreRFUI,
    PiezoWithRFUI,
    SSACharUI,
)


class _ParentWidget(QWidget):
    def __init__(self, specs=None, phase_name=None):
        super().__init__()
        self._specs = specs or []
        if phase_name is not None:
            self.PHASE_NAME = phase_name

    def get_phase_stored_field_specs(self):
        return self._specs


def _mount(layout):
    host = QWidget()
    host.setLayout(layout)
    return host


def test_piezo_build_creates_two_panel_layout_and_sections():
    parent = _ParentWidget(
        specs=[SimpleNamespace(label="Operator", widget_name="stored_operator")]
    )
    ui = PiezoPreRFUI(parent=parent)

    layout = ui.build()
    host = _mount(layout)

    assert layout.count() == 2
    titles = {group.title() for group in host.findChildren(QGroupBox)}
    assert "Piezo Tuner Pre-RF Test" in titles
    assert "Phase History" in titles
    assert "Piezo Pre-RF - Status && Results" in titles
    assert "Stored Data" in titles


def test_piezo_controls_registers_widgets_and_default_values():
    ui = PiezoPreRFUI(parent=_ParentWidget())

    group = ui._build_piezo_controls()

    assert group.title() == "Piezo Tuner Pre-RF Test"
    assert ui.widgets["offset_spinbox"].minimum() == -100
    assert ui.widgets["offset_spinbox"].maximum() == 100
    assert ui.widgets["offset_spinbox"].value() == 0
    assert ui.widgets["voltage_spinbox"].minimum() == 0
    assert ui.widgets["voltage_spinbox"].maximum() == 100
    assert ui.widgets["voltage_spinbox"].value() == 17


def test_setup_row_populates_cm_and_cavity_ranges():
    ui = PiezoPreRFUI(parent=_ParentWidget())

    wrapper = ui._build_setup_row()

    assert isinstance(wrapper, QHBoxLayout)
    assert ui.widgets["cm_spinbox"].count() == 20
    assert ui.widgets["cav_spinbox"].count() == 8
    assert ui.widgets["cm_spinbox"].currentText() == "1"
    assert ui.widgets["cav_spinbox"].currentText() == "1"


def test_combined_results_section_registers_local_and_pv_widgets():
    ui = PiezoPreRFUI(parent=_ParentWidget())

    group = ui._build_combined_results_section()

    assert group.title() == "Piezo Pre-RF - Status && Results"
    assert ui.widgets["local_current_step"].text() == "-"
    assert ui.widgets["local_phase_status"].text() == "-"
    assert ui.widgets["pv_cha_cap"].showUnits is True
    assert ui.widgets["pv_chb_cap"].showUnits is True


def test_piezo_build_registers_stored_fields_from_parent_specs():
    parent = _ParentWidget(
        specs=[
            SimpleNamespace(label="Operator", widget_name="stored_operator"),
            SimpleNamespace(label="Amplitude", widget_name="stored_amp"),
        ]
    )
    ui = PiezoPreRFUI(parent=parent)

    _mount(ui.build())

    assert "stored_operator" in ui.widgets
    assert "stored_amp" in ui.widgets


@pytest.mark.parametrize(
    "ui_cls,phase_title",
    [
        (FrequencyTuningUI, "Frequency Tuning"),
        (SSACharUI, "SSA Characterization"),
        (CavityCharUI, "Cavity Characterization"),
        (PiezoWithRFUI, "Piezo with RF"),
        (HighPowerUI, "High Power Ramp"),
    ],
)
def test_placeholder_builders_use_standard_layout_and_phase_title(
    ui_cls, phase_title
):
    parent = _ParentWidget(
        specs=[SimpleNamespace(label="Tag", widget_name="stored_tag")]
    )
    ui = ui_cls(parent=parent)

    layout = ui.build()
    host = _mount(layout)

    assert layout.count() == 2
    titles = {group.title() for group in host.findChildren(QGroupBox)}
    assert "Phase History" in titles
    assert f"{phase_title} - Status && Results" in titles
    assert "Stored Data" in titles
    assert "stored_tag" in ui.widgets


def test_generic_phase_title_uses_parent_phase_name():
    ui = GenericPhaseUI(parent=_ParentWidget(phase_name="Custom Phase"))

    assert ui.PHASE_TITLE == "Custom Phase"


def test_generic_phase_title_falls_back_to_default():
    ui = GenericPhaseUI(parent=_ParentWidget())

    assert ui.PHASE_TITLE == "Phase"
