"""Builds the MP Processing display UI.

Same grid as PiezoWithRFUI: toolbar and status against Stored Data, then
Settings against Live PVs. Below them, one row per quench, then Phase
History.
"""

from typing import NamedTuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QTableWidget,
    QVBoxLayout,
)
import pyqtgraph as pg
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.rf_commissioning.phases.mp_processing import (  # noqa: E501
    MPProcessingLimits,
)

from .base import PhaseUIBase
from .styles import PV_LABEL_STYLE
from .theme import (
    ACCENT_LOCAL,
    BORDER_EMPHASIS,
    COLOR_PRIMARY,
    RADIUS_MD,
    SANS_FONT_STACK,
    TEXT_MUTED,
    BG_INSET,
    BG_INTERACTIVE,
    BG_PANEL,
    BORDER,
    MONO_FONT_STACK,
    TEXT_DISABLED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

QUENCH_COLUMNS = ("#", "Time", "ADES (MV)", "Since previous (s)")

# No app-wide rule styles tables or spin boxes, so without these Qt falls
# back to the system palette: white in the dark theme.
SETTING_SPIN_STYLE = f"""
    QDoubleSpinBox {{
        background-color: {BG_INTERACTIVE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 2px 4px;
    }}
    QDoubleSpinBox:focus {{ border: 1px solid {ACCENT_LOCAL}; }}
    QDoubleSpinBox:disabled {{
        background-color: {BG_INSET};
        color: {TEXT_DISABLED};
    }}
    QComboBox {{
        background-color: {BG_INTERACTIVE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 2px 4px;
    }}
    QComboBox:focus {{ border: 1px solid {ACCENT_LOCAL}; }}
    QComboBox:disabled {{
        background-color: {BG_INSET};
        color: {TEXT_DISABLED};
    }}
    QComboBox QAbstractItemView {{
        background-color: {BG_INTERACTIVE};
        color: {TEXT_PRIMARY};
        selection-background-color: {ACCENT_LOCAL};
    }}
"""
QUENCH_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {BG_INSET};
        alternate-background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        gridline-color: {BORDER};
        border: 1px solid {BORDER};
        font-family: {MONO_FONT_STACK};
    }}
    QHeaderView::section {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 3px;
    }}
"""


QUENCH_TABS_STYLE = f"""
    QTabWidget#mpQuenchTabs::pane {{
        background-color: {BG_INSET};
        border: 1px solid {BORDER};
        border-top: none;
    }}
    QTabWidget#mpQuenchTabs > QTabBar::tab {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        padding: 4px 12px;
        border: 1px solid {BORDER};
        border-bottom: none;
        font-family: {SANS_FONT_STACK};
    }}
    QTabWidget#mpQuenchTabs > QTabBar::tab:selected {{
        background-color: {BG_INSET};
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {COLOR_PRIMARY};
    }}
    QTabWidget#mpQuenchTabs > QTabBar::tab:hover:!selected {{
        background-color: {BG_INTERACTIVE};
    }}
