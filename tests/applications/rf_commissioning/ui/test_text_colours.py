"""Text stays readable under a light palette.

The phase styles paint dark backgrounds. If a style leaves out `color:`, the
text colour comes from the platform palette: white on a dark desktop theme,
black on a light one. These tests force Fusion's light palette, which is what
offscreen Qt gives anyway, so a missing colour shows up as black on near-black.

Qt folds a polished widget's stylesheet `color` and `background` into its
palette, so the effective colours can be read back without grabbing pixels.
"""

from unittest.mock import patch

import pytest
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QLabel, QStyleFactory

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    TEXT_PRIMARY,
)

# WCAG AA for body text, the same bar theme.py sets for its text tokens.
MIN_CONTRAST = 4.5


def _luminance(color: QColor) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def _contrast(a: QColor, b: QColor) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.fixture
def light_palette(qapp):
    original = QApplication.palette()
    qapp.setPalette(QStyleFactory.create("Fusion").standardPalette())
    yield
    qapp.setPalette(original)


def _styled_labels(widget):
    """Labels whose own stylesheet paints an opaque background."""
    for label in widget.findChildren(QLabel):
        if "background" not in label.styleSheet():
            continue
        if label.palette().color(QPalette.Window).alpha() < 255:
            continue
        yield label


@pytest.mark.parametrize(
    "phase", [CommissioningPhase.CAVITY_CHAR, CommissioningPhase.PIEZO_PRE_RF]
)
def test_readouts_readable_on_a_bare_phase_display(
    qtbot, tmp_path, light_palette, phase
):
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )

    session = CommissioningSession(db_path=str(tmp_path / "c.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        display = PHASE_DISPLAY_MAP[phase](session=session)
    qtbot.addWidget(display)
    display.show()
    qtbot.waitExposed(display)

    labels = list(_styled_labels(display))
    assert labels, "expected styled readout labels on the display"
    for label in labels:
        pal = label.palette()
        text, bg = pal.color(QPalette.WindowText), pal.color(QPalette.Window)
        assert _contrast(text, bg) >= MIN_CONTRAST, (
            f"{type(label).__name__} {label.objectName()!r}: "
            f"{text.name()} on {bg.name()}"
        )


def test_container_gives_plain_labels_a_light_text_colour(
    qtbot, tmp_path, light_palette
):
    """The tab pane paints BG_DEEP, so plain labels need light text."""
    from sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen import (  # noqa: E501
        MultiPhaseCommissioningDisplay,
    )

    session = CommissioningSession(db_path=str(tmp_path / "c.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        display = MultiPhaseCommissioningDisplay(
            session=session, refresh_interval_ms=0
        )
    qtbot.addWidget(display)
    display.show()
    qtbot.waitExposed(display)

    page = display.tabs.widget(0)
    plain = [w for w in page.findChildren(QLabel) if not w.styleSheet()]
    assert plain, "expected plain form labels on the first phase page"
    for label in plain:
        assert label.palette().color(QPalette.WindowText) == QColor(
            TEXT_PRIMARY
        ), label.text()
