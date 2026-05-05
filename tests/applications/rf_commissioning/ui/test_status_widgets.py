from types import SimpleNamespace

from PyQt5.QtWidgets import QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.cm_status_panel import (
    CMStatusPanel,
)
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


def test_cm_status_panel_counts_complete_cavities(qtbot):
    class _TerminalPhase:
        value = "terminal"

        @staticmethod
        def get_next_phase():
            return None

    db = SimpleNamespace(
        get_records_by_cryomodule=lambda _cm, active_only=False: [
            SimpleNamespace(
                current_phase=CommissioningPhase.COMPLETE,
                overall_status="in_progress",
            ),
            SimpleNamespace(
                current_phase=_TerminalPhase(),
                overall_status="in_progress",
            ),
            SimpleNamespace(
                current_phase=CommissioningPhase.PIEZO_PRE_RF,
                overall_status="in_progress",
            ),
        ]
    )

    panel = CMStatusPanel("L1B", "01", db)
    qtbot.addWidget(panel)

    assert panel.cavity_count_label.text() == "2/8 Complete"

    panel.cryomodule = ""
    panel.refresh()
    assert panel.cavity_count_label.text() == "0/8 Complete"


def test_cm_status_panel_builds_widget_tree(qtbot):
    db = SimpleNamespace(get_records_by_cryomodule=lambda *_a, **_k: [])
    panel = CMStatusPanel("L1B", "01", db)
    qtbot.addWidget(panel)

    assert isinstance(panel, QWidget)
    assert panel.minimumHeight() == 82