"""


class Setting(NamedTuple):
    """One spin box for an MPProcessingLimits field.

    The box shows field / scale: the hold at ADES_MAX is set in minutes,
    and MPProcessingLimits keeps seconds.
    """

    widget: str
    caption: str
    field: str
    unit: str
    low: float
    high: float
    step: float
    decimals: int
    scale: float = 1.0


SETTINGS = (
    Setting("start_mv_spin", "Start ADES:", "start_amplitude_mv", "MV",
            0.5, 30.0, 0.1, 2),
    Setting("step_mv_spin", "Step:", "step_mv", "MV", 0.01, 2.0, 0.05, 2),
    Setting("step_seconds_spin", "Step every:", "step_seconds", "s",
            1.0, 600.0, 1.0, 0),
    Setting("quench_hold_spin", "Hold after quench:", "quench_hold_seconds",
            "s", 5.0, 3600.0, 5.0, 0),
    Setting("stable_minutes_spin", "Hold at ADES_MAX:", "stable_seconds",
            "min", 0.5, 120.0, 0.5, 1, scale=60.0),
    # Over DECARAD_BACKGROUND_READING_RAW; see MPProcessingLimits.
    Setting("fe_pause_spin", "FE pause above:", "fe_pause_above",
            "over bkg", 0.5, 1000.0, 1.0, 1),
)  # fmt: skip
# Decarad choices on the Settings box -> MPProcessingLimits.decarad.
DECARAD_CHOICES = (("Off", None), ("1", 1), ("2", 2))


# Spin box name -> caption, for the MPProcessingData fields in FE_DATA_FIELDS.
FE_FIELDS = (
    ("fe_onset_spin", "FE onset:"),
    ("fe_50_spin", "50 mR/h sustained at:"),
)
# Spin box name -> MPProcessingData field it fills.
FE_DATA_FIELDS = {
    "fe_onset_spin": "field_emission_onset",
    "fe_50_spin": "fe_50_mr_h_amplitude",
}


class MPProcessingUI(PhaseUIBase):
    """Builds the MP Processing display UI."""

    def build(self) -> QVBoxLayout:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addLayout(self._build_main_toolbar(), 0, 0)
        grid.addWidget(self._build_status(), 1, 0)
        grid.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            ),
            0,
            1,
            2,
            1,
        )
        grid.addWidget(self._build_settings(), 2, 0)
        grid.addWidget(self._build_live_pvs(), 2, 1)
        grid.addWidget(self._build_field_emission(), 3, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        main_layout.addLayout(grid)
        # The plot needs the height more than the log does.
        main_layout.addWidget(self._build_quench_tabs(), stretch=2)
        main_layout.addWidget(self._build_history(), stretch=1)
        return main_layout

    def _build_status(self) -> QGroupBox:
        """This run, read from record.mp_processing once a second."""
        group = QGroupBox("MP Processing")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        rows = (
            ("Step:", "step_label"),
            ("Phase:", "local_phase_status"),
            ("Quenches:", "quench_count_label"),
            ("Highest ADES written:", "max_ades_label"),
            ("Since last quench:", "since_quench_label"),
            ("Decarad max:", "radiation_label"),
        )
        for row, (caption, name) in enumerate(rows):
            layout.addWidget(QLabel(caption), row, 0)
            layout.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )
        group.setLayout(layout)
        return group

    def _build_settings(self) -> QGroupBox:
        """MPProcessingLimits for the next run. Locked while one runs."""
        group = QGroupBox("Settings")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        defaults = MPProcessingLimits()
        for row, setting in enumerate(SETTINGS):
            spin = self._register(
                setting.widget, QDoubleSpinBox(parent=self.parent)
            )
            spin.setRange(setting.low, setting.high)
            spin.setSingleStep(setting.step)
            spin.setDecimals(setting.decimals)
            spin.setSuffix(f" {setting.unit}")
            spin.setStyleSheet(SETTING_SPIN_STYLE)
            spin.setValue(getattr(defaults, setting.field) / setting.scale)
            layout.addWidget(QLabel(setting.caption), row, 0)
            layout.addWidget(spin, row, 1)
        combo = self._register("decarad_combo", QComboBox(parent=self.parent))
        combo.setStyleSheet(SETTING_SPIN_STYLE)
        for text, _ in DECARAD_CHOICES:
            combo.addItem(text)
        combo.setToolTip(
            "Decarad whose GAMMA_DOSE_RATE pauses the walk. Off: no "
            "radiation pause."
        )
        layout.addWidget(QLabel("Decarad:"), len(SETTINGS), 0)
        layout.addWidget(combo, len(SETTINGS), 1)
        group.setLayout(layout)
        return group

    def _build_field_emission(self) -> QGroupBox:
        """What the operator saw on the decarad, saved with the run.

        Editable at any time, also during a run. At 0 a box reads "not
        seen" and saves None. Amplitudes are ADES, in MV.
        """
        group = QGroupBox("Field Emission (operator)")
        layout = QHBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        for widget, caption in FE_FIELDS:
            spin = self._register(widget, QDoubleSpinBox(parent=self.parent))
            spin.setRange(0.0, 30.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.setSuffix(" MV")
            spin.setSpecialValueText("not seen")
            spin.setStyleSheet(SETTING_SPIN_STYLE)
            layout.addWidget(QLabel(caption))
            layout.addWidget(spin, stretch=1)
        save = self._register("fe_save_button", QPushButton("Save FE"))
        save.setToolTip(
            "Save these to the record. A run saves them when it finishes."
        )
        # Same look as the toolbar's Next button.
        save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: white;
                padding: 4px 12px;
                border-radius: {RADIUS_MD};
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:disabled {{
                background-color: {BORDER_EMPHASIS};
                color: {TEXT_MUTED};
            }}
        """)
        save.setEnabled(False)
        layout.addWidget(save)
        watching = self._register(
            "override_radiation_button", QPushButton("I'm watching")
        )
        watching.setToolTip(
            "Stop radiation pauses for the rest of this run. Your name is "
            "recorded in the notes."
        )
        watching.setStyleSheet(save.styleSheet())
        watching.setEnabled(False)
        layout.addWidget(watching)
        group.setLayout(layout)
        return group

    def _build_live_pvs(self) -> QGroupBox:
        """Read-only PyDMLabels. MPProcessingController sets each channel."""
        group = QGroupBox("Live PVs")
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)
        # decimals: None keeps the PV's own PREC. Amplitudes show 2: the sim
        # serves ADES_MAX with PREC 0, which showed 15.8 as "16".
        # CHECK: what PREC do ADES, AACTMEAN and ADES_MAX have on production?
        rows = (
            ("ADES:", "pydm_ades", 2),
            ("AACTMEAN:", "pydm_aact", 2),
            ("ADES_MAX:", "pydm_ades_max", 2),
            ("Quench latch (QUENCH_LTCH):", "pydm_quench_latch", None),
            ("RF mode (RFMODE):", "pydm_rf_mode", None),
            ("RF state (RFSTATE):", "pydm_rf_state", None),
        )
        for row, (caption, name, decimals) in enumerate(rows):
            label = self._register(name, PyDMLabel(parent=self.parent))
            label.setStyleSheet(PV_LABEL_STYLE)
            label.setAlignment(Qt.AlignCenter)
            label.showUnits = True
            if decimals is not None:
                label.precisionFromPV = False
                label.precision = decimals
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(label, row, 1)
        group.setLayout(grid)
        return group

    def _build_quench_tabs(self) -> QTabWidget:
        """The quench table and the radiation plot share one space."""
        tabs = self._register("quench_tabs", QTabWidget(parent=self.parent))
        # Dark like the phase tabs (multi_phase_screen.py), scoped by object
        # name. Without it the tabs take the desktop's light palette.
        tabs.setObjectName("mpQuenchTabs")
        tabs.setStyleSheet(QUENCH_TABS_STYLE)
        tabs.addTab(self._build_quench_table(), "Quenches")
        tabs.addTab(self._build_radiation_tab(), "Radiation vs amplitude")
        return tabs

    def _build_radiation_tab(self) -> QWidget:
        """The plot, with a Full range box above it."""
        box = QWidget(parent=self.parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        full = self._register(
            "full_range_check", QCheckBox("Full range", parent=self.parent)
        )
        full.setToolTip(
            "Fit every reading, spikes included. Off: the axis stops above "
            "FE onset and higher readings show as triangles on the top edge."
        )
        full.setStyleSheet(f"QCheckBox {{ color: {TEXT_SECONDARY}; }}")
        layout.addWidget(full, alignment=Qt.AlignRight)
        layout.addWidget(self._build_radiation_plot(), stretch=1)
        box.setLayout(layout)
        return box

    def _build_radiation_plot(self) -> pg.PlotWidget:
        """Highest decarad head over background against AACTMEAN.

        One point per radiation reading in this run, a red cross at each
        quench and a dashed line at FE pause above. The display draws them
        from the phase once a second.
        """
        plot = self._register(
            "radiation_plot", pg.PlotWidget(parent=self.parent)
        )
        plot.setBackground(BG_INSET)
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setLabel("bottom", "AACTMEAN", units="MV")
        plot.setLabel("left", "Max head − bkg")
        for side in ("bottom", "left"):
            axis = plot.getAxis(side)
            axis.setPen(TEXT_SECONDARY)
            axis.setTextPen(TEXT_SECONDARY)
        # Top left: points start at the start ADES, so they rarely reach
        # there, and the threshold label sits at the right.
        plot.addLegend(offset=(10, 5), labelTextColor=TEXT_SECONDARY)
        plot.setMinimumHeight(80)
        return plot

    def _build_quench_table(self) -> QGroupBox:
        """One row per quench this run recorded."""
        group = QGroupBox("Quenches")
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        table = self._register(
            "quench_table", QTableWidget(0, len(QUENCH_COLUMNS))
        )
        table.setHorizontalHeaderLabels(QUENCH_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(QUENCH_TABLE_STYLE)
        table.setMinimumHeight(80)
        layout.addWidget(table)
        group.setLayout(layout)
        return group
