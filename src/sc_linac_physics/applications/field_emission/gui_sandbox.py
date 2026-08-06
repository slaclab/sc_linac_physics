import sys
import math
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QSpacerItem,
    QScrollArea,
    QWidget,
    QAbstractItemView,
)
from pydm import Display, PyDMApplication
from matplotlib.figure import Figure
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import (
    NavigationToolbar2QT as NavigationToolbar,
)
from sc_linac_physics.applications.field_emission.measurements import (
    match_measurement_dates,
    fetch_measurement_metadata,
    find_dataframes,
)
from sc_linac_physics.applications.field_emission.plot_me import plot_amp_vs_rad

# LINAC CONFIGURATION
VALID_LINACS = {0, 1, 2, 3}
VALID_CMS = {key: LINAC_CM_DICT[key] for key in VALID_LINACS}


class FieldEmission(Display):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("LCLS-II Field Emission")

        self.cryo_dropdown = None
        self.cavity_cb = None
        self.sel_all_cav_btn = None
        self.cavity_dropdown = None
        self._current_measurements = [None]
        self._selected_rows = [None]
        self.meas_list_widget = None
        # self.meas_dropdown = None
        self.meas_date_label = None
        self.meas_start_label = None
        self.meas_end_label = None
        self.meas_dec_label = None
        self.meas_notes_label = None
        self.meas_elog_label = None
        self.dec_dropdown = None
        self.readout_dropdown = None
        self.sel_all_rad_btn = None
        self.rad_chan_cb = None
        self.radio_amp_rad_btn = None
        self.radio_fit_btn = None
        self.plot_btn = None
        self.fig = None
        self.toolbar = None
        self.canvas = None

        outer = QHBoxLayout()
        self.setLayout(outer)

        # Configure main panels as widgets
        left_side = QWidget()
        left_side_layout = QVBoxLayout()
        left_side_layout.setContentsMargins(0, 0, 0, 0)
        left_side.setLayout(left_side_layout)

        right_side = QWidget()
        right_side_layout = QVBoxLayout()
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side.setLayout(right_side_layout)

        # Left panel layout
        left_side_layout.addWidget(self.build_linac_configuration())
        left_side_layout.addWidget(self.build_meas_selection())
        left_side_layout.addWidget(self.build_decarad_configuration())
        left_side_layout.addLayout(self.build_radio_buttons())
        left_side_layout.addWidget(self.build_plot_button())

        # Right panel layout
        right_side_layout.addItem(
            QSpacerItem(0, 15, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )
        canvas_build = self.build_plot_canvas()
        right_side_layout.addWidget(self.build_toolbar())
        right_side_layout.addWidget(canvas_build)

        outer.addWidget(left_side, stretch=3)  # 30% width
        outer.addWidget(right_side, stretch=7)  # 70% width

        self.connect_signals()

    def connect_signals(self):
        self.cryo_dropdown.currentTextChanged.connect(
            self.on_cryomodule_updated
        )
        for checkbox in self.cavity_cb:
            checkbox.toggled.connect(self.update_sel_all_cav_btn_label)
            checkbox.toggled.connect(self.on_cb_clicked)
        self.sel_all_cav_btn.clicked.connect(self.on_sel_all_cav_btn_clicked)
        self.meas_list_widget.itemClicked.connect(self.on_measurement_updated)
        # self.meas_dropdown.currentTextChanged.connect(self.on_measurement_updated)
        for checkbox in self.rad_chan_cb:
            checkbox.toggled.connect(self.update_sel_all_rad_btn_label)
            checkbox.toggled.connect(self.on_cb_clicked)
        self.sel_all_rad_btn.clicked.connect(self.on_sel_all_rad_btn_clicked)
        self.plot_btn.clicked.connect(self.on_plot_btn_clicked)

    def _checkbox_helper(self, labels, cols):
        grid_layout = QGridLayout()
        checkboxes = []
        for i, label in enumerate(labels):
            cb = QCheckBox(label)
            row, col = divmod(i, cols)
            grid_layout.addWidget(cb, row, col)
            checkboxes.append(cb)
        return grid_layout, checkboxes

    def _update_btn_label_helper(self, cb_list, button, label):
        any_unchecked = any(not cb.isChecked() for cb in cb_list)
        if any_unchecked:
            button.setText(f"Select All {label}")
        else:
            button.setText(f"Deselect All {label}")

    def _on_btn_clicked_helper(self, cb_list):
        any_unchecked = any(not cb.isChecked() for cb in cb_list)
        for cb in cb_list:
            cb.setChecked(any_unchecked)

    def on_cb_clicked(self):
        cav_checked = any(cb.isChecked() for cb in self.cavity_cb)
        rad_checked = any(cb.isChecked() for cb in self.rad_chan_cb)
        cm_idx = self.cryo_dropdown.currentIndex()
        has_measurement = self.meas_list_widget.count() > 0
        if cav_checked and rad_checked and cm_idx > -1 and has_measurement:
            self.plot_btn.setEnabled(True)
        else:
            self.plot_btn.setEnabled(False)

    def build_linac_configuration(self):
        # Linac configuration groupbox
        linac_config = QGroupBox("Measurement Filter")
        linac_layout = QVBoxLayout()
        linac_config.setLayout(linac_layout)

        # Cryomodule Selection
        cryo_sel_layout = QHBoxLayout()
        cryo_sel_layout.addWidget(QLabel("Cryomodule"))
        self.cryo_dropdown = QComboBox()
        self.cryo_dropdown.addItems(
            [str(cm) for linac in VALID_CMS.values() for cm in linac]
        )
        self.cryo_dropdown.setCurrentIndex(-1)
        cryo_sel_layout.addWidget(self.cryo_dropdown)
        linac_layout.addLayout(cryo_sel_layout)

        # Cavity Selection
        cav_channels = QGroupBox("Cavity Selection")
        cav_layout, self.cavity_cb = self._checkbox_helper(
            [f"Cavity {i}" for i in range(1, 9)], 4
        )
        cav_channels.setLayout(cav_layout)
        linac_layout.addWidget(cav_channels)

        # Select/deselect all button
        self.sel_all_cav_btn = QPushButton("Select All Cavities")
        linac_layout.addWidget(self.sel_all_cav_btn)
        return linac_config

    def update_sel_all_cav_btn_label(self):
        self._update_btn_label_helper(
            self.cavity_cb, self.sel_all_cav_btn, "Cavities"
        )

    def on_sel_all_cav_btn_clicked(self):
        self._on_btn_clicked_helper(self.cavity_cb)

    def build_meas_selection(self):
        # Measurement Selection
        measurement_selection = QGroupBox("Available Measurements")
        measurement_layout = QVBoxLayout()
        measurement_selection.setLayout(measurement_layout)

        # TODO - listwidget
        self.meas_list_widget = QListWidget()
        # TODO - make height larger? idk
        self.meas_list_widget.setFixedHeight(70)
        self.meas_list_widget.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        measurement_layout.addWidget(self.meas_list_widget)

        # Measurement Metadata Section
        meta_data = QGroupBox("Measurement Information")
        container_layout = QVBoxLayout()
        meta_data.setLayout(container_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container_layout.addWidget(scroll)

        container = QWidget()
        meta_data_layout = QGridLayout()
        meta_data_layout.setColumnMinimumWidth(0, 90)
        container.setLayout(meta_data_layout)

        meta_data_layout.addWidget(QLabel("Date: "), 0, 0)
        self.meas_date_label = QLabel("")
        meta_data_layout.addWidget((self.meas_date_label), 0, 1, 1, 2)

        meta_data_layout.addWidget(QLabel("Start Time: "), 1, 0)
        self.meas_start_label = QLabel("")
        meta_data_layout.addWidget((self.meas_start_label), 1, 1, 1, 2)

        meta_data_layout.addWidget(QLabel("End Time: "), 2, 0)
        self.meas_end_label = QLabel("")
        meta_data_layout.addWidget((self.meas_end_label), 2, 1, 1, 2)

        meta_data_layout.addWidget(QLabel("Decarad: "), 3, 0)
        self.meas_dec_label = QLabel("")
        meta_data_layout.addWidget((self.meas_dec_label), 3, 1, 1, 2)

        meta_data_layout.addWidget(QLabel("eLog: "), 4, 0)
        self.meas_elog_label = QLabel("")
        self.meas_elog_label.setWordWrap(True)
        meta_data_layout.addWidget((self.meas_elog_label), 4, 1, 2, 2)

        meta_data_layout.addWidget(QLabel("Notes: "), 6, 0)
        self.meas_notes_label = QLabel("")
        self.meas_notes_label.setWordWrap(True)
        meta_data_layout.addWidget((self.meas_notes_label), 6, 1, 2, 2)

        scroll.setWidget(container)
        measurement_layout.addWidget(meta_data)
        return measurement_selection

    def on_cryomodule_updated(self):
        cm = self.cryo_dropdown.currentText()
        self._current_measurements = match_measurement_dates(str(cm))

        self.meas_list_widget.blockSignals(True)
        self.meas_list_widget.clear()
        self.meas_list_widget.addItems(
            meas["display"] for meas in self._current_measurements
        )
        self.meas_list_widget.setCurrentRow(
            0 if self._current_measurements else -1
        )
        self.meas_list_widget.blockSignals(False)

        self.on_measurement_updated()
        self.on_cb_clicked()

    def on_measurement_updated(self):
        self._selected_rows = [
            self.meas_list_widget.row(item)
            for item in self.meas_list_widget.selectedItems()
        ]
        print(f"selected rows: {self._selected_rows}")
        # TODO - circular index??
        idx = self._selected_rows[-1]
        m = self._current_measurements[idx]

        if idx < 0 or not self._selected_rows:
            self.clear_metadata_labels()
            return

        labels = fetch_measurement_metadata(m["cm"], m["date"])

        if labels is None:
            self.clear_metadata_labels()
            return

        (
            date_label,
            start_label,
            end_label,
            dec_label,
            elog_label,
            notes_label,
        ) = labels

        # Populate updated metadata labels
        self.meas_date_label.setText(date_label)
        self.meas_start_label.setText(start_label)
        self.meas_end_label.setText(end_label)
        self.meas_dec_label.setText(dec_label)
        elog_link = f'<a href="{elog_label}">{elog_label}</a>'
        self.meas_elog_label.setText(elog_link)
        self.meas_elog_label.setOpenExternalLinks(True)
        self.meas_notes_label.setText(notes_label)

    def clear_metadata_labels(self):
        self.meas_date_label.setText("-")
        self.meas_start_label.setText("-")
        self.meas_end_label.setText("-")
        self.meas_dec_label.setText("-")
        self.meas_elog_label.setText("-")
        self.meas_notes_label.setText("-")

    def build_decarad_configuration(self):
        # Decarad Configuration
        decarad_config = QGroupBox("Decarad Configuration")
        decarad_config_layout = QVBoxLayout()
        decarad_config.setLayout(decarad_config_layout)

        # Radiation Readout Selection
        readout_layout = QHBoxLayout()
        readout_layout.addWidget(QLabel("Readout Type:"))
        self.readout_dropdown = QComboBox()
        self.readout_dropdown.addItems(["Average", "Instant"])
        readout_layout.addWidget(self.readout_dropdown)
        decarad_config_layout.addLayout(readout_layout)
        decarad_config_layout.addWidget(self.build_rad_channels())

        # Select/deselect all button
        self.sel_all_rad_btn = QPushButton("Select All Channels")

        decarad_config_layout.addWidget(self.sel_all_rad_btn)
        return decarad_config

    def build_rad_channels(self):
        # Decarad Channel Selection
        rad_channels = QGroupBox("Channel Selection")
        rad_channel_layout, self.rad_chan_cb = self._checkbox_helper(
            [f"Ch {i}" for i in range(1, 11)], 5
        )
        rad_channels.setLayout(rad_channel_layout)
        return rad_channels

    def update_sel_all_rad_btn_label(self):
        self._update_btn_label_helper(
            self.rad_chan_cb, self.sel_all_rad_btn, "Channels"
        )

    def on_sel_all_rad_btn_clicked(self):
        self._on_btn_clicked_helper(self.rad_chan_cb)

    def build_radio_buttons(self):
        # Buttons to choose plot style
        radio_btn_layout = QHBoxLayout()
        self.radio_amp_rad_btn = QRadioButton("Radiation vs Amplitude")
        self.radio_amp_rad_btn.setChecked(True)
        self.radio_fit_btn = QRadioButton("Fit Line")
        radio_btn_layout.addWidget(self.radio_amp_rad_btn)
        radio_btn_layout.addWidget(self.radio_fit_btn)
        return radio_btn_layout

    def build_toolbar(self):
        # Embed provided matplotlib toolbar into Qt layout
        self.toolbar = NavigationToolbar(self.canvas, self)
        return self.toolbar

    def build_plot_canvas(self):
        # Embed canvas into Qt layout
        self.fig = Figure(figsize=(5, 4))
        self.canvas = FigureCanvas(self.fig)
        return self.canvas

    def build_plot_button(self):
        # Create plot button
        self.plot_btn = QPushButton("PLOT")
        self.plot_btn.setEnabled(False)
        return self.plot_btn

    def on_plot_btn_clicked(self):
        cav = [cb.isChecked() for cb in self.cavity_cb]
        meas = [self._current_measurements[row] for row in self._selected_rows]
        readout = self.readout_dropdown.currentText()
        r_channels = [cb.isChecked() for cb in self.rad_chan_cb]
        fit = self.radio_fit_btn.isChecked()
        for m in meas:
            selected, label, n = find_dataframes(
                m["cm"], m["date"], cav, readout
            )

        # Calculate subplot rows, cols
        n = n * len(meas)
        col = math.ceil(n / 2)
        row = min(2, n)
        print(n)

        self.fig.clear()
        axes = []

        # Generate subplots
        for i, (cav_num, df) in enumerate(selected.items(), start=1):
            print(f"CAVITY {cav_num}")  # debug line
            ax = self.fig.add_subplot(row, col, i)
            plot_amp_vs_rad(df, ax, r_channels, fit)
            ax.set_title(f"Cavity {cav_num}")
            axes.append(ax)

        # Build summary legend
        all_handles = []
        all_labels = []
        for ax in axes:
            handles, labels = ax.get_legend_handles_labels()
            for h, l in zip(handles, labels):
                if l not in all_labels:
                    all_handles.append(h)
                    all_labels.append(l)

        self.fig.legend(
            all_handles, all_labels, fontsize="x-small", loc="upper right"
        )
        self.fig.suptitle(label)
        self.fig.supxlabel("Amplitude (MV)")
        self.fig.supylabel("Radiation (mR/hr)")
        self._unify_axes(axes)
        self.canvas.draw()

    def _unify_axes(self, axes):
        if not axes:
            return

        # Find the overall min/max across every subplot
        x_mins, x_maxs, y_mins, y_maxs = [], [], [], []
        for ax in axes:
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()
            x_mins.append(x_min)
            x_maxs.append(x_max)
            y_mins.append(y_min)
            y_maxs.append(y_max)

        x_range = (min(x_mins), max(x_maxs))
        y_range = (min(y_mins), max(y_maxs))

        # Apply to every subplot
        for ax in axes:
            ax.set_xlim(x_range)
            ax.set_ylim(y_range)


if __name__ == "__main__":
    app = PyDMApplication(use_main_window=False)
    window = FieldEmission()
    window.resize(1220, 900)
    window.show()

    sys.exit(app.exec())
