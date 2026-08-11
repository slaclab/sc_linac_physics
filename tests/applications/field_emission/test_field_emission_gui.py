import pytest
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QCheckBox,
    QListWidget,
    QPushButton,
    QRadioButton,
)
from unittest.mock import patch, MagicMock

from sc_linac_physics.applications.field_emission.field_emission_gui import (
    FieldEmission,
)
from sc_linac_physics.applications.field_emission import (
    field_emission_gui as feg,
)

# ---------------------------------------------------------------------------
# Sample data used to fake the external "measurements" module
# ---------------------------------------------------------------------------
SAMPLE_MEASUREMENTS = [
    {
        "cm": "01",
        "date": datetime(2024, 1, 1, 8, 0),
        "display": "2024-01-01 (CM01)",
    },
    {
        "cm": "01",
        "date": datetime(2024, 2, 2, 9, 0),
        "display": "2024-02-02 (CM01)",
    },
]

SAMPLE_METADATA = (
    "2024-01-01",  # date_label
    "08:00",  # start_label
    "10:00",  # end_label
    "Decarad 1",  # dec_label
    "http://elog.example",  # elog_label
    "Some notes",  # notes_label
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
    with (
        patch.object(
            feg,
            "match_measurement_dates",
            return_value=list(SAMPLE_MEASUREMENTS),
        ),
        patch.object(
            feg, "fetch_measurement_metadata", return_value=SAMPLE_METADATA
        ),
        patch.object(feg, "find_dataframes", return_value=({}, "label", 0)),
        patch.object(feg, "plot_amp_vs_rad"),
    ):
        widget = FieldEmission()
        qtbot.addWidget(widget)
        yield widget


def _select_rows(display, rows):
    """
    Helper: select the given row indices in the multi-select list widget
    and fire the selection handler (mirrors what itemClicked would do).
    """
    display.meas_list_widget.clearSelection()
    for r in rows:
        item = display.meas_list_widget.item(r)
        if item is not None:
            item.setSelected(True)
    display.on_measurement_updated()


# ---------------------------------------------------------------------------
# Construction / basic UI wiring
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_window_title(self, display):
        assert display.windowTitle() == "LCLS-II Field Emission"

    def test_widgets_exist(self, display):
        assert isinstance(display.cryo_dropdown, QComboBox)
        # meas selection is now a multi-select list widget, not a combo box
        assert isinstance(display.meas_list_widget, QListWidget)
        assert isinstance(display.readout_dropdown, QComboBox)
        assert isinstance(display.sel_all_cav_btn, QPushButton)
        assert isinstance(display.sel_all_rad_btn, QPushButton)
        assert isinstance(display.plot_btn, QPushButton)
        assert isinstance(display.radio_amp_rad_btn, QRadioButton)
        assert isinstance(display.radio_fit_btn, QRadioButton)

    def test_meas_list_is_multiselect(self, display):
        from PyQt5.QtWidgets import QAbstractItemView

        assert (
            display.meas_list_widget.selectionMode()
            == QAbstractItemView.ExtendedSelection
        )

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
        items = [
            display.readout_dropdown.itemText(i)
            for i in range(display.readout_dropdown.count())
        ]
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
        qtbot.mouseClick(display.sel_all_cav_btn, Qt.LeftButton)
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
#
# NOTE: enable requires cav checked AND rad checked AND cm index > -1
#       AND meas_list_widget.count() > 0.
# ---------------------------------------------------------------------------
class TestPlotButtonEnableLogic:
    def _prime_selection(self, display):
        """Set cryomodule so the measurement list gets populated (count > 0)."""
        display.cryo_dropdown.setCurrentIndex(
            0
        )  # triggers on_cryomodule_updated

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
        with patch.object(
            feg,
            "match_measurement_dates",
            return_value=list(SAMPLE_MEASUREMENTS),
        ) as mock_match:
            display.cryo_dropdown.setCurrentIndex(0)
            mock_match.assert_called_once()
            items = [
                display.meas_list_widget.item(i).text()
                for i in range(display.meas_list_widget.count())
            ]
            assert items == [m["display"] for m in SAMPLE_MEASUREMENTS]

    def test_stores_current_measurements(self, display):
        with patch.object(
            feg,
            "match_measurement_dates",
            return_value=list(SAMPLE_MEASUREMENTS),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display._current_measurements == SAMPLE_MEASUREMENTS

    def test_populated_list_selects_first_row(self, display):
        with patch.object(
            feg,
            "match_measurement_dates",
            return_value=list(SAMPLE_MEASUREMENTS),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            # code sets current row to 0 when measurements exist
            assert display.meas_list_widget.currentRow() == 0

    def test_empty_measurements_sets_row_negative(self, display):
        with patch.object(feg, "match_measurement_dates", return_value=[]):
            display.cryo_dropdown.setCurrentIndex(0)
            assert display.meas_list_widget.count() == 0
            assert display.meas_list_widget.currentRow() == -1


# ---------------------------------------------------------------------------
# on_measurement_updated + clear_metadata_labels
# ---------------------------------------------------------------------------
class TestMeasurementUpdated:
    def test_populates_metadata_labels(self, display):
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "fetch_measurement_metadata", return_value=SAMPLE_METADATA
            ),
        ):
            display.cryo_dropdown.setCurrentIndex(0)  # selects row 0 by default
            _select_rows(display, [0])
            assert display.meas_date_label.text() == "2024-01-01"
            assert display.meas_start_label.text() == "08:00"
            assert display.meas_end_label.text() == "10:00"
            assert display.meas_dec_label.text() == "Decarad 1"
            assert "http://elog.example" in display.meas_elog_label.text()
            assert display.meas_notes_label.text() == "Some notes"

    def test_elog_label_is_html_link(self, display):
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "fetch_measurement_metadata", return_value=SAMPLE_METADATA
            ),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])
            assert display.meas_elog_label.text().startswith("<a href=")
            assert display.meas_elog_label.openExternalLinks() is True

    def test_metadata_none_clears_labels(self, display):
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(feg, "fetch_measurement_metadata", return_value=None),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])
            assert display.meas_date_label.text() == "-"
            assert display.meas_notes_label.text() == "-"

    def test_no_selection_clears_labels(self, display):
        """With nothing selected, on_measurement_updated clears the labels."""
        with patch.object(
            feg,
            "match_measurement_dates",
            return_value=list(SAMPLE_MEASUREMENTS),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            display.meas_list_widget.clearSelection()
            display.on_measurement_updated()
            assert display.meas_date_label.text() == "-"

    def test_last_selected_row_drives_metadata(self, display):
        """When multiple rows are selected, metadata reflects the last row."""

        def fake_meta(cm, date):
            # Return a distinguishable date_label based on which measurement
            return (str(date), "s", "e", "d", "http://x", "n")

        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "fetch_measurement_metadata", side_effect=fake_meta
            ),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0, 1])
            # idx = self._selected_rows[-1] -> row 1 -> second measurement's date
            assert display.meas_date_label.text() == str(
                SAMPLE_MEASUREMENTS[1]["date"]
            )

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
# _fetch_plot_data
# ---------------------------------------------------------------------------
class TestFetchPlotData:
    def test_empty_when_no_measurement(self, display):
        result = display._fetch_plot_data([True], [], "Average")
        assert result == {}

    def test_empty_when_no_cavity_checked(self, display):
        result = display._fetch_plot_data(
            [False] * 8, list(SAMPLE_MEASUREMENTS), "Average"
        )
        assert result == {}

    def test_one_result_per_measurement(self, display):
        selected = {1: MagicMock()}
        with patch.object(
            feg, "find_dataframes", return_value=(selected, "Label", 1)
        ) as mock_find:
            result = display._fetch_plot_data(
                [True] + [False] * 7, list(SAMPLE_MEASUREMENTS), "Average"
            )
        assert isinstance(result, list)
        assert len(result) == 2  # two measurements -> two results
        assert mock_find.call_count == 2
        for r in result:
            assert set(r.keys()) == {"measurement", "dataframes", "label"}

    def test_forwards_args_to_find_dataframes(self, display):
        selected = {1: MagicMock()}
        cav = [True, False, True] + [False] * 5
        with patch.object(
            feg, "find_dataframes", return_value=(selected, "Label", 1)
        ) as mock_find:
            display._fetch_plot_data(cav, [SAMPLE_MEASUREMENTS[0]], "Instant")
        cm_arg, date_arg, cav_arg, readout_arg = mock_find.call_args.args
        assert cm_arg == "01"
        assert date_arg == SAMPLE_MEASUREMENTS[0]["date"]
        assert cav_arg == cav
        assert readout_arg == "Instant"


