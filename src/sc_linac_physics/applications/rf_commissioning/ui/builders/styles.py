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

PV_LABEL_STYLE = (
    f"background: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-size: 11px; border-radius: {RADIUS_SM};"
)

PV_CAP_STYLE = (
    f"background-color: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
)

LOCAL_LABEL_STYLE = (
    f"background: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {BORDER}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM};"
)

LOCAL_CAP_STYLE = (
    f"background-color: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {BORDER}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
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
