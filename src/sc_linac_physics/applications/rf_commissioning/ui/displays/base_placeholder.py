"""Base placeholder display implementation for RF commissioning phases."""

from datetime import datetime

from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    get_phase_display_specs,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
    LOCAL_LABEL_STYLE,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)


class BasePlaceholderDisplay(PhaseDisplayBase):
    """Base class for placeholder phase displays."""

    step_progress_signal = pyqtSignal(str, int)
    UI_CLASS = GenericPhaseUI
    PHASE_NAME = ""
    DATA_ATTR = ""
    DATA_MODEL = None

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle(f"{self.PHASE_NAME} - RF Commissioning")
        self.session = session or CommissioningSession()
        self.step_progress_signal.connect(self._on_step_progress)
        self.setup_ui()

    def setup_ui(self):
        """Create the main UI layout."""
        callbacks = {
            "on_run_automated_test": self.on_run_automated_test,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display when active record changes."""
        self._update_phase_data_readouts(record)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Update display when a record is loaded."""
        self._update_phase_data_readouts(record)

    def _update_phase_data_readouts(self, record: CommissioningRecord) -> None:
        """Update readout labels from phase dataclass stored on the record."""
        phase_data = getattr(record, self.DATA_ATTR, None)
        if phase_data is None:
            self._clear_phase_specific_readouts()
            if hasattr(self, "local_phase_status"):
                self.local_phase_status.setText("No stored data")
            self._clear_generic_stored_data()
            return

        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText("Stored data loaded")

        self._apply_phase_specific_readouts(phase_data)
        self._set_generic_stored_data(phase_data)

    def _set_generic_stored_data(self, phase_data) -> None:
        """Update shared Stored Data fields (status/timestamp/notes)."""
        if hasattr(self, "local_stored_status"):
            status_text, status_style = self._get_stored_status_presentation(
                phase_data
            )
            self.local_stored_status.setText(status_text)
            self.local_stored_status.setStyleSheet(status_style)

        if hasattr(self, "local_stored_timestamp"):
            timestamp = getattr(phase_data, "timestamp", None)
            self.local_stored_timestamp.setText(self._fmt_timestamp(timestamp))

        if hasattr(self, "local_stored_notes"):
            self.local_stored_notes.setText(
                getattr(phase_data, "notes", None) or "-"
            )

    def _clear_generic_stored_data(self) -> None:
        """Reset shared Stored Data fields."""
        if hasattr(self, "local_stored_status"):
            self.local_stored_status.setText("-")
        if hasattr(self, "local_stored_timestamp"):
            self.local_stored_timestamp.setText("-")
        if hasattr(self, "local_stored_notes"):
            self.local_stored_notes.setText("-")

    def _clear_phase_specific_readouts(self) -> None:
        """Reset phase readout labels to placeholder state."""
        for widget_name in self._get_readout_widget_names():
            if hasattr(self, widget_name):
                getattr(self, widget_name).setText("-")

        self._clear_generic_stored_data()

    def _apply_phase_specific_readouts(self, phase_data) -> None:
        """Apply phase-specific formatted values to their widgets."""
        for widget_name, value in self._format_phase_data_readouts(
            phase_data
        ).items():
            if hasattr(self, widget_name):
                getattr(self, widget_name).setText(value)

    @classmethod
    def get_phase_stored_field_specs(cls):
        """Get ordered stored-data specs declared by the phase dataclass."""
        if cls.DATA_MODEL is None:
            return []
        return get_phase_display_specs(cls.DATA_MODEL)

    def _get_readout_widget_names(self) -> tuple[str, ...]:
        """Get widget names for all phase-specific stored-data readouts."""
        return tuple(
            spec.widget_name for spec in self.get_phase_stored_field_specs()
        )

    def _format_phase_data_readouts(self, phase_data) -> dict[str, str]:
        """Format phase dataclass values for display labels."""
        return {
            spec.widget_name: self._format_spec_value(
                getattr(phase_data, spec.source_attr, None), spec
            )
            for spec in self.get_phase_stored_field_specs()
        }

    def _format_spec_value(self, value, spec) -> str:
        """Format one dataclass-driven display value."""
        if value is None:
            return "-"

        if isinstance(value, bool):
            return spec.true_text if value else spec.false_text

        if isinstance(value, datetime):
            return self._fmt_timestamp(value)

        if isinstance(value, (int, float)) and spec.format_spec:
            return self._fmt_float(value, spec.format_spec, spec.unit)

        if isinstance(value, float):
            return self._fmt_float(value, unit=spec.unit)

        if spec.unit and isinstance(value, int):
            return f"{value} {spec.unit}".strip()

        return str(value)

    def _get_stored_status_presentation(self, phase_data) -> tuple[str, str]:
        """Choose the stored-data status text and styling."""
        if hasattr(phase_data, "passed"):
            passed = bool(getattr(phase_data, "passed"))
            return (
                "PASS" if passed else "FAIL",
                (
                    (
                        LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
                        + "color: #90ee90;"
                    )
                    if passed
                    else (
                        LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
                        + "color: #ff6b6b;"
                    )
                ),
            )

        if hasattr(phase_data, "is_complete"):
            complete = bool(getattr(phase_data, "is_complete"))
            return (
                "COMPLETE" if complete else "INCOMPLETE",
                (
                    (
                        LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
                        + "color: #90ee90;"
                    )
                    if complete
                    else (
                        LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c4b1a")
                        + "color: #ffd166;"
                    )
                ),
            )

        return "AVAILABLE", LOCAL_LABEL_STYLE

    @staticmethod
    def _fmt_float(
        value: float | None, fmt: str = ".3f", unit: str = ""
    ) -> str:
        """Format optional float with optional engineering unit."""
        if value is None:
            return "-"
        rendered = format(value, fmt)
        return f"{rendered} {unit}".strip()

    @staticmethod
    def _fmt_timestamp(value: datetime | None) -> str:
        """Format optional timestamp."""
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def clear_results(self):
        """Clear all result displays."""
        if hasattr(self, "local_progress_bar"):
            self.local_progress_bar.setValue(0)
        if hasattr(self, "local_current_step"):
            self.local_current_step.setText("-")
        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText("-")
        if hasattr(self, "history_text"):
            self.history_text.clear()

    @pyqtSlot()
    def on_run_automated_test(self):
        """Placeholder for running automated test."""
        operator = self.get_current_operator()
        if not operator:
            self.show_error("Please select an operator before running test.")
            return

        cavity_info = self.get_current_cavity()
        if not cavity_info:
            self.show_error("Please select a cavity before running test.")
            return

        self.log_message(f"Starting {self.PHASE_NAME} test...")
        self.log_message("⚠️  This is a placeholder implementation")
        self.log_message(
            "Actual test logic will be implemented in phase-specific controller"
        )

        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText("Placeholder - Not Implemented")

    def update_timestamp(self):
        """Update the timestamp label with current time."""
        if hasattr(self, "timestamp_label"):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.timestamp_label.setText(current_time)
            self.timestamp_label.setStyleSheet(
                "color: #888888; font-size: 9pt;"
            )

        QTimer.singleShot(1000, self.update_timestamp)
