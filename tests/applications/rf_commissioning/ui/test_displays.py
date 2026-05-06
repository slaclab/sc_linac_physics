"""Tests for BasePlaceholderDisplay, PhaseDisplayBase, and display registry."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtWidgets import QLabel, QProgressBar

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    FrequencyTuningData,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.base_placeholder import (
    BasePlaceholderDisplay,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (
    PHASE_DISPLAY_MAP,
    get_phase_display_class,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.standard import (
    FrequencyTuningDisplay,
    SSACharDisplay,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="01", cavity_number=1)


@pytest.fixture
def session(record, tmp_path):
    s = CommissioningSession(db_path=str(tmp_path / "test.db"))
    s._active_record = record
    s._active_record_id = 1
    return s


# =============================================================================
# PhaseDisplayBase
# =============================================================================


class TestPhaseDisplayBase:
    def test_init_stores_session(self, qtbot, tmp_path):
        s = CommissioningSession(db_path=str(tmp_path / "test.db"))
        w = PhaseDisplayBase(session=s)
        qtbot.addWidget(w)
        assert w.session is s

    def test_init_without_session(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        assert w.session is None

    def test_set_session(self, qtbot, tmp_path):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        s = CommissioningSession(db_path=str(tmp_path / "test.db"))
        w.set_session(s)
        assert w.session is s

    def test_refresh_from_record_is_noop(self, qtbot, record):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        assert w.refresh_from_record(record) is None

    def test_on_phase_completed_is_noop(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        assert w.on_phase_completed() is None

    def test_get_current_cavity_with_active_record(
        self, qtbot, session, record
    ):
        w = PhaseDisplayBase(session=session)
        qtbot.addWidget(w)
        result = w.get_current_cavity()
        assert result == (record.short_cavity_name, record.cryomodule)

    def test_get_current_cavity_without_session(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        assert w.get_current_cavity() is None

    def test_get_current_cavity_empty_session(self, qtbot, tmp_path):
        s = CommissioningSession(db_path=str(tmp_path / "test.db"))
        w = PhaseDisplayBase(session=s)
        qtbot.addWidget(w)
        assert w.get_current_cavity() is None

    def test_log_message_with_history_widget(self, qtbot):
        from PyQt5.QtWidgets import QTextEdit

        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.history_text = QTextEdit()
        w.log_message("hello")
        assert "hello" in w.history_text.toPlainText()

    def test_log_message_without_history_widget(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.log_message("should not raise")

    def test_update_timestamp_with_label(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.timestamp_label = QLabel()
        w.update_timestamp()
        assert "Last Updated:" in w.timestamp_label.text()

    def test_update_timestamp_without_label(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.update_timestamp()

    def test_bind_ui_widgets(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        label = QLabel("x")
        w.ui = SimpleNamespace(widgets={"my_label": label})
        w._bind_ui_widgets()
        assert w.my_label is label

    def test_bind_ui_widgets_no_ui(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w._bind_ui_widgets()

    def test_on_step_progress_updates_widgets(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.local_current_step = QLabel()
        bar = QProgressBar()
        w.local_progress_bar = bar
        w.log_message = MagicMock()
        w._on_step_progress("tuning", 42)
        assert w.local_current_step.text() == "tuning"
        assert bar.value() == 42

    def test_on_step_progress_without_widgets(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w._on_step_progress("step", 10)

    @patch(
        "sc_linac_physics.applications.rf_commissioning.ui.phase_display_base.QMessageBox.critical"
    )
    def test_show_error(self, mock_crit, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.show_error("oops")
        mock_crit.assert_called_once()

    @patch(
        "sc_linac_physics.applications.rf_commissioning.ui.phase_display_base.QMessageBox.information"
    )
    def test_show_info(self, mock_info, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        w.show_info("Title", "body")
        mock_info.assert_called_once()

    def test_notify_parent_walks_hierarchy(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        # No parent — should not raise
        w._notify_parent_of_record_update(MagicMock(), "msg")

    def test_get_current_operator_no_parent(self, qtbot):
        w = PhaseDisplayBase()
        qtbot.addWidget(w)
        assert w.get_current_operator() is None


# =============================================================================
# BasePlaceholderDisplay (via FrequencyTuningDisplay / SSACharDisplay)
# =============================================================================


@pytest.fixture
def freq_display(qtbot, tmp_path):
    s = CommissioningSession(db_path=str(tmp_path / "freq.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        d = FrequencyTuningDisplay(session=s)
        qtbot.addWidget(d)
        return d


@pytest.fixture
def ssa_display(qtbot, tmp_path):
    s = CommissioningSession(db_path=str(tmp_path / "ssa.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        d = SSACharDisplay(session=s)
        qtbot.addWidget(d)
        return d


class TestBasePlaceholderDisplay:
    def test_init_sets_window_title(self, freq_display):
        assert "Frequency Tuning" in freq_display.windowTitle()

    def test_init_uses_provided_session(self, freq_display):
        assert isinstance(freq_display.session, CommissioningSession)

    def test_refresh_from_record_no_data(self, freq_display, record):
        freq_display.refresh_from_record(record)

    def test_on_record_loaded_no_data(self, freq_display, record):
        freq_display.on_record_loaded(record, 1)

    def test_update_phase_data_readouts_with_data(self, freq_display, record):
        record.frequency_tuning = FrequencyTuningData()
        freq_display._update_phase_data_readouts(record)

    def test_update_phase_data_readouts_none_data(self, freq_display, record):
        record.frequency_tuning = None
        freq_display._update_phase_data_readouts(record)

    def test_clear_results(self, freq_display):
        freq_display.clear_results()

    def test_get_phase_stored_field_specs_with_model(self, freq_display):
        specs = FrequencyTuningDisplay.get_phase_stored_field_specs()
        assert isinstance(specs, list)

    def test_get_phase_stored_field_specs_no_model(self):
        class NoModel(BasePlaceholderDisplay):
            DATA_MODEL = None

        assert NoModel.get_phase_stored_field_specs() == []

    def test_format_spec_value_none(self, freq_display):
        assert freq_display._format_spec_value(None, SimpleNamespace()) == "-"

    def test_format_spec_value_bool_true(self, freq_display):
        spec = SimpleNamespace(true_text="YES", false_text="NO")
        assert freq_display._format_spec_value(True, spec) == "YES"

    def test_format_spec_value_bool_false(self, freq_display):
        spec = SimpleNamespace(true_text="YES", false_text="NO")
        assert freq_display._format_spec_value(False, spec) == "NO"

    def test_format_spec_value_datetime(self, freq_display):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        spec = SimpleNamespace()
        result = freq_display._format_spec_value(dt, spec)
        assert "2024-01-15" in result

    def test_format_spec_value_float_with_fmt(self, freq_display):
        spec = SimpleNamespace(format_spec=".2f", unit="Hz")
        result = freq_display._format_spec_value(3.14159, spec)
        assert "3.14" in result
        assert "Hz" in result

    def test_format_spec_value_float_no_fmt(self, freq_display):
        spec = SimpleNamespace(format_spec=None, unit="")
        result = freq_display._format_spec_value(1.5, spec)
        assert "1.5" in result

    def test_format_spec_value_int_with_unit(self, freq_display):
        spec = SimpleNamespace(format_spec=None, unit="ms")
        result = freq_display._format_spec_value(42, spec)
        assert "42" in result
        assert "ms" in result

    def test_format_spec_value_string(self, freq_display):
        spec = SimpleNamespace(format_spec=None, unit=None)
        assert freq_display._format_spec_value("hello", spec) == "hello"

    def test_stored_status_presentation_passed(self, freq_display):
        data = SimpleNamespace(passed=True)
        text, style = freq_display._get_stored_status_presentation(data)
        assert text == "PASS"

    def test_stored_status_presentation_failed(self, freq_display):
        data = SimpleNamespace(passed=False)
        text, style = freq_display._get_stored_status_presentation(data)
        assert text == "FAIL"

    def test_stored_status_presentation_complete(self, freq_display):
        data = SimpleNamespace(is_complete=True)
        text, style = freq_display._get_stored_status_presentation(data)
        assert text == "COMPLETE"

    def test_stored_status_presentation_incomplete(self, freq_display):
        data = SimpleNamespace(is_complete=False)
        text, style = freq_display._get_stored_status_presentation(data)
        assert text == "INCOMPLETE"

    def test_stored_status_presentation_available(self, freq_display):
        data = SimpleNamespace()
        text, _ = freq_display._get_stored_status_presentation(data)
        assert text == "AVAILABLE"

    def test_fmt_float_none(self):
        assert BasePlaceholderDisplay._fmt_float(None) == "-"

    def test_fmt_float_with_unit(self):
        result = BasePlaceholderDisplay._fmt_float(1.234, ".2f", "kHz")
        assert "1.23" in result
        assert "kHz" in result

    def test_fmt_float_no_unit(self):
        result = BasePlaceholderDisplay._fmt_float(2.5)
        assert "2.500" in result

    def test_fmt_timestamp_none(self):
        assert BasePlaceholderDisplay._fmt_timestamp(None) == "-"

    def test_fmt_timestamp_value(self):
        dt = datetime(2024, 6, 1, 12, 0, 0)
        assert (
            BasePlaceholderDisplay._fmt_timestamp(dt) == "2024-06-01 12:00:00"
        )

    @patch(
        "sc_linac_physics.applications.rf_commissioning.ui.phase_display_base.QMessageBox.critical"
    )
    def test_on_run_automated_test_no_operator(self, mock_crit, freq_display):
        freq_display.on_run_automated_test()
        mock_crit.assert_called_once()

    @patch(
        "sc_linac_physics.applications.rf_commissioning.ui.phase_display_base.QMessageBox.critical"
    )
    def test_on_run_automated_test_no_cavity(self, mock_crit, freq_display):
        freq_display.get_current_operator = lambda: "operator1"
        freq_display.on_run_automated_test()
        mock_crit.assert_called_once()

    def test_on_run_automated_test_with_operator_and_cavity(self, freq_display):
        freq_display.get_current_operator = lambda: "op1"
        freq_display.get_current_cavity = lambda: ("01_CAV1", "01")
        freq_display.on_run_automated_test()


# =============================================================================
# Display registry
# =============================================================================


class TestDisplayRegistry:
    def test_known_phase_returns_mapped_class(self):
        cls = get_phase_display_class(
            CommissioningPhase.FREQUENCY_TUNING,
            "Frequency Tuning",
            "frequency_tuning",
            FrequencyTuningData,
        )
        assert cls is FrequencyTuningDisplay

    def test_unknown_phase_generates_class_dynamically(self, qtbot):
        cls = get_phase_display_class(
            CommissioningPhase.PIEZO_PRE_RF,
            "Piezo Pre-RF",
            "piezo_pre_rf",
            None,
        )
        assert issubclass(cls, BasePlaceholderDisplay)
        assert cls.PHASE_NAME == "Piezo Pre-RF"
        assert cls.DATA_ATTR == "piezo_pre_rf"

    def test_unknown_phase_class_name_is_camel_case(self):
        cls = get_phase_display_class(
            CommissioningPhase.PIEZO_PRE_RF, "label", "attr", None
        )
        assert cls.__name__ == "PiezoPreRfDisplay"

    def test_all_standard_phases_in_map(self):
        standard_phases = [
            CommissioningPhase.FREQUENCY_TUNING,
            CommissioningPhase.SSA_CHAR,
            CommissioningPhase.CAVITY_CHAR,
            CommissioningPhase.PIEZO_WITH_RF,
            CommissioningPhase.HIGH_POWER_RAMP,
            CommissioningPhase.MP_PROCESSING,
            CommissioningPhase.ONE_HOUR_RUN,
        ]
        for phase in standard_phases:
            assert phase in PHASE_DISPLAY_MAP
