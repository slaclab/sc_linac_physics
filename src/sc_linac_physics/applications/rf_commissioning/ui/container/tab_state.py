"""Tab initialization and state helpers for multi-phase commissioning."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)


class _TabsMixin:
    def _init_tabs(self) -> None:
        """Initialize tabs with enhanced visual feedback."""
        for i, spec in enumerate(self.phase_specs):
            tab_widget = QWidget()
            tab_layout = QVBoxLayout()
            tab_layout.setContentsMargins(0, 0, 0, 0)

            display = spec.display_class(
                parent=tab_widget, session=self.session
            )
            self._phase_displays.append(display)

            tab_layout.addWidget(display)
            tab_widget.setLayout(tab_layout)

            self.tabs.addTab(
                tab_widget,
                self._get_phase_icon(spec.phase) + " " + spec.title,
            )

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _get_phase_icon(self, phase: CommissioningPhase | None) -> str:
        """Get status icon for a phase."""
        projection = self.session.get_active_phase_projection()
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

    def _update_tab_states(self) -> None:
        """Update tab states and icons."""
        projection = self.session.get_active_phase_projection()
        if projection is None:
            for i in range(1, self.tabs.count()):
                self.tabs.setTabEnabled(i, False)
            return

        current_phase = projection.get("current_phase")
        phase_status = projection.get("phase_status", {})
        phase_order = CommissioningPhase.get_phase_order()
        current_index = phase_order.index(current_phase)

        for i, spec in enumerate(self.phase_specs):
            if spec.phase is None:
                self.tabs.setTabEnabled(i, True)
                continue

            phase_index = phase_order.index(spec.phase)
            status = phase_status.get(spec.phase)
            is_done = status is not None and status.value in {
                "complete",
                "skipped",
            }
            is_accessible = phase_index <= current_index or is_done

            self.tabs.setTabEnabled(i, is_accessible)

            icon = self._get_phase_icon(spec.phase)
            self.tabs.setTabText(i, f"{icon} {spec.title}")

            if status is not None and status.value == "failed":
                self.tabs.tabBar().setTabTextColor(i, Qt.red)
            elif phase_index == current_index:
                self.tabs.tabBar().setTabTextColor(i, Qt.blue)
            elif phase_index < current_index:
                self.tabs.tabBar().setTabTextColor(i, Qt.darkGreen)
            else:
                self.tabs.tabBar().setTabTextColor(i, Qt.gray)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab changes by auto-saving current work."""
        if self.session.has_active_record():
            try:
                self.save_active_record()
            except RecordConflictError:
                self._update_sync_status(False, "Unsaved changes")


# Backward-compat aliases so existing tests continue to work.
init_tabs = _TabsMixin._init_tabs
get_phase_icon = _TabsMixin._get_phase_icon
update_tab_states = _TabsMixin._update_tab_states
on_tab_changed = _TabsMixin._on_tab_changed
