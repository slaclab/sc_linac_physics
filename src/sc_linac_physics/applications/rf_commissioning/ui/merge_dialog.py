"""Merge dialog for resolving record conflicts."""

import copy
from datetime import datetime
from typing import Optional

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QScrollArea,
    QWidget,
    QFrame,
)
from PyQt5.QtCore import Qt

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PHASE_REGISTRY,
)


class MergeDialog(QDialog):
    """Dialog for manually merging conflicting commissioning records.

    Shows side-by-side comparison of local changes vs database version,
    allowing user to select which version to keep for each field.
    """

    def __init__(
        self,
        local_record: CommissioningRecord,
        db_record: CommissioningRecord,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Merge Conflicting Changes")
        self.setModal(True)
        self.resize(800, 600)

        self.local_record = local_record
        self.db_record = db_record
        self.merged_record: Optional[CommissioningRecord] = None

        # Track user's choices for each field
        self._field_choices: dict[str, str] = (
            {}
        )  # field_name -> "local" or "db"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            "This record was modified by another user.\n"
            "Choose which version to keep for each field:\n\n"
            "<b>Note:</b> All measurement history from both users is automatically preserved."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Scrollable comparison area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)

        self._build_field_comparisons()

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        keep_all_local = QPushButton("Keep All My Changes")
        keep_all_local.clicked.connect(self._keep_all_local)
        button_layout.addWidget(keep_all_local)

        keep_all_db = QPushButton("Keep All Their Changes")
        keep_all_db.clicked.connect(self._keep_all_db)
        button_layout.addWidget(keep_all_db)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Merge")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply_merge)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

    def _build_field_comparisons(self):
        """Build UI showing all field differences."""

        # Compare basic fields
        self._add_field_comparison(
            "Current Phase",
            "current_phase",
            str(self.local_record.current_phase.value),
            str(self.db_record.current_phase.value),
        )

        self._add_field_comparison(
            "Overall Status",
            "overall_status",
            self.local_record.overall_status,
            self.db_record.overall_status,
        )

        # Compare phase status map (single pick keeps choices understandable)
        self._add_field_comparison(
            "Phase Status",
            "phase_status",
            self._phase_status_summary(self.local_record),
            self._phase_status_summary(self.db_record),
        )

        # Compare phase data dynamically from registry so newly-added phases
        # automatically appear in conflict UI.
        for phase, registration in PHASE_REGISTRY.items():
            if not registration.record_attr:
                continue
            self._add_phase_data_comparison(
                registration.display_label,
                registration.record_attr,
                getattr(self.local_record, registration.record_attr),
                getattr(self.db_record, registration.record_attr),
            )

        # Phase history comparison
        self._add_field_comparison(
            "Phase History Length",
            "phase_history",
            f"{len(self.local_record.phase_history)} entries",
            f"{len(self.db_record.phase_history)} entries",
        )

    def _add_field_comparison(
        self,
        display_name: str,
        field_name: str,
        local_value: str,
        db_value: str,
    ):
        """Add a single field comparison row."""

        # Skip if values are identical
        if local_value == db_value:
            return

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)

        # Field name header
        header = QLabel(f"<b>{display_name}</b>")
        frame_layout.addWidget(header)

        # Radio button group for this field
        radio_layout = QHBoxLayout()
        button_group = QButtonGroup(self)

        # Local version
        local_layout = QVBoxLayout()
        local_radio = QRadioButton("My version:")
        local_radio.setChecked(True)  # Default to local
        button_group.addButton(local_radio, 0)
        local_layout.addWidget(local_radio)

        local_label = QLabel(str(local_value))
        local_label.setWordWrap(True)
        local_label.setStyleSheet("padding-left: 20px; color: #0066cc;")
        local_layout.addWidget(local_label)

        radio_layout.addLayout(local_layout)

        # Database version
        db_layout = QVBoxLayout()
        db_radio = QRadioButton("Their version:")
        button_group.addButton(db_radio, 1)
        db_layout.addWidget(db_radio)

        db_label = QLabel(str(db_value))
        db_label.setWordWrap(True)
        db_label.setStyleSheet("padding-left: 20px; color: #cc6600;")
        db_layout.addWidget(db_label)

        radio_layout.addLayout(db_layout)

        frame_layout.addLayout(radio_layout)

        # Store button group to retrieve choice later
        button_group.buttonClicked.connect(
            lambda btn: self._on_field_choice(
                field_name, "local" if button_group.id(btn) == 0 else "db"
            )
        )
        self._field_choices[field_name] = "local"  # Default

        self.content_layout.addWidget(frame)

    def _add_phase_data_comparison(
        self, display_name: str, field_name: str, local_data, db_data
    ):
        """Add comparison for phase-specific data objects."""

        # Convert to summary strings
        local_str = self._phase_data_summary(local_data)
        db_str = self._phase_data_summary(db_data)

        self._add_field_comparison(display_name, field_name, local_str, db_str)

    def _phase_data_summary(self, data) -> str:
        """Create human-readable summary of phase data."""
        if data is None:
            return "No data"

        # Convert dataclass to dict for display
        if hasattr(data, "to_dict"):
            data_dict = data.to_dict()
            lines = []
            for key, value in data_dict.items():
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"{key}: {value}")
            return "\n".join(lines[:5])  # Show first 5 fields

        return str(data)

    def _phase_status_summary(self, record: CommissioningRecord) -> str:
        """Create compact phase-status summary ordered by workflow."""
        lines = [
            f"{phase.value}: {record.get_phase_status(phase).value}"
            for phase in record.current_phase.get_phase_order()
        ]
        return "\n".join(lines)

    def _on_field_choice(self, field_name: str, choice: str):
        """Record user's choice for a field."""
        self._field_choices[field_name] = choice

    def _keep_all_local(self):
        """Set all fields to keep local version."""
        for field_name in self._field_choices.keys():
            self._field_choices[field_name] = "local"
        self._apply_merge()

    def _keep_all_db(self):
        """Set all fields to keep database version."""
        for field_name in self._field_choices.keys():
            self._field_choices[field_name] = "db"
        self._apply_merge()

    def _apply_merge(self):
        """Create merged record based on user's choices."""
        # Start with a copy of local record
        merged = copy.deepcopy(self.local_record)

        # Apply user's choices
        for field_name, choice in self._field_choices.items():
            if choice == "db":
                # Take field from database version
                db_value = getattr(self.db_record, field_name)
                setattr(merged, field_name, db_value)

        # Always preserve checkpoints from both versions.
        merged.phase_history = self._merge_phase_history(
            self.local_record.phase_history,
            self.db_record.phase_history,
        )

        # Keep current phase/status in sync when phase_status field is chosen.
        if self._field_choices.get("phase_status") == "db":
            merged.current_phase = self.db_record.current_phase

        self.merged_record = merged
        self.accept()

    def _merge_phase_history(self, local_history, db_history):
        """Merge checkpoint history lists without losing entries.

        Uses dataclass payloads as stable keys and returns chronologically
        sorted unique checkpoints.
        """
        merged_by_key = {}
        for checkpoint in [*local_history, *db_history]:
            key = (
                checkpoint.phase.value,
                checkpoint.timestamp.isoformat(),
                checkpoint.operator,
                checkpoint.step_name,
                checkpoint.success,
                checkpoint.error_message,
                repr(checkpoint.notes),
                repr(sorted(checkpoint.measurements.items())),
            )
            merged_by_key[key] = checkpoint

        return sorted(
            merged_by_key.values(),
            key=lambda checkpoint: checkpoint.timestamp,
        )

    def get_merged_record(self) -> Optional[CommissioningRecord]:
        """Get the merged record after dialog is accepted.

        Returns:
            Merged record if dialog was accepted, None otherwise
        """
        return self.merged_record
