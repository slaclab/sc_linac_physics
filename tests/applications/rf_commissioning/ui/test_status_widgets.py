from sc_linac_physics.applications.rf_commissioning.ui.magnet_status_badge import (
    MagnetStatusBadge,
)


def test_magnet_status_badge_updates_text_and_status(qtbot):
    badge = MagnetStatusBadge()
    qtbot.addWidget(badge)

    assert badge.label.text() == "? PENDING"

    badge.set_status("pass")
    assert badge.status == "PASS"
    assert badge.label.text() == "✓ PASS"

    badge.set_status("FAIL")
    assert badge.label.text() == "✗ FAIL"
