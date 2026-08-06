"""Progress panel builders for the multi-phase commissioning display."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_DEEP,
    BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.progress import (
    build_progress_phases,
)


class _ProgressMixin:
    def _build_compact_progress_bar(self) -> QWidget:
        """Build a compact horizontal progress indicator."""
        widget = QWidget()
        widget.setMaximumHeight(100)
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_DEEP};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        title = QLabel("Commissioning Progress")
        title.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;"
        )
        main_layout.addWidget(title)

        progress_container = QWidget()
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(0)
        progress_layout.setContentsMargins(20, 0, 20, 0)

        phases = build_progress_phases()

        self.phase_indicators = {}
        self.phase_connectors = []

        for i, (label, phase) in enumerate(phases):
            node_container = QWidget()
            node_layout = QVBoxLayout()
            node_layout.setSpacing(4)
            node_layout.setContentsMargins(0, 0, 0, 0)
            node_layout.setAlignment(Qt.AlignCenter)

            circle = QLabel("●")
            circle.setAlignment(Qt.AlignCenter)
            circle.setMinimumSize(32, 32)
            circle.setStyleSheet(f"""
                font-size: 28px;
                color: {TEXT_MUTED};
                background-color: transparent;
            """)
            self.phase_indicators[phase] = circle

            text = QLabel(label)
            text.setAlignment(Qt.AlignCenter)
            text.setStyleSheet(
                f"font-size: 9px; color: {TEXT_MUTED}; background-color: transparent;"
            )
            text.setWordWrap(True)
            text.setFixedWidth(60)

            node_layout.addWidget(circle)
            node_layout.addWidget(text)
            node_container.setLayout(node_layout)

            progress_layout.addWidget(node_container)

            if i < len(phases) - 1:
                connector = QLabel("━━━━")
                connector.setAlignment(Qt.AlignCenter)
                connector.setStyleSheet(f"""
                    color: {TEXT_MUTED};
                    font-size: 16px;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)
                connector.setFixedHeight(32)
                self.phase_connectors.append(connector)
                progress_layout.addWidget(connector)

        progress_container.setLayout(progress_layout)
        main_layout.addWidget(progress_container)

        widget.setLayout(main_layout)
        return widget

    def update_progress_indicator(self, record) -> None:
        """Update status icons/colors for the compact progress bar."""
        projection = self.session.get_active_phase_projection()
        if projection is None:
            return

        current_phase = projection.get("current_phase")
        phase_status = projection.get("phase_status", {})

        phase_order = CommissioningPhase.get_phase_order()
        current_idx = phase_order.index(current_phase)

        for phase, indicator in self.phase_indicators.items():
            idx = phase_order.index(phase)
            status = phase_status.get(phase)
            if status is not None and status.value in {"complete", "skipped"}:
                indicator.setText("✔")
                indicator.setStyleSheet(f"""
                    font-size: 28px;
                    color: {COLOR_SUCCESS};
                    font-weight: bold;
                    background-color: rgba(74, 183, 130, 0.15);
                    border-radius: 16px;
                    border: 2px solid {COLOR_SUCCESS};
                """)
            elif status is not None and status.value == "failed":
                indicator.setText("✖")
                indicator.setStyleSheet(f"""
                    font-size: 24px;
                    color: {COLOR_ERROR};
                    font-weight: bold;
                    background-color: rgba(192, 84, 74, 0.15);
                    border-radius: 16px;
                    border: 2px solid {COLOR_ERROR};
                """)
            elif idx == current_idx:
                indicator.setText("▶")
                indicator.setStyleSheet(f"""
                    font-size: 24px;
                    color: {COLOR_PRIMARY};
                    font-weight: bold;
                    background-color: rgba(123, 140, 222, 0.2);
                    border-radius: 16px;
                    border: 2px solid {COLOR_PRIMARY};
                """)
            else:
                indicator.setText("○")
                indicator.setStyleSheet(f"""
                    font-size: 28px;
                    color: {TEXT_MUTED};
                    background-color: transparent;
                    border-radius: 16px;
                """)

        for i, connector in enumerate(self.phase_connectors):
            if i < current_idx:
                connector.setStyleSheet(f"""
                    color: {COLOR_SUCCESS};
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)
            else:
                connector.setStyleSheet(f"""
                    color: {TEXT_MUTED};
                    font-size: 16px;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)


# Backward-compat aliases so existing tests continue to work.
build_compact_progress_bar = _ProgressMixin._build_compact_progress_bar
update_progress_indicator = _ProgressMixin.update_progress_indicator
