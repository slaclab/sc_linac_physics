"""Tab initialization and state helpers for multi-phase commissioning."""

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)

# Every status glyph is paired with a word.  Operator feedback on PR #270 was
# that the glyphs alone were ambiguous ("a triangle means that step is running
# and checkmark is done?"), so the symbol is decoration and the word carries the
# meaning.  The word is appended to the tab tooltip rather than the tab label
# for the settled states, because nine tabs have to fit across the window; the
# running phase is the one an operator needs to spot at a glance, so it — and a
# failure — also get the word inline on the tab itself.
# "In progress", not "Running": ▶ is returned for phase == current_phase, which
# means "this is where you are in the workflow", not "a stage is executing right
# now". Calling it Running contradicted the status bar, which legitimately reads
# IDLE while the current phase sits waiting for an operator confirmation.
_PHASE_STATUS_WORDS = {
    "○": "Not started",
    "✓": "Done",
    "✗": "Failed",
    "▶": "In progress",
    "●": "Overview",
}

# Statuses urgent enough to spend horizontal tab space on.
_INLINE_STATUS_GLYPHS = ("▶", "✗")


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

            icon = self._get_phase_icon(spec.phase)
            self.tabs.addTab(
                tab_widget, self._format_tab_text(icon, spec.title)
            )
            self.tabs.setTabToolTip(
                i, self._format_tab_tooltip(icon, spec.title)
            )
            self.tabs.tabBar().setTabTextColor(i, QColor(TEXT_MUTED))

        self.tabs.currentChanged.connect(self._on_tab_changed)

    @staticmethod
    def _format_tab_text(icon: str, title: str) -> str:
        """Build tab label text, spelling out the status for urgent states."""
        word = _PHASE_STATUS_WORDS.get(icon)
        if word and icon in _INLINE_STATUS_GLYPHS:
            return f"{icon} {title} · {word}"
        return f"{icon} {title}"

    @staticmethod
    def _format_tab_tooltip(icon: str, title: str) -> str:
        """Build the tab tooltip, which always spells the status out in words."""
        word = _PHASE_STATUS_WORDS.get(icon, "Not started")
        return f"{title} — {word}"

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
            self.tabs.setTabText(i, self._format_tab_text(icon, spec.title))
            self.tabs.setTabToolTip(
                i, self._format_tab_tooltip(icon, spec.title)
            )

            if status is not None and status.value == "failed":
                self.tabs.tabBar().setTabTextColor(i, QColor(COLOR_ERROR))
            elif phase_index == current_index:
                self.tabs.tabBar().setTabTextColor(i, QColor(COLOR_PRIMARY))
            elif phase_index < current_index:
                self.tabs.tabBar().setTabTextColor(i, QColor(COLOR_SUCCESS))
            else:
                self.tabs.tabBar().setTabTextColor(i, QColor(TEXT_SECONDARY))

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
