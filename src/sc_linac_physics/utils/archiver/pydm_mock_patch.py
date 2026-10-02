"""
Auto-attach the mock archiver to every PyDMArchiverTimePlot curve.

When SC_ARCHIVER_MOCK=1, this wraps PyDMArchiverTimePlot.addYChannel so each
curve's archive_data_request_signal is fed by the mock generator instead of
PyDM's HTTP plugin. No display code (plot.py / embeddable_plots.py) changes.

Call install_mock_archiver_patch() ONCE, early, before any plot is built.
Idempotent and a no-op unless SC_ARCHIVER_MOCK=1.
"""

from __future__ import annotations
from qtpy.QtCore import QTimer

import logging
import os
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)

_PATCHED = False
_LIVE_TIMER = None
_LIVE_CURVES = []


def _mock_enabled() -> bool:
    return os.getenv("SC_ARCHIVER_MOCK") == "1"


def _wire_curve(curve) -> None:
    """Connect one curve's archive request signal to the mock generator."""
    pv = getattr(curve, "address", None)
    if not pv:
        return
    if getattr(curve, "_mock_wired", False):
        return  # idempotent — never double-connect

    def _feed(min_x, max_x, _cmd=None, c=curve, pv=pv):
        try:
            from sc_linac_physics.utils.archiver import get_values_over_time_range

            start = datetime.fromtimestamp(min_x, tz=timezone.utc)
            end = datetime.fromtimestamp(max_x, tz=timezone.utc)
            handler = get_values_over_time_range([pv], start, end)[pv]

            ts = np.array([t.timestamp() for t in handler.timestamps], dtype=float)
            try:
                vals = np.array([float(v) for v in handler.values], dtype=float)
            except (TypeError, ValueError):
                return  # non-numeric PV (e.g. CUDSTATUS) — not plottable

            if ts.size == 0:
                return

            buf = int(getattr(c, "_archiveBufferSize", 8000))
            max_points = max(buf - 100, 100)
            if ts.size > max_points:
                idx = np.linspace(0, ts.size - 1, max_points).astype(int)
                ts, vals = ts[idx], vals[idx]

            c.receiveArchiveData(np.array([ts, vals]))
        except Exception as e:  # never break the display
            logger.warning("Mock archive feed failed for %s: %s", pv, e)

    try:
        curve.archive_data_request_signal.connect(_feed)
        curve._mock_wired = True
        _LIVE_CURVES.append(curve)
        _start_live_driver()
    except Exception as e:
        logger.warning("Could not wire mock for %s: %s", pv, e)


def install_mock_archiver_patch() -> None:
    """Wrap PyDMArchiverTimePlot.addYChannel so new curves auto-wire to mock."""
    global _PATCHED
    if _PATCHED or not _mock_enabled():
        return

    try:
        from pydm.widgets import PyDMArchiverTimePlot
    except Exception as e:  # PyDM unavailable (e.g. pure-backend context)
        logger.debug("PyDM not available; mock patch skipped: %s", e)
        return

    original_add = PyDMArchiverTimePlot.addYChannel

    def patched_add(self, *args, **kwargs):
        curve = original_add(self, *args, **kwargs)
        target = curve
        if target is None:  # some PyDM versions return None
            try:
                items = self.getPlotItem().curves
                target = items[-1] if items else None
            except Exception:
                target = None
        if target is not None:
            _wire_curve(target)
        return curve

    PyDMArchiverTimePlot.addYChannel = patched_add
    _PATCHED = True
    logger.info("Mock archiver patch installed (SC_ARCHIVER_MOCK=1)")

def _start_live_driver(period_ms: int = 1000) -> None:
    """Push one fresh mock sample into each wired curve every period_ms."""
    global _LIVE_TIMER
    if _LIVE_TIMER is not None:
        return
    _LIVE_TIMER = QTimer()
    _LIVE_TIMER.setInterval(period_ms)
    _LIVE_TIMER.timeout.connect(_tick_live)
    _LIVE_TIMER.start()

def _tick_live() -> None:
    from sc_linac_physics.utils.archiver import get_values_over_time_range
    now = datetime.now(timezone.utc)
    # a 2-second window; take the last sample as "the current value"
    start = now - __import__("datetime").timedelta(seconds=2)
    for c in list(_LIVE_CURVES):
        pv = getattr(c, "address", None)
        if not pv:
            continue
        try:
            handler = get_values_over_time_range([pv], start, now)[pv]
            if not handler.values:
                continue
            v = handler.values[-1]
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue  # non-numeric PV
            # PyDM live path: update the curve's latest value + timestamp
            if hasattr(c, "receiveNewValue"):
                c.receiveNewValue(v)
            # ensure the plot advances its time axis
            plot = getattr(c, "plot_widget", None) or getattr(c, "_plot", None)
        except Exception as e:
            logger.debug("live tick failed for %s: %s", pv, e)