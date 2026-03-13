"""
Placeholder displays for RF commissioning phases.

These are minimal implementations that provide the basic UI structure
for each phase. They can be expanded with phase-specific functionality
as needed.
"""

from datetime import datetime

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTimer

from sc_linac_physics.applications.rf_commissioning import CommissioningRecord
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    ColdLandingData,
    CavityCharacterization,
    HighPowerRampData,
    PiezoPreRFCheck,
    PiezoWithRFTest,
    SSACharacterization,
    get_phase_display_specs,
)
from sc_linac_physics.applications.rf_commissioning.ui.ui_builder import (
    ColdLandingUI,
    GenericPhaseUI,
    SSACharUI,
    CavityCharUI,
    PiezoWithRFUI,
    HighPowerUI,
    PiezoPreRFUI,
    LOCAL_CAP_STYLE,
    LOCAL_LABEL_STYLE,
)


class BasePlaceholderDisplay(PhaseDisplayBase):
    """Base class for placeholder phase displays."""

    step_progress_signal = pyqtSignal(str, int)  # (step_name, progress)
    # Subclasses may override UI_CLASS with a specialised builder.  When left
    # as GenericPhaseUI the standard toolbar/history/results layout is used.
    UI_CLASS = GenericPhaseUI
    PHASE_NAME = ""  # Override with a human-readable phase name
    DATA_ATTR = ""  # Override with the CommissioningRecord attribute name
    DATA_MODEL = None  # Override with the phase dataclass type

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle(f"{self.PHASE_NAME} - RF Commissioning")
        self.session = session or CommissioningSession()

        # Connect progress signal
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


