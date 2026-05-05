"""Tab initialization and state helpers for multi-phase commissioning."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)


def init_tabs(host) -> None:
    """Initialize tabs with enhanced visual feedback."""
    for i, spec in enumerate(host.phase_specs):
        tab_widget = QWidget()
        tab_layout = QVBoxLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)

        display = spec.display_class(parent=tab_widget, session=host.session)
        host._phase_displays.append(display)

        tab_layout.addWidget(display)
        tab_widget.setLayout(tab_layout)

        host.tabs.addTab(
            tab_widget,
            get_phase_icon(host, spec.phase) + " " + spec.title,
        )

    host.tabs.currentChanged.connect(host._on_tab_changed)


def get_phase_icon(host, phase: CommissioningPhase | None) -> str:
    """Get status icon for a phase."""
    projection = host.session.get_active_phase_projection()
    if projection is None:
        return "○"

    current_phase = projection.get("current_phase")
    phase_status = projection.get("phase_status", {})

    if phase is None:
        return "●"

    status = phase_status.get(phase)
    if status is not None:
        if status.value == "complete":
            return "✓"
        if status.value == "failed":
            return "✗"

    if phase == current_phase:
        return "▶"

    phase_order = CommissioningPhase.get_phase_order()
    current_idx = phase_order.index(current_phase)
    phase_idx = phase_order.index(phase)
    if phase_idx < current_idx:
        return "✓"
    return "○"


def update_tab_states(host) -> None:
    """Update tab states and icons."""
    projection = host.session.get_active_phase_projection()
    if projection is None:
        for i in range(1, host.tabs.count()):
            host.tabs.setTabEnabled(i, False)
        return

    current_phase = projection.get("current_phase")
    phase_status = projection.get("phase_status", {})
    phase_order = CommissioningPhase.get_phase_order()
    current_index = phase_order.index(current_phase)

    for i, spec in enumerate(host.phase_specs):
        if spec.phase is None:
            host.tabs.setTabEnabled(i, True)
            continue

        phase_index = phase_order.index(spec.phase)
        status = phase_status.get(spec.phase)
        is_done = status is not None and status.value in {"complete", "skipped"}
        is_accessible = phase_index <= current_index or is_done

        host.tabs.setTabEnabled(i, is_accessible)

        icon = get_phase_icon(host, spec.phase)
        host.tabs.setTabText(i, f"{icon} {spec.title}")

        if status is not None and status.value == "failed":
            host.tabs.tabBar().setTabTextColor(i, Qt.red)
        elif phase_index == current_index:
            host.tabs.tabBar().setTabTextColor(i, Qt.blue)
        elif phase_index < current_index:
            host.tabs.tabBar().setTabTextColor(i, Qt.darkGreen)
        else:
            host.tabs.tabBar().setTabTextColor(i, Qt.gray)


def on_tab_changed(host, index: int) -> None:
    """Handle tab changes by auto-saving current work."""
    if host.session.has_active_record():
        try:
            host.save_active_record()
        except RecordConflictError:
            host._update_sync_status(False, "Unsaved changes")
