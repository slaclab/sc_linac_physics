import pytest
from PyQt5.QtWidgets import (
    QComboBox,
    QCheckBox,
    QPushButton,
    QRadioButton,
)
from unittest.mock import MagicMock, patch

from sc_linac_physics.applications.field_emission.field_emission_gui import FieldEmission
from sc_linac_physics.applications.field_emission import field_emission_gui as feg

"""
Unit tests for the FieldEmission PyDM Display.

Run with:  pytest -q test_field_emission.py

Requirements:
    pytest
    pytest-qt
    PyQt5
    matplotlib

NOTE:
    Replace `field_emission_display` everywhere below with the actual
    import path / module name of the script under test.
"""

# ---------------------------------------------------------------------------
# Sample data used to fake the external "measurements" module
# ---------------------------------------------------------------------------
SAMPLE_MEASUREMENTS = [
    {"cm": "01", "date": "2024-01-01", "display": "2024-01-01 (CM01)"},
    {"cm": "01", "date": "2024-02-02", "display": "2024-02-02 (CM01)"},
]

SAMPLE_METADATA = (
    "2024-01-01",               # date_label
    "08:00",                    # start_label
    "10:00",                    # end_label
    "Decarad 1",                # dec_label
    "http://elog.example",      # elog_label
    "Some notes",               # notes_label
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def display(qtbot):
    """
    Create a FieldEmission widget with all external side-effect functions
    patched out. Returns the live widget registered with qtbot.
    """
    with patch.object(feg, "match_measurement_dates", return_value=list(SAMPLE_MEASUREMENTS)), \
         patch.object(feg, "fetch_measurement_metadata", return_value=SAMPLE_METADATA), \
         patch.object(feg, "find_dataframes", return_value=({}, "label", 0)), \
         patch.object(feg, "plot_amp_vs_rad"):
        widget = FieldEmission()
        qtbot.addWidget(widget)
        yield widget


# ---------------------------------------------------------------------------
# Construction / basic UI wiring
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_window_title(self, display):
        assert display.windowTitle() == "LCLS-II Field Emission"

    def test_widgets_exist(self, display):
        assert isinstance(display.cryo_dropdown, QComboBox)
        assert isinstance(display.meas_dropdown, QComboBox)
        assert isinstance(display.readout_dropdown, QComboBox)
        assert isinstance(display.sel_all_cav_btn, QPushButton)
        assert isinstance(display.sel_all_rad_btn, QPushButton)
        assert isinstance(display.plot_btn, QPushButton)
        assert isinstance(display.radio_amp_rad_btn, QRadioButton)
        assert isinstance(display.radio_fit_btn, QRadioButton)

    def test_cavity_checkboxes_count(self, display):
        assert len(display.cavity_cb) == 8
        for i, cb in enumerate(display.cavity_cb, start=1):
            assert isinstance(cb, QCheckBox)
            assert cb.text() == f"Cavity {i}"

    def test_rad_channel_checkboxes_count(self, display):
        assert len(display.rad_chan_cb) == 10
        for i, cb in enumerate(display.rad_chan_cb, start=1):
            assert isinstance(cb, QCheckBox)
            assert cb.text() == f"Ch {i}"

    def test_readout_options(self, display):
        items = [display.readout_dropdown.itemText(i)
                 for i in range(display.readout_dropdown.count())]
        assert items == ["Average", "Instant"]

    def test_cryo_dropdown_starts_unselected(self, display):
        assert display.cryo_dropdown.currentIndex() == -1

    def test_cryo_dropdown_populated(self, display):
        # There should be at least one cryomodule listed
        assert display.cryo_dropdown.count() > 0

    def test_plot_button_disabled_initially(self, display):
        assert display.plot_btn.isEnabled() is False

    def test_default_radio_is_amp_vs_rad(self, display):
        assert display.radio_amp_rad_btn.isChecked() is True
        assert display.radio_fit_btn.isChecked() is False

    def test_canvas_and_toolbar_created(self, display):
        assert display.fig is not None
        assert display.canvas is not None
        assert display.toolbar is not None


# ---------------------------------------------------------------------------
# _checkbox_helper
# ---------------------------------------------------------------------------
class TestCheckboxHelper:
    def test_layout_and_count(self, display):
        layout, boxes = display._checkbox_helper(["a", "b", "c"], 2)
        assert len(boxes) == 3
        assert all(isinstance(b, QCheckBox) for b in boxes)
        # 3 items in 2 columns -> 2 rows
        assert layout.rowCount() == 2
        assert layout.columnCount() == 2

    def test_labels_applied(self, display):
        _, boxes = display._checkbox_helper(["x", "y"], 1)
        assert [b.text() for b in boxes] == ["x", "y"]


# ---------------------------------------------------------------------------
# Select-all / Deselect-all button label helpers
# ---------------------------------------------------------------------------
class TestSelectAllButtons:
    def test_cav_label_says_select_when_any_unchecked(self, display):
        # start: all unchecked
        display.update_sel_all_cav_btn_label()
        assert display.sel_all_cav_btn.text() == "Select All Cavities"

    def test_cav_label_says_deselect_when_all_checked(self, display):
        for cb in display.cavity_cb:
            cb.setChecked(True)
        display.update_sel_all_cav_btn_label()
        assert display.sel_all_cav_btn.text() == "Deselect All Cavities"

    def test_cav_button_selects_all(self, display):
        assert all(not cb.isChecked() for cb in display.cavity_cb)
        display.on_sel_all_cav_btn_clicked()
        assert all(cb.isChecked() for cb in display.cavity_cb)

    def test_cav_button_deselects_all(self, display):
        for cb in display.cavity_cb:
            cb.setChecked(True)
        display.on_sel_all_cav_btn_clicked()
        assert all(not cb.isChecked() for cb in display.cavity_cb)

    def test_cav_button_click_signal(self, display, qtbot):
        qtbot.mouseClick(display.sel_all_cav_btn, Qt_LeftButton())
        assert all(cb.isChecked() for cb in display.cavity_cb)

    def test_rad_label_says_select_when_any_unchecked(self, display):
        display.update_sel_all_rad_btn_label()
        assert display.sel_all_rad_btn.text() == "Select All Channels"

    def test_rad_label_says_deselect_when_all_checked(self, display):
        for cb in display.rad_chan_cb:
            cb.setChecked(True)
        display.update_sel_all_rad_btn_label()
        assert display.sel_all_rad_btn.text() == "Deselect All Channels"

    def test_rad_button_toggles_all(self, display):
        display.on_sel_all_rad_btn_clicked()
        assert all(cb.isChecked() for cb in display.rad_chan_cb)
        display.on_sel_all_rad_btn_clicked()
        assert all(not cb.isChecked() for cb in display.rad_chan_cb)


# ---------------------------------------------------------------------------
# _update_btn_label_helper and _on_btn_clicked_helper (direct unit tests)
# ---------------------------------------------------------------------------
class TestButtonHelpers:
    def test_update_label_helper_partial(self, display):
        cbs = [QCheckBox(), QCheckBox()]
        cbs[0].setChecked(True)  # one checked, one not
        btn = QPushButton()
        display._update_btn_label_helper(cbs, btn, "Widgets")
        assert btn.text() == "Select All Widgets"

    def test_update_label_helper_all_checked(self, display):
        cbs = [QCheckBox(), QCheckBox()]
        for c in cbs:
            c.setChecked(True)
        btn = QPushButton()
        display._update_btn_label_helper(cbs, btn, "Widgets")
        assert btn.text() == "Deselect All Widgets"

    def test_on_btn_clicked_helper_checks_all_when_any_unchecked(self, display):
        cbs = [QCheckBox(), QCheckBox()]
        cbs[0].setChecked(True)
        display._on_btn_clicked_helper(cbs)
        assert all(c.isChecked() for c in cbs)

    def test_on_btn_clicked_helper_unchecks_all_when_all_checked(self, display):
        cbs = [QCheckBox(), QCheckBox()]
        for c in cbs:
            c.setChecked(True)
        display._on_btn_clicked_helper(cbs)
        assert all(not c.isChecked() for c in cbs)


# ---------------------------------------------------------------------------
# on_cb_clicked -> plot button enable/disable logic
# ---------------------------------------------------------------------------
class TestPlotButtonEnableLogic:
    def _prime_selection(self, display):
        """Set cryomodule + measurement so indices are >= 0."""
        display.cryo_dropdown.setCurrentIndex(0)  # triggers on_cryomodule_updated

    def test_disabled_when_nothing_selected(self, display):
        display.on_cb_clicked()
        assert display.plot_btn.isEnabled() is False

    def test_disabled_when_only_cavity_checked(self, display):
        self._prime_selection(display)
        display.cavity_cb[0].setChecked(True)
        display.on_cb_clicked()
        assert display.plot_btn.isEnabled() is False

    def test_disabled_when_only_channel_checked(self, display):
        self._prime_selection(display)
        display.rad_chan_cb[0].setChecked(True)
        display.on_cb_clicked()
        assert display.plot_btn.isEnabled() is False

    def test_disabled_when_no_cryomodule(self, display):
        # cavity + channel checked but cryo index == -1
        display.cryo_dropdown.setCurrentIndex(-1)
        display.cavity_cb[0].setChecked(True)
        display.rad_chan_cb[0].setChecked(True)
        display.on_cb_clicked()
        assert display.plot_btn.isEnabled() is False

    def test_enabled_when_all_conditions_met(self, display):
        self._prime_selection(display)
        display.cavity_cb[0].setChecked(True)
        display.rad_chan_cb[0].setChecked(True)
        display.on_cb_clicked()
        assert display.plot_btn.isEnabled() is True


# ---------------------------------------------------------------------------
# on_cryomodule_updated
# ---------------------------------------------------------------------------
class TestCryomoduleUpdated:
    def test_populates_measurements(self, display):
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)) as mock_match:
            display.cryo_dropdown.setCurrentIndex(0)
            mock_match.assert_called_once()
            items = [display.meas_dropdown.itemText(i)
                     for i in range(display.meas_dropdown.count())]
            assert items == [m["display"] for m in SAMPLE_MEASUREMENTS]

    def test_stores_current_measurements(self, display):
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display._current_measurements == SAMPLE_MEASUREMENTS

    def test_empty_measurements_sets_index_negative(self, display):
        with patch.object(feg, "match_measurement_dates", return_value=[]):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display.meas_dropdown.count() == 0
            assert display.meas_dropdown.currentIndex() == -1