class PiezoPreRFDisplay(BasePlaceholderDisplay):
    """Display for Piezo Pre-RF phase (fully implemented)."""

    UI_CLASS = PiezoPreRFUI
    PHASE_NAME = "Piezo Pre-RF"
    DATA_ATTR = "piezo_pre_rf"
    DATA_MODEL = PiezoPreRFCheck

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("Piezo Pre-RF Test - PyDM")

        self.controller = PiezoPreRFController(self, self.session)
        if hasattr(self.controller, "phase_completed"):
            self.controller.phase_completed.connect(
                self._on_controller_phase_completed
            )
        if hasattr(self.controller, "setup_pv_connections"):
            self.controller.setup_pv_connections()

    def setup_ui(self):
        """Create the main UI layout."""
        callbacks = {
            "toggle_piezo_enable": self.toggle_piezo_enable,
            "toggle_manual_mode": self.toggle_manual_mode,
            "on_run_automated_test": self.on_run_automated_test,
            "on_abort_test": self.on_abort,
            "on_pause_test": self.on_pause_test,
            "on_toggle_step_mode": self.on_toggle_step_mode,
            "on_next_step": self.on_next_step,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display when active record changes."""
        result = record.piezo_pre_rf
        if result:
            self._update_local_results(result)
        else:
            self.clear_results()

        self._update_stored_readout(result)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Update display when a record is loaded."""
        # Update PV addresses to match the loaded record's cavity
        if hasattr(self.controller, "update_pv_addresses"):
            self.controller.update_pv_addresses(
                record.cryomodule, str(record.cavity_number)
            )
        self.refresh_from_record(record)

    def _on_controller_phase_completed(self, record):
        """Handle phase completion from controller - notify parent container."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    def _update_local_results(self, result: PiezoPreRFCheck):
        """Update local result displays (orange-bordered widgets on right panel)."""
        pass_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
            + "color: #90ee90; font-weight: bold;"
        )
        fail_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
            + "color: #ff6b6b; font-weight: bold;"
        )

        if hasattr(self, "local_cha_result"):
            self.local_cha_result.setText(
                "PASS" if result.channel_a_passed else "FAIL"
            )
            self.local_cha_result.setStyleSheet(
                pass_style if result.channel_a_passed else fail_style
            )

        if hasattr(self, "local_chb_result"):
            self.local_chb_result.setText(
                "PASS" if result.channel_b_passed else "FAIL"
            )
            self.local_chb_result.setStyleSheet(
                pass_style if result.channel_b_passed else fail_style
            )

        if hasattr(self, "local_overall_result"):
            self.local_overall_result.setText(
                "PASS" if result.passed else "FAIL"
            )
            overall_style = (
                pass_style if result.passed else fail_style
            ) + "font-weight: bold;"
            self.local_overall_result.setStyleSheet(overall_style)

        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText(
                "Complete" if result.passed else "Incomplete"
            )

    def _update_stored_readout(self, result: PiezoPreRFCheck | None) -> None:
        """Update stored-data labels from the record dataclass."""
        if result is None:
            self._clear_phase_specific_readouts()
            return

        self._set_generic_stored_data(result)
        self._apply_phase_specific_readouts(result)

    def clear_results(self):
        """Clear all result displays."""
        super().clear_results()

        if hasattr(self, "local_cha_result"):
            self.local_cha_result.setText("-")
            self.local_cha_result.setStyleSheet(LOCAL_LABEL_STYLE)
        if hasattr(self, "local_chb_result"):
            self.local_chb_result.setText("-")
            self.local_chb_result.setStyleSheet(LOCAL_LABEL_STYLE)
        if hasattr(self, "local_cha_cap"):
            self.local_cha_cap.setText("-")
            self.local_cha_cap.setStyleSheet(LOCAL_CAP_STYLE)
        if hasattr(self, "local_chb_cap"):
            self.local_chb_cap.setText("-")
            self.local_chb_cap.setStyleSheet(LOCAL_CAP_STYLE)
        if hasattr(self, "local_overall_result"):
            self.local_overall_result.setText("-")
            self.local_overall_result.setStyleSheet(
                LOCAL_LABEL_STYLE + "font-weight: bold;"
            )

        self._clear_generic_stored_data()
        if hasattr(self, "local_stored_cap_a"):
            self.local_stored_cap_a.setText("-")
        if hasattr(self, "local_stored_cap_b"):
            self.local_stored_cap_b.setText("-")

    def update_timestamp(self):
        """Update the timestamp label with current time."""
        if hasattr(self, "timestamp_label"):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.timestamp_label.setText(current_time)
            self.timestamp_label.setStyleSheet(
                "color: #888888; font-size: 9pt;"
            )

        QTimer.singleShot(1000, self.update_timestamp)

    def update_piezo_readbacks(self, piezo) -> None:
        """No-op: PyDM widgets are the source of truth for readbacks."""
        return

    @pyqtSlot()
    def toggle_piezo_enable(self):
        """Toggle piezo enable/disable state."""
        self.log_message("Use the PyDM enable control for PV writes")

    @pyqtSlot()
    def toggle_manual_mode(self):
        """Toggle manual/feedback mode."""
        self.log_message("Use the PyDM mode control for PV writes")

    @pyqtSlot()
    def on_run_automated_test(self):
        """Handle Run Automated Test button click."""
        self.controller.on_run_automated_test()

    @pyqtSlot()
    def on_abort(self):
        """Handle abort button click."""
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        """Handle pause button click."""
        self.controller.on_pause_test()

    @pyqtSlot()
    def on_toggle_step_mode(self):
        """Handle step mode toggle."""
        self.controller.on_toggle_step_mode()

    @pyqtSlot()
    def on_next_step(self):
        """Handle next step button click."""
        self.controller.on_next_step()


class ColdLandingDisplay(BasePlaceholderDisplay):
    """Display for Cold Landing phase."""

    UI_CLASS = ColdLandingUI
    PHASE_NAME = "Cold Landing"
    DATA_ATTR = "cold_landing"
    DATA_MODEL = ColdLandingData


class SSACharDisplay(BasePlaceholderDisplay):
    """Display for SSA Characterization phase."""

    UI_CLASS = SSACharUI
    PHASE_NAME = "SSA Characterization"
    DATA_ATTR = "ssa_char"
    DATA_MODEL = SSACharacterization


class CavityCharDisplay(BasePlaceholderDisplay):
    """Display for Cavity Characterization phase."""

    UI_CLASS = CavityCharUI
    PHASE_NAME = "Cavity Characterization"
    DATA_ATTR = "cavity_char"
    DATA_MODEL = CavityCharacterization


class PiezoWithRFDisplay(BasePlaceholderDisplay):
    """Display for Piezo with RF phase."""

    UI_CLASS = PiezoWithRFUI
    PHASE_NAME = "Piezo with RF"
    DATA_ATTR = "piezo_with_rf"
    DATA_MODEL = PiezoWithRFTest


class HighPowerDisplay(BasePlaceholderDisplay):
    """Display for High Power Ramp phase."""

    UI_CLASS = HighPowerUI
    PHASE_NAME = "High Power Ramp"
    DATA_ATTR = "high_power"
    DATA_MODEL = HighPowerRampData


# ---------------------------------------------------------------------------
# Phase display registry
# ---------------------------------------------------------------------------
# Maps CommissioningPhase values to their specialised display class.
# Any phase NOT listed here falls back to a dynamically-created subclass of
# BasePlaceholderDisplay that uses GenericPhaseUI.
#
# To add a custom screen for a new phase, just insert an entry here.

PHASE_DISPLAY_MAP: dict[CommissioningPhase, type[BasePlaceholderDisplay]] = {
    CommissioningPhase.PIEZO_PRE_RF: PiezoPreRFDisplay,
    CommissioningPhase.COLD_LANDING: ColdLandingDisplay,
    CommissioningPhase.SSA_CHAR: SSACharDisplay,
    CommissioningPhase.CAVITY_CHAR: CavityCharDisplay,
    CommissioningPhase.PIEZO_WITH_RF: PiezoWithRFDisplay,
    CommissioningPhase.HIGH_POWER: HighPowerDisplay,
}


def get_phase_display_class(
    phase: CommissioningPhase,
    display_label: str,
    record_attr: str,
    data_model,
) -> type[BasePlaceholderDisplay]:
    """Return a display class for *phase*, creating a generic one if needed.

    Looks up ``PHASE_DISPLAY_MAP`` first.  If the phase has no entry a new
    ``BasePlaceholderDisplay`` subclass is created on the fly using
    ``GenericPhaseUI`` so that newly registered phases get a working (though
    un-specialised) screen automatically.

    Args:
        phase:         The ``CommissioningPhase`` enum value.
        display_label: Human-readable tab title (used as ``PHASE_NAME``).
        record_attr:   Attribute name on ``CommissioningRecord``.
        data_model:    Dataclass type for phase results (may be ``None``).

    Returns:
        A concrete subclass of ``BasePlaceholderDisplay``.
    """
    if phase in PHASE_DISPLAY_MAP:
        return PHASE_DISPLAY_MAP[phase]

    # Dynamically build a display class for unregistered phases so callers
    # always get a usable widget without manual boilerplate.
    class_name = (
        "".join(word.capitalize() for word in phase.value.split("_"))
        + "Display"
    )
    return type(
        class_name,
        (BasePlaceholderDisplay,),
        {
            "UI_CLASS": GenericPhaseUI,
            "PHASE_NAME": display_label,
            "DATA_ATTR": record_attr or "",
            "DATA_MODEL": data_model,
        },
    )
