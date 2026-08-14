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

# ── Font sizes ─────────────────────────────────────────────────────────────────

# The phase tab bar is the primary navigation affordance and is read from
# operator-console viewing distance, so it is sized above the 11px used for
# dense in-panel labels.  Operator feedback on PR #270 was that the tab text
# was too small to scan comfortably.
FONT_SIZE_TAB = "13px"

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
#
# Contrast targets: every token below that is used for *readable* text clears
# WCAG AA (4.5:1) against the darkest surface it is drawn on (BG_PANEL,
# #242830).  Ratios in the comments are measured against BG_PANEL, which is the
# worst case — BG_DEEP and BG_INSET are darker and therefore score higher.
#
# This matters because operator feedback on PR #270 (Janice Nelson, AOSD) was
# that grey-on-dark-grey text — completed and inactive phase tabs in
# particular — was hard to read on the console.  The fix is applied here rather
# than at the call sites so that every commissioning phase display inherits it.

TEXT_PRIMARY = "#c9cdd6"  # 9.28:1
TEXT_SECONDARY = "#a6b0c2"  # 6.76:1 (was #8b96a8, 4.94:1 — only just passing)
TEXT_MUTED = "#8e99ad"  # 5.14:1 (was #5a6278, 2.43:1 — failed AA)

# Genuinely disabled controls only.  WCAG exempts disabled elements from the
# contrast minimum, and keeping this below TEXT_MUTED is what preserves the
# "this is not actionable" signal.  Note that *disabled tabs* deliberately do
# not use this token — they use TEXT_MUTED, because operators still need to
# read which phase a locked-out tab represents.
TEXT_DISABLED = "#7a8598"  # 3.97:1

# ── Semantic colors ────────────────────────────────────────────────────────────

COLOR_SUCCESS = "#4ab782"  # 5.90:1
COLOR_PRIMARY = "#97a5e8"  # 6.24:1 (was #7b8cde, 4.68:1 — marginal)
COLOR_WARNING = "#d4956a"  # 5.84:1
COLOR_ERROR = "#e0796e"  # 5.02:1 (was #c0544a, 3.24:1 — failed AA)
COLOR_DISABLED = "#353a45"  # borders/fills only, never text

# Accent colors for label left-border stripes
ACCENT_PV = "#8b96c4"
ACCENT_LOCAL = "#c4956b"

# Translucent tinted backgrounds for badge/chip use
COLOR_SUCCESS_BG = "rgba(74, 183, 130, 0.12)"
COLOR_SUCCESS_BORDER = "rgba(74, 183, 130, 0.25)"
COLOR_WARNING_BG = "rgba(212, 149, 106, 0.15)"
COLOR_PRIMARY_BG = "rgba(151, 165, 232, 0.12)"
COLOR_PRIMARY_BORDER = "#3d4560"

# Text colors for status labels
COLOR_STATUS_PASS = "#6ebf8e"
COLOR_STATUS_FAIL = "#d47070"
COLOR_STATUS_INCOMPLETE = "#d4af70"

# ── Shape ──────────────────────────────────────────────────────────────────────

RADIUS_LG = "8px"
RADIUS_MD = "6px"
RADIUS_SM = "5px"
