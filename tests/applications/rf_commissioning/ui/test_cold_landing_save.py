"""Tests for the cold-landing save dialog.

Named ..._save rather than ..._dialog on purpose: tests/conftest.py replaces
builtins.open with a mock for any path containing "log", so a file called
test_cold_landing_dialog.py is read as empty and silently collects zero tests.

The dialog is the only route to DF_COLD, so what it returns has to be exactly
what gets written to both the PV and the record.
"""

import pytest

from sc_linac_physics.applications.rf_commissioning.ui.cold_landing_dialog import (
    ColdLandingDialog,
    SOURCE_ENTERED,
    SOURCE_LIVE,
    SOURCE_MEASURED,
    measured_text,
)


@pytest.fixture
def dialog(qtbot):
    def _make(measured=3739.0, live=3800.0):
        d = ColdLandingDialog(measured, live)
        qtbot.addWidget(d)
        return d

    return _make


def test_defaults_to_the_measured_value(dialog):
    """The common case is the value Stage 1 just measured."""
    d = dialog()

    choice = d.choice()

    assert choice.source == SOURCE_MEASURED
    assert choice.value_hz == 3739.0


def test_live_reading_is_selectable(dialog):
    d = dialog()
    d._live_radio.setChecked(True)

    choice = d.choice()

    assert choice.source == SOURCE_LIVE
    assert choice.value_hz == 3800.0


def test_entered_value_requires_a_justification(dialog):
    """Save stays disabled until an entered value explains itself."""
    d = dialog()
    d._entered_radio.setChecked(True)
    d._refresh_enabled()

    assert d._buttons.button(d._buttons.Save).isEnabled() is False
    assert "justification" in d._warning.text().lower()

    d._justification.setPlainText("cold landing measured at JLab during VTS")

    assert d._buttons.button(d._buttons.Save).isEnabled() is True
    assert d._warning.text() == ""


def test_entered_value_carries_its_justification(dialog):
    d = dialog()
    d._entered_radio.setChecked(True)
    d._value_box.setValue(1234.0)
    d._justification.setPlainText("from partner lab")

    choice = d.choice()

    assert choice.source == SOURCE_ENTERED
    assert choice.value_hz == 1234.0
    assert choice.justification == "from partner lab"


def test_whitespace_is_not_a_justification(dialog):
    d = dialog()
    d._entered_radio.setChecked(True)
    d._justification.setPlainText("   \n  ")
    d._refresh_enabled()

    assert d._buttons.button(d._buttons.Save).isEnabled() is False


def test_falls_back_to_entry_when_nothing_was_measured(dialog):
    """A cavity with no measurement and no live reading can still be set."""
    d = dialog(measured=None, live=None)

    assert d._measured_radio.isEnabled() is False
    assert d._live_radio.isEnabled() is False
    assert d._entered_radio.isChecked() is True


def test_provenance_names_the_source(dialog):
    d = dialog()
    assert "measured by Stage 1" in d.choice().provenance()

    d._entered_radio.setChecked(True)
    d._value_box.setValue(50.0)
    d._justification.setPlainText("JLab value")
    assert "JLab value" in d.choice().provenance()


def test_measured_text_handles_a_missing_value():
    assert measured_text(None) == "not available"
    assert measured_text(3739.0) == "3739 Hz"