# ---------------------------------------------------------------------------
# on_measurement_updated + clear_metadata_labels
# ---------------------------------------------------------------------------
class TestMeasurementUpdated:
    def test_populates_metadata_labels(self, display):
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "fetch_measurement_metadata",
                          return_value=SAMPLE_METADATA):
            display.cryo_dropdown.setCurrentIndex(0)  # selects meas index 0
            assert display.meas_date_label.text() == "2024-01-01"
            assert display.meas_start_label.text() == "08:00"
            assert display.meas_end_label.text() == "10:00"
            assert display.meas_dec_label.text() == "Decarad 1"
            assert "http://elog.example" in display.meas_elog_label.text()
            assert display.meas_notes_label.text() == "Some notes"

    def test_elog_label_is_html_link(self, display):
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "fetch_measurement_metadata",
                          return_value=SAMPLE_METADATA):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display.meas_elog_label.text().startswith('<a href=')
            assert display.meas_elog_label.openExternalLinks() is True

    def test_metadata_none_clears_labels(self, display):
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "fetch_measurement_metadata", return_value=None):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display.meas_date_label.text() == "-"
            assert display.meas_notes_label.text() == "-"

    def test_clear_metadata_labels_sets_dashes(self, display):
        display.clear_metadata_labels()
        for lbl in (
            display.meas_date_label,
            display.meas_start_label,
            display.meas_end_label,
            display.meas_dec_label,
            display.meas_elog_label,
            display.meas_notes_label,
        ):
            assert lbl.text() == "-"


