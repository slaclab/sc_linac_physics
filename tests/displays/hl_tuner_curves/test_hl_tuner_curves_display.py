"""Tests for the HL tuner curve viewer; no archiver."""

from unittest.mock import patch

import pandas as pd
import pytest
from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QApplication

from sc_linac_physics.displays.hl_tuner_curves import (
    hl_tuner_curves_display as D,
)
from sc_linac_physics.displays.hl_tuner_curves import runs as R

T0 = pd.Timestamp("2026-03-01 12:00")


@pytest.fixture(autouse=True)
def flush_deferred_deletes():
    """Deliver qtbot's deleteLater() inside this test (see test_cryo_signals)."""
    yield
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture
def display(qtbot):
    d = D.HLTunerCurvesDisplay()
    qtbot.addWidget(d)
    return d


class SyncThread:
    """Stands in for threading.Thread: runs the target on start()."""

    def __init__(self, target, args, **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def run_with_ratio(curve, ratio):
    """A run whose segments took `ratio` times the curve's microsteps."""
    lo, hi = -300e3, -200e3
    expected = R._curve_at(curve, hi) - R._curve_at(curve, lo)
    run = R.Run(start=T0, points=[(0, lo), (ratio * expected, hi)])
    run.segments = [(lo, hi, ratio * expected)]
    return run


def test_lists_hl_cavities(display):
    assert display.cavity_combo.count() == 16
    assert display.cavity_combo.itemText(0) == "H1 cav 1"
    assert display.prefix == "ACCL:L1B:H110:"
    assert display.table.rowCount() == 0


def test_fetch_shows_runs_and_flags_ratio(display):
    curve = display.curves[display.prefix]
    runs = [run_with_ratio(curve, 1.0), run_with_ratio(curve, 1.3)]
    with (
        patch.object(D.threading, "Thread", SyncThread),
        patch.object(D.R, "fetch_runs", return_value=runs) as fetch,
    ):
        display.fetch()
    assert fetch.call_args.args[:2] == (display.prefix, display.fetch_start)
    assert display.status.text() == "H1 cav 1: 2 new runs"
    assert display.fetch_button.isEnabled()
    assert display.table.item(0, 2).text() == "1.00"
    assert display.table.item(1, 2).text() == "1.30"
    assert display.table.item(0, 2).toolTip() == ""
    assert "refitting" in display.table.item(1, 2).toolTip()


def test_runs_stay_with_their_cavity(display):
    display._on_runs_ready(display.prefix, [R.Run(start=T0)])
    assert display.table.rowCount() == 1
    assert display.table.item(0, 2).text() == "-"
    display.cavity_combo.setCurrentIndex(1)
    assert display.table.rowCount() == 0


def test_fetch_failure_shows_message(display):
    with (
        patch.object(D.threading, "Thread", SyncThread),
        patch.object(D.R, "fetch_runs", side_effect=RuntimeError("down")),
    ):
        display.fetch()
    assert display.status.text() == "H1 cav 1 fetch failed: down"
    assert display.fetch_button.isEnabled()
