"""Progress panel builders for the multi-phase commissioning display."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_DEEP,
    BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    RADIUS_MD,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.progress import (
    build_progress_phases,
)

_NODE_BASE = "font-size: 9pt; padding: 2px 6px; background-color: transparent;"
_CONN_STYLE = (
    f"color: {TEXT_MUTED}; font-size: 10px; background-color: transparent;"
)


class _ProgressMixin:
    def _build_compact_progress_bar(self) -> QWidget:
        """Build a compact single-row phase progress indicator."""
        widget = QWidget()
        widget.setObjectName("progressPanel")
        widget.setStyleSheet(f"""
            QWidget#progressPanel {{
                background-color: {BG_DEEP};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 5, 16, 5)
        layout.setSpacing(0)

        phases = build_progress_phases()
        self.phase_indicators = {}
        self.phase_connectors = []
        self._phase_labels = {}

        for i, (label, phase) in enumerate(phases):
            short = label.replace("\n", " ")
            self._phase_labels[phase] = short

            node = QLabel(f"○ {short}")
            node.setAlignment(Qt.AlignCenter)
            node.setStyleSheet(f"{_NODE_BASE} color: {TEXT_MUTED};")
            self.phase_indicators[phase] = node
            layout.addWidget(node, stretch=2)

            if i < len(phases) - 1:
                conn = QLabel("─")
                conn.setAlignment(Qt.AlignCenter)
                conn.setStyleSheet(_CONN_STYLE)
                self.phase_connectors.append(conn)
                layout.addWidget(conn, stretch=1)

        widget.setLayout(layout)
        return widget

    def update_progress_indicator(self, record) -> None:
        """Update phase node colors and icons in the progress bar."""
        projection = self.session.get_active_phase_projection()
        if projection is None:
            return

        current_phase = projection.get("current_phase")
        phase_status = projection.get("phase_status", {})
        phase_order = CommissioningPhase.get_phase_order()
        current_idx = phase_order.index(current_phase)

        for phase, node in self.phase_indicators.items():
            idx = phase_order.index(phase)
            status = phase_status.get(phase)
            lbl = self._phase_labels.get(phase, "")

            if status is not None and status.value in {"complete", "skipped"}:
                node.setText(f"✔ {lbl}")
                node.setStyleSheet(
                    f"{_NODE_BASE} color: {COLOR_SUCCESS}; font-weight: bold;"
                )
            elif status is not None and status.value == "failed":
                node.setText(f"✖ {lbl}")
                node.setStyleSheet(
                    f"{_NODE_BASE} color: {COLOR_ERROR}; font-weight: bold;"
                )
            elif idx == current_idx:
                node.setText(f"▶ {lbl}")
                node.setStyleSheet(
                    f"{_NODE_BASE} color: {COLOR_PRIMARY}; font-weight: bold;"
                    f" background-color: rgba(123,140,222,0.15);"
                    f" border-radius: {RADIUS_MD};"
                )
            else:
                node.setText(f"○ {lbl}")
                node.setStyleSheet(
                    f"{_NODE_BASE} color: {TEXT_SECONDARY};"
                    if idx < current_idx
                    else f"{_NODE_BASE} color: {TEXT_MUTED};"
                )

        for i, conn in enumerate(self.phase_connectors):
            conn.setStyleSheet(
                f"color: {COLOR_SUCCESS}; font-size: 10px; background-color: transparent;"
                if i < current_idx
                else _CONN_STYLE
            )


# Backward-compat aliases so existing tests continue to work.
build_compact_progress_bar = _ProgressMixin._build_compact_progress_bar
update_progress_indicator = _ProgressMixin.update_progress_indicator