# ---------------------------------------------------------------------------
# _plot_one_date
# ---------------------------------------------------------------------------
class TestPlotOneDate:
    def _measurement_result(self, n_cavs, label="My Label"):
        return {
            "measurement": SAMPLE_MEASUREMENTS[0],
            "dataframes": {
                i: MagicMock(name=f"df{i}") for i in range(1, n_cavs + 1)
            },
            "label": label,
        }

    def test_one_subplot_and_plot_call_per_cavity(self, display):
        result = self._measurement_result(4)
        with patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            axes, title = display._plot_one_date(result, [True] * 10, False)
        assert len(axes) == 4
        assert mock_plot.call_count == 4
        assert len(display.fig.axes) == 4

    def test_returns_label_as_title(self, display):
        result = self._measurement_result(1, label="Some Title")
        with patch.object(feg, "plot_amp_vs_rad"):
            axes, title = display._plot_one_date(result, [True] * 10, False)
        assert title == "Some Title"

    def test_subplot_titles_name_cavities(self, display):
        result = self._measurement_result(2)
        with patch.object(feg, "plot_amp_vs_rad"):
            axes, _ = display._plot_one_date(result, [True] * 10, False)
        titles = [ax.get_title() for ax in axes]
        assert titles == ["Cavity 1", "Cavity 2"]

    def test_fit_flag_forwarded(self, display):
        result = self._measurement_result(1)
        with patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            display._plot_one_date(result, [True] * 10, True)
        args = mock_plot.call_args.args
        # signature: plot_amp_vs_rad(df, ax, r_channels, fit)
        assert args[-1] is True