# ---------------------------------------------------------------------------
# on_plot_btn_clicked
# ---------------------------------------------------------------------------
class TestPlotButtonClicked:
    def _make_selected(self, n):
        """Return a dict mapping cavity number -> fake dataframe."""
        return {i: MagicMock(name=f"df{i}") for i in range(1, n + 1)}

    def test_single_cavity_plot(self, display):
        selected = self._make_selected(1)
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "find_dataframes",
                          return_value=(selected, "My Label", 1)) as mock_find, \
             patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            display.cryo_dropdown.setCurrentIndex(0)
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)

            display.on_plot_btn_clicked()

            mock_find.assert_called_once()
            assert mock_plot.call_count == 1
            assert display.fig._suptitle.get_text() == "My Label"

    def test_multiple_cavities_plot_called_per_cavity(self, display):
        selected = self._make_selected(4)
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "find_dataframes",
                          return_value=(selected, "Label", 4)), \
             patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            display.cryo_dropdown.setCurrentIndex(0)
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)

            display.on_plot_btn_clicked()

            assert mock_plot.call_count == 4
            # 4 cavities -> 4 subplots (axes) on the figure
            assert len(display.fig.axes) == 4

    def test_fit_flag_passed_through(self, display):
        selected = self._make_selected(1)
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "find_dataframes",
                          return_value=(selected, "Label", 1)), \
             patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            display.cryo_dropdown.setCurrentIndex(0)
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)
            display.radio_fit_btn.setChecked(True)

            display.on_plot_btn_clicked()

            # signature: plot_amp_vs_rad(df, ax, r_channels, fit)
            _, kwargs = mock_plot.call_args
            args = mock_plot.call_args.args
            assert args[-1] is True  # fit flag

    def test_readout_passed_to_find_dataframes(self, display):
        selected = self._make_selected(1)
        with patch.object(feg, "match_measurement_dates",
                          return_value=list(SAMPLE_MEASUREMENTS)), \
             patch.object(feg, "find_dataframes",
                          return_value=(selected, "Label", 1)) as mock_find, \
             patch.object(feg, "plot_amp_vs_rad"):
            display.cryo_dropdown.setCurrentIndex(0)
            display.cavity_cb[2].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)
            display.readout_dropdown.setCurrentText("Instant")

            display.on_plot_btn_clicked()

            cm_arg, date_arg, cav_arg, readout_arg = mock_find.call_args.args
            assert cm_arg == "01"
            assert date_arg == "2024-01-01"
            assert readout_arg == "Instant"
            assert cav_arg[2] is True  # cavity 3 checked


