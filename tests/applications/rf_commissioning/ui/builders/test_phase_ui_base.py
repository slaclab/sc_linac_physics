"""Tests for the RF commissioning PhaseUIBase builder."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QPushButton

from sc_linac_physics.applications.rf_commissioning.ui.builders.base import (
    PhaseUIBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.styles import (
    LOCAL_LABEL_STYLE,
)


@pytest.fixture
def callbacks():
    return {
        "on_run_automated_test": Mock(),
        "on_pause_test": Mock(),
        "on_abort_test": Mock(),
        "on_toggle_step_mode": Mock(),
        "on_next_step": Mock(),
    }


@pytest.fixture
def base(callbacks):
    return PhaseUIBase(parent=SimpleNamespace(), callbacks=callbacks)


def test_register_stores_widget_and_returns_same_instance(base):
    widget = QLabel("value")

    registered = base._register("my_widget", widget)

    assert registered is widget
    assert base.widgets["my_widget"] is widget


def test_connect_wires_button_callback(callbacks):
    base = PhaseUIBase(parent=SimpleNamespace(), callbacks=callbacks)
    button = QPushButton("Run")

    base._connect(button, "on_run_automated_test")
    button.click()

    callbacks["on_run_automated_test"].assert_called_once()


def test_connect_missing_callback_is_safe_noop(callbacks):
    base = PhaseUIBase(parent=SimpleNamespace(), callbacks=callbacks)
    button = QPushButton("Run")

    base._connect(button, "missing_callback")
    button.click()

    for callback in callbacks.values():
        callback.assert_not_called()


def test_build_main_toolbar_registers_expected_widgets_and_defaults(base):
    wrapper = base._build_main_toolbar()

    assert wrapper.count() == 1
    assert base.widgets["run_button"].isEnabled() is True
    assert base.widgets["pause_button"].isEnabled() is False
    assert base.widgets["abort_button"].isEnabled() is False
    assert base.widgets["next_step_btn"].isEnabled() is False
    assert base.widgets["status_indicator"].text() == "● READY"
    assert base.widgets["timestamp_label"].text() == "--:--:--"


@pytest.mark.parametrize(
    "state,run_enabled,run_text,pause_enabled,abort_enabled,status_text",
    [
        ("idle", True, "▶ Start Test", False, False, "● READY"),
        ("running", False, "▶ Start Test", True, True, "● RUNNING"),
        ("paused", True, "▶ Resume", False, True, "● PAUSED"),
        ("complete", True, "▶ Start Test", False, False, "✓ COMPLETE"),
        ("error", True, "▶ Retry", False, False, "✗ ERROR"),
    ],
)
def test_update_toolbar_state_sets_buttons_and_status(
    base,
    state,
    run_enabled,
    run_text,
    pause_enabled,
    abort_enabled,
    status_text,
):
    base._build_main_toolbar()

    base.update_toolbar_state(state)

    assert base.widgets["run_button"].isEnabled() is run_enabled
    assert base.widgets["run_button"].text() == run_text
    assert base.widgets["pause_button"].isEnabled() is pause_enabled
    assert base.widgets["abort_button"].isEnabled() is abort_enabled
    assert base.widgets["status_indicator"].text() == status_text


def test_build_history_creates_readonly_bounded_text_widget(base):
    group = base._build_history()
    history_text = base.widgets["history_text"]

    assert group.title() == "Phase History"
    assert history_text.isReadOnly() is True
    assert history_text.minimumHeight() == 60
    assert history_text.maximumHeight() == 180


def test_build_basic_results_section_registers_labels(base):
    group = base._build_basic_results_section("My Phase")

    assert group.title() == "My Phase - Status && Results"
    assert base.widgets["local_current_step"].text() == "-"
    assert base.widgets["local_phase_status"].text() == "-"


def test_make_local_label_applies_default_style_and_alignment(base):
    label = base._make_local_label("hello")

    assert label.text() == "hello"
    assert label.styleSheet() == LOCAL_LABEL_STYLE
    assert label.alignment() == Qt.AlignCenter


def test_build_stored_data_section_registers_core_and_custom_widgets(base):
    group = base._build_stored_data_section(
        fields=[("Field A", "local_field_a"), ("Field B", "local_field_b")]
    )

    assert group.title() == "Stored Data"
    assert "local_progress_bar" in base.widgets
    assert "local_stored_status" in base.widgets
    assert "local_field_a" in base.widgets
    assert "local_field_b" in base.widgets
    assert "local_stored_timestamp" in base.widgets
    assert "local_stored_notes" in base.widgets
    assert base.widgets["local_stored_notes"].wordWrap() is True


def test_get_parent_stored_data_fields_maps_spec_objects():
    parent = SimpleNamespace(
        get_phase_stored_field_specs=lambda: [
            SimpleNamespace(label="Amplitude", widget_name="amp_widget"),
            SimpleNamespace(label="Phase", widget_name="phase_widget"),
        ]
    )
    base = PhaseUIBase(parent=parent)

    fields = base._get_parent_stored_data_fields()

    assert fields == [("Amplitude", "amp_widget"), ("Phase", "phase_widget")]


def test_get_parent_stored_data_fields_returns_empty_without_parent_method():
    base = PhaseUIBase(parent=SimpleNamespace())

    assert base._get_parent_stored_data_fields() == []