# ---------------------------------------------------------------------------
# _plot_multiple_dates
# ---------------------------------------------------------------------------
class TestPlotMultipleDates:
    def _results(self, cav_maps, label="Multi Label"):
        """cav_maps: list of {cav_num: df} dicts, one per measurement."""
        out = []
        for i, cav_map in enumerate(cav_maps):
            out.append(
                {
                    "measurement": SAMPLE_MEASUREMENTS[i],
                    "dataframes": cav_map,
                    "label": label,
                }
            )
        return out

    def test_grid_is_cavities_by_measurements(self, display):
        # 2 measurements, cavities {1,2} union {2,3} = {1,2,3}
        results = self._results(
            [
                {1: MagicMock(), 2: MagicMock()},
                {2: MagicMock(), 3: MagicMock()},
            ]
        )
        with patch.object(feg, "plot_amp_vs_rad"):
            axes, title = display._plot_multiple_dates(
                results, [True] * 10, False
            )
        # 3 cavities (rows) x 2 measurements (cols) = 6 subplots
        assert len(axes) == 6
        assert len(display.fig.axes) == 6
        assert title == "Multi Label"

    def test_missing_cavity_shows_no_data_text(self, display):
        # measurement 0 has cavity 1 only; measurement 1 has cavity 2 only
        df1 = MagicMock()
        df1.empty = False
        df2 = MagicMock()
        df2.empty = False
        results = self._results([{1: df1}, {2: df2}])
        with patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            axes, _ = display._plot_multiple_dates(results, [True] * 10, False)
        # union of cavities = {1, 2} -> 2 rows x 2 cols = 4 subplots
        assert len(axes) == 4
        # Only 2 of the 4 cells actually have data -> plot called twice
        assert mock_plot.call_count == 2
        # The other 2 cells should carry a "no data" annotation
        no_data_axes = [
            ax
            for ax in axes
            if any(
                getattr(t, "get_text", lambda: "")() == "no data"
                for t in ax.texts
            )
        ]
        assert len(no_data_axes) == 2

    def test_empty_dataframe_treated_as_no_data(self, display):
        empty_df = MagicMock()
        empty_df.empty = True
        results = self._results([{1: empty_df}])
        with patch.object(feg, "plot_amp_vs_rad") as mock_plot:
            axes, _ = display._plot_multiple_dates(results, [True] * 10, False)
        mock_plot.assert_not_called()
        assert any(
            any(
                getattr(t, "get_text", lambda: "")() == "no data"
                for t in ax.texts
            )
            for ax in axes
        )

    def test_subplot_titles_include_cavity_and_date(self, display):
        df = MagicMock()
        df.empty = False
        results = self._results([{1: df}])
        with patch.object(feg, "plot_amp_vs_rad"):
            axes, _ = display._plot_multiple_dates(results, [True] * 10, False)
        expected_date = SAMPLE_MEASUREMENTS[0]["date"].strftime("%m/%d %H:%M")
        assert axes[0].get_title() == f"Cavity 1 - {expected_date}"


