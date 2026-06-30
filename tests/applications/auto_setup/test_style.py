from sc_linac_physics.applications.auto_setup.frontend.style import (
    step_label_for_progress,
    card_stylesheet,
    chip_stylesheet,
    dot_stylesheet,
    status_icon,
    status_text_color,
    STATUS_RUNNING_BORDER,
    STATUS_ERROR_BORDER,
    STATUS_READY_BORDER,
    STATUS_LOCKED_BORDER,
    STATUS_READY_TEXT,
    STATUS_LOCKED_TEXT,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


def test_step_label_boundaries():
    assert step_label_for_progress(0) == "SSA Cal · 0%"
    assert step_label_for_progress(25) == "SSA Cal · 25%"
    assert step_label_for_progress(26) == "Auto Tune · 26%"
    assert step_label_for_progress(50) == "Auto Tune · 50%"
    assert step_label_for_progress(51) == "Cavity Char · 51%"
    assert step_label_for_progress(70) == "Cavity Char · 70%"
    assert step_label_for_progress(71) == "RF Ramp · 71%"
    assert step_label_for_progress(100) == "RF Ramp · 100%"


def test_card_stylesheet_running():
    ss = card_stylesheet(STATUS_RUNNING_VALUE)
    assert STATUS_RUNNING_BORDER in ss


def test_card_stylesheet_error():
    ss = card_stylesheet(STATUS_ERROR_VALUE)
    assert STATUS_ERROR_BORDER in ss


def test_card_stylesheet_ready():
    ss = card_stylesheet(STATUS_READY_VALUE)
    assert STATUS_READY_BORDER in ss


def test_card_stylesheet_locked_overrides_status():
    ss = card_stylesheet(STATUS_READY_VALUE, locked=True)
    assert STATUS_LOCKED_BORDER in ss
    assert STATUS_READY_BORDER not in ss


def test_status_icon_values():
    assert status_icon(STATUS_RUNNING_VALUE) == "⟳"
    assert status_icon(STATUS_ERROR_VALUE) == "✗"
    assert status_icon(STATUS_READY_VALUE) == "●"
    assert status_icon(99) == "—"


def test_chip_stylesheet_ready():
    ss = chip_stylesheet(STATUS_READY_VALUE)
    assert STATUS_READY_BORDER in ss


def test_dot_stylesheet_locked():
    ss = dot_stylesheet(STATUS_READY_VALUE, locked=True)
    assert STATUS_LOCKED_BORDER in ss


def test_status_text_color_ready():
    assert status_text_color(STATUS_READY_VALUE) == STATUS_READY_TEXT


def test_status_text_color_locked_overrides():
    assert (
        status_text_color(STATUS_READY_VALUE, locked=True) == STATUS_LOCKED_TEXT
    )
