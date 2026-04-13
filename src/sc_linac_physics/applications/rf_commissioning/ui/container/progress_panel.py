"""Progress panel builders for the multi-phase commissioning display."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.progress import (
    build_progress_phases,
)


def build_compact_progress_bar(host) -> QWidget:
    """Build a compact horizontal progress indicator."""
    widget = QWidget()
    widget.setMaximumHeight(100)
    widget.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            border-bottom: 1px solid #333;
        }
    """)

    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(10, 8, 10, 8)
    main_layout.setSpacing(8)

    title = QLabel("Commissioning Progress")
    title.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
    main_layout.addWidget(title)

    progress_container = QWidget()
    progress_layout = QHBoxLayout()
    progress_layout.setSpacing(0)
    progress_layout.setContentsMargins(20, 0, 20, 0)

    phases = build_progress_phases()

    host.phase_indicators = {}
    host.phase_connectors = []

    for i, (label, phase) in enumerate(phases):
        node_container = QWidget()
        node_layout = QVBoxLayout()
        node_layout.setSpacing(4)
        node_layout.setContentsMargins(0, 0, 0, 0)
        node_layout.setAlignment(Qt.AlignCenter)

        circle = QLabel("●")
        circle.setAlignment(Qt.AlignCenter)
        circle.setMinimumSize(32, 32)
        circle.setStyleSheet("""
            font-size: 28px;
            color: #444;
            background-color: transparent;
        """)
        host.phase_indicators[phase] = circle

        text = QLabel(label)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(
            "font-size: 9px; color: #888; background-color: transparent;"
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
            connector.setStyleSheet("""
                color: #444;
                font-size: 16px;
                padding: 0px;
                margin: 0px 4px 24px 4px;
                background-color: transparent;
            """)
            connector.setFixedHeight(32)
            host.phase_connectors.append(connector)
            progress_layout.addWidget(connector)

    progress_container.setLayout(progress_layout)
    main_layout.addWidget(progress_container)

    widget.setLayout(main_layout)
    return widget


def update_progress_indicator(host, record) -> None:
    """Update status icons/colors for the compact progress bar."""
    projection = host.session.get_active_phase_projection()
    if projection is None:
        return

    current_phase = projection.get("current_phase")
    phase_status = projection.get("phase_status", {})

    phase_order = CommissioningPhase.get_phase_order()
    current_idx = phase_order.index(current_phase)

    for phase, indicator in host.phase_indicators.items():
        idx = phase_order.index(phase)
        status = phase_status.get(phase)
        if status is not None and status.value in {"complete", "skipped"}:
            indicator.setText("✔")
            indicator.setStyleSheet("""
                font-size: 28px;
                color: #4CAF50;
                font-weight: bold;
                background-color: rgba(76, 175, 80, 0.2);
                border-radius: 16px;
                border: 2px solid #4CAF50;
            """)
        elif status is not None and status.value == "failed":
            indicator.setText("✖")
            indicator.setStyleSheet("""
                font-size: 24px;
                color: #ef5350;
                font-weight: bold;
                background-color: rgba(239, 83, 80, 0.2);
                border-radius: 16px;
                border: 2px solid #ef5350;
            """)
        elif idx == current_idx:
            indicator.setText("▶")
            indicator.setStyleSheet("""
                font-size: 24px;
                color: #2196F3;
                font-weight: bold;
                background-color: rgba(33, 150, 243, 0.3);
                border-radius: 16px;
                border: 2px solid #2196F3;
            """)
        else:
            indicator.setText("○")
            indicator.setStyleSheet("""
                font-size: 28px;
                color: #444;
                background-color: transparent;
                border-radius: 16px;
            """)

    for i, connector in enumerate(host.phase_connectors):
        if i < current_idx:
            connector.setStyleSheet("""
                color: #4CAF50;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                margin: 0px 4px 24px 4px;
                background-color: transparent;
            """)
        else:
            connector.setStyleSheet("""
                color: #444;
                font-size: 16px;
                padding: 0px;
                margin: 0px 4px 24px 4px;
                background-color: transparent;
            """)
