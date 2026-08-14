"""Status text and label styles for the frequency tuning stage cards.

Every status pairs a glyph with a word.  Operator feedback on PR #270 (Janice
Nelson, AOSD) was that the glyphs alone were ambiguous — "a triangle means that
step is running and checkmark is done?" — so the word carries the meaning and
the glyph is decoration.  The strings live here, rather than inline at each call
site, so that the UI builder that creates the labels and the controller that
updates them cannot drift apart.
"""

from .theme import (
    BG_INSET,
    BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_PRIMARY_BG,
    COLOR_SUCCESS,
    RADIUS_SM,
    TEXT_MUTED,
)

__all__ = [
    "STAGE_CARD_STYLE_IDLE",
    "STAGE_CARD_STYLE_RUNNING",
    "STAGE_STATUS_DONE",
    "STAGE_STATUS_FAILED",
    "STAGE_STATUS_NOT_STARTED",
    "STAGE_STATUS_RUNNING",
    "STAGE_STATUS_STYLE_DONE",
    "STAGE_STATUS_STYLE_FAILED",
    "STAGE_STATUS_STYLE_NOT_STARTED",
    "STAGE_STATUS_STYLE_RUNNING",
]

STAGE_STATUS_NOT_STARTED = "⬜ Not started"
STAGE_STATUS_RUNNING = "⟳ Running"
STAGE_STATUS_DONE = "✓ Done"
STAGE_STATUS_FAILED = "✗ Failed"

# Running and Failed are bold so the eye lands on them without hunting; the two
# settled/neutral states are not, so that "Running" stands out in a column of
# four stage cards.
STAGE_STATUS_STYLE_NOT_STARTED = (
    f"QLabel {{ color: {TEXT_MUTED}; font-size: 9pt; }}"
)
STAGE_STATUS_STYLE_RUNNING = (
    f"QLabel {{ color: {COLOR_PRIMARY}; font-size: 10pt; font-weight: bold; }}"
)
STAGE_STATUS_STYLE_DONE = (
    f"QLabel {{ color: {COLOR_SUCCESS}; font-size: 9pt; font-weight: bold; }}"
)
STAGE_STATUS_STYLE_FAILED = (
    f"QLabel {{ color: {COLOR_ERROR}; font-size: 10pt; font-weight: bold; }}"
)

# Card chrome for the two states an operator has to tell apart at a glance.
# The running card keeps a highlighted border and tinted fill for as long as its
# Run button is greyed out — the feedback on PR #270 was that once the button
# greys out there is nothing left showing which stage is actually going.
#
# Object-name scoped (`QFrame#stageCard`) so the background and border do not
# cascade onto the card's child labels and buttons when the style is swapped at
# runtime.
STAGE_CARD_STYLE_IDLE = f"""
    QFrame#stageCard {{
        background-color: {BG_INSET};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM};
    }}
"""
STAGE_CARD_STYLE_RUNNING = f"""
    QFrame#stageCard {{
        background-color: {COLOR_PRIMARY_BG};
        border: 2px solid {COLOR_PRIMARY};
        border-radius: {RADIUS_SM};
    }}
"""
