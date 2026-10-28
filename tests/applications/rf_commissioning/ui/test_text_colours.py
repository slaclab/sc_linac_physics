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
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QRadioButton,
    QStyleFactory,
)

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.stage_status import (  # noqa: E501
    STAGE_CARD_STYLE_IDLE,
    STAGE_CARD_STYLE_RUNNING,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_DEEP,
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


def _assert_readable(widget, text: QColor, bg: QColor) -> None:
    assert _contrast(text, bg) >= MIN_CONTRAST, (
        f"{type(widget).__name__} {widget.objectName()!r}: "
        f"{text.name()} on {bg.name()}"
    )


def _container(qtbot, tmp_path):
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
    return display


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
        _assert_readable(
            label, pal.color(QPalette.WindowText), pal.color(QPalette.Window)
        )


def test_bare_phase_display_paints_a_dark_page(qtbot, tmp_path, light_palette):
    """Shown on its own, the page is dark like it is in the container."""
    from sc_linac_physics.applications.rf_commissioning.ui.displays.cavity_char import (  # noqa: E501
        CavityCharDisplay,
    )

    session = CommissioningSession(db_path=str(tmp_path / "c.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        display = CavityCharDisplay(session=session)
    qtbot.addWidget(display)
    display.show()
    qtbot.waitExposed(display)

    assert display.palette().color(QPalette.Window) == QColor(BG_DEEP)
    plain = [w for w in display.findChildren(QLabel) if not w.styleSheet()]
    assert plain
    for label in plain:
        assert label.palette().color(QPalette.WindowText) == QColor(
            TEXT_PRIMARY
        ), label.text()


def test_container_gives_plain_labels_a_light_text_colour(
    qtbot, tmp_path, light_palette
):
    """The tab pane paints BG_DEEP, so plain labels need light text."""
    display = _container(qtbot, tmp_path)
    page = display.tabs.widget(0)
    plain = [w for w in page.findChildren(QLabel) if not w.styleSheet()]
    assert plain, "expected plain form labels on the first phase page"
    for label in plain:
        assert label.palette().color(QPalette.WindowText) == QColor(
            TEXT_PRIMARY
        ), label.text()


@pytest.mark.parametrize(
    "card_style",
    [STAGE_CARD_STYLE_IDLE, STAGE_CARD_STYLE_RUNNING],
    ids=["idle", "running"],
)
def test_stage_card_captions_readable_in_both_states(
    qtbot, tmp_path, light_palette, card_style
):
    display = _container(qtbot, tmp_path)
    cards = [
        f
        for f in display.tabs.findChildren(QFrame)
        if f.objectName() == "stageCard"
    ]
    assert cards, "expected frequency tuning stage cards"
    for card in cards:
        card.setStyleSheet(card_style)
    QApplication.processEvents()

    for card in cards:
        bg = card.palette().color(QPalette.Window)
        assert bg.alpha() == 255, "card fill must be opaque"
        for label in card.findChildren(QLabel):
            if "background" in label.styleSheet():
                continue
            _assert_readable(
                label, label.palette().color(QPalette.WindowText), bg
            )


def test_dialog_on_a_phase_page_keeps_the_palette_text_colour(
    qtbot, tmp_path, light_palette
):
    """Dialogs inherit the page rule but paint the desktop window colour."""
    from sc_linac_physics.applications.rf_commissioning.ui.cold_landing_dialog import (  # noqa: E501
        ColdLandingDialog,
    )

    display = _container(qtbot, tmp_path)
    dialog = ColdLandingDialog(None, None, parent=display.tabs.widget(0))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    # Some radios are disabled until a value exists, so compare the active
    # colour group: the point is that the page colours did not leak in.
    expected = QApplication.palette().color(
        QPalette.Active, QPalette.WindowText
    )
    radios = dialog.findChildren(QRadioButton)
    assert radios
    for radio in radios:
        colour = radio.palette().color(QPalette.Active, QPalette.WindowText)
        assert colour == expected, radio.text()


def test_tab_strip_right_of_the_last_tab_is_dark(
    qtbot, tmp_path, light_palette
):
    """The tab row past the last tab showed the desktop's white window."""
    display = _container(qtbot, tmp_path)
    display.resize(1500, 900)
    QApplication.processEvents()
    tabs = display.tabs
    bar = tabs.tabBar()
    assert bar.width() < tabs.width(), "need an empty strip to check"

    image = tabs.grab().toImage()
    x = (bar.width() + tabs.width()) // 2
    assert image.pixelColor(x, bar.height() // 2) == QColor(BG_DEEP)