# ---------------------------------------------------------------------------
# on_plot_btn_clicked  (integration through the branching logic)
# ---------------------------------------------------------------------------
class TestPlotButtonClicked:
    def _make_selected(self, n):
        """Return a dict mapping cavity number -> fake dataframe."""
        dfs = {}
        for i in range(1, n + 1):
            m = MagicMock(name=f"df{i}")
            m.empty = False
            dfs[i] = m
        return dfs

    def test_single_date_single_cavity_plot(self, display):
        selected = self._make_selected(1)
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "find_dataframes", return_value=(selected, "My Label", 1)
            ) as mock_find,
            patch.object(feg, "plot_amp_vs_rad") as mock_plot,
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])  # single measurement -> _plot_one_date
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)

            display.on_plot_btn_clicked()

            mock_find.assert_called_once()
            assert mock_plot.call_count == 1
            assert display.fig._suptitle.get_text() == "My Label"

    def test_single_date_multiple_cavities(self, display):
        selected = self._make_selected(4)
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "find_dataframes", return_value=(selected, "Label", 4)
            ),
            patch.object(feg, "plot_amp_vs_rad") as mock_plot,
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)

            display.on_plot_btn_clicked()

            assert mock_plot.call_count == 4
            assert len(display.fig.axes) == 4

    def test_multiple_dates_uses_multi_plot(self, display):
        selected = self._make_selected(1)
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "find_dataframes", return_value=(selected, "Label", 1)
            ) as mock_find,
            patch.object(feg, "plot_amp_vs_rad") as mock_plot,
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(
                display, [0, 1]
            )  # two measurements -> _plot_multiple_dates
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)

            display.on_plot_btn_clicked()

            # find_dataframes called once per selected measurement
            assert mock_find.call_count == 2
            # 1 cavity x 2 measurements = 2 subplots, each with data -> 2 plot calls
            assert len(display.fig.axes) == 2
            assert mock_plot.call_count == 2

    def test_fit_flag_passed_through(self, display):
        selected = self._make_selected(1)
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "find_dataframes", return_value=(selected, "Label", 1)
            ),
            patch.object(feg, "plot_amp_vs_rad") as mock_plot,
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])
            display.cavity_cb[0].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)
            display.radio_fit_btn.setChecked(True)

            display.on_plot_btn_clicked()

            # signature: plot_amp_vs_rad(df, ax, r_channels, fit)
            args = mock_plot.call_args.args
            assert args[-1] is True  # fit flag

    def test_readout_passed_to_find_dataframes(self, display):
        selected = self._make_selected(1)
        with (
            patch.object(
                feg,
                "match_measurement_dates",
                return_value=list(SAMPLE_MEASUREMENTS),
            ),
            patch.object(
                feg, "find_dataframes", return_value=(selected, "Label", 1)
            ) as mock_find,
            patch.object(feg, "plot_amp_vs_rad"),
        ):
            display.cryo_dropdown.setCurrentIndex(0)
            _select_rows(display, [0])
            display.cavity_cb[2].setChecked(True)
            display.rad_chan_cb[0].setChecked(True)
            display.readout_dropdown.setCurrentText("Instant")

            display.on_plot_btn_clicked()

            cm_arg, date_arg, cav_arg, readout_arg = mock_find.call_args.args
            assert cm_arg == "01"
            assert date_arg == SAMPLE_MEASUREMENTS[0]["date"]
            assert readout_arg == "Instant"
            assert cav_arg[2] is True  # cavity 3 checked


# ---------------------------------------------------------------------------
# _unify_legends
# ---------------------------------------------------------------------------
class TestUnifyLegends:
    def test_dedupes_labels_across_axes(self, display):
        fig = display.fig
        fig.clear()
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)
        ax1.plot([0, 1], [0, 1], label="Ch 1")
        ax1.plot([0, 1], [1, 2], label="Ch 2")
        ax2.plot([0, 1], [0, 1], label="Ch 1")  # duplicate label

        handles, labels = display._unify_legends([ax1, ax2])
        # "Ch 1" should appear only once despite being on both axes
        assert labels == ["Ch 1", "Ch 2"]
        assert len(handles) == 2

    def test_empty_axes_returns_empty(self, display):
        fig = display.fig
        fig.clear()
        ax = fig.add_subplot(1, 1, 1)
        handles, labels = display._unify_legends([ax])
        assert handles == []
        assert labels == []


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
