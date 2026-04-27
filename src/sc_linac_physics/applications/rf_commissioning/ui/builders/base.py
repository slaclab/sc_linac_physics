"""Base UI builder used by RF commissioning phase screens."""

from collections.abc import Callable
from typing import TypeVar

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from .styles import LOCAL_LABEL_STYLE, MONO_FONT_STACK


class PhaseUIBase:
    """Base UI builder with common components for all commissioning phases."""

    def __init__(
        self,
        parent,
        callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self.parent = parent
        self.callbacks = callbacks or {}
        self.widgets: dict[str, object] = {}

    _W = TypeVar("_W")

    def _register(self, name: str, widget: _W) -> _W:
        """Register a widget by name for easy access."""
        self.widgets[name] = widget
        return widget

    def _connect(self, widget, callback_key: str) -> None:
        """Connect widget signal to callback if callback exists."""
        callback = self.callbacks.get(callback_key)
        if callback:
            widget.clicked.connect(callback)

    def _build_main_toolbar(self) -> QVBoxLayout:
        """Create an enhanced toolbar with better controls and visual hierarchy."""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.setContentsMargins(4, 4, 4, 4)

        primary_group = QHBoxLayout()
        primary_group.setSpacing(4)

        run_button = self._register("run_button", QPushButton("▶ Start Test"))
        run_button.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
                border: none;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        run_button.setFixedHeight(40)
        run_button.setMinimumWidth(120)
        self._connect(run_button, "on_run_automated_test")

        pause_button = self._register("pause_button", QPushButton("⏸ Pause"))
        pause_button.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        pause_button.setFixedHeight(40)
        pause_button.setEnabled(False)
        self._connect(pause_button, "on_pause_test")

        abort_button = self._register("abort_button", QPushButton("⏹ Abort"))
        abort_button.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        abort_button.setFixedHeight(40)
        abort_button.setEnabled(False)
        self._connect(abort_button, "on_abort_test")

        primary_group.addWidget(run_button)
        primary_group.addWidget(pause_button)
        primary_group.addWidget(abort_button)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setStyleSheet("QFrame { color: #4a4a4a; }")

        secondary_group = QHBoxLayout()
        secondary_group.setSpacing(4)

        step_mode_btn = self._register(
            "step_mode_btn", QPushButton("Step Mode")
        )
        step_mode_btn.setCheckable(True)
        step_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                padding: 8px 12px;
                border-radius: 4px;
                border: 1px solid #4b5563;
            }
            QPushButton:checked {
                background-color: #059669;
                color: white;
                border: 1px solid #047857;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        step_mode_btn.setFixedHeight(40)
        self._connect(step_mode_btn, "on_toggle_step_mode")

        next_step_btn = self._register("next_step_btn", QPushButton("Next →"))
        next_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        next_step_btn.setFixedHeight(40)
        next_step_btn.setEnabled(False)
        self._connect(next_step_btn, "on_next_step")

        secondary_group.addWidget(step_mode_btn)
        secondary_group.addWidget(next_step_btn)

        status_section = QVBoxLayout()
        status_section.setSpacing(2)

        status_indicator = self._register("status_indicator", QLabel("● READY"))
        status_indicator.setStyleSheet("""
            QLabel {
                color: #10b981;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        status_indicator.setAlignment(Qt.AlignRight)

        timestamp_label = self._register("timestamp_label", QLabel("--:--:--"))
        timestamp_label.setAlignment(Qt.AlignRight)
        timestamp_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 9pt;
                font-family: %s;
            }
            """ % MONO_FONT_STACK)

        status_section.addWidget(status_indicator)
        status_section.addWidget(timestamp_label)

        toolbar.addLayout(primary_group)
        toolbar.addWidget(sep1)
        toolbar.addLayout(secondary_group)
        toolbar.addStretch()
        toolbar.addLayout(status_section)

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        frame.setLayout(toolbar)

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)

        return wrapper

    def update_toolbar_state(self, state: str) -> None:
        """Update toolbar button states based on test state."""
        run_btn = self.widgets.get("run_button")
        pause_btn = self.widgets.get("pause_button")
        abort_btn = self.widgets.get("abort_button")
        status_ind = self.widgets.get("status_indicator")

        if state == "idle":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("● READY")
            status_ind.setStyleSheet(
                "QLabel { color: #10b981; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "running":
            run_btn.setEnabled(False)
            pause_btn.setEnabled(True)
            abort_btn.setEnabled(True)
            status_ind.setText("● RUNNING")
            status_ind.setStyleSheet(
                "QLabel { color: #3b82f6; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "paused":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Resume")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(True)
            status_ind.setText("● PAUSED")
            status_ind.setStyleSheet(
                "QLabel { color: #f59e0b; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "complete":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✓ COMPLETE")
            status_ind.setStyleSheet(
                "QLabel { color: #10b981; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "error":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Retry")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✗ ERROR")
            status_ind.setStyleSheet(
                "QLabel { color: #dc2626; font-weight: bold; font-size: 10pt; }"
            )

    def _build_history(self) -> QGroupBox:
        """Build a space-efficient phase history section."""
        group = QGroupBox("Phase History")

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        history_text = self._register("history_text", QTextEdit())
        history_text.setReadOnly(True)
        history_text.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #00ff00; "
            f"font-family: {MONO_FONT_STACK}; "
            "font-size: 10pt; }"
        )

        history_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        history_text.setMinimumHeight(60)
        history_text.setMaximumHeight(180)

        layout.addWidget(history_text)
        group.setLayout(layout)
        return group

    def _build_basic_results_section(self, phase_name: str) -> QGroupBox:
        """Build a basic results section for placeholder phases."""
        group = QGroupBox(f"{phase_name} - Status && Results")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        step_label = QLabel("Current Step:")
        step_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(step_label)

        current_step = self._register("local_current_step", QLabel("-"))
        current_step.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        current_step.setAlignment(Qt.AlignCenter)
        layout.addWidget(current_step)

        phase_label = QLabel("Test Status:")
        phase_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(phase_label)

        phase_status = self._register("local_phase_status", QLabel("-"))
        phase_status.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        phase_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(phase_status)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _make_local_label(self, text: str) -> QLabel:
        """Create a local (non-EPICS) label with standard styling."""
        label = QLabel(text)
        label.setStyleSheet(LOCAL_LABEL_STYLE)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _build_stored_data_section(
        self, fields: list[tuple[str, str]] = None
    ) -> QGroupBox:
        """Build a generalized 'Stored Data' section with standard fields."""
        fields = fields or []
        group = QGroupBox("Stored Data")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        grid = QGridLayout()
        grid.setSpacing(5)

        row = 0

        grid.addWidget(QLabel("Progress:"), row, 0)
        progress_bar = self._register("local_progress_bar", QProgressBar())
        progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #ff9a4a; border-radius: 3px; "
            "background-color: #2a2a1a; text-align: center; color: white; "
            "min-height: 20px; max-height: 20px; } "
            "QProgressBar::chunk { background-color: #ff9a4a; }"
        )
        grid.addWidget(progress_bar, row, 1)
        row += 1

        grid.addWidget(QLabel("Status:"), row, 0)
        status_label = self._register(
            "local_stored_status", self._make_local_label("-")
        )
        grid.addWidget(status_label, row, 1)
        row += 1

        for label_text, widget_name in fields:
            grid.addWidget(QLabel(f"  {label_text}:"), row, 0)
            value_label = self._register(
                widget_name, self._make_local_label("-")
            )
            grid.addWidget(value_label, row, 1)
            row += 1

        grid.addWidget(QLabel("Stored At:"), row, 0)
        timestamp_label = self._register(
            "local_stored_timestamp", self._make_local_label("-")
        )
        grid.addWidget(timestamp_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Notes:"), row, 0)
        notes_label = self._register(
            "local_stored_notes", self._make_local_label("-")
        )
        notes_label.setWordWrap(True)
        notes_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(notes_label, row, 1)

        layout.addLayout(grid)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def _get_parent_stored_data_fields(self) -> list[tuple[str, str]]:
        """Get stored-data field definitions from the parent display."""
        if hasattr(self.parent, "get_phase_stored_field_specs"):
            return [
                (spec.label, spec.widget_name)
                for spec in self.parent.get_phase_stored_field_specs()
            ]
        return []
