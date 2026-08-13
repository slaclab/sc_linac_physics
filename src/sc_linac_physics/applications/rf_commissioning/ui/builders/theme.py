"""Centralized visual theme tokens for the RF commissioning UI."""

import sys

# ── Fonts ──────────────────────────────────────────────────────────────────────

if sys.platform == "darwin":
    MONO_FONT_STACK = (
        "'Menlo', 'Monaco', 'Consolas', 'DejaVu Sans Mono', "
        "'Liberation Mono', 'Noto Sans Mono'"
    )
elif sys.platform.startswith("linux"):
    MONO_FONT_STACK = (
        "'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', "
        "'Consolas', 'Menlo', 'Monaco'"
    )
else:
    MONO_FONT_STACK = (
        "'Consolas', 'DejaVu Sans Mono', 'Liberation Mono', "
        "'Noto Sans Mono', 'Menlo', 'Monaco'"
    )

SANS_FONT_STACK = (
    "system-ui, -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
)

# ── Backgrounds ────────────────────────────────────────────────────────────────

BG_DEEP = "#1c1f26"
BG_PANEL = "#242830"
BG_INTERACTIVE = "#2d3344"
BG_INSET = "#1c2030"
BG_PV = "#1c2030"
BG_LOCAL = "#211d18"

# Status display backgrounds (used in stored-data status labels)
BG_STATUS_PASS = "#1e3020"
BG_STATUS_FAIL = "#2d1a1a"
BG_STATUS_INCOMPLETE = "#2d2415"

# ── Borders ────────────────────────────────────────────────────────────────────

BORDER = "#353a45"
BORDER_EMPHASIS = "#454c5e"

# ── Text ───────────────────────────────────────────────────────────────────────

TEXT_PRIMARY = "#c9cdd6"
TEXT_SECONDARY = "#8b96a8"
TEXT_MUTED = "#5a6278"
TEXT_DISABLED = "#5a6278"

# ── Semantic colors ────────────────────────────────────────────────────────────

COLOR_SUCCESS = "#4ab782"
COLOR_PRIMARY = "#7b8cde"
COLOR_WARNING = "#d4956a"
COLOR_ERROR = "#c0544a"
COLOR_DISABLED = "#353a45"

# Accent colors for label left-border stripes
ACCENT_PV = "#8b96c4"
ACCENT_LOCAL = "#c4956b"

# Translucent tinted backgrounds for badge/chip use
COLOR_SUCCESS_BG = "rgba(74, 183, 130, 0.12)"
COLOR_SUCCESS_BORDER = "rgba(74, 183, 130, 0.25)"
COLOR_WARNING_BG = "rgba(212, 149, 106, 0.15)"
COLOR_PRIMARY_BG = "rgba(123, 140, 222, 0.12)"
COLOR_PRIMARY_BORDER = "#3d4560"

# Text colors for status labels
COLOR_STATUS_PASS = "#6ebf8e"
COLOR_STATUS_FAIL = "#d47070"
COLOR_STATUS_INCOMPLETE = "#d4af70"

# ── Shape ──────────────────────────────────────────────────────────────────────

RADIUS_LG = "8px"
RADIUS_MD = "6px"
RADIUS_SM = "5px"
