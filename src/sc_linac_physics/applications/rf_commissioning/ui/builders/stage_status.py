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
    COLOR_WARNING,
    COLOR_WARNING_BG,
    RADIUS_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

__all__ = [
    "COLD_LANDING_TOOLTIP_NEEDED",
    "COLD_LANDING_TOOLTIP_SET",
    "PUSH_DF_COLD_ATTENTION",
    "PUSH_DF_COLD_NEUTRAL",
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

# Sizes raised on operator feedback (asked twice): these are the labels read
# during a run, and were among the smallest text on the screen.
# Running and Failed are bold so the eye lands on them without hunting; the two
# settled/neutral states are not, so that "Running" stands out in a column of
# four stage cards.
STAGE_STATUS_STYLE_NOT_STARTED = (
    f"QLabel {{ color: {TEXT_MUTED}; font-size: 11pt; }}"
)
STAGE_STATUS_STYLE_RUNNING = (
    f"QLabel {{ color: {COLOR_PRIMARY}; font-size: 12pt; font-weight: bold; }}"
)
STAGE_STATUS_STYLE_DONE = (
    f"QLabel {{ color: {COLOR_SUCCESS}; font-size: 11pt; font-weight: bold; }}"
)
STAGE_STATUS_STYLE_FAILED = (
    f"QLabel {{ color: {COLOR_ERROR}; font-size: 12pt; font-weight: bold; }}"
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


# The Save Cold Landing Frequency button. It is not an optional extra: Stage 2
# will not move the stepper until DF_COLD holds the agreed value, because tuning
# away destroys the ability to measure the cold landing. An operator reviewing
# the screen read the flat grey button as "we don't always do this", so it wears
# an attention style until the value is committed.
PUSH_DF_COLD_NEUTRAL = f"""
    QPushButton {{
        background-color: #374151; color: {TEXT_PRIMARY};
        font-size: 9pt; padding: 2px 8px;
        border-radius: 3px; border: 1px solid {BORDER};
    }}
    QPushButton:hover {{ background-color: #4b5563; }}
    QPushButton:disabled {{ background-color: #1f2937; color: {TEXT_MUTED}; }}
"""
PUSH_DF_COLD_ATTENTION = f"""
    QPushButton {{
        background-color: {COLOR_WARNING_BG}; color: {COLOR_WARNING};
        font-size: 9pt; font-weight: bold; padding: 2px 8px;
        border-radius: 3px; border: 2px solid {COLOR_WARNING};
    }}
    QPushButton:hover {{ background-color: rgba(212, 149, 106, 0.28); }}
"""

COLD_LANDING_TOOLTIP_NEEDED = (
    "Commit the cavity's resting frequency to the DF_COLD PV.\n\n"
    "Required before Stage 2: moving the stepper makes the cold landing "
    "impossible to measure afterwards, so the reference has to be stored "
    "first.\n\n"
    "You choose which value goes in — the one Stage 1 measured, the current "
    "live detune, or a value entered by hand (a partner-lab measurement, for "
    "example, which needs a justification)."
)
COLD_LANDING_TOOLTIP_SET = (
    "DF_COLD already matches the recorded cold landing. Click to change it — "
    "any new value is stored on the record too, so the two cannot disagree."
)
