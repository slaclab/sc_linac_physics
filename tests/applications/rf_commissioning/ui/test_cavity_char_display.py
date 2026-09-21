"""Tests for the Cavity Characterization display."""

from unittest.mock import patch

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (
    CavityCharLimits,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
    GenericPhaseUI,
)
from sc_linac_physics.utils.sc_linac import linac_utils


@pytest.fixture
def display(qtbot, tmp_path):
    from sc_linac_physics.applications.rf_commissioning.ui.displays.cavity_char import (  # noqa: E501
        CavityCharDisplay,
    )

    s = CommissioningSession(db_path=str(tmp_path / "cav.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        d = CavityCharDisplay(session=s)
        qtbot.addWidget(d)
        return d


def test_the_tab_is_no_longer_a_placeholder(display):
    assert display.UI_CLASS is CavityCharUI
    assert display.UI_CLASS is not GenericPhaseUI


def test_registry_resolves_cavity_char_to_this_display():
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.displays.cavity_char import (  # noqa: E501
        CavityCharDisplay,
    )

    assert (
        PHASE_DISPLAY_MAP[CommissioningPhase.CAVITY_CHAR] is CavityCharDisplay
    )


def test_package_export_matches_the_registry():
    """The trap #270 left for frequency tuning, and #297 fixed.

    A phase display starts as a placeholder in displays.standard. Repointing
    the registry without repointing the package re-export hands importers the
    dead placeholder while the app runs the real one.
    """
    from sc_linac_physics.applications.rf_commissioning.ui import (
        displays as displays_pkg,
    )
    from sc_linac_physics.applications.rf_commissioning import ui as ui_pkg
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )

    registry_cls = PHASE_DISPLAY_MAP[CommissioningPhase.CAVITY_CHAR]
    assert displays_pkg.CavityCharDisplay is registry_cls
    assert getattr(ui_pkg, "CavityCharDisplay", registry_cls) is registry_cls


def test_placeholder_is_gone_from_standard():
    from sc_linac_physics.applications.rf_commissioning.ui.displays import (
        standard,
    )

    assert not hasattr(standard, "CavityCharDisplay")


def test_drive_level_bounds_come_from_cavity_char_limits(display):
    """The builder cannot see CavityCharLimits, so the display applies it.

    Builders in this package do not import from phases/; the display owns the
    controller, and the controller owns the limits.
    """
    limits = CavityCharLimits()
    assert display.drive_level_spinbox.maximum() == limits.max_drive_level
    assert display.drive_level_spinbox.value() == (
        linac_utils.SAFE_PULSED_DRIVE_LEVEL
    )
    assert display.drive_level_spinbox.value() == limits.default_drive_level


def test_elapsed_label_shows_progress_against_the_timeout(display):
    display._on_elapsed(42.0)
    text = display.elapsed_label.text()
    assert "42" in text
    assert "300" in text


def test_set_char_status_writes_the_backend_message_verbatim(display):
    message = (
        "Characterization crashed — check the cavity's PROBECALSTS and "
        "the RF interlocks"
    )
    display.set_char_status(message)
    assert display.char_status_label.text() == message


def test_a_record_with_no_cavity_char_does_not_raise(display):
    from sc_linac_physics.applications.rf_commissioning.models.data_models import (  # noqa: E501
        CommissioningRecord,
    )

    record = CommissioningRecord(linac=0, cryomodule="01", cavity_number=1)
    assert record.cavity_char is None
    display.refresh_from_record(record)