# ---------------------------------------------------------------------------
# _unify_axes
# ---------------------------------------------------------------------------
class TestUnifyAxes:
    def test_empty_axes_no_error(self, display):
        # Should simply return without raising
        assert display._unify_axes([]) is None

    def test_axes_share_common_limits(self, display):
        fig = display.fig
        fig.clear()
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)
        ax1.set_xlim(0, 10)
        ax1.set_ylim(0, 5)
        ax2.set_xlim(2, 20)
        ax2.set_ylim(1, 8)

        display._unify_axes([ax1, ax2])

        assert ax1.get_xlim() == ax2.get_xlim()
        assert ax1.get_ylim() == ax2.get_ylim()
        # Unified range is the overall min/max
        assert ax1.get_xlim() == (0.0, 20.0)
        assert ax1.get_ylim() == (0.0, 8.0)


# ---------------------------------------------------------------------------
# Signal wiring integration (checkbox toggle -> button label update)
# ---------------------------------------------------------------------------
class TestSignalWiring:
    def test_checking_cavity_updates_button_label(self, display):
        for cb in display.cavity_cb:
            cb.setChecked(True)
        # Signal should have flipped the label to "Deselect All Cavities"
        assert display.sel_all_cav_btn.text() == "Deselect All Cavities"

    def test_checking_channel_updates_button_label(self, display):
        for cb in display.rad_chan_cb:
            cb.setChecked(True)
        assert display.sel_all_rad_btn.text() == "Deselect All Channels"


# ---------------------------------------------------------------------------
# Small helper so we don't need a top-level PyQt import for the mouse button
# ---------------------------------------------------------------------------
def Qt_LeftButton():
    from PyQt5.QtCore import Qt
    return Qt.LeftButton
