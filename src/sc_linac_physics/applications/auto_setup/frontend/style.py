from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)

PAGE_BG = "#0f1825"

LINAC_COLORS = {
    "L0B": "#6688cc",
    "L1B": "#44aaaa",
    "L2B": "#cc9944",
    "L3B": "#cc5588",
    "L4B": "#66bb66",
}

# (bg, border, text) for each linac's ready state
_LINAC_READY_TOKENS = {
    "L0B": ("#182840", "#336699", "#88aadd"),
    "L1B": ("#102828", "#227777", "#55bbbb"),
    "L2B": ("#281e0a", "#996622", "#ccaa55"),
    "L3B": ("#280f1a", "#993355", "#cc6688"),
    "L4B": ("#102010", "#336633", "#66aa66"),
}
CARD_BG = "#182030"
CARD_BORDER = "#2a3a55"
CARD_TEXT = "#a0b0c8"
MUTED_TEXT = "#8090a8"
NOTE_TEXT = "#506080"
ACCENT_BORDER = "#6688cc"
ACCENT_TEXT = "#a8c8f0"

STATUS_READY_BG = "#182a20"
STATUS_READY_BORDER = "#2a5535"
STATUS_READY_TEXT = "#80c8a0"

STATUS_RUNNING_BG = "#2a2015"
STATUS_RUNNING_BORDER = "#5a4520"
STATUS_RUNNING_TEXT = "#e0b070"

STATUS_ERROR_BG = "#2a1520"
STATUS_ERROR_BORDER = "#5a2840"
STATUS_ERROR_TEXT = "#e08090"

STATUS_LOCKED_BG = "#1a1a28"
STATUS_LOCKED_BORDER = "#303050"
STATUS_LOCKED_TEXT = "#7080a0"

_STATUS_TOKENS = {
    STATUS_READY_VALUE: (
        STATUS_READY_BG,
        STATUS_READY_BORDER,
        STATUS_READY_TEXT,
    ),
    STATUS_RUNNING_VALUE: (
        STATUS_RUNNING_BG,
        STATUS_RUNNING_BORDER,
        STATUS_RUNNING_TEXT,
    ),
    STATUS_ERROR_VALUE: (
        STATUS_ERROR_BG,
        STATUS_ERROR_BORDER,
        STATUS_ERROR_TEXT,
    ),
}
_LOCKED_TOKENS = (STATUS_LOCKED_BG, STATUS_LOCKED_BORDER, STATUS_LOCKED_TEXT)
_DEFAULT_TOKENS = (CARD_BG, CARD_BORDER, CARD_TEXT)


def _tokens(status: int, locked: bool):
    if locked:
        return _LOCKED_TOKENS
    return _STATUS_TOKENS.get(status, _DEFAULT_TOKENS)


def step_label_for_progress(progress: int) -> str:
    if progress <= 25:
        return f"SSA Cal · {progress}%"
    elif progress <= 50:
        return f"Auto Tune · {progress}%"
    elif progress <= 70:
        return f"Cavity Char · {progress}%"
    return f"RF Ramp · {progress}%"


def status_icon(status: int) -> str:
    return {
        STATUS_RUNNING_VALUE: "⟳",
        STATUS_ERROR_VALUE: "✗",
        STATUS_READY_VALUE: "●",
    }.get(status, "—")


def status_text_color(status: int, locked: bool = False) -> str:
    return _tokens(status, locked)[2]


def card_stylesheet(status: int, locked: bool = False) -> str:
    bg, border, _ = _tokens(status, locked)
    return (
        f"QFrame {{ background-color: {bg}; border: 2px solid {border}; "
        f"border-radius: 6px; }}"
    )


def button_stylesheet() -> str:
    return (
        f"QPushButton {{ background: {CARD_BG}; color: {CARD_TEXT}; "
        f"border: 1px solid {CARD_BORDER}; border-radius: 4px; "
        f"padding: 3px 10px; font-size: 11px; }}"
        f"QPushButton:hover {{ border-color: {ACCENT_BORDER}; color: {ACCENT_TEXT}; }}"
        f"QPushButton:pressed {{ background: {ACCENT_BORDER}; }}"
        f"QPushButton:checked {{ background: {CARD_BORDER}; }}"
    )


def chip_frame_stylesheet(status: int, locked: bool = False) -> str:
    bg, border, _ = _tokens(status, locked)
    return (
        f"QFrame {{ background-color: {bg}; border: 1px solid {border}; "
        f"border-radius: 3px; }}"
    )


def chip_stylesheet(status: int, locked: bool = False) -> str:
    bg, border, color = _tokens(status, locked)
    return (
        f"background-color: {bg}; border: 1px solid {border}; "
        f"color: {color}; border-radius: 3px; padding: 5px 10px; "
        f"font-size: 11px; font-weight: 700;"
    )


def linac_frame_stylesheet(linac_name: str) -> str:
    """Colored-border QFrame wrapping a linac's CM chips."""
    color = LINAC_COLORS[linac_name]
    return (
        f"QFrame {{ background-color: {CARD_BG}; "
        f"border: 2px solid {color}; border-radius: 4px; }}"
    )


def chip_stylesheet_linac(status: int, locked: bool, linac_name: str) -> str:
    """Like chip_stylesheet but uses the linac's color theme when ready."""
    if locked or status != STATUS_READY_VALUE:
        return chip_stylesheet(status, locked)
    bg, border, color = _LINAC_READY_TOKENS[linac_name]
    return (
        f"background-color: {bg}; border: 1px solid {border}; "
        f"color: {color}; border-radius: 3px; padding: 5px 10px; "
        f"font-size: 11px; font-weight: 700;"
    )


def dot_text(status: int, locked: bool = False) -> str:
    if locked:
        return ""
    return {STATUS_RUNNING_VALUE: "⟳", STATUS_ERROR_VALUE: "✗"}.get(status, "")


def dot_stylesheet(
    status: int, locked: bool = False, font_size: int = 0
) -> str:
    _, border, text_color = _tokens(status, locked)
    fs = f" font-size: {font_size}px;" if font_size > 0 else ""
    return (
        f"background-color: {border}; border-radius: 5px; "
        f"color: {text_color}; font-weight: bold;{fs}"
    )
