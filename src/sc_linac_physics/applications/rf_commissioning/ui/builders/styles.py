"""Shared style constants for RF commissioning UI builders."""

from .theme import (
    ACCENT_LOCAL,
    ACCENT_PV,
    BG_INSET,
    BG_LOCAL,
    BORDER,
    BG_STATUS_FAIL,
    BG_STATUS_INCOMPLETE,
    BG_STATUS_PASS,
    COLOR_STATUS_FAIL,
    COLOR_STATUS_INCOMPLETE,
    COLOR_STATUS_PASS,
    MONO_FONT_STACK,
    RADIUS_SM,
    SANS_FONT_STACK,
    TEXT_PRIMARY,
)

__all__ = [
    "LOCAL_CAP_STYLE",
    "LOCAL_LABEL_STYLE",
    "MONO_FONT_STACK",
    "PV_CAP_STYLE",
    "PV_LABEL_STYLE",
    "SANS_FONT_STACK",
    "STATUS_LABEL_FAIL",
    "STATUS_LABEL_INCOMPLETE",
    "STATUS_LABEL_PASS",
]

# Every style below that sets a dark background also sets its own `color:`.
# Without it the text colour comes from the platform palette. That is white
# under a dark desktop theme but black under a light one (offscreen Qt, and any
# console without a dark theme), which puts black text on near-black. Setting
# it here means a widget is readable wherever it is shown, including outside a
# PhaseDisplayBase page (which sets its own dark page style).
PV_LABEL_STYLE = (
    f"background: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-size: 11px; border-radius: {RADIUS_SM};"
    f" color: {TEXT_PRIMARY};"
)

PV_CAP_STYLE = (
    f"background-color: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
    f" color: {TEXT_PRIMARY};"
)

# 12px, not 11: these carry the live step and phase text in the status bar, which
# an operator reads mid-run from console distance. Raised on operator feedback.
LOCAL_LABEL_STYLE = (
    f"background: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {BORDER}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 12px; border-radius: {RADIUS_SM};"
    f" color: {TEXT_PRIMARY};"
)

LOCAL_CAP_STYLE = (
    f"background-color: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {BORDER}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
    f" color: {TEXT_PRIMARY};"
)

STATUS_LABEL_PASS = (
    f"background: {BG_STATUS_PASS}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_PASS}; font-weight: bold;"
)

STATUS_LABEL_FAIL = (
    f"background: {BG_STATUS_FAIL}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_FAIL}; font-weight: bold;"
)

STATUS_LABEL_INCOMPLETE = (
    f"background: {BG_STATUS_INCOMPLETE}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_INCOMPLETE};"
)
